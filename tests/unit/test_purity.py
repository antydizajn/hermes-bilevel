from __future__ import annotations

from hermes_bilevel.purity.registry import load_default_registry


def test_unknown_denied():
    reg = load_default_registry()
    d = reg.classify("nope_tool")
    assert d.classification.value == "UNKNOWN"
    assert d.replay_allowed is False


def test_remote_denied():
    reg = load_default_registry()
    d = reg.classify("send_message")
    assert d.classification.value == "MUTATING_REMOTE"
    assert d.replay_allowed is False


def test_hash_stable():
    a = load_default_registry()
    b = load_default_registry()
    assert a.registry_hash == b.registry_hash
