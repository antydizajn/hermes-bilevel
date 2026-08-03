"""Correlate Hermes events with provider records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CorrelationResult:
    left_id: str
    right_id: str
    quality: str  # exact|composite|heuristic|unmatched
    confidence: float
    explanation: dict[str, Any] = field(default_factory=dict)
    alternatives: list[str] = field(default_factory=list)


class CorrelationEngine:
    def __init__(self, max_time_window_s: float = 30.0) -> None:
        self.max_time_window_s = max_time_window_s

    def correlate(
        self,
        left: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
    ) -> CorrelationResult:
        left_id = str(left.get("event_id") or left.get("id") or "")
        # 1) exact IDs
        for c in candidates:
            rid = str(c.get("record_id") or c.get("id") or "")
            for key in ("provider_request_id", "tool_call_id", "turn_id"):
                lv = left.get(key)
                rv = c.get(key)
                if lv and rv and lv == rv:
                    return CorrelationResult(left_id, rid, "exact", 1.0, {"matched": key})
        # 2) composite
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for c in candidates:
            rid = str(c.get("record_id") or c.get("id") or "")
            features = []
            score = 0.0
            for key, weight in (
                ("session_id", 0.3),
                ("turn_id", 0.3),
                ("model", 0.1),
                ("request_hash", 0.4),
                ("payload_hash", 0.3),
            ):
                if left.get(key) and c.get(key) and left.get(key) == c.get(key):
                    score += weight
                    features.append(key)
            if score >= 0.7:
                scored.append((score, rid, {"matched": features, "mode": "composite"}))
            elif score >= 0.4:
                scored.append((min(score, 0.69), rid, {"matched": features, "mode": "heuristic"}))
        if not scored:
            return CorrelationResult(left_id, "", "unmatched", 0.0, {"reason": "no_candidates"})
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0]
        alts = [s[1] for s in scored[1:4] if abs(s[0] - best[0]) < 1e-9]
        quality = "composite" if best[2].get("mode") == "composite" else "heuristic"
        if alts and quality == "heuristic":
            return CorrelationResult(
                left_id, best[1], "heuristic", best[0], best[2], alternatives=alts
            )
        return CorrelationResult(left_id, best[1], quality, best[0], best[2], alternatives=alts)
