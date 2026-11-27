import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

from openace.cli import json_payload
from openace.core.project_store import ProjectStore


def run_cli(tmp_path, *args):
    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(tmp_path)
    env["OPENACE_CI_SYNTH_FIXTURE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "openace.cli", *args],
        cwd=os.getcwd(),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_cli_agent_editing_commands_roundtrip(tmp_path):
    project = run_cli(tmp_path, "create-project", "--title", "CLI edit")
    track_id = project["tracks"][0]["id"]
    notes = run_cli(
        tmp_path,
        "batch-add-notes",
        project["id"],
        track_id,
        json.dumps([
            {"start_ticks": 0, "duration_ticks": 480, "pitch": 60, "lyric": "你"},
            {"start_ticks": 480, "duration_ticks": 480, "pitch": 62, "lyric": "好"},
        ]),
    )
    assert len(notes) == 2
    updated = run_cli(tmp_path, "update-note", project["id"], track_id, notes[1]["id"], json.dumps({"pitch": 64}))
    assert updated["pitch"] == 64
    lane = run_cli(tmp_path, "set-expression", project["id"], track_id, "dynamic", json.dumps([{"ticks": 0, "value": 0.5}]))
    assert lane[0]["value"] == 0.5
    breath = run_cli(tmp_path, "upsert-breath", project["id"], track_id, json.dumps({"start_ticks": 960, "duration_ticks": 120, "intensity": 1.5, "timbre": "soft"}))
    assert breath["timbre"] == "soft"

    media = tmp_path / "cli_clip.wav"
    sf.write(media, np.zeros(2400, dtype=np.float32), 24000)
    clip = run_cli(tmp_path, "upsert-clip", project["id"], track_id, json.dumps({"path": str(media), "start_ticks": 0, "duration_ticks": 480}))
    assert clip["path"] == str(media)
    tempo = run_cli(tmp_path, "set-tempo", project["id"], "--bpm", "130", "--points-json", json.dumps([{"ticks": 960, "bpm": 65}]))
    assert tempo["bpm"] == 130
    voice = run_cli(tmp_path, "assign-voice", project["id"], track_id, "voice_cli", "--reference-voice", str(media))
    assert voice["reference_voice_path"] == str(media)

    stored = ProjectStore(tmp_path / "projects").get(project["id"])
    stored_track = stored.track(track_id)
    assert stored_track.notes[1].pitch == 64
    assert stored_track.automation.dynamic[0].value == 0.5
    assert stored_track.breaths[0].intensity == 1.5
    assert stored_track.clips[0].label == ""
    assert stored.tempo_map[0].bpm == 65
    assert stored_track.voice_id == "voice_cli"


def test_long_inline_json_is_not_mistaken_for_a_path():
    raw = json.dumps([{"ticks": index * 480, "value": 0.5} for index in range(500)])
    assert len(raw) > 4096
    payload = json_payload(raw)
    assert len(payload) == 500 and payload[-1]["ticks"] == 499 * 480


def test_cli_project_duplicate_and_delete_roundtrip(tmp_path):
    project = run_cli(tmp_path, "create-project", "--title", "Project ops")
    duplicate = run_cli(tmp_path, "duplicate-project", project["id"], "--title", "Project ops copy")
    assert duplicate["id"] != project["id"]
    assert duplicate["title"] == "Project ops copy"
    deleted = run_cli(tmp_path, "delete-project", duplicate["id"])
    assert deleted["deleted"] is True
    store = ProjectStore(tmp_path / "projects")
    assert not store.path_for(duplicate["id"]).exists()
    assert store.path_for(project["id"]).exists()


def test_cli_project_organization_and_duplicate_unpinned(tmp_path):
    project = run_cli(tmp_path, "create-project", "--title", "Organize CLI")
    organized = run_cli(tmp_path, "organize-project", project["id"], "--pinned", "true", "--tags", "lead, lead, draft", "--folders", "songs, songs, demos")
    assert organized["metadata"]["pinned"] is True
    assert organized["metadata"]["tags"] == ["lead", "draft"]
    assert organized["metadata"]["folders"] == ["songs", "demos"]
    listing = ProjectStore(tmp_path / "projects").list()
    assert listing[0]["id"] == project["id"]
    assert listing[0]["pinned"] is True
    assert listing[0]["tags"] == ["lead", "draft"]
    assert listing[0]["folders"] == ["songs", "demos"]
    duplicate = run_cli(tmp_path, "duplicate-project", project["id"])
    assert duplicate["metadata"]["tags"] == ["lead", "draft"]
    assert duplicate["metadata"]["folders"] == ["songs", "demos"]
    assert duplicate["metadata"]["pinned"] is False


def test_cli_split_note_outputs_continuation(tmp_path):
    project = run_cli(tmp_path, "create-project", "--title", "CLI split")
    track_id = project["tracks"][0]["id"]
    notes = run_cli(tmp_path, "batch-add-notes", project["id"], track_id, '[{"start_ticks":0,"duration_ticks":480,"pitch":60,"lyric":"你"}]')
    payload = run_cli(tmp_path, "split-note", project["id"], track_id, notes[0]["id"], "240")
    assert payload["first"]["duration_ticks"] == 240
    assert payload["second"]["start_ticks"] == 240
    assert payload["second"]["lyric"] == "-"
    assert "continuation" in payload["second"]["techniques"]


def test_cli_ripple_delete_range_persists_cross_track_edit(tmp_path):
    project = run_cli(tmp_path, "create-project", "--title", "CLI ripple")
    track_id = project["tracks"][0]["id"]
    run_cli(tmp_path, "batch-add-notes", project["id"], track_id, json.dumps([
        {"start_ticks": 0, "duration_ticks": 960, "pitch": 60, "lyric": "你"},
        {"start_ticks": 1440, "duration_ticks": 480, "pitch": 62, "lyric": "好"},
    ]))
    media = tmp_path / "ripple_clip.wav"
    sf.write(media, np.zeros(24000, dtype=np.float32), 24000)
    run_cli(tmp_path, "upsert-clip", project["id"], track_id, json.dumps({"path": str(media), "start_ticks": 0, "duration_ticks": 1920, "offset_ticks": 0}))

    result = run_cli(tmp_path, "ripple-delete-range", project["id"], "480", "960")
    assert result["ripple_ticks"] == 480
    stored = ProjectStore(tmp_path / "projects").get(project["id"])
    track = stored.track(track_id)
    assert [(note.start_ticks, note.duration_ticks, note.lyric) for note in track.notes] == [(0, 480, "你"), (960, 480, "好")]
    assert [(clip.start_ticks, clip.duration_ticks, clip.offset_ticks) for clip in track.clips] == [(0, 480, 0), (480, 960, 960)]
