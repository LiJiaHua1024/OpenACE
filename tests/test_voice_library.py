import io
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from openace.core.voice_library import VoiceLibrary


def wav_bytes(seconds=0.5, sr=24000):
    buffer = io.BytesIO()
    t = np.arange(int(seconds * sr)) / sr
    sf.write(buffer, 0.1 * np.sin(2 * np.pi * 220 * t), sr, format="WAV", subtype="PCM_16")
    buffer.seek(0)
    return buffer


def test_voice_library_create_list_rename_delete_persists(tmp_path):
    library = VoiceLibrary(tmp_path / "voices")
    voice = library.create("My Singer!.wav", wav_bytes())
    assert voice.duration_seconds == pytest.approx(0.5, rel=0.02)
    assert voice.sample_rate == 24000
    assert voice.channels == 1
    assert voice.size_bytes > 1000
    assert "My_Singer_" in voice.path or "My_Singer" in voice.path

    reloaded = VoiceLibrary(tmp_path / "voices")
    assert [item.id for item in reloaded.list()] == [voice.id]
    renamed = reloaded.rename(voice.id, "Lead reference")
    assert renamed.name == "Lead reference"
    assert VoiceLibrary(tmp_path / "voices").get(voice.id).name == "Lead reference"

    deleted = reloaded.delete(voice.id)
    assert deleted.id == voice.id
    assert reloaded.list() == []
    assert not (tmp_path / "voices" / (voice.id + "_My_Singer_.wav")).exists()


def test_voice_library_rejects_non_audio_and_too_short_files(tmp_path):
    library = VoiceLibrary(tmp_path / "voices")
    with pytest.raises(ValueError, match="unsupported"):
        library.create("notes.txt", io.BytesIO(b"not audio"))
    with pytest.raises(ValueError, match="readable audio"):
        library.create("broken.wav", io.BytesIO(b"not audio"))
    with pytest.raises(ValueError, match="too short"):
        library.create("tiny.wav", wav_bytes(seconds=0.01))
    assert library.list() == []
    assert list((tmp_path / "voices").glob("*.wav")) == []


def test_voice_library_quality_metrics_and_warnings_are_truthful(tmp_path):
    library = VoiceLibrary(tmp_path / "voices")
    clean = library.create("clean.wav", wav_bytes(seconds=3.0))
    assert clean.peak_level == pytest.approx(0.1, abs=0.01)
    assert clean.clipping_ratio == 0
    assert clean.silence_ratio < 0.05
    assert clean.voiced_seconds == pytest.approx(3.0, abs=0.05)
    assert clean.quality_warnings == []

    clipped_buffer = io.BytesIO()
    t = np.arange(24000 * 3) / 24000
    sf.write(clipped_buffer, np.sign(np.sin(2 * np.pi * 220 * t)), 24000, format="WAV", subtype="PCM_16")
    clipped_buffer.seek(0)
    clipped = library.create("clipped.wav", clipped_buffer)
    assert clipped.peak_level >= 0.999
    assert clipped.clipping_ratio > 0.001
    assert any("clipped" in warning for warning in clipped.quality_warnings)

    short = library.create("short.wav", wav_bytes(seconds=0.5))
    assert any("shorter than 2s" in warning for warning in short.quality_warnings)


def test_voice_library_trimmed_copy_preserves_source_and_reanalyzes(tmp_path):
    library = VoiceLibrary(tmp_path / "voices")
    source = library.create("source.wav", wav_bytes(seconds=3.0))
    trimmed = library.create_trimmed_copy(source.id, 1.0, 2.5)
    assert trimmed.id != source.id
    assert trimmed.source_voice_id == source.id
    assert trimmed.trim_start_seconds == pytest.approx(1.0)
    assert trimmed.trim_end_seconds == pytest.approx(2.5)
    assert trimmed.duration_seconds == pytest.approx(1.5, abs=0.02)
    assert trimmed.sample_rate == source.sample_rate
    assert trimmed.channels == source.channels
    assert Path(trimmed.path).exists() and Path(source.path).exists()
    data, sr = sf.read(trimmed.path)
    assert sr == source.sample_rate
    assert len(data) == pytest.approx(1.5 * source.sample_rate, abs=2)
    assert [item.id for item in library.list()][:2] == [trimmed.id, source.id]


def test_voice_library_trim_rejects_invalid_ranges(tmp_path):
    library = VoiceLibrary(tmp_path / "voices")
    source = library.create("source.wav", wav_bytes(seconds=1.0))
    for start, end in [(-0.1, 0.5), (0.5, 0.5), (0.9, 1.2)]:
        with pytest.raises(ValueError):
            library.create_trimmed_copy(source.id, start, end)
    assert len(library.list()) == 1
