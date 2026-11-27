from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import Project, Track


def normalize_project_tags(values) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    tags = []
    for raw in values or []:
        tag = str(raw).strip()[:32]
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) >= 12:
            break
    return tags


def normalize_project_folders(values) -> list[str]:
    if isinstance(values, str):
        values = values.split(",")
    folders = []
    for raw in values or []:
        folder = str(raw).strip()[:48]
        if folder and folder not in folders:
            folders.append(folder)
        if len(folders) >= 8:
            break
    return folders


class ProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, project_id: str) -> Path:
        safe = "".join(ch for ch in project_id if ch.isalnum() or ch in {"_", "-"})
        return self.root / f"{safe}.openace.json"

    def create(self, title: str = "Untitled OpenACE Project") -> Project:
        project = Project(title=title)
        project.add_track(Track(name="Lead Vocal", color="#7367ff"))
        self.save(project)
        return project

    def save(self, project: Project) -> Project:
        project.touch()
        project.save(self.path_for(project.id))
        return project

    def get(self, project_id: str) -> Project:
        path = self.path_for(project_id)
        if not path.exists():
            raise KeyError(f"project not found: {project_id}")
        return Project.load(path)

    def list(self) -> List[dict]:
        projects = []
        for path in sorted(self.root.glob("*.openace.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                project = Project.load(path)
                metadata = project.metadata or {}
                tags = normalize_project_tags(metadata.get("tags", []))
                projects.append(
                    {
                        "id": project.id,
                        "title": project.title,
                        "bpm": project.bpm,
                        "track_count": len(project.tracks),
                        "updated_at": project.updated_at,
                        "pinned": bool(metadata.get("pinned")),
                        "tags": tags,
                        "folders": normalize_project_folders(metadata.get("folders", [])),
                    }
                )
            except Exception:
                continue
        projects.sort(key=lambda item: (not item["pinned"], -(item["updated_at"] or 0)))
        return projects

    def delete(self, project_id: str) -> bool:
        path = self.path_for(project_id)
        if path.exists():
            path.unlink()
            return True
        return False
