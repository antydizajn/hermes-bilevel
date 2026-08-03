"""Non-LLM random baseline proposer."""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import Any


class RandomSearchBackend:
    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def propose(
        self,
        evidence: Mapping[str, Any],
        search_space: Mapping[str, Any],
        count: int,
        budget: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        rng = random.Random(self.seed)
        target = str(search_space.get("target_type") or "skill")
        path = str(search_space.get("target_path") or "skills/example/SKILL.md")
        token = str(evidence.get("target_token") or "BASELINE")
        out: list[Mapping[str, Any]] = []
        for _i in range(max(0, int(count))):
            tag = f"R{rng.randint(1000, 9999)}"
            out.append(
                {
                    "target_type": target,
                    "target_path": path,
                    "hypothesis": f"random baseline variant {tag} improves {token}",
                    "mechanism": "random_token_injection",
                    "patch": f"--- a/{path}\n+++ b/{path}\n@@\n+{token}-{tag}\n",
                    "proposer_backend": "random_search",
                    "parent_hash": evidence.get("baseline_hash"),
                }
            )
        return out
