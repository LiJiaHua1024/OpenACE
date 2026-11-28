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
    assert second.vibrato.phase == pytest.approx(0.5 + math.tau * 5 * 0.25)
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


def test_merge_notes_preserves_lyrics_phonemes_and_pitch_steps():
    from openace.core.editing import merge_notes

    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    first = track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你", pitch_curve=[PitchPoint(offset_ms=250, cents=20)]))
    second = track.add_note(Note(start_ticks=480, duration_ticks=480, pitch=62, lyric="好", pitch_curve=[PitchPoint(offset_ms=100, cents=10)]))

    merged = merge_notes(project, track.id, [second.id, first.id])

    assert merged.id == first.id
    assert (merged.start_ticks, merged.duration_ticks, merged.pitch) == (0, 960, 60)
    assert merged.lyric == "你好"
    assert len(track.notes) == 1
    assert [phoneme.symbol for phoneme in merged.phonemes] == ["n", "i", "x", "au"]
    starts = [phoneme.start_ms for phoneme in merged.phonemes]
    assert starts == sorted(starts)
    for left, right in zip(merged.phonemes, merged.phonemes[1:]):
        assert left.start_ms + left.duration_ms == pytest.approx(right.start_ms)
    curve = [(round(point.offset_ms, 2), round(point.cents, 2)) for point in merged.pitch_curve]
    assert (250.0, 20.0) in curve
    assert (500.0, 210.0) in curve
    assert (600.0, 210.0) in curve
    assert curve[-1] == (1000.0, 210.0)
    pre_boundary = [item for item in curve if item[0] < 500]
    assert pre_boundary[-1][1] == 20.0


def test_merge_notes_rejects_gaps_velocity_and_vibrato_truthfully():
    from openace.core.editing import merge_notes

    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    a = track.add_note(Note(start_ticks=0, duration_ticks=240, pitch=60, lyric="你"))
    b = track.add_note(Note(start_ticks=480, duration_ticks=240, pitch=60, lyric="好"))
    with pytest.raises(ValueError, match="contiguous"):
        merge_notes(project, track.id, [a.id, b.id])

    track.notes.clear()
    a = track.add_note(Note(start_ticks=0, duration_ticks=240, pitch=60, velocity=80))
    b = track.add_note(Note(start_ticks=240, duration_ticks=240, pitch=60, velocity=90))
    with pytest.raises(ValueError, match="velocities"):
        merge_notes(project, track.id, [a.id, b.id])

    track.notes.clear()
    a = track.add_note(Note(start_ticks=0, duration_ticks=240, pitch=60, vibrato=Vibrato()))
    b = track.add_note(Note(start_ticks=240, duration_ticks=240, pitch=60))
    with pytest.raises(ValueError, match="vibrato"):
        merge_notes(project, track.id, [a.id, b.id])


def test_merge_split_continuation_roundtrip_preserves_vowel_timing():
    from openace.core.editing import merge_notes

    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    original = track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你", pitch_curve=[PitchPoint(offset_ms=100, cents=10), PitchPoint(offset_ms=300, cents=30)]))
    first, second = split_note(project, track.id, original.id, 240)

    merged = merge_notes(project, track.id, [first.id, second.id])

    assert merged.lyric == "你"
    assert merged.duration_ticks == 480
    assert [phoneme.symbol for phoneme in merged.phonemes] == ["n", "i"]
    assert merged.phonemes[-1].duration_ms == pytest.approx(500)
    assert [(round(point.offset_ms), round(point.cents)) for point in merged.pitch_curve] == [(0, 10), (100, 10), (250, 25), (300, 30), (500, 30)]


def test_merge_notes_rejects_custom_phoneme_override_instead_of_losing_it():
    from openace.core.editing import merge_notes
    from openace.core.models import Phoneme

    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    a = track.add_note(Note(start_ticks=0, duration_ticks=240, pitch=60, lyric="你", phonemes=[Phoneme(symbol="m", start_ms=-45, duration_ms=45), Phoneme(symbol="i", start_ms=0, duration_ms=300, is_vowel=True)]))
    b = track.add_note(Note(start_ticks=240, duration_ticks=240, pitch=60, lyric="好"))
    with pytest.raises(ValueError, match="custom phoneme"):
        merge_notes(project, track.id, [a.id, b.id])


def test_merge_notes_endpoint_persists_and_validates(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import openace.server.app as app_module
    from openace.core.project_store import ProjectStore

    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    project = store.create("merge endpoint")
    track = project.tracks[0]
    a = track.add_note(Note(start_ticks=0, duration_ticks=240, pitch=60, lyric="你"))
    b = track.add_note(Note(start_ticks=240, duration_ticks=240, pitch=62, lyric="好"))
    store.save(project)
    client = TestClient(app_module.app)

    response = client.post(f"/api/projects/{project.id}/tracks/{track.id}/notes/merge", json={"note_ids": [b.id, a.id]})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["duration_ticks"] == 480
    assert payload["lyric"] == "你好"
    persisted = store.get(project.id)
    assert len(persisted.tracks[0].notes) == 1

    response = client.post(f"/api/projects/{project.id}/tracks/{track.id}/notes/merge", json={"note_ids": [payload["id"], payload["id"]]})
    assert response.status_code == 422
    assert "Duplicate" in response.text or "duplicate" in response.text


def test_merge_split_continuation_reconstructs_continuous_vibrato():
    from openace.core.editing import merge_notes

    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    original = track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="你", vibrato=Vibrato(start_ratio=0.2, depth_cents=30, frequency_hz=5, phase=0.5)))
    first, second = split_note(project, track.id, original.id, 240)

    merged = merge_notes(project, track.id, [first.id, second.id])

    assert merged.vibrato is not None
    assert merged.vibrato.start_ratio == pytest.approx(0.2)
    assert merged.vibrato.depth_cents == pytest.approx(30)
    assert merged.vibrato.frequency_hz == pytest.approx(5)
    assert merged.vibrato.phase == pytest.approx(0.5)


def test_merge_split_continuation_reconstructs_nonzero_phase_vibrato():
    from openace.core.editing import merge_notes

    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    original = track.add_note(Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="啊", vibrato=Vibrato(start_ratio=0.25, depth_cents=42, frequency_hz=6.1, phase=0.35)))
    first, second = split_note(project, track.id, original.id, 480)

    merged = merge_notes(project, track.id, [first.id, second.id])

    assert merged.vibrato is not None
    assert merged.vibrato.start_ratio == pytest.approx(0.25)
    assert merged.vibrato.depth_cents == pytest.approx(42)
    assert merged.vibrato.frequency_hz == pytest.approx(6.1)
    assert merged.vibrato.phase == pytest.approx(0.35)
