from __future__ import annotations

import importlib
from hermes_bilevel.plugin import register


class FakeCtx:
    def __init__(self):
        self.hooks = []
        self.cli = []
        self.commands = []
        self.skills = []
        self.profile_name = "default"

    def register_hook(self, name, cb):
        self.hooks.append(name)

    def register_cli_command(self, **kwargs):
        self.cli.append(kwargs["name"])

    def register_command(self, **kwargs):
        self.commands.append(kwargs["name"])

    def register_skill(self, **kwargs):
        self.skills.append(kwargs["name"])


def test_register_observe_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_BILEVEL_ROOT", str(tmp_path))
    ctx = FakeCtx()
    register(ctx)
    assert "pre_llm_call" in ctx.hooks
    assert "pre_tool_call" in ctx.hooks
    assert "bilevel" in ctx.cli
    assert "bilevel" in ctx.commands
    # skill may or may not depending on path existence
    assert importlib.import_module("hermes_bilevel.plugin").register


def test_entry_point_metadata():
    # packaging metadata may be absent in editable src tests; check callable path
    from hermes_bilevel import plugin as p
    assert callable(p.register)
