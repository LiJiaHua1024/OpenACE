from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np

from .models import Note, Project
from .pitch import correct_octave_errors, hz_to_midi, pitch_curve_for_notes


def extract_f0(path: Path, frame_ms: float = 10.0) -> Tuple[np.ndarray, np.ndarray]:
    """Extract F0 with librosa/pyin when available.

    0Hz/unvoiced frames are represented as NaN, never as zero, so downstream smoothing
    cannot be polluted by silence.
    """
    try:
        import librosa  # type: ignore

        y, sr = librosa.load(str(path), sr=None, mono=True)
        hop = max(1, int(sr * frame_ms / 1000.0))
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("F2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            frame_length=2048,
            hop_length=hop,
        )
        f0 = np.asarray(f0, dtype=np.float64)
        f0[~np.asarray(voiced_flag, dtype=bool)] = np.nan
        f0 = correct_octave_errors(f0)
        times = np.arange(len(f0)) * frame_ms / 1000.0
        return times, f0
    except Exception as exc:
        raise RuntimeError("F0 extraction requires the optional audio dependency librosa") from exc


def beat_offsets_ms(project: Project, notes: Sequence[Note], actual_onsets_s: Optional[Sequence[float]] = None) -> np.ndarray:
    """Return per-note onset deviations in milliseconds.

    If measured onsets are unavailable, the expected deviation is zero because symbolic
    beat anchoring has already been enforced. This function never fabricates errors.
    """
    expected = np.array([project.ticks_to_seconds(note.start_ticks) for note in notes], dtype=float)
    if actual_onsets_s is None:
        return np.zeros(len(notes))
    actual = np.asarray(actual_onsets_s, dtype=float)
    if len(actual) != len(expected):
        raise ValueError("actual onset count does not match note count")
    return (actual - expected) * 1000.0


def spectral_mask_heatmap(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Compute a compact time/frequency occupancy heatmap for diagnostics."""
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    frame = 2048
    hop = 512
    if len(audio) < frame:
        audio = np.pad(audio, (0, frame - len(audio)))
    windows = []
    for start in range(0, max(1, len(audio) - frame + 1), hop):
        chunk = audio[start:start + frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        windows.append(np.abs(np.fft.rfft(chunk * np.hanning(frame))))
    spec = np.asarray(windows).T
    bins = 64
    grouped = spec[: (spec.shape[0] // bins) * bins].reshape(bins, -1, spec.shape[1]).mean(axis=1)
    db = 20 * np.log10(grouped + 1e-8)
    return db


def write_diagnostic(
    output_path: Path,
    project: Project,
    notes: Sequence[Note],
    rendered_audio: Optional[np.ndarray] = None,
    sample_rate: int = 48000,
    actual_f0_hz: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    provenance: str = "OpenACE render",
    pitch_automation=None,
) -> Path:
    """Write the acoustic X-ray diagnostic PNG required by every render."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path.parent.mkdir(parents=True, exist_ok=True)
    times, target_f0 = pitch_curve_for_notes(project.ppq, project.bpm, notes, pitch_automation=pitch_automation)
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), constrained_layout=True)
    fig.patch.set_facecolor("#111217")
    for ax in axes:
        ax.set_facecolor("#171923")
        ax.grid(color="#3a3f52", alpha=0.35, linewidth=0.6)
        ax.tick_params(colors="#c9d1e3")
        for spine in ax.spines.values():
            spine.set_color("#454b62")

    ax = axes[0]
    ax.plot(times, target_f0, color="#79b8ff", linewidth=1.8, label="target F0")
    if actual_f0_hz is not None:
        actual_times, actual_values = actual_f0_hz
        actual_values = np.asarray(actual_values, dtype=float).copy()
        actual_values[actual_values <= 0] = np.nan
        valid = np.isfinite(actual_values)
        if valid.any():
            actual = np.full_like(times, np.nan, dtype=float)
            valid_times = times[(times >= actual_times[valid][0]) & (times <= actual_times[valid][-1])]
            actual[(times >= actual_times[valid][0]) & (times <= actual_times[valid][-1])] = np.interp(
                valid_times, actual_times[valid], actual_values[valid]
            )
            ax.plot(times, actual, color="#ff7b72", linewidth=1.1, alpha=0.85, label="rendered F0")
    ax.set_ylabel("Hz", color="#c9d1e3")
    ax.set_title("Target pitch vs rendered F0", color="white")
    ax.legend(facecolor="#171923", labelcolor="white")

    ax = axes[1]
    offsets = beat_offsets_ms(project, notes)
    x = [project.ticks_to_seconds(n.start_ticks) for n in notes]
    ax.stem(x, offsets, linefmt="#f2cc60", markerfmt="o", basefmt=" ")
    ax.axhline(0, color="#79b8ff", linewidth=0.8)
    ax.set_ylabel("ms", color="#c9d1e3")
    ax.set_title("Per-note beat offset (vowel onset anchor)", color="white")

    ax = axes[2]
    if rendered_audio is not None and len(rendered_audio):
        heat = spectral_mask_heatmap(rendered_audio, sample_rate)
        im = ax.imshow(heat, origin="lower", aspect="auto", cmap="magma")
        fig.colorbar(im, ax=ax, label="dB")
    else:
        ax.text(0.5, 0.5, "No rendered audio supplied", transform=ax.transAxes, ha="center", color="white")
    ax.set_title("Spectral occupancy / masking heatmap", color="white")
    ax.set_xlabel("frame", color="#c9d1e3")
    ax.set_ylabel("frequency band", color="#c9d1e3")

    fig.text(0.995, 0.005, provenance, ha="right", va="bottom", color="#ffb86b" if "FIXTURE" in provenance else "#8ea0c9", fontsize=9)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path
