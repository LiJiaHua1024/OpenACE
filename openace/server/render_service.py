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
from openace.core.expression import apply_air_envelope, apply_dynamic_envelope, apply_energy_envelope, apply_falsetto_envelope, apply_note_velocity, apply_tension_envelope
from openace.core.models import AudioClip, Project, RenderJob, RenderJobStatus, RenderMode, TimedLyric, Track, TrackType
from openace.core.project_store import ProjectStore
from openace.core.render_fingerprint import vocal_render_input_hash
from openace.engines.acestep import ACEStepEngine
from openace.engines.base import EngineUnavailable
from openace.engines.fixture import FixtureMusicEngine, FixtureVocalEngine, fixture_enabled, fixture_separate_stems
from openace.engines.processes import CancellationToken, JobCancelled
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



def _path_identity(path: str) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(path)


def clip_source_offset_seconds(project: Project, clip: AudioClip) -> float:
    offset_ticks = int(clip.offset_ticks or 0)
    if offset_ticks <= 0:
        return 0.0
    return project.tick_duration_seconds(clip.start_ticks - offset_ticks, offset_ticks)


def clip_timeline_span_seconds(project: Project, clip: AudioClip) -> tuple[float, float]:
    start_s = project.ticks_to_seconds(clip.start_ticks)
    if clip.duration_ticks is not None:
        duration_s = project.tick_duration_seconds(clip.start_ticks, clip.duration_ticks)
    else:
        try:
            info = sf.info(str(clip.path))
            duration_s = max(0.0, info.frames / float(info.samplerate) - clip_source_offset_seconds(project, clip))
        except Exception:
            duration_s = 0.0
    return start_s, start_s + duration_s


def find_clip(project: Project, clip_id: str) -> tuple[Track, AudioClip] | tuple[None, None]:
    for track in project.tracks:
        for clip in track.clips:
            if clip.id == clip_id:
                return track, clip
    return None, None


def resolve_vocal2bgm_source(project: Project, source_audio: Optional[str], track_id: Optional[str], clip_id: Optional[str]) -> tuple[str, int, Optional[float], Optional[float], Optional[str]]:
    """Resolve Vocal2BGM input and arrangement anchoring without inventing timeline context."""
    if track_id:
        try:
            track = project.track(track_id)
        except KeyError as exc:
            raise ValueError(f"Vocal2BGM track not found: {track_id}") from exc
        if track.type != TrackType.VOCAL:
            raise ValueError("Vocal2BGM track must be a vocal track")
        if not track.render_path:
            raise ValueError("selected vocal track has no rendered audio; render it before Vocal2BGM")
        if not track.render_fingerprint or track.render_fingerprint != vocal_render_input_hash(project, track):
            raise ValueError("selected vocal render is stale; render the current vocal before Vocal2BGM")
        return track.render_path, 0, None, None, None

    def anchored_clip(clip: AudioClip) -> tuple[str, int, float, float, str]:
        clip_start, clip_end = clip_timeline_span_seconds(project, clip)
        offset = clip_source_offset_seconds(project, clip)
        visible = max(0.0, clip_end - clip_start)
        if visible <= 0:
            raise ValueError("Vocal2BGM source clip has no visible audio duration")
        return clip.path, clip.start_ticks, offset, offset + visible, clip.id

    if clip_id:
        _, clip = find_clip(project, clip_id)
        if clip is None:
            raise ValueError(f"Vocal2BGM source clip not found: {clip_id}")
        return anchored_clip(clip)

    if not source_audio:
        raise ValueError("Vocal2BGM requires a rendered vocal track, source_audio, or clip_id")
    wanted = _path_identity(source_audio)
    matches = [clip for track in project.tracks for clip in track.clips if _path_identity(clip.path) == wanted]
    if len(matches) == 1:
        return anchored_clip(matches[0])
    if len(matches) > 1:
        raise ValueError("multiple arrangement clips use this source audio; pass clip_id explicitly")
    return source_audio, 0, None, None, None


