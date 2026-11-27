from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import List, Optional

from openace.core import editing
from openace.core.models import Note, RenderMode, Track, new_id
from openace.core.phonemes import ensure_note_phonemes
from openace.core.pitch import transpose_notes_preserve_intervals
from openace.core.media_library import delete_media_file, list_media, place_media_clip
from openace.core.project_store import ProjectStore, normalize_project_folders, normalize_project_tags
from openace.core.timing import validate_absolute_beat_anchor
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.importers.audio import project_from_audio
from openace.importers.midi import import_midi
from openace.exporters.svp import export_svp
from openace.exporters.master import export_compressed_master, export_master_wav, export_stems_zip
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


def notify_project_deleted(project_id: str) -> None:
    try:
        import urllib.request

        body = json.dumps({"project_id": project_id}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8787/api/internal/project-deleted",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=0.25).read()
    except Exception:
        pass


def notify_media(media: dict, action: str) -> None:
    try:
        import urllib.request
        body = json.dumps({"action": action, "media": media}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8787/api/internal/media-updated", data=body, headers={"Content-Type": "application/json"}, method="POST")
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


def duplicate_project(project_id: str, title: Optional[str] = None) -> str:
    source = store.get(project_id)
    duplicate = type(source).model_validate(source.model_dump())
    duplicate.id = new_id("project")
    duplicate.title = title or f"{source.title} Copy"
    duplicate.metadata = dict(source.metadata or {})
    duplicate.metadata["pinned"] = False
    store.save(duplicate)
    notify_web(duplicate)
    return dumps(duplicate.model_dump(mode="json"))


def organize_project(project_id: str, pinned: Optional[bool] = None, tags: Optional[List[str]] = None, folders: Optional[List[str]] = None) -> str:
    project = store.get(project_id)
    metadata = dict(project.metadata or {})
    if pinned is not None:
        metadata["pinned"] = bool(pinned)
    if tags is not None:
        metadata["tags"] = normalize_project_tags(tags)
    if folders is not None:
        metadata["folders"] = normalize_project_folders(folders)
    project.metadata = metadata
    project.save(store.path_for(project.id))
    notify_web(project)
    return dumps(project.model_dump(mode="json"))


def delete_project(project_id: str) -> str:
    if not store.delete(project_id):
        raise KeyError(f"project not found: {project_id}")
    notify_project_deleted(project_id)
    return dumps({"deleted": True, "project_id": project_id})


def list_media_files() -> str:
    return dumps(list_media(DATA / "uploads"))


def place_media(project_id: str, media_name: str, start_ticks: int = 0, track_id: Optional[str] = None) -> str:
    project = store.get(project_id)
    track, clip = place_media_clip(store, project, DATA / "uploads", media_name, start_ticks, track_id)
    notify_web(project)
    return dumps({"track": track.model_dump(mode="json"), "clip": clip.model_dump(mode="json")})


def delete_media(media_name: str) -> str:
    entry = delete_media_file(store, DATA / "uploads", media_name)
    notify_media(entry, "deleted")
    return dumps({"deleted": True, "media": entry})


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
    ensure_note_phonemes(note, track.language, project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0)
    validate_absolute_beat_anchor(track.notes, project.ppq, project.bpm, project=project)
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
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


async def vocal2bgm(project_id: str, source_audio: str, caption: str = "professional instrumental accompaniment") -> str:
    job = render_service.create_job(project_id, RenderMode.VOCAL2BGM, source_audio=source_audio, caption=caption)
    result = await render_service.run_music_generation(job.id, source_audio, caption)
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


async def repaint(project_id: str, source_audio: str, start_s: float, end_s: float, caption: str = "") -> str:
    job = render_service.create_job(project_id, RenderMode.REPAINT, source_audio=source_audio, caption=caption, start_s=start_s, end_s=end_s)
    result = await render_service.run_music_generation(job.id, source_audio, caption, start_s, end_s)
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


async def separate_stems(project_id: str, source_audio: str) -> str:
    job = render_service.create_job(project_id, RenderMode.SEPARATE, source_audio=source_audio)
    result = await render_service.run_separation(job.id, source_audio)
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


async def svc_convert(project_id: str, source_audio: str, reference_voice: str) -> str:
    job = render_service.create_job(project_id, RenderMode.SVC, source_audio=source_audio, reference_voice=reference_voice)
    result = await render_service.run_svc(job.id, source_audio, reference_voice)
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


def cancel_render_job(job_id: str) -> str:
    """Cancel a queued render job or terminate a running engine subprocess when possible."""
    if job_id in render_service.jobs:
        return dumps(render_service.cancel_job(job_id).model_dump(mode="json"))
    try:
        import urllib.request

        request = urllib.request.Request(f"http://127.0.0.1:8787/api/jobs/{job_id}/cancel", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=1.0) as response:
            return response.read().decode("utf-8")
    except Exception:
        pass
    return dumps(render_service.cancel_job(job_id).model_dump(mode="json"))


def export_project(project_id: str, fmt: str, output_path: str) -> str:
    project = store.get(project_id)
    output = Path(output_path)
    exporters = {"mid": export_midi, "lrc": export_lrc, "ustx": export_ustx, "svp": export_svp, "vpr": export_vpr, "wav": export_master_wav, "stems": export_stems_zip}
    if fmt in {"mp3", "flac", "ogg"}:
        export_compressed_master(project, output, fmt)
        return dumps({"output": str(output), "bytes": output.stat().st_size})
    if fmt not in exporters:
        raise ValueError(f"unsupported format: {fmt}")
    exporters[fmt](project, output)
    return dumps({"output": str(output), "bytes": output.stat().st_size})


def save_and_notify(project) -> None:
    store.save(project)
    notify_web(project)


def batch_add_notes(project_id: str, track_id: str, notes: list[dict]) -> str:
    project = store.get(project_id)
    added = editing.add_notes(project, track_id, notes)
    save_and_notify(project)
    return dumps([note.model_dump(mode="json") for note in added])


def update_note(project_id: str, track_id: str, note_id: str, patch: dict) -> str:
    project = store.get(project_id)
    note = editing.update_note(project, track_id, note_id, patch)
    save_and_notify(project)
    return dumps(note.model_dump(mode="json"))


def split_note(project_id: str, track_id: str, note_id: str, split_ticks: int) -> str:
    project = store.get(project_id)
    first, second = editing.split_note(project, track_id, note_id, split_ticks)
    save_and_notify(project)
    return dumps({"first": first.model_dump(mode="json"), "second": second.model_dump(mode="json")})


def ripple_delete_range(project_id: str, start_ticks: int, end_ticks: int) -> str:
    project = store.get(project_id)
    result = editing.ripple_delete_time_range(project, start_ticks, end_ticks)
    save_and_notify(project)
    return dumps(result)


def delete_note(project_id: str, track_id: str, note_id: str) -> str:
    project = store.get(project_id)
    deleted = editing.delete_note(project, track_id, note_id)
    if not deleted:
        raise KeyError(f"note not found: {note_id}")
    save_and_notify(project)
    return dumps({"deleted": True, "note_id": note_id})


def set_expression_lane(project_id: str, track_id: str, lane: str, points: list[dict]) -> str:
    project = store.get(project_id)
    parsed = editing.set_automation_lane(project, track_id, lane, points)
    save_and_notify(project)
    return dumps([point.model_dump(mode="json") for point in parsed])


def upsert_breath(project_id: str, track_id: str, breath: dict, breath_id: Optional[str] = None) -> str:
    project = store.get(project_id)
    item = editing.upsert_breath(project, track_id, breath, breath_id)
    save_and_notify(project)
    return dumps(item.model_dump(mode="json"))


def delete_breath(project_id: str, track_id: str, breath_id: str) -> str:
    project = store.get(project_id)
    deleted = editing.delete_breath(project, track_id, breath_id)
    if not deleted:
        raise KeyError(f"breath not found: {breath_id}")
    save_and_notify(project)
    return dumps({"deleted": True, "breath_id": breath_id})


def upsert_audio_clip(project_id: str, track_id: str, clip: dict, clip_id: Optional[str] = None) -> str:
    project = store.get(project_id)
    item = editing.upsert_audio_clip(project, track_id, clip, clip_id)
    save_and_notify(project)
    return dumps(item.model_dump(mode="json"))


def delete_audio_clip(project_id: str, track_id: str, clip_id: str) -> str:
    project = store.get(project_id)
    deleted = editing.delete_audio_clip(project, track_id, clip_id)
    if not deleted:
        raise KeyError(f"clip not found: {clip_id}")
    save_and_notify(project)
    return dumps({"deleted": True, "clip_id": clip_id})


def set_tempo_map(project_id: str, bpm: Optional[float] = None, points: Optional[list[dict]] = None) -> str:
    project = store.get(project_id)
    tempo_map = editing.set_tempo_map(project, bpm, points or [])
    save_and_notify(project)
    return dumps({"bpm": project.bpm, "tempo_map": [point.model_dump(mode="json") for point in tempo_map]})


def assign_voice(project_id: str, track_id: str, voice_id: str, reference_voice_path: Optional[str] = None) -> str:
    project = store.get(project_id)
    result = editing.assign_voice(project, track_id, voice_id, reference_voice_path)
    save_and_notify(project)
    return dumps(result)


async def import_audio_project(path: str, title: Optional[str] = None) -> str:
    source = Path(path)
    if not source.exists():
        raise ValueError(f"audio file does not exist: {source}")
    project = await asyncio.to_thread(project_from_audio, source, title)
    store.save(project)
    notify_web(project)
    return dumps(project.model_dump(mode="json"))


def import_midi_project(path: str, title: Optional[str] = None) -> str:
    project = import_midi(Path(path), title=title)
    store.save(project)
    notify_web(project)
    return dumps(project.model_dump(mode="json"))


def build_mcp_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("install the `mcp` Python package to run openace-mcp") from exc

    mcp = FastMCP("OpenACE")
    mcp.tool()(create_project)
    mcp.tool()(list_projects)
    mcp.tool()(get_project)
    mcp.tool()(duplicate_project)
    mcp.tool()(organize_project)
    mcp.tool()(delete_project)
    mcp.tool()(list_media_files)
    mcp.tool()(place_media)
    mcp.tool()(delete_media)
    mcp.tool()(add_track)
    mcp.tool()(add_note)
    mcp.tool()(transpose_track)
    mcp.tool()(render_vocal)
    mcp.tool()(vocal2bgm)
    mcp.tool()(repaint)
    mcp.tool()(svc_convert)
    mcp.tool()(cancel_render_job)
    mcp.tool()(separate_stems)
    mcp.tool()(export_project)
    mcp.tool()(batch_add_notes)
    mcp.tool()(update_note)
    mcp.tool()(delete_note)
    mcp.tool()(split_note)
    mcp.tool()(ripple_delete_range)
    mcp.tool()(set_expression_lane)
    mcp.tool()(upsert_breath)
    mcp.tool()(delete_breath)
    mcp.tool()(upsert_audio_clip)
    mcp.tool()(delete_audio_clip)
    mcp.tool()(set_tempo_map)
    mcp.tool()(assign_voice)
    mcp.tool()(import_audio_project)
    mcp.tool()(import_midi_project)
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
