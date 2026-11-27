from fastapi.testclient import TestClient

from openace.core.models import Note, Project
from openace.importers.audio import assign_lyrics_to_notes
import openace.importers.audio as audio_importer
import openace.server.app as app_module


def test_asr_words_align_to_temporally_overlapping_notes():
    project = Project(bpm=120)
    notes = [
        Note(start_ticks=0, duration_ticks=480, pitch=60),
        Note(start_ticks=480, duration_ticks=480, pitch=62),
        Note(start_ticks=960, duration_ticks=480, pitch=64),
    ]
    words = [
        {"text": "你", "start": 0.03, "end": 0.32},
        {"text": "好", "start": 0.54, "end": 0.91},
        {"text": "远", "start": 5.0, "end": 5.4},
    ]
    assigned = assign_lyrics_to_notes(notes, words, project, "zh")
    assert assigned == 2
    assert [note.lyric for note in notes] == ["你", "好", ""]


def test_asr_words_join_english_with_spaces_and_near_onset_tolerance():
    project = Project(bpm=120)
    notes = [Note(start_ticks=0, duration_ticks=960, pitch=60)]
    words = [
        {"text": "hello", "start": -0.05, "end": 0.12},
        {"text": "world", "start": 0.25, "end": 0.65},
    ]
    assigned = assign_lyrics_to_notes(notes, words, project, "en")
    assert assigned == 2
    assert notes[0].lyric == "hello world"


def test_audio_import_endpoint_assigns_real_asr_words(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audio_importer,
        "audio_to_midi_notes",
        lambda path, project: [Note(start_ticks=0, duration_ticks=480, pitch=60)],
    )
    monkeypatch.setattr(
        audio_importer,
        "transcribe_lyric_words",
        lambda path: ([{"text": "你", "start": 0.02, "end": 0.35}], "zh"),
    )
    source = tmp_path / "vocal.wav"
    source.write_bytes(b"not-a-real-decode-target")
    client = TestClient(app_module.app)
    with source.open("rb") as handle:
        response = client.post("/api/import/audio", files={"file": ("vocal.wav", handle, "audio/wav")})
    assert response.status_code == 200
    track = response.json()["tracks"][0]
    assert track["language"] == "zh"
    assert track["notes"][0]["lyric"] == "你"


def test_audio_import_fails_loudly_when_asr_cannot_align(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audio_importer,
        "audio_to_midi_notes",
        lambda path, project: [Note(start_ticks=0, duration_ticks=480, pitch=60)],
    )
    monkeypatch.setattr(
        audio_importer,
        "transcribe_lyric_words",
        lambda path: ([{"text": "unrelated", "start": 8.0, "end": 8.4}], "en"),
    )
    source = tmp_path / "vocal.wav"
    source.write_bytes(b"not-a-real-decode-target")
    client = TestClient(app_module.app)
    with source.open("rb") as handle:
        response = client.post("/api/import/audio", files={"file": ("vocal.wav", handle, "audio/wav")})
    assert response.status_code == 422
    assert "could not be aligned" in response.json()["detail"]


def test_shared_audio_project_builder_matches_server_semantics(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audio_importer,
        "audio_to_midi_notes",
        lambda path, project: [Note(start_ticks=0, duration_ticks=480, pitch=60)],
    )
    monkeypatch.setattr(
        audio_importer,
        "transcribe_lyric_words",
        lambda path: ([{"text": "hello", "start": 0.02, "end": 0.35}], "en"),
    )
    project = audio_importer.project_from_audio(tmp_path / "take.wav", "Agent import")
    assert project.title == "Agent import"
    assert project.tracks[0].language == "en"
    assert project.tracks[0].notes[0].lyric == "hello"
