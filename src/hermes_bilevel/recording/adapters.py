"""Recorder adapters with explicit fidelity labels."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from hermes_bilevel.protocols import (
    ProviderRecord,
    RecorderCapabilities,
    RecorderSource,
    VerificationResult,
)


class HooksOnlyRecorderAdapter:
    def probe(self) -> RecorderCapabilities:
        return RecorderCapabilities(
            fidelity="HOOK_METADATA",
            supports_stream=False,
            supports_retries=False,
            supports_fallbacks=False,
            exact_provider_boundary=False,
        )

    def iter_records(self, source: RecorderSource) -> Iterable[ProviderRecord]:
        # Hooks-only has no external file source; empty by design.
        return []

    def verify_record(self, record: ProviderRecord) -> VerificationResult:
        if record.fidelity != "HOOK_METADATA":
            return VerificationResult(False, "hooks-only adapter rejects non-hook fidelity")
        return VerificationResult(True, "ok")


class JsonlRecorderAdapter:
    def probe(self) -> RecorderCapabilities:
        return RecorderCapabilities(
            fidelity="LOGICAL_REQUEST",
            supports_stream=True,
            supports_retries=True,
            supports_fallbacks=True,
            exact_provider_boundary=False,
        )

    def iter_records(self, source: RecorderSource) -> Iterator[ProviderRecord]:
        if not source.path:
            return iter(())
        path = Path(source.path)
        if not path.exists():
            return iter(())

        def _gen() -> Iterator[ProviderRecord]:
            with path.open("r", encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    yield ProviderRecord(
                        record_id=str(obj.get("record_id") or f"{path.name}:{i}"),
                        fidelity=str(obj.get("fidelity") or "LOGICAL_REQUEST"),
                        created_at=str(obj.get("created_at") or ""),
                        model=obj.get("model"),
                        provider=obj.get("provider"),
                        session_id=obj.get("session_id"),
                        turn_id=obj.get("turn_id"),
                        request_hash=obj.get("request_hash"),
                        response_hash=obj.get("response_hash"),
                        payload=obj.get("payload"),
                        attempt_index=int(obj.get("attempt_index") or 0),
                        is_fallback=bool(obj.get("is_fallback")),
                        is_stream=bool(obj.get("is_stream")),
                    )

        return _gen()

    def verify_record(self, record: ProviderRecord) -> VerificationResult:
        if not record.record_id:
            return VerificationResult(False, "missing record_id")
        return VerificationResult(True, "ok")


class DirectoryRecorderAdapter:
    def probe(self) -> RecorderCapabilities:
        return RecorderCapabilities(
            fidelity="PROVIDER_ATTEMPT",
            supports_stream=True,
            supports_retries=True,
            supports_fallbacks=True,
            exact_provider_boundary=False,
        )

    def iter_records(self, source: RecorderSource) -> Iterator[ProviderRecord]:
        if not source.path:
            return iter(())
        root = Path(source.path)
        if not root.exists():
            return iter(())
        jsonl = JsonlRecorderAdapter()

        def _gen() -> Iterator[ProviderRecord]:
            for p in sorted(root.rglob("*.jsonl")):
                yield from jsonl.iter_records(
                    RecorderSource(source_id=source.source_id, kind="jsonl", path=str(p))
                )

        return _gen()

    def verify_record(self, record: ProviderRecord) -> VerificationResult:
        return JsonlRecorderAdapter().verify_record(record)
