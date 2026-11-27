import asyncio
import os
from pathlib import Path

import numpy as np
import pytest

from openace.core.audio import read_audio
from openace.core.models import Breath, EnvelopePoint, Note, RenderJobStatus, RenderMode, Track
from openace.core.project_store import ProjectStore
from openace.engines.fixture import FixtureVocalEngine
from openace.server.render_service import RenderService


def test_fixture_engine_requires_explicit_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENACE_CI_SYNTH_FIXTURE", raising=False)
    project_store = ProjectStore(tmp_path / "projects")
    project = project_store.create("fixture")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    project_store.save(project)
    with pytest.raises(RuntimeError, match="OPENACE_CI_SYNTH_FIXTURE"):
        FixtureVocalEngine().render_score(project, track, tmp_path / "x.wav")


def test_explicit_ci_fixture_renders_wav_and_diagnostic(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("fixture")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=64, lyric="好"))
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)
    result = asyncio.run(service.run_vocal_render(job.id))
    assert result.status == "completed"
    assert Path(result.output_path).exists()
    assert Path(result.diagnostic_path).exists()
    assert Path(result.output_path).stat().st_size > 1000


def test_dynamic_automation_postprocesses_fixture_render(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("fixture")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=60, lyric="好"))
    track.automation.dynamic = [
        EnvelopePoint(ticks=0, value=0.0),
        EnvelopePoint(ticks=960, value=1.0),
    ]
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)
    result = asyncio.run(service.run_vocal_render(job.id))
    assert result.status == "completed"
    assert result.message == "completed with Dynamic post-processing"
    audio, sr = read_audio(Path(result.output_path))
    first_note = audio[int(0.05 * sr):int(0.42 * sr)]
    second_note = audio[int(0.55 * sr):int(0.92 * sr)]
    first_rms = float(np.sqrt(np.mean(first_note ** 2)))
    second_rms = float(np.sqrt(np.mean(second_note ** 2)))
    assert second_rms / first_rms > 1.4


def test_acestep_vocal2bgm_uses_complete_task_not_cover():
    source = Path("openace/engines/acestep.py").read_text()
    vocal_fn = source.split("def vocal_to_bgm", 1)[1].split("def repaint", 1)[0]
    assert '"task_type": "complete"' in vocal_fn
    assert '"task_type": "cover"' not in vocal_fn


def test_render_jobs_persist_and_interrupted_vocal_job_requeues(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("durable")
    track = project.tracks[0]
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)
    service.jobs[job.id].status = RenderJobStatus.RUNNING
    service._publish_job(service.jobs[job.id])

    recovered_service = RenderService(store, tmp_path / "renders")
    recovered = recovered_service.recover_interrupted_jobs()
    assert [item.id for item in recovered] == [job.id]
    assert recovered_service.jobs[job.id].status == RenderJobStatus.QUEUED
    assert recovered_service.jobs[job.id].message == "requeued after backend restart"
    assert recovered_service.recover_interrupted_jobs() == []
    result = asyncio.run(recovered_service.recovery_coro(recovered[0]))
    assert result.status == RenderJobStatus.COMPLETED
    assert Path(result.output_path).exists()


def test_unrecoverable_interrupted_music_job_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("legacy-durable")
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.VOCAL2BGM)
    service.jobs[job.id].status = RenderJobStatus.RUNNING
    service._publish_job(service.jobs[job.id])

    recovered = RenderService(store, tmp_path / "renders")
    assert recovered.recover_interrupted_jobs() == []
    assert recovered.jobs[job.id].status == RenderJobStatus.FAILED
    assert "backend restarted" in recovered.jobs[job.id].error
    assert "automatic requeue" in recovered.jobs[job.id].error


