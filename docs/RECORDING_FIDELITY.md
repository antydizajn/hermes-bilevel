# Recording fidelity

Levels: HOOK_METADATA | LOGICAL_REQUEST | PROVIDER_ATTEMPT | WIRE_EXACT | UNKNOWN.

Hooks-only reports:

```
recording_fidelity: HOOK_METADATA
exact_provider_boundary_verified: false
```

Never claim wire-exact from ordinary lifecycle hooks.
