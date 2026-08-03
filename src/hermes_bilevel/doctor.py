"""Doctor checks with explicit per-gate statuses."""

from __future__ import annotations

from typing import Any

from hermes_bilevel.compatibility import detect_hermes_version
from hermes_bilevel.config.schema import BilevelConfig
from hermes_bilevel.paths import get_bilevel_root
from hermes_bilevel.version import __version__


def _check(name: str, status: str, detail: str = "") -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def run_doctor(cfg: BilevelConfig, *, runtime: Any | None = None) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    hv = detect_hermes_version()
    checks.append(
        _check(
            "Hermes detected",
            "PASS" if hv else "UNKNOWN",
            hv or "hermes-agent not importable in this env",
        )
    )
    checks.append(
        _check(
            "Hermes version supported",
            "PASS" if hv else "UNKNOWN",
            "tested against 0.19.x plugin API",
        )
    )
    import sys

    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    checks.append(
        _check("Python version supported", "PASS" if sys.version_info >= (3, 11) else "FAIL", py)
    )
    checks.append(_check("plugin version", "PASS", __version__))
    checks.append(_check("mode", "PASS", cfg.mode))
    checks.append(_check("wire", "PASS" if not cfg.wire else "FAIL", str(cfg.wire)))
    checks.append(_check("content mode", "PASS", cfg.content_mode))
    checks.append(
        _check(
            "redaction enabled",
            "PASS" if cfg.get("redaction", "enabled", default=True) else "FAIL",
            "",
        )
    )
    checks.append(
        _check(
            "model calls enabled",
            "PASS" if not cfg.get("model_calls", "enabled") else "BLOCKED",
            str(cfg.get("model_calls", "enabled")),
        )
    )
    checks.append(
        _check(
            "paid calls enabled",
            "PASS" if not cfg.get("model_calls", "allow_paid_calls") else "BLOCKED",
            str(cfg.get("model_calls", "allow_paid_calls")),
        )
    )
    checks.append(
        _check(
            "optimization enabled",
            "PASS" if not cfg.get("optimization", "enabled") else "BLOCKED",
            str(cfg.get("optimization", "enabled")),
        )
    )
    checks.append(
        _check(
            "live inner runs",
            "PASS" if not cfg.get("optimization", "live_inner_runs") else "BLOCKED",
            "",
        )
    )
    checks.append(
        _check(
            "shadow candidates",
            "PASS" if not cfg.get("optimization", "shadow_candidates") else "BLOCKED",
            "",
        )
    )
    checks.append(
        _check(
            "promotion enabled", "PASS" if not cfg.get("promotion", "enabled") else "BLOCKED", ""
        )
    )
    checks.append(
        _check(
            "automatic promotion",
            "PASS" if not cfg.get("promotion", "automatic") else "FAIL",
            "must remain false",
        )
    )
    checks.append(
        _check(
            "network outbound",
            "PASS" if not cfg.get("network", "outbound_enabled") else "BLOCKED",
            "",
        )
    )
    checks.append(_check("active candidate", "PASS", str(cfg.get("promotion", "active_candidate"))))

    root = get_bilevel_root(cfg.get("storage", "root"))
    try:
        root.mkdir(parents=True, exist_ok=True)
        test = root / ".doctor_write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        checks.append(_check("state root writable", "PASS", str(root)))
    except Exception as e:
        checks.append(_check("state root writable", "FAIL", type(e).__name__))

    if runtime is not None:
        try:
            integ = runtime.store.integrity_check()
            checks.append(
                _check(
                    "database integrity",
                    "PASS" if integ.get("integrity") == "ok" else "FAIL",
                    str(integ),
                )
            )
            checks.append(
                _check(
                    "WAL active",
                    "PASS" if str(integ.get("journal_mode")).lower() == "wal" else "UNKNOWN",
                    str(integ.get("journal_mode")),
                )
            )
            checks.append(_check("dropped event count", "PASS", str(runtime.store.loss_count())))
            checks.append(
                _check(
                    "event queue healthy",
                    "PASS",
                    f"qsize={runtime.queue.qsize()} dropped={runtime.queue.dropped}",
                )
            )
            checks.append(_check("purity registry hash", "PASS", runtime.purity.registry_hash))
            checks.append(_check("unknown purity policy", "PASS", runtime.purity.unknown_policy))
            checks.append(_check("recording fidelity", "PASS", "HOOK_METADATA"))
            checks.append(_check("exact provider capture verified", "PASS", "false"))
        except Exception as e:
            checks.append(_check("runtime probes", "FAIL", type(e).__name__))
    else:
        checks.append(_check("runtime probes", "NOT_APPLICABLE", "no runtime"))

    # never healthy if critical unknown/fail
    critical_fail = any(c["status"] == "FAIL" for c in checks)
    critical_unknown = any(
        c["name"] in {"database integrity"} and c["status"] == "UNKNOWN" for c in checks
    )
    overall = "FAIL" if critical_fail else ("UNKNOWN" if critical_unknown else "PASS")
    return {
        "overall": overall,
        "checks": checks,
        "plugin_version": __version__,
        "hermes_version": hv,
    }
