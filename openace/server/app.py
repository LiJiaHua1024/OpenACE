from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from openace.core.models import AudioClip, Note, Project, RenderMode, Track, TrackType, new_id
from openace.core.phonemes import PhonemeError, ensure_note_phonemes, timed_phonemes, tokens_from_symbols
from openace.core.editing import ripple_delete_time_range, split_note as split_note_operation
from openace.core.project_store import ProjectStore, normalize_project_folders, normalize_project_tags
from openace.core.voice_library import VoiceLibrary
from openace.core.timing import validate_absolute_beat_anchor
from openace.exporters.master import export_lyrics_video, export_master_wav
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.exporters.svp import export_svp
from openace.exporters.ustx import export_ustx
from openace.exporters.vpr import export_vpr
from openace.importers.audio import project_from_audio
from openace.importers.midi import import_midi
from openace.importers.ustx import import_ustx
from openace.engines.vram import vram_manager

from .events import event_bus
from .render_service import RenderService

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("OPENACE_DATA_DIR", ROOT / "data"))
PROJECTS = DATA / "projects"
RENDERS = DATA / "renders"
UPLOADS = DATA / "uploads"
VOICES = DATA / "voices"
EXPORTS = DATA / "exports"
for directory in (PROJECTS, RENDERS, UPLOADS, VOICES, EXPORTS):
    directory.mkdir(parents=True, exist_ok=True)

store = ProjectStore(PROJECTS)
render_service = RenderService(store, RENDERS)
voice_library = VoiceLibrary(VOICES)

app = FastAPI(title="OpenACE", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/renders", StaticFiles(directory=str(RENDERS)), name="renders")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")
@app.on_event("startup")
async def recover_interrupted_render_jobs():
    for recovered_job in render_service.recover_interrupted_jobs():
        render_service.enqueue_job(recovered_job.id)


@app.on_event("shutdown")
async def shutdown_render_queue():
    await render_service.shutdown()


class CreateProjectRequest(BaseModel):
    title: str = "Untitled OpenACE Project"


class ProjectOrganizationRequest(BaseModel):
    pinned: Optional[bool] = None
    tags: Optional[List[str]] = None
    folders: Optional[Union[List[str], str]] = None


class CreateTrackRequest(BaseModel):
    name: str
    type: TrackType = TrackType.VOCAL
    language: str = "zh"
    color: str = "#7c5cff"


class SplitNoteRequest(BaseModel):
    split_ticks: int


class RippleDeleteRangeRequest(BaseModel):
    start_ticks: int
    end_ticks: int


class PlaceMediaClipRequest(BaseModel):
    media_name: str
    start_ticks: int = 0
    track_id: Optional[str] = None


class PhonemeTimingRequest(BaseModel):
    symbols: List[str]
    duration_ms: float



class NoteRequest(BaseModel):
    start_ticks: int
    duration_ticks: int
    pitch: int
    lyric: str = ""
    velocity: int = 90


class RenderRequest(BaseModel):
    track_id: Optional[str] = None
    source_audio: Optional[str] = None
    reference_voice: Optional[str] = None
    caption: str = ""
    start_s: float = 0.0
    end_s: float = -1.0


