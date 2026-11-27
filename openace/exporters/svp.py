from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

from openace.core.models import Project, TrackType


def _svp_curve(project: Project, points, mapper) -> dict:
    """Serialize normalized automation as Synthesizer V flattened blick/value pairs."""
    flattened = []
    for point in sorted(points, key=lambda item: item.ticks):
        flattened.extend([_units(project, point.ticks), round(float(mapper(point.value)), 6)])
    return {"mode": "linear", "points": flattened}


def _centered_unit(value: float) -> float:
    """Map OpenACE normalized 0..1 automation (0.5 neutral) to SVP -1..1."""
    return max(-1.0, min(1.0, (max(0.0, min(1.0, value)) - 0.5) * 2.0))

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
        seconds_per_tick = 60.0 / project.bpm / project.ppq
        for note in track.sorted_notes():
            phonemes = " ".join(p.symbol for p in note.phonemes)
            note_seconds = note.duration_ticks * seconds_per_tick
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
                        "tF0VbrStart": (note.vibrato.start_ratio * note_seconds) if note.vibrato else 0.25,
                    },
                    "systemAttributes": {},
                    "pitchTakes": {"activeTakeId": 0, "takes": []},
                    "timbreTakes": {"activeTakeId": 0, "takes": []},
                    "expressionTakes": {"activeTakeId": 0, "takes": []},
                }
            )
        group_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"openace-svp-group/{project.id}/{track.id}"))
        group = {
            "uuid": group_uuid,
            "name": track.name,
            "notes": notes,
            "parameters": {
                # pitchDelta is semitones; loudness is dB; tension/breathiness are -1..1.
                "pitchDelta": _svp_curve(project, track.automation.pitch_cents, lambda value: value / 100.0),
                "loudness": _svp_curve(project, track.automation.dynamic, lambda value: (max(0.0, min(1.0, value)) - 0.5) * 12.0),
                "tension": _svp_curve(project, track.automation.tension, _centered_unit),
                "breathiness": _svp_curve(project, track.automation.air, _centered_unit),
                "voicing": {"mode": "linear", "points": []},
                "gender": {"mode": "linear", "points": []},
                "toneShift": {"mode": "linear", "points": []},
            },
        }
        main_ref = {
            "groupID": group_uuid,
            "blickOffset": 0,
            "blickAbsoluteBegin": 0,
            "pitchOffset": 0,
            "database": {"name": track.voice_id},
            "voice": {
                "vocalModeParams": {},
                "tension": 0.0,
                "breathiness": 0.0,
                "gender": 0.0,
                "voicing": 1.0,
                "toneShift": 0.0,
            },
            "isInstrumental": not is_vocal,
        }
        tracks.append(
            {
                "name": track.name,
                "dispColor": track.color.lstrip("#"),
                "dispOrder": index,
                "renderEnabled": True,
                "mixer": {
                    "gainDecibel": 20 * math.log10(max(track.volume, 0.001)),
                    "pan": track.pan,
                    "mute": track.mute,
                    "solo": track.solo,
                    "display": True,
                },
                "mainGroup": group if is_vocal else {"uuid": group_uuid, "name": track.name, "notes": [], "parameters": {}},
                "mainRef": main_ref,
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
