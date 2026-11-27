import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

import openace.mcp_server as mcp_server
from openace.core.project_store import ProjectStore


def make_media(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.zeros(2400, dtype=np.float32), 24000)
    return path


def test_mcp_media_list_place_and_safe_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "DATA", tmp_path)
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(mcp_server, "store", store)
    media = make_media(tmp_path / "uploads" / "clip_test_agent.wav")
    listing = json.loads(mcp_server.list_media_files())
    assert listing[0]["file_name"] == media.name
    assert listing[0]["duration_seconds"] == 0.1

    project = store.create("MCP media")
    placed = json.loads(mcp_server.place_media(project.id, media.name, start_ticks=480))
    assert placed["clip"]["start_ticks"] == 480
    assert placed["track"]["type"] == "audio"
    try:
        mcp_server.delete_media(media.name)
        raise AssertionError("in-use delete should fail")
    except ValueError as exc:
        assert "used by arrangement clips" in str(exc)
    store.delete(project.id)
    deleted = json.loads(mcp_server.delete_media(media.name))
    assert deleted["deleted"] is True
    assert not media.exists()


def test_cli_media_list_place_and_delete(tmp_path):
    media = make_media(tmp_path / "uploads" / "clip_cli_media.wav")
    env = dict(os.environ, OPENACE_DATA_DIR=str(tmp_path), OPENACE_CI_SYNTH_FIXTURE="1")
    cmd = [sys.executable, "-m", "openace.cli"]
    listing = subprocess.run(cmd + ["list-media"], cwd="/home/ubuntu/repos/OpenACE", env=env, text=True, capture_output=True)
    assert listing.returncode == 0, listing.stderr
    assert json.loads(listing.stdout)[0]["file_name"] == media.name

    create = subprocess.run(cmd + ["create-project", "--title", "CLI media"], cwd="/home/ubuntu/repos/OpenACE", env=env, text=True, capture_output=True)
    assert create.returncode == 0, create.stderr
    project_id = json.loads(create.stdout)["id"]
    placed = subprocess.run(cmd + ["place-media-clip", project_id, media.name, "--start-ticks", "480"], cwd="/home/ubuntu/repos/OpenACE", env=env, text=True, capture_output=True)
    assert placed.returncode == 0, placed.stderr
    assert json.loads(placed.stdout)["clip"]["start_ticks"] == 480

    blocked = subprocess.run(cmd + ["delete-media", media.name], cwd="/home/ubuntu/repos/OpenACE", env=env, text=True, capture_output=True)
    assert blocked.returncode != 0
    subprocess.run(cmd + ["delete-project", project_id], cwd="/home/ubuntu/repos/OpenACE", env=env, text=True, capture_output=True)
    deleted = subprocess.run(cmd + ["delete-media", media.name], cwd="/home/ubuntu/repos/OpenACE", env=env, text=True, capture_output=True)
    assert deleted.returncode == 0, deleted.stderr
    assert json.loads(deleted.stdout)["ok"] is True


def test_mcp_ripple_delete_range_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "DATA", tmp_path)
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(mcp_server, "store", store)
    project = store.create("MCP ripple")
    track = project.tracks[0]
    from openace.core.models import Note
    track.add_note(Note(start_ticks=0, duration_ticks=960, pitch=60, lyric="你"))
    track.add_note(Note(start_ticks=1440, duration_ticks=480, pitch=62, lyric="好"))
    store.save(project)

    result = json.loads(mcp_server.ripple_delete_range(project.id, 480, 960))
    assert result["removed"]["notes"] >= 1
    stored = store.get(project.id)
    assert [(note.start_ticks, note.duration_ticks) for note in stored.tracks[0].notes] == [(0, 480), (960, 480)]
    try:
        mcp_server.ripple_delete_range(project.id, 960, 480)
        raise AssertionError("invalid range should fail")
    except ValueError as exc:
        assert "start_ticks" in str(exc)
