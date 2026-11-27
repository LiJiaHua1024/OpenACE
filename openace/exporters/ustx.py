from __future__ import annotations

import math
import os
from pathlib import Path

import yaml

from openace.core.models import Note, Project, TrackType

# OpenUtau's UI palette is name-based, not hex-based. Map OpenACE's freely colored
# tracks to the closest real OpenUtau color instead of writing an invalid hex string.
_OPENUTAU_COLORS = {
    "Pink": "#F06292",
    "Red": "#EF5350",
    "Orange": "#FF8A65",
    "Yellow": "#FBC02D",
    "Light Green": "#CDDC39",
    "Green": "#66BB6A",
    "Light Blue": "#4FC3F7",
    "Blue": "#4EA6EA",
    "Purple": "#BA68C8",
    "Pink2": "#E91E63",
    "Red2": "#D32F2F",
    "Orange2": "#FF5722",
    "Yellow2": "#FF8F00",
    "Light Green2": "#AFB42B",
    "Green2": "#2E7D32",
    "Light Blue2": "#1976D2",
    "Blue2": "#3949AB",
    "Purple2": "#7B1FA2",
}


def _rgb(color: str) -> tuple[int, int, int] | None:
    value = color.strip().lstrip("#")
    if len(value) != 6:
        return None
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return None


def _nearest_openutau_color(color: str) -> str:
    source = _rgb(color)
    if source is None:
        return "Blue"
    return min(
        _OPENUTAU_COLORS,
        key=lambda name: sum((a - b) ** 2 for a, b in zip(source, _rgb(_OPENUTAU_COLORS[name]) or (0, 0, 0))),
    )


def _track_volume_db(volume: float) -> float:
    """Convert OpenACE linear track gain to OpenUtau's -24..+12 dB fader scale."""
    if volume <= 0:
        return -24.0
    return round(max(-24.0, min(12.0, 20.0 * math.log10(volume))), 3)


