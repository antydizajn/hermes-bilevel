# Grok 4.5

## Design

Use Hermes host-owned LLM interface (`ctx.llm`) — do **not** initialize the
xAI SDK directly in this plugin.

## Gates

```
model_calls.enabled=true
AND CLI --allow-model-call
AND positive budgets
```

No silent fallback. Record every attempt separately.

## v0.1 status

`HermesLlmProposalBackend` exists as an interface/test double.
Paid proposal execution is intentionally blocked until dual-gated CLI paths
are expanded in v0.2.

## Reproducibility limits

Model sampling, provider routing, and reasoning traces may be non-deterministic.
Always store provider/model/usage/latency/response hash.
