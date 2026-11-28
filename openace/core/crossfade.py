"""Automatic equal-power crossfades for overlapping arrangement clips."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Literal

import numpy as np

from openace.core.models import AudioClip, Project, Track


@dataclass(frozen=True)
class CrossfadeInterval:
    start_ticks: int
    end_ticks: int
    role: Literal["outgoing", "incoming"]
    other_clip_id: str


def _ordered_clips(track: Track) -> list[AudioClip]:
    return sorted(track.clips, key=lambda clip: (clip.start_ticks, clip.id))


def crossfade_intervals(track: Track, clip: AudioClip) -> List[CrossfadeInterval]:
    """Return automatic overlap intervals for a clip on its arrangement track."""
    if clip.duration_ticks is None or clip.duration_ticks <= 0:
        return []
    ordered = _ordered_clips(track)
    positions = {item.id: index for index, item in enumerate(ordered)}
    clip_start = clip.start_ticks
    clip_end = clip.start_ticks + clip.duration_ticks
    intervals: List[CrossfadeInterval] = []
    for other in ordered:
        if other.id == clip.id or other.duration_ticks is None or other.duration_ticks <= 0:
            continue
        other_start = other.start_ticks
        other_end = other.start_ticks + other.duration_ticks
        start = max(clip_start, other_start)
        end = min(clip_end, other_end)
        if end <= start:
            continue
        role: Literal["outgoing", "incoming"] = "outgoing" if positions[clip.id] < positions[other.id] else "incoming"
        intervals.append(CrossfadeInterval(start, end, role, other.id))
    return intervals


def crossfade_gain_at(track: Track, clip: AudioClip, position_ticks: float) -> float:
    """Evaluate the automatic equal-power crossfade gain at a timeline position."""
    gain = 1.0
    for interval in crossfade_intervals(track, clip):
        if position_ticks < interval.start_ticks or position_ticks > interval.end_ticks:
            continue
        span = max(1e-9, interval.end_ticks - interval.start_ticks)
        progress = max(0.0, min(1.0, (position_ticks - interval.start_ticks) / span))
        shape = math.cos(progress * math.pi / 2.0) if interval.role == "outgoing" else math.sin(progress * math.pi / 2.0)
        gain *= shape
    return gain


def apply_automatic_crossfades(data: np.ndarray, project: Project, track: Track, clip: AudioClip, sample_rate: int) -> np.ndarray:
    """Apply equal-power overlap envelopes to an exported clip slice."""
    if not len(data) or clip.duration_ticks is None or clip.duration_ticks <= 0:
        return data
    intervals = crossfade_intervals(track, clip)
    if not intervals:
        return data
    processed = np.array(data, dtype=np.float32, copy=True)
    clip_start = clip.start_ticks
    clip_end = clip.start_ticks + clip.duration_ticks
    clip_start_seconds = project.ticks_to_seconds(clip_start)
    clip_duration_seconds = project.tick_duration_seconds(clip_start, clip.duration_ticks)
    for interval in intervals:
        local_start = max(0.0, project.seconds_between_ticks(clip_start, interval.start_ticks))
        local_end = min(clip_duration_seconds, project.seconds_between_ticks(clip_start, min(interval.end_ticks, clip_end)))
        first = max(0, int(math.floor(local_start * sample_rate)))
        last = min(len(processed), int(math.ceil(local_end * sample_rate)))
        if last <= first:
            continue
        local_seconds = (first + np.arange(last - first, dtype=np.float64)) / sample_rate
        positions = np.asarray([
            project.seconds_to_ticks_float(clip_start_seconds + float(offset))
            for offset in local_seconds
        ])
        progress = np.clip((positions - interval.start_ticks) / max(1e-9, interval.end_ticks - interval.start_ticks), 0.0, 1.0)
        if interval.role == "outgoing":
            shape = np.cos(progress * np.pi / 2.0)
        else:
            shape = np.sin(progress * np.pi / 2.0)
        processed[first:last] *= shape[:, None].astype(np.float32)
    return processed
