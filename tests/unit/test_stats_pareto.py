from __future__ import annotations

from hermes_bilevel.optimization.pareto import nondominated_sort
from hermes_bilevel.statistics.stats import paired_bootstrap_ci, wilson_interval


def test_wilson():
    lo, hi = wilson_interval(8, 10)
    assert 0 <= lo <= hi <= 1


def test_bootstrap():
    md, lo, hi = paired_bootstrap_ci([0, 0, 0, 0], [1, 1, 1, 1], n_boot=200, seed=1)
    assert md == 1.0
    assert lo > 0


def test_pareto():
    rows = [
        {
            "candidate_hash": "a",
            "metrics": {
                "task_success_rate": 1.0,
                "estimated_cost_usd": 2.0,
                "latency_ms": 10,
                "tool_call_count": 5,
            },
        },
        {
            "candidate_hash": "b",
            "metrics": {
                "task_success_rate": 1.0,
                "estimated_cost_usd": 1.0,
                "latency_ms": 10,
                "tool_call_count": 5,
            },
        },
        {
            "candidate_hash": "c",
            "metrics": {
                "task_success_rate": 0.5,
                "estimated_cost_usd": 0.1,
                "latency_ms": 10,
                "tool_call_count": 5,
            },
        },
    ]
    front = nondominated_sort(rows)
    hashes = {r["candidate_hash"] for r in front}
    assert "b" in hashes
    assert "a" not in hashes  # dominated by b on cost
