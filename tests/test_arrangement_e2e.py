import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pytest
import soundfile as sf

from openace.core.models import AudioClip, Project, Track, TrackType
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
def test_arrangement_decodes_waveform_and_drags_audio_clip_independently(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = Path(os.environ.get("OPENACE_CHROME", "/home/ubuntu/.local/bin/google-chrome"))
    if not chrome.exists():
        pytest.skip("system Chrome not available")

    data = tmp_path / "data"
    render_dir = data / "renders" / "fixture_project"
    render_dir.mkdir(parents=True)
    sr = 48000
    t = np.arange(sr * 2) / sr
    # Test-only fixture audio: deliberately asymmetric so decoded peaks differ across time.
    audio = np.column_stack([
        np.sin(2 * np.pi * 220 * t) * np.linspace(0.05, 0.9, len(t)),
        np.sin(2 * np.pi * 220 * t) * np.linspace(0.05, 0.9, len(t)),
    ]).astype(np.float32)
    wav = render_dir / "clip.wav"
    sf.write(wav, audio, sr)

    project = Project(title="Arrangement E2E")
    project.add_track(Track(name="Lead Vocal"))
    bgm = project.add_track(Track(name="BGM", type=TrackType.ACCOMPANIMENT, color="#2fb996"))
    bgm.clips.append(AudioClip(path=str(wav), start_ticks=0, duration_ticks=1920, label="fixture"))
    store = ProjectStore(data / "projects")
    store.save(project)

    env = os.environ.copy()
    env["OPENACE_DATA_DIR"] = str(data)
    env["OPENACE_PORT"] = "8798"
    server = subprocess.Popen(
        [sys.executable, "-m", "openace.server.app"], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = "http://127.0.0.1:8798"
    try:
        wait_health(base)
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chrome), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            errors = []
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(base, wait_until="networkidle")
            page.wait_for_timeout(1400)
            box = page.locator(".arrangement-view canvas").bounding_box()
            assert box
            waveform_pixels = page.evaluate(
                """() => {
                  const canvas = document.querySelector('.arrangement-view canvas')
                  const ctx = canvas.getContext('2d')
                  const data = ctx.getImageData(75, 68, 420, 15).data
                  let count = 0
                  for (let i = 0; i < data.length; i += 4) {
                    if (data[i] < 160 && data[i + 1] > 145 && data[i + 2] > 105) count++
                  }
                  return count
                }"""
            )
            assert waveform_pixels > 80  # decoded waveform strokes inside the clip interior

            # BGM is the second row; dragging 100px at 112px/beat snaps to +480 ticks.
            page.mouse.move(box["x"] + 220, box["y"] + 75)
            page.mouse.down()
            page.mouse.move(box["x"] + 320, box["y"] + 75, steps=5)
            page.mouse.up()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert saved["tracks"][1]["clips"][0]["start_ticks"] == 480

            page.evaluate(
                """() => {
                  window.__openaceStarts = []
                  window.__openaceOriginalStart ||= AudioBufferSourceNode.prototype.start
                  const original = window.__openaceOriginalStart
                  AudioBufferSourceNode.prototype.start = function(when = 0, offset = 0, duration) {
                    window.__openaceStarts.push({ when, offset, duration, now: this.context.currentTime })
                    return original.call(this, when, offset, duration)
                  }
                }"""
            )
            page.locator('.play-button').click()
            page.wait_for_timeout(350)
            page.locator('.play-button').click()
            starts = page.evaluate("() => window.__openaceStarts")
            assert starts and abs((starts[0]["when"] - starts[0]["now"]) - 0.5) < 0.2
            assert starts[0]["offset"] == 0

            page.mouse.move(box["x"] + 320, box["y"] + 75)
            page.mouse.down()
            page.mouse.move(box["x"] + 220, box["y"] + 75, steps=5)
            page.mouse.up()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert saved["tracks"][1]["clips"][0]["start_ticks"] == 0

            # Drag clip fade handles on the top edge: half a beat inward on both sides.
            page.mouse.move(box["x"] + 64, box["y"] + 68)
            page.mouse.down()
            page.mouse.move(box["x"] + 120, box["y"] + 68, steps=4)
            page.mouse.up()
            page.mouse.move(box["x"] + 512, box["y"] + 68)
            page.mouse.down()
            page.mouse.move(box["x"] + 456, box["y"] + 68, steps=4)
            page.mouse.up()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            clip = saved["tracks"][1]["clips"][0]
            assert (clip["fade_in_ticks"], clip["fade_out_ticks"]) == (240, 240)

            # The visible inner endpoint of the fade slope is itself draggable.
            page.mouse.move(box["x"] + 120, box["y"] + 68)
            page.mouse.down()
            page.mouse.move(box["x"] + 176, box["y"] + 68, steps=3)
            page.mouse.up()
            page.wait_for_timeout(450)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert saved["tracks"][1]["clips"][0]["fade_in_ticks"] == 480
            page.mouse.move(box["x"] + 176, box["y"] + 68)
            page.mouse.down()
            page.mouse.move(box["x"] + 120, box["y"] + 68, steps=3)
            page.mouse.up()
            page.wait_for_timeout(450)

            page.mouse.click(box["x"] + 220, box["y"] + 75, button="right")
            page.locator(".clip-gain-control input").fill("-6")
            page.wait_for_timeout(500)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert saved["tracks"][1]["clips"][0]["gain_db"] == -6
            page.locator(".clip-gain-control input").fill("0")
            page.keyboard.press("Escape")
            page.mouse.click(box["x"] + 40, box["y"] + 75)

            page.locator('button[title="Stop"]').click()
            page.wait_for_timeout(100)
            page.evaluate(
                """() => {
                  window.__openaceRampCount = 0
                  window.__openaceOriginalRamp ||= AudioParam.prototype.linearRampToValueAtTime
                  const original = window.__openaceOriginalRamp
                  AudioParam.prototype.linearRampToValueAtTime = function(value, endTime) {
                    window.__openaceRampCount++
                    return original.call(this, value, endTime)
                  }
                }"""
            )
            page.locator('.play-button').click()
            page.wait_for_timeout(180)
            page.locator('.play-button').click()
            assert page.evaluate("() => window.__openaceRampCount") >= 2

            # Trim the right edge inward by one beat, then the left edge inward by one beat.
            page.mouse.move(box["x"] + 512, box["y"] + 75)
            page.mouse.down()
            page.mouse.move(box["x"] + 400, box["y"] + 75, steps=4)
            page.mouse.up()
            page.wait_for_timeout(500)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert saved["tracks"][1]["clips"][0]["duration_ticks"] == 1440

            page.mouse.move(box["x"] + 64, box["y"] + 75)
            page.mouse.down()
            page.mouse.move(box["x"] + 176, box["y"] + 75, steps=4)
            page.mouse.up()
            page.wait_for_timeout(500)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            clip = saved["tracks"][1]["clips"][0]
            assert (clip["start_ticks"], clip["offset_ticks"], clip["duration_ticks"]) == (480, 480, 960)

            # Splitting at the center preserves source-time continuity across the two clips.
            page.mouse.click(box["x"] + 288, box["y"] + 75, button="right")
            page.locator(".arrangement-context-menu button", has_text="Split at cursor").click()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            clips = saved["tracks"][1]["clips"]
            assert len(clips) == 2
            assert [(c["start_ticks"], c["offset_ticks"], c["duration_ticks"]) for c in clips] == [
                (480, 480, 480),
                (960, 960, 480),
            ]
            assert [(c["fade_in_ticks"], c["fade_out_ticks"]) for c in clips] == [(240, 0), (0, 240)]

            page.locator('button[title="Stop"]').click()
            page.wait_for_timeout(100)
            page.evaluate(
                """() => {
                  window.__openaceStarts = []
                  window.__openaceOriginalStart ||= AudioBufferSourceNode.prototype.start
                  const original = window.__openaceOriginalStart
                  AudioBufferSourceNode.prototype.start = function(when = 0, offset = 0, duration) {
                    window.__openaceStarts.push({ when, offset, duration, now: this.context.currentTime })
                    return original.call(this, when, offset, duration)
                  }
                }"""
            )
            page.locator('.play-button').click()
            page.wait_for_timeout(300)
            page.locator('.play-button').click()
            starts = page.evaluate("() => window.__openaceStarts")
            assert len(starts) == 2
            assert abs((starts[0]["when"] - starts[0]["now"]) - 0.5) < 0.2
            assert abs(starts[0]["offset"] - 0.5) < 0.03
            assert abs(starts[0]["duration"] - 0.5) < 0.03
            assert abs((starts[1]["when"] - starts[1]["now"]) - 1.0) < 0.2
            assert abs(starts[1]["offset"] - 1.0) < 0.03
            assert abs(starts[1]["duration"] - 0.5) < 0.03

            # Drag the second clip half a beat backward so it overlaps the first.
            # The overlap is automatically rendered as an equal-power crossfade.
            page.mouse.move(box["x"] + 344, box["y"] + 75)
            page.mouse.down()
            page.mouse.move(box["x"] + 288, box["y"] + 75, steps=4)
            page.mouse.up()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            clips = saved["tracks"][1]["clips"]
            assert [c["start_ticks"] for c in clips] == [480, 720]
            cyan_pixels = page.evaluate(
                """() => {
                  const canvas = document.querySelector('.arrangement-view canvas')
                  const ctx = canvas.getContext('2d')
                  const data = ctx.getImageData(232, 64, 56, 26).data
                  let count = 0
                  for (let i = 0; i < data.length; i += 4) {
                    if (data[i] < 150 && data[i + 1] > 120 && data[i + 2] > 160) count++
                  }
                  return count
                }"""
            )
            assert cyan_pixels > 10
            page.locator('button[title="Stop"]').click()
            page.wait_for_timeout(100)
            page.evaluate(
                """() => {
                  window.__openaceRampCount = 0
                  window.__openaceOriginalRamp ||= AudioParam.prototype.linearRampToValueAtTime
                  const original = window.__openaceOriginalRamp
                  AudioParam.prototype.linearRampToValueAtTime = function(value, endTime) {
                    window.__openaceRampCount++
                    return original.call(this, value, endTime)
                  }
                }"""
            )
            page.locator('.play-button').click()
            page.wait_for_timeout(180)
            page.locator('.play-button').click()
            assert page.evaluate("() => window.__openaceRampCount") >= 10

            # Clip context operations copy/paste across empty space, duplicate, and delete.
            page.mouse.click(box["x"] + 300, box["y"] + 75, button="right")
            page.locator(".arrangement-context-menu button", has_text="Copy").click()
            page.mouse.click(box["x"] + 620, box["y"] + 75, button="right")
            page.locator(".arrangement-context-menu button", has_text="Paste at cursor").click()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            clips = saved["tracks"][1]["clips"]
            assert len(clips) == 3
            pasted = clips[-1]
            assert pasted["start_ticks"] == 2400
            assert (pasted["offset_ticks"], pasted["duration_ticks"]) == (960, 480)

            page.mouse.click(box["x"] + 680, box["y"] + 75, button="right")
            page.locator(".arrangement-context-menu button", has_text="Duplicate").click()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            clips = saved["tracks"][1]["clips"]
            assert len(clips) == 4
            assert clips[-1]["start_ticks"] == 2880

            page.mouse.click(box["x"] + 792, box["y"] + 75, button="right")
            page.locator(".arrangement-context-menu").get_by_role("button", name="Delete", exact=True).click()
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert len(saved["tracks"][1]["clips"]) == 3
            page.keyboard.press("Control+z")
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert len(saved["tracks"][1]["clips"]) == 4
            page.keyboard.press("Control+y")
            page.wait_for_timeout(650)
            saved = httpx.get(f"{base}/api/projects/{project.id}").json()
            assert len(saved["tracks"][1]["clips"]) == 3
            assert errors == []
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
