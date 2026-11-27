from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from .base import EngineUnavailable
from .processes import CancellationToken, run_cancellable
from .downloader import external_dir
from .vram import VRAMManager


def acestep_repo_path() -> Path:
    return Path(os.environ.get("OPENACE_ACESTEP_REPO", external_dir() / "ACE-Step-1.5")).resolve()


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return '""'
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def write_toml(path: Path, data: Dict[str, Any]) -> None:
    lines = [f"{key} = {_toml_value(value)}" for key, value in data.items() if value is not None]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ACEStepEngine:
    """Production adapter for the real ACE-Step 1.5 CLI/runtime."""

    def __init__(self, repo_path: Optional[Path] = None, device: str = "auto", vram: Optional[VRAMManager] = None):
        self.repo = (repo_path or acestep_repo_path()).resolve()
        self.device = device
        self.vram = vram or VRAMManager()

    def _require(self) -> None:
        if not (self.repo / "cli.py").exists() or not (self.repo / "acestep/inference.py").exists():
            raise EngineUnavailable(
                f"ACE-Step 1.5 source is missing at {self.repo}; run scripts/bootstrap_models.py"
            )

    def _run_generation(self, config: Dict[str, Any], output_path: Path, cancellation: Optional[CancellationToken] = None) -> Path:
        self._require()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="openace-acestep-") as tmp:
            tmpdir = Path(tmp)
            save_dir = tmpdir / "out"
            save_dir.mkdir()
            merged = {
                "project_root": str(self.repo),
                "checkpoint_dir": str(self.repo / "checkpoints"),
                "device": self.device,
                "backend": "pt",
                "offload_to_cpu": True,
                "offload_dit_to_cpu": True,
                "save_dir": str(save_dir),
                "audio_format": "wav",
                "batch_size": 1,
                "inference_steps": 8,
                "seed": -1,
                "use_random_seed": True,
                "thinking": False,
                "use_cot_metas": False,
                "use_cot_caption": False,
                "use_cot_language": False,
                "use_constrained_decoding": False,
                "enable_normalization": True,
                "normalization_db": -1.0,
            }
            merged.update(config)
            config_path = tmpdir / "generation.toml"
            write_toml(config_path, merged)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.repo) + os.pathsep + env.get("PYTHONPATH", "")
            env.setdefault("ACESTEP_CHECKPOINTS_DIR", str(self.repo / "checkpoints"))
            cmd = [sys.executable, "cli.py", "--config", str(config_path), "--backend", "pt"]
            with self.vram.acquire("ace-step-1.5", estimated_gb=4.0):
                proc = run_cancellable(
                    cmd,
                    cancellation,
                    cwd=self.repo,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            if proc.returncode != 0:
                raise EngineUnavailable("ACE-Step generation failed:\n" + proc.stdout[-6000:])
            candidates = sorted(save_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not candidates:
                raise EngineUnavailable("ACE-Step completed without a wav output")
            shutil.copyfile(candidates[0], output_path)
        return output_path

    def vocal_to_bgm(self, vocal_audio: Path, output_path: Path, caption: str, duration: float, bpm: float, cancellation: Optional[CancellationToken] = None) -> Path:
        if not vocal_audio.exists():
            raise FileNotFoundError(vocal_audio)
        return self._run_generation(
            {
                # ACE-Step's vocal-to-BGM workflow is the base-model `complete` task:
                # the source vocal is the partial track and the model adds mixed accompaniment.
                "task_type": "complete",
                "src_audio": str(vocal_audio),
                "instruction": "Complete the input track with drums, bass, keyboard, guitar:",
                "caption": caption or "professional accompaniment matching the vocal melody",
                "lyrics": "",
                "duration": round(duration, 2),
                "bpm": round(bpm),
            },
            output_path,
            cancellation,
        )

    def repaint(self, source_audio: Path, output_path: Path, start_s: float, end_s: float, caption: str, cancellation: Optional[CancellationToken] = None) -> Path:
        if not source_audio.exists():
            raise FileNotFoundError(source_audio)
        if end_s != -1 and end_s <= start_s:
            raise ValueError("repaint end must be greater than start")
        return self._run_generation(
            {
                "task_type": "repaint",
                "src_audio": str(source_audio),
                "repainting_start": round(start_s, 3),
                "repainting_end": round(end_s, 3),
                "chunk_mask_mode": "explicit",
                "caption": caption or "seamlessly regenerate the selected region in the same musical style",
                "instrumental": True,
                "lyrics": "[Instrumental]",
            },
            output_path,
            cancellation,
        )

    def text_to_music(self, output_path: Path, caption: str, duration: float, bpm: float, lyrics: str = "[Instrumental]") -> Path:
        return self._run_generation(
            {
                "task_type": "text2music",
                "caption": caption,
                "lyrics": lyrics,
                "instrumental": lyrics.strip().lower() == "[instrumental]",
                "duration": round(duration, 2),
                "bpm": round(bpm),
            },
            output_path,
        )
