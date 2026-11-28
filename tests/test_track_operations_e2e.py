import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts/e2e_screenshots/track_operations"


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
def test_track_context_duplicate_reorder_color_delete_and_undo(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path(os.environ.get("OPENACE_CHROME", "/home/ubuntu/.local/bin/google-chrome"))
    if not chrome.exists():
        pytest.skip("system Chrome not available")

    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(tmp_path / "data")
    env["OPENACE_PORT"] = "8793"
    server = subprocess.Popen(
        [sys.executable, "-m", "openace.server.app"], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = "http://127.0.0.1:8793"
    try:
        wait_health(base)
        project = httpx.post(f"{base}/api/projects", json={"title": "Track Operations"}).json()
        lead = project["tracks"][0]
        httpx.post(
            f"{base}/api/projects/{project['id']}/tracks/{lead['id']}/notes",
            json={"start_ticks": 0, "duration_ticks": 480, "pitch": 60, "lyric": "你", "velocity": 90},
        )
        httpx.post(
            f"{base}/api/projects/{project['id']}/tracks",
            json={"name": "BGM Operations", "type": "accompaniment", "language": "zh", "color": "#2fb996"},
        )

        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chrome), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            errors = []
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(base, wait_until="networkidle")
            page.wait_for_selector(".track-card")
            assert page.locator(".track-card").count() == 2

            page.locator(".track-card").first.click(button="right")
            assert page.locator(".track-context-menu").count() == 1
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(ARTIFACTS / "01_track_context_menu.png"))
            page.locator(".track-context-menu button", has_text="Duplicate track").click()
            page.wait_for_timeout(700)
            saved = httpx.get(f"{base}/api/projects/{project['id']}").json()
            assert [track["name"] for track in saved["tracks"]] == ["Lead Vocal", "Lead Vocal copy", "BGM Operations"]
            copy_track = saved["tracks"][1]
            assert len(copy_track["notes"]) == 1
            assert copy_track["notes"][0]["id"] != saved["tracks"][0]["notes"][0]["id"]

            page.locator(".track-card").nth(1).click(button="right")
            page.locator(".track-context-menu button", has_text="Move down").click()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project['id']}").json()
            assert [track["name"] for track in saved["tracks"]] == ["Lead Vocal", "BGM Operations", "Lead Vocal copy"]

            page.locator(".track-card").nth(2).click(button="right")
            page.locator(".track-color-swatch").nth(2).click()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project['id']}").json()
            assert saved["tracks"][2]["color"] == "#e6a23c"

            page.locator(".track-card").nth(2).click(button="right")
            page.locator(".track-context-menu button", has_text="Delete track").click()
            page.wait_for_timeout(700)
            saved = httpx.get(f"{base}/api/projects/{project['id']}").json()
            assert [track["name"] for track in saved["tracks"]] == ["Lead Vocal", "BGM Operations"]

            page.keyboard.press("Control+z")
            page.wait_for_timeout(700)
            saved = httpx.get(f"{base}/api/projects/{project['id']}").json()
            assert [track["name"] for track in saved["tracks"]] == ["Lead Vocal", "BGM Operations", "Lead Vocal copy"]
            page.keyboard.press("Control+y")
            page.wait_for_timeout(700)
            saved = httpx.get(f"{base}/api/projects/{project['id']}").json()
            assert [track["name"] for track in saved["tracks"]] == ["Lead Vocal", "BGM Operations"]

            page.locator(".track-card .track-menu-button").first.click()
            assert page.locator(".track-context-menu").count() == 1
            page.keyboard.press("Escape")
            assert page.locator(".track-context-menu").count() == 0
            page.screenshot(path=str(ARTIFACTS / "02_track_operations_final.png"))
            assert errors == []
            browser.close()
    finally:
        server.kill()
        server.wait(timeout=5)
