"""
screen_progress.py
------------------
Singleton progress manager untuk stock screener.
Backend emit() progress events → SSE endpoint stream ke frontend.
"""
import asyncio
import json
import time
from typing import Optional

class ScreenProgressManager:
    def __init__(self):
        self._state: dict = {"stage": "idle", "message": "", "pct": 0, "detail": ""}
        self._queues: list[asyncio.Queue] = []

    def emit(self, stage: str, message: str, pct: int, detail: str = ""):
        """Emit a progress event. Called from sync screener code via asyncio."""
        self._state = {
            "stage": stage,
            "message": message,
            "pct": pct,
            "detail": detail,
            "ts": time.time()
        }
        # Push to all active SSE queues
        for q in list(self._queues):
            try:
                q.put_nowait(dict(self._state))
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def current(self) -> dict:
        return dict(self._state)

    def reset(self):
        self._state = {"stage": "idle", "message": "", "pct": 0, "detail": ""}


# Global singleton
progress_manager = ScreenProgressManager()
