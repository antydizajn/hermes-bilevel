# Changelog

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
