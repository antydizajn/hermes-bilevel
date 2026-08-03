#!/usr/bin/env python3
from __future__ import annotations
import subprocess, sys
from pathlib import Path

def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    run([sys.executable, "-m", "pytest"])
    run([sys.executable, "-m", "hermes_bilevel.cli", "selftest", "--json"])
    print("release verification OK")

if __name__ == "__main__":
    main()