def get_project(project_id: str) -> Project:
    try:
        return store.get(project_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


def validate_project_editing_invariants(project: Project) -> None:
    try:
        for track in project.vocal_tracks():
            ordered = sorted(track.notes, key=lambda note: (note.start_ticks, note.pitch, note.id))
            for previous, following in zip(ordered, ordered[1:]):
                if following.start_ticks < previous.start_ticks + previous.duration_ticks:
                    raise ValueError("vocal notes may not overlap on a monophonic track; trim or move the conflicting note")
            for note in track.notes:
                if note.lyric.strip():
                    ensure_note_phonemes(note, track.language, project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0)
            validate_absolute_beat_anchor(track.notes, project.ppq, project.bpm, project=project)
    except (PhonemeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


def publish_project(project: Project) -> None:
    event_bus.publish("project_updated", {"project_id": project.id, "project": project.model_dump(mode="json")})


@app.post("/api/internal/project-updated")
def internal_project_updated(payload: Dict[str, Any]):
    # Local first-party processes (CLI/MCP) use this loopback notification so external
    # edits arrive on the same SSE channel as workstation edits. The server binds local
    # loopback by default; exposing it publicly is an operator-level network decision.
    project = Project.model_validate(payload)
    publish_project(project)
    return {"ok": True}


@app.post("/api/internal/media-updated")
def internal_media_updated(payload: Dict[str, Any]):
    action = str(payload.get("action") or "updated")
    media = payload.get("media") or {}
    event_bus.publish("media_library", {"action": action, "media": media})
    return {"ok": True}


@app.post("/api/internal/project-deleted")
def internal_project_deleted(payload: Dict[str, Any]):
    project_id = str(payload.get("project_id") or "")
    if not project_id:
        raise HTTPException(400, "project_id is required")
    event_bus.publish("project_deleted", {"project_id": project_id})
    return {"ok": True}


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "fixture_mode": os.environ.get("OPENACE_CI_SYNTH_FIXTURE") == "1",
        "vram": vram_manager.status(),
    }


@app.get("/api/events")
async def events():
    queue = event_bus.subscribe()

    async def stream():
        try:
            yield "event: hello\ndata: {\"ok\": true}\n\n"
            while True:
                event = await queue.get()
                yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/projects")
def list_projects():
    return store.list()


@app.post("/api/projects")
def create_project(request: CreateProjectRequest):
    project = store.create(request.title)
    publish_project(project)
    return project.model_dump(mode="json")


@app.get("/api/projects/{project_id}")
def read_project(project_id: str):
    return get_project(project_id).model_dump(mode="json")


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, payload: Dict[str, Any]):
    # Validate the complete project graph before saving. This endpoint is used by the
    # workstation for undoable high-level operations; atomic note endpoints below are
    # preferred for editing.
    project = Project.model_validate(payload)
    if project.id != project_id:
        raise HTTPException(400, "project id mismatch")
    validate_project_editing_invariants(project)
    store.save(project)
    publish_project(project)
    return project.model_dump(mode="json")


@app.patch("/api/projects/{project_id}/organization")
def update_project_organization(project_id: str, request: ProjectOrganizationRequest):
    try:
        project = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(404, "project not found") from exc
    metadata = dict(project.metadata or {})
    if request.pinned is not None:
        metadata["pinned"] = bool(request.pinned)
    if request.tags is not None:
        metadata["tags"] = normalize_project_tags(request.tags)
    if request.folders is not None:
        metadata["folders"] = normalize_project_folders(request.folders)
    project.metadata = metadata
    project.save(store.path_for(project.id))
    publish_project(project)
    return project.model_dump(mode="json")


@app.post("/api/projects/{project_id}/duplicate")
def duplicate_project(project_id: str):
    try:
        source = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(404, "project not found") from exc
    duplicate = Project.model_validate(source.model_dump())
    duplicate.id = new_id("project")
    duplicate.title = f"{source.title} Copy"
    duplicate.metadata = dict(source.metadata or {})
    duplicate.metadata["pinned"] = False
    duplicate.touch()
    store.save(duplicate)
    publish_project(duplicate)
    return duplicate.model_dump(mode="json")


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    if not store.delete(project_id):
        raise HTTPException(404, "project not found")
    event_bus.publish("project_deleted", {"project_id": project_id})
    return {"ok": True}


@app.post("/api/projects/{project_id}/tracks")
def create_track(project_id: str, request: CreateTrackRequest):
    project = get_project(project_id)
    track = project.add_track(Track(name=request.name, type=request.type, language=request.language, color=request.color))
    store.save(project)
    publish_project(project)
    return track.model_dump(mode="json")


