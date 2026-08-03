"""Metric definitions — precise names only."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def compute_basic_metrics(
    *,
    successes: Sequence[bool],
    tool_calls: int = 0,
    duplicate_tool_calls: int = 0,
    tool_errors: int = 0,
    timeouts: int = 0,
    remote_mutation_attempts: int = 0,
    purity_violations: int = 0,
    token_usage: int = 0,
    estimated_cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    retries: int = 0,
    fallbacks: int = 0,
) -> dict[str, Any]:
    n = len(successes)
    task_success_rate = (sum(1 for s in successes if s) / n) if n else 0.0
    return {
        "episode_count": n,
        "task_success_rate": task_success_rate,
        "deterministic_validator_success_rate": task_success_rate,
        "tool_call_count": tool_calls,
        "duplicate_tool_call_count": duplicate_tool_calls,
        "tool_error_count": tool_errors,
        "timeout_count": timeouts,
        "remote_mutation_attempts": remote_mutation_attempts,
        "purity_violations": purity_violations,
        "token_usage": token_usage,
        "estimated_cost_usd": estimated_cost_usd,
        "latency_ms": latency_ms,
        "retry_count": retries,
        "fallback_count": fallbacks,
    }
