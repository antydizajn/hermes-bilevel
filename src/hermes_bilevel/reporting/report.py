"""JSON + Markdown reports."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from hermes_bilevel.canonical import hash_canonical
from hermes_bilevel.ids import SortableIdGenerator, SystemClock
from hermes_bilevel.optimization.pareto import nondominated_sort

_ids = SortableIdGenerator()
_clock = SystemClock()


def build_comparison_report(
    *,
    baseline: Mapping[str, Any] | None,
    results: Sequence[Mapping[str, Any]],
    dataset_hashes: Mapping[str, str],
    recording_fidelity: str = "HOOK_METADATA",
    exact_provider_boundary_verified: bool = False,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    frontier = nondominated_sort(results)
    body = {
        "report_id": _ids.new_id("rep"),
        "schema_version": "1.0.0",
        "created_at": _clock.now_rfc3339(),
        "experiment_id": experiment_id or _ids.new_id("exp"),
        "baseline": baseline,
        "results": list(results),
        "pareto_frontier": frontier,
        "dataset_hashes": dict(dataset_hashes),
        "recording_fidelity": recording_fidelity,
        "exact_provider_boundary_verified": exact_provider_boundary_verified,
        "reproducibility_status": (
            "deterministic_offline"
            if not exact_provider_boundary_verified
            else "provider_boundary_verified"
        ),
        "excluded_runs": [],
        "unresolved_unknowns": (
            []
            if exact_provider_boundary_verified
            else ["exact provider payload not verified from hooks-only telemetry"]
        ),
    }
    body["report_hash"] = hash_canonical(body)
    return body


def render_markdown_report(report: Mapping[str, Any]) -> str:
    rid = report.get("report_id")
    lines = [
        f"# Bilevel comparison report `{rid}`",
        "",
        f"- created_at: `{report.get('created_at')}`",
        f"- experiment_id: `{report.get('experiment_id')}`",
        f"- recording_fidelity: `{report.get('recording_fidelity')}`",
        f"- exact_provider_boundary_verified: `{report.get('exact_provider_boundary_verified')}`",
        f"- reproducibility_status: `{report.get('reproducibility_status')}`",
        "",
        "## Dataset hashes",
    ]
    for k, v in (report.get("dataset_hashes") or {}).items():
        lines.append(f"- **{k}**: `{v}`")
    lines += ["", "## Results", ""]
    for r in report.get("results") or []:
        m = r.get("metrics") or {}
        ch = str(r.get("candidate_hash", ""))[:18]
        lines.append(
            f"- candidate `{ch}...` label={r.get('label')} "
            f"success={m.get('task_success_rate')} cost={m.get('estimated_cost_usd')}"
        )
    lines += ["", "## Pareto frontier", ""]
    for r in report.get("pareto_frontier") or []:
        ch = str(r.get("candidate_hash", ""))[:18]
        lines.append(f"- `{ch}...`")
    if report.get("unresolved_unknowns"):
        lines += ["", "## Unresolved unknowns", ""]
        for u in report["unresolved_unknowns"]:
            lines.append(f"- {u}")
    lines.append("")
    return "\n".join(lines)
