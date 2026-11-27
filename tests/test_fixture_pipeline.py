import asyncio
import os
from pathlib import Path

import numpy as np
import pytest

from openace.core.audio import read_audio
from openace.core.models import Breath, EnvelopePoint, Note, RenderJobStatus, RenderMode, Track
from openace.core.project_store import ProjectStore
from openace.core.render_fingerprint import vocal_render_input_hash
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
    stored = store.get(project.id)
    stored_track = stored.track(track.id)
    assert stored_track.render_fingerprint == vocal_render_input_hash(stored, stored_track)


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
    monkeypatch.setattr(
        "openace.importers.audio.transcribe_lyric_words",
        lambda _path: ([{"text": "你", "start": 0.1, "end": 0.4}, {"text": "好", "start": 0.45, "end": 0.8}], "zh"),
    )
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
    assert [(word.text, word.start, word.end) for word in clip.transcribed_lyrics] == [("你", 0.1, 0.4), ("好", 0.45, 0.8)]
    assert conversion.render_path == result.output_path
    provenance = updated.metadata["svc_conversions"][-1]
    assert provenance["job_id"] == job.id
    assert provenance["track_id"] == conversion.id
    assert provenance["source_audio"] == str(source)
    assert provenance["reference_voice"] == str(reference)
    assert provenance["lyric_language"] == "zh"
    assert provenance["lyric_word_count"] == 2
    assert provenance["lyric_transcription_error"] is None
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


def test_svc_transcription_failure_is_explicit_but_does_not_invent_lyrics(monkeypatch, tmp_path):
    import soundfile as sf

    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    sr = 24000
    audio = np.zeros(sr, dtype=np.float32)
    source = tmp_path / "source.wav"
    reference = tmp_path / "reference.wav"
    sf.write(source, audio, sr)
    sf.write(reference, audio, sr)
    store = ProjectStore(tmp_path / "projects")
    project = store.create("svc-asr-failure")
    store.save(project)
    monkeypatch.setattr(
        "openace.importers.audio.transcribe_lyric_words",
        lambda _path: (_ for _ in ()).throw(RuntimeError("ASR unavailable")),
    )
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SVC, source_audio=str(source), reference_voice=str(reference))
    result = asyncio.run(service.run_svc(job.id, str(source), str(reference)))
    assert result.status == RenderJobStatus.COMPLETED
    conversion = store.get(project.id).tracks[-1]
    assert conversion.clips[0].transcribed_lyrics == []
    provenance = store.get(project.id).metadata["svc_conversions"][-1]
    assert provenance["lyric_word_count"] == 0
    assert "ASR unavailable" in provenance["lyric_transcription_error"]

def test_fixture_stem_separation_adds_dry_wet_tracks_with_provenance(monkeypatch, tmp_path):
    import soundfile as sf

    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    sr = 24000
    t = np.arange(sr) / sr
    source = tmp_path / "mixed_song.wav"
    sf.write(source, 0.1 * np.sin(2 * np.pi * 220 * t) + 0.1 * np.sin(2 * np.pi * 1200 * t), sr)

    store = ProjectStore(tmp_path / "projects")
    project = store.create("separation")
    store.save(project)
    service = RenderService(store, tmp_path / "renders")
    job = service.create_job(project.id, RenderMode.SEPARATE, source_audio=str(source))
    result = asyncio.run(service.run_separation(job.id, str(source)))

    assert result.status == RenderJobStatus.COMPLETED
    assert "separated vocal/instrumental" in result.message
    updated = store.get(project.id)
    vocal_tracks = [track for track in updated.tracks if track.name == "Separated vocal — mixed_song"]
    instrumental_tracks = [track for track in updated.tracks if track.name == "Separated instrumental — mixed_song"]
    assert len(vocal_tracks) == len(instrumental_tracks) == 1
    vocal_clip = vocal_tracks[0].clips[0]
    instrumental_clip = instrumental_tracks[0].clips[0]
    assert vocal_clip.path == result.output_path
    assert vocal_clip.duration_ticks == updated.seconds_to_ticks(1.0)
    assert instrumental_clip.duration_ticks == vocal_clip.duration_ticks
    assert Path(instrumental_clip.path).exists()
    provenance = updated.metadata["stem_separations"][-1]
    assert provenance["job_id"] == job.id
    assert provenance["vocal_track_id"] == vocal_tracks[0].id
    assert provenance["accompaniment_track_id"] == instrumental_tracks[0].id
    assert provenance["engine"] == "explicit CI separation fixture"
    assert Path(result.diagnostic_path).exists()

    vocal_audio, vocal_sr = read_audio(Path(vocal_clip.path))
    instrumental_audio, instrumental_sr = read_audio(Path(instrumental_clip.path))
    assert vocal_sr == instrumental_sr == sr
    vocal_array = np.asarray(vocal_audio)
    instrumental_array = np.asarray(instrumental_audio)
    assert float(np.max(np.abs(vocal_array))) > 0.01
    assert float(np.max(np.abs(instrumental_array))) > 0.01



def test_acestep_bootstrap_syncs_checkpoint_model_code(tmp_path):
    from openace.engines.downloader import sync_acestep_model_code

    repo = tmp_path / "ace"
    for variant, checkpoint in [("base", "acestep-v15-base"), ("turbo", "acestep-v15-turbo")]:
        source = repo / "acestep/models" / variant
        target = repo / "checkpoints" / checkpoint
        source.mkdir(parents=True)
        target.mkdir(parents=True)
        (source / "modeling.py").write_text("correct = True\n")
        (source / "__init__.py").write_text("skip = True\n")
        (target / "modeling.py").write_text("correct = False\n")
    synced = sync_acestep_model_code(repo)
    assert sorted(synced) == ["acestep-v15-base/modeling.py", "acestep-v15-turbo/modeling.py"]
    assert (repo / "checkpoints/acestep-v15-base/modeling.py").read_text() == "correct = True\n"
    assert not (repo / "checkpoints/acestep-v15-base/__init__.py").exists()
