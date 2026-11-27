from __future__ import annotations

"""Explicit CI-only deterministic synthesis fixtures.

This module is never a production engine. `EngineFactory` refuses to construct it unless
OPENACE_CI_SYNTH_FIXTURE=1 is present, and every rendered file metadata/diagnostic marks
it as a fixture. It exists only so CPU sandboxes can verify orchestration, invariants,
API plumbing, and UI behavior without pretending to be SoulX-Singer or ACE-Step.
"""

import os
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from openace.core.models import Project, Track
from openace.core.pitch import midi_to_hz

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
    def render_score(self, project: Project, track: Track, output_path: Path, reference_voice=None) -> Path:
        require_fixture_enabled()
        sr = 24000
        total = max(1, int(project.ticks_to_seconds(project.duration_ticks() + project.ppq) * sr))
        out = np.zeros(total, dtype=np.float32)
        for note in track.sorted_notes():
            start = int(project.ticks_to_seconds(note.start_ticks) * sr)
            end = min(total, int(project.ticks_to_seconds(note.end_ticks) * sr))
            if end <= start:
                continue
            t = np.arange(end - start) / sr
            f0 = midi_to_hz(note.pitch)
            # Harmonic fixture intentionally sounds artificial; it validates control flow only.
            env = np.minimum(1.0, np.linspace(0, 8, len(t))) * np.minimum(1.0, np.linspace(8, 0, len(t)))
            signal = (
                0.30 * np.sin(2 * np.pi * f0 * t)
                + 0.14 * np.sin(2 * np.pi * f0 * 2.0 * t)
                + 0.06 * np.sin(2 * np.pi * f0 * 3.0 * t)
            ) * env
            out[start:end] += signal.astype(np.float32)
        return write_fixture_wav(output_path, out, sr)

    def convert_voice(self, source_audio: Path, reference_voice: Path, output_path: Path) -> Path:
        require_fixture_enabled()
        data, sr = sf.read(str(source_audio), always_2d=False)
        # A transparent pass-through would be misleading, so add a clear low-level fixture tremolo.
        mono = np.asarray(data, dtype=np.float32)
        if mono.ndim > 1:
            mono = mono.mean(axis=1)
        t = np.arange(len(mono)) / sr
        fixture = mono * (0.8 + 0.2 * np.sin(2 * np.pi * 5 * t))
        return write_fixture_wav(output_path, fixture, sr)


class FixtureMusicEngine:
    def vocal_to_bgm(self, vocal_audio: Path, output_path: Path, caption: str, duration: float, bpm: float) -> Path:
        require_fixture_enabled()
        sr = 24000
        n = int(max(1.0, duration) * sr)
        t = np.arange(n) / sr
        beat_hz = bpm / 60.0
        # Sparse rhythm/chord fixture; deliberately not a substitute for ACE-Step.
        chord = 0.08 * np.sin(2 * np.pi * 110 * t) + 0.06 * np.sin(2 * np.pi * 165 * t)
        gate = (np.sin(2 * np.pi * beat_hz * t) > -0.2).astype(np.float32)
        return write_fixture_wav(output_path, chord * gate, sr)

    def repaint(self, source_audio: Path, output_path: Path, start_s: float, end_s: float, caption: str) -> Path:
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
        return write_fixture_wav(output_path, audio, sr)
