"""Validated high-level project editing operations shared by CLI and MCP."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from openace.core.models import AudioClip, Breath, EnvelopePoint, Note, Project, TempoPoint
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
