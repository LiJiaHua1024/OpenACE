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


@pytest.mark.skipif(not (ROOT / "frontend/dist/index.html").exists(), reason="frontend production build required")
def test_piano_roll_marquee_clipboard_and_velocity_lane(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path(os.environ.get("OPENACE_CHROME", "/home/ubuntu/.local/bin/google-chrome"))
    if not chrome.exists():
        pytest.skip("system Chrome not available for canvas E2E test")

    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(tmp_path / "data")
    env["OPENACE_PORT"] = "8799"
    server = subprocess.Popen(
        [sys.executable, "-m", "openace.server.app"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = "http://127.0.0.1:8799"
    try:
        _wait_health(base)
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chrome), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            errors = []
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(base, wait_until="networkidle")
            page.locator(".new-project").click()
            page.wait_for_timeout(350)
            box = page.locator(".piano-roll-canvas").bounding_box()
            assert box

            def drag_note(x, y, w=55):
                page.mouse.move(box["x"] + x, box["y"] + y)
                page.mouse.down()
                page.mouse.move(box["x"] + x + w, box["y"] + y, steps=4)
                page.mouse.up()
                page.wait_for_timeout(60)

            # Three notes at pitches C4/E4/G4-ish rows in the default viewport.
            drag_note(140, 315)
            drag_note(275, 285)
            drag_note(410, 255)

            page.locator('button[title="Select/move (V)"]').click()
            page.mouse.move(box["x"] + 110, box["y"] + 270)
            page.mouse.down()
            page.mouse.move(box["x"] + 360, box["y"] + 340, steps=6)
            page.mouse.up()
            assert page.locator(".selection-count").inner_text() == "2 selected"

            # Multi-select movement is bidirectional. One grid step is exactly 28px at
            # the default 112px/beat zoom; one row is one semitone.
            page.mouse.move(box["x"] + 170, box["y"] + 315)
            page.mouse.down()
            page.mouse.move(box["x"] + 198, box["y"] + 300, steps=4)
            page.mouse.up()
            page.wait_for_timeout(550)
            project_id = httpx.get(f"{base}/api/projects").json()[0]["id"]
            moved = httpx.get(f"{base}/api/projects/{project_id}").json()["tracks"][0]["notes"]
            assert [(n["start_ticks"], n["pitch"]) for n in moved[:2]] == [(480, 61), (1080, 63)]
            page.mouse.move(box["x"] + 198, box["y"] + 300)
            page.mouse.down()
            page.mouse.move(box["x"] + 170, box["y"] + 315, steps=4)
            page.mouse.up()
            page.wait_for_timeout(550)
            restored = httpx.get(f"{base}/api/projects/{project_id}").json()["tracks"][0]["notes"]
            assert [(n["start_ticks"], n["pitch"]) for n in restored[:2]] == [(360, 60), (960, 62)]

            page.keyboard.press("Control+c")
            page.mouse.click(box["x"] + 650, box["y"] + 15)
            page.keyboard.press("Control+v")
            page.wait_for_timeout(650)
            assert page.locator(".selection-count").inner_text() == "2 selected"
            page.keyboard.press("Control+d")
            page.wait_for_timeout(650)

            projects = httpx.get(f"{base}/api/projects").json()
            project_id = projects[0]["id"]
            project = httpx.get(f"{base}/api/projects/{project_id}").json()
            notes = project["tracks"][0]["notes"]
            assert len(notes) == 7  # 3 original + 2 pasted + 2 duplicated

            # Velocity lane is the bottom strip; x=170 lies inside the first note body.
            page.mouse.move(box["x"] + 170, box["y"] + box["height"] - 35)
            page.mouse.down()
            page.mouse.move(box["x"] + 170, box["y"] + box["height"] - 8, steps=3)
            page.mouse.up()
            page.wait_for_timeout(650)
            project = httpx.get(f"{base}/api/projects/{project_id}").json()
            velocities = {note["start_ticks"]: note["velocity"] for note in project["tracks"][0]["notes"]}
            assert velocities[360] < 20

            page.mouse.click(box["x"] + 170, box["y"] + 315, button="right")
            assert page.locator(".piano-context-menu").count() == 1
            page.locator(".piano-context-menu button", has_text="Vibrato").click()
            assert page.locator(".vibrato-editor").count() == 1
            page.locator(".vibrato-enable input").check()
            page.locator(".vibrato-editor input[type='range']").nth(1).evaluate(
                """(el) => {
                  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, '80')
                  el.dispatchEvent(new Event('input', { bubbles: true }))
                  el.dispatchEvent(new Event('change', { bubbles: true }))
                }"""
            )
            page.locator(".vibrato-header button").click()
            page.wait_for_timeout(700)
            project = httpx.get(f"{base}/api/projects/{project_id}").json()
            first = next(note for note in project["tracks"][0]["notes"] if note["start_ticks"] == 360)
            assert first["vibrato"]["depth_cents"] == 80
            assert first["vibrato"]["frequency_hz"] == 5.2
            page.keyboard.press("Control+z")
            page.wait_for_timeout(700)
            project = httpx.get(f"{base}/api/projects/{project_id}").json()
            first = next(note for note in project["tracks"][0]["notes"] if note["start_ticks"] == 360)
            assert first["vibrato"] is None
            assert errors == []
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
