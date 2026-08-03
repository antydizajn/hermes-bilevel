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


def test_promote_blocked_by_default():
    res = promote_candidate({"candidate_hash": "sha256:x"}, None, promotion_enabled=False)
    assert res["ok"] is False
    auto = promote_candidate({"candidate_hash": "sha256:x"}, {"decision": "approve"}, automatic=True)
    assert auto["status"] == "NOT_IMPLEMENTED_BY_DESIGN"
