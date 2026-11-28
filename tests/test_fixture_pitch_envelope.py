import numpy as np
import soundfile as sf
import pytest

from openace.core.models import EnvelopePoint, Note, Project, Track
from openace.engines.fixture import FixtureVocalEngine


def _dominant_frequency(path, sr=24000):
    data, actual_sr = sf.read(str(path))
    assert actual_sr == sr
    segment = np.asarray(data[sr // 8: sr // 2], dtype=np.float32)
    spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
    frequencies = np.fft.rfftfreq(len(segment), 1 / sr)
    return float(frequencies[int(np.argmax(spectrum))])


def test_fixture_render_consumes_continuous_pitch_automation(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    project = Project(title="pitch automation fixture", bpm=120)
    track = Track(name="lead")
    track.add_note(Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="la"))
    project.add_track(track)
    base = tmp_path / "base.wav"
    shifted = tmp_path / "shifted.wav"
    FixtureVocalEngine().render_score(project, track, base)
    base_frequency = _dominant_frequency(base)
    track.automation.pitch_cents = [EnvelopePoint(ticks=0, value=600), EnvelopePoint(ticks=960, value=600)]
    FixtureVocalEngine().render_score(project, track, shifted)
    shifted_frequency = _dominant_frequency(shifted)
    assert 255.0 < base_frequency < 268.0
    assert shifted_frequency / base_frequency == pytest.approx(2.0 ** 0.5, rel=0.03)
