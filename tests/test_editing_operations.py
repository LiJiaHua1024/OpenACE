import numpy as np
import pytest
import soundfile as sf

from openace.core import editing
from openace.core.models import Project, Track


def project_with_track():
    project = Project()
    track = project.add_track(Track(name="Lead"))
    return project, track


def test_batch_note_update_delete_and_validation():
    project, track = project_with_track()
    added = editing.add_notes(project, track.id, [
        {"start_ticks": 0, "duration_ticks": 480, "pitch": 60, "lyric": "你"},
        {"start_ticks": 480, "duration_ticks": 480, "pitch": 62, "lyric": "好"},
    ])
    assert len(added) == 2
    assert added[0].phonemes[1].start_ms == 0
    updated = editing.update_note(project, track.id, added[1].id, {"pitch": 64, "lyric": "好"})
    assert updated.pitch == 64
    assert editing.delete_note(project, track.id, added[0].id) is True
    assert [note.id for note in track.notes] == [added[1].id]

    with pytest.raises(Exception):
        editing.add_notes(project, track.id, [{"start_ticks": 960, "duration_ticks": 0, "pitch": 60, "lyric": "你"}])


def test_automation_breath_tempo_and_voice_validation(tmp_path):
    project, track = project_with_track()
    points = editing.set_automation_lane(project, track.id, "dynamic", [{"ticks": 480, "value": 0.8}, {"ticks": 0, "value": 0.5}])
    assert [point.ticks for point in points] == [0, 480]
    with pytest.raises(ValueError, match="normalized"):
        editing.set_automation_lane(project, track.id, "dynamic", [{"ticks": 0, "value": 1.2}])
    with pytest.raises(ValueError, match="±100"):
        editing.set_automation_lane(project, track.id, "pitch_cents", [{"ticks": 0, "value": 101}])

    breath = editing.upsert_breath(project, track.id, {"start_ticks": 480, "duration_ticks": 120, "intensity": 1.4, "timbre": "strong"})
    updated = editing.upsert_breath(project, track.id, {"intensity": 0.6, "timbre": "soft"}, breath.id)
    assert updated.intensity == 0.6 and updated.timbre == "soft"
    assert editing.delete_breath(project, track.id, breath.id) is True

    tempo_map = editing.set_tempo_map(project, 130.0, [{"ticks": 960, "bpm": 65}, {"ticks": 0, "bpm": 130}, {"ticks": 960, "bpm": 70}])
    assert project.bpm == 130
    assert len(tempo_map) == 1
    assert tempo_map[0].ticks == 960
    assert tempo_map[0].bpm == 70
    assert editing.set_tempo_map(project, None, []) == []
    assert project.tempo_map == []

    reference = tmp_path / "voice.wav"
    sf.write(reference, np.zeros(2400, dtype=np.float32), 24000)
    result = editing.assign_voice(project, track.id, "voice_x", str(reference))
    assert result["reference_voice_path"] == str(reference)
    with pytest.raises(ValueError, match="does not exist"):
        editing.assign_voice(project, track.id, "voice_bad", str(tmp_path / "missing.wav"))


def test_audio_clip_upsert_requires_real_file_and_preserves_edits(tmp_path):
    project, track = project_with_track()
    media = tmp_path / "clip.wav"
    sf.write(media, np.zeros(2400, dtype=np.float32), 24000)
    with pytest.raises(ValueError, match="does not exist"):
        editing.upsert_audio_clip(project, track.id, {"path": str(tmp_path / "missing.wav")})
    clip = editing.upsert_audio_clip(project, track.id, {"path": str(media), "start_ticks": 480, "duration_ticks": 480, "label": "take"})
    updated = editing.upsert_audio_clip(project, track.id, {"start_ticks": 960, "gain_db": -3}, clip.id)
    assert updated.start_ticks == 960
    assert updated.duration_ticks == 480
    assert updated.label == "take"
    assert updated.gain_db == -3
    assert editing.delete_audio_clip(project, track.id, clip.id) is True
