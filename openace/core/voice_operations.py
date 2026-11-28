"""Shared voice-library operations for API, CLI, and MCP surfaces."""
from __future__ import annotations

from typing import Callable, List, Tuple

from openace.core.models import Project
from openace.core.project_store import ProjectStore
from openace.core.voice_library import VoiceLibrary, VoiceProfile


def scan_voice_usage(store: ProjectStore, voice: VoiceProfile) -> List[Tuple[Project, object]]:
    """Find project tracks that reference a voice by id or by its audio path."""
    usages: List[Tuple[Project, object]] = []
    for path in sorted(store.root.glob("*.openace.json")):
        try:
            project = Project.load(path)
        except Exception:
            continue
        for track in project.tracks:
            if track.voice_id == voice.id or track.reference_voice_path == voice.path:
                usages.append((project, track))
    return usages


def delete_voice_with_project_cleanup(
    store: ProjectStore,
    voice_library: VoiceLibrary,
    voice_id: str,
    unassign: bool = False,
    publish_project: Callable[[Project], None] | None = None,
) -> dict:
    """Delete a voice, either rejecting active use or explicitly unassigning it.

    The voice metadata/audio are removed only after every affected project has been
    durably saved, so a failed unassignment cannot silently strand the library state.
    """
    voice = voice_library.get(voice_id)
    usages = scan_voice_usage(store, voice)
    if usages and not unassign:
        project, track = usages[0]
        raise RuntimeError(f"voice is in use by project '{project.title}' track '{track.name}'")
    if usages:
        changed_projects = {project.id: project for project, _ in usages}
        for project in changed_projects.values():
            changed = False
            for track in project.tracks:
                if track.voice_id == voice.id:
                    track.voice_id = ""
                    changed = True
                if track.reference_voice_path == voice.path:
                    track.reference_voice_path = None
                    changed = True
            if changed:
                store.save(project)
                if publish_project:
                    publish_project(project)
    deleted = voice_library.delete(voice_id)
    return {"deleted": deleted.model_dump(mode="json"), "unassigned": len(usages)}
