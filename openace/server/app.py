from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from openace.core.models import Note, Project, RenderMode, Track, TrackType, new_id
from openace.core.phonemes import PhonemeError, ensure_note_phonemes, timed_phonemes, tokens_from_symbols
from openace.core.project_store import ProjectStore
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
recovery_tasks: set[asyncio.Task] = set()


@app.on_event("startup")
async def recover_interrupted_render_jobs():
    recovered = render_service.recover_interrupted_jobs()

    async def run_recovered_jobs():
        for recovered_job in recovered:
            await render_service.recovery_coro(recovered_job)

    if recovered:
        task = asyncio.create_task(run_recovered_jobs())
        recovery_tasks.add(task)
        task.add_done_callback(recovery_tasks.discard)


class CreateProjectRequest(BaseModel):
    title: str = "Untitled OpenACE Project"


class CreateTrackRequest(BaseModel):
    name: str
    type: TrackType = TrackType.VOCAL
    language: str = "zh"
    color: str = "#7c5cff"


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


@app.post("/api/projects/{project_id}/duplicate")
def duplicate_project(project_id: str):
    try:
        source = store.get(project_id)
    except KeyError as exc:
        raise HTTPException(404, "project not found") from exc
    duplicate = Project.model_validate(source.model_dump())
    duplicate.id = new_id("project")
    duplicate.title = f"{source.title} Copy"
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
async def render_vocal(project_id: str, request: RenderRequest, background: BackgroundTasks):
    if not request.track_id:
        raise HTTPException(400, "track_id is required")
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.SVS_SCORE, request.track_id)
    background.add_task(render_service.run_vocal_render, job.id)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/vocal2bgm")
async def render_vocal2bgm(project_id: str, request: RenderRequest, background: BackgroundTasks):
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.VOCAL2BGM, request.track_id, source_audio=request.source_audio, caption=request.caption)
    background.add_task(render_service.run_music_generation, job.id, request.source_audio, request.caption)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/repaint")
async def render_repaint(project_id: str, request: RenderRequest, background: BackgroundTasks):
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.REPAINT, request.track_id, source_audio=request.source_audio, caption=request.caption, start_s=request.start_s, end_s=request.end_s)
    background.add_task(render_service.run_music_generation, job.id, request.source_audio, request.caption, request.start_s, request.end_s)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/separate")
async def render_separation(project_id: str, request: RenderRequest, background: BackgroundTasks):
    get_project(project_id)
    if not request.source_audio:
        raise HTTPException(400, "source_audio is required")
    job = render_service.create_job(project_id, RenderMode.SEPARATE, request.track_id, source_audio=request.source_audio)
    background.add_task(render_service.run_separation, job.id, request.source_audio)
    return job.model_dump(mode="json")


@app.post("/api/projects/{project_id}/render/svc")
async def render_svc(project_id: str, request: RenderRequest, background: BackgroundTasks):
    get_project(project_id)
    job = render_service.create_job(project_id, RenderMode.SVC, request.track_id, source_audio=request.source_audio, reference_voice=request.reference_voice)
    background.add_task(render_service.run_svc, job.id, request.source_audio, request.reference_voice)
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
    destination = UPLOADS / safe
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return {"path": str(destination), "name": safe, "size": destination.stat().st_size}


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
