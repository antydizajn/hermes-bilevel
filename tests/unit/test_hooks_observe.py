from __future__ import annotations

from hermes_bilevel.config.schema import load_config
from hermes_bilevel.events.queue import BoundedEventQueue
from hermes_bilevel.hooks.handlers import HookHandlers


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
