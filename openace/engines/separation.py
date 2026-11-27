"""Local open-source stem separation backend."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import soundfile as sf

from openace.engines.base import EngineUnavailable


class DemucsStemSeparator:
    """Run Demucs locally and return vocals/no-vocals stems.

    Demucs is an optional production dependency because it pulls a large torch/model
    stack. It is never replaced by synthetic fixture output unless the explicit CI
    fixture environment variable is set.
    """

    def __init__(self, model: str = "htdemucs"):
        self.model = model

    def separate(self, source_audio: Path, output_dir: Path) -> tuple[Path, Path]:
        if importlib.util.find_spec("demucs") is None:
            raise EngineUnavailable(
                "Demucs is not installed. Install OpenACE GPU extras (`pip install -e .[gpu]`) "
                "or `pip install demucs` on the local machine; no API key is required."
            )
        if not Path(source_audio).exists():
            raise ValueError(f"source audio does not exist: {source_audio}")
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "demucs",
            "-n",
            self.model,
            "--two-stems",
            "vocals",
            "-o",
            str(output_dir),
            str(source_audio),
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=3600)
        if result.returncode != 0:
            raise RuntimeError("Demucs separation failed:\n" + result.stdout[-3000:])
        stem_dir = output_dir / self.model / Path(source_audio).stem
        vocals = stem_dir / "vocals.wav"
        accompaniment = stem_dir / "no_vocals.wav"
        if not vocals.exists() or not accompaniment.exists():
            raise RuntimeError(f"Demucs did not produce expected stems in {stem_dir}")
        stable_vocals = output_dir / "separated_vocal.wav"
        stable_accompaniment = output_dir / "separated_accompaniment.wav"
        shutil.copy2(vocals, stable_vocals)
        shutil.copy2(accompaniment, stable_accompaniment)
        for path in (stable_vocals, stable_accompaniment):
            info = sf.info(str(path))
            if info.frames <= 0:
                raise RuntimeError(f"Demucs produced empty stem: {path}")
        return stable_vocals, stable_accompaniment