def _part_duration(project: Project, max_end_tick: int) -> int:
    """Return the minimum beat-aligned UVoicePart duration in OpenUtau's fixed 480 PPQ."""
    signature = project.time_signature
    ticks_per_beat = 480 * 4 / signature.denominator
    ticks_per_bar = ticks_per_beat * signature.numerator
    last_occupied_tick = max(0, max_end_tick - 1)
    bar = int(last_occupied_tick // ticks_per_bar)
    beat = int((last_occupied_tick % ticks_per_bar) // ticks_per_beat)
    return int(round((bar * ticks_per_bar) + ((beat + 1) * ticks_per_beat)))


def _pitch_data(note: Note) -> list[dict[str, float | str]]:
    """Convert cents to OpenUtau pitch units and always emit the required two points."""
    if note.pitch_curve:
        return [
            {"x": round(point.offset_ms, 3), "y": round(point.cents / 10.0, 4), "shape": "io"}
            for point in sorted(note.pitch_curve, key=lambda item: item.offset_ms)
        ]
    # OpenUtau's UNote.Validate indexes pitch.data[0]; an empty user pitch lane is
    # therefore not a valid portable note. These are OpenUtau's own standard defaults.
    return [
        {"x": -40, "y": 0, "shape": "io"},
        {"x": 40, "y": 0, "shape": "io"},
    ]


def _curve(points, mapper, tick_scale: float) -> dict[str, object]:
    ordered = sorted(points, key=lambda point: point.ticks)
    return {
        "abbr": None,
        "xs": [int(round(point.ticks * tick_scale)) for point in ordered],
        "ys": [int(round(mapper(point.value))) for point in ordered],
    }


def _part_curves(track, tick_scale: float) -> list[dict[str, object]]:
    curves: list[dict[str, object]] = []
    if track.automation.dynamic:
        # OpenACE: normalized 0..1, 0.5 neutral, ±6dB.
        # OpenUtau dyn: decibels * 10 (descriptor range -240..120).
        curve = _curve(track.automation.dynamic, lambda value: (max(0.0, min(1.0, value)) - 0.5) * 120.0, tick_scale)
        curve["abbr"] = "dyn"
        curves.append(curve)
    if track.automation.pitch_cents:
        # Both systems use cents for pitch deviation.
        curve = _curve(track.automation.pitch_cents, lambda value: max(-1200.0, min(1200.0, value)), tick_scale)
        curve["abbr"] = "pitd"
        curves.append(curve)
    return curves


def _wave_part(project: Project, clip, track_index: int, tick_scale: float, output_path: Path) -> dict[str, object]:
    """Map an OpenACE timeline clip to OpenUtau's source-relative UWavePart semantics."""
    try:
        import soundfile as sf  # type: ignore
    except ImportError as exc:
        raise RuntimeError("USTX wave-part export requires soundfile to measure audio clips") from exc
    source = Path(clip.path).expanduser()
    try:
        info = sf.info(str(source))
    except Exception as exc:
        raise RuntimeError(f"cannot measure USTX wave-part source {source}: {exc}") from exc
    file_seconds = info.frames / float(info.samplerate)
    file_start_ticks = clip.start_ticks - clip.offset_ticks
    file_start_seconds = project.ticks_to_seconds(file_start_ticks)
    file_end_ticks = project.seconds_to_ticks_float(file_start_seconds + file_seconds)
    full_source_ticks = int(round(file_end_ticks - file_start_ticks))
    duration_ticks = clip.duration_ticks if clip.duration_ticks is not None else max(1, full_source_ticks - clip.offset_ticks)
    position = int(round(clip.start_ticks * tick_scale))
    skip = int(round(clip.offset_ticks * tick_scale))
    duration = max(1, int(round(duration_ticks * tick_scale)))
    full_duration = max(1, int(round(full_source_ticks * tick_scale)))
    trim = max(0, full_duration - skip - duration)
    try:
        relative_path = os.path.relpath(source.resolve(), output_path.parent.resolve())
    except OSError:
        relative_path = str(source)
    return {
        "name": clip.label or source.name,
        "track_no": track_index,
        "position": position,
        "relative_path": relative_path,
        "file_duration_ms": round(file_seconds * 1000.0, 3),
        "skip": skip,
        "trim": trim,
        "fadein": int(round(clip.fade_in_ticks * tick_scale)),
        "fadeout": int(round(clip.fade_out_ticks * tick_scale)),
    }


def export_ustx(project: Project, output_path: Path) -> Path:
    """Export an OpenUtau 0.10 YAML project using source-derived USTX semantics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tracks = []
    voice_parts = []
    wave_parts = []
    tick_scale = 480.0 / project.ppq
    for index, track in enumerate(project.tracks):
        tracks.append(
            {
                "track_name": track.name,
                "track_color": _nearest_openutau_color(track.color),
                "singer": track.voice_id if track.type == TrackType.VOCAL else "",
                "phonemizer": "OpenUtau.Core.DefaultPhonemizer",
                "mute": track.mute,
                "solo": track.solo,
                "volume": _track_volume_db(track.volume),
                "pan": round(max(-100.0, min(100.0, track.pan * 100.0)), 3),
            }
        )
        for clip in track.clips:
            wave_parts.append(_wave_part(project, clip, index, tick_scale, output_path))
        if track.type != TrackType.VOCAL:
            continue
        notes = []
        for note in track.sorted_notes():
            if note.vibrato:
                phase_ratio = (note.vibrato.phase / (2.0 * math.pi)) % 1.0
                vibrato = {
                    "length": round(max(0.0, min(100.0, (1.0 - note.vibrato.start_ratio) * 100.0)), 3),
                    "period": round(max(5.0, min(500.0, 1000.0 / note.vibrato.frequency_hz)), 3),
                    "depth": round(max(5.0, min(200.0, note.vibrato.depth_cents)), 3),
                    "in": 10,
                    "out": 10,
                    "shift": round(phase_ratio * 100.0, 3),
                    "drift": 0,
                    "vol_link": 0,
                }
            else:
                vibrato = {"length": 0, "period": 175, "depth": 25, "in": 10, "out": 10, "shift": 0, "drift": 0, "vol_link": 0}
            item = {
                "position": int(round(note.start_ticks * tick_scale)),
                "duration": max(1, int(round(note.duration_ticks * tick_scale))),
                "tone": note.pitch,
                "lyric": note.lyric,
                "pitch": {"data": _pitch_data(note), "snap_first": True},
                "vibrato": vibrato,
                "tuning": 0,
                "phoneme_expressions": [],
                "phoneme_overrides": [
                    {"index": i, "phoneme": ph.symbol}
                    for i, ph in enumerate(note.phonemes)
                    if ph.symbol
                ],
            }
            notes.append(item)
        max_end = max((int(round(note.end_ticks * tick_scale)) for note in track.notes), default=480)
        voice_parts.append(
            {
                "name": track.name,
                "comment": f"OpenACE voice_id: {track.voice_id}",
                "track_no": index,
                "position": 0,
                "duration": _part_duration(project, max_end),
                "notes": notes,
                "curves": _part_curves(track, tick_scale),
                "masked_curves": [],
            }
        )
    data = {
        "name": project.title,
        "comment": "Exported by OpenACE",
        "output_dir": "Vocal",
        "cache_dir": "UCache",
        "ustx_version": "0.10",
        "expressions": {},
        "exp_selectors": ["dyn", "pitd", "clr", "eng", "vel", "vol", "atk", "dec", "gen", "bre"],
        "exp_primary": 0,
        "exp_secondary": 1,
        "key": 0,
        "time_signatures": [
            {
                "bar_position": 0,
                "beat_per_bar": project.time_signature.numerator,
                "beat_unit": project.time_signature.denominator,
            }
        ],
        "tempos": [
            {"position": int(round(point.ticks * tick_scale)), "bpm": point.bpm}
            for point in project.normalized_tempo_map()
        ],
        "tracks": tracks,
        "voice_parts": voice_parts,
        "wave_parts": wave_parts,
    }
    output_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return output_path
