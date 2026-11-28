import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _wait_health(base: str, timeout: float = 10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{base}/api/health", timeout=0.5).status_code == 200:
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("test server did not become healthy")


def _note(note_id, start_ticks, vibrato):
    return {
        "id": note_id,
        "start_ticks": start_ticks,
        "duration_ticks": 480,
        "pitch": 65,
        "lyric": "啊",
        "velocity": 90,
        "phonemes": [],
        "pitch_curve": [],
        "pitch_snap_first": True,
        "pitch_modulation": 1,
        "vibrato": vibrato,
        "techniques": [],
    }


@pytest.mark.skipif(not (ROOT / "frontend/dist/index.html").exists(), reason="frontend production build required")
def test_vibrato_marquee_delete_is_grouped_and_undoable(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path(os.environ.get("OPENACE_CHROME", "/home/ubuntu/.local/bin/google-chrome"))
    if not chrome.exists():
        pytest.skip("system Chrome not available for canvas E2E test")

    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(tmp_path / "data")
    env["OPENACE_PORT"] = "8801"
    server = subprocess.Popen(
        [sys.executable, "-m", "openace.server.app"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = "http://127.0.0.1:8801"
    va = {"start_ratio": 0.25, "depth_cents": 45, "frequency_hz": 5.2, "phase": 0.0, "attack_ratio": 0.2, "release_ratio": 0.1}
    vb = {"start_ratio": 0.3, "depth_cents": 60, "frequency_hz": 4.8, "phase": 0.5, "attack_ratio": 0.1, "release_ratio": 0.25}
    vc = {"start_ratio": 0.2, "depth_cents": 75, "frequency_hz": 6.0, "phase": 0.75, "attack_ratio": 0.3, "release_ratio": 0.2}
    try:
        _wait_health(base)
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chrome), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            errors = []
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(base, wait_until="networkidle")
            page.locator(".new-project").click()
            page.wait_for_timeout(500)
            project_id = httpx.get(f"{base}/api/projects").json()[0]["id"]

            def project():
                return httpx.get(f"{base}/api/projects/{project_id}").json()

            seeded = project()
            seeded["tracks"][0]["notes"] = [
                _note("va", 120, va.copy()),
                _note("vb", 600, vb.copy()),
                _note("vc", 1200, vc.copy()),
                _note("vd", 1800, None),
            ]
            httpx.put(f"{base}/api/projects/{project_id}", json=seeded).raise_for_status()
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(700)
            box = page.locator(".piano-roll-canvas").bounding_box()
            assert box
            page.keyboard.press("4")
            page.wait_for_timeout(120)

            def dragrect(x1, y1, x2, y2, shift=False):
                if shift:
                    page.keyboard.down("Shift")
                page.mouse.move(box["x"] + x1, box["y"] + y1)
                page.mouse.down()
                page.mouse.move(box["x"] + x2, box["y"] + y2, steps=6)
                page.mouse.up()
                if shift:
                    page.keyboard.up("Shift")
                page.wait_for_timeout(220)

            # The rectangles start in blank space but intersect the vibrato spans
            # of A/B, then Shift-add C. D has no vibrato and is irrelevant.
            dragrect(110, 225, 250, 258)
            dragrect(340, 225, 385, 258, shift=True)
            before = project()["tracks"][0]["notes"]
            before_vibratos = {note["id"]: note["vibrato"] for note in before}
            assert before_vibratos["va"] == va
            assert before_vibratos["vb"] == vb
            assert before_vibratos["vc"] == vc

            page.keyboard.press("Delete")
            page.wait_for_timeout(750)
            after = project()["tracks"][0]["notes"]
            assert len(after) == len(before)
            assert [(n["start_ticks"], n["duration_ticks"], n["pitch"]) for n in after] == [(n["start_ticks"], n["duration_ticks"], n["pitch"]) for n in before]
            assert {note["id"]: note["vibrato"] for note in after} == {"va": None, "vb": None, "vc": None, "vd": None}

            page.keyboard.press("Control+z")
            page.wait_for_timeout(750)
            assert {note["id"]: note["vibrato"] for note in project()["tracks"][0]["notes"]} == before_vibratos
            page.keyboard.press("Control+Shift+z")
            page.wait_for_timeout(750)
            assert {note["id"]: note["vibrato"] for note in project()["tracks"][0]["notes"]} == {"va": None, "vb": None, "vc": None, "vd": None}
            assert errors == []
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
