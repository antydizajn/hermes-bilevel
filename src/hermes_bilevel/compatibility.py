"""Hermes compatibility helpers — feature detection, no private internals."""

from __future__ import annotations

from typing import Any

SUPPORTED_HOOKS = (
    "on_session_start",
    "pre_llm_call",
    "post_llm_call",
    "pre_tool_call",
    "post_tool_call",
    "on_session_end",
    "on_session_finalize",
    "on_session_reset",
    "subagent_start",
    "subagent_stop",
)

ENTRY_POINT_GROUP = "hermes_agent.plugins"
ENTRY_POINT_NAME = "bilevel"
REGISTER_ATTR = "register"


def detect_hermes_version() -> str | None:
    try:
        import importlib.metadata as md

        return md.version("hermes-agent")
    except Exception:
        return None


def ctx_has(ctx: Any, attr: str) -> bool:
    return hasattr(ctx, attr) and callable(getattr(ctx, attr, None))


def summarize_context_capabilities(ctx: Any) -> dict[str, bool]:
    return {
        "register_hook": ctx_has(ctx, "register_hook"),
        "register_cli_command": ctx_has(ctx, "register_cli_command"),
        "register_command": ctx_has(ctx, "register_command"),
        "register_skill": ctx_has(ctx, "register_skill"),
        "register_tool": ctx_has(ctx, "register_tool"),
        "llm": hasattr(ctx, "llm"),
        "profile_name": hasattr(ctx, "profile_name"),
    }
