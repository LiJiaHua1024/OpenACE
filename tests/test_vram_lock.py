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


def test_nvidia_smi_query_parses_memory_without_cuda_context(monkeypatch):
    import openace.engines.vram as vram
    from types import SimpleNamespace

    monkeypatch.setattr(vram.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="NVIDIA GeForce RTX 3060, 12288, 10240\n")

    monkeypatch.setattr(vram.subprocess, "run", fake_run)
    gpu = vram.query_nvidia_gpu()
    assert gpu == {"name": "NVIDIA GeForce RTX 3060", "total_gb": 12.0, "free_gb": 10.0}
    assert "--query-gpu=name,memory.total,memory.free" in calls[0]


def test_available_vram_prefers_nvidia_smi(monkeypatch):
    import openace.engines.vram as vram

    monkeypatch.setattr(vram, "query_cuda_visible_nvidia_gpu", lambda: {"name": "GPU", "total_gb": 12.0, "free_gb": 4.5})
    assert VRAMManager().available_gb() == 4.5


def test_empty_cache_does_not_initialize_parent_cuda_context(monkeypatch):
    import sys
    from types import SimpleNamespace

    calls = []

    class FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def is_initialized():
            return False

        @staticmethod
        def empty_cache():
            calls.append("empty")

        @staticmethod
        def ipc_collect():
            calls.append("ipc")

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=FakeCuda))
    VRAMManager()._empty_cache()
    assert calls == []

    class InitializedCuda(FakeCuda):
        @staticmethod
        def is_initialized():
            return True

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=InitializedCuda))
    VRAMManager()._empty_cache()
    assert calls == ["empty", "ipc"]


def test_cuda_visible_numeric_mapping_controls_nvidia_smi_selector(monkeypatch):
    import openace.engines.vram as vram
    from types import SimpleNamespace

    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2,0")
    monkeypatch.setattr(vram.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="GPU, 12288, 10240\n")

    monkeypatch.setattr(vram.subprocess, "run", fake_run)
    gpu = vram.query_cuda_visible_nvidia_gpu(0)
    assert gpu["free_gb"] == 10.0
    assert calls[0][calls[0].index("-i") + 1] == "2"
    assert vram.nvidia_selector_for_cuda_visible(1) == "0"
    assert vram.nvidia_selector_for_cuda_visible(2) is None


def test_cuda_visible_uuid_and_empty_mapping_are_truthful(monkeypatch):
    import openace.engines.vram as vram
    from types import SimpleNamespace

    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-test-uuid")
    monkeypatch.setattr(vram.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="GPU, 12288, 10240\n")

    monkeypatch.setattr(vram.subprocess, "run", fake_run)
    assert vram.query_cuda_visible_nvidia_gpu(0) is not None
    assert calls[0][calls[0].index("-i") + 1] == "GPU-test-uuid"

    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    calls.clear()
    assert vram.query_cuda_visible_nvidia_gpu(0) is None
    assert calls == []
