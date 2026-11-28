from __future__ import annotations

"""Explicit CI-only deterministic synthesis fixtures.

This module is never a production engine. `EngineFactory` refuses to construct it unless
OPENACE_CI_SYNTH_FIXTURE=1 is present, and every rendered file metadata/diagnostic marks
it as a fixture. It exists only so CPU sandboxes can verify orchestration, invariants,
API plumbing, and UI behavior without pretending to be SoulX-Singer or ACE-Step.
"""

import os
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from openace.core.models import Project, Track
from openace.core.pitch import midi_to_hz, vibrato_envelope, pitch_envelope_state
from openace.engines.processes import JobCancelled

FIXTURE_ENV = "OPENACE_CI_SYNTH_FIXTURE"


def fixture_enabled() -> bool:
    return os.environ.get(FIXTURE_ENV) == "1"


def require_fixture_enabled() -> None:
    if not fixture_enabled():
        raise RuntimeError("CI synthesis fixture requires OPENACE_CI_SYNTH_FIXTURE=1")


def write_fixture_wav(path: Path, samples: np.ndarray, sample_rate: int = 24000) -> Path:
    require_fixture_enabled()
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), samples.astype(np.float32), sample_rate, subtype="PCM_16")
    return path


class FixtureVocalEngine:
    def render_score(self, project: Project, track: Track, output_path: Path, reference_voice=None, cancellation=None, progress=None) -> Path:
        require_fixture_enabled()
        delay = float(os.environ.get("OPENACE_CI_FIXTURE_DELAY_SECONDS", "0") or 0)
        if progress: progress(0.12, "fixture vocal synthesis stage")
        failure_file = os.environ.get("OPENACE_CI_FIXTURE_FAIL_VOCAL_FILE", "")
        if failure_file and Path(failure_file).exists():
            raise RuntimeError("explicit CI vocal render failure requested")
        if delay > 0:
            deadline = time.time() + delay
            while time.time() < deadline:
                if cancellation is not None and cancellation.cancelled:
                    raise JobCancelled("render job cancelled")
                time.sleep(min(0.05, deadline - time.time()))
        sr = 24000
        total = max(1, int(project.ticks_to_seconds(project.duration_ticks() + project.ppq) * sr))
        out = np.zeros(total, dtype=np.float32)
        automation_points = sorted(track.automation.pitch_cents, key=lambda point: point.ticks)
        automation_x = np.array([point.ticks for point in automation_points], dtype=np.float64)
        automation_y = np.array([point.value for point in automation_points], dtype=np.float64)
        for note in track.sorted_notes():
            start = int(project.ticks_to_seconds(note.start_ticks) * sr)
            end = min(total, int(project.ticks_to_seconds(note.end_ticks) * sr))
            if end <= start:
                continue
            t = np.arange(end - start) / sr
            absolute_seconds = start / sr + t
            duration_ms = max(1e-9, (end - start) / sr * 1000.0)
            offset_ms = t * 1000.0
            handle_points = sorted(note.pitch_curve, key=lambda point: point.offset_ms)
            if handle_points:
                cents = np.interp(
                    offset_ms,
                    np.array([point.offset_ms for point in handle_points], dtype=np.float64),
                    np.array([point.cents for point in handle_points], dtype=np.float64),
                )
            else:
                cents = np.zeros(len(t), dtype=np.float64)
            if note.vibrato:
                envelope = np.array([vibrato_envelope(note, float(value), duration_ms) for value in offset_ms], dtype=np.float64)
                cents = cents + max(0.0, min(2.0, note.pitch_modulation)) * envelope * note.vibrato.depth_cents * np.sin(2.0 * np.pi * note.vibrato.frequency_hz * offset_ms / 1000.0 + note.vibrato.phase)
            voiced_mask = np.ones(len(t), dtype=np.float64)
            if len(automation_x):
                ticks = np.array([project.seconds_to_ticks_float(float(value)) for value in absolute_seconds], dtype=np.float64)
                cents = cents + np.interp(ticks, automation_x, automation_y)
                states = [pitch_envelope_state(automation_points, float(tick))[1] for tick in ticks]
                voiced_mask = np.array(states, dtype=np.float64)
            instantaneous_f0 = midi_to_hz(note.pitch) * np.power(2.0, cents / 1200.0)
            phase = 2.0 * np.pi * np.cumsum(instantaneous_f0) / sr
            # Harmonic fixture intentionally sounds artificial; it validates control flow only.
            env = np.minimum(1.0, np.linspace(0, 8, len(t))) * np.minimum(1.0, np.linspace(8, 0, len(t)))
            signal = (
                0.30 * np.sin(phase)
                + 0.14 * np.sin(2.0 * phase)
                + 0.06 * np.sin(3.0 * phase)
            ) * env * voiced_mask
            out[start:end] += signal.astype(np.float32)
        if progress: progress(0.82, "writing fixture vocal output")
        return write_fixture_wav(output_path, out, sr)

    def convert_voice(self, source_audio: Path, reference_voice: Path, output_path: Path, cancellation=None, progress=None, pitch_shift: int = 0, auto_shift: bool = False) -> Path:
        require_fixture_enabled()
        data, sr = sf.read(str(source_audio), always_2d=False)
        # A transparent pass-through would be misleading, so add a clear low-level fixture tremolo.
        mono = np.asarray(data, dtype=np.float32)
        if mono.ndim > 1:
            mono = mono.mean(axis=1)
        shift = int(pitch_shift)
        if auto_shift and shift == 0:
            try:
                import librosa

                def median_f0(audio):
                    f0 = librosa.yin(np.asarray(audio, dtype=np.float32), fmin=50, fmax=1000, sr=sr)
                    voiced = f0[np.isfinite(f0) & (f0 > 0)]
                    return float(np.median(voiced)) if len(voiced) else 0.0

                ref_data, ref_sr = sf.read(str(reference_voice), always_2d=False)
                ref = np.asarray(ref_data, dtype=np.float32)
                if ref.ndim > 1:
                    ref = ref.mean(axis=1)
                if ref_sr != sr:
                    ref = librosa.resample(ref, orig_sr=ref_sr, target_sr=sr)
                source_median = median_f0(mono)
                reference_median = median_f0(ref)
                if source_median > 0 and reference_median > 0:
                    shift = int(round(12.0 * np.log2(reference_median / source_median)))
            except Exception:
                shift = 0
        fixture = mono
        if shift:
            try:
                import librosa

                fixture = librosa.effects.pitch_shift(np.asarray(mono, dtype=np.float32), sr=sr, n_steps=shift)
            except Exception:
                fixture = mono
        t = np.arange(len(fixture)) / sr
        fixture = fixture * (0.8 + 0.2 * np.sin(2 * np.pi * 5 * t))
        if progress: progress(0.82, "writing fixture conversion output")
        return write_fixture_wav(output_path, fixture, sr)


