"""Validated high-level project editing operations shared by CLI and MCP."""
from __future__ import annotations

from pathlib import Path
import math
import re
from typing import Any, Dict, List, Optional

from openace.core.models import AudioClip, Breath, EnvelopePoint, Note, Phoneme, PitchPoint, Project, TempoPoint, Track, Vibrato, new_id
from openace.core.phonemes import ensure_note_phonemes, ensure_ordered_note_phonemes, phonemes_for_text
from openace.core.timing import validate_absolute_beat_anchor

AUTOMATION_KEYS = {"pitch_cents", "dynamic", "air", "falsetto", "tension", "energy", "volume", "pan"}


def validate_project(project: Project) -> None:
    for track in project.vocal_tracks():
        ordered = sorted(track.notes, key=lambda note: (note.start_ticks, note.pitch, note.id))
        for previous, following in zip(ordered, ordered[1:]):
            if following.start_ticks < previous.start_ticks + previous.duration_ticks:
                raise ValueError("vocal notes may not overlap on a monophonic track; trim or move the conflicting note")
        ensure_ordered_note_phonemes(
            track.notes,
            track.language,
            lambda note: project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0,
        )
        validate_absolute_beat_anchor(track.notes, project.ppq, project.bpm, project=project)


_TRACK_PATCH_FIELDS = {
    "name", "color", "language", "mute", "solo", "volume", "pan",
    "midi_channel", "midi_program", "openutau_singer", "openutau_phonemizer",
}
_SUPPORTED_LANGUAGES = {
    "zh", "zh-cn", "mandarin", "cmn",
    "en", "en-us", "en-gb", "english",
    "yue", "cantonese", "zh-hk",
    "mixed", "multilingual", "zh-en", "en-zh",
    "mixed-yue", "yue-en", "en-yue", "cantonese-english",
}


def update_track(project: Project, track_id: str, patch: Dict[str, Any]) -> Track:
    """Update validated track metadata/mixer fields without weakening musical validation."""
    unknown = sorted(set(patch) - _TRACK_PATCH_FIELDS)
    if unknown:
        raise ValueError("unsupported track patch fields: " + ", ".join(unknown))
    track = project.track(track_id)
    original = track.model_copy(deep=True)
    try:
        for key, value in patch.items():
            if key == "name":
                value = str(value).strip()
                if not value:
                    raise ValueError("track name must not be empty")
            elif key == "color":
                value = str(value)
                if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                    raise ValueError("track color must be a #RRGGBB hex color")
            elif key == "language":
                value = str(value).lower()
                if value not in _SUPPORTED_LANGUAGES:
                    raise ValueError(f"unsupported lyric language: {value}")
            elif key == "volume":
                value = float(value)
                if not 0.0 <= value <= 1.0:
                    raise ValueError("track volume must be normalized in [0, 1]")
            elif key == "pan":
                value = float(value)
                if not -1.0 <= value <= 1.0:
                    raise ValueError("track pan must be normalized in [-1, 1]")
            elif key in {"mute", "solo"}:
                value = bool(value)
            elif key in {"midi_channel", "midi_program"} and value is not None:
                value = int(value)
                limit = 15 if key == "midi_channel" else 127
                if not 0 <= value <= limit:
                    raise ValueError(f"{key} must be within [0, {limit}] or null")
            setattr(track, key, value)
        validate_project(project)
    except Exception:
        project.tracks = [original if item.id == track_id else item for item in project.tracks]
        raise
    return track


def duplicate_track(project: Project, track_id: str, name: Optional[str] = None) -> Track:
    """Duplicate a track with fresh object ids while sharing only immutable source media paths."""
    source = project.track(track_id)
    duplicate = source.model_copy(deep=True)
    duplicate.id = new_id("track")
    duplicate.name = (name or f"{source.name} copy").strip() or f"{source.name} copy"
    duplicate.created_by_job_id = None
    duplicate.render_path = None
    duplicate.render_revision = 0
    duplicate.render_fingerprint = None
    for note in duplicate.notes:
        note.id = new_id("note")
    for breath in duplicate.breaths:
        breath.id = new_id("br")
    for clip in duplicate.clips:
        clip.id = new_id("clip")
        clip.created_by_job_id = None
        clip.updated_by_job_id = None
    index = project.tracks.index(source)
    project.tracks.insert(index + 1, duplicate)
    validate_project(project)
    return duplicate


