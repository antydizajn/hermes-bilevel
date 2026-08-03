from __future__ import annotations

import threading
import time

import pytest

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


def test_queue_invalid_arguments():
    # 1. maxsize < 1
    with pytest.raises(ValueError, match="maxsize must be >= 1"):
        BoundedEventQueue(maxsize=0)

    # 2. Invalid overflow policy
    with pytest.raises(ValueError, match="invalid overflow_policy"):
        BoundedEventQueue(overflow_policy="invalid_policy")


def test_queue_drop_oldest():
    dropped_items = []

    def on_drop(reason, data):
        dropped_items.append((reason, data))

    q = BoundedEventQueue(
        maxsize=2,
        overflow_policy="drop_oldest",
        on_drop=on_drop,
        start_worker=False,
    )

    # Put elements to fill the queue
    assert q.put({"event_id": "1", "event_type": "a"}) is True
    assert q.put({"event_id": "2", "event_type": "b"}) is True

    # Overflow: drop oldest ("1") and accept "3"
    assert q.put({"event_id": "3", "event_type": "c"}) is True

    assert len(dropped_items) == 1
    reason, dropped_data = dropped_items[0]
    assert reason == "drop_oldest"
    assert dropped_data["event_id"] == "1"


def test_queue_writer_error():
    dropped_reasons = []

    def on_drop(reason, data):
        dropped_reasons.append(reason)

    def bad_writer(item):
        raise RuntimeError("write failure")

    q = BoundedEventQueue(
        maxsize=10,
        overflow_policy="drop_newest",
        on_drop=on_drop,
        writer=bad_writer,
        start_worker=True,
    )

    assert q.put({"event_id": "1", "event_type": "a"}) is True
    q.flush()
    q.close()

    assert "writer_error" in dropped_reasons


def test_queue_other_cases():
    # 1. put on a closed queue returns False
    q = BoundedEventQueue(maxsize=5, start_worker=False)
    q.close()
    assert q.put({"event_id": "1", "event_type": "a"}) is False

    # 2. close on already closed queue is idempotent
    q.close()

    # 3. flush when writer is None returns immediately
    q2 = BoundedEventQueue(maxsize=5, start_worker=False)
    q2.flush()

    # 4. on_drop throws exception - swallowed safely
    def throwing_on_drop(reason, data):
        raise RuntimeError("boom")

    q3 = BoundedEventQueue(
        maxsize=1,
        overflow_policy="drop_newest",
        on_drop=throwing_on_drop,
        start_worker=False,
    )
    assert q3.put({"event_id": "1"}) is True
    assert q3.put({"event_id": "2"}) is False  # triggers drop

    # 5. close when queue is full (sentinel cannot be put)
    q4 = BoundedEventQueue(maxsize=1, start_worker=False)
    q4.put({"event_id": "1"})
    # now queue is full, close() will raise Full when attempting to put sentinel,
    # catching it and setting stop event.
    q4.close()
    assert q4._stop.is_set()

