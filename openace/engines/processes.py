"""Cancellation-aware local engine subprocess execution."""
from __future__ import annotations

import os
import signal
import subprocess
import threading
from typing import Optional


class JobCancelled(Exception):
    """Raised when a render job cancellation reaches its engine subprocess."""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen] = set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()
        with self._lock:
            processes = list(self._processes)
        for process in processes:
            terminate_process_tree(process)

    def register(self, process: subprocess.Popen) -> None:
        with self._lock:
            self._processes.add(process)
        if self.cancelled:
            terminate_process_tree(process)

    def unregister(self, process: subprocess.Popen) -> None:
        with self._lock:
            self._processes.discard(process)


def terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.terminate()
        except Exception:
            return
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.kill()
            except Exception:
                pass


def popen_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def run_cancellable(command, token: Optional[CancellationToken] = None, **kwargs) -> subprocess.CompletedProcess:
    if token and token.cancelled:
        raise JobCancelled("render job cancelled")
    process = subprocess.Popen(command, **kwargs, **popen_kwargs())
    if token:
        token.register(process)
    try:
        capture = kwargs.get("stdout") is not None
        if capture:
            stdout, stderr = process.communicate()
        else:
            process.wait()
            stdout, stderr = None, None
        if token and token.cancelled:
            raise JobCancelled("render job cancelled")
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except BaseException:
        if process.poll() is None:
            terminate_process_tree(process)
        raise
    finally:
        if token:
            token.unregister(process)
