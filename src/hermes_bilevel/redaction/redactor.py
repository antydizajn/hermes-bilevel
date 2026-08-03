"""Secret redaction before persistence."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

# Patterns: (rule_id, compiled regex)
_DEFAULT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("github_fine", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*([A-Za-z0-9/+=]{30,})")),
    ("bearer", re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([A-Za-z0-9._\-+=/]{8,})")),
    ("basic_auth_header", re.compile(r"(?i)(authorization\s*:\s*basic\s+)([A-Za-z0-9+/=]{8,})")),
    ("cookie_header", re.compile(r"(?i)(cookie\s*:\s*)([^\n]+)")),
    ("password_assign", re.compile(r"(?i)(password\s*[=:]\s*)([^\s#'\"]+)")),
    ("api_key_assign", re.compile(r"(?i)((?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*)([^\s#'\"]+)")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("db_url_pass", re.compile(r"((?:postgres|mysql|mongodb|redis)://[^:/\s]+:)([^@\s]+)(@)")),
    ("oauth_refresh", re.compile(r"(?i)(refresh[_-]?token\s*[=:]\s*)([^\s#'\"]+)")),
    ("xai_key", re.compile(r"xai-[A-Za-z0-9]{20,}")),
    ("env_secret_line", re.compile(r"(?m)^([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z0-9_]*\s*=\s*)(.+)$")),
    ("query_secret", re.compile(r"([?&](?:token|key|password|secret|access_token)=)([^&\s]+)", re.I)),
]

_PLACEHOLDER = "[REDACTED:{rule}]"


@dataclass
class RedactionResult:
    text: str
    original_length: int
    redacted_length: int
    substitutions: int
    rules_fired: list[str] = field(default_factory=list)
    rejected: bool = False
    reason: str = ""


def redact_text(
    text: str | None,
    *,
    custom_patterns: Sequence[str] | None = None,
    max_bytes: int = 65_536,
) -> RedactionResult:
    if text is None:
        return RedactionResult(text="", original_length=0, redacted_length=0, substitutions=0)
    original = text
    original_len = len(original.encode("utf-8"))
    if original_len > max_bytes:
        return RedactionResult(
            text="",
            original_length=original_len,
            redacted_length=0,
            substitutions=0,
            rejected=True,
            reason=f"content exceeds max_bytes={max_bytes}",
        )

    patterns = list(_DEFAULT_PATTERNS)
    if custom_patterns:
        for i, pat in enumerate(custom_patterns):
            try:
                patterns.append((f"custom_{i}", re.compile(pat)))
            except re.error:
                continue

    out = original
    fired: list[str] = []
    subs = 0
    for rule_id, cre in patterns:
        def _sub(m: re.Match[str], rid: str = rule_id) -> str:
            nonlocal subs
            subs += 1
            if m.lastindex and m.lastindex >= 2:
                # keep prefix/suffix groups when present
                if m.lastindex >= 3:
                    return f"{m.group(1)}{_PLACEHOLDER.format(rule=rid)}{m.group(3)}"
                return f"{m.group(1)}{_PLACEHOLDER.format(rule=rid)}"
            return _PLACEHOLDER.format(rule=rid)

        new_out, n = cre.subn(_sub, out)
        if n:
            fired.append(rule_id)
            out = new_out
    return RedactionResult(
        text=out,
        original_length=original_len,
        redacted_length=len(out.encode("utf-8")),
        substitutions=subs,
        rules_fired=fired,
    )
