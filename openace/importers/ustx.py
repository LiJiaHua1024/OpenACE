from __future__ import annotations

import math
from pathlib import Path

import yaml

from openace.core.models import (
    AudioClip,
    EnvelopePoint,
    Note,
    Phoneme,
    PitchPoint,
    Project,
    TempoPoint,
    TimeSignature,
    Track,
    TrackType,
    Vibrato,
)

_OPENUTAU_COLOR_HEX = {
    "Pink": "#F06292", "Red": "#EF5350", "Orange": "#FF8A65", "Yellow": "#FBC02D",
    "Light Green": "#CDDC39", "Green": "#66BB6A", "Light Blue": "#4FC3F7", "Blue": "#4EA6EA",
    "Purple": "#BA68C8", "Pink2": "#E91E63", "Red2": "#D32F2F", "Orange2": "#FF5722",
    "Yellow2": "#FF8F00", "Light Green2": "#AFB42B", "Green2": "#2E7D32",
    "Light Blue2": "#1976D2", "Blue2": "#3949AB", "Purple2": "#7B1FA2",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _linear_volume(db: float) -> float:
    """Convert OpenUtau's -24..+12 dB fader scale to OpenACE linear gain."""
    return round(10.0 ** (_clamp(float(db), -24.0, 12.0) / 20.0), 6)


def _color_hex(name: object) -> str:
    return _OPENUTAU_COLOR_HEX.get(str(name or ""), "#4EA6EA")


def _pitch_curve(raw_points) -> list[PitchPoint]:
    points = [
        PitchPoint(offset_ms=float(point.get("x", 0.0)), cents=float(point.get("y", 0.0)) * 10.0)
        for point in raw_points or []
    ]
    # OpenUtau requires the two default points even for untouched notes. Do not
    # mistake those serializer defaults for intentional user-drawn pitch automation.
    if len(points) == 2 and points[0].offset_ms == -40 and points[0].cents == 0 and points[1].offset_ms == 40 and points[1].cents == 0:
        return []
    return points


def _vibrato(raw) -> Vibrato | None:
    length = float((raw or {}).get("length", 0.0))
    if length <= 0.0:
        return None
    period = _clamp(float(raw.get("period", 175.0)), 5.0, 500.0)
    return Vibrato(
        start_ratio=_clamp(1.0 - length / 100.0, 0.0, 1.0),
        depth_cents=_clamp(float(raw.get("depth", 25.0)), 5.0, 200.0),
        frequency_hz=1000.0 / period,
        phase=(float(raw.get("shift", 0.0)) / 100.0) * 2.0 * math.pi,
    )


def _import_note(raw, part_position: int) -> Note:
    overrides = sorted(raw.get("phoneme_overrides") or [], key=lambda item: int(item.get("index", 0)))
    note = Note(
        start_ticks=part_position + int(raw.get("position", 0)),
        duration_ticks=max(1, int(raw.get("duration", 1))),
        pitch=int(raw.get("tone", 60)),
        lyric=str(raw.get("lyric", "") or ""),
        pitch_curve=_pitch_curve((raw.get("pitch") or {}).get("data")),
        vibrato=_vibrato(raw.get("vibrato")),
    )
    note.phonemes = [Phoneme(symbol=str(item.get("phoneme", "") or "")) for item in overrides]
    return note


def _import_curves(raw_curves, part_position: int) -> dict[str, list[EnvelopePoint]]:
    dynamic: list[EnvelopePoint] = []
    pitch: list[EnvelopePoint] = []
    for curve in raw_curves or []:
        xs = curve.get("xs") or []
        ys = curve.get("ys") or []
        for x, y in zip(xs, ys):
            ticks = part_position + int(x)
            if curve.get("abbr") == "dyn":
                dynamic.append(EnvelopePoint(ticks=ticks, value=_clamp(0.5 + float(y) / 120.0, 0.0, 1.0)))
            elif curve.get("abbr") == "pitd":
                pitch.append(EnvelopePoint(ticks=ticks, value=_clamp(float(y), -1200.0, 1200.0)))
    return {"dynamic": dynamic, "pitch_cents": pitch}


def _resolve_wave_path(ustx_path: Path, relative_path: object) -> str:
    value = str(relative_path or "").replace("\\", "/")
    if not value:
        return ""
    source = Path(value)
    if not source.is_absolute():
        source = (ustx_path.parent / source).resolve()
    return str(source)


def import_ustx(path: Path, title: str | None = None) -> Project:
    """Import a real OpenUtau 0.10 USTX project into OpenACE timeline semantics."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "tracks" not in raw:
        raise RuntimeError("invalid USTX project: missing tracks")
    project = Project(title=title or str(raw.get("name") or path.stem), ppq=480)
    tempos = raw.get("tempos") or []
    if tempos:
        project.tempo_map = [TempoPoint(ticks=int(item.get("position", 0)), bpm=float(item.get("bpm", 120.0))) for item in tempos]
        project.bpm = project.tempo_map[0].bpm
    signatures = raw.get("time_signatures") or []
    if signatures:
        first = signatures[0]
        project.time_signature = TimeSignature(
            numerator=int(first.get("beat_per_bar", 4)),
            denominator=int(first.get("beat_unit", 4)),
        )

    voice_parts_by_track: dict[int, list[dict]] = {}
    for part in raw.get("voice_parts") or []:
        voice_parts_by_track.setdefault(int(part.get("track_no", 0)), []).append(part)
    wave_parts_by_track: dict[int, list[dict]] = {}
    for part in raw.get("wave_parts") or []:
        wave_parts_by_track.setdefault(int(part.get("track_no", 0)), []).append(part)

    for index, raw_track in enumerate(raw.get("tracks") or []):
        voice_parts = voice_parts_by_track.get(index, [])
        track = Track(
            name=str(raw_track.get("track_name") or f"Track {index + 1}"),
            type=TrackType.VOCAL if voice_parts else TrackType.AUDIO,
            color=_color_hex(raw_track.get("track_color")),
            voice_id=str(raw_track.get("singer") or "zero-shot-reference"),
            mute=bool(raw_track.get("mute", False)),
            solo=bool(raw_track.get("solo", False)),
            volume=_linear_volume(float(raw_track.get("volume", 0.0))),
            pan=_clamp(float(raw_track.get("pan", 0.0)) / 100.0, -1.0, 1.0),
        )
        for part in sorted(voice_parts, key=lambda item: int(item.get("position", 0))):
            position = int(part.get("position", 0))
            for raw_note in part.get("notes") or []:
                track.notes.append(_import_note(raw_note, position))
            curves = _import_curves(part.get("curves"), position)
            track.automation.dynamic.extend(curves["dynamic"])
            track.automation.pitch_cents.extend(curves["pitch_cents"])
        track.notes.sort(key=lambda note: (note.start_ticks, note.pitch))
        track.automation.dynamic.sort(key=lambda point: point.ticks)
        track.automation.pitch_cents.sort(key=lambda point: point.ticks)

        for part in sorted(wave_parts_by_track.get(index, []), key=lambda item: int(item.get("position", 0))):
            file_seconds = float(part.get("file_duration_ms", 0.0)) / 1000.0
            skip = max(0, int(part.get("skip", 0)))
            trim = max(0, int(part.get("trim", 0)))
            position = max(0, int(part.get("position", 0)))
            file_start_ticks = position - skip
            file_start_seconds = project.ticks_to_seconds(file_start_ticks)
            file_end_ticks = project.seconds_to_ticks_float(file_start_seconds + file_seconds)
            full_ticks = int(round(file_end_ticks - file_start_ticks))
            duration = max(1, full_ticks - skip - trim)
            source = _resolve_wave_path(path, part.get("relative_path"))
            if not source:
                raise RuntimeError(f"USTX wave part {part.get('name') or '<unnamed>'} has no audio source path")
            track.clips.append(AudioClip(
                path=source,
                start_ticks=position,
                duration_ticks=duration,
                offset_ticks=skip,
                fade_in_ticks=max(0, int(part.get("fadein", 0))),
                fade_out_ticks=max(0, int(part.get("fadeout", 0))),
                label=str(part.get("name") or Path(source).name),
            ))
        project.add_track(track)
    return project
