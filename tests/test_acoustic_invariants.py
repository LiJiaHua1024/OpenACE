from pathlib import Path

import numpy as np
import pytest

from openace.core.models import Note, Project, Track
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

    _, diagnostic_f0 = pitch_curve_for_notes(project, [bent], frame_ms=10.0)
    base_hz = 261.6255653005986
    assert diagnostic_f0[25] / base_hz == pytest.approx(2 ** (50 / 1200), rel=0.002)


def test_diagnostic_target_f0_includes_track_pitch_automation():
    from openace.core.models import EnvelopePoint
    from openace.core.pitch import pitch_curve_for_notes

    project = Project(title="diagnostic automation")
    note = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    automation = [EnvelopePoint(ticks=0, value=0.0), EnvelopePoint(ticks=960, value=100.0)]
    _, plain = pitch_curve_for_notes(project, [note], frame_ms=10.0)
    _, automated = pitch_curve_for_notes(project, [note], frame_ms=10.0, pitch_automation=automation)
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

def test_cantonese_jyutping_phonemes_and_soulx_tokens_are_validated():
    import json
    from openace.core.phonemes import cantonese_jyutping_syllables, phonemes_for_text
    from openace.engines.soulx import lyric_to_soulx_tokens

    assert cantonese_jyutping_syllables("我愛你") == ["ngo5", "oi3", "nei5"]
    tokens = phonemes_for_text("我愛你", "yue")
    assert [(token.symbol, token.is_vowel) for token in tokens] == [
        ("ŋ", False), ("ɔː", True),
        ("ɔː", True), ("i", False),
        ("n", False), ("ɛː", True), ("i", False),
    ]
    syllabic = phonemes_for_text("唔", "yue")
    assert [(token.symbol, token.is_vowel) for token in syllabic] == [("m̩", True)]
    phoneset = set(json.loads(Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json").read_text(encoding="utf-8")))
    assert lyric_to_soulx_tokens("我愛你", "yue", phoneset) == ["yue_ngo5", "yue_oi3", "yue_nei5"]


def test_cantonese_unknown_or_non_cjk_lyrics_fail_loudly():
    from openace.core.phonemes import phonemes_for_text

    for lyric in ["A", "𠮷"]:
        with pytest.raises(PhonemeError):
            phonemes_for_text(lyric, "yue")


def test_cantonese_soulx_metadata_uses_cantonese_language_and_yue_phones():
    import json
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Cantonese", language="yue")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="我"))
    project.add_track(track)
    phoneset_path = Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json")
    metadata = build_soulx_target_metadata(project, track, phoneset_path)[0]
    assert metadata["language"] == "Cantonese"
    assert "yue_ngo5" in metadata["phoneme"].split()
    assert "zh_" not in metadata["phoneme"]



def test_soulx_metadata_melisma_continuation_uses_type3_and_source_syllable():
    import json
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Melisma", language="zh")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="-"))
    project.add_track(track)
    phoneset_path = Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json")
    metadata = build_soulx_target_metadata(project, track, phoneset_path)[0]
    phonemes = metadata["phoneme"].split()
    text = metadata["text"].split()
    types = [int(x) for x in metadata["note_type"].split()]
    sung_indexes = [index for index, value in enumerate(types) if value in {2, 3}]
    assert [types[index] for index in sung_indexes] == [2, 3]
    assert [text[index] for index in sung_indexes] == ["你", "你"]
    assert phonemes[sung_indexes[0]] == phonemes[sung_indexes[1]]
    assert "-" not in text


def test_project_validation_derives_melisma_continuation_vowel():
    from openace.core.editing import validate_project

    project = Project(bpm=120)
    track = Track(name="Melisma validation", language="zh")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="-"))
    project.add_track(track)
    validate_project(project)
    first = track.notes[0]
    second = track.notes[1]
    first_vowel = [phoneme for phoneme in first.phonemes if phoneme.is_vowel][-1]
    assert len(second.phonemes) == 1
    assert second.phonemes[0].symbol == first_vowel.symbol
    assert second.phonemes[0].is_vowel
    assert second.phonemes[0].start_ms == pytest.approx(0.0)


