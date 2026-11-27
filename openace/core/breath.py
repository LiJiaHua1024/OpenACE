from __future__ import annotations

"""Honest post-render breath-event processing.

SoulX-Singer exposes no neural breath-event conditioning input. OpenACE therefore does
not synthesize white noise and pretend it is a singer breath. When the user places breath
markers, this module extracts broad-band aspiration noise that already exists in the
reference voice (preferred) or in the rendered vocal itself, then overlays a filtered,
time-fitted copy at the requested timeline positions. If no suitable real donor noise is
present, it explicitly reports that no breath was applied instead of fabricating one.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from openace.core.audio import read_audio
from openace.core.models import Project, Track


@dataclass
class BreathProcessingResult:
    applied: int
    donor_source: str = ""
    detail: str = ""
    skipped: list[str] = field(default_factory=list)


def _mono(audio: np.ndarray) -> np.ndarray:
    data = np.asarray(audio, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)


def _spectral_highpass(samples: np.ndarray, sample_rate: int, low_hz: float = 550.0, high_hz: float = 1300.0) -> np.ndarray:
    if len(samples) < 8:
        return samples.astype(np.float32)
    spectrum = np.fft.rfft(samples)
    frequencies = np.fft.rfftfreq(len(samples), 1.0 / sample_rate)
    gain = np.clip((frequencies - low_hz) / max(1.0, high_hz - low_hz), 0.0, 1.0)
    filtered = np.fft.irfft(spectrum * gain, n=len(samples))
    return np.asarray(filtered, dtype=np.float32)


def extract_breath_donor(audio: np.ndarray, sample_rate: int, max_seconds: float = 0.8) -> Optional[np.ndarray]:
    """Extract the strongest broad-band aperiodic aspiration segment from real audio."""
    mono = _mono(audio)
    frame = min(1024, max(256, int(round(sample_rate * 0.04))))
    hop = max(128, frame // 4)
    if len(mono) < frame * 2:
        return None
    count = 1 + (len(mono) - frame) // hop
    if count < 3:
        return None
    frames = np.lib.stride_tricks.as_strided(
        mono,
        shape=(count, frame),
        strides=(mono.strides[0] * hop, mono.strides[0]),
    )
    window = np.hanning(frame).astype(np.float32)
    best_group: tuple[float, int, int] | None = None
    group_start: int | None = None
    group_score = 0.0
    scores = []
    metrics = []
    chunk = 512
    for offset in range(0, count, chunk):
        block = frames[offset:offset + chunk] * window
        spectrum = np.fft.rfft(block, axis=1)
        power = np.abs(spectrum) ** 2
        frequencies = np.fft.rfftfreq(frame, 1.0 / sample_rate)
        total = power.sum(axis=1) + 1e-12
        high_mask = frequencies >= 1200.0
        high = power[:, high_mask]
        high_power = high.sum(axis=1)
        hf_ratio = high_power / total
        magnitude = np.sqrt(high) + 1e-9
        flatness = np.exp(np.mean(np.log(magnitude), axis=1)) / (np.mean(magnitude, axis=1) + 1e-12)
        rms = np.sqrt(np.mean(np.square(block), axis=1))
        for index in range(len(block)):
            metrics.append((float(rms[index]), float(flatness[index]), float(hf_ratio[index])))
    rms_values = np.asarray([item[0] for item in metrics])
    noise_floor = float(np.percentile(rms_values, 20))
    peak = float(np.max(rms_values))
    threshold = max(noise_floor * 1.8, peak * 0.012, 1e-5)
    for index, (rms, flatness, hf_ratio) in enumerate(metrics):
        suitable = rms >= threshold and flatness >= 0.16 and hf_ratio >= 0.22
        score = rms * flatness * hf_ratio if suitable else 0.0
        scores.append(score)
        if suitable:
            if group_start is None:
                group_start = index
                group_score = 0.0
            group_score += score
        elif group_start is not None:
            group_length = index - group_start
            weighted = group_score * min(3.0, group_length / 3.0)
            if group_length >= 3 and (best_group is None or weighted > best_group[0]):
                best_group = (weighted, group_start, index)
            group_start = None
    if group_start is not None:
        group_length = count - group_start
        weighted = group_score * min(3.0, group_length / 3.0)
        if group_length >= 3 and (best_group is None or weighted > best_group[0]):
            best_group = (weighted, group_start, count)
    if best_group is None:
        return None
    _, first, last = best_group
    start = max(0, first * hop - hop // 2)
    end = min(len(mono), last * hop + frame + hop // 2)
    max_length = max(frame, int(round(max_seconds * sample_rate)))
    if end - start > max_length:
        center = (start + end) // 2
        start = max(0, center - max_length // 2)
        end = min(len(mono), start + max_length)
    donor = np.asarray(mono[start:end], dtype=np.float32)
    donor = _spectral_highpass(donor, sample_rate)
    donor -= float(np.mean(donor))
    rms = float(np.sqrt(np.mean(np.square(donor)))) if len(donor) else 0.0
    if rms < 1e-5:
        return None
    return donor / rms


def _join_with_crossfade(left: np.ndarray, right: np.ndarray, overlap: int) -> np.ndarray:
    if overlap <= 0 or len(left) <= overlap or len(right) <= overlap:
        return np.concatenate([left, right])
    fade = np.linspace(0.0, np.pi / 2.0, overlap, dtype=np.float32)
    merged = np.concatenate([
        left[:-overlap],
        left[-overlap:] * np.cos(fade) + right[:overlap] * np.sin(fade),
        right[overlap:],
    ])
    return merged.astype(np.float32)


def _fit_donor(donor: np.ndarray, length: int, sample_rate: int) -> np.ndarray:
    if len(donor) >= length:
        # Prefer the center of the donor where detection confidence is strongest.
        start = max(0, (len(donor) - length) // 2)
        return np.asarray(donor[start:start + length], dtype=np.float32)
    overlap = min(int(round(0.012 * sample_rate)), max(1, len(donor) // 3))
    fitted = np.asarray(donor, dtype=np.float32)
    while len(fitted) < length:
        fitted = _join_with_crossfade(fitted, donor, overlap)
    return fitted[:length]


def _active_vocal_rms(mono: np.ndarray) -> float:
    if len(mono) == 0:
        return 0.0
    frame = min(2048, len(mono))
    count = max(1, len(mono) // frame)
    trimmed = mono[:count * frame].reshape(count, frame)
    frame_rms = np.sqrt(np.mean(np.square(trimmed), axis=1))
    active = frame_rms[frame_rms > max(1e-5, float(np.percentile(frame_rms, 60)))]
    if not len(active):
        return float(np.sqrt(np.mean(np.square(mono))))
    return float(np.percentile(active, 75))


def apply_breath_events(
    audio: np.ndarray,
    sample_rate: int,
    project: Project,
    track: Track,
    reference_audio: Optional[np.ndarray] = None,
    reference_sample_rate: Optional[int] = None,
) -> tuple[np.ndarray, BreathProcessingResult]:
    """Overlay real donor aspiration noise at user-authored breath markers."""
    events = sorted(track.breaths, key=lambda breath: breath.start_ticks)
    if not events or len(audio) == 0:
        return audio, BreathProcessingResult(applied=0, detail="no breath events")
    donor = None
    donor_source = ""
    if reference_audio is not None and reference_sample_rate:
        reference = np.asarray(reference_audio, dtype=np.float32)
        if reference_sample_rate != sample_rate:
            ratio = sample_rate / reference_sample_rate
            mono_reference = _mono(reference)
            x_old = np.linspace(0.0, 1.0, num=len(mono_reference), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=max(1, int(round(len(mono_reference) * ratio))), endpoint=False)
            reference = np.interp(x_new, x_old, mono_reference).astype(np.float32)
        donor = extract_breath_donor(reference, sample_rate)
        if donor is not None:
            donor_source = "reference voice"
    if donor is None:
        donor = extract_breath_donor(audio, sample_rate)
        if donor is not None:
            donor_source = "rendered vocal aspiration"
    if donor is None:
        return audio, BreathProcessingResult(
            applied=0,
            detail="no real aspiration donor found in reference voice or rendered vocal; no synthetic noise inserted",
            skipped=[breath.id for breath in events],
        )

    processed = np.array(audio, dtype=np.float32, copy=True)
    if processed.ndim == 1:
        processed = processed[:, None]
    vocal_rms = max(0.0, _active_vocal_rms(_mono(processed)))
    applied = 0
    skipped: list[str] = []
    for breath in events:
        start_seconds = project.ticks_to_seconds(breath.start_ticks)
        duration_seconds = project.tick_duration_seconds(breath.start_ticks, max(1, breath.duration_ticks))
        first = int(round(start_seconds * sample_rate))
        last = int(round((start_seconds + duration_seconds) * sample_rate))
        first = max(0, first)
        last = min(len(processed), last)
        if last - first < max(8, int(round(0.015 * sample_rate))):
            skipped.append(breath.id)
            continue
        length = last - first
        fitted = _fit_donor(donor, length, sample_rate)
        edge = min(length // 3, max(1, int(round(0.025 * sample_rate))))
        envelope = np.ones(length, dtype=np.float32)
        envelope[:edge] = np.sin(np.linspace(0.0, np.pi / 2.0, edge, dtype=np.float32)) ** 0.8
        envelope[-edge:] = np.sin(np.linspace(np.pi / 2.0, 0.0, edge, dtype=np.float32)) ** 0.8
        target_rms = max(0.004, vocal_rms * 0.20 * 0.7)
        fitted *= target_rms
        processed[first:last] += (fitted * envelope)[:, None]
        applied += 1
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak > 0.98:
        processed *= 0.98 / peak
    detail = "real donor-noise overlays derived from " + donor_source
    if skipped:
        detail += f"; {len(skipped)} out-of-range/too-short events skipped"
    return processed, BreathProcessingResult(applied=applied, donor_source=donor_source, detail=detail, skipped=skipped)


def load_reference_audio(path: str | None) -> tuple[Optional[np.ndarray], Optional[int]]:
    if not path:
        return None, None
    reference = Path(path)
    if not reference.exists():
        return None, None
    try:
        return read_audio(reference)
    except Exception:
        return None, None
