import json
import zipfile
from pathlib import Path

import mido
import pytest
import yaml

from openace.core.models import Note, Project, TempoPoint, Track
from openace.engines.soulx import build_soulx_target_metadata
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.exporters.svp import export_svp
from openace.exporters.ustx import export_ustx
from openace.exporters.vpr import export_vpr
from openace.importers.midi import import_midi


def tempo_project():
    project = Project(title="Tempo Map", bpm=120.0, ppq=480)
    project.tempo_map = [TempoPoint(ticks=0, bpm=120.0), TempoPoint(ticks=960, bpm=60.0)]
    track = Track(name="Lead")
    track.add_note(Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=960, duration_ticks=480, pitch=62, lyric="好"))
    project.add_track(track)
    return project


def test_piecewise_tempo_conversion_and_inverse_are_exact():
    project = tempo_project()
    assert project.ticks_to_seconds(960) == pytest.approx(1.0)
    assert project.ticks_to_seconds(1440) == pytest.approx(2.0)
    assert project.tick_duration_seconds(480, 960) == pytest.approx(1.5)
    assert project.seconds_to_ticks(2.0) == 1440
    assert project.seconds_to_ticks_float(1.5) == pytest.approx(1200.0)
    assert project.seconds_to_ticks_from(960, 0.5) == 240
    assert project.bpm_at(959) == pytest.approx(120.0)
    assert project.bpm_at(960) == pytest.approx(60.0)


def test_midi_tempo_map_roundtrip_and_lrc_times_follow_tempo_changes(tmp_path):
    project = tempo_project()
    midi_path = export_midi(project, tmp_path / "tempo.mid")
    merged_events = []
    absolute = 0
    for message in mido.merge_tracks(mido.MidiFile(str(midi_path)).tracks):
        absolute += message.time
        if message.type == "set_tempo":
            merged_events.append((absolute, round(mido.tempo2bpm(message.tempo), 6)))
    assert merged_events == [(0, 120.0), (960, 60.0)]

    imported = import_midi(midi_path)
    assert [(point.ticks, point.bpm) for point in imported.tempo_map] == [(0, 120.0), (960, 60.0)]
    assert imported.bpm == pytest.approx(120.0)
    assert [note.start_ticks for note in imported.tracks[0].notes] == [0, 960]

    lrc = export_lrc(project, tmp_path / "tempo.lrc").read_text(encoding="utf-8")
    assert "[00:00.00]你" in lrc
    assert "[00:01.00]好" in lrc


def test_soulx_metadata_uses_piecewise_tempo_note_timing():
    project = tempo_project()
    metadata = build_soulx_target_metadata(
        project,
        project.tracks[0],
        Path("external/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json"),
    )[0]
    durations = [float(value) for value in metadata["duration"].split()]
    # Each one-character note is one SoulX syllable token. At 120 BPM the first
    # two beats last 1s; after the 60 BPM tempo change the next beat also lasts 1s.
    assert durations[:2] == pytest.approx([1.0, 1.0], abs=0.001)


def test_tempo_maps_are_written_to_ustx_svp_and_vpr(tmp_path):
    project = tempo_project()
    ustx = yaml.safe_load(export_ustx(project, tmp_path / "tempo.ustx").read_text(encoding="utf-8"))
    assert [(item["position"], item["bpm"]) for item in ustx["tempos"]] == [(0, 120.0), (960, 60.0)]

    svp = json.loads(export_svp(project, tmp_path / "tempo.svp").read_text(encoding="utf-8"))
    assert [(item["position"], item["bpm"]) for item in svp["time"]["tempo"]] == [(0, 120.0), (1411200000, 60.0)]

    vpr_path = export_vpr(project, tmp_path / "tempo.vpr")
    with zipfile.ZipFile(vpr_path) as archive:
        sequence = json.loads(archive.read("Project/sequence.json"))
    assert [(item["posTick"], item["bpm"]) for item in sequence["masterTrack"]["tempo"]["events"]] == [(0, 12000), (960, 6000)]

def test_expression_automation_interpolates_in_musical_ticks_across_tempo_changes():
    import numpy as np
    from openace.core.expression import apply_dynamic_envelope
    from openace.core.models import EnvelopePoint

    project = tempo_project()
    track = project.tracks[0]
    track.automation.dynamic = [EnvelopePoint(ticks=0, value=0.5), EnvelopePoint(ticks=1440, value=1.0)]
    sr = 1000
    audio = np.ones((sr * 3, 1), dtype=np.float32) * 0.1
    processed, applied = apply_dynamic_envelope(audio, sr, project, track)
    assert applied
    # At 1s the tempo boundary tick is 960, two thirds of the musical-tick lane
    # from 0 to 1440. A wrong seconds-domain interpolation would produce halfway.
    tick_value = 0.5 + 0.5 * (960 / 1440)
    expected_gain = 10 ** (((tick_value - 0.5) * 12) / 20)
    assert float(processed[1000, 0]) == pytest.approx(0.1 * expected_gain, rel=0.01)


def test_clip_source_timing_is_anchored_across_tempo_changes():
    project = tempo_project()
    # A one-beat clip starting at the 60 BPM tempo boundary lasts one second;
    # a quarter-beat source offset immediately before it crosses the boundary lasts 0.125s at the prior 120 BPM tempo.
    assert project.tick_duration_seconds(960, 480) == pytest.approx(1.0)
    assert project.seconds_between_ticks(960 - 120, 960) == pytest.approx(0.125)
    # Durations fully before the change are also half as long in seconds.
    assert project.tick_duration_seconds(480, 480) == pytest.approx(0.5)
    assert project.seconds_between_ticks(480 - 120, 480) == pytest.approx(0.125)

def test_midi_import_uses_standard_default_tempo_before_first_late_tempo_event(tmp_path):
    path = tmp_path / "late_tempo.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60), time=960))
    tempo_track.append(mido.MetaMessage("end_of_track", time=0))
    note_track = mido.MidiTrack()
    note_track.append(mido.Message("note_on", note=60, velocity=64, time=0))
    note_track.append(mido.Message("note_off", note=60, velocity=0, time=480))
    note_track.append(mido.MetaMessage("end_of_track", time=0))
    midi.tracks.extend([tempo_track, note_track])
    midi.save(path)

    imported = import_midi(path)
    assert [(point.ticks, point.bpm) for point in imported.tempo_map] == [(0, 120.0), (960, 60.0)]