def test_project_validation_rejects_orphan_melisma_continuation():
    from openace.core.editing import validate_project

    project = Project(bpm=120)
    track = Track(name="Orphan melisma", language="zh")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="-"))
    project.add_track(track)
    with pytest.raises(PhonemeError, match="before a sung lyric"):
        validate_project(project)


def _soulx_timeline_items(metadata):
    durations = [float(value) for value in metadata["duration"].split()]
    phonemes = metadata["phoneme"].split()
    types = [int(value) for value in metadata["note_type"].split()]
    items = []
    cursor = 0.0
    for duration, phoneme, note_type in zip(durations, phonemes, types):
        items.append({"start": cursor - 0.1, "end": cursor + duration - 0.1, "phoneme": phoneme, "type": note_type})
        cursor += duration
    return items


def test_soulx_preonset_consumes_preceding_silence_without_moving_vowel_anchor():
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Preonset", language="zh")
    track.add_note(Note(start_ticks=960, duration_ticks=480, pitch=60, lyric="你"))
    project.add_track(track)
    metadata = build_soulx_target_metadata(
        project,
        track,
        Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json"),
    )[0]
    items = _soulx_timeline_items(metadata)
    sung = next(item for item in items if item["type"] == 2)
    # At 120 BPM tick 960 is exactly 1s. The 45ms consonant preonset begins in the
    # preceding silence, leaving the vowel anchor at the symbolic onset.
    assert sung["start"] == pytest.approx(0.955, abs=0.001)
    assert sung["end"] == pytest.approx(1.5, abs=0.001)
    assert items[0]["phoneme"] == "<SP>"
    assert items[0]["end"] == pytest.approx(0.955, abs=0.001)
    f0 = [float(value) for value in metadata["f0"].split()]
    first_voiced = next(index for index, value in enumerate(f0) if value > 0)
    assert first_voiced * 20 == pytest.approx(1100, abs=10)  # metadata 1.1s == project 1.0s + preroll


def test_soulx_melisma_continuation_starts_exactly_at_symbolic_onset():
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Melisma timing", language="zh")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="-"))
    project.add_track(track)
    metadata = build_soulx_target_metadata(
        project,
        track,
        Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json"),
    )[0]
    sung = [item for item in _soulx_timeline_items(metadata) if item["type"] in {2, 3}]
    assert sung[0]["start"] == pytest.approx(-0.045, abs=0.001)
    assert sung[0]["end"] == pytest.approx(0.5, abs=0.001)
    assert sung[1]["start"] == pytest.approx(0.5, abs=0.001)
    assert sung[1]["end"] == pytest.approx(1.0, abs=0.001)


def test_manual_english_phoneme_override_is_written_to_soulx_tokens():
    from openace.core.phonemes import timed_phonemes, tokens_from_symbols
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Manual English", language="en")
    note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="sing")
    note.phonemes = timed_phonemes(tokens_from_symbols(["s", "i", "ŋ"]), 500.0)
    track.add_note(note)
    project.add_track(track)
    metadata = build_soulx_target_metadata(
        project,
        track,
        Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json"),
    )[0]
    assert "en_S-IY0-NG" in metadata["phoneme"].split()


def test_exact_upstream_mandarin_syllable_override_is_written_to_soulx_tokens():
    from openace.core.phonemes import timed_phonemes, tokens_from_symbols
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Manual Mandarin", language="zh")
    note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你")
    note.phonemes = timed_phonemes(tokens_from_symbols(["zh_ni4"]), 500.0)
    track.add_note(note)
    project.add_track(track)
    metadata = build_soulx_target_metadata(
        project,
        track,
        Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json"),
    )[0]
    assert "zh_ni4" in metadata["phoneme"].split()
    assert "zh_ni3" not in metadata["phoneme"].split()
    sung = next(item for item in _soulx_timeline_items(metadata) if item["type"] == 2)
    assert sung["start"] == pytest.approx(-0.045, abs=0.001)


