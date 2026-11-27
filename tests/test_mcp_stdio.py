import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
import soundfile as sf
import numpy as np


@pytest.mark.asyncio
async def test_mcp_stdio_create_project_and_add_note(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(tmp_path)
    env["OPENACE_CI_SYNTH_FIXTURE"] = "1"
    params = StdioServerParameters(command=sys.executable, args=["-m", "openace.mcp_server", "--transport", "stdio"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {"create_project", "add_note", "export_project", "import_audio_project", "duplicate_project", "delete_project"}.issubset(names)
            created = await session.call_tool("create_project", {"title": "MCP Smoke"})
            project = json.loads(created.content[0].text)
            track_id = project["tracks"][0]["id"]
            note = await session.call_tool(
                "add_note",
                {
                    "project_id": project["id"],
                    "track_id": track_id,
                    "start_ticks": 0,
                    "duration_ticks": 480,
                    "pitch": 60,
                    "lyric": "你",
                },
            )
            payload = json.loads(note.content[0].text)
            assert payload["phonemes"][0]["start_ms"] < 0
            assert payload["phonemes"][1]["start_ms"] == 0

            batch = await session.call_tool(
                "batch_add_notes",
                {
                    "project_id": project["id"],
                    "track_id": track_id,
                    "notes": [{"start_ticks": 480, "duration_ticks": 480, "pitch": 62, "lyric": "好"}],
                },
            )
            batch_notes = json.loads(batch.content[0].text)
            assert len(batch_notes) == 1
            updated = await session.call_tool(
                "update_note",
                {"project_id": project["id"], "track_id": track_id, "note_id": batch_notes[0]["id"], "patch": {"pitch": 64}},
            )
            assert json.loads(updated.content[0].text)["pitch"] == 64
            lane = await session.call_tool(
                "set_expression_lane",
                {"project_id": project["id"], "track_id": track_id, "lane": "dynamic", "points": [{"ticks": 0, "value": 0.5}, {"ticks": 960, "value": 1.0}]},
            )
            assert len(json.loads(lane.content[0].text)) == 2
            breath = await session.call_tool(
                "upsert_breath",
                {"project_id": project["id"], "track_id": track_id, "breath": {"start_ticks": 960, "duration_ticks": 120, "intensity": 1.4, "timbre": "strong"}},
            )
            breath_payload = json.loads(breath.content[0].text)
            assert breath_payload["intensity"] == 1.4

            media = tmp_path / "agent_clip.wav"
            sf.write(media, np.zeros(2400, dtype=np.float32), 24000)
            clip = await session.call_tool(
                "upsert_audio_clip",
                {"project_id": project["id"], "track_id": track_id, "clip": {"path": str(media), "start_ticks": 0, "duration_ticks": 480, "label": "agent take"}},
            )
            assert json.loads(clip.content[0].text)["label"] == "agent take"
            tempo = await session.call_tool(
                "set_tempo_map",
                {"project_id": project["id"], "bpm": 130, "points": [{"ticks": 960, "bpm": 65}]},
            )
            assert json.loads(tempo.content[0].text)["tempo_map"][0]["bpm"] == 65
            voice = await session.call_tool(
                "assign_voice",
                {"project_id": project["id"], "track_id": track_id, "voice_id": "voice_test", "reference_voice_path": str(media)},
            )
            assert json.loads(voice.content[0].text)["reference_voice_path"] == str(media)
            fetched = await session.call_tool("get_project", {"project_id": project["id"]})
            fetched_project = json.loads(fetched.content[0].text)
            fetched_track = fetched_project["tracks"][0]
            assert fetched_track["automation"]["dynamic"][1]["value"] == 1.0
            assert fetched_track["breaths"][0]["timbre"] == "strong"
            assert fetched_track["clips"][0]["path"] == str(media)
            assert fetched_project["bpm"] == 130
            assert fetched_project["tempo_map"][0]["ticks"] == 960
            duplicate = await session.call_tool("duplicate_project", {"project_id": project["id"], "title": "MCP Smoke Copy"})
            duplicate_project = json.loads(duplicate.content[0].text)
            assert duplicate_project["id"] != project["id"]
            assert duplicate_project["title"] == "MCP Smoke Copy"
            deleted = await session.call_tool("delete_project", {"project_id": duplicate_project["id"]})
            assert json.loads(deleted.content[0].text)["deleted"] is True
