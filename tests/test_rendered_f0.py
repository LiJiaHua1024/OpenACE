import json

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

import openace.server.app as app_module
from openace.core.diagnostics import write_f0_json
from openace.core.models import Note
from openace.core.project_store import ProjectStore
from openace.core.render_fingerprint import vocal_render_input_hash
from openace.server.render_service import RenderService


def test_write_f0_json_serializes_unvoiced_frames_as_null(tmp_path):
    output = tmp_path / "f0.json"
    write_f0_json(output, np.array([0.0, 0.01, 0.02]), np.array([220.0, np.nan, 0.0]))
    payload = json.loads(output.read_text())
    assert payload["frame_ms"] == 10.0
    assert payload["times"] == [0.0, 0.01, 0.02]
    assert payload["f0_hz"] == [220.0, None, None]


def test_rendered_f0_endpoint_requires_fresh_render_and_serves_cache(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    service = RenderService(store, tmp_path / "renders")
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "render_service", service)
    client = TestClient(app_module.app)

    project = store.create("rendered f0")
    track = project.tracks[0]
    track.add_note(Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="la"))
    render_dir = tmp_path / "renders" / project.id / "job_test"
    render_dir.mkdir(parents=True)
    wav = render_dir / "vocal.wav"
    sf.write(str(wav), np.zeros(2400, dtype=np.float32), 24000)
    write_f0_json(render_dir / "f0.json", [0.0, 0.01, 0.02], [261.63, None, 262.0])
    track.render_path = str(wav)
    track.render_revision = 1
    track.render_fingerprint = vocal_render_input_hash(project, track)
    store.save(project)

    response = client.get(f"/api/projects/{project.id}/tracks/{track.id}/rendered-f0")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "fresh-rendered-f0"
    assert payload["f0_hz"] == [261.63, None, 262.0]

    stale = store.get(project.id)
    stale.tracks[0].notes[0].pitch = 61
    store.save(stale)
    response = client.get(f"/api/projects/{project.id}/tracks/{track.id}/rendered-f0")
    assert response.status_code == 409
    assert "stale" in response.text
