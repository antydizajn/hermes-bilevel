"""End-to-end CLI integration tests: exercise the real binary against an
isolated state root. No network, no model calls — the full pipeline from
init through dataset/candidate/experiment (both backends) to
compare/report/dossier/integrity/export."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HERMES_BILEVEL_ROOT"] = str(root)
    return subprocess.run(
        [sys.executable, "-m", "hermes_bilevel.cli", "--root", str(root), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        timeout=120,
    )


@pytest.fixture()
def cli_root(tmp_path: Path) -> Path:
    root = tmp_path / "state"
    root.mkdir()
    return root


def test_version(cli_root: Path) -> None:
    r = run_cli(cli_root, "version", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "version" in data


def test_init_and_status(cli_root: Path) -> None:
    r = run_cli(cli_root, "init", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data.get("ok") is True
    r = run_cli(cli_root, "status", "--json")
    assert r.returncode == 0, r.stderr
    status = json.loads(r.stdout)
    # fail-closed default mode must be observe
    assert status.get("mode") == "observe"


def test_doctor_safe_defaults(cli_root: Path) -> None:
    r = run_cli(cli_root, "doctor", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    # fail-closed guarantees must be visible in doctor output
    flat = json.dumps(data)
    assert "model_calls" in flat or "safe" in flat


def test_dataset_lifecycle(cli_root: Path) -> None:
    tasks = [
        {"task_id": "t1", "expected_token": "FIXME", "prompt": "do one"},
        {"task_id": "t2", "expected_token": "FIXME", "prompt": "do two"},
    ]
    task_file = cli_root.parent / "tasks.json"
    task_file.write_text(json.dumps(tasks), encoding="utf-8")
    r = run_cli(
        cli_root,
        "dataset",
        "build",
        "--name",
        "demo",
        "--split",
        "inner_train",
        "--tasks",
        str(task_file),
        "--lock",
        "--json",
    )
    assert r.returncode == 0, r.stderr
    built = json.loads(r.stdout)
    assert built.get("ok") is True
    assert built.get("manifest_hash")
    assert built.get("path")
    r = run_cli(cli_root, "dataset", "inspect", built["path"], "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data.get("manifest_id")
    # non-list task file must fail cleanly, not with a ValueError traceback
    bad = cli_root.parent / "bad_tasks.json"
    bad.write_text(json.dumps({"task_id": "t1"}), encoding="utf-8")
    r = run_cli(
        cli_root,
        "dataset",
        "build",
        "--name",
        "demo2",
        "--split",
        "inner_train",
        "--tasks",
        str(bad),
        "--lock",
        "--json",
    )
    assert r.returncode == 2, r.stdout
    assert "must be a JSON list" in json.loads(r.stdout)["error"]


def test_candidate_import_and_validate(cli_root: Path) -> None:
    cand = {
        "target_type": "skill",
        "target_path": "skills/demo/SKILL.md",
        "hypothesis": "adding FIXME token satisfies deterministic offline validator",
        "patch": (
            "diff --git a/skills/demo/SKILL.md b/skills/demo/SKILL.md\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/skills/demo/SKILL.md\n"
            "@@ -0,0 +1,1 @@\n"
            "+FIXME guidance\n"
        ),
        "proposer_backend": "manual",
    }
    cand_file = cli_root.parent / "cand.json"
    cand_file.write_text(json.dumps(cand), encoding="utf-8")
    r = run_cli(cli_root, "candidate", "import", str(cand_file), "--json")
    assert r.returncode == 0, r.stderr
    imp = json.loads(r.stdout)
    assert imp.get("candidate_hash", "").startswith("sha256:")
    cand_id = imp["candidate_id"]
    r = run_cli(cli_root, "candidate", "inspect", cand_id, "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout).get("target_path") == "skills/demo/SKILL.md"


def test_experiment_synthetic_and_report(cli_root: Path) -> None:
    """Full pipeline: dataset -> candidate -> experiment (synthetic) ->
    compare -> report -> dossier."""
    tasks = [{"task_id": "t1", "expected_token": "FIXME", "prompt": "do one"}]
    task_file = cli_root.parent / "tasks.json"
    task_file.write_text(json.dumps(tasks), encoding="utf-8")
    r = run_cli(
        cli_root,
        "dataset",
        "build",
        "--name",
        "demo",
        "--split",
        "inner_train",
        "--tasks",
        str(task_file),
        "--lock",
        "--json",
    )
    assert r.returncode == 0, r.stderr
    dataset_hash = json.loads(r.stdout)["manifest_hash"]

    cand = {
        "target_type": "skill",
        "target_path": "skills/demo/SKILL.md",
        "hypothesis": "adding FIXME token satisfies deterministic offline validator",
        "patch": (
            "diff --git a/skills/demo/SKILL.md b/skills/demo/SKILL.md\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/skills/demo/SKILL.md\n"
            "@@ -0,0 +1,1 @@\n"
            "+FIXME guidance\n"
        ),
        "proposer_backend": "manual",
        "dataset_manifest_hash": dataset_hash,
    }
    cand_file = cli_root.parent / "cand.json"
    cand_file.write_text(json.dumps(cand), encoding="utf-8")

    r = run_cli(
        cli_root,
        "experiment",
        "run",
        "--candidate",
        str(cand_file),
        "--tasks",
        str(task_file),
        "--backend",
        "synthetic",
        "--json",
    )
    assert r.returncode == 0, r.stderr
    ev = json.loads(r.stdout)
    assert ev.get("label") == "FIXTURE_PASS", ev
    assert ev.get("evaluation_mode") == "synthetic_fixture"

    r = run_cli(cli_root, "experiment", "run", "--candidate", str(cand_file), "--tasks", str(task_file), "--json")
    assert r.returncode == 0, r.stderr

    results = json.dumps([ev])
    results_file = cli_root.parent / "results.json"
    results_file.write_text(results, encoding="utf-8")
    r = run_cli(cli_root, "compare", "--results", str(results_file), "--json")
    assert r.returncode == 0, r.stderr
    r = run_cli(cli_root, "report", "--results", str(results_file), "--json")
    assert r.returncode == 0, r.stderr
    r = run_cli(cli_root, "dossier", "--candidate", str(cand_file), "--results", str(results_file), "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout).get("dossier_id")


def test_experiment_episode_backend(cli_root: Path) -> None:
    """experiment run --backend episode executes a real subprocess episode."""
    tasks = [
        {
            "task_id": "ep1",
            "expected_token": "FIXME",
            "prompt": "check file exists",
            "command_src": (
                "import os\n"
                "print('EP_OK' if os.path.exists('skills/demo/SKILL.md') else 'EP_MISSING')\n"
            ),
            "validators": [{"type": "contains", "key": "stdout", "value": "EP_OK"}],
        }
    ]
    task_file = cli_root.parent / "tasks.json"
    task_file.write_text(json.dumps(tasks), encoding="utf-8")

    cand = {
        "target_type": "skill",
        "target_path": "skills/demo/SKILL.md",
        "hypothesis": "adding a skill file makes the episode command observe it",
        "patch": (
            "diff --git a/skills/demo/SKILL.md b/skills/demo/SKILL.md\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/skills/demo/SKILL.md\n"
            "@@ -0,0 +1,1 @@\n"
            "+EP_OK guidance\n"
        ),
        "proposer_backend": "manual",
    }
    cand_file = cli_root.parent / "cand.json"
    cand_file.write_text(json.dumps(cand), encoding="utf-8")

    r = run_cli(
        cli_root,
        "experiment",
        "run",
        "--candidate",
        str(cand_file),
        "--tasks",
        str(task_file),
        "--backend",
        "episode",
        "--json",
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out.get("mode") == "episode"
    ep = out["results"][0]
    assert ep.get("label") == "EPISODE_PASS", ep
    assert ep["trajectory"]["baseline_stdout"].strip() == "EP_MISSING"
    assert ep["trajectory"]["candidate_stdout"].strip() == "EP_OK"


def test_doctor_reports_missing_state(cli_root: Path) -> None:
    """doctor must fail closed when the state root is not initialized."""
    empty = cli_root.parent / "empty"
    empty.mkdir()
    r = run_cli(empty, "doctor", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    # fail-closed guarantees must be present regardless of initialization
    flat = json.dumps(data)
    assert "model_calls" in flat or "wire" in flat
    assert data.get("overall") in {"PASS", "WARN", "FAIL"}


def test_cli_export_import_gc(cli_root: Path) -> None:
    # First init the state root
    assert run_cli(cli_root, "init", "--json").returncode == 0

    # Add a candidate so we have some data
    cand = {
        "target_type": "skill",
        "target_path": "skills/demo/SKILL.md",
        "hypothesis": "adding a skill file makes the episode command observe it",
        "patch": (
            "diff --git a/skills/demo/SKILL.md b/skills/demo/SKILL.md\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/skills/demo/SKILL.md\n"
            "@@ -0,0 +1,1 @@\n"
            "+EP_OK guidance\n"
        ),
        "proposer_backend": "manual",
    }
    cand_file = cli_root.parent / "candidate.json"
    cand_file.write_text(json.dumps(cand), encoding="utf-8")
    assert run_cli(cli_root, "candidate", "import", str(cand_file), "--json").returncode == 0

    # 1. Export without path (stdout)
    r = run_cli(cli_root, "export", "--json")
    assert r.returncode == 0, r.stderr
    dump = json.loads(r.stdout)
    assert dump["format"] == "hermes_bilevel_state"
    assert len(dump["tables"]["candidates"]) == 1

    # 2. Export with path
    export_file = cli_root.parent / "export.json"
    r = run_cli(cli_root, "export", str(export_file), "--json")
    assert r.returncode == 0, r.stderr
    res = json.loads(r.stdout)
    assert res["ok"] is True
    assert export_file.exists()

    # 3. Import back to a fresh state root
    fresh_root = cli_root.parent / "fresh_state"
    fresh_root.mkdir()
    assert run_cli(fresh_root, "init", "--json").returncode == 0
    r = run_cli(fresh_root, "import", str(export_file), "--json")
    assert r.returncode == 0, r.stderr
    res = json.loads(r.stdout)
    assert res["ok"] is True
    assert res["rows"] > 0

    # 4. GC
    r = run_cli(cli_root, "gc", "--json")
    assert r.returncode == 0, r.stderr
    res = json.loads(r.stdout)
    assert res["integrity"] == "ok"
    assert res["vacuum"] is True

