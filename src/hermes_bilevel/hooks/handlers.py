"""Observe-only hook handlers. Never mutate live behavior."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Any

from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.config.schema import BilevelConfig
from hermes_bilevel.events.envelope import make_event
from hermes_bilevel.events.queue import BoundedEventQueue
from hermes_bilevel.purity.registry import PurityRegistry
from hermes_bilevel.redaction.redactor import redact_text

logger = logging.getLogger(__name__)


def _shape(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return {str(k): type(v).__name__ for k, v in list(obj.items())[:50]}
    if isinstance(obj, (list, tuple)):
        return {
            "__list_len__": len(obj),
            "__item_types__": sorted({type(x).__name__ for x in obj[:20]}),
        }
    return type(obj).__name__


def _hash_obj(obj: Any) -> str | None:
    if obj is None:
        return None
    try:
        if isinstance(obj, str):
            return "sha256:" + hashlib.sha256(obj.encode("utf-8")).hexdigest()
        return hash_canonical(obj)
    except Exception:
        return None


class HookHandlers:
    def __init__(
        self,
        cfg: BilevelConfig,
        queue: BoundedEventQueue,
        hermes_version: str | None = None,
        profile_name: str | None = None,
        purity: PurityRegistry | None = None,
    ) -> None:
        self.cfg = cfg
        self.queue = queue
        self.hermes_version = hermes_version
        self.profile_name = profile_name
        self.purity = purity

    def _emit(self, event_type: str, payload: dict[str, Any], **ids: Any) -> None:
        if not self.cfg.get("hooks", "enabled", default=True):
            return
        try:
            ev = make_event(
                event_type,
                payload,
                hermes_version=self.hermes_version,
                profile_name=self.profile_name,
                **ids,
            )
            self.queue.put(ev)
        except Exception as exc:  # plugin boundary
            logger.debug("bilevel emit failed: %s", type(exc).__name__)

    def on_session_start(self, **kwargs: Any) -> None:
        self._emit(
            "on_session_start",
            {
                "keys": sorted(str(k) for k in kwargs.keys()),
                "model": kwargs.get("model"),
                "platform": kwargs.get("platform"),
                "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            },
            session_id=kwargs.get("session_id") or kwargs.get("task_id"),
            platform=kwargs.get("platform"),
        )

    def pre_llm_call(self, **kwargs: Any) -> None:
        # OBSERVE MODE: always return None (no context injection)
        user_message = kwargs.get("user_message")
        history = kwargs.get("conversation_history")
        payload = {
            "model": kwargs.get("model"),
            "platform": kwargs.get("platform"),
            "first_turn": kwargs.get("is_first_turn"),
            "user_message_hash": _hash_obj(user_message) if user_message is not None else None,
            "history_shape": _shape(history),
            "callback_schema": "pre_llm_call@observe",
            "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            "api_request_id": kwargs.get("api_request_id"),
            "api_call_count": kwargs.get("api_call_count"),
        }
        if self.cfg.content_mode != "metadata_only" and isinstance(user_message, str):
            rr = redact_text(
                user_message,
                max_bytes=int(self.cfg.get("recording", "max_text_bytes", default=65536)),
            )
            if not rr.rejected and self.cfg.content_mode in {"redacted_content", "full_content"}:
                payload["user_message_redacted"] = (
                    rr.text if self.cfg.get("redaction", "enabled", default=True) else user_message
                )
                payload["redaction"] = {
                    "substitutions": rr.substitutions,
                    "rules": rr.rules_fired,
                    "original_length": rr.original_length,
                }
        self._emit(
            "pre_llm_call",
            payload,
            session_id=kwargs.get("session_id"),
            turn_id=kwargs.get("turn_id"),
            task_id=kwargs.get("task_id"),
            platform=kwargs.get("platform"),
            provider_request_id=kwargs.get("api_request_id"),
        )
        return None

    def post_llm_call(self, **kwargs: Any) -> None:
        response = None
        for key in ("response", "text", "content"):
            if key in kwargs:
                response = kwargs[key]
                break

        status = kwargs.get("status") if "status" in kwargs else kwargs.get("completion_status")

        payload = {
            "model": kwargs.get("model"),
            "platform": kwargs.get("platform"),
            "response_hash": _hash_obj(response),
            "response_length": len(response) if isinstance(response, str) else None,
            "status": status,
            "history_shape": _shape(kwargs.get("conversation_history")),
            "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            "api_request_id": kwargs.get("api_request_id"),
            "api_call_count": kwargs.get("api_call_count"),
        }
        self._emit(
            "post_llm_call",
            payload,
            session_id=kwargs.get("session_id"),
            turn_id=kwargs.get("turn_id"),
            task_id=kwargs.get("task_id"),
            platform=kwargs.get("platform"),
            provider_request_id=kwargs.get("api_request_id"),
        )

    def pre_tool_call(self, **kwargs: Any) -> None:
        # OBSERVE MODE: always return None (never block)
        args = kwargs.get("args")
        tool_name = kwargs.get("tool_name") or kwargs.get("name")
        purity_info = {}
        if self.purity is not None and tool_name:
            classification = self.purity.classify(tool_name)
            purity_info = {
                "purity_class": classification.classification.value,
                "rule_id": classification.rule_id,
                "replay_allowed": classification.replay_allowed,
                "reasoning": classification.reasoning,
                "replay_requirements": list(classification.replay_requirements),
                "registry_version": self.purity.version,
                "registry_hash": self.purity.registry_hash,
            }
        payload = {
            "tool_name": tool_name,
            "args_hash": _hash_obj(args),
            "args_shape": _shape(args),
            "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            "api_request_id": kwargs.get("api_request_id"),
            "api_call_count": kwargs.get("api_call_count"),
            "purity": purity_info,
        }
        self._emit(
            "pre_tool_call",
            payload,
            session_id=kwargs.get("session_id"),
            turn_id=kwargs.get("turn_id"),
            task_id=kwargs.get("task_id"),
            tool_call_id=kwargs.get("tool_call_id"),
            provider_request_id=kwargs.get("api_request_id"),
        )
        return None

    def post_tool_call(self, **kwargs: Any) -> None:
        result = kwargs.get("result") if "result" in kwargs else kwargs.get("tool_result")
        args = kwargs.get("args")
        tool_name = kwargs.get("tool_name") or kwargs.get("name")
        duration_ms = kwargs.get("duration_ms") if "duration_ms" in kwargs else kwargs.get("duration")
        purity_info = {}
        if self.purity is not None and tool_name:
            classification = self.purity.classify(tool_name)
            purity_info = {
                "purity_class": classification.classification.value,
                "rule_id": classification.rule_id,
                "replay_allowed": classification.replay_allowed,
                "reasoning": classification.reasoning,
                "replay_requirements": list(classification.replay_requirements),
                "registry_version": self.purity.version,
                "registry_hash": self.purity.registry_hash,
            }
        payload = {
            "tool_name": tool_name,
            "args_hash": _hash_obj(args),
            "result_hash": _hash_obj(result),
            "result_length": len(result) if isinstance(result, str) else None,
            "result_type": type(result).__name__ if result is not None else None,
            "duration_ms": duration_ms,
            "error": bool(kwargs.get("error")),
            "timeout": bool(kwargs.get("timeout")),
            "truncated": bool(kwargs.get("truncated")),
            "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            "api_request_id": kwargs.get("api_request_id"),
            "api_call_count": kwargs.get("api_call_count"),
            "purity": purity_info,
        }
        self._emit(
            "post_tool_call",
            payload,
            session_id=kwargs.get("session_id"),
            turn_id=kwargs.get("turn_id"),
            task_id=kwargs.get("task_id"),
            tool_call_id=kwargs.get("tool_call_id"),
            provider_request_id=kwargs.get("api_request_id"),
        )

    def on_session_end(self, **kwargs: Any) -> None:
        self._emit(
            "on_session_end",
            {
                "keys": sorted(str(k) for k in kwargs.keys()),
                "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            },
            session_id=kwargs.get("session_id"),
        )
        try:
            self.queue.flush(timeout=0.5)
        except Exception:
            pass

    def on_session_finalize(self, **kwargs: Any) -> None:
        self._emit(
            "on_session_finalize",
            {
                "keys": sorted(str(k) for k in kwargs.keys()),
                "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            },
            session_id=kwargs.get("session_id"),
        )
        try:
            self.queue.flush(timeout=0.5)
        except Exception:
            pass

    def on_session_reset(self, **kwargs: Any) -> None:
        self._emit(
            "on_session_reset",
            {
                "keys": sorted(str(k) for k in kwargs.keys()),
                "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            },
            session_id=kwargs.get("session_id"),
        )

    def subagent_start(self, **kwargs: Any) -> None:
        self._emit(
            "subagent_start",
            {
                "parent_session": kwargs.get("parent_session_id") or kwargs.get("parent_session"),
                "role": kwargs.get("role"),
                "depth": kwargs.get("depth"),
                "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            },
            session_id=kwargs.get("session_id"),
            task_id=kwargs.get("task_id"),
        )

    def subagent_stop(self, **kwargs: Any) -> None:
        duration = kwargs.get("duration") if "duration" in kwargs else kwargs.get("duration_ms")
        self._emit(
            "subagent_stop",
            {
                "status": kwargs.get("status"),
                "duration": duration,
                "role": kwargs.get("role"),
                "telemetry_schema_version": kwargs.get("telemetry_schema_version"),
            },
            session_id=kwargs.get("session_id"),
            task_id=kwargs.get("task_id"),
        )
