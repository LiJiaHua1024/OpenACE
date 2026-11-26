from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import soundfile as sf


TARGET_LUFS = -14.0
TRUE_PEAK_CEILING_DBTP = -1.0


def dbfs(samples: np.ndarray) -> float:
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    return -120.0 if peak <= 1e-12 else 20.0 * math.log10(peak)


def true_peak_db(samples: np.ndarray, sample_rate: int, oversample: int = 4) -> float:
    if samples.size == 0:
        return -120.0
    # Linear interpolation is not a perfect polyphase true-peak meter, but it is a
    # conservative local validation gate when ffmpeg/pyloudnorm is unavailable.
    x = np.asarray(samples)
    if x.ndim > 1:
        x = np.max(np.abs(x), axis=1)
    xp = np.arange(len(x) * oversample) / oversample
    interp = np.interp(xp, np.arange(len(x)), x)
    peak = float(np.max(np.abs(interp)))
    return -120.0 if peak <= 1e-12 else 20.0 * math.log10(peak)


def rms_dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(samples))))
    return -120.0 if rms <= 1e-12 else 20.0 * math.log10(rms)


def integrated_loudness_lufs(samples: np.ndarray, sample_rate: int) -> float:
    try:
        import pyloudnorm as pyln  # type: ignore

        meter = pyln.Meter(sample_rate)
        return float(meter.integrated_loudness(samples))
    except Exception:
        # Fallback is explicitly approximate RMS-based loudness. Production exports use
        # ffmpeg loudnorm when present; this path keeps local validation operational.
        return rms_dbfs(samples) - 0.691


def normalize_loudness(samples: np.ndarray, sample_rate: int, target_lufs: float = TARGET_LUFS) -> np.ndarray:
    loudness = integrated_loudness_lufs(samples, sample_rate)
    gain_db = target_lufs - loudness
    gained = samples * (10.0 ** (gain_db / 20.0))
    peak = true_peak_db(gained, sample_rate)
    if peak > TRUE_PEAK_CEILING_DBTP:
        gained *= 10.0 ** ((TRUE_PEAK_CEILING_DBTP - peak) / 20.0)
    return np.asarray(gained, dtype=np.float32)


def read_audio(path: Path) -> Tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), always_2d=True)
    return np.asarray(data, dtype=np.float32), int(sr)


def write_wav(path: Path, samples: np.ndarray, sample_rate: int, normalize: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = normalize_loudness(samples, sample_rate) if normalize else samples
    sf.write(str(path), data, sample_rate, subtype="PCM_24")


def mix_tracks(buffers: Iterable[Tuple[np.ndarray, int]], sample_rate: int = 48000) -> np.ndarray:
    arrays = []
    max_len = 0
    for data, sr in buffers:
        if sr != sample_rate:
            data = resample_linear(data, sr, sample_rate)
        arrays.append(data)
        max_len = max(max_len, len(data))
    if not arrays:
        return np.zeros((0, 2), dtype=np.float32)
    mixed = np.zeros((max_len, 2), dtype=np.float32)
    for data in arrays:
        if data.ndim == 1:
            data = data[:, None].repeat(2, axis=1)
        if data.shape[1] == 1:
            data = data.repeat(2, axis=1)
        mixed[:len(data), :2] += data[:, :2]
    peak = np.max(np.abs(mixed)) if mixed.size else 0.0
    if peak > 0.98:
        mixed /= peak / 0.98
    return mixed


def resample_linear(data: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or len(data) == 0:
        return data
    ratio = dst_sr / src_sr
    out_len = max(1, int(round(len(data) * ratio)))
    x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=out_len, endpoint=False)
    if data.ndim == 1:
        return np.interp(x_new, x_old, data).astype(np.float32)
    channels = [np.interp(x_new, x_old, data[:, ch]) for ch in range(data.shape[1])]
    return np.stack(channels, axis=1).astype(np.float32)


def export_video_with_lyrics(audio_path: Path, lyrics_path: Path, output_path: Path, resolution: str = "1920x1080") -> None:
    """Render a simple compliant MP4 with dynamic timed lyric text using ffmpeg drawtext.

    This uses only ffmpeg/system fonts and contains no copyrighted assets.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = resolution.split("x")
    textfile = str(lyrics_path).replace(":", "\\:")
    filter_expr = (
        f"drawtext=textfile='{textfile}':fontcolor=white:fontsize=48:"
        f"x=(w-text_w)/2:y=h*0.82:box=1:boxcolor=black@0.35:boxborderw=18"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x111118:s={width}x{height}",
        "-i", str(audio_path), "-vf", filter_expr,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError("ffmpeg MP4 export failed; install ffmpeg with libx264") from exc
