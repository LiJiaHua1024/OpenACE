from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from openace.core import editing
from openace.core.models import Note, RenderMode, Track, new_id
from openace.core.phonemes import ensure_note_phonemes
from openace.core.pitch import transpose_notes_preserve_intervals
from openace.core.media_library import delete_media_file, list_media, place_media_clip
from openace.core.project_store import ProjectStore, normalize_project_folders, normalize_project_tags
from openace.core.timing import validate_absolute_beat_anchor
from openace.exporters.master import export_master_wav
from openace.importers.audio import project_from_audio
from openace.importers.midi import import_midi
from openace.exporters.midi_lrc import export_lrc, export_midi
from openace.exporters.svp import export_svp
from openace.exporters.ustx import export_ustx
from openace.exporters.vpr import export_vpr
from openace.server.render_service import RenderService

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("OPENACE_DATA_DIR", ROOT / "data"))


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def services() -> tuple[ProjectStore, RenderService]:
    store = ProjectStore(DATA / "projects")
    return store, RenderService(store, DATA / "renders")


def notify_web(project) -> None:
    try:
        import urllib.request

        body = json.dumps(project.model_dump(mode="json")).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:8787/api/internal/project-updated",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=0.25).read()
    except Exception:
        pass


def notify_project_deleted(project_id: str) -> None:
    try:
        import urllib.request

        body = json.dumps({"project_id": project_id}).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:8787/api/internal/project-deleted",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=0.25).read()
    except Exception:
        pass


