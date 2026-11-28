from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .models import Note, Project
from .pitch import correct_octave_errors, midi_to_hz, hz_to_midi, pitch_curve_for_notes


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

    If measured onsets are unavailable, deviations are NaN. Returning zero here would
    fabricate perfect rendered-audio timing evidence that was never measured.
    """
    expected = np.array([project.ticks_to_seconds(note.start_ticks) for note in notes], dtype=float)
    if actual_onsets_s is None:
        return np.full(len(notes), np.nan)
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
    actual_onsets_s: Optional[Sequence[float]] = None,
) -> Path:
    """Write the acoustic X-ray diagnostic PNG required by every render."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path.parent.mkdir(parents=True, exist_ok=True)
    times, target_f0 = pitch_curve_for_notes(project, notes, pitch_automation=pitch_automation)
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
    offsets = beat_offsets_ms(project, notes, actual_onsets_s)
    x = np.array([project.ticks_to_seconds(n.start_ticks) for n in notes], dtype=float)
    measured = np.isfinite(offsets)
    if len(x):
        ax.vlines(x, 0, 1, color="#46506e", linewidth=0.8, alpha=0.55, label="symbolic vowel anchor")
        if measured.any():
            ax.stem(x[measured], offsets[measured], linefmt="#f2cc60", markerfmt="o", basefmt=" ")
            ax.axhline(0, color="#79b8ff", linewidth=0.8)
        if not measured.all():
            ax.text(
                0.5,
                0.82,
                "Rendered onset measurement unavailable; zero error is not fabricated",
                transform=ax.transAxes,
                ha="center",
                color="#ffb86b",
                fontsize=9,
            )
    else:
        ax.text(0.5, 0.5, "No vocal notes in project", transform=ax.transAxes, ha="center", color="#8ea0c9")
    ax.set_ylabel("ms", color="#c9d1e3")
    ax.set_title("Vowel-anchor timing: measured offsets plus symbolic positions", color="white")

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


def sustained_voiced_onsets(times: np.ndarray, f0: np.ndarray, min_frames: int = 3) -> List[float]:
    """Return start times of contiguous voiced regions without treating isolated noise as onsets."""
    starts: List[float] = []
    finite = np.isfinite(f0)
    index = 0
    while index < len(f0):
        if not finite[index]:
            index += 1
            continue
        start = index
        while index < len(f0) and finite[index]:
            index += 1
        if index - start >= min_frames:
            starts.append(float(times[start]))
    return starts


def measured_pitch_transition(times: np.ndarray, f0: np.ndarray, boundary_s: float, low_hz: float, high_hz: float) -> Optional[float]:
    """Estimate a low-to-high pitch transition time requiring three sustained frames."""
    threshold = float(np.sqrt(low_hz * high_hz))
    finite = np.isfinite(f0)
    for index in range(len(f0) - 2):
        if times[index] < boundary_s - 0.12 or times[index] > boundary_s + 0.2:
            continue
        window = f0[index:index + 3]
        if np.all(np.isfinite(window)) and np.all(window >= threshold):
            return float(times[index])
    return None


def vocal_alignment_measurements(path: Path, project: Project, notes: Sequence[Note]) -> dict:
    """Measure rendered SVS onset/pitch-transition alignment without fabricating precision."""
    if len(notes) < 2:
        raise ValueError("at least two notes are required for transition alignment measurement")
    times, f0 = extract_f0(path)
    onsets = sustained_voiced_onsets(times, f0)
    ordered = sorted(notes, key=lambda note: note.start_ticks)
    first, second = ordered[0], ordered[1]
    boundary_s = project.ticks_to_seconds(second.start_ticks)
    low_hz = midi_to_hz(first.pitch)
    high_hz = midi_to_hz(second.pitch)
    transition = measured_pitch_transition(times, f0, boundary_s, low_hz, high_hz) if high_hz > low_hz else None
    first_onset = onsets[0] if onsets else None
    return {
        "method": "librosa/pyin sustained-voiced onset and geometric-mean pitch crossing; frame-level estimate, not sample-exact proof",
        "first_voiced_onset_s": first_onset,
        "expected_first_onset_s": project.ticks_to_seconds(first.start_ticks),
        "first_onset_error_ms": None if first_onset is None else round((first_onset - project.ticks_to_seconds(first.start_ticks)) * 1000.0, 1),
        "pitch_transition_s": transition,
        "expected_transition_s": boundary_s,
        "transition_error_ms": None if transition is None else round((transition - boundary_s) * 1000.0, 1),
        "voiced_region_count": len(onsets),
    }
