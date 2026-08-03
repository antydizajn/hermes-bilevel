# Sandboxing

Default backend: disposable temporary directory + subprocess.

- secret-stripped env allowlist
- timeout
- destroy on completion
- `network_isolation: UNKNOWN` unless stronger backend is used

Git worktree and Docker backends are planned (v0.2/v0.3).