@app.post("/api/projects/{project_id}/tracks/{track_id}/notes")
def create_note(project_id: str, track_id: str, request: NoteRequest):
    project = get_project(project_id)
    try:
        track = project.track(track_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    note = track.add_note(Note(**request.model_dump()))
    validate_project_editing_invariants(project)
    store.save(project)
    publish_project(project)
    return note.model_dump(mode="json")


@app.patch("/api/projects/{project_id}/tracks/{track_id}/notes/{note_id}")
def update_note(project_id: str, track_id: str, note_id: str, payload: Dict[str, Any]):
    project = get_project(project_id)
    try:
        note = project.track(track_id).note(note_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    data = note.model_dump()
    data.update(payload)
    updated = Note.model_validate(data)
    track = project.track(track_id)
    track.notes = [updated if n.id == note_id else n for n in track.notes]
    track.notes.sort(key=lambda n: (n.start_ticks, n.pitch))
    validate_project_editing_invariants(project)
    store.save(project)
    publish_project(project)
    return updated.model_dump(mode="json")


@app.post("/api/projects/{project_id}/editing/ripple-delete-range")
def ripple_delete_range(project_id: str, request: RippleDeleteRangeRequest):
    project = get_project(project_id)
    try:
        result = ripple_delete_time_range(project, request.start_ticks, request.end_ticks)
    except (ValueError, PhonemeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    store.save(project)
    publish_project(project)
    return result


@app.post("/api/projects/{project_id}/tracks/{track_id}/notes/{note_id}/split")
def split_note(project_id: str, track_id: str, note_id: str, request: SplitNoteRequest):
    project = get_project(project_id)
    try:
        first, second = split_note_operation(project, track_id, note_id, request.split_ticks)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, PhonemeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    store.save(project)
    publish_project(project)
    return {"first": first.model_dump(mode="json"), "second": second.model_dump(mode="json")}


@app.delete("/api/projects/{project_id}/tracks/{track_id}/notes/{note_id}")
def delete_note(project_id: str, track_id: str, note_id: str):
    project = get_project(project_id)
    try:
        track = project.track(track_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    if not track.delete_note(note_id):
        raise HTTPException(404, "note not found")
    store.save(project)
    publish_project(project)
    return {"ok": True}


@app.post("/api/phonemes/time")
def time_manual_phonemes(request: PhonemeTimingRequest):
    try:
        tokens = tokens_from_symbols(request.symbols)
        return [item.model_dump(mode="json") for item in timed_phonemes(tokens, request.duration_ms)]
    except PhonemeError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/projects/{project_id}/render/vocal")
async def render_vocal(project_id: str, request: RenderRequest):
    if not request.track_id:
        raise HTTPException(400, "track_id is required")
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.SVS_SCORE, request.track_id)
    render_service.enqueue_job(job.id)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/vocal2bgm")
async def render_vocal2bgm(project_id: str, request: RenderRequest):
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.VOCAL2BGM, request.track_id, source_audio=request.source_audio, caption=request.caption)
    render_service.enqueue_job(job.id)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/repaint")
async def render_repaint(project_id: str, request: RenderRequest):
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.REPAINT, request.track_id, source_audio=request.source_audio, caption=request.caption, start_s=request.start_s, end_s=request.end_s)
    render_service.enqueue_job(job.id)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/separate")
async def render_separation(project_id: str, request: RenderRequest):
    get_project(project_id)
    if not request.source_audio:
        raise HTTPException(400, "source_audio is required")
    job = render_service.create_job(project_id, RenderMode.SEPARATE, request.track_id, source_audio=request.source_audio)
    render_service.enqueue_job(job.id)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/svc")
async def render_svc(project_id: str, request: RenderRequest):
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.SVC, request.track_id, source_audio=request.source_audio, reference_voice=request.reference_voice)
    render_service.enqueue_job(job.id)
    return job.model_dump(mode="json")


@app.get("/api/jobs/{job_id}")
def read_job(job_id: str):
    if job_id not in render_service.jobs:
        raise HTTPException(404, "job not found")
    return render_service.jobs[job_id].model_dump(mode="json")


@app.get("/api/jobs")
def list_jobs():
    return [job.model_dump(mode="json") for job in sorted(render_service.jobs.values(), key=lambda j: j.created_at, reverse=True)]


class VoiceRenameRequest(BaseModel):
    name: str


class VoiceTrimRequest(BaseModel):
    start_seconds: float
    end_seconds: float


class MediaOrganizationRequest(BaseModel):
    tags: Optional[List[str]] = None
    folders: Optional[List[str]] = None


@app.get("/api/voices")
def list_voices():
    return [voice.model_dump(mode="json") for voice in voice_library.list()]


@app.post("/api/voices")
async def create_voice(file: UploadFile = File(...)):
    try:
        voice = voice_library.create(file.filename or "reference.wav", file.file)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    event_bus.publish("voice_library", {"action": "created", "voice": voice.model_dump(mode="json")})
    return voice.model_dump(mode="json")


