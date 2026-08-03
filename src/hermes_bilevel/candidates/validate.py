"""Candidate validation pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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

PATH_SCOPES = {
    "skill": ("skills/",),
    "executive_policy": ("policies/executive/",),
    "workflow_policy": ("policies/workflow/",),
    "retrieval_policy": ("policies/retrieval/",),
    "memory_policy": ("policies/memory/",),
    "tool_routing_policy": ("policies/tool_routing/",),
    "budget_policy": ("policies/budget/",),
    "reflection_policy": ("policies/reflection/",),
    "stopping_policy": ("policies/stopping/",),
}


class CandidateValidationError(ValueError):
    def __init__(self, reason: str, code: str = "reject") -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


def _normalize_path(path: str) -> str:
    p = path.strip().replace("\\", "/")
    return p


def parse_diff_paths(patch: str) -> list[str]:
    """Parse all paths modified in the unified diff headers."""
    paths = set()
    for line in patch.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            parts = line[4:].split()
            if not parts:
                continue
            path = parts[0]
            for prefix in ("a/", "b/", "i/", "w/", "o/", "c/"):
                if path.startswith(prefix):
                    path = path[len(prefix):]
                    break
            if path != "/dev/null":
                paths.add(path)
        elif line.startswith("diff --git "):
            parts = line[11:].split()
            if len(parts) >= 2:
                p1, p2 = parts[0], parts[1]
                for prefix in ("a/", "b/"):
                    if p1.startswith(prefix):
                        p1 = p1[len(prefix):]
                    if p2.startswith(prefix):
                        p2 = p2[len(prefix):]
                if p1 != "/dev/null":
                    paths.add(p1)
                if p2 != "/dev/null":
                    paths.add(p2)
        elif line.startswith("rename from ") or line.startswith("copy from "):
            parts = line.split(" ", 2)
            if len(parts) > 2:
                paths.add(parts[2].strip())
        elif line.startswith("rename to ") or line.startswith("copy to "):
            parts = line.split(" ", 2)
            if len(parts) > 2:
                paths.add(parts[2].strip())
    return sorted(list(paths))


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
        raise CandidateValidationError(
            f"experimental surface disabled in v0.1: {target}", "experimental"
        )
    if target not in ALLOWED_SURFACES:
        raise CandidateValidationError(f"target_type not allowed: {target}", "allowlist")

    hypothesis = str(raw["hypothesis"]).strip()
    if len(hypothesis) < 8:
        raise CandidateValidationError("hypothesis too short / not falsifiable", "hypothesis")

    # Validate target_path field if present
    path = _normalize_path(str(raw.get("target_path") or ""))
    if path:
        if path.startswith(("/", "~")) or path.startswith("../") or "/../" in path or ".." in path.split("/"):
            raise CandidateValidationError("path traversal or absolute path", "path")
        for pref in FORBIDDEN_PATH_PREFIXES:
            if path.startswith(pref):
                raise CandidateValidationError(f"forbidden path prefix: {pref}", "path")
        if path.endswith("approval.json") or "heldout" in path.lower():
            raise CandidateValidationError("candidate cannot touch approvals/heldout", "path")
        
        allowed_prefixes = PATH_SCOPES.get(target)
        if allowed_prefixes:
            if not any(path.startswith(pref) for pref in allowed_prefixes):
                raise CandidateValidationError(
                    f"target_type is {target} but path is outside allowed scopes {allowed_prefixes}: {path}",
                    "path"
                )

    patch = str(raw.get("patch") or "")
    if len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
        raise CandidateValidationError("patch too large", "patch_size")
    if "\0" in patch:
        raise CandidateValidationError("binary patch not supported", "binary")

    # Parse and validate paths in diff headers
    diff_paths = parse_diff_paths(patch)
    if not diff_paths:
        raise CandidateValidationError("patch is not a valid unified diff (no modified files parsed)", "patch")

    for p in diff_paths:
        p_norm = _normalize_path(p)
        if p_norm.startswith(("/", "~")) or p_norm.startswith("../") or "/../" in p_norm or ".." in p_norm.split("/"):
            raise CandidateValidationError(f"path traversal or absolute path in diff: {p}", "path")
        for pref in FORBIDDEN_PATH_PREFIXES:
            if p_norm.startswith(pref):
                raise CandidateValidationError(f"forbidden path prefix in diff: {pref} in {p}", "path")
        if p_norm.endswith("approval.json") or "heldout" in p_norm.lower():
            raise CandidateValidationError("candidate diff cannot touch approvals/heldout", "path")
        
        allowed_prefixes = PATH_SCOPES.get(target)
        if allowed_prefixes:
            if not any(p_norm.startswith(pref) for pref in allowed_prefixes):
                raise CandidateValidationError(
                    f"target_type is {target} but diff modifies file outside allowed scopes {allowed_prefixes}: {p}",
                    "path"
                )

    # secret scan on patch
    rr = redact_text(patch)
    if rr.substitutions:
        raise CandidateValidationError("secrets detected in patch", "secret")

    # Strict parent_hash checking: if parent_hash is expected, it must match candidate parent_hash exactly
    if parent_hash is not None:
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
