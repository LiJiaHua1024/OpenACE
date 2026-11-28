import json
from types import SimpleNamespace

import pytest

from openace.core import editing
from openace.core.project_store import ProjectStore


def test_update_duplicate_reorder_delete_track_semantics(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create("tracks")
    track = project.tracks[0]

    updated = editing.update_track(project, track.id, {"name": "Lead", "color": "#1122aa", "volume": 0.65, "pan": -0.25, "mute": True, "midi_channel": 2, "midi_program": 40})
    assert updated.name == "Lead"
    assert updated.volume == 0.65
    assert updated.pan == -0.25
    assert updated.midi_channel == 2

    with pytest.raises(ValueError, match="volume"):
        editing.update_track(project, track.id, {"volume": 1.2, "name": "bad"})
    assert project.track(track.id).name == "Lead"
    assert project.track(track.id).volume == 0.65
    with pytest.raises(ValueError, match="midi_channel"):
        editing.update_track(project, track.id, {"midi_channel": 16})

    second = editing.duplicate_track(project, track.id, "Harmony")
    assert second.id != track.id
    assert project.tracks.index(second) == 1
    assert second.render_path is None and second.render_fingerprint is None
    reordered = editing.reorder_track(project, second.id, 0)
    assert project.tracks[0].id == reordered.id
    assert editing.delete_track(project, second.id) is True
    assert [item.id for item in project.tracks] == [track.id]


def test_cli_and_mcp_track_atoms_share_persistent_state(tmp_path, monkeypatch):
    import openace.cli as cli
    import openace.mcp_server as mcp

    store = ProjectStore(tmp_path / "projects")
    project = store.create("agent tracks")
    track = project.tracks[0]
    monkeypatch.setattr(cli, "services", lambda: (store, None))
    monkeypatch.setattr(mcp, "store", store)

    cli.cmd_update_track(SimpleNamespace(project=project.id, track=track.id, patch_json=json.dumps({"name": "CLI lead", "solo": True, "pan": 0.4})))
    assert store.get(project.id).tracks[0].name == "CLI lead"

    duplicate_payload = json.loads(mcp.duplicate_track(project.id, track.id, "MCP harmony"))
    assert duplicate_payload["id"] != track.id
    assert store.get(project.id).tracks[1].name == "MCP harmony"

    order_payload = json.loads(mcp.reorder_track(project.id, duplicate_payload["id"], 0))
    assert order_payload["order"][0] == duplicate_payload["id"]

    cli.cmd_delete_track(SimpleNamespace(project=project.id, track=duplicate_payload["id"]))
    assert len(store.get(project.id).tracks) == 1
    with pytest.raises(ValueError, match="unsupported track patch"):
        json.loads(mcp.update_track(project.id, track.id, {"type": "audio"}))
