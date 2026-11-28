from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import mido
from mido.midifiles.meta import meta_charset

from openace.core.expression import envelope_value
from openace.core.models import Project, Track, TrackType
from openace.core.pitch import note_expression_cents
from openace.core.timing import stepped_tempo_events


def _bend_value(cents: float, range_cents: float = 600.0) -> int:
    clamped = max(-range_cents, min(range_cents, cents))
    return int(round(clamped / range_cents * 8191.0))


def _note_pitchbend_events(project: Project, track: Track, channel: int) -> list[tuple[int, int]]:
    """Return (tick, signed pitch-wheel value) events for continuous pitch expression.

    Events are sampled on the continuous-time expression curve and mapped back through the
    piecewise tempo map, avoiding the linear-tempo inversion errors that made older MIDI
    exports lose expression timing.
    """
    events: list[tuple[int, int]] = []
    last_value: int | None = None
    for note in track.sorted_notes():
        start_s = project.ticks_to_seconds(note.start_ticks)
        end_s = project.ticks_to_seconds(note.end_ticks)
        duration_ms = max(1e-9, (end_s - start_s) * 1000.0)
        frames = max(1, int((end_s - start_s) / 0.02))
        positions = [start_s + min(end_s - start_s, index * 0.02) for index in range(frames + 1)]
        if positions[-1] < end_s - 1e-9:
            positions.append(end_s)
        emitted_for_note = False
        for position_s in positions:
            absolute_ticks = project.seconds_to_ticks_float(position_s)
            offset_ms = (position_s - start_s) * 1000.0
            cents = note_expression_cents(note, offset_ms, duration_ms)
            cents += envelope_value(track.automation.pitch_cents, absolute_ticks, default=0.0)
            value = _bend_value(cents)
            if value != last_value:
                events.append((int(round(absolute_ticks)), value))
                last_value = value
                emitted_for_note = True
        if emitted_for_note and last_value != 0:
            events.append((note.end_ticks, 0))
            last_value = 0
    if not any(value != 0 for _, value in events):
        return []
    return events


def export_midi(project: Project, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mid = mido.MidiFile(type=1, ticks_per_beat=project.ppq, charset="utf-8")
    tempo_track = mido.MidiTrack()
    tempo_track.append(
        mido.MetaMessage(
            "time_signature",
            numerator=project.time_signature.numerator,
            denominator=project.time_signature.denominator,
            time=0,
        )
    )
    tempo_points = stepped_tempo_events(project)
    last_tempo_tick = 0
    for tick, bpm in tempo_points:
        tick = max(0, int(round(tick)))
        tempo_track.append(
            mido.MetaMessage(
                "set_tempo",
                tempo=mido.bpm2tempo(bpm),
                time=max(0, tick - last_tempo_tick),
            )
        )
        last_tempo_tick = tick
    tempo_track.append(mido.MetaMessage("end_of_track", time=0))
    mid.tracks.append(tempo_track)
    melodic_track_index = 0
    for track in project.tracks:
        if track.type != TrackType.VOCAL:
            continue
        if track.midi_channel is not None:
            channel = track.midi_channel
        else:
            channel = melodic_track_index % 15
            if channel >= 9:
                channel += 1
        mt = mido.MidiTrack()
        mt.append(mido.MetaMessage("track_name", name=track.name, time=0))
        if track.midi_program is not None:
            mt.append(mido.Message("program_change", channel=channel, program=track.midi_program, time=0))
        events = []
        # Select RPN 0/0 and set pitch-bend sensitivity to ±6 semitones, matching
        # OpenACE's validated ±600-cent pitch automation lane. Importers without RPN
        # support still receive standard 14-bit pitchwheel curves.
        for controller, value in ((101, 0), (100, 0), (6, 6), (38, 0)):
            events.append((0, 0, mido.Message("control_change", channel=channel, control=controller, value=value, time=0)))
        for note in track.sorted_notes():
            if note.lyric:
                events.append((note.start_ticks, 1, mido.MetaMessage("lyrics", text=note.lyric, time=0)))
            events.append((note.start_ticks, 3, mido.Message("note_on", channel=channel, note=note.pitch, velocity=note.velocity, time=0)))
            events.append((note.end_ticks, 0, mido.Message("note_off", channel=channel, note=note.pitch, velocity=0, time=0)))
        for tick, value in _note_pitchbend_events(project, track, channel):
            events.append((tick, 2, mido.Message("pitchwheel", channel=channel, pitch=value, time=0)))
        events.sort(key=lambda item: (item[0], item[1]))
        last = 0
        for absolute, _order, message in events:
            message.time = max(0, absolute - last)
            mt.append(message)
            last = absolute
        mt.append(mido.MetaMessage("end_of_track", time=0))
        mid.tracks.append(mt)
        melodic_track_index += 1
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
