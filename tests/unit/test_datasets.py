from __future__ import annotations

from hermes_bilevel.datasets.manifest import build_manifest, lock_manifest, verify_manifest


def test_manifest_lock_verify():
    m = build_manifest("t", "inner_train", [{"task_id": "a", "prompt": "x"}])
    ok, reason = verify_manifest(m)
    assert ok, reason
    locked = lock_manifest(m)
    assert locked.locked is True
    ok2, reason2 = verify_manifest(locked)
    assert ok2, reason2