def delete_track(project: Project, track_id: str) -> bool:
    """Delete a track object; media/render files are user assets and are not removed."""
    before = len(project.tracks)
    project.tracks = [track for track in project.tracks if track.id != track_id]
    if len(project.tracks) == before:
        raise KeyError(f"track not found: {track_id}")
    validate_project(project)
    return True


def reorder_track(project: Project, track_id: str, index: int) -> Track:
    """Move a track to an exact zero-based arrangement index."""
    track = project.track(track_id)
    if index < 0 or index >= len(project.tracks):
        raise ValueError(f"track index must be within [0, {len(project.tracks) - 1}]")
    project.tracks.remove(track)
    project.tracks.insert(index, track)
    return track


def add_notes(project: Project, track_id: str, note_payloads: List[Dict[str, Any]]) -> List[Note]:
    track = project.track(track_id)
    added = []
    for payload in note_payloads:
        added.append(track.add_note(Note.model_validate(payload)))
    validate_project(project)
    return added


def update_note(project: Project, track_id: str, note_id: str, patch: Dict[str, Any]) -> Note:
    track = project.track(track_id)
    note = track.note(note_id)
    data = note.model_dump()
    data.update(patch)
    updated = Note.model_validate(data)
    track.notes = [updated if item.id == note_id else item for item in track.notes]
    track.notes.sort(key=lambda item: (item.start_ticks, item.pitch))
    validate_project(project)
    return updated


def _pitch_cents_at(points: List[PitchPoint], offset_ms: float) -> float:
    if not points:
        return 0.0
    ordered = sorted(points, key=lambda point: point.offset_ms)
    if offset_ms <= ordered[0].offset_ms:
        return float(ordered[0].cents)
    if offset_ms >= ordered[-1].offset_ms:
        return float(ordered[-1].cents)
    for left, right in zip(ordered, ordered[1:]):
        if left.offset_ms <= offset_ms <= right.offset_ms:
            ratio = (offset_ms - left.offset_ms) / max(1e-9, right.offset_ms - left.offset_ms)
            return float(left.cents + (right.cents - left.cents) * ratio)
    return float(ordered[-1].cents)


def _split_pitch_curve(points: List[PitchPoint], split_ms: float) -> tuple[List[PitchPoint], List[PitchPoint]]:
    if not points:
        return [], []
    boundary = _pitch_cents_at(points, split_ms)
    first = [point.model_copy(deep=True) for point in sorted(points, key=lambda item: item.offset_ms) if point.offset_ms < split_ms]
    first.append(PitchPoint(offset_ms=split_ms, cents=boundary))
    second = [PitchPoint(offset_ms=0.0, cents=boundary)]
    for point in sorted(points, key=lambda item: item.offset_ms):
        if point.offset_ms > split_ms:
            second.append(PitchPoint(offset_ms=point.offset_ms - split_ms, cents=point.cents))
    return first, second


def _split_phonemes_at_vowel(phonemes: List[Phoneme], split_ms: float) -> tuple[List[Phoneme], List[Phoneme]]:
    if not phonemes:
        return [], []
    ordered = [item.model_copy(deep=True) for item in sorted(phonemes, key=lambda point: point.start_ms)]
    split_index = None
    for index, phoneme in enumerate(ordered):
        end_ms = phoneme.start_ms + phoneme.duration_ms
        if phoneme.is_vowel and phoneme.start_ms <= split_ms < end_ms:
            split_index = index
            break
    if split_index is None:
        raise ValueError("split point must fall inside a sustained vowel; consonant-only tails cannot become independent sung notes")

    first: List[Phoneme] = []
    for index, phoneme in enumerate(ordered):
        end_ms = phoneme.start_ms + phoneme.duration_ms
        if end_ms <= split_ms:
            first.append(phoneme.model_copy(deep=True))
        elif index == split_index:
            part = phoneme.model_copy(deep=True)
            part.duration_ms = split_ms - phoneme.start_ms
            if part.duration_ms > 0.75:
                first.append(part)
        if index >= split_index:
            break

    source = ordered[split_index]
    vowel_end = source.start_ms + source.duration_ms
    second = [Phoneme(symbol=source.symbol, start_ms=0.0, duration_ms=vowel_end - split_ms, is_vowel=True)]
    cursor = second[0].duration_ms
    for phoneme in ordered[split_index + 1:]:
        continuation = phoneme.model_copy(deep=True)
        continuation.start_ms = cursor
        second.append(continuation)
        cursor += continuation.duration_ms
    return first, second


