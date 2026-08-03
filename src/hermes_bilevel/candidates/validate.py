"""Candidate validation pipeline."""
from __future__ import annotations

import re
from typing import Any, Mapping

from hermes_bilevel.candidates.surfaces import (
    ALLOWED_SURFACES,
    EXPERIMENTAL_DISABLED,
    FORBIDDEN_PATH_PREFIXES,
    FORBIDDEN_SURFACES,
)
from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.ids import SortableIdGenerator, SystemClock
from hermes_bilevel.redaction.redactor import redact_text

_ids = SortableIdGenerator()
_clock = SystemClock()

MAX_PATCH_BYTES = 200_000


class CandidateValidationError(ValueError):
    def __init__(self, reason: str, code: str = "reject") -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


def _normalize_path(path: str) -> str:
    p = path.strip().replace("\\", "/")
    return p


def validate_candidate(raw: Mapping[str, Any], *, parent_hash: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CandidateValidationError("candidate must be a mapping", "schema")

    required = ["target_type", "hypothesis", "patch"]
    for k in required:
        if not raw.get(k):
            raise CandidateValidationError(f"missing field: {k}", "schema")

    target = str(raw["target_type"])
    if target in FORBIDDEN_SURFACES:
        raise CandidateValidationError(f"forbidden target_type: {target}", "forbidden_surface")
    if target in EXPERIMENTAL_DISABLED:
        raise CandidateValidationError(f"experimental surface disabled in v0.1: {target}", "experimental")
    if target not in ALLOWED_SURFACES:
        raise CandidateValidationError(f"target_type not allowed: {target}", "allowlist")

    hypothesis = str(raw["hypothesis"]).strip()
    if len(hypothesis) < 8:
        raise CandidateValidationError("hypothesis too short / not falsifiable", "hypothesis")

    path = _normalize_path(str(raw.get("target_path") or ""))
    if path:
        if path.startswith(("/", "~")) or path.startswith("../") or "/../" in path:
            raise CandidateValidationError("path traversal or absolute path", "path")
        for pref in FORBIDDEN_PATH_PREFIXES:
            if path.startswith(pref):
                raise CandidateValidationError(f"forbidden path prefix: {pref}", "path")
        if path.endswith("approval.json") or "heldout" in path.lower():
            raise CandidateValidationError("candidate cannot touch approvals/heldout", "path")

    patch = str(raw.get("patch") or "")
    if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise CandidateValidationError("patch too large", "patch_size")
    if "\0" in patch:
        raise CandidateValidationError("binary patch not supported", "binary")

    # secret scan on patch
    rr = redact_text(patch)
    if rr.substitutions:
        raise CandidateValidationError("secrets detected in patch", "secret")

    if parent_hash is not None and raw.get("parent_hash") not in {None, parent_hash}:
        # if provided parent_hash expected, must match
        if raw.get("parent_hash") != parent_hash:
            raise CandidateValidationError("parent_hash mismatch", "parent")

    body = {
        "schema_version": str(raw.get("schema_version") or "1.0.0"),
        "target_type": target,
        "target_path": path,
        "hypothesis": hypothesis,
        "mechanism": str(raw.get("mechanism") or ""),
        "evidence_used": list(raw.get("evidence_used") or []),
        "failure_modes_addressed": list(raw.get("failure_modes_addressed") or []),
        "expected_metric_changes": dict(raw.get("expected_metric_changes") or {}),
        "possible_regressions": list(raw.get("possible_regressions") or []),
        "safety_analysis": list(raw.get("safety_analysis") or []),
        "patch_format": str(raw.get("patch_format") or "unified_diff"),
        "patch": patch,
        "rollback_plan": str(raw.get("rollback_plan") or "restore parent artifact"),
        "proposer_backend": str(raw.get("proposer_backend") or "manual"),
        "proposer_provider": raw.get("proposer_provider"),
        "proposer_model": raw.get("proposer_model"),
        "proposer_prompt_hash": raw.get("proposer_prompt_hash"),
        "dataset_manifest_hash": raw.get("dataset_manifest_hash"),
        "evaluator_contract_hash": raw.get("evaluator_contract_hash"),
        "purity_registry_hash": raw.get("purity_registry_hash"),
        "configuration_hash": raw.get("configuration_hash"),
        "parent_hash": raw.get("parent_hash"),
    }
    ch = hash_canonical(body)
    out = {
        "candidate_id": str(raw.get("candidate_id") or _ids.new_id("cand")),
        "created_at": str(raw.get("created_at") or _clock.now_rfc3339()),
        "candidate_hash": ch,
        "status": "validated",
        **body,
    }
    return out
