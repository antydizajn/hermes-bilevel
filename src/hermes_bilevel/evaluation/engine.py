"""Deterministic evaluation (no model judge required)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.evaluation.metrics import compute_basic_metrics
from hermes_bilevel.ids import SortableIdGenerator, SystemClock
from hermes_bilevel.purity.registry import PurityRegistry

_ids = SortableIdGenerator()
_clock = SystemClock()


def _run_validators(task: Mapping[str, Any], artifacts: Mapping[str, Any]) -> bool:
    validators = task.get("validators") or []
    if not validators:
        # default: require hypothesis non-empty already validated at candidate stage
        return True
    for v in validators:
        vtype = v.get("type") if isinstance(v, Mapping) else None
        if vtype == "artifact_exists":
            name = v.get("name")
            if name not in artifacts:
                return False
        elif vtype == "equals":
            if artifacts.get(v.get("key")) != v.get("value"):
                return False
        elif vtype == "contains":
            hay = str(artifacts.get(v.get("key") or "", ""))
            if str(v.get("value") or "") not in hay:
                return False
        else:
            # unknown validator => fail closed for deterministic mode
            return False
    return True


def evaluate_candidate_synthetic_fixture(
    candidate: Mapping[str, Any],
    tasks: Sequence[Mapping[str, Any]],
    *,
    purity: PurityRegistry | None = None,
    seeds: Sequence[int] | None = None,
    mode: str = "synthetic_fixture",
) -> dict[str, Any]:
    """Evaluate candidate with deterministic validators only.

    mode labels: synthetic_fixture
    """
    seeds = list(seeds or [0])
    successes: list[bool] = []
    per_task: list[dict[str, Any]] = []
    hard_gate_ok = True
    purity_violations = 0

    # hard gates
    if candidate.get("status") not in {None, "validated", "imported"}:
        hard_gate_ok = False
    if not candidate.get("candidate_hash"):
        hard_gate_ok = False

    for task in tasks:
        allowed = set(task.get("allowed_tools") or [])
        denied = set(task.get("denied_tools") or [])
        # purity check for allowed tools
        if purity is not None:
            for tname in allowed:
                d = purity.classify(tname)
                if d.classification.value == "MUTATING_REMOTE":
                    # not a violation to list; replay would be denied elsewhere
                    pass
            for _tname in denied:
                pass
        # simulate deterministic artifact from patch content hash interaction with task
        # This is intentionally simple and fully deterministic for offline labs.
        patch = str(candidate.get("patch") or "")
        expected_token = str(task.get("expected_token") or task.get("task_id") or "")
        artifact_ok = expected_token in patch or bool(task.get("always_pass"))
        artifacts = {
            "patch_len": len(patch),
            "contains_expected_token": artifact_ok,
            "output": "ok" if artifact_ok else "miss",
        }
        ok = (
            hard_gate_ok
            and _run_validators(task, artifacts)
            and artifacts["contains_expected_token"]
        )
        # if task has explicit validators, those dominate contains_expected_token only when present
        if task.get("validators"):
            ok = hard_gate_ok and _run_validators(task, artifacts)
        successes.append(bool(ok))
        per_task.append(
            {
                "task_id": task.get("task_id"),
                "success": bool(ok),
                "artifacts": artifacts,
                "seed": seeds[0],
            }
        )

    metrics = compute_basic_metrics(
        successes=successes,
        tool_calls=int(candidate.get("tool_call_count") or 0),
        purity_violations=purity_violations,
    )
    label = (
        "INVALID"
        if not hard_gate_ok
        else (
            "FIXTURE_PASS"
            if metrics["task_success_rate"] >= 1.0
            else "FIXTURE_FAIL"
        )
    )
    body = {
        "result_id": _ids.new_id("eval"),
        "created_at": _clock.now_rfc3339(),
        "candidate_hash": candidate.get("candidate_hash"),
        "evaluation_mode": "synthetic_fixture",
        "metrics": metrics,
        "per_task": per_task,
        "hard_gate_ok": hard_gate_ok,
        "label": label,
        "seeds": list(seeds),
    }
    body["result_hash"] = hash_canonical(body)
    return body
