from __future__ import annotations

from hermes_bilevel.storage.store import BilevelStore


def test_event_roundtrip(tmp_path):
    store = BilevelStore(tmp_path)
    store.insert_event(
        {
            "event_id": "evt_1",
            "event_type": "test",
            "created_at": "2026-08-03T00:00:00Z",
            "source": "test",
            "payload_hash": "sha256:x",
            "payload": {"a": 1},
        }
    )
    assert store.count_events() == 1
    assert store.integrity_check()["integrity"] == "ok"
    # blob
    d = store.blobs.put_bytes(b"hello")
    assert store.blobs.exists(d)
    assert store.blobs.get_bytes(d) == b"hello"
    store.close()
