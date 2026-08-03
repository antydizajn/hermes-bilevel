from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from hermes_bilevel.cli import (
    _load_task_list,
    _print,
    hermes_bilevel_command,
    main,
    setup_hermes_cli,
)


def test_print_as_json(capsys):
    _print({"ok": True, "value": 42}, as_json=True)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["value"] == 42


def test_print_as_text_dict(capsys):
    _print({"ok": True, "value": 42}, as_json=False)
    captured = capsys.readouterr()
    assert "ok: True" in captured.out
    assert "value: 42" in captured.out


def test_print_as_text_custom_checks(capsys):
    data = {
        "checks": [
            {"status": "PASS", "name": "check1", "detail": "looks good"},
            {"status": "FAIL", "name": "check2", "detail": "bad"},
        ]
    }
    _print(data, as_json=False)
    captured = capsys.readouterr()
    assert "checks:" in captured.out
    assert "[PASS] check1: looks good" in captured.out
    assert "[FAIL] check2: bad" in captured.out


def test_print_as_text_non_dict(capsys):
    _print("hello text", as_json=False)
    captured = capsys.readouterr()
    assert "hello text" in captured.out.strip()


def test_load_task_list_invalid(tmp_path):
    f = tmp_path / "tasks.json"
    f.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="task file must be a JSON list"):
        _load_task_list(str(f))


