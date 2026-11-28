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
from openace.core.voice_library import VoiceLibrary
from openace.core.voice_operations import delete_voice_with_project_cleanup
from openace.core.timing import validate_absolute_beat_anchor
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.importers.audio import project_from_audio
from openace.importers.midi import import_midi
from openace.exporters.svp import export_svp
from openace.exporters.master import export_compressed_master, export_lyrics_video_master, export_master_wav, export_stems_zip
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


def notify_voice_library(payload: dict) -> None:
    try:
        import urllib.request
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8787/api/internal/voice-library-updated", data=body, headers={"Content-Type": "application/json"}, method="POST")
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


def update_track(project_id: str, track_id: str, patch: dict) -> str:
    """Update validated track metadata/mixer fields such as name, color, language, mute/solo, volume/pan, MIDI channel/program, or OpenUtau host mapping."""
    project = store.get(project_id)
    track = editing.update_track(project, track_id, patch)
    save_and_notify(project)
    return dumps(track.model_dump(mode="json"))


def duplicate_track(project_id: str, track_id: str, name: Optional[str] = None) -> str:
    """Duplicate a track with fresh note/clip/breath ids; source media paths are shared but render provenance is not faked."""
    project = store.get(project_id)
    track = editing.duplicate_track(project, track_id, name)
    save_and_notify(project)
    return dumps(track.model_dump(mode="json"))


def delete_track(project_id: str, track_id: str) -> str:
    """Delete a track object without deleting underlying media/render files."""
    project = store.get(project_id)
    editing.delete_track(project, track_id)
    save_and_notify(project)
    return dumps({"deleted": True, "track_id": track_id})


def reorder_track(project_id: str, track_id: str, index: int) -> str:
    """Move a track to an exact zero-based arrangement index."""
    project = store.get(project_id)
    track = editing.reorder_track(project, track_id, index)
    save_and_notify(project)
    return dumps({"track": track.model_dump(mode="json"), "order": [item.id for item in project.tracks]})


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


async def vocal2bgm(project_id: str, source_audio: str = "", caption: str = "professional instrumental accompaniment", track_id: str = "", clip_id: str = "") -> str:
    job = render_service.create_job(project_id, RenderMode.VOCAL2BGM, track_id or None, source_audio=source_audio or None, caption=caption, clip_id=clip_id or None)
    result = await render_service.run_music_generation(job.id, source_audio, caption)
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


async def repaint(project_id: str, source_audio: str, start_s: float, end_s: float, caption: str = "", clip_id: str = "") -> str:
    job = render_service.create_job(project_id, RenderMode.REPAINT, source_audio=source_audio, caption=caption, start_s=start_s, end_s=end_s, clip_id=clip_id or None)
    result = await render_service.run_music_generation(job.id, source_audio, caption, start_s, end_s)
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


async def separate_stems(project_id: str, source_audio: str = "", clip_id: str = "") -> str:
    job = render_service.create_job(project_id, RenderMode.SEPARATE, source_audio=source_audio or None, clip_id=clip_id or None)
    result = await render_service.run_separation(job.id, source_audio)
    notify_web(store.get(project_id))
    return dumps(result.model_dump(mode="json"))


async def svc_convert(project_id: str, source_audio: str, reference_voice: str, clip_id: str = "", pitch_shift: int = 0, auto_shift: bool = False) -> str:
    """Convert source audio into a reference voice, optionally transposing by manual semitones or automatic median-F0 key matching."""
    job = render_service.create_job(project_id, RenderMode.SVC, source_audio=source_audio, reference_voice=reference_voice, clip_id=clip_id or None, pitch_shift=pitch_shift, auto_shift=auto_shift)
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


