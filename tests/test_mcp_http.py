import asyncio
import os
import subprocess
import sys
import time

import pytest


@pytest.mark.asyncio
async def test_mcp_streamable_http_lists_tools(tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(tmp_path)
    env["OPENACE_CI_SYNTH_FIXTURE"] = "1"
    port = 8798
    proc = subprocess.Popen(
        [sys.executable, "-m", "openace.mcp_server", "--transport", "streamable-http", "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 8
        last_error = None
        while time.time() < deadline:
            try:
                async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        assert "render_vocal" in {tool.name for tool in tools.tools}
                        return
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(0.2)
        raise AssertionError(f"MCP streamable HTTP did not become ready: {last_error}")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
