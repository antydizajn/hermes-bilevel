from __future__ import annotations

from hermes_bilevel.correlation.engine import CorrelationEngine


def test_exact_and_unmatched():
    eng = CorrelationEngine()
    r = eng.correlate({"event_id": "e", "turn_id": "t1"}, [{"record_id": "r", "turn_id": "t1"}])
    assert r.quality == "exact"
    r2 = eng.correlate({"event_id": "e"}, [{"record_id": "r", "session_id": "nope"}])
    assert r2.quality == "unmatched"


def test_composite():
    eng = CorrelationEngine()
    r = eng.correlate(
        {"event_id": "e", "session_id": "s", "turn_id": "t", "request_hash": "h"},
        [{"record_id": "r", "session_id": "s", "turn_id": "t", "request_hash": "h"}],
    )
    assert r.quality in {"composite", "exact"}
