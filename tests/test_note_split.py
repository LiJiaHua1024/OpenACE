import math
import pytest

from openace.core.editing import split_note
from openace.core.models import Note, PitchPoint, Project, Track, Vibrato


def test_split_note_preserves_vowel_phonemes_pitch_and_vibrato_phase():
    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    note = track.add_note(Note(
        start_ticks=0,
        duration_ticks=480,
        pitch=60,
        lyric="你",
        pitch_curve=[PitchPoint(offset_ms=100, cents=10), PitchPoint(offset_ms=300, cents=30)],
        vibrato=Vibrato(start_ratio=0.2, depth_cents=30, frequency_hz=5, phase=0.5),
    ))

    first, second = split_note(project, track.id, note.id, 240)

    assert (first.duration_ticks, second.start_ticks, second.duration_ticks) == (240, 240, 240)
    assert first.lyric == "你"
    assert second.lyric == "-"
    assert "continuation" in second.techniques
    assert [item.symbol for item in first.phonemes] == ["n", "i"]
    assert first.phonemes[-1].start_ms == 0
    assert first.phonemes[-1].duration_ms == pytest.approx(250)
    assert [item.symbol for item in second.phonemes] == ["i"]
    assert second.phonemes[0].start_ms == 0
    assert second.phonemes[0].duration_ms == pytest.approx(250)
    assert [(round(p.offset_ms), p.cents) for p in first.pitch_curve] == [(100, 10), (250, 25)]
    assert [(round(p.offset_ms), p.cents) for p in second.pitch_curve] == [(0, 25), (50, 30)]
    assert first.vibrato is not None
    assert first.vibrato.start_ratio == pytest.approx(0.4)
    assert second.vibrato is not None
    assert second.vibrato.start_ratio == 0
    assert second.vibrato.phase == pytest.approx(0.5 + math.tau * 5 * 0.15)
    assert [item.id for item in track.notes] == [first.id, second.id]
    assert first.id == note.id
    assert second.id != note.id


def test_split_note_rejects_consonant_tail_instead_of_faking_vowel():
    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead", language="en"))
    note = track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="cat"))
    # At 120 BPM this position lands in the final /t/ tail rather than the sustained /ae/ vowel.
    tail_start_ticks = 470
    with pytest.raises(ValueError, match="sustained vowel"):
        split_note(project, track.id, note.id, tail_start_ticks)


def test_split_note_rejects_outside_positions():
    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    note = track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你"))
    with pytest.raises(ValueError, match="inside"):
        split_note(project, track.id, note.id, 0)
    with pytest.raises(ValueError, match="inside"):
        split_note(project, track.id, note.id, 480)


def test_split_note_endpoint_persists_and_reports_invalid_tail(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import openace.server.app as app_module
    from openace.core.project_store import ProjectStore

    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    project = store.create("Endpoint split")
    track = project.tracks[0]
    track.language = "en"
    note = track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="cat"))
    store.save(project)
    client = TestClient(app_module.app)

    response = client.post(f"/api/projects/{project.id}/tracks/{track.id}/notes/{note.id}/split", json={"split_ticks": 240})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["first"]["duration_ticks"] == 240
    assert payload["second"]["lyric"] == "-"
    assert "continuation" in payload["second"]["techniques"]
    stored = store.get(project.id)
    assert len(stored.tracks[0].notes) == 2

    response = client.post(f"/api/projects/{project.id}/tracks/{track.id}/notes/{payload['second']['id']}/split", json={"split_ticks": 470})
    assert response.status_code == 422
    assert "sustained vowel" in response.text
