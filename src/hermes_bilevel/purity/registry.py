"""Versioned tool purity registry."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from hermes_bilevel.canonical import hash_canonical


class PurityClass(StrEnum):
    PURE = "PURE"
    READ_ONLY = "READ_ONLY"
    MUTATING_LOCAL = "MUTATING_LOCAL"
    MUTATING_REMOTE = "MUTATING_REMOTE"
    SUBAGENT = "SUBAGENT"
    UNKNOWN = "UNKNOWN"


DEFAULT_TOOLS: dict[str, dict[str, str]] = {
    # conservative defaults for common Hermes tools
    "read_file": {"class": "READ_ONLY", "rule": "filesystem_read"},
    "search_files": {"class": "READ_ONLY", "rule": "filesystem_read"},
    "web_search": {"class": "READ_ONLY", "rule": "network_read"},
    "web_extract": {"class": "READ_ONLY", "rule": "network_read"},
    "terminal": {"class": "MUTATING_LOCAL", "rule": "shell_general"},
    "write_file": {"class": "MUTATING_LOCAL", "rule": "filesystem_write"},
    "patch": {"class": "MUTATING_LOCAL", "rule": "filesystem_write"},
    "skill_manage": {"class": "MUTATING_LOCAL", "rule": "skill_mutation"},
    "memory": {"class": "MUTATING_LOCAL", "rule": "memory_write"},
    "send_message": {"class": "MUTATING_REMOTE", "rule": "external_message"},
    "cronjob": {"class": "MUTATING_LOCAL", "rule": "scheduler"},
    "delegate_task": {"class": "SUBAGENT", "rule": "subagent"},
    "execute_code": {"class": "MUTATING_LOCAL", "rule": "code_exec"},
    "image_generate": {"class": "MUTATING_REMOTE", "rule": "external_api"},
    "text_to_speech": {"class": "MUTATING_REMOTE", "rule": "external_api"},
}


@dataclass(frozen=True)
class PurityDecision:
    tool_name: str
    classification: PurityClass
    registry_version: str
    registry_hash: str
    rule_id: str
    reasoning: str
    replay_allowed: bool
    replay_requirements: tuple[str, ...]


class PurityRegistry:
    def __init__(
        self,
        tools: Mapping[str, Mapping[str, str]],
        version: str = "1.0.0",
        unknown_policy: str = "deny",
    ) -> None:
        self.version = version
        self.unknown_policy = unknown_policy
        self.tools = {k: dict(v) for k, v in tools.items()}
        self.registry_hash = hash_canonical(
            {"version": version, "tools": self.tools, "unknown_policy": unknown_policy}
        )

    def classify(self, tool_name: str) -> PurityDecision:
        entry = self.tools.get(tool_name)
        if not entry:
            cls = PurityClass.UNKNOWN
            rule = "unknown_default"
            reasoning = "tool not present in registry"
        else:
            cls = PurityClass(entry.get("class", "UNKNOWN"))
            rule = entry.get("rule", "listed")
            reasoning = entry.get("reasoning", f"registry entry for {tool_name}")

        replay_allowed = False
        req: list[str] = []
        if cls is PurityClass.PURE:
            replay_allowed = True
        elif cls is PurityClass.READ_ONLY:
            replay_allowed = True
            req.append("verified_isolated_environment")
        elif cls is PurityClass.MUTATING_LOCAL:
            replay_allowed = True
            req.append("disposable_sandbox_or_worktree")
        elif cls is PurityClass.MUTATING_REMOTE:
            replay_allowed = False
            req.append("never_automatic_replay")
        elif cls is PurityClass.SUBAGENT:
            replay_allowed = False
            req.append("evaluate_as_new_inner_episode")
        else:
            replay_allowed = False
            req.append("deny_unknown")
            if self.unknown_policy != "deny":
                # still deny automatic replay; unknown_policy only affects messaging
                pass

        return PurityDecision(
            tool_name=tool_name,
            classification=cls,
            registry_version=self.version,
            registry_hash=self.registry_hash,
            rule_id=rule,
            reasoning=reasoning,
            replay_allowed=replay_allowed
            and cls not in {PurityClass.MUTATING_REMOTE, PurityClass.UNKNOWN, PurityClass.SUBAGENT},
            replay_requirements=tuple(req),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "unknown_policy": self.unknown_policy,
            "tools": self.tools,
            "registry_hash": self.registry_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PurityRegistry:
        return cls(
            tools=data.get("tools") or {},
            version=str(data.get("version", "1.0.0")),
            unknown_policy=str(data.get("unknown_policy", "deny")),
        )


def load_default_registry(
    path: str | Path | None = None, unknown_policy: str = "deny"
) -> PurityRegistry:
    if path:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if unknown_policy:
            data["unknown_policy"] = unknown_policy
        return PurityRegistry.from_dict(data)
    return PurityRegistry(DEFAULT_TOOLS, version="1.0.0", unknown_policy=unknown_policy)
