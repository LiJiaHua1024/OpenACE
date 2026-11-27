from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


@lru_cache(maxsize=4)
def _whisper_model(model_name: str, device: str, compute_type: str):
    """Load and cache the local faster-whisper model."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("lyric transcription requires optional dependency faster-whisper") from exc
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_lyric_words(audio_path: Path, language: str = "auto") -> Tuple[List[Dict[str, float | str]], str]:
    """Transcribe lyrics with local faster-whisper word timestamps.

    The returned words are evidence from the uploaded vocal itself. No lyric is invented
    or replaced with a placeholder when recognition fails.
    """
    model_name = os.environ.get("OPENACE_WHISPER_MODEL", "small")
    device = os.environ.get("OPENACE_WHISPER_DEVICE", "auto")
    compute_type = os.environ.get("OPENACE_WHISPER_COMPUTE_TYPE", "default")
    model = _whisper_model(model_name, device, compute_type)
    segments, info = model.transcribe(
        str(audio_path),
        language=None if language == "auto" else language,
        word_timestamps=True,
    )
    words: List[Dict[str, float | str]] = []
    for segment in list(segments):
        for word in segment.words or []:
            text = str(word.word).strip()
            if not text or word.start is None or word.end is None or word.end <= word.start:
                continue
            words.append({"text": text, "start": float(word.start), "end": float(word.end)})
    if not words:
        raise RuntimeError("ASR produced no timestamped lyrics; refusing placeholder substitution")
    return words, str(getattr(info, "language", language) or language)


def _joined_lyric(tokens: List[str], language: str) -> str:
    if language in {"zh", "yue", "ja"}:
        return "".join(token.strip() for token in tokens)
    return " ".join(token.strip() for token in tokens if token.strip())


def assign_lyrics_to_notes(notes: List[Note], words: List[Dict[str, float | str]], project: Project, language: str) -> int:
    """Assign each ASR word once to the note with maximum temporal overlap.

    Stable pitch onset/offset often misses the exact vocal onset by a small amount, so a
    non-overlapping word may attach to the nearest note within 300ms. Words outside that
    tolerance remain unassigned rather than being forced onto the wrong melody.
    """
    if not notes or not words:
        return 0
    assignments: List[List[str]] = [[] for _ in notes]
    note_times = []
    for note in notes:
        start = project.ticks_to_seconds(note.start_ticks)
        end = project.ticks_to_seconds(note.start_ticks + note.duration_ticks)
        note_times.append((start, end))
    assigned = 0
    for word in sorted(words, key=lambda item: float(item["start"])):
        word_start = float(word["start"])
        word_end = float(word["end"])
        overlaps = [max(0.0, min(end, word_end) - max(start, word_start)) for start, end in note_times]
        index = max(range(len(notes)), key=lambda i: overlaps[i])
        if overlaps[index] <= 0.0:
            center = (word_start + word_end) / 2.0
            distances = [
                0.0 if start <= center <= end else min(abs(center - start), abs(center - end))
                for start, end in note_times
            ]
            nearest = min(range(len(notes)), key=lambda i: distances[i])
            if distances[nearest] <= 0.3:
                index = nearest
            else:
                continue
        assignments[index].append(str(word["text"]))
        assigned += 1
    for note, tokens in zip(notes, assignments):
        note.lyric = _joined_lyric(tokens, language)
    return assigned


def transcribe_lyrics(audio_path: Path, language: str = "auto") -> str:
    """Transcribe real lyrics with faster-whisper; never returns placeholder syllables."""
    words, detected_language = transcribe_lyric_words(audio_path, language)
    return _joined_lyric([str(word["text"]) for word in words], detected_language)

def project_from_audio(audio_path: Path, title: Optional[str] = None) -> Project:
    """Build a vocal project from real monophonic audio and local ASR evidence.

    Both pitch transcription and lyric alignment must succeed. Missing or unaligned
    lyrics remain blank only at the note level when some words align; total alignment
    failure is loud rather than substituted with placeholders.
    """
    project = Project(title=title or audio_path.stem or "Imported Audio")
    track = project.add_track(Track(name="Imported Vocal", color="#7c5cff"))
    track.notes = audio_to_midi_notes(audio_path, project)
    track.notes.sort(key=lambda note: (note.start_ticks, note.pitch))
    if not track.notes:
        raise RuntimeError("no stable monophonic pitch contour found; refusing fabricated notes")
    words, detected_language = transcribe_lyric_words(audio_path)
    assigned = assign_lyrics_to_notes(track.notes, words, project, detected_language)
    if not assigned:
        raise RuntimeError("ASR lyrics could not be aligned to the transcribed melody; refusing fabricated lyric placement")
    track.language = detected_language
    return project
