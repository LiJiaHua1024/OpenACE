import asyncio
import time

import numpy as np
import soundfile as sf

from openace.core.models import Note, RenderJobStatus, RenderMode
from openace.core.project_store import ProjectStore
from openace.core.render_fingerprint import vocal_render_input_hash
from openace.server.render_service import RenderService


def test_vocal_render_completion_does_not_overwrite_concurrent_user_edits(tmp_path):
    service = RenderService(ProjectStore(tmp_path / "projects"), tmp_path / "renders")
    project = service.store.create("completion merge")
    track = project.tracks[0]
    track.notes = [Note(start_ticks=0, duration_ticks=480, pitch=60, lyric="原")]
    service.store.save(project)

    class SlowEngine:
        def render_score(self, project, track, output_path, cancellation=None, progress=None):
            time.sleep(0.25)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sr = 24000
            sf.write(str(output_path), np.zeros(sr // 2, dtype=np.float32), sr, subtype="PCM_24")

    service.vocal_engine = SlowEngine()
    job = service.create_job(project.id, RenderMode.SVS_SCORE, track.id)

    async def run_test():
        task = asyncio.create_task(service.run_vocal_render(job.id))
        for _ in range(100):
            if service.jobs[job.id].status == RenderJobStatus.RUNNING:
                break
            await asyncio.sleep(0.01)
        latest = service.store.get(project.id)
        latest.tracks[0].notes[0].lyric = "改"
        service.store.save(latest)
        return await asyncio.wait_for(task, timeout=5)

    result = asyncio.run(run_test())

    assert result.status == RenderJobStatus.COMPLETED
    reloaded = service.store.get(project.id)
    assert reloaded.tracks[0].notes[0].lyric == "改"
    assert reloaded.tracks[0].render_path == result.output_path
    assert reloaded.tracks[0].render_fingerprint != vocal_render_input_hash(reloaded, reloaded.tracks[0])
