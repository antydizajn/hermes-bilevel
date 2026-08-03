from __future__ import annotations

import pytest

from hermes_bilevel.candidates.validate import CandidateValidationError, validate_candidate


def _good(**kw):
    base = {
        "target_type": "skill",
        "target_path": "skills/x/SKILL.md",
        "hypothesis": "this hypothesis is falsifiable enough",
        "patch": "+hello\n",
    }
    base.update(kw)
    return base


def test_valid():
    c = validate_candidate(_good())
    assert c["candidate_hash"].startswith("sha256:")


def test_forbidden_path():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(target_path="../secret"))


def test_absolute_path():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(target_path="/etc/passwd"))


def test_parent_mismatch():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(parent_hash="sha256:aa"), parent_hash="sha256:bb")


def test_secret_in_patch():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(patch="token sk-abcdefghijklmnopqrstuvwxyz123456\n"))


def test_forbidden_surface():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(target_type="purity_registry"))