def split_note(project: Project, track_id: str, note_id: str, split_ticks: int) -> tuple[Note, Note]:
    """Split a note while preserving vowel continuity and expressive timing truthfully."""
    track = project.track(track_id)
    note = track.note(note_id)
    split_ticks = int(split_ticks)
    if split_ticks <= note.start_ticks or split_ticks >= note.start_ticks + note.duration_ticks:
        raise ValueError("split position must be inside the selected note")
    left_ticks = split_ticks - note.start_ticks
    right_ticks = note.start_ticks + note.duration_ticks - split_ticks
    original_duration_ms = project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0
    if note.lyric.strip() or note.phonemes:
        ensure_note_phonemes(note, track.language, original_duration_ms)
    split_ms = project.tick_duration_seconds(note.start_ticks, left_ticks) * 1000.0
    first_phonemes, second_phonemes = _split_phonemes_at_vowel(note.phonemes, split_ms) if note.phonemes else ([], [])
    first_pitch, second_pitch = _split_pitch_curve(note.pitch_curve, split_ms)

    first = note.model_copy(deep=True)
    first.duration_ticks = left_ticks
    first.phonemes = first_phonemes
    first.pitch_curve = first_pitch

    second = note.model_copy(deep=True)
    second.id = new_id("note")
    second.start_ticks = split_ticks
    second.duration_ticks = right_ticks
    second.phonemes = second_phonemes
    second.pitch_curve = second_pitch
    if second_phonemes:
        second.lyric = "-"
        if "continuation" not in second.techniques:
            second.techniques.append("continuation")

    if note.vibrato:
        split_ratio = left_ticks / note.duration_ticks
        vibrato_start = note.vibrato.start_ratio
        if vibrato_start < split_ratio:
            first.vibrato = note.vibrato.model_copy(deep=True)
            first.vibrato.start_ratio = vibrato_start / split_ratio
            # Vibrato phase is expressed in the note-local oscillator coordinate used by
            # pitch rendering (2πft + phase from note onset), not at the vibrato activation
            # point. Preserve exact oscillator continuity across the split boundary.
            continuation_phase = note.vibrato.phase + 2.0 * 3.141592653589793 * note.vibrato.frequency_hz * (split_ms / 1000.0)
            second.vibrato = Vibrato(
                start_ratio=0.0,
                depth_cents=note.vibrato.depth_cents,
                frequency_hz=note.vibrato.frequency_hz,
                phase=continuation_phase,
            )
        else:
            first.vibrato = None
            second.vibrato = note.vibrato.model_copy(deep=True)
            second.vibrato.start_ratio = max(0.0, (vibrato_start - split_ratio) / (right_ticks / note.duration_ticks))
    else:
        first.vibrato = None
        second.vibrato = None

    track.notes = [item for item in track.notes if item.id != note.id] + [first, second]
    track.notes.sort(key=lambda item: (item.start_ticks, item.pitch))
    validate_project(project)
    return first, second


