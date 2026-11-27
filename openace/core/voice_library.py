"""Persistent zero-shot reference voice library."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import BinaryIO, List, Optional

import numpy as np
import soundfile as sf
from pydantic import BaseModel

from openace.core.models import new_id

AUDIO_SUFFIXES = {".wav", ".flac", ".aiff", ".aif", ".ogg", ".mp3"}


class VoiceProfile(BaseModel):
    id: str
    name: str
    path: str
    created_at: float
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    size_bytes: int = 0
    peak_level: float = 0.0
    clipping_ratio: float = 0.0
    rms_dbfs: float = -120.0
    silence_ratio: float = 1.0
    voiced_seconds: float = 0.0
    quality_warnings: List[str] = []



def analyze_voice_quality(path: Path, duration: float, sample_rate: int) -> dict:
    """Measure conservative reference-audio quality signals without judging model output."""
    try:
        data, sr = sf.read(str(path), always_2d=True)
        mono = np.asarray(data, dtype=np.float64).mean(axis=1)
    except Exception:
        return {
            "peak_level": 0.0,
            "clipping_ratio": 0.0,
            "rms_dbfs": -120.0,
            "silence_ratio": 1.0,
            "voiced_seconds": 0.0,
            "quality_warnings": ["audio quality analysis failed; verify the file manually before rendering"],
        }
    if mono.size == 0:
        mono = np.zeros(1, dtype=np.float64)
    peak = float(np.max(np.abs(mono)))
    clipping_ratio = float(np.mean(np.abs(mono) >= 0.999))
    rms = float(np.sqrt(np.mean(mono ** 2))) if mono.size else 0.0
    rms_dbfs = 20.0 * np.log10(max(rms, 1e-9))
    frame = max(1, int(round(sr * 0.02)))
    usable_frames = mono.size // frame
    if usable_frames:
        trimmed = mono[:usable_frames * frame].reshape(usable_frames, frame)
        frame_rms = np.sqrt(np.mean(trimmed ** 2, axis=1))
    else:
        frame_rms = np.array([rms])
    nonsilent = frame_rms >= 10 ** (-45.0 / 20.0)
    silence_ratio = float(1.0 - np.mean(nonsilent))
    voiced_seconds = float(np.sum(nonsilent) * frame / sr)
    warnings = []
    if duration < 2.0:
        warnings.append("reference is shorter than 2s; zero-shot timbre may be unstable")
    elif duration > 30.0:
        warnings.append("reference is longer than 30s; trim to the cleanest phrase for faster and more predictable zero-shot prompting")
    if voiced_seconds < 1.0 or silence_ratio > 0.75:
        warnings.append("reference is mostly silence or contains too little usable voiced material")
    if peak >= 0.999 or clipping_ratio > 0.001:
        warnings.append("reference appears clipped; use a cleaner non-distorted vocal take")
    if rms_dbfs < -45.0:
        warnings.append("reference level is very low; increase input gain without clipping")
    if sample_rate < 16000:
        warnings.append("sample rate is below 16kHz; use a cleaner vocal recording")
    return {
        "peak_level": round(peak, 5),
        "clipping_ratio": round(clipping_ratio, 6),
        "rms_dbfs": round(float(rms_dbfs), 2),
        "silence_ratio": round(silence_ratio, 4),
        "voiced_seconds": round(voiced_seconds, 3),
        "quality_warnings": warnings,
    }

class VoiceLibrary:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.root / "voices.json"

    def _load(self) -> List[VoiceProfile]:
        if not self.metadata_path.exists():
            return []
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            return [VoiceProfile.model_validate(item) for item in payload]
        except Exception:
            return []

    def _save(self, voices: List[VoiceProfile]) -> None:
        payload = json.dumps([voice.model_dump(mode="json") for voice in voices], ensure_ascii=False, indent=2)
        temporary = self.metadata_path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.metadata_path)

    def list(self) -> List[VoiceProfile]:
        return sorted(
            [voice for voice in self._load() if Path(voice.path).exists()],
            key=lambda voice: voice.created_at,
            reverse=True,
        )

    def get(self, voice_id: str) -> VoiceProfile:
        for voice in self._load():
            if voice.id == voice_id:
                return voice
        raise KeyError(f"voice not found: {voice_id}")

    def create(self, filename: str, stream: BinaryIO) -> VoiceProfile:
        original = Path(filename or "reference.wav").name
        suffix = Path(original).suffix.lower() or ".wav"
        if suffix not in AUDIO_SUFFIXES:
            raise ValueError(f"unsupported reference voice format: {suffix}")
        voice_id = new_id("voice")
        safe_stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in Path(original).stem).strip("_") or "reference"
        destination = self.root / f"{voice_id}_{safe_stem}{suffix}"
        with destination.open("wb") as handle:
            while True:
                chunk = stream.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
        try:
            info = sf.info(str(destination))
            duration = info.frames / float(info.samplerate)
            sample_rate = int(info.samplerate)
            channels = int(info.channels)
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise ValueError("reference voice is not readable audio") from exc
        if duration <= 0.05:
            destination.unlink(missing_ok=True)
            raise ValueError("reference voice is too short")
        quality = analyze_voice_quality(destination, duration, sample_rate)
        voice = VoiceProfile(
            id=voice_id,
            name=Path(original).stem or "Reference voice",
            path=str(destination),
            created_at=time.time(),
            duration_seconds=round(duration, 3),
            sample_rate=sample_rate,
            channels=channels,
            size_bytes=destination.stat().st_size,
            **quality,
        )
        voices = self._load()
        voices.append(voice)
        self._save(voices)
        return voice

    def rename(self, voice_id: str, name: str) -> VoiceProfile:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("voice name must not be empty")
        voices = self._load()
        for index, voice in enumerate(voices):
            if voice.id == voice_id:
                updated = voice.model_copy(update={"name": cleaned})
                voices[index] = updated
                self._save(voices)
                return updated
        raise KeyError(f"voice not found: {voice_id}")

    def delete(self, voice_id: str) -> VoiceProfile:
        voices = self._load()
        for index, voice in enumerate(voices):
            if voice.id == voice_id:
                voices.pop(index)
                self._save(voices)
                Path(voice.path).unlink(missing_ok=True)
                return voice
        raise KeyError(f"voice not found: {voice_id}")
