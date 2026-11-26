from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import mido
from mido.midifiles.meta import meta_charset

from openace.core.models import Project, Track, TrackType


def export_midi(project: Project, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mid = mido.MidiFile(type=1, ticks_per_beat=project.ppq, charset="utf-8")
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(project.bpm), time=0))
    tempo_track.append(
        mido.MetaMessage(
            "time_signature",
            numerator=project.time_signature.numerator,
            denominator=project.time_signature.denominator,
            time=0,
        )
    )
    mid.tracks.append(tempo_track)
    for track in project.tracks:
        if track.type != TrackType.VOCAL:
            continue
        mt = mido.MidiTrack()
        mt.append(mido.MetaMessage("track_name", name=track.name, time=0))
        events = []
        for note in track.sorted_notes():
            if note.lyric:
                events.append((note.start_ticks, mido.MetaMessage("lyrics", text=note.lyric, time=0)))
            events.append((note.start_ticks, mido.Message("note_on", note=note.pitch, velocity=note.velocity, time=0)))
            events.append((note.end_ticks, mido.Message("note_off", note=note.pitch, velocity=0, time=0)))
        events.sort(key=lambda item: (item[0], 0 if isinstance(item[1], mido.MetaMessage) else 1))
        last = 0
        for absolute, message in events:
            message.time = max(0, absolute - last)
            mt.append(message)
            last = absolute
        mt.append(mido.MetaMessage("end_of_track", time=0))
        mid.tracks.append(mt)
    # Modern DAWs commonly use UTF-8 lyric events for CJK projects. Mido defaults to
    # latin-1, so scope the charset override to encoding this file.
    with meta_charset("utf-8"):
        mid.save(str(output_path))
    return output_path


def _lrc_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    sec = seconds - minutes * 60
    return f"[{minutes:02d}:{sec:05.2f}]"


def export_lrc(project: Project, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[ti:" + project.title + "]",
        "[ar:OpenACE]",
        "[al:OpenACE Project]",
        "[by:OpenACE]",
    ]
    for track in project.vocal_tracks():
        for note in track.sorted_notes():
            if not note.lyric:
                continue
            lines.append(_lrc_time(project.ticks_to_seconds(note.start_ticks)) + note.lyric)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