@app.get("/api/voices/{voice_id}/audio")
def voice_audio(voice_id: str):
    try:
        voice = voice_library.get(voice_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    path = Path(voice.path).resolve()
    voices_root = VOICES.resolve()
    if voices_root not in path.parents or not path.exists():
        raise HTTPException(404, "voice audio not found")
    return FileResponse(str(path), filename=path.name)


@app.post("/api/voices/{voice_id}/trim")
def trim_voice(voice_id: str, request: VoiceTrimRequest):
    try:
        voice = voice_library.create_trimmed_copy(voice_id, request.start_seconds, request.end_seconds)
        event_bus.publish("voice_library", {"action": "created", "voice": voice.model_dump(mode="json")})
        return voice.model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.patch("/api/voices/{voice_id}")
def rename_voice(voice_id: str, request: VoiceRenameRequest):
    try:
        updated = voice_library.rename(voice_id, request.name)
        event_bus.publish("voice_library", {"action": "renamed", "voice": updated.model_dump(mode="json")})
        return updated.model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: str, unassign: bool = False):
    try:
        voice = voice_library.get(voice_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    usages = []
    projects = []
    for path in PROJECTS.glob("*.openace.json"):
        try:
            project = Project.load(path)
        except Exception:
            continue
        projects.append(project)
        for track in project.tracks:
            if track.voice_id == voice_id or track.reference_voice_path == voice.path:
                usages.append((project, track))
    if usages and not unassign:
        project, track = usages[0]
        raise HTTPException(409, f"voice is in use by project '{project.title}' track '{track.name}'")
    if usages:
        for project in projects:
            changed = False
            for track in project.tracks:
                if track.voice_id == voice_id:
                    track.voice_id = ""
                    changed = True
                if track.reference_voice_path == voice.path:
                    track.reference_voice_path = None
                    changed = True
            if changed:
                store.save(project)
                publish_project(project)
    try:
        deleted = voice_library.delete(voice_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    event_bus.publish("voice_library", {"action": "deleted", "voice_id": voice_id, "unassigned": len(usages)})
    return {"ok": True, "deleted": deleted.model_dump(mode="json"), "unassigned": len(usages)}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    safe = Path(file.filename or "upload.bin").name
    destination = UPLOADS / f"{new_id('upload')}_{safe}"
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    entry = media_entry(destination) if destination.suffix.lower() in AUDIO_MEDIA_EXTENSIONS else {"id": destination.name, "name": safe, "path": str(destination)}
    publish_media_library("created", entry)
    return {"path": str(destination), "name": safe, "size": destination.stat().st_size}


AUDIO_MEDIA_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".aiff", ".aif"}


def media_path_for(media_name: str) -> Path:
    safe = Path(media_name).name
    path = (UPLOADS / safe).resolve()
    root = UPLOADS.resolve()
    if path.parent != root or not path.exists() or not path.is_file():
        raise HTTPException(404, "media file not found")
    return path


def media_metadata_path() -> Path:
    return UPLOADS / "media_metadata.json"


def load_media_metadata() -> Dict[str, Any]:
    path = media_metadata_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def save_media_metadata(metadata: Dict[str, Any]) -> None:
    path = media_metadata_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def clean_media_labels(values: Optional[List[str]], field: str) -> List[str]:
    if values is None:
        return []
    cleaned = []
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        if len(item) > 40:
            raise ValueError(f"media {field} must be at most 40 characters")
        if item not in cleaned:
            cleaned.append(item)
    return cleaned[:24]


def media_entry(path: Path) -> Dict[str, Any]:
    parts = path.name.split("_", 2)
    display_name = parts[2] if len(parts) == 3 else path.name
    entry: Dict[str, Any] = {
        "id": path.name,
        "name": display_name,
        "file_name": path.name,
        "path": str(path),
        "size": path.stat().st_size,
        "modified_at": path.stat().st_mtime,
        "valid": False,
    }
    try:
        info = sf.info(path)
        entry.update({
            "valid": bool(info.frames and info.samplerate > 0),
            "duration_seconds": info.frames / info.samplerate if info.samplerate else 0.0,
            "sample_rate": info.samplerate,
            "channels": info.channels,
        })
    except Exception as exc:
        entry["error"] = str(exc)
    organization = load_media_metadata().get(path.name) or {}
    entry["tags"] = list(organization.get("tags") or [])
    entry["folders"] = list(organization.get("folders") or [])
    return entry


def media_file_in_use(path: Path) -> List[str]:
    target = str(path.resolve())
    users = []
    for summary in store.list():
        try:
            candidate = store.get(summary["id"])
        except Exception:
            continue
        if any(str(Path(clip.path).resolve()) == target for track in candidate.tracks for clip in track.clips):
            users.append(candidate.id)
    return users


def publish_media_library(action: str, media: Dict[str, Any]) -> None:
    event_bus.publish("media_library", {"action": action, "media": media})


@app.get("/api/media")
def list_media_files():
    files = []
    for path in sorted(UPLOADS.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.is_file() and path.suffix.lower() in AUDIO_MEDIA_EXTENSIONS:
            files.append(media_entry(path))
    return files


@app.patch("/api/media/{media_name}/organization")
def update_media_organization(media_name: str, request: MediaOrganizationRequest):
    path = media_path_for(media_name)
    try:
        tags = clean_media_labels(request.tags, "tags") if request.tags is not None else None
        folders = clean_media_labels(request.folders, "folders") if request.folders is not None else None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    metadata = load_media_metadata()
    current = dict(metadata.get(path.name) or {})
    if tags is not None:
        current["tags"] = tags
    if folders is not None:
        current["folders"] = folders
    if current.get("tags") or current.get("folders"):
        metadata[path.name] = current
    else:
        metadata.pop(path.name, None)
    save_media_metadata(metadata)
    entry = media_entry(path)
    publish_media_library("updated", entry)
    return entry


@app.delete("/api/media/{media_name}")
def delete_media_file(media_name: str):
    path = media_path_for(media_name)
    entry = media_entry(path)
    users = media_file_in_use(path)
    if users:
        raise HTTPException(409, f"media file is used by arrangement clips in {len(users)} project(s); remove those clips before deleting it")
    path.unlink()
    metadata = load_media_metadata()
    if metadata.pop(path.name, None) is not None:
        save_media_metadata(metadata)
    publish_media_library("deleted", entry)
    return {"ok": True, "deleted": entry}


@app.post("/api/projects/{project_id}/media/clip")
def place_media_clip(project_id: str, request: PlaceMediaClipRequest):
    project = get_project(project_id)
    path = media_path_for(request.media_name)
    try:
        info = sf.info(path)
        if not info.frames or info.samplerate <= 0:
            raise ValueError("audio file has no samples")
    except Exception as exc:
        raise HTTPException(422, f"invalid audio clip: {exc}") from exc
    if request.track_id:
        try:
            track = project.track(request.track_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if track.type == TrackType.VOCAL:
            raise HTTPException(422, "imported audio clips cannot be placed on vocal note tracks; select an audio/accompaniment track or omit track_id")
    else:
        track = project.add_track(Track(name=f"Audio — {Path(media_entry(path)['name']).stem}", type=TrackType.AUDIO, color="#ff8f5a"))
    duration_ticks = project.seconds_to_ticks(info.frames / info.samplerate)
    clip = AudioClip(path=str(path), start_ticks=max(0, request.start_ticks), duration_ticks=duration_ticks, label=Path(media_entry(path)["name"]).stem)
    track.clips.append(clip)
    track.clips.sort(key=lambda item: item.start_ticks)
    store.save(project)
    publish_project(project)
    return {"project": project.model_dump(mode="json"), "track": track.model_dump(mode="json"), "clip": clip.model_dump(mode="json")}


@app.post("/api/projects/{project_id}/clips/import")
async def import_audio_clip(project_id: str, file: UploadFile = File(...), start_ticks: int = Form(0), track_id: Optional[str] = Form(None)):
    project = get_project(project_id)
    suffix = Path(file.filename or "clip.wav").suffix or ".wav"
    safe = Path(file.filename or "clip.wav").name
    destination = UPLOADS / f"{new_id('clip')}_{safe}"
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        info = sf.info(destination)
        if not info.frames or info.samplerate <= 0:
            raise ValueError("audio file has no samples")
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, f"invalid audio clip: {exc}") from exc
    if track_id:
        try:
            track = project.track(track_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if track.type == TrackType.VOCAL:
            raise HTTPException(422, "imported audio clips cannot be placed on vocal note tracks; select an audio/accompaniment track or omit track_id")
    else:
        track = project.add_track(Track(name=f"Audio — {Path(safe).stem}", type=TrackType.AUDIO, color="#ff8f5a"))
    duration_ticks = project.seconds_to_ticks(info.frames / info.samplerate)
    clip = AudioClip(path=str(destination), start_ticks=max(0, start_ticks), duration_ticks=duration_ticks, label=Path(safe).stem)
    track.clips.append(clip)
    track.clips.sort(key=lambda item: item.start_ticks)
    store.save(project)
    publish_project(project)
    publish_media_library("created", media_entry(destination))
    return {"project": project.model_dump(mode="json"), "track": track.model_dump(mode="json"), "clip": clip.model_dump(mode="json")}


@app.post("/api/import/midi")
async def import_midi_file(file: UploadFile = File(...)):
    suffix = Path(file.filename or "input.mid").suffix or ".mid"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        project = import_midi(tmp_path, title=Path(file.filename or "Imported MIDI").stem)
        store.save(project)
        publish_project(project)
        return project.model_dump(mode="json")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/import/ustx")
async def import_ustx_file(file: UploadFile = File(...)):
    suffix = Path(file.filename or "input.ustx").suffix or ".ustx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        source_path = tmp_path
        if suffix.lower() == ".zip":
            package_dir = UPLOADS / "ustx_packages" / Path(tempfile.mkdtemp(prefix="pkg_")).name
            package_dir.mkdir(parents=True, exist_ok=False)
            try:
                with zipfile.ZipFile(tmp_path) as archive:
                    for member in archive.infolist():
                        name = Path(member.filename)
                        if name.is_absolute() or ".." in name.parts:
                            raise RuntimeError(f"unsafe USTX package path: {member.filename}")
                        mode = (member.external_attr >> 16) & 0o170000
                        if mode == 0o120000:
                            raise RuntimeError(f"unsafe USTX package symlink: {member.filename}")
                        if member.is_dir():
                            continue
                        target = package_dir / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as src, target.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                candidates = sorted(package_dir.rglob("*.ustx"))
                if len(candidates) != 1:
                    raise RuntimeError(f"USTX package must contain exactly one .ustx file, found {len(candidates)}")
                source_path = candidates[0]
            except Exception:
                shutil.rmtree(package_dir, ignore_errors=True)
                raise
        project = import_ustx(source_path)
        store.save(project)
        publish_project(project)
        return project.model_dump(mode="json")
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/import/audio")
async def import_audio_file(file: UploadFile = File(...)):
    suffix = Path(file.filename or "input.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        project = await asyncio.to_thread(project_from_audio, tmp_path, Path(file.filename or "Imported Audio").stem)
        store.save(project)
        publish_project(project)
        return project.model_dump(mode="json")
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/api/projects/{project_id}/export/{fmt}")
def export_project(project_id: str, fmt: str):
    project = get_project(project_id)
    safe_title = "".join(ch if ch.isalnum() or ch in " _-" else "_" for ch in project.title).strip() or "openace"
    mapping = {
        "mid": (export_midi, EXPORTS / f"{safe_title}.mid"),
        "lrc": (export_lrc, EXPORTS / f"{safe_title}.lrc"),
        "ustx": (export_ustx, EXPORTS / f"{safe_title}.ustx"),
        "svp": (export_svp, EXPORTS / f"{safe_title}.svp"),
        "vpr": (export_vpr, EXPORTS / f"{safe_title}.vpr"),
    }
    if fmt == "wav":
        path = EXPORTS / f"{safe_title}.wav"
        export_master_wav(project, path)
    elif fmt == "mp4":
        wav = EXPORTS / f"{safe_title}.wav"
        if not wav.exists():
            export_master_wav(project, wav)
        path = EXPORTS / f"{safe_title}.mp4"
        export_lyrics_video(project, wav, path)
    elif fmt in mapping:
        func, path = mapping[fmt]
        func(project, path)
    else:
        raise HTTPException(400, f"unsupported export format: {fmt}")
    return FileResponse(str(path), filename=path.name)


def mount_frontend() -> None:
    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")


mount_frontend()


def run() -> None:
    uvicorn.run("openace.server.app:app", host="127.0.0.1", port=int(os.environ.get("OPENACE_PORT", "8787")), reload=False)


if __name__ == "__main__":
    run()
