# Security Policy

## Supported

| Version | Supported |
|---------|-----------|
| 0.1.x | yes |

## Reporting

Use private GitHub security advisories. Do not open public issues for active exploits.

## Defaults

Observe-only. `wire=false`. No model calls. No automatic promotion.
Environment variables alone must never enable mutation.

## Hard rules

- No automatic promotion
- No candidate self-approval
- Unknown purity => deny replay
- Remote-mutating tools => never automatic replay
- Hooks never make model or network calls
