"""Hermes host-owned LLM proposal backend.

Does not call models unless dual-gated by config + CLI flag at a higher layer.
This class itself is a pure interface/test double container in v0.1.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping


class HermesLlmProposalBackend:
    def __init__(self, complete_fn: Callable[[str], str] | None = None) -> None:
        self.complete_fn = complete_fn

    def propose(
        self,
        evidence: Mapping[str, Any],
        search_space: Mapping[str, Any],
        count: int,
        budget: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        if self.complete_fn is None:
            raise RuntimeError(
                "HermesLlmProposalBackend requires explicit complete_fn and dual activation; "
                "no silent model calls"
            )
        # Intentionally minimal: higher layer must enforce budgets/gates and parse/validate.
        _ = self.complete_fn
        raise RuntimeError("LLM proposal execution is disabled unless dual-gated by CLI layer")
