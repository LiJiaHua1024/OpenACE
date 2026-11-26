import asyncio
import os
from pathlib import Path

import numpy as np
import pytest

from openace.core.audio import read_audio
from openace.core.models import EnvelopePoint, Note, RenderMode, Track
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
