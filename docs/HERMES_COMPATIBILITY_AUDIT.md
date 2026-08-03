# Hermes Compatibility Audit

Date: 2026-08-03

## Environment detected during implementation

| Item | Value |
|------|-------|
| OS | macOS (Darwin) 15.7.3 |
| `hermes version` | Hermes Agent v0.19.0 (2026.7.20) |
| Git revision | `477c08b44766ace8b890faa72bf82ecbcf2b3ba8` |
| Install method | git (`~/.hermes/hermes-agent`) |
| Hermes Python | 3.11.15 (reported by hermes version) |
| Local `python3` | 3.13.7 (system); dev target 3.11+ |
| Plugin system docs | `hermes_cli/plugins.py`, `docs/observability/README.md` |

## Plugin discovery modes (confirmed)

1. Bundled: `<repo>/plugins/<name>/`
2. User: `~/.hermes/plugins/<name>/` (via `HERMES_HOME`)
3. Project: `./.hermes/plugins/<name>/` (opt-in `HERMES_ENABLE_PROJECT_PLUGINS`)
4. Pip entry points: group `hermes_agent.plugins`

Directory plugins require `plugin.yaml` + `__init__.py` with `register(ctx)`.

## Entry-point format (confirmed)

```toml
[project.entry-points."hermes_agent.plugins"]
bilevel = "hermes_bilevel.plugin:register"
```

Loader resolves a **callable** `register` (function), not merely a module.

## PluginContext public surfaces used

| API | Confirmed | Usage in bilevel |
|-----|-----------|------------------|
| `register_hook(name, cb)` | yes | observe hooks |
| `register_cli_command(name, help, setup_fn, handler_fn=...)` | yes | `hermes bilevel` |
| `register_command(name, handler, ...)` | yes | `/bilevel` slash |
| `register_skill(name, path, description)` | yes | `bilevel:bilevel-lab` |
| `register_tool(...)` | yes, unused by default | read-only tools disabled |
| `ctx.llm` | yes | not called in v0.1 observe path |
| `ctx.profile_name` | yes | attribution |
| `inject_message` | exists | **not used** |

## Hooks registered (subset of VALID_HOOKS)

- on_session_start, on_session_end, on_session_finalize, on_session_reset
- pre_llm_call, post_llm_call
- pre_tool_call, post_tool_call
- subagent_start, subagent_stop

### Hook return contracts respected

- `pre_llm_call` returns `None` in observe mode (no context injection)
- `pre_tool_call` returns `None` (no block)
- All callbacks accept `**kwargs` and swallow exceptions at boundary

## Skill registration

`ctx.register_skill(name, path)` exposes skill as `<plugin_name>:<name>`
→ `bilevel:bilevel-lab`.

## CLI registration

`ctx.register_cli_command(name="bilevel", setup_fn=..., handler_fn=...)`
yields `hermes bilevel ...`. Remainder-args pattern used for deep subcommands.

## Home / profile resolution

Uses `HERMES_HOME` when present; else `~/.hermes`.
State: `$HERMES_HOME/bilevel/` or `HERMES_BILEVEL_ROOT`.

## Known risks / workarounds

1. Discovery ≠ enablement — operator must enable plugin.
2. Hermes update (`git reset --hard`) does not remove pip-installed plugins but may change hook kwargs; handlers tolerate missing keys.
3. Exact provider-boundary capture is **not** available via public hooks → fidelity labeled HOOK_METADATA.
4. Network isolation cannot be claimed on tempdir sandbox → `UNKNOWN`.
5. Do not access private `_manager` / `_cli_ref`.

## Interface gaps (no Hermes core patches made)

- No public stable “install plugin from path” beyond user dir / pip / git install.
- No public wire-level recorder API in Hermes core consumed here.
- Live promotion into active skills is intentionally not implemented.
