from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, Optional


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
        if estimated_gb > self.budget_gb:
            raise RuntimeError(
                f"{engine} requires {estimated_gb:.1f}GB, above configured {self.budget_gb:.1f}GB budget"
            )
        with self._lock:
            if self._active is not None:
                raise RuntimeError(f"VRAM already reserved by {self._active.engine}")
            if estimated_gb > self.available_gb() + 0.25:
                raise RuntimeError(
                    f"insufficient free VRAM for {engine}: need {estimated_gb:.1f}GB, "
                    f"available {self.available_gb():.1f}GB"
                )
            reservation = VRAMReservation(engine=engine, estimated_gb=estimated_gb, device="cuda", acquired_at=time.time())
            self._active = reservation
        try:
            yield reservation
        finally:
            with self._lock:
                self._last_engine = self._active.engine if self._active else engine
                self._active = None
            self._empty_cache()

    def _empty_cache(self) -> None:
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
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
