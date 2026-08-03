"""Hermes plugin entrypoint.

Public registration:

    def register(ctx) -> None: ...

Entry point:
    [project.entry-points."hermes_agent.plugins"]
    bilevel = "hermes_bilevel.plugin:register"

Safety: observe-only by default. Hooks never inject context, never block tools,
never call models, never touch the network.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from hermes_bilevel.compatibility import SUPPORTED_HOOKS, summarize_context_capabilities
from hermes_bilevel.config.schema import load_config
from hermes_bilevel.runtime import get_runtime
from hermes_bilevel.version import __version__

logger = logging.getLogger(__name__)

_REGISTERED = False


def _safe_hook(fn):  # type: ignore[no-untyped-def]
    def wrapper(**kwargs: Any) -> Any:
        try:
            return fn(**kwargs)
        except Exception as exc:  # never break host agent
            logger.debug("bilevel hook %s failed: %s", getattr(fn, "__name__", "?"), type(exc).__name__)
            return None

    wrapper.__name__ = getattr(fn, "__name__", "bilevel_hook")
    return wrapper


def register(ctx: Any) -> None:
    """Register bilevel plugin surfaces with Hermes."""
    global _REGISTERED
    # Idempotent-ish: avoid duplicate hook spam on repeated discovery in tests.
    # Hermes itself may still call register once per process.
    cfg = load_config()
    # Fail closed on unsafe default activation
    try:
        if cfg.mode == "observe":
            cfg.assert_observe_safe()
    except Exception as exc:
        logger.error("bilevel refused to register: %s", exc)
        return

    caps = summarize_context_capabilities(ctx)
    logger.info("bilevel %s registering; caps=%s", __version__, caps)

    runtime = get_runtime(cfg)
    h = runtime.handlers
    if hasattr(ctx, "profile_name"):
        try:
            h.profile_name = ctx.profile_name  # type: ignore[assignment]
        except Exception:
            pass

    if caps.get("register_hook"):
        mapping = {
            "on_session_start": h.on_session_start,
            "pre_llm_call": h.pre_llm_call,
            "post_llm_call": h.post_llm_call,
            "pre_tool_call": h.pre_tool_call,
            "post_tool_call": h.post_tool_call,
            "on_session_end": h.on_session_end,
            "on_session_finalize": h.on_session_finalize,
            "on_session_reset": h.on_session_reset,
            "subagent_start": h.subagent_start,
            "subagent_stop": h.subagent_stop,
        }
        for name in SUPPORTED_HOOKS:
            ctx.register_hook(name, _safe_hook(mapping[name]))

    if caps.get("register_cli_command"):
        from hermes_bilevel.cli import hermes_bilevel_command, setup_hermes_cli

        ctx.register_cli_command(
            name="bilevel",
            help="Auditable bilevel optimization laboratory (observe-only by default)",
            setup_fn=setup_hermes_cli,
            handler_fn=hermes_bilevel_command,
            description=(
                "Bilevel lab for Hermes: telemetry, datasets, candidates, offline evaluation. "
                "Defaults are fail-closed. See: hermes bilevel doctor"
            ),
        )

    if caps.get("register_command"):
        def _slash(raw_args: str) -> str:
            raw = (raw_args or "").strip()
            parts = raw.split()
            sub = parts[0] if parts else "status"
            if sub in {"status", "doctor", "latest"}:
                from hermes_bilevel.cli import main
                import io
                from contextlib import redirect_stdout

                buf = io.StringIO()
                argv = ["doctor", "--json"] if sub == "doctor" else ["status", "--json"]
                if sub == "latest":
                    argv = ["status", "--json"]
                with redirect_stdout(buf):
                    code = main(argv)
                return buf.getvalue() or json_fallback(code)
            if sub == "explain" and len(parts) > 1:
                return f"Candidate explain is read-only. Use: hermes bilevel candidate inspect {parts[1]}"
            return (
                "bilevel slash (read-only): /bilevel status|doctor|latest|explain <id>\n"
                "Mutation/promotion/model calls are disabled from slash commands."
            )

        def json_fallback(code: int) -> str:
            return f'{{"ok": {str(code == 0).lower()}}}'

        ctx.register_command(
            name="bilevel",
            handler=_slash,
            description="Read-only bilevel status/doctor/latest/explain",
            args_hint="status|doctor|latest|explain <id>",
        )

    if caps.get("register_skill"):
        skill_path = Path(__file__).resolve().parent / "skills" / "bilevel-lab" / "SKILL.md"
        if skill_path.exists():
            try:
                ctx.register_skill(
                    name="bilevel-lab",
                    path=skill_path,
                    description="Operate the hermes-bilevel laboratory safely (observe-first).",
                )
            except Exception as exc:
                logger.debug("skill registration failed: %s", exc)

    # Read-only tools intentionally disabled by default (no register_tool).
    _REGISTERED = True
    logger.info("bilevel plugin register() completed")
