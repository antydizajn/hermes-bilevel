"""Bounded non-blocking event queue with durable loss counters."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

from hermes_bilevel.events.envelope import EventEnvelope

_SENTINEL = object()


class BoundedEventQueue:
    def __init__(
        self,
        maxsize: int = 2048,
        overflow_policy: str = "drop_newest",
        on_drop: Callable[[str, Mapping[str, Any]], None] | None = None,
        writer: Callable[[Mapping[str, Any]], None] | None = None,
        start_worker: bool = True,
    ) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        if overflow_policy not in {"drop_newest", "drop_oldest", "block"}:
            raise ValueError(f"invalid overflow_policy: {overflow_policy}")
        self.maxsize = maxsize
        self.overflow_policy = overflow_policy
        self.on_drop = on_drop
        self.writer = writer
        self._q: queue.Queue[Any] = queue.Queue(maxsize=maxsize)
        self._dropped = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._closed = False
        self._thread: threading.Thread | None = None
        if start_worker and writer is not None:
            self._thread = threading.Thread(
                target=self._run, name="bilevel-event-writer", daemon=True
            )
            self._thread.start()

    @property
    def dropped(self) -> int:
        with self._lock:
            return self._dropped

    def qsize(self) -> int:
        return self._q.qsize()

    def put(self, event: EventEnvelope | Mapping[str, Any]) -> bool:
        with self._lock:
            if self._closed:
                return False
        data = event.to_dict() if isinstance(event, EventEnvelope) else dict(event)
        try:
            if self.overflow_policy == "block":
                self._q.put(data, timeout=0.05)
                return True
            self._q.put_nowait(data)
            return True
        except queue.Full:
            if self.overflow_policy == "drop_newest":
                self._mark_drop("drop_newest", data)
                return False
            if self.overflow_policy == "drop_oldest":
                try:
                    old = self._q.get_nowait()
                    self._q.task_done()
                    self._mark_drop("drop_oldest", old)
                except queue.Empty:
                    pass
                try:
                    self._q.put_nowait(data)
                    return True
                except queue.Full:
                    self._mark_drop("drop_newest_after_oldest", data)
                    return False
            self._mark_drop("full", data)
            return False

    def _mark_drop(self, reason: str, data: Mapping[str, Any]) -> None:
        with self._lock:
            self._dropped += 1
        if self.on_drop:
            try:
                self.on_drop(reason, data)
            except Exception:
                pass

    def _run(self) -> None:
        while True:
            try:
                item = self._q.get(timeout=0.1)
            except queue.Empty:
                if self._stop.is_set():
                    break
                continue

            if item is _SENTINEL:
                self._q.task_done()
                break

            if self.writer is not None:
                try:
                    self.writer(item)
                except Exception:
                    self._mark_drop("writer_error", item)
            self._q.task_done()

    def flush(self, timeout: float = 2.0) -> None:
        """Best-effort wait until all current items in queue are processed."""
        if self.writer is None:
            return
        start = time.time()
        while self._q.unfinished_tasks > 0 and (time.time() - start) < timeout:
            time.sleep(0.01)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            self._q.put(_SENTINEL, timeout=0.5)
        except queue.Full:
            self._stop.set()
        self.flush()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
