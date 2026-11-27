from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from openace.core.models import Note, RenderMode, Track
from openace.core.phonemes import ensure_note_phonemes
from openace.core.pitch import transpose_notes_preserve_intervals
from openace.core.project_store import ProjectStore
from openace.core.timing import validate_absolute_beat_anchor
from openace.exporters.master import export_master_wav
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


def cmd_create_project(args) -> None:
    store, _ = services()
    emit(store.create(args.title).model_dump(mode="json"))


def cmd_add_track(args) -> None:
    store, _ = services()
    project = store.get(args.project)
    track = project.add_track(Track(name=args.name, language=args.language))
    store.save(project)
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
    store.save(project)
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
    store.save(project)
    emit({"updated": len(mapping), "intervals": "preserved"})


def cmd_render_vocal(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.SVS_SCORE, args.track)
    emit(asyncio.run(service.run_vocal_render(job.id)).model_dump(mode="json"))


def cmd_vocal2bgm(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.VOCAL2BGM, args.track, source_audio=args.source_audio, caption=args.caption)
    emit(asyncio.run(service.run_music_generation(job.id, args.source_audio, args.caption)).model_dump(mode="json"))


def cmd_repaint(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.REPAINT, args.track, source_audio=args.source_audio, caption=args.caption, start_s=args.start, end_s=args.end)
    emit(asyncio.run(service.run_music_generation(job.id, args.source_audio, args.caption, args.start, args.end)).model_dump(mode="json"))


def cmd_svc(args) -> None:
    store, service = services()
    job = service.create_job(args.project, RenderMode.SVC, args.track, source_audio=args.source_audio, reference_voice=args.reference_voice)
    emit(asyncio.run(service.run_svc(job.id, args.source_audio, args.reference_voice)).model_dump(mode="json"))


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openace-tool", description="OpenACE atomic local CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-project")
    p.add_argument("--title", default="Untitled OpenACE Project")
    p.set_defaults(func=cmd_create_project)

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

    p = sub.add_parser("svc")
    p.add_argument("project")
    p.add_argument("source_audio")
    p.add_argument("reference_voice")
    p.add_argument("--track", default=None)
    p.set_defaults(func=cmd_svc)

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