def test_music_job_recovery_parameters_are_durable(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("music-durable")
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(
        project.id,
        RenderMode.REPAINT,
        source_audio="/tmp/source.wav",
        caption="warmer drums",
        start_s=1.25,
        end_s=2.5,
    )
    service.jobs[job.id].status = RenderJobStatus.RUNNING
    service._publish_job(service.jobs[job.id])

    recovered_service = RenderService(store, tmp_path / "renders")
    recovered = recovered_service.recover_interrupted_jobs()
    assert [item.id for item in recovered] == [job.id]
    restored = recovered[0]
    assert restored.source_audio == "/tmp/source.wav"
    assert restored.caption == "warmer drums"
    assert restored.start_s == 1.25
    assert restored.end_s == 2.5


def test_air_automation_postprocesses_fixture_render(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("fixture")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.automation.air = [EnvelopePoint(ticks=0, value=1.0)]
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)
    result = asyncio.run(service.run_vocal_render(job.id))
    assert result.status == "completed"
    assert result.message == "completed with Air post-processing"
    assert Path(result.output_path).exists()

def test_energy_tension_automation_postprocesses_fixture_render(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("fixture")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.automation.energy = [EnvelopePoint(ticks=0, value=1.0)]
    track.automation.tension = [EnvelopePoint(ticks=0, value=1.0)]
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)
    result = asyncio.run(service.run_vocal_render(job.id))
    assert result.status == "completed"
    assert result.message == "completed with Energy/Tension post-processing"
    assert Path(result.output_path).exists()

def test_falsetto_automation_postprocesses_fixture_render(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("fixture")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.automation.falsetto = [EnvelopePoint(ticks=0, value=1.0)]
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)
    result = asyncio.run(service.run_vocal_render(job.id))
    assert result.status == "completed"
    assert result.message == "completed with Falsetto post-processing"
    assert Path(result.output_path).exists()


def test_breath_event_postprocesses_fixture_render_with_real_reference_donor(monkeypatch, tmp_path):
    import soundfile as sf

    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    sr = 24000
    reference = np.zeros(sr * 2, dtype=np.float32)
    rng = np.random.default_rng(11)
    reference[int(0.15 * sr):int(0.75 * sr)] = rng.normal(0.0, 0.08, int(0.60 * sr)).astype(np.float32)
    reference_path = tmp_path / "reference.wav"
    sf.write(reference_path, reference, sr)

    store = ProjectStore(tmp_path / "projects")
    project = store.create("fixture")
    track = project.add_track(Track(name="Lead"))
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.breaths.append(Breath(start_ticks=480, duration_ticks=240))
    track.reference_voice_path = str(reference_path)
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)
    result = asyncio.run(service.run_vocal_render(job.id))
    assert result.status == "completed"
    assert result.message == "completed with 1 real-donor breath overlay(s)"
    audio, out_sr = read_audio(Path(result.output_path))
    # The fixture note occupies 0-0.5s; the authored breath begins exactly after it.
    breath_region = audio[int(0.56 * out_sr):int(0.70 * out_sr), 0]
    note_region = audio[int(0.10 * out_sr):int(0.40 * out_sr), 0]
    breath_rms = float(np.sqrt(np.mean(breath_region**2)))
    assert breath_rms > 0.004
    assert breath_rms < float(np.sqrt(np.mean(note_region**2)))

def test_svc_conversion_is_added_to_arrangement_with_provenance(monkeypatch, tmp_path):
    import soundfile as sf

    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    sr = 24000
    t = np.arange(sr) / sr
    source = tmp_path / "take_one.wav"
    reference = tmp_path / "voice_reference.wav"
    sf.write(source, 0.2 * np.sin(2 * np.pi * 220 * t), sr)
    sf.write(reference, 0.1 * np.sin(2 * np.pi * 180 * t), sr)

    store = ProjectStore(tmp_path / "projects")
    project = store.create("svc-arrangement")
    vocal = project.add_track(Track(name="Lead"))
    vocal.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(
        project.id,
        RenderMode.SVC,
        source_audio=str(source),
        reference_voice=str(reference),
    )
    result = asyncio.run(service.run_svc(job.id, str(source), str(reference)))

    assert result.status == RenderJobStatus.COMPLETED
    assert "added to arrangement" in result.message
    updated = store.get(project.id)
    conversion_tracks = [track for track in updated.tracks if track.name == "SVC — take_one"]
    assert len(conversion_tracks) == 1
    conversion = conversion_tracks[0]
    assert conversion.type.value == "audio"
    assert len(conversion.clips) == 1
    clip = conversion.clips[0]
    assert clip.path == result.output_path
    assert clip.start_ticks == 0
    assert clip.duration_ticks == updated.seconds_to_ticks(1.0)
    assert clip.label == "SVC: take_one"
    assert conversion.render_path == result.output_path
    provenance = updated.metadata["svc_conversions"][-1]
    assert provenance["job_id"] == job.id
    assert provenance["track_id"] == conversion.id
    assert provenance["source_audio"] == str(source)
    assert provenance["reference_voice"] == str(reference)
    assert Path(result.diagnostic_path).exists()

    second = service.create_job(
        project.id,
        RenderMode.SVC,
        source_audio=str(source),
        reference_voice=str(reference),
    )
    asyncio.run(service.run_svc(second.id, str(source), str(reference)))
    updated = store.get(project.id)
    assert len([track for track in updated.tracks if track.name == "SVC — take_one"]) == 2
