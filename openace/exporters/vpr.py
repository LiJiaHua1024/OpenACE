from __future__ import annotations

import json
import zipfile
from pathlib import Path

from openace.core.models import Project, TrackType
from openace.core.timing import stepped_tempo_events

TICKS_PER_QUARTER_VPR = 480


def _vpr_ticks(project: Project, ticks: int) -> int:
    return int(round(ticks * TICKS_PER_QUARTER_VPR / project.ppq))


def export_vpr(project: Project, output_path: Path) -> Path:
    """Export a VOCALOID5/6-compatible VPR zip with Project/sequence.json."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    voices = []
    tracks = []
    for index, track in enumerate(project.tracks):
        if track.type != TrackType.VOCAL:
            continue
        voice_id = f"openace_voice_{index}"
        voices.append({"vVoiceId": voice_id, "name": track.voice_id, "parameter": {"breathiness": 0, "brightness": 0, "clearness": 0, "genderFactor": 0, "opening": 0}})
        notes = []
        controllers = []
        for note in track.sorted_notes():
            notes.append(
                {
                    "posTick": _vpr_ticks(project, note.start_ticks),
                    "durTick": _vpr_ticks(project, note.duration_ticks),
                    "noteNum": note.pitch,
                    "lyric": note.lyric,
                    "phoneme": " ".join(p.symbol for p in note.phonemes),
                    "velocity": note.velocity,
                    "protected": False,
                }
            )
        tracks.append(
            {
                "name": track.name,
                "type": "vocal",
                "vVoiceId": voice_id,
                "parts": [
                    {
                        "name": track.name,
                        "posTick": 0,
                        "durTick": _vpr_ticks(project, project.duration_ticks()),
                        "notes": notes,
                        "controllers": controllers,
                        "stylePlugin": {},
                    }
                ],
                "volume": round(track.volume * 127),
                "panpot": round((track.pan + 1) * 64),
                "mute": track.mute,
                "solo": track.solo,
            }
        )
    sequence = {
        "version": {"major": 5, "minor": 0, "revision": 0},
        "vender": "Yamaha Corporation",
        "title": project.title,
        "masterTrack": {
            "samplingRate": 48000,
            "loop": {"isEnabled": False, "startTick": 0, "endTick": 0},
            "tempo": {"events": [
                {"posTick": _vpr_ticks(project, ticks), "bpm": int(round(bpm * 100))}
                for ticks, bpm in stepped_tempo_events(project)
            ]},
            "timeSig": {"events": [{"posTick": 0, "numerator": project.time_signature.numerator, "denominator": project.time_signature.denominator}]},
            "volume": {"events": [{"posTick": 0, "value": 100}]},
        },
        "voices": voices,
        "tracks": tracks,
    }
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Project/sequence.json", json.dumps(sequence, ensure_ascii=False, indent=2))
    return output_path
