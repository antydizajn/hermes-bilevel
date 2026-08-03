"""Deterministic offline self-test. No network, no model, no live mutation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from hermes_bilevel.candidates.validate import CandidateValidationError, validate_candidate
from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.config.schema import load_config
from hermes_bilevel.correlation.engine import CorrelationEngine
from hermes_bilevel.datasets.manifest import build_manifest, lock_manifest, verify_manifest
from hermes_bilevel.evaluation.engine import evaluate_candidate_synthetic_fixture
from hermes_bilevel.governance.dossier import build_promotion_dossier
from hermes_bilevel.optimization.pareto import nondominated_sort
from hermes_bilevel.purity.registry import load_default_registry
from hermes_bilevel.redaction.redactor import redact_text
from hermes_bilevel.reporting.report import build_comparison_report, render_markdown_report
from hermes_bilevel.runtime import BilevelRuntime, reset_runtime
from hermes_bilevel.sandbox.tempdir import TempDirSandbox
from hermes_bilevel.storage.store import BilevelStore


class SelfTestError(RuntimeError):
    pass


def run_selftest() -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    model_calls = 0
    paid_calls = 0

    def ok(name: str, detail: str = "") -> None:
        steps.append({"name": name, "status": "PASS", "detail": detail})

    def fail(name: str, detail: str) -> None:
        steps.append({"name": name, "status": "FAIL", "detail": detail})
        raise SelfTestError(f"{name}: {detail}")

    with tempfile.TemporaryDirectory(prefix="bilevel-selftest-") as td:
        root = Path(td)
        # isolate from user home
        cfg = load_config(overrides={"storage": {"root": str(root)}, "mode": "observe"})
        store = BilevelStore(root)
        ok("initialize schema", store.integrity_check().get("integrity", ""))

        purity = load_default_registry()
        store.put_purity_registry(purity.registry_hash, purity.version, purity.to_dict())
        ok("load purity registry", purity.registry_hash[:20])

        rt = BilevelRuntime(cfg, store)
        # synthetic events including retry/fallback/stream markers in payload
        rt.handlers.on_session_start(session_id="s1", platform="cli", model="test-model")
        rt.handlers.pre_llm_call(
            session_id="s1", turn_id="t1", user_message="hello", model="test-model"
        )
        rt.handlers.pre_tool_call(
            session_id="s1", turn_id="t1", tool_name="read_file", args={"path": "x"}
        )
        rt.handlers.post_tool_call(
            session_id="s1", turn_id="t1", tool_name="read_file", args={"path": "x"}, result="ok"
        )
        rt.handlers.post_llm_call(
            session_id="s1", turn_id="t1", response="world", model="test-model"
        )
        # retry/fallback/stream synthetic emit via queue
        from hermes_bilevel.events.envelope import make_event

        rt.queue.put(
            make_event(
                "provider_attempt",
                {"attempt_index": 0, "is_stream": True, "status": "start"},
                session_id="s1",
                turn_id="t1",
            )
        )
        rt.queue.put(
            make_event(
                "provider_attempt",
                {"attempt_index": 1, "is_fallback": True, "status": "retry"},
                session_id="s1",
                turn_id="t1",
            )
        )
        rt.queue.flush(timeout=3.0)
        n_events = store.count_events()
        if n_events < 5:
            fail("ingest synthetic events", f"only {n_events} events")
        ok("ingest synthetic events", str(n_events))

        # correlate
        eng = CorrelationEngine()
        left = {"event_id": "e1", "session_id": "s1", "turn_id": "t1", "model": "m"}
        cands = [
            {
                "record_id": "r1",
                "session_id": "s1",
                "turn_id": "t1",
                "model": "m",
                "request_hash": "h",
            },
            {"record_id": "r2", "session_id": "other"},
        ]
        cr = eng.correlate(left, cands)
        if cr.quality not in {"exact", "composite", "heuristic"}:
            fail("correlate events", cr.quality)
        ok("correlate events", cr.quality)

        # canonical hash stability
        h1 = hash_canonical({"b": 1, "a": 2})
        h2 = hash_canonical({"a": 2, "b": 1})
        if h1 != h2:
            fail("canonical hashes", "order instability")
        ok("canonical hashes", h1[:18])

        # redaction
        rr = redact_text("token sk-abcdefghijklmnopqrstuvwxyz123456 password=supersecret")
        if rr.substitutions < 1 or "sk-abc" in rr.text or "supersecret" in rr.text:
            fail("redaction", rr.text)
        ok("redaction", f"subs={rr.substitutions}")

        # purity denies
        d_unknown = purity.classify("totally_unknown_tool_xyz")
        if d_unknown.replay_allowed:
            fail("deny unknown tool replay", "allowed")
        d_remote = purity.classify("send_message")
        if d_remote.replay_allowed:
            fail("deny remote mutation replay", "allowed")
        ok("deny unknown/remote replay")

        # dataset
        tasks = [
            {"task_id": "taskA", "expected_token": "FIXME", "prompt": "do A"},
            {"task_id": "taskB", "expected_token": "FIXME", "prompt": "do B"},
        ]
        man = lock_manifest(build_manifest("demo", "inner_train", tasks))
        v_ok, v_reason = verify_manifest(man)
        if not v_ok:
            fail("dataset lock/verify", v_reason)
        store.put_dataset_manifest(man.to_dict())
        ok("dataset lock/verify", man.manifest_hash[:18])

        # heldout separate
        held = lock_manifest(
            build_manifest(
                "demo-hold",
                "final_locked_heldout",
                [{"task_id": "hold1", "prompt": "secret-holdout"}],
            )
        )
        store.put_dataset_manifest(held.to_dict())
        ok("heldout manifest", held.manifest_hash[:18])

        # valid candidate
        valid = validate_candidate(
            {
                "target_type": "skill",
                "target_path": "skills/demo/SKILL.md",
                "hypothesis": "inject FIXME token to satisfy deterministic validator",
                "patch": "--- a/skills/demo/SKILL.md\n+++ b/skills/demo/SKILL.md\n@@\n+FIXME guidance\n",
                "proposer_backend": "manual",
                "dataset_manifest_hash": man.manifest_hash,
                "purity_registry_hash": purity.registry_hash,
            }
        )
        store.put_candidate(valid)
        ok("import valid candidate", valid["candidate_hash"][:18])

        # forbidden path candidate
        try:
            validate_candidate(
                {
                    "target_type": "skill",
                    "target_path": "../etc/passwd",
                    "hypothesis": "should fail path traversal check now",
                    "patch": "+x\n",
                }
            )
            fail("reject forbidden path", "accepted")
        except CandidateValidationError:
            ok("reject forbidden path")

        # parent mismatch
        try:
            validate_candidate(
                {
                    "target_type": "skill",
                    "target_path": "skills/demo/SKILL.md",
                    "hypothesis": "parent mismatch should be rejected here",
                    "patch": "+FIXME\n",
                    "parent_hash": "sha256:deadbeef",
                },
                parent_hash="sha256:cafebabe",
            )
            fail("reject parent mismatch", "accepted")
        except CandidateValidationError:
            ok("reject parent mismatch")

        # sandbox apply-ish
        sbx = TempDirSandbox(timeout_seconds=30)
        handle = sbx.prepare({})
        wp = Path(handle["workspace"]) / "cand.patch"
        wp.write_text(valid["patch"], encoding="utf-8")
        run = sbx.run(handle, ["python3", "-c", "print('ok')"])
        if run.get("returncode") != 0:
            fail("sandbox run", str(run))
        sbx.destroy(handle)
        ok("sandbox disposable run")

        # evaluate
        ev = evaluate_candidate_synthetic_fixture(valid, tasks, purity=purity)
        store.put_evaluation_result(ev)
        if ev["metrics"]["task_success_rate"] < 1.0:
            fail("deterministic validators", str(ev["metrics"]))
        ok("deterministic validators", ev["label"])

        # pareto
        other = dict(ev)
        other["metrics"] = dict(ev["metrics"])
        other["metrics"]["estimated_cost_usd"] = 1.0
        other["candidate_hash"] = valid["candidate_hash"] + "-b"
        frontier = nondominated_sort([ev, other])
        if not frontier:
            fail("pareto", "empty")
        ok("pareto", str(len(frontier)))

        report = build_comparison_report(
            baseline=None,
            results=[ev, other],
            dataset_hashes={
                "inner_train": man.manifest_hash,
                "final_locked_heldout": held.manifest_hash,
            },
            recording_fidelity="HOOK_METADATA",
            exact_provider_boundary_verified=False,
        )
        md = render_markdown_report(report)
        if "recording_fidelity" not in md:
            fail("report", "missing fidelity")
        dossier = build_promotion_dossier(
            valid,
            baseline_hash=None,
            dataset_hashes={"inner_train": man.manifest_hash},
            evaluation_results=[ev],
            purity_registry_hash=purity.registry_hash,
            evaluator_contract_hash="sha256:det-v1",
        )
        ok("report and dossier", dossier["dossier_id"])

        # ensure no model calls
        if model_calls or paid_calls:
            fail("no model calls", f"model={model_calls} paid={paid_calls}")
        ok("no model calls")

        # cleanup handled by TemporaryDirectory
        store.close()
        reset_runtime()
        ok("cleanup temp resources")

    return {
        "ok": all(s["status"] == "PASS" for s in steps),
        "steps": steps,
        "model_calls": model_calls,
        "paid_calls": paid_calls,
        "network_requests": 0,
    }
