import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_backend_restart_automatically_requeues_interrupted_vocal_job(tmp_path):
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update({
        "OPENACE_DATA_DIR": str(tmp_path),
        "OPENACE_CI_SYNTH_FIXTURE": "1",
        "OPENACE_PORT": str(port),
        "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
    })

    def start_server():
        return subprocess.Popen(
            [sys.executable, "-m", "openace.server.app"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def request(path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            base + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read())

    def wait_health():
        for _ in range(80):
            try:
                request("/api/health")
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("server did not start")

    proc = start_server()
    wait_health()
    try:
        project = request("/api/projects", {"title": "Recovery Proof"})
        track = project["tracks"][0]
        request(
            f"/api/projects/{project['id']}/tracks/{track['id']}/notes",
            {"start_ticks": 0, "duration_ticks": 480, "pitch": 60, "lyric": "你", "velocity": 90},
        )
        job = request(f"/api/projects/{project['id']}/render/vocal", {"track_id": track["id"]})
    finally:
        proc.kill()
        proc.wait(timeout=5)

    jobs_path = tmp_path / "renders/jobs.json"
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    for item in jobs:
        if item["id"] == job["id"]:
            item["status"] = "running"
            item["progress"] = 0.42
            item["message"] = "rendering before power loss"
            item["output_path"] = None
            item["diagnostic_path"] = None
            item["finished_at"] = None
    jobs_path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")

    proc = start_server()
    wait_health()
    try:
        deadline = time.time() + 15
        final = None
        while time.time() < deadline:
            final = request(f"/api/jobs/{job['id']}")
            if final["status"] in {"completed", "failed"}:
                break
            time.sleep(0.15)
        assert final is not None
        evidence = {
            "job_id": job["id"],
            "final_status": final["status"],
            "message": final["message"],
            "output_exists": bool(final.get("output_path")) and Path(final["output_path"]).exists(),
            "diagnostic_exists": bool(final.get("diagnostic_path")) and Path(final["diagnostic_path"]).exists(),
            "project_id": project["id"],
        }
        artifact = ROOT / "artifacts/e2e_screenshots/render_recovery_proof.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        assert final["status"] == "completed", final
        assert evidence["output_exists"]
        assert evidence["diagnostic_exists"]
    finally:
        proc.kill()
        proc.wait(timeout=5)
