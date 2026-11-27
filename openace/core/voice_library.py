"""Persistent zero-shot reference voice library."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import BinaryIO, List, Optional

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
        voice = VoiceProfile(
            id=voice_id,
            name=Path(original).stem or "Reference voice",
            path=str(destination),
            created_at=time.time(),
            duration_seconds=round(duration, 3),
            sample_rate=sample_rate,
            channels=channels,
            size_bytes=destination.stat().st_size,
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
