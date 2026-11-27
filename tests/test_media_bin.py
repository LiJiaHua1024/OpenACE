from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

import openace.server.app as app_module
from openace.core.project_store import ProjectStore


def test_media_bin_lists_places_and_safely_deletes_audio(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(app_module, "UPLOADS", uploads)
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    project = store.create("Media bin")
    source = tmp_path / "take one.wav"
    sf.write(source, np.zeros(24000, dtype=np.float32), 24000)
    client = TestClient(app_module.app)

    with source.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": ("take one.wav", handle, "audio/wav")})
    assert upload.status_code == 200, upload.text
    media_name = Path(upload.json()["path"]).name

    listing = client.get("/api/media")
    assert listing.status_code == 200
    rows = {item["file_name"]: item for item in listing.json()}
    item = rows[media_name]
    assert item["name"] == "take one.wav"
    assert item["valid"] is True
    assert item["duration_seconds"] == 1.0
    assert item["sample_rate"] == 24000
    assert item["channels"] == 1

    placed = client.post(f"/api/projects/{project.id}/media/clip", json={"media_name": media_name, "start_ticks": 480})
    assert placed.status_code == 200, placed.text
    assert placed.json()["clip"]["duration_ticks"] == 960
    stored = store.get(project.id)
    assert stored.tracks[-1].type == "audio"
    assert stored.tracks[-1].clips[0].path == item["path"]

    blocked = client.delete(f"/api/media/{media_name}")
    assert blocked.status_code == 409
    client.delete(f"/api/projects/{project.id}")
    deleted = client.delete(f"/api/media/{media_name}")
    assert deleted.status_code == 200
    assert not (uploads / media_name).exists()
    assert media_name not in {row["file_name"] for row in client.get("/api/media").json()}


def test_media_bin_rejects_missing_media_invalid_audio_and_vocal_target(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(app_module, "UPLOADS", uploads)
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    project = store.create("Media validation")
    client = TestClient(app_module.app)

    assert client.post(f"/api/projects/{project.id}/media/clip", json={"media_name": "missing.wav"}).status_code == 404
    bad = uploads / "upload_bad_bad.wav"
    bad.write_bytes(b"not audio")
    listing = client.get("/api/media").json()
    row = next(item for item in listing if item["file_name"] == bad.name)
    assert row["valid"] is False
    assert client.post(f"/api/projects/{project.id}/media/clip", json={"media_name": bad.name}).status_code == 422

    source = tmp_path / "valid.wav"
    sf.write(source, np.zeros(1200, dtype=np.float32), 24000)
    with source.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": ("valid.wav", handle, "audio/wav")})
    media_name = Path(upload.json()["path"]).name
    vocal_target = client.post(
        f"/api/projects/{project.id}/media/clip",
        json={"media_name": media_name, "track_id": project.tracks[0].id},
    )
    assert vocal_target.status_code == 422