def test_unrepresentable_mandarin_subsyllable_override_fails_loudly():
    from openace.core.phonemes import timed_phonemes, tokens_from_symbols
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Impossible Mandarin", language="zh")
    note = Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你")
    note.phonemes = timed_phonemes(tokens_from_symbols(["m", "i"]), 500.0)
    track.add_note(note)
    project.add_track(track)
    with pytest.raises(PhonemeError, match="syllable-level tokens"):
        build_soulx_target_metadata(
            project,
            track,
            Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json"),
        )


def test_vocal_alignment_helpers_measure_sustained_onset_and_transition():
    from openace.core.diagnostics import measured_pitch_transition, sustained_voiced_onsets

    times = np.arange(100) * 0.01
    f0 = np.full(100, np.nan)
    f0[10:50] = 261.0
    f0[50:90] = 294.0
    assert sustained_voiced_onsets(times, f0)[0] == pytest.approx(0.1)
    assert measured_pitch_transition(times, f0, 0.5, 261.0, 294.0) == pytest.approx(0.5)

    noisy = f0.copy()
    noisy[49] = np.nan
    noisy[50] = np.nan
    noisy[51] = np.nan
    assert measured_pitch_transition(times, noisy, 0.5, 261.0, 294.0) == pytest.approx(0.52)


def test_beat_offsets_are_nan_until_rendered_onsets_are_measured():
    from openace.core.diagnostics import beat_offsets_ms

    project = Project(bpm=120)
    notes = [Note(start_ticks=480, duration_ticks=480, pitch=60, lyric="你")]
    offsets = beat_offsets_ms(project, notes)
    assert np.isnan(offsets[0])
    measured = beat_offsets_ms(project, notes, [0.52])
    assert measured[0] == pytest.approx(20.0)


def test_mixed_mandarin_english_tokens_and_soulx_phones_are_script_segmented():
    import json
    from openace.core.phonemes import phonemes_for_text
    from openace.engines.soulx import lyric_to_soulx_tokens

    tokens = phonemes_for_text("你 hello", "mixed")
    assert tokens[0].symbol == "n"
    assert any(token.symbol in {"hh", "h"} for token in tokens)
    assert any(token.is_vowel for token in tokens)
    phoneset = set(json.loads(Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json").read_text(encoding="utf-8")))
    soulx_tokens = lyric_to_soulx_tokens("你 hello", "mixed", phoneset)
    assert soulx_tokens[0] == "zh_ni3"
    assert any(token.startswith("en_") for token in soulx_tokens[1:])
    for token in soulx_tokens:
        if token.startswith("en_"):
            assert all(("en_" + piece) in phoneset for piece in token[3:].split("-"))
        else:
            assert token in phoneset


def test_mixed_language_metadata_combines_zh_and_en_tokens_with_dominant_language():
    from openace.engines.soulx import build_soulx_target_metadata

    project = Project(bpm=120)
    track = Track(name="Mixed", language="mixed")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="hello"))
    track.add_note(Note(start_ticks=960, duration_ticks=480, pitch=64, lyric="world"))
    project.add_track(track)
    metadata = build_soulx_target_metadata(project, track, Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json"))[0]
    phonemes = metadata["phoneme"].split()
    assert "zh_ni3" in phonemes
    assert any(token.startswith("en_") for token in phonemes)
    assert metadata["language"] == "English"
    assert "yue_" not in metadata["phoneme"]


def test_mixed_language_rejects_non_mandarin_cjk_or_japanese_scripts_loudly():
    from openace.core.phonemes import phonemes_for_text

    with pytest.raises(PhonemeError, match="unsupported character"):
        phonemes_for_text("你 こんにちは", "mixed")
