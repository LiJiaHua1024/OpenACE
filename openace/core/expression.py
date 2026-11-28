from __future__ import annotations

import numpy as np

from openace.core.models import EnvelopePoint, Project, Track

_NEUTRAL = 0.5
_DYNAMIC_RANGE_DB = 12.0


def _seconds_to_ticks_array(project: Project, seconds: np.ndarray) -> np.ndarray:
    """Vectorized exact inverse of Project.ticks_to_seconds for automation DSP."""
    points = project.normalized_tempo_map()
    samples = np.asarray(seconds, dtype=np.float64)
    result = np.asarray(samples, dtype=np.float64) * points[0].bpm / 60.0 * project.ppq

    segments = []
    elapsed = 0.0
    previous = points[0]
    for point in points[1:]:
        segment_seconds = project._segment_seconds(previous.ticks, point.ticks, previous.bpm, point.bpm, point.curve == "linear")
        segments.append((elapsed, elapsed + segment_seconds, previous.ticks, point.ticks, previous.bpm, point.bpm, point.curve == "linear"))
        elapsed += segment_seconds
        previous = point
    segments.append((elapsed, np.inf, previous.ticks, previous.ticks, previous.bpm, previous.bpm, False))

    end_seconds = np.asarray([segment[1] for segment in segments], dtype=np.float64)
    indexes = np.searchsorted(end_seconds, samples, side="right")
    for row, segment in enumerate(segments):
        start_second, _, start_ticks, end_ticks, start_bpm, end_bpm, linear = segment
        mask = (indexes == row) & (samples >= start_second)
        if not np.any(mask):
            continue
        local_seconds = samples[mask] - start_second
        if linear and abs(end_bpm - start_bpm) > 1e-9:
            span = end_ticks - start_ticks
            bpm = start_bpm * np.exp(local_seconds * project.ppq / 60.0 * (end_bpm - start_bpm) / span)
            result[mask] = start_ticks + span * (bpm - start_bpm) / (end_bpm - start_bpm)
        else:
            result[mask] = start_ticks + local_seconds * start_bpm / 60.0 * project.ppq
    return result


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


_VELOCITY_NEUTRAL = 90


def velocity_gain_db(velocity: int) -> float:
    """Map OpenACE note velocity to explicit post-render loudness gain."""
    value = max(1, min(127, int(velocity)))
    if value >= _VELOCITY_NEUTRAL:
        return (value - _VELOCITY_NEUTRAL) / 37.0 * 6.0
    return (value - _VELOCITY_NEUTRAL) / 89.0 * 18.0


def apply_note_velocity(audio: np.ndarray, sample_rate: int, project: Project, track: Track) -> tuple[np.ndarray, bool]:
    """Apply per-note velocity as click-safe post-render gain.

    SoulX-Singer's score interface does not consume velocity as neural articulation
    conditioning. OpenACE therefore treats the velocity lane honestly as a per-note
    loudness-performance control: the existing default value 90 is transparent,
    higher values reach +6 dB at 127, and lower values reach -18 dB at 1. Gains are
    placed by exact tempo-aware note boundaries and smoothed over approximately 4 ms
    so step changes do not create sample discontinuities.
    """
    notes = sorted(track.notes, key=lambda note: (note.start_ticks, note.pitch))
    if not notes or not len(audio):
        return audio, False
    gain_db = [velocity_gain_db(note.velocity) for note in notes]
    if all(abs(value) < 0.01 for value in gain_db):
        return audio, False
    if audio.ndim == 1:
        audio = audio[:, None]
    envelope = np.ones(len(audio), dtype=np.float32)
    for note, db in zip(notes, gain_db):
        start_seconds = project.ticks_to_seconds(note.start_ticks)
        end_seconds = project.ticks_to_seconds(note.start_ticks + note.duration_ticks)
        start = max(0, min(len(audio), int(round(start_seconds * sample_rate))))
        end = max(start, min(len(audio), int(round(end_seconds * sample_rate))))
        if end > start:
            envelope[start:end] = float(10.0 ** (db / 20.0))
    smooth_width = max(3, int(round(sample_rate * 0.004)) | 1)
    kernel = np.ones(smooth_width, dtype=np.float32) / float(smooth_width)
    envelope = np.convolve(envelope, kernel, mode="same").astype(np.float32)
    processed = np.array(audio, dtype=np.float32, copy=True)
    processed *= envelope[:, None]
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak > 0.98:
        processed *= 0.98 / peak
    return processed, True


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
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(audio, dtype=np.float32, copy=True)
    peak = 0.0
    chunk_size = 262144
    for start in range(0, len(audio), chunk_size):
        end = min(len(audio), start + chunk_size)
        sample_seconds = (start + np.arange(end - start, dtype=np.float64)) / sample_rate
        sample_ticks = _seconds_to_ticks_array(project, sample_seconds)
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
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(audio, dtype=np.float32, copy=True)
    chunk_size = 262144
    for start in range(0, len(processed), chunk_size):
        end = min(len(processed), start + chunk_size)
        sample_seconds = (start + np.arange(end - start, dtype=np.float64)) / sample_rate
        sample_ticks = _seconds_to_ticks_array(project, sample_seconds)
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
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(source, dtype=np.float32, copy=True)
    chunk_size = 262144
    for start in range(0, len(processed), chunk_size):
        end = min(len(processed), start + chunk_size)
        sample_seconds = (start + np.arange(end - start, dtype=np.float64)) / sample_rate
        sample_ticks = _seconds_to_ticks_array(project, sample_seconds)
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
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(source, dtype=np.float32, copy=True)
    chunk_size = 262144
    for start in range(0, len(processed), chunk_size):
        end = min(len(processed), start + chunk_size)
        sample_seconds = (start + np.arange(end - start, dtype=np.float64)) / sample_rate
        sample_ticks = _seconds_to_ticks_array(project, sample_seconds)
        values = np.interp(sample_ticks, point_ticks, point_values, left=point_values[0], right=point_values[-1])
        bipolar = (values - _NEUTRAL) * 2.0
        amounts = (bipolar * 0.75)[:, None].astype(np.float32)
        processed[start:end] += presence[start:end] * amounts
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak > 0.98:
        processed *= 0.98 / peak
    return processed, True


