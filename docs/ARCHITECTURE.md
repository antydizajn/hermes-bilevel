# Architecture

## Layers

1. **Hermes integration** (`plugin.py`, `cli.py`, hooks) — thin adapters.
2. **Experiment engine** — config, events, storage, recorders, correlation,
   datasets, candidates, evaluation, statistics, sandbox, governance, reporting.
3. **Protocols** (`protocols.py`) — dependency inversion; no live PluginContext.

## Data flow (observe)

hook kwargs → sanitize/shape/hash → EventEnvelope → BoundedEventQueue → SQLite/blobs

## Non-goals in plugin layer

No tool override, no message injection, no provider transport patching,
no private `_manager` / `_cli_ref` access.
