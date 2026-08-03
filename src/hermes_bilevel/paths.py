"""Resolve state directories without hard-coding ~/.hermes."""

from __future__ import annotations

import os
from pathlib import Path


def get_hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    # Official Hermes default
    return (Path.home() / ".hermes").resolve()


def get_bilevel_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("HERMES_BILEVEL_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return get_hermes_home() / "bilevel"


def ensure_layout(root: Path) -> dict[str, Path]:
    sub = {
        "root": root,
        "blobs": root / "blobs",
        "manifests": root / "manifests",
        "experiments": root / "experiments",
        "reports": root / "reports",
        "worktrees": root / "worktrees",
        "approvals": root / "approvals",
        "backups": root / "backups",
        "exports": root / "exports",
        "logs": root / "logs",
        "candidates": root / "candidates",
        "datasets": root / "datasets",
    }
    for p in sub.values():
        p.mkdir(parents=True, exist_ok=True)
    return sub
