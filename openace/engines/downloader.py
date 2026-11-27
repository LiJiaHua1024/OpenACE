from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from .base import EngineUnavailable

SOULX_REPO = "https://github.com/Soul-AILab/SoulX-Singer.git"
ACESTEP_REPO = "https://github.com/ace-step/ACE-Step-1.5.git"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def external_dir() -> Path:
    return repo_root() / "external"


def clone_or_update(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (destination / ".git").exists():
        subprocess.run(["git", "-C", str(destination), "pull", "--ff-only"], check=True)
    elif not destination.exists() or not any(destination.iterdir()):
        subprocess.run(["git", "clone", "--depth", "1", url, str(destination)], check=True)
    return destination


def download_hf(repo_id: str, local_dir: Path, endpoint: Optional[str] = None) -> Path:
    """Download model weights with Hugging Face mirror support.

    Set `HF_ENDPOINT` (for example https://hf-mirror.com) or pass `endpoint`; no API key
    is needed for public SoulX-Singer artifacts.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise EngineUnavailable("huggingface-hub is required to download model weights") from exc
    local_dir.mkdir(parents=True, exist_ok=True)
    old_endpoint = os.environ.get("HF_ENDPOINT")
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint
    try:
        snapshot_download(repo_id=repo_id, local_dir=str(local_dir), local_dir_use_symlinks=False)
    finally:
        if endpoint:
            if old_endpoint is None:
                os.environ.pop("HF_ENDPOINT", None)
            else:
                os.environ["HF_ENDPOINT"] = old_endpoint
    return local_dir


def ensure_engine_sources(root: Optional[Path] = None) -> tuple[Path, Path]:
    root = root or external_dir()
    soulx = clone_or_update(SOULX_REPO, root / "SoulX-Singer")
    acestep = clone_or_update(ACESTEP_REPO, root / "ACE-Step-1.5")
    return soulx, acestep


def sync_acestep_model_code(acestep_repo: Path) -> list[str]:
    """Mirror ACE-Step's own downloader contract: checkpoint Python code must match source."""
    synced = []
    variants = {"acestep-v15-base": "base", "acestep-v15-turbo": "turbo"}
    checkpoints = acestep_repo / "checkpoints"
    for directory, variant in variants.items():
        source_dir = acestep_repo / "acestep/models" / variant
        target_dir = checkpoints / directory
        if not source_dir.exists() or not target_dir.exists():
            continue
        for source in source_dir.glob("*.py"):
            if source.name == "__init__.py":
                continue
            shutil.copy2(source, target_dir / source.name)
            synced.append(f"{directory}/{source.name}")
    return synced
