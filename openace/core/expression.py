from __future__ import annotations

import numpy as np

from openace.core.models import EnvelopePoint, Project, Track

_NEUTRAL = 0.5
_DYNAMIC_RANGE_DB = 12.0


def envelope_value(points: list[EnvelopePoint], ticks: float, default: float = _NEUTRAL) -> float:
    """Linearly interpolate a project-time automation envelope."""
    if not points:
        return default
    ordered = sorted(points, key=lambda point: point.ticks)
    if ticks <= ordered[0].ticks:
        return float(ordered[0].value)
    if ticks >= ordered[-1].ticks:
        return float(ordered[-1].value)
    for left, right in zip(ordered, ordered[1:]):
        if left.ticks <= ticks <= right.ticks:
            span = max(1e-9, right.ticks - left.ticks)
            ratio = (ticks - left.ticks) / span
            return float(left.value + (right.value - left.value) * ratio)
    return float(ordered[-1].value)


def apply_dynamic_envelope(audio: np.ndarray, sample_rate: int, project: Project, track: Track) -> tuple[np.ndarray, bool]:
    """Apply the Dynamic lane as honest post-render gain automation.

    SoulX-Singer does not expose a direct dynamic-conditioning input. Rather than
    pretending the curve is neural conditioning, OpenACE renders the score and then
    applies the user-drawn gain envelope in the audio domain. The lane is centered at
    0.5 and spans ±6 dB. Gain is interpolated at every audio sample in bounded chunks,
    avoiding zipper noise without requiring large temporary envelope arrays.
    """
    points = list(track.automation.dynamic)
    if not points or not len(audio):
        return audio, False
    if audio.ndim == 1:
        audio = audio[:, None]
    seconds_per_tick = 60.0 / project.bpm / project.ppq
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(audio, dtype=np.float32, copy=True)
    peak = 0.0
    chunk_size = 262144
    for start in range(0, len(audio), chunk_size):
        end = min(len(audio), start + chunk_size)
        sample_ticks = (start + np.arange(end - start, dtype=np.float64)) / sample_rate / seconds_per_tick
        values = np.interp(sample_ticks, point_ticks, point_values, left=point_values[0], right=point_values[-1])
        gains = 10.0 ** (((values - _NEUTRAL) * _DYNAMIC_RANGE_DB) / 20.0)
        processed[start:end] *= gains[:, None].astype(np.float32)
        if end:
            peak = max(peak, float(np.max(np.abs(processed[start:end]))))
    if peak > 0.98:
        processed *= 0.98 / peak
    return processed, True


def apply_air_envelope(audio: np.ndarray, sample_rate: int, project: Project, track: Track) -> tuple[np.ndarray, bool]:
    """Apply Air as time-varying high-frequency emphasis derived from the rendered vocal.

    This is transparently a post-render DSP approximation, not neural conditioning:
    a 3 kHz high-frequency residue extracted from the actual vocal is reinforced or
    attenuated according to the lane. No synthetic noise is injected.
    """
    points = list(track.automation.air)
    if not points or not len(audio):
        return audio, False
    from scipy import signal

    if audio.ndim == 1:
        audio = audio[:, None]
    mono_reference = np.mean(audio, axis=1)
    sos = signal.butter(2, min(3000.0, sample_rate * 0.45), btype="lowpass", fs=sample_rate, output="sos")
    low = signal.sosfiltfilt(sos, mono_reference)
    residue = (mono_reference - low)[:, None]
    seconds_per_tick = 60.0 / project.bpm / project.ppq
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(audio, dtype=np.float32, copy=True)
    chunk_size = 262144
    for start in range(0, len(processed), chunk_size):
        end = min(len(processed), start + chunk_size)
        sample_ticks = (start + np.arange(end - start, dtype=np.float64)) / sample_rate / seconds_per_tick
        values = np.interp(sample_ticks, point_ticks, point_values, left=point_values[0], right=point_values[-1])
        bipolar = (values - _NEUTRAL) * 2.0
        amounts = np.where(bipolar >= 0.0, bipolar * 1.8, bipolar * 0.8)
        processed[start:end] += residue[start:end] * amounts[:, None].astype(np.float32)
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak > 0.98:
        processed *= 0.98 / peak
    return processed, True


