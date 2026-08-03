from __future__ import annotations

from hermes_bilevel.candidates.validate import validate_candidate
from hermes_bilevel.evaluation.engine import evaluate_candidate_deterministic


def test_det_eval_pass():
    c = validate_candidate(
        {
            "target_type": "skill",
            "target_path": "skills/x/SKILL.md",
            "hypothesis": "include TOKEN for success",
            "patch": "TOKEN please\n",
        }
    )
    tasks = [{"task_id": "t1", "expected_token": "TOKEN"}]
    r = evaluate_candidate_deterministic(c, tasks)
    assert r["metrics"]["task_success_rate"] == 1.0
