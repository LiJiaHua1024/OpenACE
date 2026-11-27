from fastapi.testclient import TestClient

import openace.server.app as app_module
from openace.core.project_store import ProjectStore


def test_project_organization_pin_tags_and_duplicate_semantics(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "store", store)
    older = store.create("Older")
    newer = store.create("Newer")
    newer.updated_at = older.updated_at + 10
    newer.save(store.path_for(newer.id))
    client = TestClient(app_module.app)

    response = client.patch(
        f"/api/projects/{older.id}/organization",
        json={"pinned": True, "tags": [" demo ", "Lead", "demo", "", "x" * 40]},
    )
    assert response.status_code == 200, response.text
    metadata = response.json()["metadata"]
    assert metadata["pinned"] is True
    assert metadata["tags"] == ["demo", "Lead", "x" * 32]

    listing = client.get("/api/projects").json()
    by_id = {item["id"]: item for item in listing}
    assert by_id[older.id]["pinned"] is True
    assert by_id[older.id]["tags"] == ["demo", "Lead", "x" * 32]
    assert listing[0]["id"] == older.id

    duplicate = client.post(f"/api/projects/{older.id}/duplicate").json()
    assert duplicate["metadata"]["pinned"] is False
    assert duplicate["metadata"]["tags"] == metadata["tags"]

    response = client.patch(f"/api/projects/{older.id}/organization", json={"pinned": False})
    assert response.status_code == 200
    listing = client.get("/api/projects").json()
    assert listing[0]["id"] == newer.id


def test_mcp_organize_project_updates_metadata_without_touching_updated_at(tmp_path, monkeypatch):
    import openace.mcp_server as mcp_server

    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(mcp_server, "store", store)
    project = store.create("MCP organize")
    original_updated_at = project.updated_at
    import json
    payload = json.loads(mcp_server.organize_project(project.id, pinned=True, tags=["mcp", "mcp", "mix"]))
    assert payload["metadata"]["pinned"] is True
    assert payload["metadata"]["tags"] == ["mcp", "mix"]
    assert payload["updated_at"] == original_updated_at
