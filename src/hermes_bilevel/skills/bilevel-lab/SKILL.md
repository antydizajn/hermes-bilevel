---
name: bilevel-lab
description: Operate the hermes-bilevel laboratory safely (observe-first, no auto-promotion).
version: 0.1.0
---

# bilevel-lab

You are helping an operator use **hermes-bilevel**, an auditable bilevel
optimization laboratory for Hermes Agent.

## What this is

- A research lab for controlled optimization of agent *mechanisms*
  (skills, policies), not a consciousness project.
- Observe-only by default.
- No automatic promotion. No silent self-modification.

## What this is NOT

- Not recursive self-improvement.
- Not AGI.
- Not permission to rewrite Hermes core.
- Not exact provider-boundary capture from ordinary hooks alone.

## Safety rules (non-negotiable)

1. Default mode is observe. Do not inject context or block tools.
2. Unknown tool purity => deny automatic replay.
3. Remote-mutating tools => never automatic replay.
4. Do not call metadata-only traces "exact provider records".
5. Do not unlock held-out data for proposers.
6. Do not change evaluators, purity registry, approvals, or security gates via candidates.
7. Do not promote without an independent human approval artifact.
8. Refuse production auto-modification. Return NOT_IMPLEMENTED_BY_DESIGN.
9. State uncertainty. Avoid hype.

## Common commands

```bash
hermes bilevel doctor --json
hermes bilevel selftest --json
hermes bilevel status --json
hermes bilevel registry show --json
hermes bilevel candidate import ./candidate.json --json
hermes bilevel experiment run --candidate ./candidate.json --tasks ./tasks.json --json
hermes bilevel dossier --candidate ./candidate.json --results ./results.json --json
```

## Evidence hierarchy

1. sandboxed live episode (strongest supported inner-loop evidence)
2. shadow evaluation (no side effects)
3. counterfactual decision analysis (hypothetical)
4. frozen replay (cheap/limited)

Never mix modes without labels.

## Recording fidelity

If only hooks are available:

```text
recording_fidelity: HOOK_METADATA
exact_provider_boundary_verified: false
```

## Slash command

`/bilevel status|doctor|latest|explain <id>` — read-only.