def export_project(project_id: str, fmt: str, output_path: str, start_ticks: int = -1, end_ticks: int = -1) -> str:
    """Export a project; optional nonnegative tick range applies to audio masters/stems."""
    project = store.get(project_id)
    output = Path(output_path)
    start = None if start_ticks < 0 else start_ticks
    end = None if end_ticks < 0 else end_ticks
    if (start is None) != (end is None):
        raise ValueError("export range requires both start_ticks and end_ticks")
    if start is not None:
        if end <= start:
            raise ValueError("export range must satisfy 0 <= start_ticks < end_ticks")
        if fmt not in {"wav", "mp3", "flac", "ogg", "stems"}:
            raise ValueError(f"range export is currently supported for audio masters/stems, not {fmt}")
    exporters = {"mid": export_midi, "lrc": export_lrc, "ustx": export_ustx, "svp": export_svp, "vpr": export_vpr, "wav": export_master_wav, "stems": export_stems_zip}
    if fmt in {"mp3", "flac", "ogg"}:
        export_compressed_master(project, output, fmt, start_ticks=start, end_ticks=end)
        return dumps({"output": str(output), "bytes": output.stat().st_size})
    if fmt == "mp4":
        export_lyrics_video_master(project, output)
        return dumps({"output": str(output), "bytes": output.stat().st_size})
    if fmt not in exporters:
        raise ValueError(f"unsupported format: {fmt}")
    if fmt == "wav":
        export_master_wav(project, output, start_ticks=start, end_ticks=end)
    elif fmt == "stems":
        export_stems_zip(project, output, start_ticks=start, end_ticks=end)
    else:
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


def merge_notes(project_id: str, track_id: str, note_ids_json: str) -> str:
    """Merge exactly contiguous vocal notes, preserving pitch movement truthfully."""
    import json

    project = store.get(project_id)
    note_ids = json.loads(note_ids_json)
    if not isinstance(note_ids, list) or not all(isinstance(item, str) for item in note_ids):
        raise ValueError("note_ids_json must be a JSON array of note ids")
    merged = editing.merge_notes(project, track_id, note_ids)
    save_and_notify(project)
    return dumps(merged.model_dump(mode="json"))


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


def voice_library() -> VoiceLibrary:
    return VoiceLibrary(DATA / "voices")


def list_voices() -> str:
    """List persistent zero-shot reference voices with truthful measured quality metadata."""
    return dumps([voice.model_dump(mode="json") for voice in voice_library().list()])


def import_voice(path: str, name: str = "") -> str:
    """Import a local reference audio file into the persistent voice library."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"reference voice not found: {source}")
    library = voice_library()
    with source.open("rb") as stream:
        voice = library.create(source.name, stream)
    if name.strip():
        voice = library.rename(voice.id, name)
    notify_voice_library({"action": "created", "voice": voice.model_dump(mode="json")})
    return dumps(voice.model_dump(mode="json"))


def trim_voice(voice_id: str, start_seconds: float, end_seconds: float) -> str:
    """Create an exact sample-based trimmed copy of a reference voice."""
    voice = voice_library().create_trimmed_copy(voice_id, start_seconds, end_seconds)
    notify_voice_library({"action": "created", "voice": voice.model_dump(mode="json")})
    return dumps(voice.model_dump(mode="json"))


def rename_voice(voice_id: str, name: str) -> str:
    """Rename a persistent zero-shot reference voice."""
    voice = voice_library().rename(voice_id, name)
    notify_voice_library({"action": "renamed", "voice": voice.model_dump(mode="json")})
    return dumps(voice.model_dump(mode="json"))


def delete_voice(voice_id: str, unassign: bool = False) -> str:
    """Delete a reference voice; active project use requires explicit unassign=true."""
    try:
        result = delete_voice_with_project_cleanup(store, voice_library(), voice_id, unassign=unassign, publish_project=notify_web)
    except RuntimeError as exc:
        raise ValueError(str(exc) + "; pass unassign=true to remove the assignment explicitly") from exc
    notify_voice_library({"action": "deleted", "voice_id": voice_id, "unassigned": result["unassigned"]})
    return dumps({"ok": True, **result})


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
    mcp.tool()(update_track)
    mcp.tool()(duplicate_track)
    mcp.tool()(delete_track)
    mcp.tool()(reorder_track)
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
    mcp.tool()(merge_notes)
    mcp.tool()(ripple_delete_range)
    mcp.tool()(set_expression_lane)
    mcp.tool()(upsert_breath)
    mcp.tool()(delete_breath)
    mcp.tool()(upsert_audio_clip)
    mcp.tool()(delete_audio_clip)
    mcp.tool()(set_tempo_map)
    mcp.tool()(list_voices)
    mcp.tool()(import_voice)
    mcp.tool()(trim_voice)
    mcp.tool()(rename_voice)
    mcp.tool()(delete_voice)
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
