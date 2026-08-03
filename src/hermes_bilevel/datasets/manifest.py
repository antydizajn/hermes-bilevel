"""Immutable dataset manifests with split isolation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.ids import SortableIdGenerator, SystemClock

_ids = SortableIdGenerator()
_clock = SystemClock()

VALID_SPLITS = ("inner_train", "outer_selection", "final_locked_heldout")


@dataclass
class DatasetManifest:
    manifest_id: str
    schema_version: str
    created_at: str
    name: str
    split: str
    items: list[dict[str, Any]]
    locked: bool
    manifest_hash: str
    parent_hash: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_manifest(
    name: str,
    split: str,
    items: Sequence[Mapping[str, Any]],
    *,
    locked: bool = False,
    notes: str = "",
) -> DatasetManifest:
    if split not in VALID_SPLITS:
        raise ValueError(f"invalid split {split!r}; expected one of {VALID_SPLITS}")
    norm_items = []
    for it in items:
        item = dict(it)
        if "task_id" not in item:
            raise ValueError("each item requires task_id")
        if "content_hash" not in item:
            item["content_hash"] = hash_canonical(item)
        norm_items.append(item)
    body = {
        "name": name,
        "split": split,
        "items": norm_items,
        "notes": notes,
    }
    mh = hash_canonical(body)
    return DatasetManifest(
        manifest_id=_ids.new_id("ds"),
        schema_version="1.0.0",
        created_at=_clock.now_rfc3339(),
        name=name,
        split=split,
        items=norm_items,
        locked=locked,
        manifest_hash=mh,
        notes=notes,
    )


def lock_manifest(m: DatasetManifest) -> DatasetManifest:
    if m.locked:
        return m
    body = {
        "name": m.name,
        "split": m.split,
        "items": m.items,
        "notes": m.notes,
    }
    return DatasetManifest(
        manifest_id=m.manifest_id,
        schema_version=m.schema_version,
        created_at=m.created_at,
        name=m.name,
        split=m.split,
        items=list(m.items),
        locked=True,
        manifest_hash=hash_canonical(body),
        parent_hash=m.manifest_hash,
        notes=m.notes,
    )


def verify_manifest(m: DatasetManifest | Mapping[str, Any]) -> tuple[bool, str]:
    data = m.to_dict() if isinstance(m, DatasetManifest) else dict(m)
    body = {
        "name": data["name"],
        "split": data["split"],
        "items": data["items"],
        "notes": data.get("notes", ""),
    }
    expected = hash_canonical(body)
    if expected != data.get("manifest_hash"):
        return False, "manifest_hash mismatch"
    if data.get("split") not in VALID_SPLITS:
        return False, "invalid split"
    return True, "ok"
