from __future__ import annotations

from hermes_bilevel.governance.approval import verify_approval
from hermes_bilevel.governance.promote import promote_candidate


def test_approval_ok_and_self_approve_denied():
    ok = verify_approval(
        {
            "decision": "approve",
            "candidate_hash": "sha256:abc",
            "approved_by": "paulina",
        },
        candidate_hash="sha256:abc",
    )
    assert ok.ok
    bad = verify_approval(
        {
            "decision": "approve",
            "candidate_hash": "sha256:abc",
            "approved_by": "sha256:abc",
        },
        candidate_hash="sha256:abc",
    )
    assert not bad.ok


def test_approval_validation_failures():
    # 1. Not a mapping
    assert not verify_approval("not a mapping", candidate_hash="sha256:abc").ok  # type: ignore[arg-type]

    # 2. Decision is not approve
    assert not verify_approval(
        {"decision": "deny", "candidate_hash": "sha256:abc", "approved_by": "paulina"},
        candidate_hash="sha256:abc"
    ).ok

    # 3. Candidate hash mismatch
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:other", "approved_by": "paulina"},
        candidate_hash="sha256:abc"
    ).ok

    # 4. Baseline hash mismatch
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:abc", "baseline_hash": "sha256:wrong", "approved_by": "paulina"},
        candidate_hash="sha256:abc",
        baseline_hash="sha256:correct"
    ).ok

    # 5. Evaluator contract hash mismatch
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:abc", "evaluator_contract_hash": "sha256:wrong", "approved_by": "paulina"},
        candidate_hash="sha256:abc",
        evaluator_contract_hash="sha256:correct"
    ).ok

    # 6. Dataset hashes mismatch
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:abc", "dataset_hashes": {"ds1": "sha256:wrong"}, "approved_by": "paulina"},
        candidate_hash="sha256:abc",
        dataset_hashes={"ds1": "sha256:correct"}
    ).ok

    # 7. Approved_by is missing
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:abc"},
        candidate_hash="sha256:abc"
    ).ok

    # 8. Approved_by starts with cand_
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:abc", "approved_by": "cand_paulina"},
        candidate_hash="sha256:abc"
    ).ok

    # 9. Expires_at is expired
    from datetime import UTC, datetime
    now = datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC)
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:abc", "approved_by": "paulina", "expires_at": "2026-08-03T11:59:00Z"},
        candidate_hash="sha256:abc",
        now=now
    ).ok

    # 10. Invalid expires_at syntax
    assert not verify_approval(
        {"decision": "approve", "candidate_hash": "sha256:abc", "approved_by": "paulina", "expires_at": "not-a-date"},
        candidate_hash="sha256:abc"
    ).ok


def test_promote_blocked_by_default():
    res = promote_candidate({"candidate_hash": "sha256:x"}, None, promotion_enabled=False)
    assert res["ok"] is False
    auto = promote_candidate(
        {"candidate_hash": "sha256:x"}, {"decision": "approve"}, automatic=True
    )
    assert auto["status"] == "NOT_IMPLEMENTED_BY_DESIGN"
