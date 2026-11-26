from __future__ import annotations

import json
from pathlib import Path

from openace.core.models import Project, TrackType

UNITS_PER_TICK_AT_PPQ480 = 1_470_000


def _units(project: Project, ticks: int) -> int:
    return int(round(ticks * UNITS_PER_TICK_AT_PPQ480 * 480 / project.ppq))


def export_svp(project: Project, output_path: Path) -> Path:
    """Export a Synthesizer V Studio JSON project (.svp)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tracks = []
    for index, track in enumerate(project.tracks):
        is_vocal = track.type == TrackType.VOCAL
        notes = []
        for note in track.sorted_notes():
            phonemes = " ".join(p.symbol for p in note.phonemes)
            notes.append(
                {
                    "musicalType": "singing",
                    "onset": _units(project, note.start_ticks),
                    "duration": _units(project, note.duration_ticks),
                    "lyrics": note.lyric,
                    "phonemes": phonemes,
                    "accent": "",
                    "pitch": note.pitch,
                    "detune": 0,
                    "instantMode": True,
                    "attributes": {
                        "evenSyllableDuration": False,
                        "tF0Left": 0.04,
                        "tF0Right": 0.04,
                        "dF0Left": 0.0,
                        "dF0Right": 0.0,
                        "dF0Vbr": (note.vibrato.depth_cents / 100.0) if note.vibrato else 0.0,
                        "fF0Vbr": note.vibrato.frequency_hz if note.vibrato else 5.5,
                        "tF0VbrStart": note.vibrato.start_ratio if note.vibrato else 0.55,
                    },
                    "systemAttributes": {},
                    "pitchTakes": {"activeTakeId": 0, "takes": []},
                    "timbreTakes": {"activeTakeId": 0, "takes": []},
                    "expressionTakes": {"activeTakeId": 0, "takes": []},
                }
            )
        group = {
            "name": track.name,
            "notes": notes,
            "parameters": {
                "pitchDelta": {"mode": "linear", "points": []},
                "vibratoEnv": {"mode": "linear", "points": []},
                "loudness": {"mode": "linear", "points": []},
                "tension": {"mode": "linear", "points": []},
                "breathiness": {"mode": "linear", "points": []},
                "voicing": {"mode": "linear", "points": []},
                "gender": {"mode": "linear", "points": []},
            },
            "voice": {
                "version": "1",
                "language": track.language,
                "phoneset": "xsampa",
                "name": track.voice_id,
            },
        }
        tracks.append(
            {
                "name": track.name,
                "dispColor": track.color.lstrip("#"),
                "dispOrder": index,
                "renderEnabled": True,
                "mixer": {
                    "gainDecibel": 20 * __import__("math").log10(max(track.volume, 0.001)),
                    "pan": track.pan,
                    "mute": track.mute,
                    "solo": track.solo,
                    "display": True,
                },
                "mainGroup": group if is_vocal else {"name": track.name, "notes": [], "parameters": {}},
                "mainRef": {"isInstrumental": not is_vocal},
                "groups": [],
            }
        )
    data = {
        "version": 153,
        "time": {
            "meter": [
                {
                    "index": 0,
                    "numerator": project.time_signature.numerator,
                    "denominator": project.time_signature.denominator,
                }
            ],
            "tempo": [{"position": 0, "bpm": project.bpm}],
        },
        "library": [],
        "tracks": tracks,
        "renderConfig": {
            "sampleRate": 48000,
            "bitDepth": 24,
            "numChannels": 2,
            "aspirationFormat": "wav",
            "exportMixDown": True,
        },
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
