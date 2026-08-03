"""Simple Pareto nondominated sort without heavy deps."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def dominates(a: Mapping[str, float], b: Mapping[str, float], maximize: Sequence[str], minimize: Sequence[str]) -> bool:
    """True if a dominates b."""
    better_or_eq = True
    strictly_better = False
    for k in maximize:
        av = float(a.get(k, 0.0))
        bv = float(b.get(k, 0.0))
        if av < bv:
            better_or_eq = False
            break
        if av > bv:
            strictly_better = True
    if not better_or_eq:
        return False
    for k in minimize:
        av = float(a.get(k, 0.0))
        bv = float(b.get(k, 0.0))
        if av > bv:
            better_or_eq = False
            break
        if av < bv:
            strictly_better = True
    return better_or_eq and strictly_better


def nondominated_sort(
    rows: Sequence[Mapping[str, Any]],
    *,
    maximize: Sequence[str] = ("task_success_rate",),
    minimize: Sequence[str] = ("estimated_cost_usd", "latency_ms", "tool_call_count"),
    metrics_key: str = "metrics",
) -> list[dict[str, Any]]:
    frontier: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        mi = row.get(metrics_key) or row
        dominated = False
        for j, other in enumerate(rows):
            if i == j:
                continue
            mj = other.get(metrics_key) or other
            if dominates(mj, mi, maximize, minimize):
                dominated = True
                break
        if not dominated:
            frontier.append(dict(row))
    return frontier
