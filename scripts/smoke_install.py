#!/usr/bin/env python3
from importlib import import_module
m = import_module("hermes_bilevel.plugin")
assert callable(m.register)
print("ok", m.register)
