# Contributing

## Principles

1. Safety first — defaults remain observe-only and fail-closed.
2. No silent mutation.
3. Evidence over claims — no RSI/AGI/Nous-approval language.
4. Public schemas and CLI JSON are versioned contracts.
5. Do not modify Hermes core; file an interface-gap report.

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
./scripts/selftest.sh
```

## PR checklist

- tests, security, privacy, compatibility, docs, reproducibility
- no secrets, no unsupported claims, fail-closed defaults preserved
