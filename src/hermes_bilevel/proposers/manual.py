"""Manual proposal backend — imports operator-authored candidates only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ManualProposalBackend:
    def __init__(self, candidates: list[Mapping[str, Any]] | None = None) -> None:
        self._candidates = list(candidates or [])

    def propose(
        self,
        evidence: Mapping[str, Any],
        search_space: Mapping[str, Any],
        count: int,
        budget: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        return list(self._candidates)[: max(0, int(count))]
