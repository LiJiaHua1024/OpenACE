from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

import numpy as np

from .models import Note, Project


def midi_to_hz(pitch: float) -> float:
    return 440.0 * (2.0 ** ((pitch - 69.0) / 12.0))


def hz_to_midi(hz: float) -> float:
    if hz <= 0:
        raise ValueError("0Hz/unvoiced frames have no MIDI pitch")
    return 69.0 + 12.0 * math.log2(hz / 440.0)


def transpose_notes_preserve_intervals(notes: Sequence[Note], semitones: int) -> List[Tuple[int, int]]:
    """Return (note id, new pitch) while requiring exact interval conservation.

    This deliberately never folds, clamps, or octave-corrects an individual note. If any
    resulting pitch would leave the MIDI representable range, the entire transposition is
    rejected instead of corrupting the melody.
    """
    if not notes:
        return []
    original = [note.pitch for note in notes]
    shifted = [pitch + semitones for pitch in original]
    if min(shifted) < 0 or max(shifted) > 127:
        raise ValueError("transposition rejected: would require clamping or octave folding")
    before = [b - a for a, b in zip(original, original[1:])]
    after = [b - a for a, b in zip(shifted, shifted[1:])]
    if before != after:
        raise AssertionError("internal error: semitone interval conservation violated")
    return [(note.id, pitch) for note, pitch in zip(notes, shifted)]


def validate_no_octave_folding(original: Sequence[int], rendered: Sequence[float], tolerance_cents: float = 60.0) -> None:
    """Validate rendered F0 follows target pitch without isolated octave substitutions.

    `rendered` is a per-note median MIDI pitch. Unvoiced/0Hz frames must have been removed
    before calling this function.
    """
    if len(original) != len(rendered):
        raise ValueError("target/rendered pitch lengths differ")
    for index, (target, actual) in enumerate(zip(original, rendered)):
        cents = abs((actual - target) * 100.0)
        octave_distance = abs(cents - 1200.0)
        if octave_distance < tolerance_cents:
            raise ValueError(f"note {index} appears octave-folded ({cents:.1f} cents off)")


def sanitize_f0(f0_hz: Iterable[float], max_gap_frames: int = 8) -> np.ndarray:
    """Remove 0Hz/unvoiced pollution and interpolate only short internal gaps.

    Long leading/trailing/unvoiced regions remain NaN so downstream diagnostics and SVS
    conditioning never interpret silence as a low pitch.
    """
    arr = np.asarray(list(f0_hz), dtype=np.float64).copy()
    arr[~np.isfinite(arr)] = np.nan
    arr[arr <= 0.0] = np.nan
    valid = np.flatnonzero(np.isfinite(arr))
    if len(valid) == 0:
        return arr
    first, last = int(valid[0]), int(valid[-1])
    x = np.arange(first, last + 1)
    xp = valid[(valid >= first) & (valid <= last)]
    fp = arr[xp]
    interp = np.interp(x, xp, fp)
    # Re-open gaps longer than the permitted short dropout.
    isnan = ~np.isfinite(arr[first:last + 1])
    if np.any(isnan):
        groups: List[Tuple[int, int]] = []
        start = None
        for i, missing in enumerate(isnan):
            if missing and start is None:
                start = i
            if start is not None and (not missing or i == len(isnan) - 1):
                end = i if not missing else i + 1
                groups.append((start, end))
                start = None
        for a, b in groups:
            if b - a > max_gap_frames:
                interp[a:b] = np.nan
    arr[first:last + 1] = interp
    return arr


