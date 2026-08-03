"""Promotion control plane.

v0.1: dossier-only. Live promotion returns NOT_IMPLEMENTED_BY_DESIGN unless
explicitly enabled AND approval verified — still refuses automatic mode.
"""
from __future__ import annotations

from typing import Any, Mapping

from hermes_bilevel.governance.approval import verify_approval


def promote_candidate(
    candidate: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    *,
    promotion_enabled: bool = False,
    automatic: bool = False,
    baseline_hash: str | None = None,
    dataset_hashes: Mapping[str, str] | None = None,
    evaluator_contract_hash: str | None = None,
) -> dict[str, Any]:
    if automatic:
        return {
            "ok": False,
            "status": "NOT_IMPLEMENTED_BY_DESIGN",
            "reason": "automatic promotion is not supported",
        }
    if not promotion_enabled:
        return {
            "ok": False,
            "status": "BLOCKED",
            "reason": "promotion.enabled=false (dossier-only in v0.1)",
        }
    if approval is None:
        return {"ok": False, "status": "BLOCKED", "reason": "approval artifact required"}
    vr = verify_approval(
        approval,
        candidate_hash=str(candidate.get("candidate_hash")),
        baseline_hash=baseline_hash,
        dataset_hashes=dataset_hashes,
        evaluator_contract_hash=evaluator_contract_hash,
    )
    if not vr.ok:
        return {"ok": False, "status": "BLOCKED", "reason": vr.reason}
    # Even when enabled, v0.1 does not mutate live Hermes installation.
    return {
        "ok": False,
        "status": "NOT_IMPLEMENTED_BY_DESIGN",
        "reason": "live promotion deferred; use dossier + manual operator action outside plugin",
        "candidate_hash": candidate.get("candidate_hash"),
    }
