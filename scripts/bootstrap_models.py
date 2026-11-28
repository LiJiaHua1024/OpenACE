#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openace.engines.downloader import download_hf, ensure_engine_sources, sync_acestep_model_code  # noqa: E402


def run(cmd, cwd=None, env=None):
    print("+", " ".join(map(str, cmd)))
    subprocess.run([str(x) for x in cmd], cwd=cwd, env=env, check=True)


def pip_install(requirements: Path, mirror: str = "") -> None:
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
    if mirror:
        cmd += ["-i", mirror]
    run(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone/download the real open-source OpenACE engines")
    parser.add_argument("--install-deps", action="store_true", help="install upstream Python requirements")
    parser.add_argument("--hf-endpoint", default=os.environ.get("HF_ENDPOINT", ""), help="Hugging Face endpoint/mirror")
    parser.add_argument("--pypi-mirror", default=os.environ.get("PIP_INDEX_URL", ""))
    args = parser.parse_args()

    if args.hf_endpoint:
        os.environ["HF_ENDPOINT"] = args.hf_endpoint

    soulx, acestep = ensure_engine_sources()
    print(f"SoulX-Singer source: {soulx}")
    print(f"ACE-Step source: {acestep}")

    if args.install_deps:
        install_cmd = [sys.executable, "-m", "pip", "install", "-e", ".[gpu]"]
        if args.pypi_mirror:
            install_cmd += ["-i", args.pypi_mirror]
        run(install_cmd, cwd=ROOT)
        pip_install(soulx / "requirements.txt", args.pypi_mirror)
        pip_install(acestep / "requirements.txt", args.pypi_mirror)

    download_hf("Soul-AILab/SoulX-Singer", soulx / "pretrained_models/SoulX-Singer", endpoint=args.hf_endpoint or None)
    download_hf(
        "Soul-AILab/SoulX-Singer-Preprocess",
        soulx / "pretrained_models/SoulX-Singer-Preprocess",
        endpoint=args.hf_endpoint or None,
    )
    download_hf("ACE-Step/Ace-Step1.5", acestep / "checkpoints", endpoint=args.hf_endpoint or None)
    # Vocal2BGM/complete requires the base DiT variant rather than the turbo-only main snapshot.
    download_hf(
        "ACE-Step/acestep-v15-base",
        acestep / "checkpoints/acestep-v15-base",
        endpoint=args.hf_endpoint or None,
    )
    synced = sync_acestep_model_code(acestep)
    if synced:
        print("Synchronized ACE-Step checkpoint model code:", ", ".join(synced))
    print("Real engine sources and public weights are installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