def correct_octave_errors(f0_hz: Iterable[float], median_window: int = 7, threshold_ratio: float = 1.7) -> np.ndarray:
    """Correct isolated octave jumps while preserving melodic leaps.

    A frame is treated as an octave error only if it is close to half/double the local
    median and neighboring frames do not support a genuine leap.
    """
    arr = sanitize_f0(f0_hz)
    valid = np.isfinite(arr)
    if valid.sum() < 3:
        return arr
    out = arr.copy()
    indices = np.flatnonzero(valid)
    for idx in indices:
        lo = max(0, idx - median_window // 2)
        hi = min(len(arr), idx + median_window // 2 + 1)
        neighborhood = arr[lo:hi]
        neighborhood = neighborhood[np.isfinite(neighborhood)]
        neighborhood = neighborhood[neighborhood != arr[idx]]
        if len(neighborhood) < 2:
            continue
        med = float(np.median(neighborhood))
        ratio = arr[idx] / med
        if ratio >= threshold_ratio and abs(arr[idx] / 2.0 - med) / med < 0.12:
            out[idx] = arr[idx] / 2.0
        elif ratio <= 1.0 / threshold_ratio and abs(arr[idx] * 2.0 - med) / med < 0.12:
            out[idx] = arr[idx] * 2.0
    return out



def interpolated_pitch_cents(points: Sequence, offset_ms: float) -> float:
    """Linearly interpolate a per-note pitch-handle curve in cents."""
    if not points:
        return 0.0
    ordered = sorted(points, key=lambda point: point.offset_ms)
    if offset_ms <= ordered[0].offset_ms:
        return float(ordered[0].cents)
    if offset_ms >= ordered[-1].offset_ms:
        return float(ordered[-1].cents)
    for left, right in zip(ordered, ordered[1:]):
        if left.offset_ms <= offset_ms <= right.offset_ms:
            span = max(1e-9, right.offset_ms - left.offset_ms)
            ratio = (offset_ms - left.offset_ms) / span
            return float(left.cents + (right.cents - left.cents) * ratio)
    return 0.0


def vibrato_envelope(note: Note, offset_ms: float, duration_ms: float) -> float:
    """Return the deterministic vibrato amplitude envelope for a note-local offset."""
    vibrato = note.vibrato
    if not vibrato or duration_ms <= 0:
        return 0.0
    start_ms = vibrato.start_ratio * duration_ms
    if offset_ms < start_ms or offset_ms > duration_ms:
        return 0.0
    span_ms = max(1e-9, duration_ms - start_ms)
    attack_ms = max(0.0, min(1.0, vibrato.attack_ratio)) * span_ms
    release_ms = max(0.0, min(1.0, vibrato.release_ratio)) * span_ms
    attack = 1.0 if attack_ms <= 0 else max(0.0, min(1.0, (offset_ms - start_ms) / attack_ms))
    release = 1.0 if release_ms <= 0 else max(0.0, min(1.0, (duration_ms - offset_ms) / release_ms))
    return float(min(attack, release))


def note_expression_cents(note: Note, offset_ms: float, duration_ms: float) -> float:
    """Return deterministic per-note vibrato plus interpolated pitch-handle cents."""
    cents = interpolated_pitch_cents(note.pitch_curve, offset_ms)
    if note.vibrato and duration_ms > 0:
        envelope = vibrato_envelope(note, offset_ms, duration_ms)
        if envelope:
            cents += max(0.0, min(2.0, note.pitch_modulation)) * envelope * note.vibrato.depth_cents * np.sin(
                2.0 * np.pi * note.vibrato.frequency_hz * offset_ms / 1000.0 + note.vibrato.phase
            )
    return float(cents)


def pitch_envelope_state(points: Sequence, tick: float) -> Tuple[float, bool]:
    """Return interpolated pitch cents plus the forward-held user voicing state.

    Missing `voiced` metadata means default voiced behavior; a later legacy/unknown
    point therefore resets an earlier explicit voiceless segment instead of leaking it.
    """
    if not points:
        return 0.0, True
    ordered = sorted(points, key=lambda point: point.ticks)
    if tick <= ordered[0].ticks:
        cents = float(ordered[0].value)
    elif tick >= ordered[-1].ticks:
        cents = float(ordered[-1].value)
    else:
        cents = 0.0
        for left, right in zip(ordered, ordered[1:]):
            if left.ticks <= tick <= right.ticks:
                span = max(1e-9, right.ticks - left.ticks)
                ratio = (tick - left.ticks) / span
                cents = float(left.value + (right.value - left.value) * ratio)
                break
    voiced = True
    for point in ordered:
        if point.ticks > tick:
            break
        voiced = True if point.voiced is None else bool(point.voiced)
    return cents, voiced

def pitch_curve_for_notes(project: Project, notes: Sequence[Note], frame_ms: float = 10.0, pitch_automation: Sequence | None = None) -> Tuple[np.ndarray, np.ndarray]:
    """Build target time/F0 curve in seconds/Hz through the piecewise tempo map."""
    if not notes:
        return np.zeros(0), np.zeros(0)
    end_s = max(project.ticks_to_seconds(note.end_ticks) for note in notes)
    frames = max(1, int(np.ceil(end_s * 1000.0 / frame_ms)) + 1)
    times = np.arange(frames) * frame_ms / 1000.0
    f0 = np.full(frames, np.nan)
    for note in notes:
        note_start_ms = project.ticks_to_seconds(note.start_ticks) * 1000.0
        note_end_ms = project.ticks_to_seconds(note.end_ticks) * 1000.0
        duration_ms = max(1e-9, note_end_ms - note_start_ms)
        start = int(np.floor(note_start_ms / frame_ms))
        end = int(np.ceil(note_end_ms / frame_ms))
        base = midi_to_hz(note.pitch)
        for frame in range(start, min(end, frames)):
            absolute_ms = frame * frame_ms
            offset_ms = absolute_ms - note_start_ms
            cents = note_expression_cents(note, offset_ms, duration_ms)
            voiced = True
            if pitch_automation is not None:
                absolute_ticks = project.seconds_to_ticks_float(absolute_ms / 1000.0)
                automation_cents, voiced = pitch_envelope_state(pitch_automation, absolute_ticks)
                cents += automation_cents
            if voiced:
                f0[frame] = base * (2.0 ** (cents / 1200.0))
    return times, f0