def test_cli_version(capsys):
    code = main(["version", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "version" in data


def test_cli_init_and_status(tmp_path, capsys):
    state_root = tmp_path / "state"
    code = main(["--root", str(state_root), "init", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True

    # test status command
    code = main(["--root", str(state_root), "status", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    status = json.loads(captured.out)
    assert status["mode"] == "observe"
    assert status["events"] == 0


def test_cli_doctor(tmp_path, capsys):
    state_root = tmp_path / "state"
    # clean state, first init
    main(["--root", str(state_root), "init", "--json"])
    capsys.readouterr()  # clear init output
    code = main(["--root", str(state_root), "doctor", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["overall"] in {"PASS", "WARN", "FAIL"}


def test_cli_config_commands(tmp_path, capsys):
    state_root = tmp_path / "state"
    code = main(["--root", str(state_root), "config", "show", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    cfg_data = json.loads(captured.out)
    assert cfg_data["mode"] == "observe"

    # validate a config file
    cfg_file = tmp_path / "bilevel.yaml"
    cfg_file.write_text("mode: observe", encoding="utf-8")
    code = main(["config", "validate", str(cfg_file), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert res["mode"] == "observe"


def test_cli_registry_commands(capsys):
    code = main(["registry", "show", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    reg = json.loads(captured.out)
    assert "tools" in reg

    code = main(["registry", "hash", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert "registry_hash" in res


def test_cli_recorder_commands(tmp_path, capsys):
    # probe
    code = main(["recorder", "probe", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    probe_data = json.loads(captured.out)
    assert "jsonl" in probe_data

    # ingest & verify with a dummy jsonl recorder file
    rec_file = tmp_path / "records.jsonl"
    rec_file.write_text(
        json.dumps({"event_id": "e1", "event_type": "some_type"}) + "\n",
        encoding="utf-8",
    )
    code = main(["recorder", "ingest", "--path", str(rec_file), "--kind", "jsonl", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    ingest_data = json.loads(captured.out)
    assert ingest_data["count"] == 1

    code = main(["recorder", "verify", "--path", str(rec_file), "--kind", "jsonl", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    verify_data = json.loads(captured.out)
    assert verify_data["checked"] == 1


def test_cli_dataset_commands(tmp_path, capsys):
    # build a task file
    task_file = tmp_path / "tasks.json"
    tasks = [{"task_id": "t1", "input": "test input"}]
    task_file.write_text(json.dumps(tasks), encoding="utf-8")

    state_root = tmp_path / "state"
    main(["--root", str(state_root), "init", "--json"])
    capsys.readouterr()  # clear init output

    code = main([
        "--root", str(state_root),
        "dataset", "build",
        "--name", "test_ds",
        "--split", "inner_train",
        "--tasks", str(task_file),
        "--lock",
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    build_data = json.loads(captured.out)
    assert build_data["ok"] is True
    manifest_path = build_data["path"]

    # verify manifest
    code = main(["dataset", "verify", manifest_path, "--json"])
    assert code == 0
    captured = capsys.readouterr()
    verify_data = json.loads(captured.out)
    assert verify_data["ok"] is True

    # lock manifest
    code = main(["dataset", "lock", manifest_path, "--json"])
    assert code == 0
    captured = capsys.readouterr()
    lock_data = json.loads(captured.out)
    assert lock_data["manifest_hash"] is not None

    # inspect manifest
    code = main(["dataset", "inspect", manifest_path, "--json"])
    assert code == 0
    captured = capsys.readouterr()
    inspect_data = json.loads(captured.out)
    assert inspect_data["name"] == "test_ds"


def test_cli_candidate_commands(tmp_path, capsys):
    state_root = tmp_path / "state"
    main(["--root", str(state_root), "init", "--json"])
    capsys.readouterr()  # clear init output

    cand = {
        "target_type": "skill",
        "target_path": "skills/demo/SKILL.md",
        "hypothesis": "test hypothesis",
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
    cand_file = tmp_path / "candidate.json"
    cand_file.write_text(json.dumps(cand), encoding="utf-8")

    # propose stub (fails)
    code = main(["candidate", "propose", "--json"])
    assert code == 2
    captured = capsys.readouterr()
    propose_res = json.loads(captured.out)
    assert propose_res["status"] == "BLOCKED"

    # import
    code = main(["--root", str(state_root), "candidate", "import", str(cand_file), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    import_res = json.loads(captured.out)
    assert import_res["ok"] is True
    cand_id = import_res["candidate_id"]

    # inspect candidate via imported ID
    code = main(["--root", str(state_root), "candidate", "inspect", cand_id, "--json"])
    assert code == 0
    captured = capsys.readouterr()
    inspect_res = json.loads(captured.out)
    assert inspect_res["candidate_id"] == cand_id

    # validate candidate
    code = main(["--root", str(state_root), "candidate", "validate", cand_id, "--json"])
    assert code == 0
    captured = capsys.readouterr()
    validate_res = json.loads(captured.out)
    assert validate_res["ok"] is True

    # diff candidate
    code = main(["--root", str(state_root), "candidate", "diff", cand_id, "--json"])
    assert code == 0
    captured = capsys.readouterr()
    diff_res = json.loads(captured.out)
    assert "patch" in diff_res

    # lineage candidate
    code = main(["--root", str(state_root), "candidate", "lineage", cand_id, "--json"])
    assert code == 0
    captured = capsys.readouterr()
    lineage_res = json.loads(captured.out)
    assert lineage_res["candidate_id"] == cand_id


def test_cli_candidate_errors(tmp_path, capsys):
    state_root = tmp_path / "state"
    main(["--root", str(state_root), "init", "--json"])
    capsys.readouterr()  # clear init output

    # 1. Invalid candidate validation failure
    invalid_cand = {"target_type": "skill"}
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(json.dumps(invalid_cand), encoding="utf-8")

    code = main(["--root", str(state_root), "candidate", "import", str(invalid_file), "--json"])
    assert code == 1
    captured = capsys.readouterr()
    assert "schema" in captured.out

    # 2. Candidate not found
    code = main(["--root", str(state_root), "candidate", "inspect", "nonexistent_id", "--json"])
    assert code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_cli_experiment_stubs(capsys):
    # Test all experiment stubs create, validate, resume, cancel, inspect
    for subcmd in ("create", "validate", "resume", "cancel", "inspect"):
        code = main(["experiment", subcmd, "123", "--json"])
        assert code == 2
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == subcmd
        assert data["status"] == "NOT_IMPLEMENTED"


def test_cli_compare_pareto_report_dossier(tmp_path, capsys):
    # create a mock evaluation result file
    res = [{
        "result_id": "res_1",
        "candidate_hash": "sha256:abc",
        "dataset_hash": "sha256:xyz",
        "metrics": {"purity": 1.0, "time_ns": 1000},
        "label": "EPISODE_PASS",
        "purity_checks": [],
    }]
    res_file = tmp_path / "results.json"
    res_file.write_text(json.dumps(res), encoding="utf-8")

    # compare
    code = main(["compare", "--results", str(res_file), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    comp_data = json.loads(captured.out)
    assert "results" in comp_data

    # pareto
    code = main(["pareto", "--results", str(res_file), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    pareto_data = json.loads(captured.out)
    assert isinstance(pareto_data, list)

    # report
    code = main(["report", "--results", str(res_file), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    report_data = json.loads(captured.out)
    assert "results" in report_data

    # markdown report
    code = main(["report", "--results", str(res_file), "--markdown"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Bilevel comparison report" in captured.out

    # dossier
    cand = {"candidate_id": "cand_1", "candidate_hash": "sha256:abc"}
    cand_file = tmp_path / "candidate.json"
    cand_file.write_text(json.dumps(cand), encoding="utf-8")
    code = main(["dossier", "--candidate", str(cand_file), "--results", str(res_file), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    dos_data = json.loads(captured.out)
    assert dos_data["candidate_hash"] == "sha256:abc"


def test_cli_approval_and_promote(tmp_path, capsys):
    # approval create
    code = main(["approval", "create", "--candidate-hash", "sha256:abc", "--approved-by", "Paulina", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    app_data = json.loads(captured.out)
    assert app_data["candidate_hash"] == "sha256:abc"
    assert app_data["approved_by"] == "Paulina"

    # approval verify
    app_file = tmp_path / "approval.json"
    app_file.write_text(json.dumps(app_data), encoding="utf-8")
    code = main(["approval", "verify", str(app_file), "--candidate-hash", "sha256:abc", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    ver_data = json.loads(captured.out)
    assert ver_data["ok"] is True

    # promote
    cand = {"candidate_id": "cand_1", "candidate_hash": "sha256:abc"}
    cand_file = tmp_path / "candidate.json"
    cand_file.write_text(json.dumps(cand), encoding="utf-8")

    state_root = tmp_path / "state"
    # Write config enabling promotion
    cfg_file = tmp_path / "bilevel.yaml"
    cfg_file.write_text("promotion:\n  enabled: true\n  automatic: false", encoding="utf-8")

    code = main([
        "--config", str(cfg_file),
        "--root", str(state_root),
        "promote",
        "--candidate", str(cand_file),
        "--approval", str(app_file),
        "--dry-run",
        "--json"
    ])
    assert code == 2
    captured = capsys.readouterr()
    promo_data = json.loads(captured.out)
    assert promo_data["ok"] is False


def test_cli_rollback_stub(capsys):
    code = main(["rollback", "--json"])
    assert code == 2
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "NOT_IMPLEMENTED_BY_DESIGN"


def test_cli_integrity_and_audit(tmp_path, capsys):
    state_root = tmp_path / "state"
    main(["--root", str(state_root), "init", "--json"])
    capsys.readouterr()  # clear init output

    code = main(["--root", str(state_root), "integrity", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["integrity"] == "ok"

    code = main(["--root", str(state_root), "audit", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert "audit_events" in res


def test_hermes_cli_wrappers(tmp_path, capsys):
    # test setup_hermes_cli
    parser = MagicMock()
    setup_hermes_cli(parser)
    assert parser.add_argument.call_count == 3

    # test hermes_bilevel_command
    args = MagicMock()
    args.bilevel_args = ["version", "--json"]
    args.config = None
    args.root = str(tmp_path / "state")
    code = hermes_bilevel_command(args)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "version" in data

    # test hermes_bilevel_command with lead -- and empty args (maps to doctor)
    args2 = MagicMock()
    args2.bilevel_args = ["--"]
    args2.config = None
    args2.root = str(tmp_path / "state")
    code = hermes_bilevel_command(args2)
    # doctor on non-init state root returns 1 (degraded/not initialized) or 0 if passing safety
    assert code in {0, 1}


def test_cli_error_handling(capsys):
    # test dispatch raises ConfigError
    # We pass a non-existent config path which causes load_config to raise ConfigError (or FileNotFoundError)
    # Wait, load_config raises ConfigError if the structure is bad, or FileNotFoundError.
    # Let's verify how ConfigError is raised.
    # In cli.py:
    # try:
    #     cfg = load_config(args.config, ...)
    # except ConfigError as e:
    #     ...
    # Let's make main() load an invalid config.
    # Let's write an invalid YAML file:
    # schema.py will fail validation on load_config if the yaml is corrupt or invalid schema.
    # Let's pass a file that causes ConfigError.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tf:
        tf.write(b"mode: invalid_mode_name\n")
        tf_name = tf.name

    code = main(["--config", tf_name, "version", "--json"])
    assert code == 2
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is False
    assert "invalid_mode_name" in data["error"] or "mode" in data["error"]


def test_cli_selftest(capsys, monkeypatch):
    # Test successful selftest run
    code = main(["selftest", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True

    # Test SelfTestError exception handling
    from hermes_bilevel.selftest import SelfTestError
    def mock_run_selftest():
        raise SelfTestError("Self-test mock failure")
    monkeypatch.setattr("hermes_bilevel.cli.run_selftest", mock_run_selftest)

    code = main(["selftest", "--json"])
    assert code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert "Self-test mock failure" in res["error"]


def test_cli_doctor_failure(tmp_path, capsys, monkeypatch):
    state_root = tmp_path / "state"
    main(["--root", str(state_root), "init", "--json"])
    capsys.readouterr()  # clear output

    # Cause get_runtime to raise an exception
    def mock_get_runtime(*args, **kwargs):
        raise RuntimeError("failed to load database or layout")
    monkeypatch.setattr("hermes_bilevel.cli.get_runtime", mock_get_runtime)

    code = main(["--root", str(state_root), "doctor", "--json"])
    assert code in {0, 1}
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert "overall" in res


def test_cli_registry_validate_hash(capsys):
    # test registry validate
    code = main(["registry", "validate", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    reg = json.loads(captured.out)
    assert "tools" in reg


def test_cli_experiment_run_details(tmp_path, capsys):
    state_root = tmp_path / "state"
    main(["--root", str(state_root), "init", "--json"])
    capsys.readouterr()  # clear output

    # 1. Candidate not found
    code = main([
        "--root", str(state_root),
        "experiment", "run",
        "--candidate", "nonexistent_cand",
        "--tasks", "nonexistent_tasks",
        "--json"
    ])
    assert code == 1
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert "candidate not found" in res["reason"]

    # 2. Allow model call mismatch
    # Write a config with model_calls.enabled = false
    cfg_file = tmp_path / "bilevel.yaml"
    cfg_file.write_text("model_calls:\n  enabled: false", encoding="utf-8")
    code = main([
        "--config", str(cfg_file),
        "--root", str(state_root),
        "experiment", "run",
        "--candidate", "any",
        "--tasks", "any",
        "--allow-model-call",
        "--json"
    ])
    assert code == 2
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert "model_calls.enabled=false" in res["reason"]

