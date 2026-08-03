# Threat model

Threats considered:

- malicious candidate / path traversal / symlink escape
- prompt injection in traces
- poisoned datasets / held-out leakage
- evaluator gaming / Goodhart
- approval forgery / self-approval
- secret exfiltration via telemetry
- remote tool mutation on replay
- dependency compromise
- model fallback non-equivalence
- storage corruption / DoS via event flood (bounded queue)

Mitigations: allowlists, dual gates, redaction, deny-unknown purity,
dossier-only promotion in v0.1, append-only audit.
