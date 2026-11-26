from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from openace.core.models import Project, Track


class EngineUnavailable(RuntimeError):
    """Raised when a real model runtime or checkpoint is not installed."""


class VocalEngine(Protocol):
    def render_score(self, project: Project, track: Track, output_path: Path, reference_voice: Optional[Path] = None) -> Path:
        ...

    def convert_voice(self, source_audio: Path, reference_voice: Path, output_path: Path) -> Path:
        ...


class MusicEngine(Protocol):
    def vocal_to_bgm(self, vocal_audio: Path, output_path: Path, caption: str, duration: float, bpm: float) -> Path:
        ...

    def repaint(self, source_audio: Path, output_path: Path, start_s: float, end_s: float, caption: str) -> Path:
        ...
