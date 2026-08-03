from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hermes_bilevel.config.schema import load_config
from hermes_bilevel.events.queue import BoundedEventQueue
from hermes_bilevel.hooks.handlers import HookHandlers


def _collector_queue(maxsize: int = 100) -> tuple[BoundedEventQueue, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []

    def writer(ev: Mapping[str, Any]) -> None:
        events.append(dict(ev))

    q = BoundedEventQueue(maxsize=maxsize, writer=writer, start_worker=True)
    return q, events


def test_pre_hooks_return_none_and_do_not_mutate_args():
    cfg = load_config()
    q = BoundedEventQueue(maxsize=100, start_worker=False)
    h = HookHandlers(cfg, q)
    args = {"path": "x"}
    assert h.pre_llm_call(session_id="s", user_message="hi", model="m") is None
    assert h.pre_tool_call(session_id="s", tool_name="read_file", args=args) is None
    assert args == {"path": "x"}
    assert q.qsize() >= 2


def test_queue_drop_newest():
    q = BoundedEventQueue(maxsize=1, overflow_policy="drop_newest", start_worker=False)
    assert q.put({"event_id": "1", "event_type": "a"}) is True
    assert q.put({"event_id": "2", "event_type": "b"}) is False
    assert q.dropped == 1


def test_session_lifecycle_handlers_emit_observe_only():
    cfg = load_config()
    q, events = _collector_queue()
    h = HookHandlers(cfg, q)

    assert h.on_session_start(session_id="s", platform="cli", model="m") is None
    assert h.on_session_end(session_id="s", telemetry_schema_version="1") is None
    assert h.on_session_finalize(session_id="s", telemetry_schema_version="1") is None
    assert h.on_session_reset(session_id="s", telemetry_schema_version="1") is None
    q.flush(timeout=2.0)

    types = sorted(e["event_type"] for e in events)
    assert types == [
        "on_session_end",
        "on_session_finalize",
        "on_session_reset",
        "on_session_start",
    ]
    # lifecycle events carry key names, never raw payloads
    end = next(e for e in events if e["event_type"] == "on_session_end")
    assert end["payload"]["keys"] == ["session_id", "telemetry_schema_version"]


def test_subagent_handlers_emit_observe_only():
    cfg = load_config()
    q, events = _collector_queue()
    h = HookHandlers(cfg, q)

    assert h.subagent_start(session_id="s", task_id="t1", role="leaf", depth=1) is None
    assert h.subagent_stop(session_id="s", task_id="t1", duration_ms=120) is None
    q.flush(timeout=2.0)

    types = sorted(e["event_type"] for e in events)
    assert types == ["subagent_start", "subagent_stop"]
    stop = next(e for e in events if e["event_type"] == "subagent_stop")
    assert stop["payload"]["duration"] == 120


def test_post_llm_and_tool_emit_metadata_only():
    cfg = load_config()
    q, events = _collector_queue()
    h = HookHandlers(cfg, q)

    h.post_llm_call(session_id="s", turn_id="t", response="secret-content", model="m")
    h.post_tool_call(
        session_id="s",
        turn_id="t",
        tool_name="read_file",
        args={"path": "secret-path"},
        result={"data": "secret-body"},
    )
    q.flush(timeout=2.0)

    joined = repr([e["payload"] for e in events]).lower()
    # content mode metadata_only: no raw response bodies in payload
    assert "secret-content" not in joined
    assert "secret-body" not in joined