def merge_notes(project: Project, track_id: str, note_ids: List[str]) -> Note:
    """Merge contiguous vocal notes without inventing pitch, phoneme, or expression data.

    Pitch differences are preserved as exact cent offsets relative to the first note's
    written pitch. Velocity/vibrato configurations that cannot be represented by one
    note are rejected loudly rather than approximated away.
    """
    if len(note_ids) < 2:
        raise ValueError("select at least two contiguous notes to merge")
    if len(set(note_ids)) != len(note_ids):
        raise ValueError("duplicate notes cannot be merged")
    track = project.track(track_id)
    by_id = {note.id: note for note in track.notes}
    missing = [note_id for note_id in note_ids if note_id not in by_id]
    if missing:
        raise KeyError(f"note not found: {missing[0]}")
    notes = sorted((by_id[note_id] for note_id in note_ids), key=lambda note: note.start_ticks)
    for left, right in zip(notes, notes[1:]):
        if left.end_ticks != right.start_ticks:
            raise ValueError("only exactly contiguous selected notes can be merged; include intervening notes or close gaps first")
    if len({note.velocity for note in notes}) != 1:
        raise ValueError("notes with different velocities cannot be merged truthfully into one velocity yet")
    if len({note.pitch_snap_first for note in notes}) != 1:
        raise ValueError("notes with different pitch-snap behavior cannot be merged truthfully")
    continuation_chain = all(note.lyric == "-" and "continuation" in note.techniques for note in notes[1:])
    if any(note.vibrato for note in notes) and not continuation_chain:
        raise ValueError("vibrato-bearing notes can only be merged when they are split continuations of one vibrato span")
    if not continuation_chain:
        for note in notes:
            if note.phonemes and note.lyric.strip() and note.lyric.strip() != "-":
                default_symbols = [token.symbol for token in phonemes_for_text(note.lyric, track.language)]
                if [phoneme.symbol for phoneme in note.phonemes] != default_symbols:
                    raise ValueError("notes with custom phoneme overrides cannot be merged yet; reset phonemes first rather than losing pronunciation edits")

    first = notes[0]
    merged_duration = notes[-1].end_ticks - first.start_ticks
    merged = first.model_copy(deep=True)
    merged.duration_ticks = merged_duration
    merged.lyric = "".join(note.lyric for note in notes if note.lyric != "-")
    merged.techniques = sorted({technique for note in notes for technique in note.techniques if technique != "continuation"})

    merged_phonemes: List[Phoneme] = []
    merged_pitch: List[PitchPoint] = []
    base_pitch = first.pitch
    for index, note in enumerate(notes):
        note_duration_ms = project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0
        if note.lyric.strip() or note.phonemes:
            ensure_note_phonemes(note, track.language, note_duration_ms)
        note_offset_ms = project.seconds_between_ticks(first.start_ticks, note.start_ticks) * 1000.0
        if continuation_chain:
            for phoneme in sorted(note.phonemes, key=lambda item: item.start_ms):
                shifted = phoneme.model_copy(deep=True)
                shifted.start_ms += note_offset_ms
                merged_phonemes.append(shifted)

        ordered_pitch = sorted(note.pitch_curve, key=lambda item: item.offset_ms)
        pitch_delta = (note.pitch - base_pitch) * 100.0
        start_cents = pitch_delta + _pitch_cents_at(ordered_pitch, 0.0)
        end_cents = pitch_delta + _pitch_cents_at(ordered_pitch, note_duration_ms)
        if index > 0 and merged_pitch:
            before = _pitch_cents_at(merged_pitch, max(0.0, note_offset_ms - 0.01))
            merged_pitch.append(PitchPoint(offset_ms=max(0.0, note_offset_ms - 0.01), cents=before))
        merged_pitch.append(PitchPoint(offset_ms=note_offset_ms, cents=start_cents))
        for point in ordered_pitch:
            absolute = note_offset_ms + point.offset_ms
            if absolute <= note_offset_ms + 0.005 or absolute >= note_offset_ms + note_duration_ms - 0.005:
                continue
            merged_pitch.append(PitchPoint(offset_ms=absolute, cents=point.cents + pitch_delta))
        end_offset = note_offset_ms + note_duration_ms
        if index == len(notes) - 1:
            merged_pitch.append(PitchPoint(offset_ms=end_offset, cents=end_cents))
        else:
            merged_pitch.append(PitchPoint(offset_ms=max(0.0, end_offset - 0.01), cents=end_cents))

    if continuation_chain and merged_phonemes:
        coalesced: List[Phoneme] = []
        for phoneme in sorted(merged_phonemes, key=lambda item: item.start_ms):
            if coalesced:
                previous = coalesced[-1]
                if previous.symbol == phoneme.symbol and previous.is_vowel and phoneme.is_vowel and abs(previous.start_ms + previous.duration_ms - phoneme.start_ms) <= 0.75:
                    previous.duration_ms += phoneme.duration_ms
                    continue
            coalesced.append(phoneme)
        merged_phonemes = coalesced

    # Deduplicate near-identical anchors while preserving deliberate pitch steps.
    deduped: List[PitchPoint] = []
    for point in sorted(merged_pitch, key=lambda item: item.offset_ms):
        if deduped and abs(point.offset_ms - deduped[-1].offset_ms) < 0.02 and abs(point.cents - deduped[-1].cents) < 0.01:
            continue
        deduped.append(point)
    merged.pitch_curve = deduped
    merged.phonemes = merged_phonemes if continuation_chain else []
    merged.vibrato = None
    if continuation_chain:
        total_ms = project.tick_duration_seconds(first.start_ticks, merged_duration) * 1000.0
        vibrato_start_ms = None
        vibrato_template = None
        vibrato_phase = None
        for note in notes:
            note_offset_ms = project.seconds_between_ticks(first.start_ticks, note.start_ticks) * 1000.0
            note_duration_ms = project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0
            if not note.vibrato:
                if vibrato_template is not None:
                    raise ValueError("vibrato continuity is broken inside the selected continuation chain")
                continue
            candidate_start = note_offset_ms + note.vibrato.start_ratio * note_duration_ms if note.vibrato.start_ratio > 0.000001 else note_offset_ms
            candidate_phase = (note.vibrato.phase - math.tau * note.vibrato.frequency_hz * note_offset_ms / 1000.0) % math.tau
            if vibrato_template is None:
                vibrato_template = note.vibrato
                vibrato_start_ms = candidate_start
                vibrato_phase = candidate_phase
                continue
            if abs(note.vibrato.depth_cents - vibrato_template.depth_cents) > 0.01 or abs(note.vibrato.frequency_hz - vibrato_template.frequency_hz) > 0.001:
                raise ValueError("split continuations have inconsistent vibrato depth/frequency and cannot be merged truthfully")
            if note.vibrato.start_ratio > 0.000001 and vibrato_start_ms is not None and abs(candidate_start - vibrato_start_ms) > 1.0:
                raise ValueError("split continuations have inconsistent vibrato start times and cannot be merged truthfully")
            if vibrato_phase is not None:
                phase_error = abs((candidate_phase - vibrato_phase + math.pi) % math.tau - math.pi)
                if phase_error > 0.05:
                    raise ValueError("split continuations have inconsistent vibrato phase and cannot be merged truthfully")
        if vibrato_template is not None and vibrato_start_ms is not None and vibrato_phase is not None and total_ms > 0:
            merged.vibrato = Vibrato(
                start_ratio=max(0.0, min(1.0, vibrato_start_ms / total_ms)),
                depth_cents=vibrato_template.depth_cents,
                frequency_hz=vibrato_template.frequency_hz,
                phase=vibrato_phase,
            )

    ids = {note.id for note in notes}
    track.notes = [note for note in track.notes if note.id not in ids] + [merged]
    track.notes.sort(key=lambda item: (item.start_ticks, item.pitch))
    validate_project(project)
    return merged


