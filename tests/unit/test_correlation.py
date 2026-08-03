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


def test_correlation_composite_and_heuristic_scoring():
    eng = CorrelationEngine()

    # 1. Test score >= 0.4 (heuristic match)
    # session_id match (0.3) + model match (0.1) = 0.4
    r_heuristic = eng.correlate(
        {"event_id": "e1", "session_id": "s1", "model": "gpt-4"},
        [{"record_id": "r1", "session_id": "s1", "model": "gpt-4"}],
    )
    assert r_heuristic.quality == "heuristic"
    assert r_heuristic.confidence == 0.4
    assert r_heuristic.explanation["mode"] == "heuristic"

    # 2. Test tie with multiple candidates and alternatives
    # Left has session_id, model, payload_hash
    # Candidate 1: session_id + model = 0.4 (heuristic)
    # Candidate 2: session_id + model = 0.4 (heuristic, same score -> alternative)
    # Candidate 3: session_id = 0.3 (fails threshold < 0.4)
    r_alts = eng.correlate(
        {"event_id": "e2", "session_id": "s1", "model": "gpt-4", "payload_hash": "p1"},
        [
            {"record_id": "r_best", "session_id": "s1", "model": "gpt-4"},
            {"record_id": "r_alt1", "session_id": "s1", "model": "gpt-4"},
            {"record_id": "r_bad", "session_id": "s1"},
        ]
    )
    assert r_alts.quality == "heuristic"
    assert r_alts.right_id == "r_best"
    assert "r_alt1" in r_alts.alternatives
    assert "r_bad" not in r_alts.alternatives

    # 3. Test composite threshold (score >= 0.7)
    # session_id (0.3) + request_hash (0.4) + model (0.1) = 0.8
    r_composite = eng.correlate(
        {"event_id": "e3", "session_id": "s1", "request_hash": "h1", "model": "gpt-4"},
        [{"record_id": "r3", "session_id": "s1", "request_hash": "h1", "model": "gpt-4"}]
    )
    assert r_composite.quality == "composite"
    assert r_composite.confidence == 0.8

