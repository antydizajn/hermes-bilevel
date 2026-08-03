"""Deterministic canonicalization and hashing."""

from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import enum
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_MAX_DEPTH = 32
_MAX_ITEMS = 10_000
_MAX_BYTES = 2_000_000


class CanonicalizationError(ValueError):
    """Raised when a value cannot be safely canonicalized."""


def _reject_float(v: float) -> float:
    if math.isnan(v) or math.isinf(v):
        raise CanonicalizationError("NaN and Infinity are rejected")
    # Normalize -0.0
    if v == 0.0:
        return 0.0
    return v


def canonicalize(
    value: Any,
    *,
    _depth: int = 0,
    _seen: set[int] | None = None,
    _items: list[int] | None = None,
) -> Any:
    """Return a JSON-serializable canonical form.

    Rules:
    - mappings sorted by key (str keys only after coercion)
    - list order preserved
    - sets -> sorted list of canonical items
    - bytes -> {"__bytes_b64__": ...}
    - datetime -> RFC3339 UTC string with Z
    - Path -> posix string marked {"__path__": ...}
    - Enum -> value
    - dataclass/object with __dict__ -> mapping of public fields
    - None preserved
    - absent keys are simply absent (caller responsibility)
    - cycles -> error
    - depth/item/size limits enforced
    """
    if _depth > _MAX_DEPTH:
        raise CanonicalizationError(f"max depth {_MAX_DEPTH} exceeded")
    if _seen is None:
        _seen = set()
    if _items is None:
        _items = [0]
    _items[0] += 1
    if _items[0] > _MAX_ITEMS:
        raise CanonicalizationError(f"max items {_MAX_ITEMS} exceeded")

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return _reject_float(float(value))
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, Path):
        return {"__path__": value.as_posix()}
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return canonicalize(value.value, _depth=_depth + 1, _seen=_seen, _items=_items)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)

    oid = id(value)
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        if oid in _seen:
            raise CanonicalizationError("cycle detected")
        _seen.add(oid)

    try:
        if isinstance(value, Mapping):
            items = []
            for k, v in value.items():
                if not isinstance(k, str):
                    k = str(k)
                items.append((k, canonicalize(v, _depth=_depth + 1, _seen=_seen, _items=_items)))
            items.sort(key=lambda kv: kv[0])
            return {k: v for k, v in items}
        if isinstance(value, (list, tuple)):
            return [canonicalize(v, _depth=_depth + 1, _seen=_seen, _items=_items) for v in value]
        if isinstance(value, (set, frozenset)):
            canon_items = [
                canonicalize(v, _depth=_depth + 1, _seen=_seen, _items=_items) for v in value
            ]
            # sort by canonical JSON for stability
            canon_items.sort(key=lambda x: dumps_canonical(x))
            return {"__set__": canon_items}
        if hasattr(value, "__dict__") and not isinstance(value, type):
            public = {k: v for k, v in vars(value).items() if not k.startswith("_")}
            return canonicalize(public, _depth=_depth + 1, _seen=_seen, _items=_items)
        # unsupported
        return {
            "__unsupported__": type(value).__name__,
            "__repr__": repr(value)[:200],
        }
    finally:
        if isinstance(value, (dict, list, tuple, set, frozenset)) and oid in _seen:
            _seen.discard(oid)


def dumps_canonical(value: Any) -> str:
    canon = canonicalize(value)
    raw = json.dumps(canon, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if len(raw.encode("utf-8")) > _MAX_BYTES:
        raise CanonicalizationError(f"canonical form exceeds {_MAX_BYTES} bytes")
    return raw


def hash_canonical(value: Any) -> str:
    data = dumps_canonical(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))
