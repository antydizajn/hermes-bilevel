"""SQLite + content-addressed blob storage."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hermes_bilevel.canonical import sha256_bytes
from hermes_bilevel.ids import SortableIdGenerator, SystemClock
from hermes_bilevel.paths import ensure_layout, get_bilevel_root
from hermes_bilevel.version import SCHEMA_VERSION, __version__

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class BlobStore:
    def __init__(self, root: Path, max_blob_bytes: int = 10_485_760) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_blob_bytes = max_blob_bytes

    def put_bytes(self, data: bytes, meta: Mapping[str, Any] | None = None) -> str:
        if len(data) > self.max_blob_bytes:
            raise ValueError(f"blob exceeds max_blob_bytes={self.max_blob_bytes}")
        digest = sha256_bytes(data)
        hexd = digest.split(":", 1)[1]
        path = self.root / hexd[:2] / hexd
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        if not path.exists():
            tmp.write_bytes(data)
            os.replace(tmp, path)
        return digest

    def get_bytes(self, digest: str) -> bytes:
        hexd = digest.split(":", 1)[-1]
        path = self.root / hexd[:2] / hexd
        return path.read_bytes()

    def exists(self, digest: str) -> bool:
        hexd = digest.split(":", 1)[-1]
        return (self.root / hexd[:2] / hexd).exists()


class BilevelStore:
    def __init__(
        self,
        root: Path | None = None,
        *,
        busy_timeout_ms: int = 2500,
        wal: bool = True,
        max_blob_bytes: int = 10_485_760,
    ) -> None:
        self.root = root or get_bilevel_root()
        self.paths = ensure_layout(self.root)
        self.db_path = self.root / "state.db"
        self.blobs = BlobStore(self.paths["blobs"], max_blob_bytes=max_blob_bytes)
        self.clock = SystemClock()
        self.ids = SortableIdGenerator()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        self._conn.execute("PRAGMA foreign_keys=ON")
        if wal:
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(schema)
            cur = self._conn.execute("SELECT COUNT(*) AS c FROM schema_versions")
            if cur.fetchone()["c"] == 0:
                self._conn.execute(
                    "INSERT INTO schema_versions(version, applied_at, description) VALUES (?,?,?)",
                    (1, self.clock.now_rfc3339(), "initial"),
                )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def integrity_check(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("PRAGMA integrity_check").fetchone()
            jm = self._conn.execute("PRAGMA journal_mode").fetchone()[0]
        return {"integrity": row[0], "journal_mode": jm, "db_path": str(self.db_path)}

    def insert_event(self, event: Mapping[str, Any]) -> None:
        payload = event.get("payload") or {}
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        redaction_json = json.dumps(
            event.get("redaction_summary") or {}, ensure_ascii=False, sort_keys=True
        )
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO events(
                  event_id, event_type, schema_version, created_at, monotonic_ns,
                  session_id, turn_id, task_id, tool_call_id, source, payload_hash,
                  payload_json, redaction_json, correlation_quality, lossy,
                  plugin_version, hermes_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event["event_id"],
                    event["event_type"],
                    event.get("schema_version", SCHEMA_VERSION),
                    event["created_at"],
                    event.get("monotonic_ns"),
                    event.get("session_id"),
                    event.get("turn_id"),
                    event.get("task_id"),
                    event.get("tool_call_id"),
                    event.get("source", "hermes_hook"),
                    event.get("payload_hash", ""),
                    payload_json,
                    redaction_json,
                    event.get("correlation_quality", "unmatched"),
                    1 if event.get("lossy") else 0,
                    event.get("plugin_version", __version__),
                    event.get("hermes_version"),
                ),
            )

    def record_loss(
        self, reason: str, details: Mapping[str, Any] | None = None, count: int = 1
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO event_losses(created_at, reason, count, details_json) VALUES (?,?,?,?)",
                (
                    self.clock.now_rfc3339(),
                    reason,
                    count,
                    json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
                ),
            )

    def loss_count(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(count),0) AS c FROM event_losses"
            ).fetchone()
        return int(row["c"])

    def upsert_session(self, session_id: str, **meta: Any) -> None:
        with self._lock:
            existing = self._conn.execute(
                "SELECT session_id FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if existing:
                return
            self._conn.execute(
                "INSERT INTO sessions(session_id, created_at, platform, model, profile_name, status, meta_json) VALUES (?,?,?,?,?,?,?)",
                (
                    session_id,
                    self.clock.now_rfc3339(),
                    meta.get("platform"),
                    meta.get("model"),
                    meta.get("profile_name"),
                    meta.get("status", "open"),
                    json.dumps(
                        {
                            k: v
                            for k, v in meta.items()
                            if k not in {"platform", "model", "profile_name", "status"}
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )

    def insert_audit(
        self, actor: str, command: str, args: Mapping[str, Any], result: str, **kw: Any
    ) -> str:
        audit_id = self.ids.new_id("aud")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO audit_events(audit_id, created_at, actor, command, args_json, config_hash, result, side_effects_json, approval_ref)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    audit_id,
                    self.clock.now_rfc3339(),
                    actor,
                    command,
                    json.dumps(dict(args), ensure_ascii=False, sort_keys=True),
                    kw.get("config_hash"),
                    result,
                    json.dumps(kw.get("side_effects") or [], ensure_ascii=False),
                    kw.get("approval_ref"),
                ),
            )
        return audit_id

    def save_json_artifact(
        self, kind: str, body: Mapping[str, Any], digest: str | None = None
    ) -> str:
        artifact_id = self.ids.new_id("art")
        raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        d = digest or self.blobs.put_bytes(raw)
        from hermes_bilevel.canonical import hash_canonical

        ch = hash_canonical(body)
        with self._lock:
            self._conn.execute(
                "INSERT INTO artifacts(artifact_id, kind, created_at, digest, meta_json, canonical_hash) VALUES (?,?,?,?,?,?)",
                (artifact_id, kind, self.clock.now_rfc3339(), d, "{}", ch),
            )
        return artifact_id

    def put_candidate(self, body: Mapping[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO candidates(candidate_id, created_at, candidate_hash, parent_hash, target_type, status, body_json)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    body["candidate_id"],
                    body.get("created_at") or self.clock.now_rfc3339(),
                    body["candidate_hash"],
                    body.get("parent_hash"),
                    body["target_type"],
                    body.get("status", "validated"),
                    json.dumps(dict(body), ensure_ascii=False, sort_keys=True),
                ),
            )

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT body_json FROM candidates WHERE candidate_id=?", (candidate_id,)
            ).fetchone()
        if not row:
            return None
        res = json.loads(row["body_json"])
        if isinstance(res, dict):
            return res
        return None

    def put_dataset_manifest(self, body: Mapping[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO dataset_manifests(manifest_id, created_at, name, split, locked, manifest_hash, body_json)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    body["manifest_id"],
                    body.get("created_at") or self.clock.now_rfc3339(),
                    body.get("name", body["manifest_id"]),
                    body.get("split", "inner_train"),
                    1 if body.get("locked") else 0,
                    body["manifest_hash"],
                    json.dumps(dict(body), ensure_ascii=False, sort_keys=True),
                ),
            )

    def put_evaluation_result(self, body: Mapping[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_results(result_id, created_at, candidate_hash, dataset_hash, metrics_json, label, body_json)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    body["result_id"],
                    body.get("created_at") or self.clock.now_rfc3339(),
                    body["candidate_hash"],
                    body.get("dataset_hash"),
                    json.dumps(body.get("metrics") or {}, ensure_ascii=False, sort_keys=True),
                    body.get("label"),
                    json.dumps(dict(body), ensure_ascii=False, sort_keys=True),
                ),
            )

    def put_purity_registry(
        self, registry_hash: str, version: str, body: Mapping[str, Any]
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO purity_registry_versions(registry_hash, created_at, version, body_json) VALUES (?,?,?,?)",
                (
                    registry_hash,
                    self.clock.now_rfc3339(),
                    version,
                    json.dumps(dict(body), ensure_ascii=False, sort_keys=True),
                ),
            )

    def count_events(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"])

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT event_id, event_type, created_at, session_id, payload_hash, lossy FROM events ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    _DUMP_TABLES: tuple[str, ...] = (
        "schema_versions",
        "plugin_runs",
        "sessions",
        "turns",
        "blobs",
        "artifacts",
        "events",
        "event_losses",
        "audit_events",
        "dataset_manifests",
        "candidates",
        "evaluation_results",
        "purity_registry_versions",
        "correlations",
    )

    def dump_state(self) -> dict[str, Any]:
        """Full portable dump of every table, ordered for safe restore."""
        tables: dict[str, list[dict[str, Any]]] = {}
        with self._lock:
            for table in self._DUMP_TABLES:
                cur = self._conn.execute(f'SELECT * FROM "{table}"')
                tables[table] = [dict(r) for r in cur.fetchall()]
        return {
            "format": "hermes_bilevel_state",
            "format_version": 1,
            "schema_version": SCHEMA_VERSION,
            "exported_at": self.clock.now_rfc3339(),
            "tables": tables,
        }

    def restore_state(self, dump: Mapping[str, Any]) -> dict[str, Any]:
        """Restore a previously exported dump.

        Idempotent: INSERT OR REPLACE on every table in dependency order.
        Validates the dump shape before touching anything.
        """
        if dump.get("format") != "hermes_bilevel_state":
            raise ValueError(f"not a bilevel state dump: {dump.get('format')!r}")
        if dump.get("format_version") != 1:
            raise ValueError(f"unsupported dump format_version: {dump.get('format_version')!r}")
        tables = dump.get("tables")
        if not isinstance(tables, dict):
            raise ValueError("dump has no tables mapping")
        unknown = set(tables) - set(self._DUMP_TABLES)
        if unknown:
            raise ValueError(f"dump contains unknown tables: {sorted(unknown)}")
        inserted = 0
        with self._lock:
            for table in self._DUMP_TABLES:
                rows = tables.get(table)
                if not rows:
                    continue
                cols = [k for k in rows[0].keys()]
                placeholders = ", ".join("?" for _ in cols)
                colsql = ", ".join(f'"{c}"' for c in cols)
                for row in rows:
                    values = [row.get(c) for c in cols]
                    self._conn.execute(
                        f'INSERT OR REPLACE INTO "{table}" ({colsql}) VALUES ({placeholders})',
                        values,
                    )
                inserted += len(rows)
        return {"ok": True, "tables": len(tables), "rows": inserted}

    def gc(self, *, vacuum: bool = True) -> dict[str, Any]:
        """Housekeeping: integrity check + optional VACUUM.

        VACUUM rewrites the DB file; it cannot run inside a transaction.
        The lock is dropped for the VACUUM call itself and re-acquired after.
        """
        integrity = self.integrity_check()
        out: dict[str, Any] = {"integrity": integrity["integrity"], "vacuum": False}
        if vacuum and integrity["integrity"] == "ok":
            with self._lock:
                self._conn.execute("VACUUM")
            out["vacuum"] = True
            out["db_path"] = str(self.db_path)
        return out
