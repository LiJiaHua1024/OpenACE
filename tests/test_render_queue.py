import asyncio

import pytest

from openace.core.models import RenderJobStatus, RenderMode
from openace.core.project_store import ProjectStore
from openace.server.render_service import RenderService


@pytest.mark.asyncio
async def test_server_render_queue_serializes_jobs_fifo(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("Queue proof")
    service = RenderService(store, tmp_path / "renders")
    first = service.create_job(project.id, RenderMode.SVS_SCORE, project.tracks[0].id)
    second = service.create_job(project.id, RenderMode.SVS_SCORE, project.tracks[0].id)
    events = []
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    async def fake_render(job_id):
        events.append(("start", job_id))
        if job_id == first.id:
            first_started.set()
            await release_first.wait()
        events.append(("end", job_id))
        service.jobs[job_id].status = RenderJobStatus.COMPLETED

    monkeypatch.setattr(service, "run_vocal_render", fake_render)
    service.enqueue_job(first.id)
    service.enqueue_job(second.id)
    await asyncio.wait_for(first_started.wait(), 1.0)
    await asyncio.sleep(0.02)
    assert events == [("start", first.id)]
    assert service.jobs[second.id].status == RenderJobStatus.QUEUED

    release_first.set()
    assert service._job_queue is not None
    await asyncio.wait_for(service._job_queue.join(), 2.0)
    await service.shutdown()
    assert events == [
        ("start", first.id),
        ("end", first.id),
        ("start", second.id),
        ("end", second.id),
    ]


@pytest.mark.asyncio
async def test_server_render_queue_continues_after_unexpected_runner_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    store = ProjectStore(tmp_path / "projects")
    project = store.create("Queue failure proof")
    service = RenderService(store, tmp_path / "renders")
    first = service.create_job(project.id, RenderMode.SVS_SCORE, project.tracks[0].id)
    second = service.create_job(project.id, RenderMode.SVS_SCORE, project.tracks[0].id)
    completed = []

    async def failing_render(job_id):
        if job_id == first.id:
            raise RuntimeError("synthetic queue failure")
        service.jobs[job_id].status = RenderJobStatus.COMPLETED
        completed.append(job_id)

    monkeypatch.setattr(service, "run_vocal_render", failing_render)
    service.enqueue_job(first.id)
    service.enqueue_job(second.id)
    assert service._job_queue is not None
    await asyncio.wait_for(service._job_queue.join(), 2.0)
    await service.shutdown()
    assert service.jobs[first.id].status == RenderJobStatus.FAILED
    assert "synthetic queue failure" in service.jobs[first.id].error
    assert completed == [second.id]
