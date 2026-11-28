import time

from fastapi.testclient import TestClient

import openace.server.app as app_module
from openace.core.models import AudioClip, RenderJob, RenderJobStatus, RenderMode, Track, TrackType
from openace.core.project_store import ProjectStore
from openace.server.render_service import RenderService


def make_client(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    service = RenderService(store, tmp_path / "renders")
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "render_service", service)
    return TestClient(app_module.app), store, service


def put(client, project):
    response = client.put(f"/api/projects/{project.id}", json=project.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    return response.json()


def test_stale_autosave_preserves_render_metadata_and_user_edit(tmp_path, monkeypatch):
    client, store, _ = make_client(tmp_path, monkeypatch)
    project = store.create("conflict safe")
    stale = project.model_copy(deep=True)
    stale.updated_at = time.time() - 10

    current = store.get(project.id)
    current.tracks[0].render_path = "/renders/p/job_x/vocal.wav"
    current.tracks[0].render_revision = 7
    current.tracks[0].render_fingerprint = "abc123"
    store.save(current)

    stale.title = "user edit"
    payload = put(client, stale)
    assert payload["title"] == "user edit"
    assert payload["tracks"][0]["render_path"] == "/renders/p/job_x/vocal.wav"
    assert payload["tracks"][0]["render_revision"] == 7
    assert payload["tracks"][0]["render_fingerprint"] == "abc123"


def test_stale_autosave_preserves_unacknowledged_job_created_track_but_aware_delete_wins(tmp_path, monkeypatch):
    client, store, service = make_client(tmp_path, monkeypatch)
    project = store.create("generated merge")
    stale = project.model_copy(deep=True)
    stale.updated_at = time.time() - 10

    current = store.get(project.id)
    generated = Track(name="SVC — source", type=TrackType.AUDIO, created_by_job_id="job_svc")
    generated.clips.append(AudioClip(path=f"/renders/{project.id}/job_svc/svc.wav", created_by_job_id="job_svc"))
    current.tracks.append(generated)
    store.save(current)
    service.jobs["job_svc"] = RenderJob(
        id="job_svc", project_id=project.id, mode=RenderMode.SVC,
        status=RenderJobStatus.COMPLETED, finished_at=time.time(), output_path=f"/renders/{project.id}/job_svc/svc.wav",
    )

    stale.title = "keep generated"
    payload = put(client, stale)
    assert payload["title"] == "keep generated"
    assert any(track["created_by_job_id"] == "job_svc" for track in payload["tracks"])

    aware = store.get(project.id)
    aware.tracks = [track for track in aware.tracks if track.created_by_job_id != "job_svc"]
    aware.touch()
    payload = put(client, aware)
    assert not any(track.get("created_by_job_id") == "job_svc" for track in payload["tracks"])


def test_stale_autosave_merges_repaint_output_without_losing_user_clip_edits(tmp_path, monkeypatch):
    client, store, service = make_client(tmp_path, monkeypatch)
    project = store.create("repaint merge")
    accompaniment = project.add_track(Track(name="BGM", type=TrackType.ACCOMPANIMENT))
    clip = AudioClip(path="/uploads/old.wav", start_ticks=240, duration_ticks=480, gain_db=-3.0)
    accompaniment.clips.append(clip)
    store.save(project)
    stale = store.get(project.id)
    stale.updated_at = time.time() - 10
    stale.tracks[-1].clips[0].start_ticks = 480

    current = store.get(project.id)
    current_clip = current.tracks[-1].clips[0]
    current_clip.path = f"/renders/{project.id}/job_repaint/accompaniment.wav"
    current_clip.duration_ticks = 960
    current_clip.label = "Repaint"
    current_clip.updated_by_job_id = "job_repaint"
    store.save(current)
    service.jobs["job_repaint"] = RenderJob(
        id="job_repaint", project_id=project.id, mode=RenderMode.REPAINT,
        status=RenderJobStatus.COMPLETED, finished_at=time.time(), output_path=current_clip.path,
    )

    payload = put(client, stale)
    merged = payload["tracks"][-1]["clips"][0]
    assert merged["path"].endswith("job_repaint/accompaniment.wav")
    assert merged["duration_ticks"] == 960
    assert merged["label"] == "Repaint"
    assert merged["start_ticks"] == 480
    assert merged["gain_db"] == -3.0
    assert merged["updated_by_job_id"] == "job_repaint"