def delete_note(project: Project, track_id: str, note_id: str) -> bool:
    deleted = project.track(track_id).delete_note(note_id)
    if deleted:
        validate_project(project)
    return deleted


def set_automation_lane(project: Project, track_id: str, lane: str, points: List[Dict[str, Any]]) -> List[EnvelopePoint]:
    if lane not in AUTOMATION_KEYS:
        raise ValueError(f"unsupported automation lane: {lane}")
    track = project.track(track_id)
    parsed = sorted((EnvelopePoint.model_validate(point) for point in points), key=lambda point: point.ticks)
    if lane == "pitch_cents":
        if any(point.value < -600 or point.value > 600 for point in parsed):
            raise ValueError("pitch_cents values must be within ±600 cents")
    elif lane == "pan":
        if any(point.value < -1 or point.value > 1 for point in parsed):
            raise ValueError("pan values must be normalized in [-1, 1]")
    elif any(point.value < 0 or point.value > 1 for point in parsed):
        raise ValueError(f"{lane} values must be normalized in [0, 1]")
    setattr(track.automation, lane, parsed)
    return parsed


def upsert_breath(project: Project, track_id: str, payload: Dict[str, Any], breath_id: Optional[str] = None) -> Breath:
    track = project.track(track_id)
    if breath_id:
        for index, breath in enumerate(track.breaths):
            if breath.id == breath_id:
                data = breath.model_dump()
                data.update(payload)
                updated = Breath.model_validate(data)
                track.breaths[index] = updated
                track.breaths.sort(key=lambda item: item.start_ticks)
                return updated
        raise KeyError(f"breath not found: {breath_id}")
    breath = Breath.model_validate(payload)
    track.breaths.append(breath)
    track.breaths.sort(key=lambda item: item.start_ticks)
    return breath


def delete_breath(project: Project, track_id: str, breath_id: str) -> bool:
    track = project.track(track_id)
    before = len(track.breaths)
    track.breaths = [breath for breath in track.breaths if breath.id != breath_id]
    return len(track.breaths) != before


