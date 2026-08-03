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


def test_canonical_path_and_date_datetime():
    import datetime as dt
    from pathlib import Path

    # 1. Path
    assert canonicalize(Path("foo/bar")) == {"__path__": "foo/bar"}

    # 2. Datetime naive
    d_naive = dt.datetime(2026, 8, 3, 12, 0, 0)
    assert canonicalize(d_naive) == "2026-08-03T12:00:00Z"

    # 3. Datetime aware
    d_aware = dt.datetime(2026, 8, 3, 12, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
    assert canonicalize(d_aware) == "2026-08-03T10:00:00Z"

    # 4. Date
    assert canonicalize(dt.date(2026, 8, 3)) == "2026-08-03"


def test_canonical_enum_and_dataclass():
    import enum
    from dataclasses import dataclass

    class MyEnum(enum.Enum):
        A = "val_a"

    assert canonicalize(MyEnum.A) == "val_a"

    @dataclass
    class MyDataclass:
        x: int
        y: str

    obj = MyDataclass(1, "hello")
    assert canonicalize(obj) == {"x": 1, "y": "hello"}


def test_canonical_key_coercion_and_custom_obj():
    # 1. Non-string mapping keys
    assert canonicalize({123: "val"}) == {"123": "val"}

    # 2. Custom class with __dict__
    class Custom:
        def __init__(self):
            self.x = 42
            self._private = "hidden"

    assert canonicalize(Custom()) == {"x": 42}

    # 3. Unsupported types (e.g. complex number)
    r = canonicalize(complex(1, 2))
    assert r["__unsupported__"] == "complex"
    assert "(1+2j)" in r["__repr__"]


def test_canonical_limits(monkeypatch):
    # 1. Max depth exceeded
    deep = []
    for _ in range(40):
        deep = [deep]
    with pytest.raises(CanonicalizationError, match="max depth"):
        canonicalize(deep)

    # 2. Max items exceeded
    wide = list(range(10001))
    with pytest.raises(CanonicalizationError, match="max items"):
        canonicalize(wide)

    # 3. Max bytes exceeded
    import hermes_bilevel.canonical as canon_mod
    monkeypatch.setattr(canon_mod, "_MAX_BYTES", 10)
    with pytest.raises(CanonicalizationError, match="canonical form exceeds"):
        dumps_canonical({"a": "very long value exceeding ten bytes"})

    # 4. sha256_text
    from hermes_bilevel.canonical import sha256_text
    assert sha256_text("hello").startswith("sha256:")

