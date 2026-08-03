"""Typed configuration with fail-closed defaults."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermes_bilevel.canonical import hash_canonical

DEFAULTS: dict[str, Any] = {
    "schema_version": 1,
    "mode": "observe",
    "behavior": {
        "inject_context": False,
        "block_live_tools": False,
        "override_tools": False,
        "inject_messages": False,
        "alter_prompts": False,
        "alter_model_routing": False,
    },
    "storage": {
        "root": None,
        "sqlite_wal": True,
        "busy_timeout_ms": 2500,
        "blob_threshold_bytes": 65536,
        "max_blob_bytes": 10485760,
    },
    "hooks": {
        "enabled": True,
        "queue_size": 2048,
        "overflow_policy": "drop_newest",
        "max_callback_ms": 10,
    },
    "recording": {
        "content_mode": "metadata_only",
        "max_text_bytes": 65536,
        "store_raw_prompts": False,
        "store_raw_responses": False,
        "store_raw_tool_results": False,
        "exact_provider_required_for_replay": True,
    },
    "redaction": {
        "enabled": True,
        "custom_patterns": [],
    },
    "purity": {
        "registry_path": None,
        "unknown_policy": "deny",
    },
    "model_calls": {
        "enabled": False,
        "allow_paid_calls": False,
        "require_cli_confirmation": True,
        "allow_fallback": False,
        "max_calls_per_run": 0,
        "max_tokens_per_run": 0,
        "max_estimated_cost_usd": 0.0,
    },
    "proposer": {
        "backend": "manual",
        "model_policy": "active",
        "temperature": None,
        "candidate_count": 4,
    },
    "optimization": {
        "enabled": False,
        "live_inner_runs": False,
        "shadow_candidates": False,
        "code_candidates": False,
        "max_generations": 0,
        "population_size": 0,
        "paired_seeds": [],
    },
    "sandbox": {
        "backend": "subprocess",
        "network": False,
        "timeout_seconds": 300,
        "max_processes": 4,
        "workspace_mode": "disposable",
        "env_allowlist": [],
    },
    "evaluation": {
        "model_judge_enabled": False,
        "require_deterministic_validator": True,
        "minimum_episodes": 3,
        "confidence_level": 0.95,
    },
    "promotion": {
        "enabled": False,
        "automatic": False,
        "active_candidate": None,
        "approval_file_required": True,
        "backup_required": True,
    },
    "telemetry": {
        "external_export": False,
    },
    "network": {
        "outbound_enabled": False,
    },
    "wire": False,
}


class ConfigError(ValueError):
    pass


def _deep_merge(
    base: MutableMapping[str, Any], override: Mapping[str, Any]
) -> MutableMapping[str, Any]:
    for k, v in override.items():
        if isinstance(v, Mapping) and isinstance(base.get(k), Mapping):
            _deep_merge(base[k], v)  # type: ignore[arg-type]
        else:
            base[k] = copy.deepcopy(v)
    return base


def _as_bool(v: Any, path: str) -> bool:
    if isinstance(v, bool):
        return v
    raise ConfigError(f"{path} must be bool, got {type(v).__name__}")


@dataclass
class BilevelConfig:
    data: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULTS))

    @property
    def mode(self) -> str:
        return str(self.data.get("mode", "observe"))

    @property
    def wire(self) -> bool:
        return bool(self.data.get("wire", False))

    @property
    def content_mode(self) -> str:
        return str(self.data.get("recording", {}).get("content_mode", "metadata_only"))

    def get(self, *keys: str, default: Any = None) -> Any:
        cur: Any = self.data
        for k in keys:
            if not isinstance(cur, Mapping) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def hash(self) -> str:
        return hash_canonical(self.data)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)

    def assert_observe_safe(self) -> None:
        """Raise if config would mutate live agent behavior."""
        b = self.data.get("behavior") or {}
        for key in (
            "inject_context",
            "block_live_tools",
            "override_tools",
            "inject_messages",
            "alter_prompts",
            "alter_model_routing",
        ):
            if b.get(key):
                raise ConfigError(
                    f"behavior.{key}=true is not allowed in observe-default plugin activation"
                )
        if self.data.get("wire"):
            raise ConfigError(
                "wire=true requires explicit dual activation and is blocked for default observe mode"
            )


def validate_config(raw: Mapping[str, Any] | None) -> BilevelConfig:
    data = copy.deepcopy(DEFAULTS)
    if raw:
        if not isinstance(raw, Mapping):
            raise ConfigError("config must be a mapping")
        _deep_merge(data, raw)

    mode = data.get("mode", "observe")
    if mode not in {"observe", "prepare", "propose", "sandbox", "shadow", "canary"}:
        raise ConfigError(f"invalid mode: {mode!r}")

    cm = data.get("recording", {}).get("content_mode", "metadata_only")
    if cm not in {"metadata_only", "redacted_content", "full_content"}:
        raise ConfigError(f"invalid recording.content_mode: {cm!r}")

    # Fail closed: presence of env-like strings must not auto-enable paid paths.
    mc = data.get("model_calls") or {}
    if mc.get("enabled") and not isinstance(mc.get("enabled"), bool):
        raise ConfigError("model_calls.enabled must be bool")
    if mc.get("enabled") is True:
        # still require explicit CLI gate at runtime
        pass
    else:
        # force disabled budgets
        mc["enabled"] = False

    if data.get("promotion", {}).get("automatic") is True:
        raise ConfigError("promotion.automatic=true is NOT_IMPLEMENTED_BY_DESIGN")

    if (
        data.get("optimization", {}).get("code_candidates") is True
        and data.get("mode") == "observe"
    ):
        raise ConfigError("code_candidates cannot be enabled in observe mode")

    overflow = data.get("hooks", {}).get("overflow_policy", "drop_newest")
    if overflow not in {"drop_newest", "drop_oldest", "block"}:
        raise ConfigError(f"invalid hooks.overflow_policy: {overflow!r}")

    cfg = BilevelConfig(data=data)
    return cfg


def load_config(
    path: str | Path | None = None, overrides: Mapping[str, Any] | None = None
) -> BilevelConfig:
    raw: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            if p.suffix.lower() in {".yaml", ".yml"}:
                try:
                    import yaml  # type: ignore
                except ImportError as e:  # pragma: no cover
                    raise ConfigError("PyYAML required to load YAML config") from e
                loaded = yaml.safe_load(text) or {}
            else:
                loaded = json.loads(text)
            if not isinstance(loaded, Mapping):
                raise ConfigError("config root must be a mapping")
            raw = dict(loaded)
    if overrides:
        _deep_merge(raw, overrides)
    return validate_config(raw)
