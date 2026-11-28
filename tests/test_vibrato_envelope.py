import pytest
import yaml

from openace.core.editing import split_note
from openace.core.models import Note, Project, Track, Vibrato
from openace.core.pitch import vibrato_envelope
from openace.exporters.ustx import export_ustx
from openace.importers.ustx import import_ustx


def test_vibrato_attack_release_envelope_shape():
    note = Note(
        start_ticks=0,
        duration_ticks=480,
        pitch=60,
        vibrato=Vibrato(start_ratio=0.5, depth_cents=40, frequency_hz=5, attack_ratio=0.5, release_ratio=0.5),
    )
    duration_ms = 1000.0
    assert vibrato_envelope(note, 499, duration_ms) == 0
    assert vibrato_envelope(note, 500, duration_ms) == 0
    assert vibrato_envelope(note, 625, duration_ms) == pytest.approx(0.5)
    assert vibrato_envelope(note, 750, duration_ms) == pytest.approx(1.0)
    assert vibrato_envelope(note, 875, duration_ms) == pytest.approx(0.5)
    assert vibrato_envelope(note, 1000, duration_ms) == 0


def test_vibrato_envelope_roundtrips_ustx_in_out(tmp_path):
    project = Project(name="Envelope", bpm=120)
    track = project.add_track(Track(name="Lead", type="vocal"))
    track.add_note(Note(
        start_ticks=0,
        duration_ticks=480,
        pitch=60,
        lyric="你",
        vibrato=Vibrato(start_ratio=0.25, depth_cents=40, frequency_hz=4, attack_ratio=0.2, release_ratio=0.3),
    ))
    path = export_ustx(project, tmp_path / "env.ustx")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    vibrato = raw["voice_parts"][0]["notes"][0]["vibrato"]
    assert vibrato["in"] == pytest.approx(20.0)
    assert vibrato["out"] == pytest.approx(30.0)

    imported = import_ustx(path, "imported")
    imported_vibrato = imported.tracks[0].notes[0].vibrato
    assert imported_vibrato is not None
    assert imported_vibrato.attack_ratio == pytest.approx(0.2)
    assert imported_vibrato.release_ratio == pytest.approx(0.3)


def test_split_rejects_envelope_vibrato_instead_of_breaking_continuity():
    project = Project(bpm=120)
    track = project.add_track(Track(name="Lead"))
    note = track.add_note(Note(
        start_ticks=0,
        duration_ticks=480,
        pitch=60,
        lyric="你",
        vibrato=Vibrato(start_ratio=0.2, attack_ratio=0.2),
    ))
    with pytest.raises(ValueError, match="attack/release"):
        split_note(project, track.id, note.id, 240)
