import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from openace.core.models import Note, Project, Track
from openace.core.project_store import ProjectStore

ROOT = Path(__file__).resolve().parent.parent


def wait_health(base: str):
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if httpx.get(f"{base}/api/health", timeout=0.5).status_code == 200:
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


@pytest.mark.skipif(not (ROOT / "frontend/dist/index.html").exists(), reason="frontend production build required")
def test_large_project_piano_roll_sustains_60fps_at_dpr2(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path(os.environ.get("OPENACE_CHROME", "/home/ubuntu/.local/bin/google-chrome"))
    if not chrome.exists():
        pytest.skip("system Chrome not available")

    data = tmp_path / "data"
    project = Project(title="Large Project Performance", bpm=120)
    track = project.add_track(Track(name="Dense Lead"))
    lyrics = ["你", "好", "世", "界"]
    # 3000 total notes with hundreds simultaneously visible in the first bars.
    # This exercises both full-project hit/draw iteration and dense canvas paint cost.
    for index in range(3000):
        track.notes.append(Note(
            start_ticks=(index * 37) % 15360,
            duration_ticks=180 + (index % 5) * 60,
            pitch=48 + (index * 7) % 37,
            lyric=lyrics[index % 4],
            velocity=40 + (index * 7) % 80,
        ))
    store = ProjectStore(data / "projects")
    store.save(project)

    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(data)
    env["OPENACE_PORT"] = "8796"
    env["OPENACE_CI_SYNTH_FIXTURE"] = "1"
    server = subprocess.Popen(
        [sys.executable, "-m", "openace.server.app"], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = "http://127.0.0.1:8796"
    try:
        wait_health(base)
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chrome), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
            errors = []
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(base, wait_until="networkidle")
            page.wait_for_timeout(1800)

            def measure(label, action):
                page.evaluate(
                    """() => {
                      window.__frames = []
                      let last = performance.now()
                      function tick(now) {
                        window.__frames.push(now - last)
                        last = now
                        if (window.__frames.length < 240) requestAnimationFrame(tick)
                      }
                      requestAnimationFrame(tick)
                    }"""
                )
                action()
                page.wait_for_timeout(4300)
                frames = page.evaluate("() => window.__frames.slice(1)")
                frames.sort()
                avg = sum(frames) / len(frames)
                return {
                    "label": label,
                    "frames": len(frames),
                    "fps": 1000 / avg,
                    "p95_ms": frames[int(len(frames) * 0.95)],
                }

            def play_once():
                page.locator(".play-button").click()
                page.wait_for_timeout(3900)
                page.locator(".play-button").click()

            playback = measure("playback", play_once)

            def scroll_repeatedly():
                box = page.locator(".piano-roll-canvas").bounding_box()
                assert box
                page.mouse.move(box["x"] + 600, box["y"] + 250)
                direction = 1
                for index in range(300):
                    if index and index % 32 == 0:
                        direction *= -1
                    page.mouse.wheel(240 * direction, 0)
                    page.wait_for_timeout(10)

            scrolling = measure("scroll", scroll_repeatedly)
            assert playback["frames"] >= 180
            assert playback["fps"] >= 55
            assert playback["p95_ms"] <= 22
            assert scrolling["fps"] >= 55
            assert scrolling["p95_ms"] <= 22
            assert errors == []

            artifact = ROOT / "artifacts" / "e2e_screenshots" / "performance_large_project"
            artifact.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(artifact / "dense_project_dpr2.png"), full_page=True)
            (artifact / "performance_metrics.json").write_text(json.dumps({
                "note_count": 3000,
                "viewport": "1400x900@2x",
                "playback": playback,
                "scroll": scrolling,
            }, indent=2), encoding="utf-8")
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
