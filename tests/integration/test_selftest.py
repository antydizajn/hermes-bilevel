from __future__ import annotations

from hermes_bilevel.selftest import run_selftest


def test_selftest_passes():
    result = run_selftest()
    assert result["ok"] is True
    assert result["model_calls"] == 0
    assert result["network_requests"] == 0
