import asyncio
import json
import os
import sys
from pathlib import Path

import pytest


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
            assert {"create_project", "add_note", "export_project"}.issubset(names)
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
