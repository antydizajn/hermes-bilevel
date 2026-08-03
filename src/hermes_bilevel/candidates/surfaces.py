"""Allowed and forbidden candidate surfaces."""

from __future__ import annotations

ALLOWED_SURFACES = frozenset(
    {
        "skill",
        "executive_policy",
        "workflow_policy",
        "retrieval_policy",
        "memory_policy",
        "tool_routing_policy",
        "budget_policy",
        "reflection_policy",
        "stopping_policy",
    }
)

EXPERIMENTAL_DISABLED = frozenset({"python_code_patch", "tool_implementation", "plugin_code"})

FORBIDDEN_SURFACES = frozenset(
    {
        "hermes_core",
        "provider_transport",
        "authentication",
        "provider_recorder",
        "purity_registry",
        "redaction_rules",
        "evaluator_source",
        "dataset_manifests",
        "heldout_datasets",
        "approval_verification",
        "promotion_rules",
        "rollback_implementation",
        "security_gates",
        "audit_log",
    }
)

FORBIDDEN_PATH_PREFIXES = (
    "/",
    "~",
    "..",
    "hermes_cli/",
    "agent/",
    ".git/",
    "approvals/",
    "datasets/final_locked_heldout",
)
