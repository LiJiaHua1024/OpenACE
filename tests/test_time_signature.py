import json
import zipfile

import mido
import pytest
import yaml
from pydantic import ValidationError

from openace.core.models import Project, TimeSignature
from openace.exporters.midi_lrc import export_midi
from openace.exporters.svp import export_svp
from openace.exporters.ustx import export_ustx
from openace.exporters.vpr import export_vpr


def test_time_signature_schema_rejects_invalid_denominator_and_range():
    with pytest.raises(ValidationError):
        TimeSignature(numerator=6, denominator=5)
    with pytest.raises(ValidationError):
        TimeSignature(numerator=0, denominator=4)
    assert TimeSignature(numerator=6, denominator=8).denominator == 8


def test_time_signature_serializes_to_all_project_formats(tmp_path):
    project = Project(title="Meter", time_signature=TimeSignature(numerator=6, denominator=8))

    midi_path = export_midi(project, tmp_path / "meter.mid")
    meta = [msg for track in mido.MidiFile(midi_path).tracks for msg in track if msg.type == "time_signature"]
    assert meta and meta[0].numerator == 6 and meta[0].denominator == 8

    ustx = yaml.safe_load(export_ustx(project, tmp_path / "meter.ustx").read_text(encoding="utf-8"))
    assert ustx["time_signatures"][0]["beat_per_bar"] == 6
    assert ustx["time_signatures"][0]["beat_unit"] == 8

    svp = json.loads(export_svp(project, tmp_path / "meter.svp").read_text(encoding="utf-8"))
    assert svp["time"]["meter"][0]["numerator"] == 6
    assert svp["time"]["meter"][0]["denominator"] == 8

    with zipfile.ZipFile(export_vpr(project, tmp_path / "meter.vpr")) as archive:
        vpr = json.loads(archive.read("Project/sequence.json").decode("utf-8"))
    event = vpr["masterTrack"]["timeSig"]["events"][0]
    assert event["numerator"] == 6 and event["denominator"] == 8