def resolve_project_audio_source(project: Project, source_audio: Optional[str], clip_id: Optional[str], operation: str) -> tuple[str, int, Optional[float], Optional[float], Optional[str]]:
    """Resolve a project audio input clip without inventing arrangement context."""
    def anchored_clip(clip: AudioClip) -> tuple[str, int, float, float, str]:
        clip_start, clip_end = clip_timeline_span_seconds(project, clip)
        offset = clip_source_offset_seconds(project, clip)
        visible = max(0.0, clip_end - clip_start)
        if visible <= 0:
            raise ValueError(f"{operation} source clip has no visible audio duration")
        return clip.path, clip.start_ticks, offset, offset + visible, clip.id

    if clip_id:
        _, clip = find_clip(project, clip_id)
        if clip is None:
            raise ValueError(f"{operation} source clip not found: {clip_id}")
        return anchored_clip(clip)
    if not source_audio:
        raise ValueError(f"{operation} requires source_audio or clip_id")
    wanted = _path_identity(source_audio)
    matches = [clip for track in project.tracks for clip in track.clips if _path_identity(clip.path) == wanted]
    if len(matches) == 1:
        return anchored_clip(matches[0])
    if len(matches) > 1:
        raise ValueError("multiple arrangement clips use this source audio; pass clip_id explicitly")
    return source_audio, 0, None, None, None


def resolve_svc_source(project: Project, source_audio: Optional[str], clip_id: Optional[str]) -> tuple[str, int, Optional[float], Optional[float], Optional[str]]:
    return resolve_project_audio_source(project, source_audio, clip_id, "SVC")


def resolve_separation_source(project: Project, source_audio: Optional[str], clip_id: Optional[str]) -> tuple[str, int, Optional[float], Optional[float], Optional[str]]:
    return resolve_project_audio_source(project, source_audio, clip_id, "stem separation")


def prepare_source_segment_input(source_audio: Path, workdir: Path, source_start_s: Optional[float], source_end_s: Optional[float]) -> tuple[Path, float]:
    """Materialize the exact visible source segment and return its truthful duration."""
    if source_start_s is None and source_end_s is None:
        info = sf.info(str(source_audio))
        return source_audio, info.frames / float(info.samplerate)
    data, sample_rate = sf.read(str(source_audio), always_2d=True)
    total = len(data) / float(sample_rate)
    start = max(0.0, float(source_start_s or 0.0))
    end = total if source_end_s is None else min(total, float(source_end_s))
    if end <= start:
        raise ValueError("source clip resolves to an empty audio segment")
    excerpt = workdir / "source_segment_excerpt.wav"
    workdir.mkdir(parents=True, exist_ok=True)
    segment = data[int(round(start * sample_rate)):int(round(end * sample_rate))]
    sf.write(str(excerpt), segment, sample_rate, subtype="PCM_24")
    return excerpt, len(segment) / float(sample_rate)


def resolve_repaint_target(project: Project, source_audio: Optional[str], clip_id: Optional[str], start_s: float, end_s: float) -> tuple[Track, AudioClip, float, float, float, float]:
    """Resolve arrangement repaint selection into source-audio seconds.

    ACE-Step expects times in the source file, while the workstation selection is in
    arrangement time. The intersection is clamped to the visible clip span and then
    shifted by the clip's source offset. Times remain seconds because clips are not
    time-stretched; piecewise tempo conversion only determines the timeline endpoints.
    """
    if end_s != -1 and end_s <= start_s:
        raise ValueError("repaint end must be greater than start")
    candidates: list[tuple[Track, AudioClip]] = []
    if clip_id:
        track, clip = find_clip(project, clip_id)
        if clip is None or track is None:
            raise ValueError(f"repaint target clip not found: {clip_id}")
        candidates.append((track, clip))
        if not source_audio:
            source_audio = clip.path
    else:
        if not source_audio:
            raise ValueError("repaint requires source_audio or clip_id")
        wanted = _path_identity(source_audio)
        for track in project.tracks:
            for clip in track.clips:
                if _path_identity(clip.path) == wanted:
                    candidates.append((track, clip))
        if not candidates:
            raise ValueError("repaint source audio must be present as an arrangement clip so timeline selection can be mapped truthfully")

    best = None
    requested_end = float("inf") if end_s == -1 else end_s
    for track, clip in candidates:
        clip_start, clip_end = clip_timeline_span_seconds(project, clip)
        overlap_start = max(float(start_s), clip_start)
        overlap_end = min(requested_end, clip_end)
        if overlap_end <= overlap_start:
            continue
        offset = clip_source_offset_seconds(project, clip)
        source_start = offset + (overlap_start - clip_start)
        source_end = offset + (overlap_end - clip_start)
        overlap = overlap_end - overlap_start
        if best is None or overlap > best[-1]:
            best = (track, clip, source_start, source_end, overlap_start, overlap_end, overlap)
    if best is None:
        raise ValueError("repaint range does not intersect the source arrangement clip")
    track, clip, source_start, source_end, overlap_start, overlap_end, _ = best
    return track, clip, source_start, source_end, overlap_start, overlap_end


