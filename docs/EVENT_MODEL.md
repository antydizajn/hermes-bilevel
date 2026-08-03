# Event model

Versioned envelope fields: event_id, event_type, schema_version, created_at,
monotonic_ns, session/turn/task/tool ids, source, plugin/hermes versions,
payload, payload_hash, redaction_summary, correlation_quality, lossy.

Events are append-only. Corrections are new events.