def upsert_audio_clip(project: Project, track_id: str, payload: Dict[str, Any], clip_id: Optional[str] = None) -> AudioClip:
    track = project.track(track_id)
    path = payload.get("path")
    if path is not None and not Path(str(path)).exists():
        raise ValueError(f"audio clip file does not exist: {path}")
    if clip_id:
        for index, clip in enumerate(track.clips):
            if clip.id == clip_id:
                data = clip.model_dump()
                data.update(payload)
                updated = AudioClip.model_validate(data)
                track.clips[index] = updated
                track.clips.sort(key=lambda item: item.start_ticks)
                return updated
        raise KeyError(f"clip not found: {clip_id}")
    clip = AudioClip.model_validate(payload)
    track.clips.append(clip)
    track.clips.sort(key=lambda item: item.start_ticks)
    return clip


def delete_audio_clip(project: Project, track_id: str, clip_id: str) -> bool:
    track = project.track(track_id)
    before = len(track.clips)
    track.clips = [clip for clip in track.clips if clip.id != clip_id]
    return len(track.clips) != before


def set_tempo_map(project: Project, bpm: Optional[float], points: List[Dict[str, Any]]) -> List[TempoPoint]:
    if bpm is not None:
        if bpm <= 0:
            raise ValueError("bpm must be positive")
        project.bpm = float(bpm)
    parsed = [TempoPoint.model_validate(point) for point in points]
    deduped: dict[int, float] = {}
    for point in parsed:
        if point.ticks > 0:
            deduped[point.ticks] = point.bpm
    project.tempo_map = [TempoPoint(ticks=ticks, bpm=point_bpm) for ticks, point_bpm in sorted(deduped.items())]
    # Force conversion evaluation so malformed maps cannot be saved silently.
    project.ticks_to_seconds(project.duration_ticks())
    return project.tempo_map


def assign_voice(project: Project, track_id: str, voice_id: str, reference_voice_path: Optional[str]) -> Dict[str, Any]:
    track = project.track(track_id)
    if reference_voice_path and not Path(reference_voice_path).exists():
        raise ValueError(f"reference voice file does not exist: {reference_voice_path}")
    track.voice_id = voice_id
    track.reference_voice_path = reference_voice_path
    return {"track_id": track.id, "voice_id": track.voice_id, "reference_voice_path": track.reference_voice_path}


def _clip_duration(project: Project, clip: AudioClip) -> int:
    return int(clip.duration_ticks or project.ppq * 8)


def _envelope_value(points: List[EnvelopePoint], ticks: int) -> float | None:
    if not points:
        return None
    ordered = sorted(points, key=lambda point: point.ticks)
    if ticks <= ordered[0].ticks:
        return float(ordered[0].value)
    if ticks >= ordered[-1].ticks:
        return float(ordered[-1].value)
    for left, right in zip(ordered, ordered[1:]):
        if left.ticks <= ticks <= right.ticks:
            ratio = (ticks - left.ticks) / max(1, right.ticks - left.ticks)
            return float(left.value + (right.value - left.value) * ratio)
    return float(ordered[-1].value)


