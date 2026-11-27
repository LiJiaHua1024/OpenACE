"""Validated high-level project editing operations shared by CLI and MCP."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from openace.core.models import AudioClip, Breath, EnvelopePoint, Note, Phoneme, PitchPoint, Project, TempoPoint, Vibrato, new_id
from openace.core.phonemes import ensure_note_phonemes
from openace.core.timing import validate_absolute_beat_anchor

AUTOMATION_KEYS = {"pitch_cents", "dynamic", "air", "falsetto", "tension", "energy"}


def validate_project(project: Project) -> None:
    for track in project.vocal_tracks():
        for note in track.notes:
            if note.lyric.strip():
                ensure_note_phonemes(note, track.language, project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0)
        validate_absolute_beat_anchor(track.notes, project.ppq, project.bpm, project=project)


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
            vibrato_start_ms = note.vibrato.start_ratio * original_duration_ms
            elapsed_seconds = max(0.0, split_ms - vibrato_start_ms) / 1000.0
            continuation_phase = note.vibrato.phase + 2.0 * 3.141592653589793 * note.vibrato.frequency_hz * elapsed_seconds
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
        if any(point.value < -100 or point.value > 100 for point in parsed):
            raise ValueError("pitch_cents values must be within ±100 cents")
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
