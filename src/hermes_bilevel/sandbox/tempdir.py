"""Disposable temporary-directory subprocess sandbox."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class TempDirSandbox:
    def __init__(
        self, timeout_seconds: int = 300, env_allowlist: Sequence[str] | None = None
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.env_allowlist = list(
            env_allowlist or ["PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TMP", "TEMP"]
        )

    def prepare(self, spec: Mapping[str, Any]) -> dict[str, Any]:
        td = tempfile.mkdtemp(prefix="bilevel-sbx-")
        root = Path(td)
        # optional fixture copy
        fixture = spec.get("workspace_fixture")
        if fixture:
            src = Path(str(fixture))
            if src.exists() and src.resolve() != root.resolve():
                if src.is_dir():
                    shutil.copytree(src, root / "workspace")
                else:
                    (root / "workspace").mkdir()
                    shutil.copy2(src, root / "workspace" / src.name)
            else:
                (root / "workspace").mkdir()
        else:
            (root / "workspace").mkdir()
        return {"root": str(root), "workspace": str(root / "workspace")}

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k in self.env_allowlist}
        # strip secrets-ish
        for k in list(env):
            ku = k.upper()
            if any(s in ku for s in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")):
                env.pop(k, None)
        return env

    def run(self, handle: Mapping[str, Any], command: list[str]) -> dict[str, Any]:
        root = Path(str(handle["root"]))
        try:
            proc = subprocess.run(
                command,
                cwd=str(handle.get("workspace") or root),
                env=self._env(),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout[-50_000:],
                "stderr": proc.stderr[-50_000:],
                "network_isolation": "UNKNOWN",
            }
        except subprocess.TimeoutExpired as e:
            return {
                "returncode": -1,
                "stdout": (e.stdout or "")[-50_000:] if isinstance(e.stdout, str) else "",
                "stderr": "timeout",
                "network_isolation": "UNKNOWN",
                "timeout": True,
            }

    def collect(self, handle: Mapping[str, Any]) -> dict[str, Any]:
        root = Path(str(handle["root"]))
        files = []
        for p in root.rglob("*"):
            if p.is_file():
                files.append(p.relative_to(root).as_posix())
        return {"files": sorted(files)[:1000]}

    def destroy(self, handle: Mapping[str, Any]) -> None:
        root = handle.get("root")
        if root and Path(str(root)).exists():
            shutil.rmtree(root, ignore_errors=True)