def ripple_delete_time_range(project: Project, start_ticks: int, end_ticks: int) -> dict:
    """Destructively ripple-delete a musical time range across every track.

    Vocal notes crossing either boundary are split with the same vowel-continuity
    rules as manual note splitting; invalid boundary positions fail loudly rather
    than creating lyrically impossible notes. Audio clips are cut source-accurately.
    """
    start_ticks = int(start_ticks)
    end_ticks = int(end_ticks)
    if start_ticks < 0 or end_ticks <= start_ticks:
        raise ValueError("ripple delete requires 0 <= start_ticks < end_ticks")
    ripple = end_ticks - start_ticks
    candidate = project.model_copy(deep=True)

    # Boundary-split vocal notes atomically. split_note validates invariants and
    # refuses consonant-only continuations, so a failed attempt must not partially
    # mutate the user's project.
    before_split = candidate.model_copy(deep=True)
    try:
        for boundary in (start_ticks, end_ticks):
            for track in candidate.tracks:
                for note in list(track.notes):
                    if note.start_ticks < boundary < note.start_ticks + note.duration_ticks:
                        split_note(candidate, track.id, note.id, boundary)
    except Exception:
        candidate = before_split
        raise

    removed = {"clips": 0, "notes": 0, "breaths": 0, "automation_points": 0, "tempo_points": 0}
    for track in candidate.tracks:
        new_clips: List[AudioClip] = []
        for original in sorted(track.clips, key=lambda item: item.start_ticks):
            clip = original.model_copy(deep=True)
            duration = _clip_duration(candidate, clip)
            clip_start = clip.start_ticks
            clip_end = clip_start + duration
            if duration <= 0:
                continue
            if clip_end <= start_ticks:
                new_clips.append(clip)
            elif clip_start >= end_ticks:
                clip.start_ticks = max(0, clip.start_ticks - ripple)
                new_clips.append(clip)
            elif clip_start >= start_ticks and clip_end <= end_ticks:
                removed["clips"] += 1
            elif clip_start < start_ticks and clip_end <= end_ticks:
                clip.duration_ticks = start_ticks - clip_start
                clip.fade_out_ticks = 0
                if clip.duration_ticks > 0:
                    new_clips.append(clip)
                    removed["clips"] += 1
            elif clip_start >= start_ticks and clip_end > end_ticks:
                cut = end_ticks - clip_start
                clip.offset_ticks += cut
                clip.duration_ticks = clip_end - end_ticks
                clip.start_ticks = start_ticks
                clip.fade_in_ticks = 0
                new_clips.append(clip)
                removed["clips"] += 1
            else:  # crosses the whole deletion range
                right = clip.model_copy(deep=True)
                right.id = new_id("clip")
                right.start_ticks = start_ticks
                right.duration_ticks = clip_end - end_ticks
                right.offset_ticks += end_ticks - clip_start
                right.fade_in_ticks = 0
                clip.duration_ticks = start_ticks - clip_start
                clip.fade_out_ticks = 0
                if clip.duration_ticks > 0:
                    new_clips.append(clip)
                if right.duration_ticks > 0:
                    new_clips.append(right)
                removed["clips"] += 1
        track.clips = sorted(new_clips, key=lambda item: item.start_ticks)

        kept_notes = []
        for note in track.notes:
            note_end = note.start_ticks + note.duration_ticks
            if note_end <= start_ticks:
                kept_notes.append(note)
            elif note.start_ticks >= end_ticks:
                note.start_ticks = max(0, note.start_ticks - ripple)
                kept_notes.append(note)
            else:
                removed["notes"] += 1
        track.notes = sorted(kept_notes, key=lambda item: (item.start_ticks, item.pitch))

        kept_breaths = []
        for breath in track.breaths:
            breath_end = breath.start_ticks + breath.duration_ticks
            if breath_end <= start_ticks:
                kept_breaths.append(breath)
            elif breath.start_ticks >= end_ticks:
                breath.start_ticks = max(0, breath.start_ticks - ripple)
                kept_breaths.append(breath)
            else:
                removed["breaths"] += 1
        track.breaths = sorted(kept_breaths, key=lambda item: item.start_ticks)

        for lane_name in AUTOMATION_KEYS:
            lane = getattr(track.automation, lane_name)
            end_value = _envelope_value(lane, end_ticks)
            kept = []
            for point in lane:
                if point.ticks < start_ticks:
                    kept.append(point)
                elif point.ticks >= end_ticks:
                    point.ticks = max(0, point.ticks - ripple)
                    kept.append(point)
                else:
                    removed["automation_points"] += 1
            if end_value is not None and not any(point.ticks == start_ticks for point in kept):
                kept.append(EnvelopePoint(ticks=start_ticks, value=end_value))
            setattr(track.automation, lane_name, sorted(kept, key=lambda point: point.ticks))

    if candidate.tempo_map:
        kept_tempo = []
        for point in candidate.tempo_map:
            if point.ticks == 0 or point.ticks < start_ticks:
                kept_tempo.append(point)
            elif point.ticks >= end_ticks:
                point.ticks = max(0, point.ticks - ripple)
                kept_tempo.append(point)
            else:
                removed["tempo_points"] += 1
        deduped = []
        seen = set()
        for point in sorted(kept_tempo, key=lambda item: item.ticks):
            if point.ticks in seen:
                continue
            seen.add(point.ticks)
            deduped.append(point)
        candidate.tempo_map = deduped

    validate_project(candidate)
    project.tracks = candidate.tracks
    project.tempo_map = candidate.tempo_map
    return {"start_ticks": start_ticks, "end_ticks": end_ticks, "ripple_ticks": ripple, "removed": removed}
