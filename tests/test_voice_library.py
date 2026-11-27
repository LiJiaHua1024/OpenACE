import io

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
