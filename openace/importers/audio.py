from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np

from openace.core.models import Note, Project, Track
from openace.core.pitch import correct_octave_errors, hz_to_midi, sanitize_f0


def audio_to_midi_notes(audio_path: Path, project: Optional[Project] = None, frame_ms: float = 10.0) -> List[Note]:
    """Real audio-to-MIDI monophonic transcription using librosa pyin.

    0Hz/unvoiced frames are masked, octave artifacts are corrected, and note boundaries
    are quantized to the project grid rather than accumulating drift.
    """
    try:
        import librosa  # type: ignore
    except ImportError as exc:
        raise RuntimeError("audio-to-MIDI requires optional dependency librosa") from exc
    project = project or Project()
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    hop = max(1, int(sr * frame_ms / 1000.0))
    f0, voiced, _ = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("F2"),
        fmax=librosa.note_to_hz("C6"),
        sr=sr,
        frame_length=2048,
        hop_length=hop,
    )
    f0 = np.asarray(f0, dtype=float)
    f0[~np.asarray(voiced, dtype=bool)] = np.nan
    f0 = correct_octave_errors(f0)
    midi = np.full(len(f0), np.nan)
    finite = np.isfinite(f0)
    midi[finite] = [hz_to_midi(x) for x in f0[finite]]
    rounded = np.round(midi).astype(float)
    notes: List[Note] = []
    start = None
    current = None
    min_frames = max(2, int(round(60 / frame_ms)))
    for i, value in enumerate(rounded):
        if not np.isfinite(value):
            value = np.nan
        pitch = int(value) if np.isfinite(value) else None
        if pitch != current:
            if current is not None and start is not None and i - start >= min_frames:
                s = project.seconds_to_ticks(start * frame_ms / 1000.0)
                e = project.seconds_to_ticks(i * frame_ms / 1000.0)
                notes.append(Note(start_ticks=s, duration_ticks=max(1, e - s), pitch=current, lyric=""))
            start = i if pitch is not None else None
            current = pitch
    if current is not None and start is not None and len(rounded) - start >= min_frames:
        s = project.seconds_to_ticks(start * frame_ms / 1000.0)
        e = project.seconds_to_ticks(len(rounded) * frame_ms / 1000.0)
        notes.append(Note(start_ticks=s, duration_ticks=max(1, e - s), pitch=current, lyric=""))
    return notes


def transcribe_lyrics(audio_path: Path, language: str = "zh") -> str:
    """Transcribe real lyrics with faster-whisper; never returns placeholder syllables."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("lyric transcription requires optional dependency faster-whisper") from exc
    model = WhisperModel("small", device="auto")
    segments, _ = model.transcribe(str(audio_path), language=None if language == "auto" else language)
    text = "".join(segment.text for segment in segments).strip()
    if not text:
        raise RuntimeError("ASR produced no lyrics; refusing placeholder substitution")
    return text
