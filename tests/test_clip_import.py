from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

import openace.server.app as app_module
from openace.core.models import Project
from openace.core.project_store import ProjectStore


def test_import_audio_clip_creates_measured_arrangement_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "UPLOADS", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    project = store.create("Clip import")
    source = tmp_path / "source.wav"
    sf.write(source, np.zeros(24000, dtype=np.float32), 24000)
    client = TestClient(app_module.app)
    with source.open("rb") as handle:
        response = client.post(f"/api/projects/{project.id}/clips/import", data={"start_ticks":"480"}, files={"file": ("source.wav", handle, "audio/wav")})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["clip"]["duration_ticks"] == 960
    assert payload["clip"]["start_ticks"] == 480
    assert payload["track"]["type"] == "audio"
    stored = store.get(project.id)
    assert stored.tracks[-1].clips[0].path == payload["clip"]["path"]
    # The StaticFiles mount is intentionally bound to the production upload root at
    # app construction time; prove that route serves real uploaded audio bytes.
    original_upload_root = Path(app_module.DATA) / "uploads"
    original_upload_root.mkdir(parents=True, exist_ok=True)
    probe = original_upload_root / "clip_import_static_probe.wav"
    probe.write_bytes(Path(payload["clip"]["path"]).read_bytes())
    try:
        static_response = client.get("/uploads/" + probe.name)
        assert static_response.status_code == 200
        assert len(static_response.content) > 44
    finally:
        probe.unlink(missing_ok=True)


def test_import_audio_clip_rejects_invalid_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "UPLOADS", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    project = store.create("Clip import invalid")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio")
    client = TestClient(app_module.app)
    with bad.open("rb") as handle:
        response = client.post(f"/api/projects/{project.id}/clips/import", files={"file": ("bad.wav", handle, "audio/wav")})
    assert response.status_code == 422


def test_import_audio_clip_rejects_vocal_target_and_upload_names_are_unique(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "UPLOADS", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    project = store.create("Clip target validation")
    source = tmp_path / "source.wav"
    sf.write(source, np.zeros(2400, dtype=np.float32), 24000)
    client = TestClient(app_module.app)
    vocal_track = project.tracks[0]
    with source.open("rb") as handle:
        response = client.post(
            f"/api/projects/{project.id}/clips/import",
            data={"track_id": vocal_track.id},
            files={"file": ("source.wav", handle, "audio/wav")},
        )
    assert response.status_code == 422
    with source.open("rb") as one, source.open("rb") as two:
        first = client.post("/api/upload", files={"file": ("same.wav", one, "audio/wav")})
        second = client.post("/api/upload", files={"file": ("same.wav", two, "audio/wav")})
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["path"] != second.json()["path"]
