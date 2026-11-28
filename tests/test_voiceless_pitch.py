import numpy as np
import pytest
import soundfile as sf

from openace.core.models import EnvelopePoint, Note, Project, Track
from openace.core.pitch import pitch_curve_for_notes, pitch_envelope_state
from openace.engines.fixture import FixtureVocalEngine
from openace.engines.soulx import _f0_for_notes


def _project_with_voiceless_automation():
    project = Project(title="voiceless pitch", bpm=120)
    track = Track(name="lead")
    track.add_note(Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="la"))
    track.automation.pitch_cents = [
        EnvelopePoint(ticks=240, value=0.0, voiced=False),
        EnvelopePoint(ticks=480, value=0.0, voiced=True),
    ]
    project.add_track(track)
    return project, track


def test_pitch_envelope_state_is_forward_held_and_legacy_points_reset_to_voiced():
    points = [
        EnvelopePoint(ticks=240, value=0.0, voiced=False),
        EnvelopePoint(ticks=480, value=0.0),
    ]
    assert pitch_envelope_state(points, 239) == (0.0, True)
    assert pitch_envelope_state(points, 240) == (0.0, False)
    assert pitch_envelope_state(points, 479) == (0.0, False)
    assert pitch_envelope_state(points, 480) == (0.0, True)


def test_soulx_target_f0_uses_zero_only_inside_explicit_voiceless_segments():
    project, track = _project_with_voiceless_automation()
    f0 = _f0_for_notes(project, track.sorted_notes(), 1000, track.automation.pitch_cents)

    def at(seconds):
        return f0[int(round(seconds * 1000 / 20.0))]

    assert at(0.24) > 0
    assert at(0.26) == 0
    assert at(0.48) == 0
    assert at(0.52) > 0


def test_diagnostic_target_f0_keeps_voiceless_segments_nan_not_zero_hz():
    project, track = _project_with_voiceless_automation()
    times, f0 = pitch_curve_for_notes(project, track.sorted_notes(), pitch_automation=track.automation.pitch_cents)

    def at(seconds):
        return f0[int(round(seconds * 100))]

    assert np.isfinite(at(0.24))
    assert not np.isfinite(at(0.26))
    assert not np.isfinite(at(0.48))
    assert np.isfinite(at(0.52))


def test_fixture_voiceless_segments_remove_harmonic_output(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    project, track = _project_with_voiceless_automation()
    output = tmp_path / "voiceless.wav"
    FixtureVocalEngine().render_score(project, track, output)
    audio, sr = sf.read(str(output))

    def rms(start, end):
        segment = np.asarray(audio[int(start * sr):int(end * sr)], dtype=np.float32)
        return float(np.sqrt(np.mean(segment ** 2)))

    assert rms(0.08, 0.20) > 0.01
    assert rms(0.28, 0.45) == pytest.approx(0.0, abs=1e-8)
    assert rms(0.55, 0.80) > 0.01
