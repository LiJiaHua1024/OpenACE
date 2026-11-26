from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List


class EventBus:
    def __init__(self):
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {"type": event_type, "time": time.time(), "payload": payload}
        dead = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            self.unsubscribe(queue)


event_bus = EventBus()
