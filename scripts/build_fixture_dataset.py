#!/usr/bin/env python3
from hermes_bilevel.datasets.manifest import build_manifest, lock_manifest
import json
m = lock_manifest(build_manifest("fixture", "inner_train", [{"task_id": "f1", "prompt": "x", "expected_token": "FIXME"}]))
print(json.dumps(m.to_dict(), indent=2))
