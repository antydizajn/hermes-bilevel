# Changelog

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
