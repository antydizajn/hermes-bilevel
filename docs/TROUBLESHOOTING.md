# Troubleshooting

| Symptom | Check |
|---------|-------|
| Plugin not listed | entry point installed? `pip show hermes-bilevel` |
| Plugin listed but inactive | `hermes plugins enable bilevel` |
| Doctor UNKNOWN Hermes | hermes-agent not installed in same env |
| Queue drops | increase hooks.queue_size; inspect event_losses |
| Selftest fail | run with empty tmp root; ensure python>=3.11 |