def notify_media(media: dict, action: str) -> None:
    try:
        import urllib.request
        body = json.dumps({"action": action, "media": media}).encode("utf-8")
        request = urllib.request.Request("http://127.0.0.1:8787/api/internal/media-updated", data=body, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(request, timeout=0.25).read()
    except Exception:
        pass


def save_and_notify(store: ProjectStore, project) -> None:
    store.save(project)
    notify_web(project)


def json_payload(raw: str):
    candidate = Path(raw)
    try:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    except OSError:
        # Inline JSON can exceed host filename limits; it is payload text, not a path.
        pass
    return json.loads(raw)


def cmd_create_project(args) -> None:
    store, _ = services()
    project = store.create(args.title)
    notify_web(project)
    emit(project.model_dump(mode="json"))


def cmd_duplicate_project(args) -> None:
    store, _ = services()
    source = store.get(args.project)
    duplicate = type(source).model_validate(source.model_dump())
    duplicate.id = new_id("project")
    duplicate.title = args.title or f"{source.title} Copy"
    duplicate.metadata = dict(source.metadata or {})
    duplicate.metadata["pinned"] = False
    save_and_notify(store, duplicate)
    emit(duplicate.model_dump(mode="json"))


def cmd_organize_project(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    metadata = dict(project.metadata or {})
    if args.pinned is not None:
        metadata["pinned"] = args.pinned == "true"
    if args.tags is not None:
        metadata["tags"] = normalize_project_tags(args.tags.split(","))
    if args.folders is not None:
        metadata["folders"] = normalize_project_folders(args.folders.split(","))
    project.metadata = metadata
    project.save(store.path_for(project.id))
    notify_web(project)
    emit(project.model_dump(mode="json"))


def cmd_delete_project(args) -> None:
    store, _ = services()
    if not store.delete(args.project):
        raise SystemExit("project not found")
    notify_project_deleted(args.project)
    emit({"deleted": True, "project": args.project})


def cmd_import_audio(args) -> None:
    store, _ = services()
    source = Path(args.path)
    if not source.exists():
        raise SystemExit(f"audio file does not exist: {source}")
    project = project_from_audio(source, args.title)
    save_and_notify(store, project)
    emit(project.model_dump(mode="json"))


def cmd_add_track(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    track = project.add_track(Track(name=args.name, language=args.language))
    save_and_notify(store, project)
    emit(track.model_dump(mode="json"))


def cmd_add_note(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    track = project.track(args.track)
    note = track.add_note(
        Note(
            start_ticks=args.start,
            duration_ticks=args.duration,
            pitch=args.pitch,
            lyric=args.lyric,
            velocity=args.velocity,
        )
    )
    if args.lyric:
        ensure_note_phonemes(note, track.language, project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0)
    validate_absolute_beat_anchor(track.notes, project.ppq, project.bpm, project=project)
    save_and_notify(store, project)
    emit(note.model_dump(mode="json"))


def cmd_validate(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    result = {"project": project.id, "tracks": []}
    for track in project.tracks:
        for note in track.notes:
            if note.lyric:
                ensure_note_phonemes(note, track.language, project.tick_duration_seconds(note.start_ticks, note.duration_ticks) * 1000.0)
        anchors = validate_absolute_beat_anchor(track.notes, project.ppq, project.bpm, project=project)
        result["tracks"].append({"track": track.id, "notes": len(track.notes), "anchors": len(anchors)})
    store.save(project)
    emit(result)


def cmd_transpose(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    track = project.track(args.track)
    mapping = transpose_notes_preserve_intervals(track.notes, args.semitones)
    lookup = dict(mapping)
    for note in track.notes:
        note.pitch = lookup[note.id]
    save_and_notify(store, project)
    emit({"updated": len(mapping), "intervals": "preserved"})


def cmd_render_vocal(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.SVS_SCORE, args.track)
    result = asyncio.run(service.run_vocal_render(job.id))
    notify_web(store.get(args.project))
    emit(result.model_dump(mode="json"))


def cmd_vocal2bgm(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.VOCAL2BGM, args.track, source_audio=args.source_audio, caption=args.caption)
    result = asyncio.run(service.run_music_generation(job.id, args.source_audio, args.caption))
    notify_web(store.get(args.project))
    emit(result.model_dump(mode="json"))


def cmd_repaint(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.REPAINT, args.track, source_audio=args.source_audio, caption=args.caption, start_s=args.start, end_s=args.end)
    result = asyncio.run(service.run_music_generation(job.id, args.source_audio, args.caption, args.start, args.end))
    notify_web(store.get(args.project))
    emit(result.model_dump(mode="json"))


def cmd_separate(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.SEPARATE, args.track, source_audio=args.source_audio)
    result = asyncio.run(service.run_separation(job.id, args.source_audio))
    notify_web(store.get(args.project))
    emit(result.model_dump(mode="json"))


def cmd_svc(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.SVC, args.track, source_audio=args.source_audio, reference_voice=args.reference_voice)
    result = asyncio.run(service.run_svc(job.id, args.source_audio, args.reference_voice))
    notify_web(store.get(args.project))
    emit(result.model_dump(mode="json"))


def cmd_export(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    output = Path(args.output)
    if args.format == "mid":
        export_midi(project, output)
    elif args.format == "lrc":
        export_lrc(project, output)
    elif args.format == "ustx":
        export_ustx(project, output)
    elif args.format == "svp":
        export_svp(project, output)
    elif args.format == "vpr":
        export_vpr(project, output)
    elif args.format == "wav":
        export_master_wav(project, output)
    else:
        raise SystemExit(f"unsupported format {args.format}")
    emit({"output": str(output), "format": args.format, "bytes": output.stat().st_size})


def cmd_batch_add_notes(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    added = editing.add_notes(project, args.track, json_payload(args.notes_json))
    save_and_notify(store, project)
    emit([note.model_dump(mode="json") for note in added])


def cmd_update_note(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    note = editing.update_note(project, args.track, args.note, json_payload(args.patch_json))
    save_and_notify(store, project)
    emit(note.model_dump(mode="json"))


def cmd_split_note(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    first, second = editing.split_note(project, args.track, args.note, args.split_ticks)
    save_and_notify(store, project)
    emit({"first": first.model_dump(mode="json"), "second": second.model_dump(mode="json")})


def cmd_ripple_delete_range(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    result = editing.ripple_delete_time_range(project, args.start_ticks, args.end_ticks)
    save_and_notify(store, project)
    emit(result)


def cmd_delete_note(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    if not editing.delete_note(project, args.track, args.note):
        raise SystemExit("note not found")
    save_and_notify(store, project)
    emit({"deleted": True, "note": args.note})


def cmd_set_expression(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    points = editing.set_automation_lane(project, args.track, args.lane, json_payload(args.points_json))
    save_and_notify(store, project)
    emit([point.model_dump(mode="json") for point in points])


def cmd_upsert_breath(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    breath = editing.upsert_breath(project, args.track, json_payload(args.breath_json), args.breath_id)
    save_and_notify(store, project)
    emit(breath.model_dump(mode="json"))


def cmd_delete_breath(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    if not editing.delete_breath(project, args.track, args.breath):
        raise SystemExit("breath not found")
    save_and_notify(store, project)
    emit({"deleted": True, "breath": args.breath})


def cmd_list_media(args) -> None:
    emit(list_media(DATA / "uploads"))


def cmd_place_media_clip(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    track, clip = place_media_clip(store, project, DATA / "uploads", args.media_name, args.start_ticks, args.track_id)
    notify_web(project)
    emit({"track": track.model_dump(mode="json"), "clip": clip.model_dump(mode="json")})


def cmd_delete_media(args) -> None:
    store, _ = services()
    entry = delete_media_file(store, DATA / "uploads", args.media_name)
    notify_media(entry, "deleted")
    emit({"ok": True, "deleted": entry})


def cmd_upsert_clip(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    clip = editing.upsert_audio_clip(project, args.track, json_payload(args.clip_json), args.clip_id)
    save_and_notify(store, project)
    emit(clip.model_dump(mode="json"))


def cmd_delete_clip(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    if not editing.delete_audio_clip(project, args.track, args.clip):
        raise SystemExit("clip not found")
    save_and_notify(store, project)
    emit({"deleted": True, "clip": args.clip})


def cmd_set_tempo(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    points = json_payload(args.points_json) if args.points_json else []
    tempo_map = editing.set_tempo_map(project, args.bpm, points)
    save_and_notify(store, project)
    emit({"bpm": project.bpm, "tempo_map": [point.model_dump(mode="json") for point in tempo_map]})


def cmd_assign_voice(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    result = editing.assign_voice(project, args.track, args.voice_id, args.reference_voice)
    save_and_notify(store, project)
    emit(result)


def cmd_import_midi(args) -> None:
    store, _ = services()
    project = import_midi(Path(args.path), title=args.title)
    save_and_notify(store, project)
    emit(project.model_dump(mode="json"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openace-tool", description="OpenACE atomic local CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-project")
    p.add_argument("--title", default="Untitled OpenACE Project")
    p.set_defaults(func=cmd_create_project)

    p = sub.add_parser("duplicate-project")
    p.add_argument("project")
    p.add_argument("--title")
    p.set_defaults(func=cmd_duplicate_project)

    p = sub.add_parser("organize-project")
    p.add_argument("project")
    p.add_argument("--pinned", choices=["true", "false"])
    p.add_argument("--tags", help="comma-separated project tags")
    p.add_argument("--folders", help="comma-separated project folders")
    p.set_defaults(func=cmd_organize_project)

    p = sub.add_parser("delete-project")
    p.add_argument("project")
    p.set_defaults(func=cmd_delete_project)

    p = sub.add_parser("add-track")
    p.add_argument("project")
    p.add_argument("--name", required=True)
    p.add_argument("--language", default="zh")
    p.set_defaults(func=cmd_add_track)

    p = sub.add_parser("add-note")
    p.add_argument("project")
    p.add_argument("track")
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--duration", type=int, required=True)
    p.add_argument("--pitch", type=int, required=True)
    p.add_argument("--lyric", default="")
    p.add_argument("--velocity", type=int, default=90)
    p.set_defaults(func=cmd_add_note)

    p = sub.add_parser("validate")
    p.add_argument("project")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("transpose")
    p.add_argument("project")
    p.add_argument("track")
    p.add_argument("semitones", type=int)
    p.set_defaults(func=cmd_transpose)

    p = sub.add_parser("render-vocal")
    p.add_argument("project")
    p.add_argument("track")
    p.set_defaults(func=cmd_render_vocal)

    p = sub.add_parser("vocal2bgm")
    p.add_argument("project")
    p.add_argument("source_audio")
    p.add_argument("--track", default=None)
    p.add_argument("--caption", default="professional instrumental accompaniment")
    p.set_defaults(func=cmd_vocal2bgm)

    p = sub.add_parser("repaint")
    p.add_argument("project")
    p.add_argument("source_audio")
    p.add_argument("--track", default=None)
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--caption", default="")
    p.set_defaults(func=cmd_repaint)

    p = sub.add_parser("separate")
    p.add_argument("project")
    p.add_argument("source_audio")
    p.add_argument("--track", default=None)
    p.set_defaults(func=cmd_separate)

    p = sub.add_parser("svc")
    p.add_argument("project")
    p.add_argument("source_audio")
    p.add_argument("reference_voice")
    p.add_argument("--track", default=None)
    p.set_defaults(func=cmd_svc)

    p = sub.add_parser("batch-add-notes")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("notes_json")
    p.set_defaults(func=cmd_batch_add_notes)

    p = sub.add_parser("update-note")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("note"); p.add_argument("patch_json")
    p.set_defaults(func=cmd_update_note)

    p = sub.add_parser("list-media")
    p.set_defaults(func=cmd_list_media)

    p = sub.add_parser("place-media-clip")
    p.add_argument("project")
    p.add_argument("media_name")
    p.add_argument("--start-ticks", type=int, default=0)
    p.add_argument("--track-id")
    p.set_defaults(func=cmd_place_media_clip)

    p = sub.add_parser("delete-media")
    p.add_argument("media_name")
    p.set_defaults(func=cmd_delete_media)

    p = sub.add_parser("split-note")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("note"); p.add_argument("split_ticks", type=int)
    p.set_defaults(func=cmd_split_note)

    p = sub.add_parser("ripple-delete-range")
    p.add_argument("project")
    p.add_argument("start_ticks", type=int)
    p.add_argument("end_ticks", type=int)
    p.set_defaults(func=cmd_ripple_delete_range)

    p = sub.add_parser("delete-note")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("note")
    p.set_defaults(func=cmd_delete_note)

    p = sub.add_parser("set-expression")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("lane", choices=sorted(editing.AUTOMATION_KEYS)); p.add_argument("points_json")
    p.set_defaults(func=cmd_set_expression)

    p = sub.add_parser("upsert-breath")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("breath_json"); p.add_argument("--breath-id")
    p.set_defaults(func=cmd_upsert_breath)

    p = sub.add_parser("delete-breath")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("breath")
    p.set_defaults(func=cmd_delete_breath)

    p = sub.add_parser("upsert-clip")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("clip_json"); p.add_argument("--clip-id")
    p.set_defaults(func=cmd_upsert_clip)

    p = sub.add_parser("delete-clip")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("clip")
    p.set_defaults(func=cmd_delete_clip)

    p = sub.add_parser("set-tempo")
    p.add_argument("project"); p.add_argument("--bpm", type=float); p.add_argument("--points-json")
    p.set_defaults(func=cmd_set_tempo)

    p = sub.add_parser("assign-voice")
    p.add_argument("project"); p.add_argument("track"); p.add_argument("voice_id"); p.add_argument("--reference-voice")
    p.set_defaults(func=cmd_assign_voice)

    p = sub.add_parser("import-audio")
    p.add_argument("path"); p.add_argument("--title")
    p.set_defaults(func=cmd_import_audio)

    p = sub.add_parser("import-midi")
    p.add_argument("path"); p.add_argument("--title")
    p.set_defaults(func=cmd_import_midi)

    p = sub.add_parser("export")
    p.add_argument("project")
    p.add_argument("format", choices=["mid", "lrc", "ustx", "svp", "vpr", "wav"])
    p.add_argument("output")
    p.set_defaults(func=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:
        emit({"error": str(exc), "type": type(exc).__name__})
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
