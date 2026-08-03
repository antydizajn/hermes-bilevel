# Privacy

Default: metadata_only (hashes, shapes, lengths).

Modes: metadata_only | redacted_content | full_content.

Redaction runs before persistence. Delete data by removing `$HERMES_HOME/bilevel/`.
Disable hooks by disabling the plugin. Verify `wire=false` via doctor.
