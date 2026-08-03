"""CLI for hermes-bilevel.

Works as:
  - `hermes bilevel ...` via PluginContext.register_cli_command
  - `hermes-bilevel ...` console script
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from hermes_bilevel.candidates.validate import CandidateValidationError, validate_candidate
from hermes_bilevel.config.schema import ConfigError, load_config
from hermes_bilevel.datasets.manifest import build_manifest, lock_manifest, verify_manifest
from hermes_bilevel.doctor import run_doctor
from hermes_bilevel.evaluation.engine import evaluate_candidate_synthetic_fixture
from hermes_bilevel.governance.dossier import build_promotion_dossier
from hermes_bilevel.governance.promote import promote_candidate
from hermes_bilevel.paths import get_bilevel_root
from hermes_bilevel.purity.registry import load_default_registry
from hermes_bilevel.recording.adapters import (
    DirectoryRecorderAdapter,
    HooksOnlyRecorderAdapter,
    JsonlRecorderAdapter,
)
from hermes_bilevel.reporting.report import build_comparison_report, render_markdown_report
from hermes_bilevel.runtime import get_runtime
from hermes_bilevel.selftest import SelfTestError, run_selftest
from hermes_bilevel.version import __version__


def _print(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                if k == "checks" and isinstance(v, list):
                    print("checks:")
                    for c in v:
                        print(f"  [{c.get('status')}] {c.get('name')}: {c.get('detail')}")
                else:
                    print(f"{k}: {v}")
        else:
            print(data)


def _add_json(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="machine-readable JSON output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hermes-bilevel", description="Auditable bilevel lab for Hermes Agent"
    )
    parser.add_argument("--config", default=None, help="path to bilevel config yaml/json")
    parser.add_argument("--root", default=None, help="override state root")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("version", help="show version")
    _add_json(p)

    p = sub.add_parser("init", help="initialize state directory")
    _add_json(p)

    p = sub.add_parser("doctor", help="run readiness/safety checks")
    _add_json(p)

    p = sub.add_parser("status", help="show runtime status")
    _add_json(p)

    p = sub.add_parser("selftest", help="offline deterministic self-test")
    _add_json(p)

    p = sub.add_parser("config")
    csub = p.add_subparsers(dest="config_cmd", required=True)
    p2 = csub.add_parser("show")
    _add_json(p2)
    p2 = csub.add_parser("validate")
    p2.add_argument("path", nargs="?", default=None)
    _add_json(p2)

    p = sub.add_parser("registry")
    rsub = p.add_subparsers(dest="registry_cmd", required=True)
    for name in ("show", "validate", "hash"):
        pp = rsub.add_parser(name)
        _add_json(pp)

    p = sub.add_parser("recorder")
    rec = p.add_subparsers(dest="recorder_cmd", required=True)
    for name in ("probe", "ingest", "verify"):
        pp = rec.add_parser(name)
        if name != "probe":
            pp.add_argument("--path", required=True)
            pp.add_argument("--kind", default="jsonl", choices=["jsonl", "directory", "hooks"])
        _add_json(pp)

    p = sub.add_parser("dataset")
    dsub = p.add_subparsers(dest="dataset_cmd", required=True)
    b = dsub.add_parser("build")
    b.add_argument("--name", required=True)
    b.add_argument(
        "--split", required=True, choices=["inner_train", "outer_selection", "final_locked_heldout"]
    )
    b.add_argument("--tasks", required=True, help="JSON file with task list")
    b.add_argument("--lock", action="store_true")
    _add_json(b)
    for name in ("inspect", "verify", "lock"):
        pp = dsub.add_parser(name)
        pp.add_argument("manifest", help="manifest json path")
        _add_json(pp)

    p = sub.add_parser("candidate")
    csub = p.add_subparsers(dest="candidate_cmd", required=True)
    imp = csub.add_parser("import")
    imp.add_argument("path")
    _add_json(imp)
    for name in ("inspect", "validate", "diff", "lineage"):
        pp = csub.add_parser(name)
        pp.add_argument("id_or_path")
        _add_json(pp)
    prop = csub.add_parser("propose")
    prop.add_argument("--allow-model-call", action="store_true")
    _add_json(prop)

    p = sub.add_parser("experiment")
    esub = p.add_subparsers(dest="experiment_cmd", required=True)
    runp = esub.add_parser("run")
    runp.add_argument("--candidate", required=True)
    runp.add_argument("--tasks", required=True)
    runp.add_argument("--backend", default="synthetic", choices=["synthetic", "episode"])
    runp.add_argument("--allow-model-call", action="store_true")
    runp.add_argument("--dry-run", action="store_true")
    _add_json(runp)
    for name in ("create", "validate", "resume", "cancel", "inspect"):
        pp = esub.add_parser(name)
        pp.add_argument("id", nargs="?")
        _add_json(pp)

    p = sub.add_parser("compare")
    p.add_argument("--results", required=True, help="JSON list of evaluation results")
    _add_json(p)

    p = sub.add_parser("pareto")
    p.add_argument("--results", required=True)
    _add_json(p)

    p = sub.add_parser("report")
    p.add_argument("--results", required=True)
    p.add_argument("--markdown", action="store_true")
    _add_json(p)

    p = sub.add_parser("dossier")
    p.add_argument("--candidate", required=True)
    p.add_argument("--results", required=True)
    _add_json(p)

    p = sub.add_parser("approval")
    asub = p.add_subparsers(dest="approval_cmd", required=True)
    ac = asub.add_parser("create")
    ac.add_argument("--candidate-hash", required=True)
    ac.add_argument("--approved-by", required=True)
    _add_json(ac)
    av = asub.add_parser("verify")
    av.add_argument("path")
    av.add_argument("--candidate-hash", required=True)
    _add_json(av)

    p = sub.add_parser("promote")
    p.add_argument("--candidate", required=True)
    p.add_argument("--approval", default=None)
    p.add_argument("--dry-run", action="store_true")
    _add_json(p)

    p = sub.add_parser("rollback")
    _add_json(p)

    for name in ("audit", "integrity", "export", "import", "gc"):
        pp = sub.add_parser(name)
        if name in {"export", "import"}:
            pp.add_argument("path", nargs="?")
        _add_json(pp)

    return parser


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dispatch(args: argparse.Namespace) -> int:
    as_json = bool(getattr(args, "json", False))
    try:
        cfg = load_config(
            args.config, overrides={"storage": {"root": args.root}} if args.root else None
        )
    except ConfigError as e:
        _print({"ok": False, "error": str(e)}, True)
        return 2

    cmd = args.cmd

    if cmd == "version":
        _print({"version": __version__}, as_json or True)
        return 0

    if cmd == "init":
        root = get_bilevel_root(cfg.get("storage", "root") or args.root)
        rt: Any = get_runtime(cfg, str(root))
        _print({"ok": True, "root": str(root), "integrity": rt.store.integrity_check()}, as_json)
        return 0

    if cmd == "doctor":
        rt = None
        try:
            rt = get_runtime(cfg, args.root)
        except Exception:
            pass
        rep = run_doctor(cfg, runtime=rt)
        _print(rep, as_json)
        return 0 if rep["overall"] == "PASS" else 1

    if cmd == "status":
        rt = get_runtime(cfg, args.root)
        _print(
            {
                "mode": cfg.mode,
                "wire": cfg.wire,
                "content_mode": cfg.content_mode,
                "events": rt.store.count_events(),
                "dropped": rt.store.loss_count(),
                "queue_size": rt.queue.qsize(),
                "root": str(rt.store.root),
                "plugin_version": __version__,
            },
            as_json,
        )
        return 0

    if cmd == "selftest":
        try:
            result = run_selftest()
        except SelfTestError as e:
            _print({"ok": False, "error": str(e)}, True)
            return 1
        _print(result, as_json or True)
        return 0 if result.get("ok") else 1

    if cmd == "config":
        if args.config_cmd == "show":
            _print(cfg.to_dict(), as_json or True)
            return 0
        if args.config_cmd == "validate":
            c2 = load_config(args.path)
            _print({"ok": True, "hash": c2.hash(), "mode": c2.mode}, as_json)
            return 0

    if cmd == "registry":
        reg = load_default_registry(
            cfg.get("purity", "registry_path"),
            unknown_policy=str(cfg.get("purity", "unknown_policy", default="deny")),
        )
        if args.registry_cmd == "hash":
            _print({"registry_hash": reg.registry_hash}, as_json)
        else:
            _print(reg.to_dict(), as_json or True)
        return 0

    if cmd == "recorder":
        if args.recorder_cmd == "probe":
            adapters = {
                "hooks": HooksOnlyRecorderAdapter().probe(),
                "jsonl": JsonlRecorderAdapter().probe(),
                "directory": DirectoryRecorderAdapter().probe(),
            }
            _print({k: v.__dict__ for k, v in adapters.items()}, as_json or True)
            return 0
        from hermes_bilevel.protocols import RecorderSource

        kind = args.kind
        adapter: Any = {
            "jsonl": JsonlRecorderAdapter(),
            "directory": DirectoryRecorderAdapter(),
            "hooks": HooksOnlyRecorderAdapter(),
        }[kind]
        src = RecorderSource(source_id="cli", kind=kind, path=args.path)
        if args.recorder_cmd == "ingest":
            recs = list(adapter.iter_records(src))
            _print({"count": len(recs), "fidelity": adapter.probe().fidelity}, as_json)
            return 0
        if args.recorder_cmd == "verify":
            recs = list(adapter.iter_records(src))
            results = [adapter.verify_record(r).__dict__ for r in recs[:20]]
            _print({"checked": len(results), "results": results}, as_json)
            return 0

    if cmd == "dataset":
        if args.dataset_cmd == "build":
            tasks = _load_json(args.tasks)
            man = build_manifest(args.name, args.split, tasks)
            if args.lock:
                man = lock_manifest(man)
            out = (
                get_bilevel_root(cfg.get("storage", "root") or args.root)
                / "datasets"
                / f"{man.manifest_id}.json"
            )
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(man.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            rt = get_runtime(cfg, args.root)
            rt.store.put_dataset_manifest(man.to_dict())
            _print({"ok": True, "path": str(out), "manifest_hash": man.manifest_hash}, as_json)
            return 0
        data = _load_json(args.manifest)
        if args.dataset_cmd == "verify":
            ok, reason = verify_manifest(data)
            _print({"ok": ok, "reason": reason}, as_json)
            return 0 if ok else 1
        if args.dataset_cmd == "lock":
            from hermes_bilevel.datasets.manifest import DatasetManifest

            man = DatasetManifest(
                **{k: data[k] for k in DatasetManifest.__dataclass_fields__ if k in data}
            )
            locked = lock_manifest(man)
            Path(args.manifest).write_text(
                json.dumps(locked.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
            )
            _print({"ok": True, "manifest_hash": locked.manifest_hash}, as_json)
            return 0
        if args.dataset_cmd == "inspect":
            _print(data, as_json or True)
            return 0

    if cmd == "candidate":
        if args.candidate_cmd == "propose":
            _print(
                {
                    "ok": False,
                    "status": "BLOCKED",
                    "reason": "LLM propose requires model_calls.enabled and --allow-model-call; use candidate import in v0.1",
                },
                True,
            )
            return 2
        if args.candidate_cmd == "import":
            raw = _load_json(args.path)
            try:
                cand: Any = validate_candidate(raw)
            except CandidateValidationError as e:
                _print({"ok": False, "code": e.code, "reason": e.reason}, True)
                return 1
            rt = get_runtime(cfg, args.root)
            rt.store.put_candidate(cand)
            out = rt.store.paths["candidates"] / f"{cand['candidate_id']}.json"
            out.write_text(json.dumps(cand, indent=2, sort_keys=True), encoding="utf-8")
            _print(
                {
                    "ok": True,
                    "candidate_id": cand["candidate_id"],
                    "candidate_hash": cand["candidate_hash"],
                    "path": str(out),
                },
                as_json,
            )
            return 0
        # inspect/validate/diff/lineage
        target = args.id_or_path
        rt = get_runtime(cfg, args.root)
        data = None
        if Path(target).exists():
            data = _load_json(target)
        else:
            data = rt.store.get_candidate(target)
        if not data:
            _print({"ok": False, "reason": "not found"}, True)
            return 1
        if args.candidate_cmd == "validate":
            try:
                cand = validate_candidate(data)
                _print({"ok": True, "candidate_hash": cand["candidate_hash"]}, as_json)
                return 0
            except CandidateValidationError as e:
                _print({"ok": False, "reason": e.reason, "code": e.code}, True)
                return 1
        if args.candidate_cmd == "diff":
            _print({"patch": data.get("patch")}, as_json)
            return 0
        if args.candidate_cmd == "lineage":
            _print(
                {
                    "candidate_id": data.get("candidate_id"),
                    "parent_hash": data.get("parent_hash"),
                    "candidate_hash": data.get("candidate_hash"),
                },
                as_json,
            )
            return 0
        _print(data, as_json or True)
        return 0

    if cmd == "experiment" and args.experiment_cmd == "run":
        if args.allow_model_call and not cfg.get("model_calls", "enabled"):
            _print({"ok": False, "reason": "model_calls.enabled=false"}, True)
            return 2
        cand = (
            _load_json(args.candidate)
            if Path(args.candidate).exists()
            else get_runtime(cfg, args.root).store.get_candidate(args.candidate)
        )
        if not cand:
            _print({"ok": False, "reason": "candidate not found"}, True)
            return 1
        tasks = _load_json(args.tasks)
        if args.dry_run:
            _print({"ok": True, "dry_run": True, "tasks": len(tasks)}, as_json)
            return 0
        purity = load_default_registry()
        if args.backend == "episode":
            from hermes_bilevel.episodes.runner import EpisodeError, EpisodeRunner

            runner = EpisodeRunner(workspace_root=args.root or ".")
            results = []
            try:
                for task in tasks:
                    results.append(runner.run(cand, task))
            except EpisodeError as e:
                _print({"ok": False, "reason": f"episode backend failed: {e}"}, True)
                return 2
            result = {"mode": "episode", "results": results}
        else:
            result = evaluate_candidate_synthetic_fixture(cand, tasks, purity=purity)
        get_runtime(cfg, args.root).store.put_evaluation_result(result)
        _print(result, as_json or True)
        return 0

    if cmd in {"compare", "pareto", "report"}:
        results = _load_json(args.results)
        if cmd == "pareto":
            from hermes_bilevel.optimization.pareto import nondominated_sort

            _print(nondominated_sort(results), as_json or True)
            return 0
        rep = build_comparison_report(baseline=None, results=results, dataset_hashes={})
        if cmd == "report" and args.markdown:
            print(render_markdown_report(rep))
            return 0
        _print(rep, as_json or True)
        return 0

    if cmd == "dossier":
        cand = (
            _load_json(args.candidate)
            if Path(args.candidate).exists()
            else get_runtime(cfg, args.root).store.get_candidate(args.candidate)
        )
        results = _load_json(args.results)
        dos = build_promotion_dossier(
            cand or {},
            baseline_hash=None,
            dataset_hashes={},
            evaluation_results=results if isinstance(results, list) else [results],
            purity_registry_hash=load_default_registry().registry_hash,
            evaluator_contract_hash="sha256:det-v1",
        )
        _print(dos, as_json or True)
        return 0

    if cmd == "approval":
        if args.approval_cmd == "create":
            body = {
                "schema_version": "1.0.0",
                "candidate_hash": args.candidate_hash,
                "approved_by": args.approved_by,
                "approved_at": __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "expires_at": None,
                "scope": "dossier_only",
                "decision": "approve",
            }
            _print(body, as_json or True)
            return 0
        if args.approval_cmd == "verify":
            from hermes_bilevel.governance.approval import verify_approval

            approval = _load_json(args.path)
            vr = verify_approval(approval, candidate_hash=args.candidate_hash)
            _print(vr.__dict__, as_json or True)
            return 0 if vr.ok else 1

    if cmd == "promote":
        cand = (
            _load_json(args.candidate)
            if Path(args.candidate).exists()
            else get_runtime(cfg, args.root).store.get_candidate(args.candidate)
        )
        approval = _load_json(args.approval) if args.approval else None
        res = promote_candidate(
            cand or {},
            approval,
            promotion_enabled=bool(cfg.get("promotion", "enabled")),
            automatic=bool(cfg.get("promotion", "automatic")),
        )
        _print(res, as_json or True)
        return 0 if res.get("ok") else 2

    if cmd == "rollback":
        _print(
            {
                "ok": False,
                "status": "NOT_IMPLEMENTED_BY_DESIGN",
                "reason": "live rollback deferred; dossier-only v0.1",
            },
            True,
        )
        return 2

    if cmd == "integrity":
        rt = get_runtime(cfg, args.root)
        _print(rt.store.integrity_check(), as_json or True)
        return 0

    if cmd == "audit":
        rt = get_runtime(cfg, args.root)
        with rt.store._lock:
            rows = rt.store._conn.execute(
                "SELECT * FROM audit_events ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        events = [dict(row) for row in rows]
        _print({"ok": True, "audit_events": events}, as_json or True)
        return 0

    if cmd in {"export", "import", "gc"}:
        _print(
            {
                "ok": False,
                "status": "NOT_IMPLEMENTED",
                "command": cmd,
                "reason": f"{cmd} command is planned; use SQLite backup/vacuum in v0.1",
            },
            True,
        )
        return 2

    # experiment stubs
    if cmd == "experiment":
        _print(
            {
                "ok": False,
                "status": "NOT_IMPLEMENTED",
                "command": getattr(args, "experiment_cmd", "run"),
                "reason": "multi-seed active experiment loop deferred; use evaluate command in v0.1",
            },
            True,
        )
        return 2

    _print({"ok": False, "error": f"unknown command {cmd}"}, True)
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return dispatch(args)
    except BrokenPipeError:  # pragma: no cover
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 1


# --- Hermes plugin CLI registration helpers ---


def setup_hermes_cli(subparser: argparse.ArgumentParser) -> None:
    """Populate `hermes bilevel` subparser with the same commands."""
    # Rebuild using our parser's subparsers by parsing known structure.
    # argparse doesn't easily copy; recreate commands on provided subparser.
    subparser.add_argument("--config", default=None)
    subparser.add_argument("--root", default=None)
    # Use parent parser pattern: add a catch-all remaining args and re-parse.
    subparser.add_argument(
        "bilevel_args", nargs=argparse.REMAINDER, help="bilevel subcommand and args"
    )


def hermes_bilevel_command(args: argparse.Namespace) -> int:
    rest = list(getattr(args, "bilevel_args", []) or [])
    # strip leading `--` if present
    if rest and rest[0] == "--":
        rest = rest[1:]
    argv = []
    if getattr(args, "config", None):
        argv += ["--config", args.config]
    if getattr(args, "root", None):
        argv += ["--root", args.root]
    argv += rest
    if not rest:
        argv += ["doctor", "--json"]
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
