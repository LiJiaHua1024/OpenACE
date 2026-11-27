from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import soundfile as sf

from openace.core.audio import read_audio
from openace.core.breath import apply_breath_events, load_reference_audio
from openace.core.diagnostics import extract_f0, write_diagnostic
from openace.core.expression import apply_air_envelope, apply_dynamic_envelope, apply_energy_envelope, apply_falsetto_envelope, apply_tension_envelope
from openace.core.models import AudioClip, Project, RenderJob, RenderJobStatus, RenderMode, Track, TrackType
from openace.core.project_store import ProjectStore
from openace.engines.acestep import ACEStepEngine
from openace.engines.base import EngineUnavailable
from openace.engines.fixture import FixtureMusicEngine, FixtureVocalEngine, fixture_enabled, fixture_separate_stems
from openace.engines.separation import DemucsStemSeparator
from openace.engines.soulx import SoulXSingerEngine
from openace.engines.vram import vram_manager

from .events import event_bus


def first_vocal_notes(project: Project):
    """Return notes from the first vocal track that actually contains notes."""
    for track in project.vocal_tracks():
        if track.notes:
            return track.sorted_notes()
    return []


class RenderService:
    def __init__(self, store: ProjectStore, render_root: Path):
        self.store = store
        self.render_root = Path(render_root)
        self.render_root.mkdir(parents=True, exist_ok=True)
        self.jobs_path = self.render_root / "jobs.json"
        self.jobs: Dict[str, RenderJob] = self._load_jobs()
        self.recovery_pending: set[str] = set()
        if fixture_enabled():
            self.vocal_engine = FixtureVocalEngine()
            self.music_engine = FixtureMusicEngine()
            self.stem_separator = None
            self.vocal_engine_name = "explicit CI synthesis fixture"
            self.music_engine_name = "explicit CI music fixture"
            self.fixture_mode = True
        else:
            self.vocal_engine = SoulXSingerEngine(vram=vram_manager)
            self.music_engine = ACEStepEngine(vram=vram_manager)
            self.stem_separator = DemucsStemSeparator()
            self.vocal_engine_name = "SoulX-Singer"
            self.music_engine_name = "ACE-Step 1.5"
            self.fixture_mode = False

    def output_dir(self, project_id: str, job_id: str) -> Path:
        return self.render_root / project_id / job_id

    def _load_jobs(self) -> Dict[str, RenderJob]:
        if not self.jobs_path.exists():
            return {}
        try:
            raw = json.loads(self.jobs_path.read_text(encoding="utf-8"))
            jobs = {item["id"]: RenderJob.model_validate(item) for item in raw}
        except Exception:
            return {}
        return jobs

    def _can_recover(self, job: RenderJob) -> bool:
        if job.mode == RenderMode.SVS_SCORE:
            return bool(job.project_id and job.track_id)
        if job.mode == RenderMode.VOCAL2BGM:
            return bool(job.source_audio)
        if job.mode == RenderMode.REPAINT:
            return bool(job.source_audio) and job.start_s is not None and job.end_s is not None
        if job.mode == RenderMode.SVC:
            return bool(job.source_audio and job.reference_voice)
        if job.mode == RenderMode.SEPARATE:
            return bool(job.source_audio)
        return False

    def recover_interrupted_jobs(self) -> List[RenderJob]:
        """Requeue durable interrupted jobs whose original inputs are recoverable."""
        recovered: List[RenderJob] = []
        changed = False
        for job in self.jobs.values():
            if job.status not in {RenderJobStatus.QUEUED, RenderJobStatus.RUNNING}:
                continue
            changed = True
            if self._can_recover(job):
                if job.id in self.recovery_pending:
                    continue
                job.status = RenderJobStatus.QUEUED
                job.progress = 0.0
                job.error = None
                job.finished_at = None
                job.message = "requeued after backend restart"
                self.recovery_pending.add(job.id)
                recovered.append(job)
            else:
                job.status = RenderJobStatus.FAILED
                job.error = "backend restarted before job completion and original inputs are unavailable for automatic requeue"
                job.message = job.error
                job.finished_at = time.time()
        if changed:
            self._persist_jobs()
        return recovered

    def recovery_coro(self, job: RenderJob):
        if job.mode == RenderMode.SVS_SCORE:
            return self.run_vocal_render(job.id)
        if job.mode in {RenderMode.VOCAL2BGM, RenderMode.REPAINT}:
            return self.run_music_generation(
                job.id,
                job.source_audio,
                job.caption,
                job.start_s if job.start_s is not None else 0.0,
                job.end_s if job.end_s is not None else -1.0,
            )
        if job.mode == RenderMode.SVC:
            return self.run_svc(job.id, job.source_audio or "", job.reference_voice or "")
        if job.mode == RenderMode.SEPARATE:
            return self.run_separation(job.id, job.source_audio or "")
        raise ValueError(f"unsupported render job mode for recovery: {job.mode}")

    def _persist_jobs(self) -> None:
        self.jobs_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([job.model_dump(mode="json") for job in self.jobs.values()], ensure_ascii=False, indent=2)
        temporary = self.jobs_path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.jobs_path)

    def _publish_job(self, job: RenderJob) -> None:
        self._persist_jobs()
        event_bus.publish("render_job", job.model_dump(mode="json"))

    def _publish_project(self, project: Project) -> None:
        event_bus.publish(
            "project_updated",
            {"project_id": project.id, "project": project.model_dump(mode="json")},
        )

    def create_job(
        self,
        project_id: str,
        mode: RenderMode,
        track_id: Optional[str] = None,
        source_audio: Optional[str] = None,
        reference_voice: Optional[str] = None,
        caption: str = "",
        start_s: Optional[float] = None,
        end_s: Optional[float] = None,
    ) -> RenderJob:
        job = RenderJob(
            project_id=project_id,
            track_id=track_id,
            mode=mode,
            source_audio=source_audio,
            reference_voice=reference_voice,
            caption=caption,
            start_s=start_s,
            end_s=end_s,
        )
        job.fixture = self.fixture_mode
        job.engine = self.vocal_engine_name if mode in {RenderMode.SVS_SCORE, RenderMode.SVC} else ("Demucs" if mode == RenderMode.SEPARATE and not self.fixture_mode else self.music_engine_name)
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
            reference_audio, reference_sr = await asyncio.to_thread(load_reference_audio, track.reference_voice_path)
            audio, breath_result = await asyncio.to_thread(
                apply_breath_events,
                audio,
                sr,
                project,
                track,
                reference_audio,
                reference_sr,
            )
            audio, dynamic_applied = apply_dynamic_envelope(audio, sr, project, track)
            audio, air_applied = apply_air_envelope(audio, sr, project, track)
            audio, energy_applied = apply_energy_envelope(audio, sr, project, track)
            audio, tension_applied = apply_tension_envelope(audio, sr, project, track)
            audio, falsetto_applied = apply_falsetto_envelope(audio, sr, project, track)
            applied_lanes = [
                name
                for name, applied in (
                    ("Dynamic", dynamic_applied),
                    ("Air", air_applied),
                    ("Energy", energy_applied),
                    ("Tension", tension_applied),
                    ("Falsetto", falsetto_applied),
                )
                if applied
            ]
            if applied_lanes or breath_result.applied:
                await asyncio.to_thread(sf.write, str(wav), audio, sr, subtype="PCM_24")
                job.message = f"rendered vocal with {'/'.join(applied_lanes)} post-processing"
            try:
                actual_f0 = await asyncio.to_thread(extract_f0, wav)
            except RuntimeError:
                actual_f0 = None
            provenance = "OPENACE_CI_SYNTH_FIXTURE=1 — ORCHESTRATION TEST AUDIO, NOT MODEL OUTPUT" if self.fixture_mode else self.vocal_engine_name
            if breath_result.applied:
                provenance += " + Breath events real donor-noise overlays (post-render DSP, not neural conditioning)"
            elif track.breaths:
                provenance += " + Breath events requested but no real donor noise was available; no synthetic noise inserted"
            if dynamic_applied:
                provenance += " + Dynamic lane gain post-processing (not neural conditioning)"
            if air_applied:
                provenance += " + Air lane high-frequency DSP (not neural conditioning)"
            if energy_applied:
                provenance += " + Energy lane harmonic-density DSP (not neural conditioning)"
            if tension_applied:
                provenance += " + Tension lane presence-band DSP (not neural conditioning)"
            if falsetto_applied:
                provenance += " + Falsetto lane spectral-tilt DSP (not neural conditioning)"
            await asyncio.to_thread(write_diagnostic, diagnostic, project, track.sorted_notes(), audio, sr, actual_f0, provenance, track.automation.pitch_cents)
            track.render_path = str(wav)
            track.render_revision += 1
            self.store.save(project)
            self._publish_project(project)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            if applied_lanes and breath_result.applied:
                job.message = f"completed with {'/'.join(applied_lanes)} post-processing and {breath_result.applied} breath overlay(s)"
            elif applied_lanes:
                job.message = f"completed with {'/'.join(applied_lanes)} post-processing"
            elif breath_result.applied:
                job.message = f"completed with {breath_result.applied} real-donor breath overlay(s)"
            elif track.breaths:
                job.message = "completed; breath donor unavailable, no synthetic noise inserted"
            else:
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
            notes = first_vocal_notes(project)
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

    async def run_separation(self, job_id: str, source_audio: str) -> RenderJob:
        job = self.jobs[job_id]
        job.status = RenderJobStatus.RUNNING
        job.message = "running local stem separation"
        job.progress = 0.05
        self._publish_job(job)
        try:
            project = self.store.get(job.project_id)
            outdir = self.output_dir(project.id, job.id)
            if self.fixture_mode:
                vocals = outdir / "separated_vocal.wav"
                accompaniment = outdir / "separated_accompaniment.wav"
                await asyncio.to_thread(fixture_separate_stems, Path(source_audio), vocals, accompaniment)
            else:
                vocals, accompaniment = await asyncio.to_thread(self.stem_separator.separate, Path(source_audio), outdir)
            vocal_audio, vocal_sr = await asyncio.to_thread(read_audio, vocals)
            accompaniment_audio, accompaniment_sr = await asyncio.to_thread(read_audio, accompaniment)
            source_name = Path(source_audio).stem or "source"
            vocal_track = project.add_track(Track(name=f"Separated vocal — {source_name}", type=TrackType.AUDIO, color="#ff7b9c"))
            vocal_track.clips.append(AudioClip(path=str(vocals), start_ticks=0, duration_ticks=project.seconds_to_ticks(len(vocal_audio) / vocal_sr), label="Separated vocal"))
            vocal_track.render_path = str(vocals)
            vocal_track.render_revision += 1
            accompaniment_track = project.add_track(Track(name=f"Separated instrumental — {source_name}", type=TrackType.AUDIO, color="#42c6a8"))
            accompaniment_track.clips.append(AudioClip(path=str(accompaniment), start_ticks=0, duration_ticks=project.seconds_to_ticks(len(accompaniment_audio) / accompaniment_sr), label="Separated instrumental"))
            accompaniment_track.render_path = str(accompaniment)
            accompaniment_track.render_revision += 1
            separations = list(project.metadata.get("stem_separations", []))
            separations.append({
                "job_id": job.id,
                "source_audio": str(source_audio),
                "vocal_track_id": vocal_track.id,
                "accompaniment_track_id": accompaniment_track.id,
                "vocal_path": str(vocals),
                "accompaniment_path": str(accompaniment),
                "engine": "explicit CI separation fixture" if self.fixture_mode else "Demucs htdemucs",
            })
            project.metadata["stem_separations"] = separations
            self.store.save(project)
            self._publish_project(project)
            diagnostic = outdir / "diagnostic.png"
            provenance = "OPENACE_CI_SYNTH_FIXTURE=1 — ORCHESTRATION TEST AUDIO, NOT DEMUCS OUTPUT" if self.fixture_mode else "Demucs htdemucs local stem separation"
            await asyncio.to_thread(write_diagnostic, diagnostic, project, first_vocal_notes(project), vocal_audio, vocal_sr, None, provenance)
            job.output_path = str(vocals)
            job.diagnostic_path = str(diagnostic)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = f"completed; added separated vocal/instrumental tracks for {source_name}"
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

            # SVC output is arrangement media, not just a side-file in the job card.
            # Keep each conversion on its own audio track so users can mute/compare/move
            # alternatives without accidentally doubling the score-rendered vocal track.
            duration_ticks = project.seconds_to_ticks(len(audio) / sr) if sr else None
            source_name = Path(source_audio).stem or "source"
            conversion_track = project.add_track(
                Track(name=f"SVC — {source_name}", type=TrackType.AUDIO, color="#ff8f5a")
            )
            conversion_track.clips.append(
                AudioClip(
                    path=str(wav),
                    start_ticks=0,
                    duration_ticks=duration_ticks,
                    label=f"SVC: {source_name}",
                )
            )
            conversion_track.render_path = str(wav)
            conversion_track.render_revision += 1
            conversions = list(project.metadata.get("svc_conversions", []))
            conversions.append(
                {
                    "job_id": job.id,
                    "track_id": conversion_track.id,
                    "source_audio": str(source_audio),
                    "reference_voice": str(reference_voice),
                    "output_path": str(wav),
                }
            )
            project.metadata["svc_conversions"] = conversions
            self.store.save(project)
            self._publish_project(project)

            diagnostic = outdir / "diagnostic.png"
            notes = first_vocal_notes(project)
            provenance = "OPENACE_CI_SYNTH_FIXTURE=1 — ORCHESTRATION TEST AUDIO, NOT MODEL OUTPUT" if self.fixture_mode else f"{self.vocal_engine_name} SVC"
            await asyncio.to_thread(write_diagnostic, diagnostic, project, notes, audio, sr, None, provenance)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = f"completed; added to arrangement as {conversion_track.name}"
            job.finished_at = time.time()
        except Exception as exc:
            job.status = RenderJobStatus.FAILED
            job.error = str(exc)
            job.message = str(exc)
            job.finished_at = time.time()
        self._publish_job(job)
        event_bus.publish("project_updated", {"project_id": job.project_id})
        return job
