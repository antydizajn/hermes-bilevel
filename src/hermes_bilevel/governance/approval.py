"""Approval verification — candidates cannot self-approve."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from hermes_bilevel.protocols import VerificationResult


def _parse_ts(ts: str) -> datetime:
    t = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(t)


def verify_approval(
    approval: Mapping[str, Any],
    *,
    candidate_hash: str,
    baseline_hash: str | None = None,
    dataset_hashes: Mapping[str, str] | None = None,
    evaluator_contract_hash: str | None = None,
    now: datetime | None = None,
) -> VerificationResult:
    if not isinstance(approval, Mapping):
        return VerificationResult(False, "approval must be mapping")
    if approval.get("decision") != "approve":
        return VerificationResult(False, "decision is not approve")
    if approval.get("candidate_hash") != candidate_hash:
        return VerificationResult(False, "candidate_hash mismatch")
    if baseline_hash is not None and approval.get("baseline_hash") not in {None, baseline_hash}:
        if approval.get("baseline_hash") != baseline_hash:
            return VerificationResult(False, "baseline_hash mismatch")
    if evaluator_contract_hash is not None and approval.get("evaluator_contract_hash") not in {None, evaluator_contract_hash}:
        if approval.get("evaluator_contract_hash") != evaluator_contract_hash:
            return VerificationResult(False, "evaluator_contract_hash mismatch")
    if dataset_hashes:
        ah = approval.get("dataset_hashes") or {}
        for k, v in dataset_hashes.items():
            if ah.get(k) != v:
                return VerificationResult(False, f"dataset_hashes mismatch for {k}")
    if not approval.get("approved_by"):
        return VerificationResult(False, "approved_by required")
    # candidate must not be approver
    if str(approval.get("approved_by")).startswith("cand_") or approval.get("approved_by") == approval.get("candidate_hash"):
        return VerificationResult(False, "candidate cannot approve itself")
    exp = approval.get("expires_at")
    if exp:
        now = now or datetime.now(timezone.utc)
        try:
            if _parse_ts(str(exp)) < now:
                return VerificationResult(False, "approval expired")
        except Exception:
            return VerificationResult(False, "invalid expires_at")
    return VerificationResult(True, "ok")
