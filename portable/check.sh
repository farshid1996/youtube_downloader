#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=offscreen
portable/.venv/bin/python -m pytest portable/test_native.py -q
portable/.venv/bin/python - <<'PY'
import os
import sys
import tempfile
with tempfile.TemporaryDirectory() as directory:
    os.environ['HOME']=directory
    os.environ['XDG_DATA_HOME']=directory
    sys.path.insert(0,'portable')
    import launcher
    import pytest
    # The excluded test specifically exercises the unchanged Windows tool loader.
    raise SystemExit(pytest.main(['tests','-q','-k','not single_file_tools_repair_and_updates']))
PY
