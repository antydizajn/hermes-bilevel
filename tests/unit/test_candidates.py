from __future__ import annotations

import pytest

from hermes_bilevel.candidates.validate import CandidateValidationError, validate_candidate


def _good(**kw):
    base = {
        "target_type": "skill",
        "target_path": "skills/x/SKILL.md",
        "hypothesis": "this hypothesis is falsifiable enough",
        "patch": "--- a/skills/x/SKILL.md\n+++ b/skills/x/SKILL.md\n@@ -1,1 +1,2 @@\n+hello\n",
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

def test_scope_prefix_mismatch():
    # target_type executive_policy, path outside policies/executive/
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(
            target_type="executive_policy",
            target_path="skills/x/SKILL.md"
        ))


def test_diff_scope_prefix_mismatch():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(
            target_type="skill",
            patch="--- a/policies/executive/policy.py\n+++ b/policies/executive/policy.py\n@@ -1,1 +1,2 @@\n+hello\n"
        ))


def test_git_diff_rename_copy_parsing():
    # Test diff --git header
    c1 = validate_candidate(_good(
        patch="diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n--- a/skills/x/SKILL.md\n+++ b/skills/x/SKILL.md\n@@ -1,1 +1,2 @@\n+hello\n"
    ))
    assert c1["candidate_hash"].startswith("sha256:")

    # Test rename to
    c2 = validate_candidate(_good(
        patch="rename from skills/old/SKILL.md\nrename to skills/x/SKILL.md\n--- a/skills/x/SKILL.md\n+++ b/skills/x/SKILL.md\n@@ -1,1 +1,2 @@\n+hello\n"
    ))
    assert c2["candidate_hash"].startswith("sha256:")


def test_parent_hash_strict_check():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(parent_hash=None), parent_hash="sha256:someparent")

def test_unsupported_patch_format():
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(patch_format="banana"))


def test_header_only_patch_rejected():
    with pytest.raises(CandidateValidationError):
        # Diff header exists but there is no hunk/content
        validate_candidate(_good(
            patch="diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n"
        ))


def test_malformed_patch_rejected():
    with pytest.raises(CandidateValidationError):
        # Diff with invalid hunk headers or corrupt syntax
        validate_candidate(_good(
            patch="--- a/skills/x/SKILL.md\n+++ b/skills/x/SKILL.md\n@@ corrupt hunk @@\n+invalid\n"
        ))
