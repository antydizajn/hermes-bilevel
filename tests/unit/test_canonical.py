from __future__ import annotations

import pytest

from hermes_bilevel.canonical import (
    CanonicalizationError,
    canonicalize,
    dumps_canonical,
    hash_canonical,
)


def test_mapping_order_independent():
    assert hash_canonical({"b": 1, "a": 2}) == hash_canonical({"a": 2, "b": 1})


def test_list_order_sensitive():
    assert hash_canonical([1, 2]) != hash_canonical([2, 1])


def test_rejects_nan_inf():
    with pytest.raises(CanonicalizationError):
        canonicalize(float("nan"))
    with pytest.raises(CanonicalizationError):
        canonicalize(float("inf"))


def test_bytes_and_set():
    c = canonicalize({"data": b"abc", "s": {3, 1, 2}})
    assert c["data"]["__bytes_b64__"]
    assert c["s"]["__set__"] == [1, 2, 3]


def test_cycle_detected():
    a = {}
    a["self"] = a
    with pytest.raises(CanonicalizationError):
        canonicalize(a)


def test_null_vs_absent():
    assert dumps_canonical({"a": None}) != dumps_canonical({})


def test_unicode_stable():
    assert "zażółć" in dumps_canonical({"t": "zażółć gęślą jaźń"})
