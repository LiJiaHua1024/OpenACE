from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .models import Note, Project


@dataclass(frozen=True)
class BeatAnchor:
    note_id: str
    vowel_onset_ticks: int
    consonant_preonset_ms: float
    beat_phase_ms: float


def ticks_to_ms(ticks: float, bpm: float, ppq: int) -> float:
    return ticks / ppq * (60_000.0 / bpm)


def ms_to_ticks(ms: float, bpm: float, ppq: int) -> float:
    return ms * bpm / 60_000.0 * ppq


def beat_phase_ms(ticks: int, ppq: int, bpm: float) -> float:
    beat_ticks = ticks % ppq
    return ticks_to_ms(beat_ticks, bpm, ppq)


def validate_absolute_beat_anchor(notes: Iterable[Note], ppq: int, bpm: float, tolerance_ms: float = 1.0, project: Project | None = None) -> List[BeatAnchor]:
    """Validate that vowel onset stays on the symbolic note onset.

    Consonants may precede the onset by 40-90ms, but they must never move the vowel or
    accumulate duration drift. The note position itself is the absolute musical anchor.
    """
    anchors: List[BeatAnchor] = []
    for note in sorted(notes, key=lambda n: n.start_ticks):
        vowels = [p for p in note.phonemes if p.is_vowel]
        if vowels:
            first_vowel = min(vowels, key=lambda p: p.start_ms)
            if abs(first_vowel.start_ms) > tolerance_ms:
                raise ValueError(
                    f"note {note.id} vowel onset is {first_vowel.start_ms:.2f}ms, not beat-anchored"
                )
            consonants = [p for p in note.phonemes if not p.is_vowel and p.start_ms < 0]
            if consonants:
                preonset = abs(min(p.start_ms for p in consonants))
                if not 35.0 <= preonset <= 95.0:
                    raise ValueError(
                        f"note {note.id} consonant preonset {preonset:.1f}ms outside safe 40-90ms zone"
                    )
            else:
                preonset = 0.0
        else:
            preonset = 0.0
        anchors.append(
            BeatAnchor(
                note_id=note.id,
                vowel_onset_ticks=note.start_ticks,
                consonant_preonset_ms=preonset,
                beat_phase_ms=beat_phase_ms(note.start_ticks, ppq, project.bpm_at(note.start_ticks) if project is not None else bpm),
            )
        )
    return anchors



def stepped_tempo_events(project: Project, resolution_ticks: int = 120) -> list[tuple[int, float]]:
    """Approximate step/linear tempo automation as ordered stepped tempo events.

    MIDI and several host project formats encode tempo as discrete events rather than
    continuous ramp curves. This helper preserves the exact endpoints and densifies only
    linear segments; it must not be treated as lossless roundtrip metadata.
    """
    points = project.normalized_tempo_map()
    events: dict[int, float] = {0: float(points[0].bpm)}
    for previous, point in zip(points, points[1:]):
        if point.curve == "linear" and point.ticks > previous.ticks:
            step = max(1, min(int(resolution_ticks), point.ticks - previous.ticks))
            positions = list(range(previous.ticks + step, point.ticks, step)) + [point.ticks]
            for position in positions:
                ratio = (position - previous.ticks) / (point.ticks - previous.ticks)
                events[int(position)] = float(previous.bpm + (point.bpm - previous.bpm) * ratio)
        else:
            events[int(point.ticks)] = float(point.bpm)
    return sorted(events.items())

def quantize_ticks(ticks: float, ppq: int, division: int = 4) -> int:
    step = ppq // division
    return int(round(ticks / step) * step)


def project_duration_seconds(project: Project) -> float:
    return project.ticks_to_seconds(project.duration_ticks())
