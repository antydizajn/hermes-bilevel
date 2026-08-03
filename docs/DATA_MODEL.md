# Data model

Primary store: SQLite WAL + content-addressed blobs under `$HERMES_HOME/bilevel/`.

Entities include: sessions, events, event_losses, blobs, artifacts, datasets,
candidates, evaluation_results, purity_registry_versions, correlations, audit_events.

Every research object carries schema version, timestamps, canonical hashes,
and provenance fields where applicable.
