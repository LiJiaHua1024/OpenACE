from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from openace.core.models import Note, RenderMode, Track
from openace.core.phonemes import ensure_note_phonemes
from openace.core.pitch import transpose_notes_preserve_intervals
from openace.core.project_store import ProjectStore
from openace.core.timing import validate_absolute_beat_anchor
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.exporters.svp import export_svp
from openace.exporters.ustx import export_ustx
from openace.exporters.vpr import export_vpr
from openace.server.render_service import RenderService

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("OPENACE_DATA_DIR", ROOT / "data"))
store = ProjectStore(DATA / "projects")
render_service = RenderService(store, DATA / "renders")


def notify_web(project) -> None:
    """Best-effort loopback SSE notification for an already-open workstation."""
    try:
        import urllib.request

        body = json.dumps(project.model_dump(mode="json")).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8787/api/internal/project-updated",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=0.25).read()
    except Exception:
        pass


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def create_project(title: str = "Untitled OpenACE Project") -> str:
    return dumps(store.create(title).model_dump(mode="json"))


def list_projects() -> str:
    return dumps(store.list())


def get_project(project_id: str) -> str:
    return dumps(store.get(project_id).model_dump(mode="json"))


def add_track(project_id: str, name: str, language: str = "zh") -> str:
    project = store.get(project_id)
    track = project.add_track(Track(name=name, language=language))
    store.save(project)
    notify_web(project)
    return dumps(track.model_dump(mode="json"))


def add_note(project_id: str, track_id: str, start_ticks: int, duration_ticks: int, pitch: int, lyric: str, velocity: int = 90) -> str:
    project = store.get(project_id)
    track = project.track(track_id)
    note = track.add_note(Note(start_ticks=start_ticks, duration_ticks=duration_ticks, pitch=pitch, lyric=lyric, velocity=velocity))
    ensure_note_phonemes(note, track.language, project.ticks_to_seconds(note.duration_ticks) * 1000.0)
    validate_absolute_beat_anchor(track.notes, project.ppq, project.bpm)
    store.save(project)
    notify_web(project)
    return dumps(note.model_dump(mode="json"))


def transpose_track(project_id: str, track_id: str, semitones: int) -> str:
    project = store.get(project_id)
    track = project.track(track_id)
    mapping = transpose_notes_preserve_intervals(track.notes, semitones)
    lookup = dict(mapping)
    for note in track.notes:
        note.pitch = lookup[note.id]
    store.save(project)
    notify_web(project)
    return dumps({"updated": len(mapping), "intervals": "preserved"})


async def render_vocal(project_id: str, track_id: str) -> str:
    job = render_service.create_job(project_id, RenderMode.SVS_SCORE, track_id)
    result = await render_service.run_vocal_render(job.id)
    return dumps(result.model_dump(mode="json"))


async def vocal2bgm(project_id: str, source_audio: str, caption: str = "professional instrumental accompaniment") -> str:
    job = render_service.create_job(project_id, RenderMode.VOCAL2BGM)
    result = await render_service.run_music_generation(job.id, source_audio, caption)
    return dumps(result.model_dump(mode="json"))


async def repaint(project_id: str, source_audio: str, start_s: float, end_s: float, caption: str = "") -> str:
    job = render_service.create_job(project_id, RenderMode.REPAINT)
    result = await render_service.run_music_generation(job.id, source_audio, caption, start_s, end_s)
    return dumps(result.model_dump(mode="json"))


async def svc_convert(project_id: str, source_audio: str, reference_voice: str) -> str:
    job = render_service.create_job(project_id, RenderMode.SVC)
    result = await render_service.run_svc(job.id, source_audio, reference_voice)
    return dumps(result.model_dump(mode="json"))


def export_project(project_id: str, fmt: str, output_path: str) -> str:
    project = store.get(project_id)
    output = Path(output_path)
    exporters = {"mid": export_midi, "lrc": export_lrc, "ustx": export_ustx, "svp": export_svp, "vpr": export_vpr}
    if fmt not in exporters:
        raise ValueError(f"unsupported format: {fmt}")
    exporters[fmt](project, output)
    return dumps({"output": str(output), "bytes": output.stat().st_size})


def build_mcp_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("install the `mcp` Python package to run openace-mcp") from exc

    mcp = FastMCP("OpenACE")
    mcp.tool()(create_project)
    mcp.tool()(list_projects)
    mcp.tool()(get_project)
    mcp.tool()(add_track)
    mcp.tool()(add_note)
    mcp.tool()(transpose_track)
    mcp.tool()(render_vocal)
    mcp.tool()(vocal2bgm)
    mcp.tool()(repaint)
    mcp.tool()(svc_convert)
    mcp.tool()(export_project)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="openace-mcp")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    mcp = build_mcp_server()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # FastMCP's streamable HTTP transport is keyless/local by design; bind localhost
        # unless the operator explicitly changes host through their own network policy.
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
