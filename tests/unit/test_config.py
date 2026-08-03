from __future__ import annotations

import pytest
from hermes_bilevel.config.schema import ConfigError, load_config, validate_config


def test_defaults_observe_safe():
    cfg = load_config()
    assert cfg.mode == "observe"
    assert cfg.wire is False
    assert cfg.get("model_calls", "enabled") is False
    assert cfg.get("promotion", "automatic") is False
    cfg.assert_observe_safe()


def test_automatic_promotion_rejected():
    with pytest.raises(ConfigError):
        validate_config({"promotion": {"automatic": True}})


def test_env_presence_does_not_enable_model_calls(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = load_config()
    assert cfg.get("model_calls", "enabled") is False
