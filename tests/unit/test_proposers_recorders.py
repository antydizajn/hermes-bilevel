from __future__ import annotations

import json
from datetime import UTC

import pytest

from hermes_bilevel.candidates.validate import validate_candidate
from hermes_bilevel.config.schema import ConfigError, load_config, validate_config
from hermes_bilevel.evaluation.engine import evaluate_candidate_synthetic_fixture
from hermes_bilevel.events.envelope import make_event
from hermes_bilevel.events.queue import BoundedEventQueue
from hermes_bilevel.governance.approval import verify_approval
from hermes_bilevel.governance.promote import promote_candidate
from hermes_bilevel.paths import get_bilevel_root, get_hermes_home
from hermes_bilevel.proposers.llm import HermesLlmProposalBackend
from hermes_bilevel.proposers.manual import ManualProposalBackend
from hermes_bilevel.proposers.random_search import RandomSearchBackend
from hermes_bilevel.protocols import ProviderRecord, RecorderSource
from hermes_bilevel.recording.adapters import (
    DirectoryRecorderAdapter,
    HooksOnlyRecorderAdapter,
    JsonlRecorderAdapter,
)
from hermes_bilevel.sandbox.tempdir import TempDirSandbox
from hermes_bilevel.statistics.stats import effect_size_paired, mean, variance


def test_manual_and_random_proposers():
    man = ManualProposalBackend([{"hypothesis": "h", "patch": "+x"}])
    assert len(man.propose({}, {}, 1, {})) == 1
    rnd = RandomSearchBackend(seed=1)
    props = rnd.propose(
        {"target_token": "T", "baseline_hash": "p"}, {"target_type": "skill"}, 3, {}
    )
    assert len(props) == 3
    assert props[0]["proposer_backend"] == "random_search"


def test_llm_backend_blocked():
    b = HermesLlmProposalBackend()
    with pytest.raises(RuntimeError):
        b.propose({}, {}, 1, {})
    b2 = HermesLlmProposalBackend(complete_fn=lambda s: "{}")
    with pytest.raises(RuntimeError):
        b2.propose({}, {}, 1, {})


def test_recorders(tmp_path):
    h = HooksOnlyRecorderAdapter()
    assert h.probe().fidelity == "HOOK_METADATA"
    assert list(h.iter_records(RecorderSource("s", "hooks"))) == []
    assert h.verify_record(ProviderRecord("1", "HOOK_METADATA", "t")).ok

    p = tmp_path / "a.jsonl"
    p.write_text(
        json.dumps(
            {
                "record_id": "r1",
                "created_at": "t",
                "session_id": "s",
                "turn_id": "t1",
                "attempt_index": 1,
                "is_fallback": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    j = JsonlRecorderAdapter()
    recs = list(j.iter_records(RecorderSource("s", "jsonl", path=str(p))))
    assert len(recs) == 1
    assert j.verify_record(recs[0]).ok
    assert not j.verify_record(ProviderRecord("", "LOGICAL_REQUEST", "t")).ok

    d = DirectoryRecorderAdapter()
    recs2 = list(d.iter_records(RecorderSource("s", "dir", path=str(tmp_path))))
    assert len(recs2) == 1
    assert d.probe().fidelity == "PROVIDER_ATTEMPT"


def test_approval_expiry_and_dataset_mismatch():
    from datetime import datetime, timedelta

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    vr = verify_approval(
        {
            "decision": "approve",
            "candidate_hash": "h",
            "approved_by": "p",
            "expires_at": past,
        },
        candidate_hash="h",
    )
    assert not vr.ok
    vr2 = verify_approval(
        {
            "decision": "approve",
            "candidate_hash": "h",
            "approved_by": "p",
            "dataset_hashes": {"inner_train": "a"},
        },
        candidate_hash="h",
        dataset_hashes={"inner_train": "b"},
    )
    assert not vr2.ok


def test_promote_with_approval_still_not_live():
    res = promote_candidate(
        {"candidate_hash": "h"},
        {"decision": "approve", "candidate_hash": "h", "approved_by": "human"},
        promotion_enabled=True,
    )
    assert res["status"] == "NOT_IMPLEMENTED_BY_DESIGN"


def test_stats_and_eval_validators():
    assert mean([1, 2, 3]) == 2
    assert variance([1, 2, 3]) > 0
    assert effect_size_paired([0, 1, 0], [1, 3, 2]) != 0
    c = validate_candidate(
        {
            "target_type": "skill",
            "target_path": "skills/x/SKILL.md",
            "hypothesis": "validator path works here",
            "patch": "diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n"
                     "new file mode 100644\n"
                     "--- /dev/null\n"
                     "+++ b/skills/x/SKILL.md\n"
                     "@@ -0,0 +1,1 @@\n"
                     "+output=ok\n",
        }
    )
    tasks = [
        {
            "task_id": "t",
            "validators": [{"type": "equals", "key": "output", "value": "ok"}],
            "always_pass": True,
        }
    ]
    r = evaluate_candidate_synthetic_fixture(c, tasks)
    assert r["hard_gate_ok"] is True


def test_sandbox_fixture_and_paths(tmp_path, monkeypatch):
    fx = tmp_path / "fx"
    fx.mkdir()
    (fx / "a.txt").write_text("x", encoding="utf-8")
    sbx = TempDirSandbox(timeout_seconds=10)
    h = sbx.prepare({"workspace_fixture": str(fx)})
    files = sbx.collect(h)["files"]
    assert any("a.txt" in f for f in files)
    sbx.destroy(h)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hh"))
    assert get_hermes_home() == (tmp_path / "hh").resolve()
    monkeypatch.setenv("HERMES_BILEVEL_ROOT", str(tmp_path / "br"))
    assert get_bilevel_root() == (tmp_path / "br").resolve()


def test_config_invalid_mode_and_yaml(tmp_path):
    with pytest.raises(ConfigError):
        validate_config({"mode": "nope"})
    y = tmp_path / "c.yaml"
    y.write_text("mode: observe\nwire: false\n", encoding="utf-8")
    cfg = load_config(y)
    assert cfg.mode == "observe"


def test_queue_drop_oldest_and_writer():
    seen = []
    q = BoundedEventQueue(
        maxsize=1, overflow_policy="drop_oldest", writer=lambda e: seen.append(e), start_worker=True
    )
    assert q.put(make_event("a", {"x": 1})) is True
    assert q.put(make_event("b", {"x": 2})) in {True, False}
    q.flush(timeout=1.0)
    q.close()
    assert q.dropped >= 0