class RenderService:
    def __init__(self, store: ProjectStore, render_root: Path):
        self.store = store
        self.render_root = Path(render_root)
        self.render_root.mkdir(parents=True, exist_ok=True)
        self.jobs_path = self.render_root / "jobs.json"
        self.jobs: Dict[str, RenderJob] = self._load_jobs()
        self.recovery_pending: set[str] = set()
        self._job_queue: Optional[asyncio.Queue[str]] = None
        self._job_queue_loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue_worker: Optional[asyncio.Task] = None
        self._enqueued_jobs: set[str] = set()
        self._cancel_tokens: Dict[str, CancellationToken] = {}
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

    def _report_job_progress(self, job_id: str, progress: float, message: str) -> None:
        job = self.jobs.get(job_id)
        if job is None or job.status != RenderJobStatus.RUNNING or self.cancellation_token(job_id).cancelled:
            return
        job.progress = max(job.progress, min(0.95, progress))
        job.message = message
        self._publish_job(job)

    def _progress_callback(self, job_id: str):
        loop = asyncio.get_running_loop()

        def report(progress: float, message: str) -> None:
            loop.call_soon_threadsafe(self._report_job_progress, job_id, progress, message)

        return report

    def cancellation_token(self, job_id: str) -> CancellationToken:
        token = self._cancel_tokens.get(job_id)
        if token is None:
            token = CancellationToken()
            self._cancel_tokens[job_id] = token
        return token

    def raise_if_cancelled(self, job_id: str) -> None:
        if self.cancellation_token(job_id).cancelled:
            raise JobCancelled("render job cancelled")

    def cancel_job(self, job_id: str) -> RenderJob:
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(f"render job not found: {job_id}")
        if job.status == RenderJobStatus.QUEUED:
            job.status = RenderJobStatus.CANCELED
            job.progress = 0.0
            job.message = "cancelled before engine start"
            job.error = None
            job.finished_at = time.time()
            self.cancellation_token(job_id).cancel()
            self._publish_job(job)
            return job
        if job.status == RenderJobStatus.RUNNING:
            self.cancellation_token(job_id).cancel()
            job.message = "cancellation requested; terminating engine process"
            self._publish_job(job)
            return job
        raise ValueError(f"cannot cancel render job in state {job.status}")

    def _record_job_exception(self, job: RenderJob, exc: Exception) -> None:
        if isinstance(exc, JobCancelled) or self.cancellation_token(job.id).cancelled:
            job.status = RenderJobStatus.CANCELED
            job.error = None
            job.message = "cancelled"
        else:
            job.status = RenderJobStatus.FAILED
            job.error = str(exc)
            job.message = str(exc)
        job.finished_at = time.time()

    def enqueue_job(self, job_id: str) -> None:
        """Serialize server-triggered jobs so heavy engines never contend for VRAM."""
        if job_id not in self.jobs:
            raise KeyError(f"render job not found: {job_id}")
        if job_id in self._enqueued_jobs:
            return
        loop = asyncio.get_running_loop()
        if self._job_queue is None or self._job_queue_loop is not loop:
            self._job_queue = asyncio.Queue()
            self._job_queue_loop = loop
            self._queue_worker = None
        self._enqueued_jobs.add(job_id)
        self._job_queue.put_nowait(job_id)
        if self._queue_worker is None or self._queue_worker.done():
            self._queue_worker = loop.create_task(self._drain_job_queue())

    async def _drain_job_queue(self) -> None:
        assert self._job_queue is not None
        while True:
            job_id = await self._job_queue.get()
            self._enqueued_jobs.discard(job_id)
            try:
                job = self.jobs.get(job_id)
                if job is not None and job.status == RenderJobStatus.QUEUED:
                    await self.recovery_coro(job)
            except Exception as exc:
                job = self.jobs.get(job_id)
                if job is not None:
                    job.status = RenderJobStatus.FAILED
                    job.error = str(exc)
                    job.message = str(exc)
                    job.finished_at = time.time()
                    self._publish_job(job)
            finally:
                self._job_queue.task_done()

    async def shutdown(self) -> None:
        if self._queue_worker is not None and not self._queue_worker.done():
            self._queue_worker.cancel()
            try:
                await self._queue_worker
            except asyncio.CancelledError:
                pass

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
        clip_id: Optional[str] = None,
    ) -> RenderJob:
        source_start_s = None
        source_end_s = None
        arrangement_start_ticks = None
        if mode == RenderMode.REPAINT:
            project = self.store.get(project_id)
            _, target_clip, source_start_s, source_end_s, _, _ = resolve_repaint_target(
                project,
                source_audio,
                clip_id,
                float(start_s or 0.0),
                float(end_s if end_s is not None else -1.0),
            )
            clip_id = target_clip.id
            source_audio = target_clip.path
        elif mode == RenderMode.VOCAL2BGM:
            project = self.store.get(project_id)
            source_audio, arrangement_start_ticks, source_start_s, source_end_s, clip_id = resolve_vocal2bgm_source(
                project,
                source_audio,
                track_id,
                clip_id,
            )
        elif mode == RenderMode.SVC:
            project = self.store.get(project_id)
            source_audio, arrangement_start_ticks, source_start_s, source_end_s, clip_id = resolve_svc_source(
                project,
                source_audio,
                clip_id,
            )
        elif mode == RenderMode.SEPARATE:
            project = self.store.get(project_id)
            source_audio, arrangement_start_ticks, source_start_s, source_end_s, clip_id = resolve_separation_source(
                project,
                source_audio,
                clip_id,
            )
        job = RenderJob(
            project_id=project_id,
            track_id=track_id,
            mode=mode,
            source_audio=source_audio,
            reference_voice=reference_voice,
            caption=caption,
            start_s=start_s,
            end_s=end_s,
            clip_id=clip_id,
            source_start_s=source_start_s,
            source_end_s=source_end_s,
            arrangement_start_ticks=arrangement_start_ticks,
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
            await asyncio.to_thread(self.vocal_engine.render_score, project, track, wav, cancellation=self.cancellation_token(job_id), progress=self._progress_callback(job_id))
            self.raise_if_cancelled(job_id)
            audio, sr = await asyncio.to_thread(read_audio, wav)
            self._report_job_progress(job_id, 0.84, "applying expression and breath post-processing")
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
            audio, velocity_applied = apply_note_velocity(audio, sr, project, track)
            audio, dynamic_applied = apply_dynamic_envelope(audio, sr, project, track)
            audio, air_applied = apply_air_envelope(audio, sr, project, track)
            audio, energy_applied = apply_energy_envelope(audio, sr, project, track)
            audio, tension_applied = apply_tension_envelope(audio, sr, project, track)
            audio, falsetto_applied = apply_falsetto_envelope(audio, sr, project, track)
            applied_lanes = [
                name
                for name, applied in (
                    ("Velocity", velocity_applied),
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
            if velocity_applied:
                provenance += " + Note velocity post-render gain (not neural articulation conditioning)"
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
            self._report_job_progress(job_id, 0.92, "writing acoustic diagnostic")
            await asyncio.to_thread(write_diagnostic, diagnostic, project, track.sorted_notes(), audio, sr, actual_f0, provenance, track.automation.pitch_cents)
            completed_fingerprint = vocal_render_input_hash(project, track)
            self.raise_if_cancelled(job_id)
            latest_project = self.store.get(project.id)
            try:
                latest_track = latest_project.track(job.track_id)
            except KeyError as exc:
                raise RuntimeError("vocal track was deleted before render completion; output was not adopted") from exc
            latest_track.render_path = str(wav)
            latest_track.render_revision += 1
            latest_track.render_fingerprint = completed_fingerprint
            self.store.save(latest_project)
            self._publish_project(latest_project)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            self.raise_if_cancelled(job_id)
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
            self._record_job_exception(job, exc)
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
            source_audio = job.source_audio or source_audio
            caption = job.caption or caption
            project = self.store.get(job.project_id)
            outdir = self.output_dir(project.id, job.id)
            wav = outdir / "accompaniment.wav"
            if job.mode == RenderMode.REPAINT:
                if not source_audio:
                    raise ValueError("repaint requires source_audio")
                engine_start_s = job.source_start_s if job.source_start_s is not None else start_s
                engine_end_s = job.source_end_s if job.source_end_s is not None else end_s
                await asyncio.to_thread(self.music_engine.repaint, Path(source_audio), wav, engine_start_s, engine_end_s, caption, cancellation=self.cancellation_token(job_id), progress=self._progress_callback(job_id))
                self.raise_if_cancelled(job_id)
            else:
                if not source_audio:
                    raise ValueError("vocal2bgm requires source_audio")
                engine_source, source_duration_s = await asyncio.to_thread(
                    prepare_source_segment_input,
                    Path(source_audio),
                    outdir,
                    job.source_start_s,
                    job.source_end_s,
                )
                await asyncio.to_thread(self.music_engine.vocal_to_bgm, engine_source, wav, caption, source_duration_s, project.bpm, cancellation=self.cancellation_token(job_id), progress=self._progress_callback(job_id))
                self.raise_if_cancelled(job_id)
            audio, sr = await asyncio.to_thread(read_audio, wav)
            self._report_job_progress(job_id, 0.84, "integrating accompaniment into arrangement")
            completion_project = self.store.get(project.id)
            duration_ticks = completion_project.seconds_to_ticks(len(audio) / sr) if sr else None
            accompaniment = next((t for t in completion_project.tracks if t.type == TrackType.ACCOMPANIMENT), None)
            if accompaniment is None:
                accompaniment = completion_project.add_track(
                    Track(name="ACE-Step BGM", type=TrackType.ACCOMPANIMENT, color="#2fb996", created_by_job_id=job.id)
                )
            self.raise_if_cancelled(job_id)
            repaint_parent = None
            repaint_target = None
            if job.mode == RenderMode.REPAINT and job.clip_id:
                repaint_parent, repaint_target = find_clip(completion_project, job.clip_id)
            if job.mode == RenderMode.REPAINT:
                if repaint_target is None or repaint_parent is None:
                    raise RuntimeError("repaint target clip was deleted before render completion; output was not adopted")
                # Repaint returns a full-length revised source file aligned with the
                # original file. Preserve the user's arrangement position, trim,
                # source offset, fades, and gain exactly; only the media identity and
                # provenance change. The visible intersection was already converted to
                # source-file seconds when the job was created.
                repaint_target.path = str(wav)
                repaint_target.label = "Repaint"
                repaint_target.updated_by_job_id = job.id
                repaint_parent.render_path = str(wav)
                repaint_parent.render_revision += 1
            else:
                arrangement_start_ticks = job.arrangement_start_ticks or 0
                if job.clip_id:
                    _, source_clip = find_clip(completion_project, job.clip_id)
                    if source_clip is not None:
                        arrangement_start_ticks = source_clip.start_ticks
                accompaniment.clips.append(
                    AudioClip(
                        path=str(wav),
                        start_ticks=arrangement_start_ticks,
                        duration_ticks=duration_ticks,
                        label="Vocal2BGM",
                        created_by_job_id=job.id,
                    )
                )
                accompaniment.render_path = str(wav)
                accompaniment.render_revision += 1
            self.raise_if_cancelled(job_id)
            self.store.save(completion_project)
            self._publish_project(completion_project)
            diagnostic = outdir / "diagnostic.png"
            notes = first_vocal_notes(project)
            self._report_job_progress(job_id, 0.92, "writing acoustic diagnostic")
            await asyncio.to_thread(write_diagnostic, diagnostic, project, notes, audio, sr)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            self.raise_if_cancelled(job_id)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = "completed"
            job.finished_at = time.time()
        except Exception as exc:
            self._record_job_exception(job, exc)
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
            source_audio = job.source_audio or source_audio
            project = self.store.get(job.project_id)
            outdir = self.output_dir(project.id, job.id)
            engine_source, _ = await asyncio.to_thread(
                prepare_source_segment_input,
                Path(source_audio),
                outdir,
                job.source_start_s,
                job.source_end_s,
            )
            if self.fixture_mode:
                vocals = outdir / "separated_vocal.wav"
                accompaniment = outdir / "separated_accompaniment.wav"
                await asyncio.to_thread(fixture_separate_stems, engine_source, vocals, accompaniment, progress=self._progress_callback(job_id))
            else:
                vocals, accompaniment = await asyncio.to_thread(self.stem_separator.separate, engine_source, outdir, cancellation=self.cancellation_token(job_id), progress=self._progress_callback(job_id))
            self.raise_if_cancelled(job_id)
            vocal_audio, vocal_sr = await asyncio.to_thread(read_audio, vocals)
            accompaniment_audio, accompaniment_sr = await asyncio.to_thread(read_audio, accompaniment)
            self._report_job_progress(job_id, 0.84, "integrating separated stems into arrangement")
            self.raise_if_cancelled(job_id)
            source_name = Path(source_audio).stem or "source"
            completion_project = self.store.get(project.id)
            arrangement_start_ticks = job.arrangement_start_ticks or 0
            if job.clip_id:
                _, source_clip = find_clip(completion_project, job.clip_id)
                if source_clip is not None:
                    arrangement_start_ticks = source_clip.start_ticks
            vocal_track = completion_project.add_track(Track(name=f"Separated vocal — {source_name}", type=TrackType.AUDIO, color="#ff7b9c", created_by_job_id=job.id))
            vocal_track.clips.append(AudioClip(path=str(vocals), start_ticks=arrangement_start_ticks, duration_ticks=completion_project.seconds_to_ticks(len(vocal_audio) / vocal_sr), label="Separated vocal", created_by_job_id=job.id))
            vocal_track.render_path = str(vocals)
            vocal_track.render_revision += 1
            accompaniment_track = completion_project.add_track(Track(name=f"Separated instrumental — {source_name}", type=TrackType.AUDIO, color="#42c6a8", created_by_job_id=job.id))
            accompaniment_track.clips.append(AudioClip(path=str(accompaniment), start_ticks=arrangement_start_ticks, duration_ticks=completion_project.seconds_to_ticks(len(accompaniment_audio) / accompaniment_sr), label="Separated instrumental", created_by_job_id=job.id))
            accompaniment_track.render_path = str(accompaniment)
            accompaniment_track.render_revision += 1
            separations = list(completion_project.metadata.get("stem_separations", []))
            separations.append({
                "job_id": job.id,
                "source_audio": str(source_audio),
                "clip_id": job.clip_id,
                "source_start_s": job.source_start_s,
                "source_end_s": job.source_end_s,
                "vocal_track_id": vocal_track.id,
                "accompaniment_track_id": accompaniment_track.id,
                "vocal_path": str(vocals),
                "accompaniment_path": str(accompaniment),
                "engine": "explicit CI separation fixture" if self.fixture_mode else "Demucs htdemucs",
            })
            completion_project.metadata["stem_separations"] = separations
            self.raise_if_cancelled(job_id)
            self.store.save(completion_project)
            self._publish_project(completion_project)
            diagnostic = outdir / "diagnostic.png"
            provenance = "OPENACE_CI_SYNTH_FIXTURE=1 — ORCHESTRATION TEST AUDIO, NOT DEMUCS OUTPUT" if self.fixture_mode else "Demucs htdemucs local stem separation"
            self._report_job_progress(job_id, 0.92, "writing acoustic diagnostic")
            await asyncio.to_thread(write_diagnostic, diagnostic, project, first_vocal_notes(project), vocal_audio, vocal_sr, None, provenance)
            job.output_path = str(vocals)
            job.diagnostic_path = str(diagnostic)
            self.raise_if_cancelled(job_id)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = f"completed; added separated vocal/instrumental tracks for {source_name}"
            job.finished_at = time.time()
        except Exception as exc:
            self._record_job_exception(job, exc)
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
            source_audio = job.source_audio or source_audio
            reference_voice = job.reference_voice or reference_voice
            project = self.store.get(job.project_id)
            outdir = self.output_dir(project.id, job.id)
            wav = outdir / "svc.wav"
            engine_source, _ = await asyncio.to_thread(
                prepare_source_segment_input,
                Path(source_audio),
                outdir,
                job.source_start_s,
                job.source_end_s,
            )
            await asyncio.to_thread(self.vocal_engine.convert_voice, engine_source, Path(reference_voice), wav, cancellation=self.cancellation_token(job_id), progress=self._progress_callback(job_id))
            self.raise_if_cancelled(job_id)
            audio, sr = await asyncio.to_thread(read_audio, wav)
            self._report_job_progress(job_id, 0.84, "transcribing and integrating converted vocal")

            # SVC output is arrangement media, not just a side-file in the job card.
            # Keep each conversion on its own audio track so users can mute/compare/move
            # alternatives without accidentally doubling the score-rendered vocal track.
            source_name = Path(source_audio).stem or "source"
            self.raise_if_cancelled(job_id)
            transcribed_lyrics: List[TimedLyric] = []
            lyric_language = None
            lyric_error = None
            try:
                from openace.importers.audio import transcribe_lyric_words

                words, lyric_language = await asyncio.to_thread(transcribe_lyric_words, wav)
                transcribed_lyrics = [
                    TimedLyric(text=str(word["text"]), start=float(word["start"]), end=float(word["end"]))
                    for word in words
                ]
            except Exception as exc:
                # Missing optional ASR must never invent lyrics or invalidate an otherwise real conversion.
                lyric_error = str(exc)

            completion_project = self.store.get(project.id)
            duration_ticks = completion_project.seconds_to_ticks(len(audio) / sr) if sr else None
            conversion_track = completion_project.add_track(
                Track(name=f"SVC — {source_name}", type=TrackType.AUDIO, color="#ff8f5a", created_by_job_id=job.id)
            )
            arrangement_start_ticks = job.arrangement_start_ticks or 0
            if job.clip_id:
                _, source_clip = find_clip(completion_project, job.clip_id)
                if source_clip is not None:
                    arrangement_start_ticks = source_clip.start_ticks
            conversion_track.clips.append(
                AudioClip(
                    path=str(wav),
                    start_ticks=arrangement_start_ticks,
                    duration_ticks=duration_ticks,
                    label=f"SVC: {source_name}",
                    transcribed_lyrics=transcribed_lyrics,
                    created_by_job_id=job.id,
                )
            )
            conversion_track.render_path = str(wav)
            conversion_track.render_revision += 1
            conversions = list(completion_project.metadata.get("svc_conversions", []))
            conversions.append(
                {
                    "job_id": job.id,
                    "track_id": conversion_track.id,
                    "source_audio": str(source_audio),
                    "reference_voice": str(reference_voice),
                    "clip_id": job.clip_id,
                    "source_start_s": job.source_start_s,
                    "source_end_s": job.source_end_s,
                    "output_path": str(wav),
                    "lyric_language": lyric_language,
                    "lyric_word_count": len(transcribed_lyrics),
                    "lyric_transcription_error": lyric_error,
                }
            )
            completion_project.metadata["svc_conversions"] = conversions
            self.raise_if_cancelled(job_id)
            self.store.save(completion_project)
            self._publish_project(completion_project)

            diagnostic = outdir / "diagnostic.png"
            notes = first_vocal_notes(project)
            provenance = "OPENACE_CI_SYNTH_FIXTURE=1 — ORCHESTRATION TEST AUDIO, NOT MODEL OUTPUT" if self.fixture_mode else f"{self.vocal_engine_name} SVC"
            self._report_job_progress(job_id, 0.92, "writing acoustic diagnostic")
            await asyncio.to_thread(write_diagnostic, diagnostic, project, notes, audio, sr, None, provenance)
            job.output_path = str(wav)
            job.diagnostic_path = str(diagnostic)
            self.raise_if_cancelled(job_id)
            job.status = RenderJobStatus.COMPLETED
            job.progress = 1.0
            job.message = f"completed; added to arrangement as {conversion_track.name}"
            job.finished_at = time.time()
        except Exception as exc:
            self._record_job_exception(job, exc)
        self._publish_job(job)
        event_bus.publish("project_updated", {"project_id": job.project_id})
        return job
