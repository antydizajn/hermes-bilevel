from __future__ import annotations

from hermes_bilevel.redaction.redactor import redact_text


def test_openai_and_password():
    rr = redact_text("key sk-abcdefghijklmnopqrstuvwxyz123456 password=hunter2")
    assert rr.substitutions >= 2
    assert "sk-abc" not in rr.text
    assert "hunter2" not in rr.text


def test_bearer_and_github():
    rr = redact_text("Authorization: Bearer abcdefghijklmnop ghp_abcdefghijklmnopqrstuv")
    assert "abcdefghijklmnop" not in rr.text
    assert "ghp_" not in rr.text or "REDACTED" in rr.text


def test_private_key():
    pem = "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----"
    rr = redact_text(pem)
    assert "BEGIN PRIVATE KEY" not in rr.text or "REDACTED" in rr.text


def test_oversized_rejected():
    rr = redact_text("x" * 1000, max_bytes=10)
    assert rr.rejected


def test_db_url():
    rr = redact_text("postgres://user:secretpass@localhost/db")
    assert "secretpass" not in rr.text
