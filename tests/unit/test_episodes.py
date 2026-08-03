from __future__ import annotations

import subprocess

import pytest

from hermes_bilevel.episodes.runner import EpisodeError, EpisodeRunner

CANONICAL_NEW_FILE = (
    "diff --git a/skills/x/SKILL.md b/skills/x/SKILL.md\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/skills/x/SKILL.md\n"
    "@@ -0,0 +1,1 @@\n"
    "+hello\n"
)


@pytest.fixture()
def repo(tmp_path):
    """A real git repo with a committed baseline file."""
    git = ["git", "-C", str(tmp_path)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.name", "t"], check=True)
    subprocess.run([*git, "config", "user.email", "t@t"], check=True)
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "x").mkdir(parents=True)
    (tmp_path / "existing.md").write_text("base\n", encoding="utf-8")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "base"], check=True)
    return tmp_path


def _candidate(**kw):
    base = {
        "target_type": "skill",
        "target_path": "skills/x/SKILL.md",
        "hypothesis": "adds a skill file to make the episode pass",
        "patch": CANONICAL_NEW_FILE,
    }
    base.update(kw)
    return base


def test_episode_runner_paired_pass(repo):
    """Baseline episode must fail (file absent), candidate episode must pass."""
    runner = EpisodeRunner(workspace_root=repo)
    task = {
        "task_id": "t1",
        "command_src": (
            "import os\n"
            "print('EXISTS' if os.path.exists('skills/x/SKILL.md') else 'MISSING')\n"
        ),
        "validators": [{"type": "contains", "key": "stdout", "value": "EXISTS"}],
    }
    result = runner.run(_candidate(), task)

    assert result["mode"] == "subprocess_episode"
    assert result["label"] == "EPISODE_PASS"
    assert result["hard_gate_ok"] is True
    assert result["episode_ran"] is True
    assert result["trajectory"]["baseline"]["returncode"] == 0
    assert "MISSING" in result["trajectory"]["baseline_stdout"]
    assert "EXISTS" in result["trajectory"]["candidate_stdout"]


def test_episode_runner_paired_fail_validator(repo):
    """Candidate patch is applied but validator still fails -> EPISODE_FAIL."""
    runner = EpisodeRunner(workspace_root=repo)
    task = {
        "task_id": "t2",
        "command_src": "print('WRONG')",
        "validators": [{"type": "contains", "key": "stdout", "value": "EXPECTED"}],
    }
    result = runner.run(_candidate(), task)

    assert result["label"] == "EPISODE_FAIL"
    assert result["validators_ok"] is False
    assert result["hard_gate_ok"] is False


def test_episode_runner_requires_git_repo(tmp_path):
    runner = EpisodeRunner(workspace_root=tmp_path)  # not a git repo
    with pytest.raises(EpisodeError):
        runner.run(_candidate(), {"task_id": "t", "command_src": "print(1)"})


def test_episode_runner_patch_not_applicable(repo):
    """Patch claiming a non-zero start against /dev/null must be rejected."""
    runner = EpisodeRunner(workspace_root=repo)
    bad_patch = CANONICAL_NEW_FILE.replace("@@ -0,0 +1,1 @@", "@@ -5,1 +1,1 @@")
    with pytest.raises(EpisodeError):
        runner.run(
            _candidate(patch=bad_patch),
            {"task_id": "t", "command_src": "print(1)"},
        )


def test_episode_runner_worktrees_cleaned(repo):
    runner = EpisodeRunner(workspace_root=repo)
    runner.run(_candidate(), {"task_id": "t", "command_src": "print(1)"})
    out = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list"], capture_output=True, text=True, check=True
    )
    # only the main worktree remains
    assert len(out.stdout.strip().splitlines()) == 1
