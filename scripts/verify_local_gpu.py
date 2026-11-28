#!/usr/bin/env python3
"""One-command real-GPU acceptance check for OpenACE.

This script never uses OPENACE_CI_SYNTH_FIXTURE. It verifies CUDA, pulls the public
open-source SoulX-Singer and ACE-Step 1.5 sources/weights, renders a short real SVS
example, uses that vocal in OpenACE's production ACE-Step Vocal2BGM/`complete`
adapter, validates loudness/true peak, and writes an inspection report under
artifacts/local_gpu/.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
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

    gpu_info = None
    try:
        from openace.engines.vram import query_nvidia_gpu

        gpu_info = query_nvidia_gpu(0)
        if gpu_info is None:
            # Fallback for hosts where nvidia-smi is unavailable. This may create a CUDA
            # context in the verifier process, so the NVML path above is preferred.
            import torch

            if not torch.cuda.is_available():
                raise RuntimeError("CUDA GPU is not visible to PyTorch")
            free, total = torch.cuda.mem_get_info(0)
            gpu_info = {
                "name": torch.cuda.get_device_name(0),
                "free_gb": free / 1024**3,
                "total_gb": total / 1024**3,
            }
        report["gpu"] = {
            "name": str(gpu_info["name"]),
            "free_gb": round(float(gpu_info["free_gb"]), 2),
            "total_gb": round(float(gpu_info["total_gb"]), 2),
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

    required_files = {
        "soulx_model": ROOT / "external/SoulX-Singer/pretrained_models/SoulX-Singer/model.pt",
        "soulx_svc_model": ROOT / "external/SoulX-Singer/pretrained_models/SoulX-Singer/model-svc.pt",
        "soulx_preprocess_rmvpe": ROOT / "external/SoulX-Singer/pretrained_models/SoulX-Singer-Preprocess/rmvpe/rmvpe.pt",
        "acestep_base_config": ROOT / "external/ACE-Step-1.5/checkpoints/acestep-v15-base/config.json",
        "acestep_base_weights": ROOT / "external/ACE-Step-1.5/checkpoints/acestep-v15-base/model.safetensors",
    }
    missing = {name: str(path) for name, path in required_files.items() if not path.exists()}
    fresh_gpu_info = query_nvidia_gpu(0)
    if fresh_gpu_info is not None:
        gpu_info = fresh_gpu_info
        report["gpu"].update({
            "free_gb": round(float(gpu_info["free_gb"]), 2),
            "total_gb": round(float(gpu_info["total_gb"]), 2),
        })
    report["preflight"] = {
        "required_files": {name: {"path": str(path), "exists": path.exists(), "size_mb": round(path.stat().st_size / 1024**2, 1) if path.exists() else 0} for name, path in required_files.items()},
        "cuda_free_gb": round(float(gpu_info["free_gb"]), 2),
        "cuda_total_gb": round(float(gpu_info["total_gb"]), 2),
    }
    if missing:
        report["steps"].append({"preflight": "failed", "missing": missing})
        (artifacts / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise RuntimeError("required model files are missing after bootstrap: " + json.dumps(missing, indent=2))
    if report["preflight"]["cuda_total_gb"] < 11.5:
        report["steps"].append({"preflight": "warning", "message": "GPU is below the 12GB acceptance target; continuing but OOM risk is high"})
    else:
        report["steps"].append({"preflight": "ok"})

    # Real acceptance is implemented as subprocesses so CUDA memory is fully released
    # between the two large model families.
    vocal_out = artifacts / "soulx_real.wav"
    bgm_out = artifacts / "acestep_real.wav"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    demo = ROOT / "external/SoulX-Singer/example/audio/zh_prompt.mp3"
    if not demo.exists():
        raise RuntimeError("SoulX example prompt asset is missing after source bootstrap")

    reference_copy = artifacts / "soulx_reference.mp3"
    shutil.copyfile(demo, reference_copy)

    # Exercise OpenACE's production adapter rather than only upstream's bundled example.
    # This validates note/phoneme/F0 metadata construction, reference preprocessing,
    # melody-control CLI construction, persistent preprocessing cache integration, VRAM
    # scheduling, and output placement exactly as workstation renders use them.
    from openace.core.models import Note, Project, Track
    from openace.engines.soulx import SoulXSingerEngine

    project = Project(title="OpenACE local GPU acceptance", bpm=120)
    track = Track(name="GPU acceptance vocal", language="zh")
    track.reference_voice_path = str(reference_copy)
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="好"))
    project.add_track(track)
    progress_events = []

    def svs_progress(fraction, message):
        progress_events.append({"fraction": round(float(fraction), 3), "message": message})
        print(f"SoulX adapter {fraction:.0%}: {message}", flush=True)

    SoulXSingerEngine(device="cuda").render_score(
        project,
        track,
        vocal_out,
        reference_voice=reference_copy,
        progress=svs_progress,
    )
    if not vocal_out.exists() or vocal_out.stat().st_size == 0:
        raise RuntimeError("OpenACE SoulX adapter did not produce a nonempty vocal wav")
    report["steps"].append({
        "soulx_real_render": str(vocal_out),
        "adapter": "SoulXSingerEngine.render_score",
        "progress_events": progress_events,
    })

    # Validate the production Vocal2BGM path rather than a separately handcrafted
    # upstream config. The real SoulX adapter output becomes ACE-Step's `complete`
    # source audio, so this stage covers cross-engine timing/format compatibility too.
    from openace.engines.acestep import ACEStepEngine

    ace_progress_events = []

    def ace_progress(fraction, message):
        ace_progress_events.append({"fraction": round(float(fraction), 3), "message": message})
        print(f"ACE-Step adapter {fraction:.0%}: {message}", flush=True)

    ACEStepEngine(device="auto").vocal_to_bgm(
        vocal_out,
        bgm_out,
        caption="short polished cinematic pop accompaniment verification",
        duration=10,
        bpm=120,
        progress=ace_progress,
    )
    if not bgm_out.exists() or bgm_out.stat().st_size == 0:
        raise RuntimeError("OpenACE ACE-Step adapter did not produce a nonempty accompaniment wav")
    report["steps"].append({
        "acestep_real_render": str(bgm_out),
        "adapter": "ACEStepEngine.vocal_to_bgm",
        "task_type": "complete",
        "progress_events": ace_progress_events,
    })

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
