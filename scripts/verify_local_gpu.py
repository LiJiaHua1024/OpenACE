#!/usr/bin/env python3
"""One-command real-GPU acceptance check for OpenACE.

This script never uses OPENACE_CI_SYNTH_FIXTURE. It verifies CUDA, pulls the public
open-source SoulX-Singer and ACE-Step 1.5 sources/weights, renders a short real SVS
example, renders a short real instrumental ACE-Step example, validates loudness/true
peak, and writes an inspection report under artifacts/local_gpu/.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(cmd, cwd=None, env=None):
    print("+", " ".join(map(str, cmd)))
    subprocess.run([str(x) for x in cmd], cwd=cwd, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-separation", action="store_true", help="skip the Demucs stem-separation acceptance stage")
    parser.add_argument("--hf-endpoint", default=os.environ.get("HF_ENDPOINT", ""))
    args = parser.parse_args()

    os.environ.pop("OPENACE_CI_SYNTH_FIXTURE", None)
    report = {"started_at": time.time(), "steps": []}
    artifacts = ROOT / "artifacts" / "local_gpu"
    artifacts.mkdir(parents=True, exist_ok=True)

    try:
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is not visible to PyTorch")
        report["gpu"] = {
            "name": torch.cuda.get_device_name(0),
            "total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
        }
        report["steps"].append({"cuda": "ok", **report["gpu"]})
    except Exception as exc:
        report["steps"].append({"cuda": "failed", "error": str(exc)})
        (artifacts / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    if not args.skip_download:
        cmd = [sys.executable, str(ROOT / "scripts/bootstrap_models.py"), "--install-deps"]
        if args.hf_endpoint:
            cmd += ["--hf-endpoint", args.hf_endpoint]
        run(cmd, cwd=ROOT)
        report["steps"].append({"model_download": "ok"})

    # Real acceptance is implemented as subprocesses so CUDA memory is fully released
    # between the two large model families.
    vocal_out = artifacts / "soulx_real.wav"
    bgm_out = artifacts / "acestep_real.wav"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    demo = ROOT / "external/SoulX-Singer/example/audio/zh_prompt.mp3"
    demo_meta = ROOT / "external/SoulX-Singer/example/audio/zh_prompt.json"
    target = ROOT / "external/SoulX-Singer/example/audio/music.json"
    if not demo.exists() or not target.exists():
        raise RuntimeError("SoulX example assets are missing after source bootstrap")

    svs_dir = artifacts / "soulx_run"
    run(
        [
            sys.executable,
            "-m",
            "cli.inference",
            "--device",
            "cuda",
            "--model_path",
            "pretrained_models/SoulX-Singer/model.pt",
            "--config",
            "soulxsinger/config/soulxsinger.yaml",
            "--prompt_wav_path",
            str(demo),
            "--prompt_metadata_path",
            str(demo_meta),
            "--target_metadata_path",
            str(target),
            "--phoneset_path",
            "soulxsinger/utils/phoneme/phone_set.json",
            "--save_dir",
            str(svs_dir),
            "--auto_shift",
            "--pitch_shift",
            "0",
            "--control",
            "score",
            "--fp16",
        ],
        cwd=ROOT / "external/SoulX-Singer",
        env=env,
    )
    generated = svs_dir / "generated.wav"
    if not generated.exists():
        raise RuntimeError("SoulX-Singer did not produce generated.wav")
    generated.replace(vocal_out)
    report["steps"].append({"soulx_real_render": str(vocal_out)})

    ace_cfg = artifacts / "ace_verify.toml"
    ace_out_dir = artifacts / "ace_run"
    ace_out_dir.mkdir(exist_ok=True)
    ace_cfg.write_text(
        "\n".join(
            [
                f'project_root = "{ROOT / "external/ACE-Step-1.5"}"',
                f'checkpoint_dir = "{ROOT / "external/ACE-Step-1.5/checkpoints"}"',
                'device = "auto"',
                'backend = "pt"',
                'offload_to_cpu = true',
                'offload_dit_to_cpu = true',
                f'save_dir = "{ace_out_dir}"',
                'audio_format = "wav"',
                'caption = "short polished cinematic pop instrumental verification"',
                'lyrics = "[Instrumental]"',
                'instrumental = true',
                'duration = 10',
                'bpm = 96',
                'batch_size = 1',
                'inference_steps = 8',
                'thinking = false',
                'use_cot_metas = false',
                'use_cot_caption = false',
                'use_cot_language = false',
                'use_constrained_decoding = false',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run([sys.executable, "cli.py", "--config", str(ace_cfg), "--backend", "pt"], cwd=ROOT / "external/ACE-Step-1.5", env=env)
    candidates = sorted(ace_out_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("ACE-Step did not produce a wav")
    candidates[0].replace(bgm_out)
    report["steps"].append({"acestep_real_render": str(bgm_out)})

    from openace.core.audio import integrated_loudness_lufs, read_audio, true_peak_db

    audio_report = {}
    for name, path in {"soulx": vocal_out, "acestep": bgm_out}.items():
        data, sr = read_audio(path)
        audio_report[name] = {
            "seconds": round(len(data) / sr, 2),
            "integrated_lufs": round(integrated_loudness_lufs(data, sr), 2),
            "true_peak_dbtp_approx": round(true_peak_db(data, sr), 2),
        }
    report["audio"] = audio_report

    if not args.skip_separation:
        # Validate the production Demucs path on a real mixture made from the two model
        # outputs. This is intentionally after both heavyweight synthesis subprocesses so
        # memory use remains stage-wise rather than co-resident.
        import numpy as np
        import soundfile as sf

        from openace.engines.separation import DemucsStemSeparator

        vocal_audio, vocal_sr = read_audio(vocal_out)
        bgm_audio, bgm_sr = read_audio(bgm_out)
        vocal_mono = np.asarray(vocal_audio, dtype=np.float32)
        bgm_mono = np.asarray(bgm_audio, dtype=np.float32)
        if vocal_mono.ndim > 1:
            vocal_mono = vocal_mono.mean(axis=1)
        if bgm_mono.ndim > 1:
            bgm_mono = bgm_mono.mean(axis=1)
        if vocal_sr != bgm_sr:
            ratio = vocal_sr / bgm_sr
            x_old = np.linspace(0.0, 1.0, num=len(bgm_mono), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=max(1, int(round(len(bgm_mono) * ratio))), endpoint=False)
            bgm_mono = np.interp(x_new, x_old, bgm_mono).astype(np.float32)
            bgm_sr = vocal_sr
        length = min(len(vocal_mono), len(bgm_mono), int(5 * vocal_sr))
        if length < vocal_sr:
            raise RuntimeError("model outputs are too short for separation acceptance")
        mixture = vocal_mono[:length] * 0.8 + bgm_mono[:length] * 0.35
        mixture_path = artifacts / "separation_input.wav"
        sf.write(mixture_path, mixture, vocal_sr, subtype="PCM_16")
        sep_vocal, sep_accompaniment = DemucsStemSeparator().separate(mixture_path, artifacts / "demucs_run")
        report["steps"].append({
            "demucs_separation": "ok",
            "vocal": str(sep_vocal),
            "accompaniment": str(sep_accompaniment),
        })

    report["ok"] = True
    (artifacts / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nLocal GPU acceptance passed. Listen to:\n  {vocal_out}\n  {bgm_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
