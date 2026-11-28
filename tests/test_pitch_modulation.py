import pytest

from openace.core.editing import merge_notes
from openace.core.models import Note, PitchPoint, Project, Track, Vibrato
from openace.core.pitch import note_expression_cents


def modulation_note(value: float) -> Note:
    return Note(
        start_ticks=0,
        duration_ticks=480,
        pitch=60,
        pitch_modulation=value,
        pitch_curve=[PitchPoint(offset_ms=0, cents=30)],
        vibrato=Vibrato(start_ratio=0.0, depth_cents=80, frequency_hz=1.0, phase=0.0),
    )


def test_pitch_modulation_scales_vibrato_not_pitch_anchors():
    duration_ms = 1000.0
    offset_ms = 250.0  # 1 Hz sine reaches +1 here.
    assert note_expression_cents(modulation_note(1.0), offset_ms, duration_ms) == pytest.approx(110.0)
    assert note_expression_cents(modulation_note(0.5), offset_ms, duration_ms) == pytest.approx(70.0)
    assert note_expression_cents(modulation_note(0.0), offset_ms, duration_ms) == pytest.approx(30.0)
    assert note_expression_cents(modulation_note(2.0), offset_ms, duration_ms) == pytest.approx(190.0)


def test_merge_rejects_different_pitch_modulation():
    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    first = track.add_note(Note(start_ticks=0, duration_ticks=240, pitch=60, lyric="你", pitch_modulation=1.0))
    second = track.add_note(Note(start_ticks=240, duration_ticks=240, pitch=60, lyric="好", pitch_modulation=0.5))
    with pytest.raises(ValueError, match="pitch modulation"):
        merge_notes(project, track.id, [first.id, second.id])
