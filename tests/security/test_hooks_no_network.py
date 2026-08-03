from __future__ import annotations

import socket

from hermes_bilevel.config.schema import load_config
from hermes_bilevel.events.queue import BoundedEventQueue
from hermes_bilevel.hooks.handlers import HookHandlers


def test_hooks_do_not_open_sockets(monkeypatch):
    def blocked(*a, **k):
        raise AssertionError("socket used")

    monkeypatch.setattr(socket, "socket", blocked)
    cfg = load_config()
    q = BoundedEventQueue(maxsize=10, start_worker=False)
    h = HookHandlers(cfg, q)
    h.pre_llm_call(session_id="s", user_message="x")
    h.pre_tool_call(session_id="s", tool_name="terminal", args={"command": "echo hi"})
    h.post_tool_call(session_id="s", tool_name="terminal", result="hi")
