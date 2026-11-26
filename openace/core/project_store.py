from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import Project, Track


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
                projects.append(
                    {
                        "id": project.id,
                        "title": project.title,
                        "bpm": project.bpm,
                        "track_count": len(project.tracks),
                        "updated_at": project.updated_at,
                    }
                )
            except Exception:
                continue
        return projects

    def delete(self, project_id: str) -> bool:
        path = self.path_for(project_id)
        if path.exists():
            path.unlink()
            return True
        return False
