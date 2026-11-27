from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import mido
from mido.midifiles.meta import meta_charset

from openace.core.models import Note, Project, TempoPoint, Track


def import_midi(path: Path, title: str | None = None) -> Project:
    with meta_charset("utf-8"):
        mid = mido.MidiFile(str(path), charset="utf-8")
    project = Project(title=title or path.stem, ppq=mid.ticks_per_beat or 480)
    tempo_events: dict[int, float] = {}
    for midi_track in mid.tracks:
        abs_ticks = 0
        for msg in midi_track:
            abs_ticks += msg.time
            if msg.type == "set_tempo":
                tempo_events[abs_ticks] = round(mido.tempo2bpm(msg.tempo), 6)
    if tempo_events:
        ordered = sorted(tempo_events.items())
        if ordered[0][0] != 0:
            ordered.insert(0, (0, 120.0))
        project.tempo_map = [TempoPoint(ticks=ticks, bpm=bpm) for ticks, bpm in ordered]
        project.bpm = project.tempo_map[0].bpm
    else:
        project.tempo_map = [TempoPoint(ticks=0, bpm=120.0)]
        project.bpm = 120.0
    for track_index, midi_track in enumerate(mid.tracks):
        active: Dict[int, Tuple[int, int, str]] = {}
        pending_lyric = ""
        abs_ticks = 0
        notes: List[Note] = []
        for msg in midi_track:
            abs_ticks += msg.time
            if msg.type == "lyrics":
                pending_lyric += msg.text
            elif msg.type == "note_on" and msg.velocity > 0:
                active[msg.note] = (abs_ticks, msg.velocity, pending_lyric)
                pending_lyric = ""
            elif msg.type in {"note_off", "note_on"} and (msg.type == "note_off" or msg.velocity == 0):
                if msg.note in active:
                    start, velocity, lyric = active.pop(msg.note)
                    duration = max(1, abs_ticks - start)
                    notes.append(Note(start_ticks=start, duration_ticks=duration, pitch=msg.note, velocity=velocity, lyric=lyric))
        if notes:
            name = next((m.name for m in midi_track if m.type == "track_name"), f"Track {track_index + 1}")
            project.add_track(Track(name=name, notes=sorted(notes, key=lambda n: n.start_ticks)))
    if not project.tracks:
        project.add_track(Track(name="Vocal 1"))
    return project
