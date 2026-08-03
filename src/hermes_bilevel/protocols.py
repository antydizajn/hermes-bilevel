"""Dependency-inversion protocols. No Hermes imports here."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RecorderCapabilities:
    fidelity: str
    supports_stream: bool = False
    supports_retries: bool = False
    supports_fallbacks: bool = False
    exact_provider_boundary: bool = False


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason: str = ""
    details: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ProviderRecord:
    record_id: str
    fidelity: str
    created_at: str
    model: str | None = None
    provider: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    request_hash: str | None = None
    response_hash: str | None = None
    payload: Mapping[str, Any] | None = None
    attempt_index: int = 0
    is_fallback: bool = False
    is_stream: bool = False


@dataclass(frozen=True)
class RecorderSource:
    source_id: str
    kind: str
    path: str | None = None
    metadata: Mapping[str, Any] | None = None


@runtime_checkable
class EventSink(Protocol):
    def emit(self, event: Mapping[str, Any]) -> bool: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class RecorderAdapter(Protocol):
    def probe(self) -> RecorderCapabilities: ...
    def iter_records(self, source: RecorderSource) -> Iterable[ProviderRecord]: ...
    def verify_record(self, record: ProviderRecord) -> VerificationResult: ...


@runtime_checkable
class ProposalBackend(Protocol):
    def propose(
        self,
        evidence: Mapping[str, Any],
        search_space: Mapping[str, Any],
        count: int,
        budget: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]: ...


@runtime_checkable
class EvaluationBackend(Protocol):
    def evaluate(
        self,
        candidate: Mapping[str, Any],
        task: Mapping[str, Any],
        contract: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class SandboxBackend(Protocol):
    def prepare(self, spec: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def run(self, handle: Mapping[str, Any], command: list[str]) -> Mapping[str, Any]: ...
    def collect(self, handle: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def destroy(self, handle: Mapping[str, Any]) -> None: ...


@runtime_checkable
class ArtifactStore(Protocol):
    def put_bytes(self, data: bytes, meta: Mapping[str, Any] | None = None) -> str: ...
    def get_bytes(self, digest: str) -> bytes: ...
    def exists(self, digest: str) -> bool: ...


@runtime_checkable
class ApprovalVerifier(Protocol):
    def verify(self, approval: Mapping[str, Any], candidate_hash: str) -> VerificationResult: ...


@runtime_checkable
class Clock(Protocol):
    def now_rfc3339(self) -> str: ...
    def monotonic_ns(self) -> int: ...


@runtime_checkable
class IdGenerator(Protocol):
    def new_id(self, prefix: str = "") -> str: ...
