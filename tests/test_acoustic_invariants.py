from pathlib import Path

import numpy as np
import pytest

from openace.core.models import Note, Project
from openace.core.phonemes import PhonemeError, ensure_note_phonemes
from openace.core.pitch import correct_octave_errors, sanitize_f0, transpose_notes_preserve_intervals
from openace.core.timing import validate_absolute_beat_anchor


def test_transpose_preserves_every_semitone_interval():
    notes = [
        Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"),
        Note(start_ticks=480, duration_ticks=480, pitch=64, lyric="好"),
        Note(start_ticks=960, duration_ticks=480, pitch=62, lyric="呀"),
    ]
    mapping = transpose_notes_preserve_intervals(notes, 5)
    shifted = [pitch for _, pitch in mapping]
    assert shifted == [65, 69, 67]
    assert [b - a for a, b in zip(shifted, shifted[1:])] == [4, -2]


def test_transpose_rejects_instead_of_octave_folding_or_clamping():
    notes = [Note(start_ticks=0, duration_ticks=480, pitch=126, lyric="高")]
    with pytest.raises(ValueError, match="clamping|octave"):
        transpose_notes_preserve_intervals(notes, 2)


def test_f0_zero_frames_are_neutralized_not_smoothed_as_pitch():
    f0 = [0.0, 0.0, 220.0, 0.0, 221.0, 0.0]
    out = sanitize_f0(f0, max_gap_frames=2)
    assert not np.any(out == 0.0)
    assert np.isnan(out[0])
    assert np.isfinite(out[3])


def test_isolated_octave_error_corrected_without_harming_real_leap():
    f0 = [220, 221, 440, 222, 221, 330, 331]
    out = correct_octave_errors(f0, median_window=5)
    assert out[2] == pytest.approx(220, rel=0.03)
    assert out[5] == pytest.approx(330, rel=0.01)


def test_vowel_is_absolute_beat_anchor_and_consonant_preonset_is_bounded():
    note = Note(start_ticks=480, duration_ticks=480, pitch=60, lyric="像")
    phonemes = ensure_note_phonemes(note, "zh")
    assert any(p.is_vowel and p.start_ms == 0 for p in phonemes)
    pre = abs(min((p.start_ms for p in phonemes if not p.is_vowel), default=0))
    assert 40 <= pre <= 90
    anchors = validate_absolute_beat_anchor([note], Project().ppq, Project().bpm)
    assert anchors[0].vowel_onset_ticks == 480


def test_unknown_or_empty_lyric_never_becomes_la():
    note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="")
    with pytest.raises(PhonemeError, match="never|empty"):
        ensure_note_phonemes(note, "zh")
    note2 = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="🙂")
    with pytest.raises(PhonemeError):
        ensure_note_phonemes(note2, "zh")


def test_pitch_automation_is_written_into_soulx_f0_metadata_curve():
    from openace.core.models import EnvelopePoint
    from openace.engines.soulx import _f0_for_notes

    project = Project(title="automation")
    note = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    base = _f0_for_notes(project, [note], 1000)
    automated = _f0_for_notes(
        project,
        [note],
        1000,
        [EnvelopePoint(ticks=0, value=0.0), EnvelopePoint(ticks=480, value=100.0)],
    )
    assert automated[24] > base[24] * 1.02
    assert base[0] == automated[0]


def test_soulx_adapter_uses_module_preprocess_entrypoint():
    source = Path("openace/engines/soulx.py").read_text()
    assert '"-m",\n            "preprocess.pipeline"' in source
    assert '"preprocess/pipeline.py"' not in source