def apply_falsetto_envelope(audio: np.ndarray, sample_rate: int, project: Project, track: Track) -> tuple[np.ndarray, bool]:
    """Apply Falsetto as spectral-tilt DSP without changing the note pitch.

    Positive values thin the low chest-resonance band and reinforce existing upper
    vocal residue; negative values do the opposite for a chestier/pressed tone. This
    is a transparent post-render approximation, not neural register conditioning,
    and it intentionally does not shift F0.
    """
    points = list(track.automation.falsetto)
    if not points or not len(audio):
        return audio, False
    from scipy import signal

    if audio.ndim == 1:
        audio = audio[:, None]
    source = np.asarray(audio, dtype=np.float32)
    chest_cut = min(650.0, sample_rate * 0.12)
    upper_cut = min(2200.0, sample_rate * 0.35)
    chest_sos = signal.butter(2, chest_cut, btype="lowpass", fs=sample_rate, output="sos")
    upper_sos = signal.butter(2, upper_cut, btype="lowpass", fs=sample_rate, output="sos")
    chest = signal.sosfiltfilt(chest_sos, source, axis=0)
    lowpassed_upper = signal.sosfiltfilt(upper_sos, source, axis=0)
    upper = source - lowpassed_upper
    ordered = sorted(points, key=lambda point: point.ticks)
    point_ticks = np.asarray([point.ticks for point in ordered], dtype=np.float64)
    point_values = np.clip(np.asarray([point.value for point in ordered], dtype=np.float64), 0.0, 1.0)
    processed = np.array(source, dtype=np.float32, copy=True)
    chunk_size = 262144
    for start in range(0, len(processed), chunk_size):
        end = min(len(processed), start + chunk_size)
        sample_seconds = (start + np.arange(end - start, dtype=np.float64)) / sample_rate
        sample_ticks = _seconds_to_ticks_array(project, sample_seconds)
        values = np.interp(sample_ticks, point_ticks, point_values, left=point_values[0], right=point_values[-1])
        bipolar = (values - _NEUTRAL) * 2.0
        positive = np.clip(bipolar, 0.0, 1.0)[:, None].astype(np.float32)
        negative = np.clip(-bipolar, 0.0, 1.0)[:, None].astype(np.float32)
        processed[start:end] = (
            source[start:end]
            - chest[start:end] * positive * 0.28
            + upper[start:end] * positive * 0.45
            + chest[start:end] * negative * 0.25
            - upper[start:end] * negative * 0.25
        )
    peak = float(np.max(np.abs(processed))) if processed.size else 0.0
    if peak > 0.98:
        processed *= 0.98 / peak
    return processed, True
