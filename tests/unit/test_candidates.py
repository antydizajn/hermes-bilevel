from __future__ import annotations

import pytest

from hermes_bilevel.candidates.validate import (
    CandidateValidationError,
    parse_diff_paths,
    validate_candidate,
)


def _good(**kw):
    base = {
        "target_type": "skill",
        "target_path": "skills/x/SKILL.md",
        "hypothesis": "this hypothesis is falsifiable enough",
        # Canonical new-file unified diff: --recount is forbidden, so the
        # patch must state truthful line numbers against a real baseline.
        "patch": "diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n"
                 "new file mode 100644\n"
                 "--- /dev/null\n"
                 "+++ b/skills/x/SKILL.md\n"
                 "@@ -0,0 +1,1 @@\n"
                 "+hello\n",
    }
    base.update(kw)
    return base


def test_valid():
    c = validate_candidate(_good())
    assert c["candidate_hash"].startswith("sha256:")
    assert c["validation_stage"] == "PATCH_APPLICABLE"


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
        validate_candidate(_good(
            patch="--- /dev/null\n"
                  "+++ b/skills/x/SKILL.md\n"
                  "@@ -0,0 +1,2 @@\n"
                  "+hello\n"
                  "+token sk-1234567890abcdefghijklmnopqrstuvwxyz\n"
        ))


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
            patch="--- /dev/null\n"
                  "+++ b/policies/executive/policy.py\n"
                  "@@ -0,0 +1,1 @@\n"
                  "+hello\n"
        ))


def test_git_diff_rename_copy_parsing():
    # diff --git header (new file)
    p1 = parse_diff_paths(
        "diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/skills/x/SKILL.md\n"
    )
    assert "skills/x/SKILL.md" in p1

    # rename from/to
    p2 = parse_diff_paths(
        "diff --git a/skills/old/SKILL.md b/skills/x/SKILL.md\n"
        "similarity index 100%\n"
        "rename from skills/old/SKILL.md\n"
        "rename to skills/x/SKILL.md\n"
    )
    assert "skills/old/SKILL.md" in p2
    assert "skills/x/SKILL.md" in p2

    # copy from/to
    p3 = parse_diff_paths(
        "diff --git a/skills/old/SKILL.md b/skills/x/SKILL.md\n"
        "similarity index 100%\n"
        "copy from skills/old/SKILL.md\n"
        "copy to skills/x/SKILL.md\n"
    )
    assert "skills/old/SKILL.md" in p3
    assert "skills/x/SKILL.md" in p3


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
            patch="--- /dev/null\n"
                  "+++ b/skills/x/SKILL.md\n"
                  "@@ corrupt hunk @@\n"
                  "+invalid\n"
        ))


def test_bogus_line_numbers_rejected():
    # Hunk line numbers must be truthful: git apply must NOT be allowed to
    # re-derive them (no --recount). A new-file hunk stating a non-zero
    # old-side start (-5,1 against /dev/null) is impossible and must fail.
    with pytest.raises(CandidateValidationError):
        validate_candidate(_good(
            patch="diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n"
                  "new file mode 100644\n"
                  "--- /dev/null\n"
                  "+++ b/skills/x/SKILL.md\n"
                  "@@ -5,1 +1,1 @@\n"
                  "+hello\n"
        ))
