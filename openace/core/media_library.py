from __future__ import annotations

from pathlib import Path
from typing import Any

import soundfile as sf

from .models import AudioClip, Project, Track, TrackType
from .project_store import ProjectStore

AUDIO_MEDIA_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".aiff", ".aif"}


def resolve_media(root: Path, media_name: str) -> Path:
    path = (root / Path(media_name).name).resolve()
    if path.parent != root.resolve() or not path.exists() or not path.is_file():
        raise KeyError("media file not found")
    return path


def media_entry(path: Path) -> dict[str, Any]:
    parts = path.name.split("_", 2)
    entry: dict[str, Any] = {
        "id": path.name,
        "name": parts[2] if len(parts) == 3 else path.name,
        "file_name": path.name,
        "path": str(path),
        "size": path.stat().st_size,
        "modified_at": path.stat().st_mtime,
        "valid": False,
    }
    try:
        info = sf.info(path)
        entry.update(valid=bool(info.frames and info.samplerate > 0), duration_seconds=info.frames / info.samplerate if info.samplerate else 0.0, sample_rate=info.samplerate, channels=info.channels)
    except Exception as exc:
        entry["error"] = str(exc)
    return entry


def list_media(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    return [media_entry(path) for path in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True) if path.is_file() and path.suffix.lower() in AUDIO_MEDIA_EXTENSIONS]


def projects_using_media(store: ProjectStore, path: Path) -> list[str]:
    target = str(path.resolve())
    users = []
    for summary in store.list():
        try:
            project = store.get(summary["id"])
        except Exception:
            continue
        if any(str(Path(clip.path).resolve()) == target for track in project.tracks for clip in track.clips):
            users.append(project.id)
    return users


def place_media_clip(store: ProjectStore, project: Project, root: Path, media_name: str, start_ticks: int = 0, track_id: str | None = None):
    path = resolve_media(root, media_name)
    info = sf.info(path)
    if not info.frames or info.samplerate <= 0:
        raise ValueError("audio file has no samples")
    if track_id:
        track = project.track(track_id)
        if track.type == TrackType.VOCAL:
            raise ValueError("imported audio clips cannot be placed on vocal note tracks")
    else:
        track = project.add_track(Track(name=f"Audio — {Path(media_entry(path)['name']).stem}", type=TrackType.AUDIO, color="#ff8f5a"))
    duration_ticks = project.seconds_to_ticks(info.frames / info.samplerate)
    clip = AudioClip(path=str(path), start_ticks=max(0, int(start_ticks)), duration_ticks=duration_ticks, label=Path(media_entry(path)["name"]).stem)
    track.clips.append(clip)
    track.clips.sort(key=lambda item: item.start_ticks)
    store.save(project)
    return track, clip


def delete_media_file(store: ProjectStore, root: Path, media_name: str) -> dict[str, Any]:
    path = resolve_media(root, media_name)
    users = projects_using_media(store, path)
    if users:
        raise ValueError(f"media file is used by arrangement clips in {len(users)} project(s); remove those clips before deleting it")
    entry = media_entry(path)
    path.unlink()
    return entry
