import mido
import pytest

from openace.core.models import EnvelopePoint, Note, Project, Track, Vibrato
from openace.exporters.midi_lrc import export_midi
from openace.importers.midi import import_midi


def expressive_project():
    project = Project(title="pitchbend", bpm=120, ppq=480)
    track = Track(name="Lead")
    note = Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你")
    note.vibrato = Vibrato(start_ratio=0.0, depth_cents=40.0, frequency_hz=2.0, phase=0.0)
    track.add_note(note)
    track.automation.pitch_cents = [EnvelopePoint(ticks=0, value=0.0), EnvelopePoint(ticks=480, value=100.0), EnvelopePoint(ticks=960, value=0.0)]
    project.add_track(track)
    return project


def merged(path):
    absolute = 0
    output = []
    for message in mido.merge_tracks(mido.MidiFile(str(path)).tracks):
        absolute += message.time
        output.append((absolute, message))
    return output


def test_midi_export_writes_rpn_range_and_continuous_pitchwheel(tmp_path):
    path = export_midi(expressive_project(), tmp_path / "expressive.mid")
    events = merged(path)
    assert any(msg.type == "control_change" and msg.control == 6 and msg.value == 6 for _, msg in events)
    bends = [(tick, msg.pitch) for tick, msg in events if msg.type == "pitchwheel"]
    assert len(bends) > 12
    assert any(value > 1000 for _, value in bends)
    assert any(value < 0 for _, value in bends)
    assert max(value for _, value in bends) <= 8191
    assert min(value for _, value in bends) >= -8191
    # A center reset is written at the note boundary so downstream synthesis does not
    # leave the channel permanently detuned.
    assert any(tick == 960 and value == 0 for tick, value in bends)


def test_midi_pitchbend_roundtrip_becomes_pitch_automation(tmp_path):
    path = export_midi(expressive_project(), tmp_path / "roundtrip.mid")
    imported = import_midi(path)
    points = imported.tracks[0].automation.pitch_cents
    assert len(points) > 10
    assert max(point.value for point in points) > 80
    assert min(point.value for point in points) < 0
    near_mid = min(points, key=lambda point: abs(point.ticks - 480))
    assert near_mid.value == pytest.approx(100.0, abs=35.0)
    assert points[-1].value == pytest.approx(0.0, abs=2.0)


def test_plain_midi_export_has_no_spurious_pitch_automation(tmp_path):
    project = Project(title="plain", bpm=120)
    track = Track(name="Plain")
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="la"))
    project.add_track(track)
    path = export_midi(project, tmp_path / "plain.mid")
    assert not [msg for _, msg in merged(path) if msg.type == "pitchwheel"]
    assert import_midi(path).tracks[0].automation.pitch_cents == []
