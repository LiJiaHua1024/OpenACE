import asyncio

from openace.core.models import RenderMode, RenderJobStatus
from openace.core.project_store import ProjectStore
from openace.server.render_service import RenderService


def test_fixture_vocal_render_publishes_truthful_stage_progress(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_CI_SYNTH_FIXTURE", "1")
    service = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    project = service.store.create("progress")
    track = project.tracks[0]
    service.store.save(project)
    events = []
    original_publish = service._publish_job

    def capture(job):
        events.append((job.progress, job.message, job.status))
        original_publish(job)

    service._publish_job = capture
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)

    result = asyncio.run(service.run_vocal_render(job.id))

    assert result.status == RenderJobStatus.COMPLETED
    messages = [message for _, message, _ in events]
    assert any("fixture vocal synthesis stage" in message for message in messages)
    assert any("applying expression and breath post-processing" in message for message in messages)
    assert any("writing acoustic diagnostic" in message for message in messages)
    progresses = [progress for progress, message, status in events if status == RenderJobStatus.RUNNING and "post-processing" in message or status == RenderJobStatus.RUNNING and "diagnostic" in message]
    assert progresses and max(progresses) >= 0.92
    assert events[-1][0] == 1.0
