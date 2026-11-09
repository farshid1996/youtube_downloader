#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install --timeout 120 -r ../requirements.txt
.venv/bin/python build.py "$@"
