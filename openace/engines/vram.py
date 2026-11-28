from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import tempfile
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, Optional


def _acquire_file_lock(handle) -> None:
    if os.fstat(handle.fileno()).st_size == 0:
        handle.write(b"\0")
        handle.flush()
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.2)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _release_file_lock(handle) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def query_nvidia_gpu(index: int | str = 0) -> Optional[Dict[str, object]]:
    """Query GPU name/memory without initializing a CUDA context in this process."""
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [
                executable,
                "-i",
                str(index),
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        name, total_mib, free_mib = result.stdout.splitlines()[0].rsplit(",", 2)
        return {
            "name": name.strip(),
            "total_gb": float(total_mib.strip()) / 1024.0,
            "free_gb": float(free_mib.strip()) / 1024.0,
        }
    except (ValueError, IndexError):
        return None


def nvidia_selector_for_cuda_visible(index: int = 0) -> Optional[str]:
    """Map a CUDA-visible device ordinal to an nvidia-smi selector.

    CUDA_VISIBLE_DEVICES may contain numeric physical indexes or GPU/MIG UUIDs. An
    empty value means no CUDA device is visible. nvidia-smi accepts both numeric
    indexes and UUIDs after ``-i``, so the token can be forwarded without initializing
    CUDA in this orchestrator process.
    """
    spec = os.environ.get("CUDA_VISIBLE_DEVICES")
    if spec is None:
        return str(index)
    tokens = [token.strip() for token in spec.split(",") if token.strip()]
    if not tokens or index < 0 or index >= len(tokens):
        return None
    return tokens[index]


def query_cuda_visible_nvidia_gpu(index: int = 0) -> Optional[Dict[str, object]]:
    """Query memory for the physical GPU backing a CUDA-visible device ordinal."""
    selector = nvidia_selector_for_cuda_visible(index)
    if selector is None:
        return None
    return query_nvidia_gpu(selector)


@dataclass
class VRAMReservation:
    engine: str
    estimated_gb: float
    device: str
    acquired_at: float


class VRAMManager:
    """Stage-wise exclusive GPU scheduler for the two large model families.

    The hard invariant is that SoulX-Singer and ACE-Step are never resident together on
    a 12GB consumer card. This process-local implementation provides the orchestration
    boundary; the engine subprocesses are additionally launched only after the previous
    process has exited, so model memory is genuinely released by the OS.
    """

    def __init__(self, budget_gb: float = 12.0):
        self.budget_gb = float(os.environ.get("OPENACE_VRAM_BUDGET_GB", budget_gb))
        self._lock = threading.Lock()
        self._active: Optional[VRAMReservation] = None
        self._last_engine: Optional[str] = None

    def available_gb(self) -> float:
        gpu = query_cuda_visible_nvidia_gpu()
        if gpu is not None:
            return min(self.budget_gb, float(gpu["free_gb"]))
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                free, total = torch.cuda.mem_get_info()
                return min(self.budget_gb, free / 1024**3)
        except Exception:
            pass
        return self.budget_gb

    @contextmanager
    def acquire(self, engine: str, estimated_gb: float) -> Iterator[VRAMReservation]:
        """Reserve the GPU stage locally and across cooperating OpenACE processes.

        The lock is intentionally held for the whole engine subprocess lifetime. Waiting is
        safer than failing a queued render: two heavy model families must never become
        co-resident on a 12GB card.
        """
        if estimated_gb > self.budget_gb:
            raise RuntimeError(
                f"{engine} requires {estimated_gb:.1f}GB, above configured {self.budget_gb:.1f}GB budget"
            )
        while True:
            with self._lock:
                if self._active is None:
                    reservation = VRAMReservation(engine=engine, estimated_gb=estimated_gb, device="cuda", acquired_at=time.time())
                    self._active = reservation
                    break
            time.sleep(0.05)

        lock_path = Path(os.environ.get("OPENACE_VRAM_LOCK_PATH", Path(tempfile.gettempdir()) / "openace-vram.lock"))
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = None
        try:
            handle = lock_path.open("a+b")
            _acquire_file_lock(handle)
            if estimated_gb > self.available_gb() + 0.25:
                raise RuntimeError(
                    f"insufficient free VRAM for {engine}: need {estimated_gb:.1f}GB, "
                    f"available {self.available_gb():.1f}GB"
                )
            yield reservation
        finally:
            if handle is not None:
                _release_file_lock(handle)
                handle.close()
            with self._lock:
                self._last_engine = self._active.engine if self._active else engine
                self._active = None
            self._empty_cache()

    def _empty_cache(self) -> None:
        try:
            import torch  # type: ignore

            # Engine models run in subprocesses, so cache cleanup is only meaningful if
            # this orchestrator itself already initialized CUDA. Calling empty_cache()
            # unconditionally would lazy-initialize a resident CUDA context in the parent
            # and waste part of the 12GB budget it is meant to protect.
            if torch.cuda.is_available() and torch.cuda.is_initialized():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass

    def status(self) -> Dict[str, object]:
        return {
            "budget_gb": self.budget_gb,
            "available_gb": self.available_gb(),
            "active": self._active.engine if self._active else None,
            "last_engine": self._last_engine,
        }


vram_manager = VRAMManager()
