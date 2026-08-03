"""Versioned event envelope."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.ids import SortableIdGenerator, SystemClock
from hermes_bilevel.version import SCHEMA_VERSION, __version__

_ids = SortableIdGenerator()
_clock = SystemClock()


@dataclass
class EventEnvelope:
    event_id: str
    event_type: str
    schema_version: str
    created_at: str
    monotonic_ns: int
    session_id: str | None
    turn_id: str | None
    task_id: str | None
    tool_call_id: str | None
    provider_request_id: str | None
    provider_attempt_id: str | None
    parent_event_id: str | None
    source: str
    source_version: str | None
    plugin_version: str
    hermes_version: str | None
    profile_name: str | None
    platform: str | None
    payload: dict[str, Any]
    payload_hash: str
    redaction_summary: dict[str, Any]
    correlation_quality: str
    lossy: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(
    event_type: str,
    payload: Mapping[str, Any],
    *,
    session_id: str | None = None,
    turn_id: str | None = None,
    task_id: str | None = None,
    tool_call_id: str | None = None,
    provider_request_id: str | None = None,
    provider_attempt_id: str | None = None,
    parent_event_id: str | None = None,
    source: str = "hermes_hook",
    source_version: str | None = None,
    hermes_version: str | None = None,
    profile_name: str | None = None,
    platform: str | None = None,
    redaction_summary: Mapping[str, Any] | None = None,
    correlation_quality: str = "unmatched",
    lossy: bool = False,
) -> EventEnvelope:
    pl = dict(payload)
    return EventEnvelope(
        event_id=_ids.new_id("evt"),
        event_type=event_type,
        schema_version=SCHEMA_VERSION,
        created_at=_clock.now_rfc3339(),
        monotonic_ns=_clock.monotonic_ns(),
        session_id=session_id,
        turn_id=turn_id,
        task_id=task_id,
        tool_call_id=tool_call_id,
        provider_request_id=provider_request_id,
        provider_attempt_id=provider_attempt_id,
        parent_event_id=parent_event_id,
        source=source,
        source_version=source_version,
        plugin_version=__version__,
        hermes_version=hermes_version,
        profile_name=profile_name,
        platform=platform,
        payload=pl,
        payload_hash=hash_canonical(pl),
        redaction_summary=dict(redaction_summary or {}),
        correlation_quality=correlation_quality,
        lossy=lossy,
    )
