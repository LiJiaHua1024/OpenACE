import asyncio
import subprocess
import sys
import time

import pytest

from openace.core.models import RenderJobStatus
from openace.core.project_store import ProjectStore
from openace.engines.processes import CancellationToken, JobCancelled, run_cancellable
from openace.server.render_service import RenderService


def test_cancellable_subprocess_is_terminated():
    token = CancellationToken()
    started = time.time()
    result = {}

    def target():
        try:
            run_cancellable([sys.executable, "-c", "import time; time.sleep(30)"], token)
        except BaseException as exc:
            result["error"] = exc

    import threading
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    time.sleep(0.15)
    token.cancel()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert time.time() - started < 3
    assert isinstance(result.get("error"), JobCancelled)


def test_cancellable_subprocess_raises_job_cancelled():
    token = CancellationToken()
    token.cancel()
    with pytest.raises(JobCancelled):
        run_cancellable([sys.executable, "-c", "print('never')"], token)


def test_render_service_cancels_queued_job(tmp_path):
    service = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    project = service.store.create("cancel queued")
    job = service.create_job(project.id, mode=__import__("openace.core.models", fromlist=["RenderMode"]).RenderMode.SVS_SCORE, track_id=project.tracks[0].id)
    cancelled = service.cancel_job(job.id)
    assert cancelled.status == RenderJobStatus.CANCELED
    assert cancelled.message == "cancelled before engine start"
    reloaded = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    assert reloaded.jobs[job.id].status == RenderJobStatus.CANCELED


def test_render_service_cancels_running_engine_subprocess(tmp_path):
    service = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    project = service.store.create("cancel running")
    track = project.tracks[0]
    service.store.save(project)

    class SlowEngine:
        def render_score(self, project, track, output_path, cancellation=None, progress=None):
            run_cancellable([sys.executable, "-c", "import time; time.sleep(30)"], cancellation)

    service.vocal_engine = SlowEngine()
    job = service.create_job(project.id, mode=__import__("openace.core.models", fromlist=["RenderMode"]).RenderMode.SVS_SCORE, track_id=track.id)

    async def run_test():
        task = asyncio.create_task(service.run_vocal_render(job.id))
        for _ in range(100):
            if service.jobs[job.id].status == RenderJobStatus.RUNNING:
                break
            await asyncio.sleep(0.01)
        assert service.jobs[job.id].status == RenderJobStatus.RUNNING
        started = time.time()
        service.cancel_job(job.id)
        result = await asyncio.wait_for(task, timeout=4)
        assert time.time() - started < 4
        return result

    result = asyncio.run(run_test())
    assert result.status == RenderJobStatus.CANCELED
    assert result.error is None
    assert result.message == "cancelled"


def test_cancel_endpoint_and_conflict_states(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import openace.server.app as app_module

    service = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    monkeypatch.setattr(app_module, "render_service", service)
    client = TestClient(app_module.app)
    project = service.store.create("cancel api")
    job = service.create_job(project.id, mode=__import__("openace.core.models", fromlist=["RenderMode"]).RenderMode.SVS_SCORE, track_id=project.tracks[0].id)

    response = client.post(f"/api/jobs/{job.id}/cancel")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "canceled"
    assert client.post(f"/api/jobs/{job.id}/cancel").status_code == 409
    assert client.post("/api/jobs/job_missing/cancel").status_code == 404


def test_cli_cancel_queued_job_without_server(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    import openace.cli as cli

    monkeypatch.setenv("OPENACE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cli, "DATA", tmp_path)
    monkeypatch.setattr(cli, "server_cancel_job", lambda job_id: None)
    service = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    project = service.store.create("cli cancel")
    job = service.create_job(project.id, mode=__import__("openace.core.models", fromlist=["RenderMode"]).RenderMode.SVS_SCORE, track_id=project.tracks[0].id)

    cli.cmd_cancel_render_job(SimpleNamespace(job=job.id))
    output = capsys.readouterr().out
    assert '"status": "canceled"' in output
    reloaded = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    assert reloaded.jobs[job.id].status == RenderJobStatus.CANCELED
