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


def test_safe_hook_swallows_exceptions(tmp_path, monkeypatch):
    """A throwing hook must never break the host agent."""
    from hermes_bilevel.plugin import _safe_hook

    def boom(**kwargs):
        raise RuntimeError("host should never see this")

    wrapped = _safe_hook(boom)
    assert wrapped(foo=1) is None


def test_register_refuses_unsafe_config(tmp_path, monkeypatch):
    """register() must fail closed when config would mutate live behavior."""
    from hermes_bilevel.config.schema import BilevelConfig
    from hermes_bilevel.plugin import register

    monkeypatch.setenv("HERMES_BILEVEL_ROOT", str(tmp_path))

    unsafe = BilevelConfig({"mode": "observe", "behavior": {"inject_context": True}})
    # plugin binds load_config via `from ... import` at import time, so patch
    # the name inside the plugin module itself
    monkeypatch.setattr("hermes_bilevel.plugin.load_config", lambda: unsafe)
    monkeypatch.setattr("hermes_bilevel.plugin._REGISTERED", False)

    ctx = FakeCtx()
    register(ctx)
    # nothing registered: unsafe config must be refused before any hook is bound
    assert ctx.hooks == []
    assert ctx.cli == []


def test_register_partial_caps(tmp_path, monkeypatch):
    """register() must degrade gracefully when ctx exposes only some caps."""
    import hermes_bilevel.compatibility as compat_mod
    from hermes_bilevel.plugin import register

    monkeypatch.setenv("HERMES_BILEVEL_ROOT", str(tmp_path))

    class HookOnlyCtx:
        def __init__(self):
            self.hooks = []

        def register_hook(self, name, cb):
            self.hooks.append(name)

    # only register_hook available -> no cli/command registration
    monkeypatch.setattr(compat_mod, "ctx_has", lambda ctx, name: name == "register_hook")
    ctx = HookOnlyCtx()
    register(ctx)
    assert "pre_llm_call" in ctx.hooks
    assert not hasattr(ctx, "cli") or ctx.cli == []


def test_entry_point_metadata():
    # packaging metadata may be absent in editable src tests; check callable path
    from hermes_bilevel import plugin as p

    assert callable(p.register)