def apply_energy_envelope(audio: np.ndarray, sample_rate: int, project: Project, track: Track) -> tuple[np.ndarray, bool]:
    """Apply Energy as time-varying harmonic-density DSP.

    Positive values add harmonics through parallel soft saturation of the rendered
    vocal; negative values blend toward a softened low-passed version. This is an
    explicit post-render approximation, not neural energy conditioning.
    """
    points = list(track.automation.energy)
    if not points or not len(audio):
        return audio, False
    from scipy import signal

    if audio.ndim == 1:
        audio = audio[:, None]
    source = np.asarray(audio, dtype=np.float32)
    drive = 2.4
    excited = np.tanh(source * drive) / np.tanh(drive)
    harmonic = excited - source
    cutoff = min(5200.0, sample_rate * 0.38)
    sos = signal.butter(2, cutoff, btype="lowpass", fs=sample_rate, output="sos")
    softened = signal.sosfiltfilt(sos, source, axis=0)
    seconds_per_tick = 60.0 / project.bpm / project.ppq
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(source, dtype=np.float32, copy=True)
    chunk_size = 262144
    for start in range(0, len(processed), chunk_size):
        end = min(len(processed), start + chunk_size)
        sample_ticks = (start + np.arange(end - start, dtype=np.float64)) / sample_rate / seconds_per_tick
        values = np.interp(sample_ticks, point_ticks, point_values, left=point_values[0], right=point_values[-1])
        bipolar = (values - _NEUTRAL) * 2.0
        positive = np.clip(bipolar, 0.0, 1.0)[:, None].astype(np.float32)
        negative = np.clip(-bipolar, 0.0, 1.0)[:, None].astype(np.float32)
        softened_mix = source[start:end] * (1.0 - negative * 0.55) + softened[start:end] * negative * 0.55
        processed[start:end] = softened_mix + harmonic[start:end] * positive * 1.4
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak > 0.98:
        processed *= 0.98 / peak
    return processed, True


def apply_tension_envelope(audio: np.ndarray, sample_rate: int, project: Project, track: Track) -> tuple[np.ndarray, bool]:
    """Apply Tension as time-varying vocal presence-band DSP.

    The 0.9–5.5 kHz articulation/presence band extracted from the actual vocal is
    reinforced or attenuated according to the lane. This is distinct from Air's
    breathy 3 kHz+ residue and is explicitly not neural tension conditioning.
    """
    points = list(track.automation.tension)
    if not points or not len(audio):
        return audio, False
    from scipy import signal

    if audio.ndim == 1:
        audio = audio[:, None]
    source = np.asarray(audio, dtype=np.float32)
    low_cut = min(900.0, sample_rate * 0.12)
    high_cut = min(5500.0, sample_rate * 0.42)
    low_sos = signal.butter(2, low_cut, btype="lowpass", fs=sample_rate, output="sos")
    high_sos = signal.butter(2, high_cut, btype="lowpass", fs=sample_rate, output="sos")
    low = signal.sosfiltfilt(low_sos, source, axis=0)
    high = signal.sosfiltfilt(high_sos, source, axis=0)
    presence = high - low
    seconds_per_tick = 60.0 / project.bpm / project.ppq
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(source, dtype=np.float32, copy=True)
    chunk_size = 262144
    for start in range(0, len(processed), chunk_size):
        end = min(len(processed), start + chunk_size)
        sample_ticks = (start + np.arange(end - start, dtype=np.float64)) / sample_rate / seconds_per_tick
        values = np.interp(sample_ticks, point_ticks, point_values, left=point_values[0], right=point_values[-1])
        bipolar = (values - _NEUTRAL) * 2.0
        amounts = (bipolar * 0.75)[:, None].astype(np.float32)
        processed[start:end] += presence[start:end] * amounts
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak > 0.98:
        processed *= 0.98 / peak
    return processed, True
