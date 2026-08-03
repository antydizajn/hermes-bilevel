# Changelog

## [0.1.2] - 2026-08-03

### Added
- E2E integration tests for the whole CLI surface
  (`tests/integration/test_cli_e2e.py`): real binary against an isolated
  state root — version/init/status, doctor fail-closed defaults, dataset
  build+inspect, candidate import+inspect, full synthetic pipeline
  (dataset -> candidate -> experiment -> compare -> report -> dossier), and
  the real episode backend (baseline MISSING vs candidate OK).
- `_load_task_list` in the CLI: JSON task files must be lists; malformed
  input returns a clean exit-2 error instead of a ValueError traceback.

### Changed
- Episode backend runs against the repo in the CWD (the system being
  optimized); the state root is used for the store only.
- Coverage gate raised from 71% to 75%.

## [0.1.1] - 2026-08-03

### Added
- Real inner-loop episode runner (`hermes_bilevel/episodes/runner.py`):
  candidate patch is applied with `git apply` in a disposable worktree of the
  target repo and a paired baseline-vs-candidate subprocess episode runs with
  deterministic fail-closed validators.
- `experiment run --backend {synthetic|episode}` CLI wiring.
- E2E episode tests (paired pass, validator fail, non-repo rejection,
  non-applicable patch, worktree cleanup).

### Changed
- `validate_candidate(..., workspace_root=)` forwards workspace_root to
  `check_patch_applicability` so applicability is checked against the target
  repo rather than the current working directory.
- `check_patch_applicability` validates against a real disposable worktree of
  the workspace repo (HEAD) instead of a simulated temp repo with empty
  stubs; `git apply --check` no longer uses `--recount`, so stated hunk line
  numbers must be truthful.
- Queue overflow policy `block` renamed to the honest `bounded_block`
  (legacy alias still accepted).
- Self-test now applies a patch and runs a real subprocess episode instead of
  writing a patch file and running a detached `print('ok')` sandbox.

## [0.1.0] - 2026-08-03

### Added
- Initial public alpha of hermes-bilevel.
- Observe-only Hermes plugin registration (hooks, CLI, slash command, skill).
- Fail-closed defaults: no model calls, no promotion, no wire capture, no mutation.
- Event envelope, canonicalization, redaction, SQLite+blob storage.
- Recorder adapters (hooks-only, JSONL, directory).
- Correlation engine with exact/composite/heuristic/unmatched quality labels.
- Tool purity registry with deny-unknown default.
- Dataset manifests with train/selection/heldout separation.
- Manual candidate import + validation pipeline.
- Deterministic evaluation, Pareto comparison, reports, promotion dossiers.
- Offline deterministic self-test.
- Packaging via hermes_agent.plugins entry point `bilevel`.
