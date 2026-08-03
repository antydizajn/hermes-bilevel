"""Real inner-loop episode runner: apply candidate patch in a disposable
worktree, run a paired baseline-vs-candidate episode, collect trajectory,
and evaluate with deterministic validators.

This is the first REAL (non-synthetic) execution path in the project:
the candidate patch is actually applied with ``git apply`` and a subprocess
episode runs against the patched tree. Network stays isolated (no keys in
env), the worktree is disposable and always removed, and the result is
labelled ``subprocess_episode`` -- never confused with a live Hermes run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from hermes_bilevel.candidates.validate import CandidateValidationError, validate_candidate


class EpisodeError(RuntimeError):
    pass


def _run_validators_episode(task: Mapping[str, Any], artifacts: Mapping[str, Any]) -> bool:
    """Deterministic validators over episode artifacts. Unknown validator type
    fails closed (same policy as the synthetic engine)."""
    validators = task.get("validators") or []
    if not validators:
        return True
    for v in validators:
        vtype = v.get("type") if isinstance(v, Mapping) else None
        if vtype == "artifact_exists":
            name = v.get("name")
            if name not in artifacts:
                return False
        elif vtype == "equals":
            if artifacts.get(v.get("key")) != v.get("value"):
                return False
        elif vtype == "contains":
            key = v.get("key") or ""
            hay = str(artifacts.get(key, ""))
            if str(v.get("value") or "") not in hay:
                return False
        else:
            return False
    return True


def _truncate(s: str, limit: int = 20_000) -> str:
    s = s or ""
    return s[-limit:]


class EpisodeRunner:
    """Paired baseline-vs-candidate subprocess episode in a disposable worktree.

    Semantics (honest labels):
      - baseline : episode command run against repo HEAD (patch NOT applied)
      - candidate: episode command run against repo HEAD + candidate patch
      - label    : EPISODE_PASS / EPISODE_FAIL (validators over candidate artifacts)
      - mode     : subprocess_episode  (NOT sandboxed_live_episode, NOT Hermes)
    """

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.workspace_root = Path(workspace_root or ".")
        self.timeout_seconds = timeout_seconds

    # -- worktree helpers ----------------------------------------------------

    def _add_worktree(self, git_root: Path, tmp: Path) -> Path:
        wt = tmp / "wt"
        subprocess.run(
            ["git", "-C", str(git_root), "worktree", "add", "--detach", str(wt), "HEAD"],
            check=True, capture_output=True, text=True,
        )
        return wt

    def _remove_worktree(self, git_root: Path, wt: Path) -> None:
        subprocess.run(
            ["git", "-C", str(git_root), "worktree", "remove", "--force", str(wt)],
            capture_output=True, text=True,
        )

    def _git_root(self) -> Path:
        res = subprocess.run(
            ["git", "-C", str(self.workspace_root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            raise EpisodeError("workspace is not a git repository; episode runner requires one")
        return Path(res.stdout.strip())

    @staticmethod
    def _apply_patch(worktree: Path, patch: str) -> None:
        patch_file = worktree / "cand.patch"
        patch_file.write_text(patch, encoding="utf-8")
        check = subprocess.run(
            ["git", "-C", str(worktree), "apply", "--check", "cand.patch"],
            capture_output=True, text=True,
        )
        if check.returncode != 0:
            raise EpisodeError(f"patch does not apply: {check.stderr.strip()}")
        apply = subprocess.run(
            ["git", "-C", str(worktree), "apply", "cand.patch"],
            capture_output=True, text=True,
        )
        if apply.returncode != 0:
            raise EpisodeError(f"git apply failed: {apply.stderr.strip()}")

    # -- episode --------------------------------------------------------------

    def _episode_command(self, task: Mapping[str, Any]) -> list[str]:
        cmd = task.get("command")
        if isinstance(cmd, Sequence) and not isinstance(cmd, (str, bytes)) and cmd:
            return [str(c) for c in cmd]
        src = task.get("command_src")
        if src:
            return [sys.executable, "-c", str(src)]
        raise EpisodeError("task must define 'command' (list) or 'command_src' (python source)")

    def _run_episode(self, worktree: Path, task: Mapping[str, Any]) -> dict[str, Any]:
        cmd = self._episode_command(task)
        env = {
            k: v
            for k, v in os.environ.items()
            if k in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TMP", "TEMP", "VIRTUAL_ENV"}
        }
        # strip secret-looking vars
        for k in list(env):
            ku = k.upper()
            if any(s in ku for s in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")):
                env.pop(k, None)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(worktree),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return {
                "command": cmd,
                "returncode": proc.returncode,
                "stdout": _truncate(proc.stdout),
                "stderr": _truncate(proc.stderr),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "command": cmd,
                "returncode": -1,
                "stdout": _truncate(e.stdout or "" if isinstance(e.stdout, str) else ""),
                "stderr": "timeout",
                "timed_out": True,
            }

    def run(self, candidate: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
        """Validate candidate, apply patch in a disposable worktree, run paired
        baseline-vs-candidate episode, evaluate validators, return honest report."""
        # 1) Full validation pipeline (schema, scopes, secrets, parent_hash,
        #    applicability against a real worktree of the TARGET workspace).
        try:
            validated = validate_candidate(
                dict(candidate),
                parent_hash=candidate.get("parent_hash"),
                workspace_root=self.workspace_root,
            )
        except CandidateValidationError as e:
            raise EpisodeError(f"candidate validation failed: {e.reason}") from e

        git_root = self._git_root()
        with tempfile.TemporaryDirectory(prefix="bilevel-episode-") as td:
            tmp = Path(td)

            # 2) Paired worktrees: baseline (HEAD) vs candidate (HEAD+patch).
            baseline_wt = self._add_worktree(git_root, tmp / "base")
            candidate_wt = self._add_worktree(git_root, tmp / "cand")
            try:
                self._apply_patch(candidate_wt, str(validated["patch"]))

                baseline = self._run_episode(baseline_wt, task)
                candidate = self._run_episode(candidate_wt, task)

                artifacts: dict[str, Any] = {
                    "returncode": candidate["returncode"],
                    "stdout": candidate["stdout"],
                    "stderr": candidate["stderr"],
                    "baseline_returncode": baseline["returncode"],
                    "baseline_stdout": baseline["stdout"],
                    "patched_tree": True,
                }
                validators_ok = _run_validators_episode(task, artifacts)
                hard_gate_ok = (
                    validators_ok
                    and candidate["returncode"] == 0
                    and not candidate["timed_out"]
                )

                return {
                    "mode": "subprocess_episode",
                    "label": "EPISODE_PASS" if hard_gate_ok else "EPISODE_FAIL",
                    "hard_gate_ok": hard_gate_ok,
                    "validators_ok": validators_ok,
                    "candidate_hash": validated["candidate_hash"],
                    "target_path": validated["target_path"],
                    "trajectory": {
                        "baseline": {k: baseline[k] for k in ("command", "returncode", "timed_out")},
                        "candidate": {k: candidate[k] for k in ("command", "returncode", "timed_out")},
                        "baseline_stdout": baseline["stdout"],
                        "candidate_stdout": candidate["stdout"],
                        "candidate_stderr": candidate["stderr"],
                    },
                    "artifacts": artifacts,
                    "episode_ran": True,
                }
            finally:
                self._remove_worktree(git_root, baseline_wt)
                self._remove_worktree(git_root, candidate_wt)
