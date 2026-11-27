import os
import subprocess
import sys
import threading
import time

from openace.engines.vram import VRAMManager


def test_vram_acquire_waits_instead_of_overlapping_in_process(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENACE_VRAM_LOCK_PATH", str(tmp_path / "vram.lock"))
    manager = VRAMManager()
    active = 0
    max_active = 0
    guard = threading.Lock()

    def worker():
        nonlocal active, max_active
        with manager.acquire("test-engine", 1.0):
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with guard:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert max_active == 1


def test_vram_lock_serializes_independent_processes(tmp_path):
    lock = tmp_path / "vram.lock"
    log = tmp_path / "events.log"
    code = """
import time
from pathlib import Path
from openace.engines.vram import VRAMManager
name = __import__('sys').argv[1]
log = Path(__import__('sys').argv[2])
with VRAMManager().acquire(name, 1.0):
    with log.open('a') as fh: fh.write(f'start {name} {time.time()}\\n')
    time.sleep(0.18)
    with log.open('a') as fh: fh.write(f'end {name} {time.time()}\\n')
"""
    env = os.environ.copy()
    env["OPENACE_VRAM_LOCK_PATH"] = str(lock)
    processes = [
        subprocess.Popen([sys.executable, "-c", code, f"p{index}", str(log)], env=env)
        for index in range(2)
    ]
    for process in processes:
        assert process.wait(timeout=5) == 0
    events = []
    for line in log.read_text().splitlines():
        kind, name, stamp = line.split()
        events.append((float(stamp), kind, name))
    events.sort()
    assert [kind for _stamp, kind, _name in events] == ["start", "end", "start", "end"]
    assert events[0][2] == events[1][2]
    assert events[2][2] == events[3][2]
