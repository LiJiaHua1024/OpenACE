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


def test_manual_placeholder_la_phoneme_is_rejected():
    from openace.core.models import Phoneme
    from openace.core.phonemes import ensure_note_phonemes

    note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你")
    note.phonemes = [Phoneme(symbol="la", start_ms=0, duration_ms=100, is_vowel=True)]
    with pytest.raises(PhonemeError, match="placeholder"):
        ensure_note_phonemes(note, "zh")


def test_note_vibrato_is_written_into_soulx_f0_metadata_curve():
    from openace.engines.soulx import _f0_for_notes

    project = Project(title="vibrato")
    plain = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    vibrating = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    from openace.core.models import Vibrato
    vibrating.vibrato = Vibrato(start_ratio=0.0, depth_cents=40.0, frequency_hz=5.0, phase=0.0)
    base = _f0_for_notes(project, [plain], 1000)
    vibrato = _f0_for_notes(project, [vibrating], 1000)
    assert max(abs(a - b) for a, b in zip(base, vibrato)) > 1.0
    assert len({round(x / base[0], 4) for x in vibrato[:45]}) > 4


def test_note_pitch_handles_are_interpolated_into_soulx_and_diagnostic_f0():
    from openace.core.models import PitchPoint
    from openace.core.pitch import pitch_curve_for_notes
    from openace.engines.soulx import _f0_for_notes

    project = Project(title="pitch-handles")
    plain = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    bent = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    bent.pitch_curve = [PitchPoint(offset_ms=0, cents=0), PitchPoint(offset_ms=500, cents=100)]
    base = _f0_for_notes(project, [plain], 1000)
    rendered = _f0_for_notes(project, [bent], 1000)
    assert rendered[12] / base[12] == pytest.approx(2 ** (48 / 1200), rel=0.002)

    _, diagnostic_f0 = pitch_curve_for_notes(project.ppq, project.bpm, [bent], frame_ms=10.0)
    base_hz = 261.6255653005986
    assert diagnostic_f0[25] / base_hz == pytest.approx(2 ** (50 / 1200), rel=0.002)


def test_diagnostic_target_f0_includes_track_pitch_automation():
    from openace.core.models import EnvelopePoint
    from openace.core.pitch import pitch_curve_for_notes

    project = Project(title="diagnostic automation")
    note = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    automation = [EnvelopePoint(ticks=0, value=0.0), EnvelopePoint(ticks=960, value=100.0)]
    _, plain = pitch_curve_for_notes(project.ppq, project.bpm, [note], frame_ms=10.0)
    _, automated = pitch_curve_for_notes(project.ppq, project.bpm, [note], frame_ms=10.0, pitch_automation=automation)
    assert automated[50] / plain[50] == pytest.approx(2 ** (50 / 1200), rel=0.002)


def test_post_vowel_consonants_remain_after_beat_anchored_vowel():
    note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="sing")
    phonemes = ensure_note_phonemes(note, "en", duration_ms=500.0)
    symbols = [p.symbol for p in phonemes]
    assert symbols == ["s", "ɪ", "ŋ"]
    assert phonemes[0].start_ms < 0
    assert phonemes[1].start_ms == 0
    assert phonemes[2].start_ms > 0
    assert phonemes[2].start_ms + phonemes[2].duration_ms <= 500.1


def test_short_multi_coda_timing_ends_at_note_duration():
    from openace.core.phonemes import timed_phonemes, tokens_from_symbols

    timed = timed_phonemes(tokens_from_symbols(["s", "ɪ", "ŋ", "k"]), 120.0)
    final_end = timed[-1].start_ms + timed[-1].duration_ms
    assert final_end == pytest.approx(120.0, abs=0.01)
    assert all(phoneme.duration_ms > 0 for phoneme in timed)


def test_manual_phoneme_timing_rejects_gaps_and_unanchored_vowels():
    from openace.core.models import Phoneme

    gap_note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你")
    gap_note.phonemes = [
        Phoneme(symbol="n", start_ms=-45, duration_ms=35, is_vowel=False),
        Phoneme(symbol="i", start_ms=0, duration_ms=100, is_vowel=True),
    ]
    with pytest.raises(PhonemeError, match="contiguous"):
        ensure_note_phonemes(gap_note, "zh")

    shifted_note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你")
    shifted_note.phonemes = [Phoneme(symbol="i", start_ms=5, duration_ms=100, is_vowel=True)]
    with pytest.raises(PhonemeError, match="beat anchor"):
        ensure_note_phonemes(shifted_note, "zh")
