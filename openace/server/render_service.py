from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import soundfile as sf

from openace.core.audio import read_audio
from openace.core.diagnostics import extract_f0, write_diagnostic
from openace.core.expression import apply_dynamic_envelope
from openace.core.models import AudioClip, Project, RenderJob, RenderJobStatus, RenderMode, Track, TrackType
from openace.core.project_store import ProjectStore
from openace.engines.acestep import ACEStepEngine
from openace.engines.base import EngineUnavailable
from openace.engines.fixture import FixtureMusicEngine, FixtureVocalEngine, fixture_enabled
from openace.engines.soulx import SoulXSingerEngine
from openace.engines.vram import vram_manager

from .events import event_bus


class RenderService:
    def __init__(self, store: ProjectStore, render_root: Path):
        self.store = store
        self.render_root = Path(render_root)
        self.render_root.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, RenderJob] = {}
        if fixture_enabled():
            self.vocal_engine = FixtureVocalEngine()
            self.music_engine = FixtureMusicEngine()
            self.vocal_engine_name = "explicit CI synthesis fixture"
            self.music_engine_name = "explicit CI music fixture"
            self.fixture_mode = True
        else:
            self.vocal_engine = SoulXSingerEngine(vram=vram_manager)
            self.music_engine = ACEStepEngine(vram=vram_manager)
            self.vocal_engine_name = "SoulX-Singer"
            self.music_engine_name = "ACE-Step 1.5"
            self.fixture_mode = False

    def output_dir(self, project_id: str, job_id: str) -> Path:
        return self.render_root / project_id / job_id

    def _publish_job(self, job: RenderJob) -> None:
        event_bus.publish("render_job", job.model_dump(mode="json"))

    def _publish_project(self, project: Project) -> None:
        event_bus.publish(
            "project_updated",
            {"project_id": project.id, "project": project.model_dump(mode="json")},
        )

    def create_job(self, project_id: str, mode: RenderMode, track_id: Optional[str] = None) -> RenderJob:
        job = RenderJob(project_id=project_id, track_id=track_id, mode=mode)
        job.fixture = self.fixture_mode
        job.engine = self.vocal_engine_name if mode in {RenderMode.SVS_SCORE, RenderMode.SVC} else self.music_engine_name
        self.jobs[job.id] = job
        self._publish_job(job)
        return job

    async def run_vocal_render(self, job_id: str) -> RenderJob:
        job = self.jobs[job_id]
        job.status = RenderJobStatus.RUNNING
        job.message = f"rendering vocal with {self.vocal_engine_name}"
        job.progress = 0.05
        self._publish_job(job)
        try:
            project = self.store.get(job.project_id)
            if not job.track_id:
                raise ValueError("vocal render requires track_id")
            track = project.track(job.track_id)
            outdir = self.output_dir(project.id, job.id)
            wav = outdir / "vocal.wav"
            diagnostic = outdir / "diagnostic.png"
            await asyncio.to_thread(self.vocal_engine.render_score, project, track, wav)
            audio, sr = await asyncio.to_thread(read_audio, wav)
            audio, dynamic_applied = apply_dynamic_envelope(audio, sr, project, track)
            if dynamic_applied:
                await asyncio.to_thread(sf.write, str(wav), audio, sr, subtype="PCM_24")
                job.message = "rendered vocal with Dynamic post-processing"
            try:
                actual_f0 = await asyncio.to_thread(extract_f0, wav)
            except RuntimeError:
                actual_f0 = None
            provenance = "OPENACE_CI_SYNTH_FIXTURE=1 — ORCHESTRATION TEST AUDIO, NOT MODEL OUTPUT" if self.fixture_mode else self.vocal_engine_name
            if dynamic_applied:
                provenance += " + Dynamic lane gain post-processing (not neural conditioning)"
            await asyncio.to_thread(write_diagnostic, diagnostic, project, track.sorted_notes(), audio, sr, actual_f0, provenance)
            track.render_path = str(wav)
            track.render_revision += 1
            self.store.save(project)
            self._publish_project(project)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = "completed with Dynamic post-processing" if dynamic_applied else "completed"
            job.finished_at = time.time()
        except Exception as exc:
            job.status = RenderJobStatus.FAILED
            job.error = str(exc)
            job.message = str(exc)
            job.finished_at = time.time()
        self._publish_job(job)
        event_bus.publish("project_updated", {"project_id": job.project_id})
        return job

    async def run_music_generation(self, job_id: str, source_audio: Optional[str], caption: str, start_s: float = 0.0, end_s: float = -1.0) -> RenderJob:
        job = self.jobs[job_id]
        job.status = RenderJobStatus.RUNNING
        job.message = f"running {self.music_engine_name}"
        job.progress = 0.05
        self._publish_job(job)
        try:
            project = self.store.get(job.project_id)
            outdir = self.output_dir(project.id, job.id)
            wav = outdir / "accompaniment.wav"
            duration = project.ticks_to_seconds(project.duration_ticks())
            if job.mode == RenderMode.REPAINT:
                if not source_audio:
                    raise ValueError("repaint requires source_audio")
                await asyncio.to_thread(self.music_engine.repaint, Path(source_audio), wav, start_s, end_s, caption)
            else:
                if not source_audio:
                    raise ValueError("vocal2bgm requires source_audio")
                await asyncio.to_thread(self.music_engine.vocal_to_bgm, Path(source_audio), wav, caption, duration, project.bpm)
            audio, sr = await asyncio.to_thread(read_audio, wav)
            duration_ticks = project.seconds_to_ticks(len(audio) / sr) if sr else None
            accompaniment = next((t for t in project.tracks if t.type == TrackType.ACCOMPANIMENT), None)
            if accompaniment is None:
                accompaniment = project.add_track(
                    Track(name="ACE-Step BGM", type=TrackType.ACCOMPANIMENT, color="#2fb996")
                )
            if job.mode == RenderMode.REPAINT and accompaniment.clips:
                # Repaint returns a full-length revised accompaniment. Replacing the
                # previous clip keeps arrangement, playback, and master export consistent.
                accompaniment.clips[-1].path = str(wav)
                accompaniment.clips[-1].duration_ticks = duration_ticks
                accompaniment.clips[-1].label = "Repaint"
            else:
                accompaniment.clips.append(
                    AudioClip(
                        path=str(wav),
                        start_ticks=0,
                        duration_ticks=duration_ticks,
                        label="Repaint" if job.mode == RenderMode.REPAINT else "Vocal2BGM",
                    )
                )
            accompaniment.render_path = str(wav)
            accompaniment.render_revision += 1
            self.store.save(project)
            self._publish_project(project)
            diagnostic = outdir / "diagnostic.png"
            notes = project.vocal_tracks()[0].sorted_notes() if project.vocal_tracks() else []
            await asyncio.to_thread(write_diagnostic, diagnostic, project, notes, audio, sr)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = "completed"
            job.finished_at = time.time()
        except Exception as exc:
            job.status = RenderJobStatus.FAILED
            job.error = str(exc)
            job.message = str(exc)
            job.finished_at = time.time()
        self._publish_job(job)
        event_bus.publish("project_updated", {"project_id": job.project_id})
        return job

    async def run_svc(self, job_id: str, source_audio: str, reference_voice: str) -> RenderJob:
        job = self.jobs[job_id]
        job.status = RenderJobStatus.RUNNING
        job.message = f"running {self.vocal_engine_name} SVC"
        job.progress = 0.05
        self._publish_job(job)
        try:
            project = self.store.get(job.project_id)
            outdir = self.output_dir(project.id, job.id)
            wav = outdir / "svc.wav"
            await asyncio.to_thread(self.vocal_engine.convert_voice, Path(source_audio), Path(reference_voice), wav)
            audio, sr = await asyncio.to_thread(read_audio, wav)
            diagnostic = outdir / "diagnostic.png"
            notes = project.vocal_tracks()[0].sorted_notes() if project.vocal_tracks() else []
            await asyncio.to_thread(write_diagnostic, diagnostic, project, notes, audio, sr)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = "completed"
            job.finished_at = time.time()
        except Exception as exc:
            job.status = RenderJobStatus.FAILED
            job.error = str(exc)
            job.message = str(exc)
            job.finished_at = time.time()
        self._publish_job(job)
        return job
