from __future__ import annotations

from pathlib import Path

import yaml

from openace.core.models import Project, TrackType


def export_ustx(project: Project, output_path: Path) -> Path:
    """Export an OpenUtau-native YAML project using the public USTX structure."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tracks = []
    voice_parts = []
    for index, track in enumerate(project.tracks):
        tracks.append(
            {
                "track_name": track.name,
                "track_color": track.color.lstrip("#"),
                "singer": track.voice_id if track.type == TrackType.VOCAL else "",
                "phonemizer": "Default",
                "mute": track.mute,
                "solo": track.solo,
                "volume": track.volume,
                "pan": track.pan,
            }
        )
        if track.type != TrackType.VOCAL:
            continue
        notes = []
        for note in track.sorted_notes():
            item = {
                "position": note.start_ticks,
                "duration": note.duration_ticks,
                "tone": note.pitch,
                "lyric": note.lyric,
                "pitch": {
                    "data": [
                        {"x": p.offset_ms, "y": p.cents, "shape": "io"}
                        for p in note.pitch_curve
                    ],
                    "snap_first": True,
                },
                "vibrato": {
                    "length": (note.vibrato.start_ratio * 100) if note.vibrato else 0,
                    "period": round(1000 / note.vibrato.frequency_hz) if note.vibrato else 175,
                    "depth": note.vibrato.depth_cents if note.vibrato else 0,
                    "in": 10,
                    "out": 10,
                    "shift": 0,
                    "drift": 0,
                    "vol_link": 0,
                },
                "phoneme_overrides": [
                    {"index": i, "phoneme": ph.symbol, "offset": round(ph.start_ms, 2)}
                    for i, ph in enumerate(note.phonemes)
                ],
            }
            notes.append(item)
        voice_parts.append(
            {
                "name": track.name,
                "track_no": index,
                "position": 0,
                "notes": notes,
                "curves": [
                    {"abbr": "dyn", "x": [], "y": []},
                    {"abbr": "pitd", "x": [], "y": []},
                ],
            }
        )
    data = {
        "name": project.title,
        "ustx_version": "0.9",
        "resolution": project.ppq,
        "key": 0,
        "time_signatures": [
            {
                "bar_position": 0,
                "beat_per_bar": project.time_signature.numerator,
                "beat_unit": project.time_signature.denominator,
            }
        ],
        "tempos": [{"position": 0, "bpm": project.bpm}],
        "expressions": {},
        "tracks": tracks,
        "voice_parts": voice_parts,
        "wave_parts": [],
    }
    output_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return output_path
