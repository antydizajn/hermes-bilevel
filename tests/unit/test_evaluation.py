from __future__ import annotations

from hermes_bilevel.candidates.validate import validate_candidate
from hermes_bilevel.evaluation.engine import evaluate_candidate_synthetic_fixture


def test_det_eval_pass():
    c = validate_candidate(
        {
            "target_type": "skill",
            "target_path": "skills/x/SKILL.md",
            "hypothesis": "include TOKEN for success",
            "patch": "diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n"
                     "new file mode 100644\n"
                     "--- /dev/null\n"
                     "+++ b/skills/x/SKILL.md\n"
                     "@@ -0,0 +1,1 @@\n"
                     "+TOKEN please\n",
        }
    )
    tasks = [{"task_id": "t1", "expected_token": "TOKEN"}]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 1.0
    assert r["label"] == "FIXTURE_PASS"


def test_evaluation_engine_validators():
    c = {
        "candidate_hash": "sha256:abc",
        "status": "validated",
        "patch": "diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n+TOKEN please",
    }

    # 1. validator "artifact_exists" - check pass & fail
    tasks = [{
        "task_id": "t1",
        "validators": [{"type": "artifact_exists", "name": "patch_len"}],
        "always_pass": True,
    }]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 1.0

    tasks = [{
        "task_id": "t1",
        "validators": [{"type": "artifact_exists", "name": "non_existent_artifact"}],
        "always_pass": True,
    }]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 0.0

    # 2. validator "equals" - check pass & fail
    tasks = [{
        "task_id": "t1",
        "validators": [{"type": "equals", "key": "output", "value": "ok"}],
        "always_pass": True,
    }]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 1.0

    tasks = [{
        "task_id": "t1",
        "validators": [{"type": "equals", "key": "output", "value": "wrong_value"}],
        "always_pass": True,
    }]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 0.0

    # 3. validator "contains" - check pass & fail
    tasks = [{
        "task_id": "t1",
        "validators": [{"type": "contains", "key": "output", "value": "o"}],
        "always_pass": True,
    }]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 1.0

    tasks = [{
        "task_id": "t1",
        "validators": [{"type": "contains", "key": "output", "value": "z"}],
        "always_pass": True,
    }]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 0.0

    # 4. Unknown validator type
    tasks = [{
        "task_id": "t1",
        "validators": [{"type": "unknown_type"}],
        "always_pass": True,
    }]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["metrics"]["task_success_rate"] == 0.0


def test_evaluation_engine_hard_gates():
    # 1. Invalid status
    c1 = {
        "candidate_hash": "sha256:abc",
        "status": "rejected",
    }
    tasks = [{"task_id": "t1", "always_pass": True}]
    r = evaluate_candidate_synthetic_fixture(c1, tasks)
    assert r["label"] == "INVALID"
    assert r["hard_gate_ok"] is False

    # 2. Missing hash
    c2 = {
        "status": "validated",
    }
    r = evaluate_candidate_synthetic_fixture(c2, tasks)
    assert r["label"] == "INVALID"
    assert r["hard_gate_ok"] is False


def test_evaluation_engine_purity_checks():
    from hermes_bilevel.purity.registry import PurityRegistry
    c = {
        "candidate_hash": "sha256:abc",
        "status": "validated",
        "patch": "diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n+TOKEN please",
    }
    tasks = [{
        "task_id": "t1",
        "always_pass": True,
        "allowed_tools": ["cronjob"],
        "denied_tools": ["web_search"],
    }]
    reg = PurityRegistry({"rules": {"scheduler": "deny"}})
    # classify mutates, classifies correctly
    r = evaluate_candidate_synthetic_fixture(c, tasks, purity=reg)
    assert r["metrics"]["task_success_rate"] == 1.0

