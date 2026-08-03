"""Promotion dossier builder (reporting only in v0.1)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.ids import SortableIdGenerator, SystemClock
from hermes_bilevel.version import __version__

_ids = SortableIdGenerator()
_clock = SystemClock()


def build_promotion_dossier(
    candidate: Mapping[str, Any],
    *,
    baseline_hash: str | None,
    dataset_hashes: Mapping[str, str],
    evaluation_results: Sequence[Mapping[str, Any]],
    purity_registry_hash: str | None,
    evaluator_contract_hash: str | None,
    hermes_version: str | None = None,
    code_revision: str | None = None,
    unresolved_risks: Sequence[str] | None = None,
) -> dict[str, Any]:
    body = {
        "dossier_id": _ids.new_id("dos"),
        "schema_version": "1.0.0",
        "created_at": _clock.now_rfc3339(),
        "candidate_id": candidate.get("candidate_id"),
        "candidate_hash": candidate.get("candidate_hash"),
        "parent_hash": candidate.get("parent_hash"),
        "exact_diff": candidate.get("patch"),
        "baseline_hash": baseline_hash,
        "dataset_hashes": dict(dataset_hashes),
        "evaluator_contract_hash": evaluator_contract_hash,
        "purity_registry_hash": purity_registry_hash,
        "code_revision": code_revision,
        "hermes_version": hermes_version,
        "plugin_version": __version__,
        "proposer_provider": candidate.get("proposer_provider"),
        "proposer_model": candidate.get("proposer_model"),
        "evaluation_results": list(evaluation_results),
        "unresolved_risks": list(
            unresolved_risks or ["v0.1 promotion is dossier-only; no live activation"]
        ),
        "rollback_plan": candidate.get("rollback_plan"),
        "human_decision_field": None,
        "promotion_status": "dossier_only",
        "recording_fidelity_note": "Do not claim exact provider boundary from hooks-only data.",
    }
    body["dossier_hash"] = hash_canonical(body)
    return body
