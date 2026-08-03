from __future__ import annotations

import threading
import time

from hermes_bilevel.events.envelope import make_event
from hermes_bilevel.events.queue import BoundedEventQueue


def test_queue_deadlock_prevention():
    # Verify that calling on_drop doesn't deadlock when it queries queue
    # properties that lock. Callback must fire outside the lock.
    dropped_count = 0
    q = None

    def on_drop(reason, data):
        nonlocal dropped_count
        dropped_count += 1
        # Querying queue.dropped would deadlock if the callback ran while the
        # queue lock was held; the implementation releases the lock first.
        _ = q.dropped

    # start_worker=False keeps the queue full deterministically (no drain
    # race), so every overflow fires on_drop exactly once.
    q = BoundedEventQueue(
        maxsize=1,
        overflow_policy="drop_newest",
        on_drop=on_drop,
        start_worker=False,
    )

    assert q.put(make_event("a", {"x": 1})) is True  # fills the queue
    assert q.put(make_event("b", {"x": 2})) is False  # overflow -> drop
    assert q.put(make_event("c", {"x": 3})) is False  # overflow -> drop

    q.close()
    assert dropped_count == 2
    assert q.dropped >= 1


def test_queue_close_concurrency_race():
    # Test thread-safe closure and sentinel race prevention.
    q = BoundedEventQueue(
        maxsize=10,
        overflow_policy="bounded_block",
        writer=lambda e: time.sleep(0.001),
        start_worker=True,
    )

    def producer():
        for i in range(100):
            q.put(make_event("p", {"val": i}))

    threads = [threading.Thread(target=producer) for _ in range(5)]
    for t in threads:
        t.start()

    time.sleep(0.01)
    q.close()

    for t in threads:
        t.join()

    # The queue must be closed cleanly and no threads should hang
    assert q._closed is True
