#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
# Flatlib 0.2.3 incorrectly pins an obsolete pyswisseph; keep the current engine.
.venv/bin/pip install --no-deps flatlib==0.2.3