class FixtureMusicEngine:
    def vocal_to_bgm(self, vocal_audio: Path, output_path: Path, caption: str, duration: float, bpm: float, cancellation=None, progress=None) -> Path:
        require_fixture_enabled()
        sr = 24000
        n = int(max(1.0, duration) * sr)
        t = np.arange(n) / sr
        beat_hz = bpm / 60.0
        # Sparse rhythm/chord fixture; deliberately not a substitute for ACE-Step.
        chord = 0.08 * np.sin(2 * np.pi * 110 * t) + 0.06 * np.sin(2 * np.pi * 165 * t)
        gate = (np.sin(2 * np.pi * beat_hz * t) > -0.2).astype(np.float32)
        if progress: progress(0.82, "writing fixture accompaniment output")
        return write_fixture_wav(output_path, chord * gate, sr)

    def repaint(self, source_audio: Path, output_path: Path, start_s: float, end_s: float, caption: str, cancellation=None, progress=None) -> Path:
        require_fixture_enabled()
        data, sr = sf.read(str(source_audio), always_2d=False)
        audio = np.asarray(data, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        start = int(start_s * sr)
        end = len(audio) if end_s < 0 else min(len(audio), int(end_s * sr))
        if end > start:
            t = np.arange(end - start) / sr
            audio[start:end] = 0.12 * np.sin(2 * np.pi * 220 * t)
        if progress: progress(0.82, "writing fixture repaint output")
        return write_fixture_wav(output_path, audio, sr)

def fixture_separate_stems(source_audio: Path, vocal_output: Path, accompaniment_output: Path, progress=None) -> tuple[Path, Path]:
    """Explicit CI-only two-stem orchestration fixture, never production separation."""
    require_fixture_enabled()
    data, sr = sf.read(str(source_audio), always_2d=False)
    mono = np.asarray(data, dtype=np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    if len(mono) < 16:
        raise ValueError("source audio is too short for fixture separation")
    spectrum = np.fft.rfft(mono)
    frequencies = np.fft.rfftfreq(len(mono), 1.0 / sr)
    vocal = np.fft.irfft(spectrum * (frequencies >= 500.0), n=len(mono)).astype(np.float32)
    accompaniment = np.fft.irfft(spectrum * (frequencies < 500.0), n=len(mono)).astype(np.float32)
    if progress: progress(0.82, "writing fixture separated stems")
    write_fixture_wav(vocal_output, vocal, sr)
    write_fixture_wav(accompaniment_output, accompaniment, sr)
    return vocal_output, accompaniment_output
