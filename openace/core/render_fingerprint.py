"""Deterministic vocal render input fingerprints shared with the browser."""
from __future__ import annotations

import json
from typing import Any

from openace.core.models import Project, Track

FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3


def _number(value: float) -> str:
    if value == 0:
        return "0"
    text = f"{value:.9f}".rstrip("0").rstrip(".")
    return text if text not in {"", "-0"} else "0"


def canonical_json(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _number(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            json.dumps(str(key), ensure_ascii=False) + ":" + canonical_json(value[key])
            for key in sorted(value, key=str)
        ) + "}"
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def fnv1a64(text: str) -> str:
    value = FNV_OFFSET
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def vocal_render_input_hash(project: Project, track: Track) -> str:
    notes = []
    for note in track.sorted_notes():
        payload = note.model_dump(mode="json")
        payload.pop("id", None)
        notes.append(payload)
    breaths = []
    for breath in sorted(track.breaths, key=lambda item: (item.start_ticks, item.duration_ticks, item.id)):
        payload = breath.model_dump(mode="json")
        payload.pop("id", None)
        breaths.append(payload)
    automation = track.automation.model_dump(mode="json")
    automation.pop("volume", None)
    automation.pop("pan", None)
    # Missing and explicit null voicing both mean default voiced behavior. Omit the
    # key so legacy projects keep stable fingerprints and browser/server hashes agree.
    for lane_points in automation.values():
        if isinstance(lane_points, list):
            for point in lane_points:
                if isinstance(point, dict) and point.get("voiced") is None:
                    point.pop("voiced", None)
    payload = {
        "automation": automation,
        "breaths": breaths,
        "language": track.language,
        "notes": notes,
        "ppq": project.ppq,
        "reference_voice_path": track.reference_voice_path,
        "tempo_map": [point.model_dump(mode="json") for point in project.normalized_tempo_map()],
        "voice_id": track.voice_id,
    }
    return fnv1a64(canonical_json(payload))
