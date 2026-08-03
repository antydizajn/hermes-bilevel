"""Stable ID generation without external deps.

Uses time-sortable identifiers: prefix + hex(ms) + random hex.
Not UUIDv7, but documented, sortable, and dependency-free.
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime


class SystemClock:
    def now_rfc3339(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()


class SortableIdGenerator:
    def new_id(self, prefix: str = "") -> str:
        ms = int(time.time() * 1000)
        rand = secrets.token_hex(6)
        body = f"{ms:013x}{rand}"
        if prefix:
            return f"{prefix}_{body}"
        return body


def content_address(data: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(data).hexdigest()
