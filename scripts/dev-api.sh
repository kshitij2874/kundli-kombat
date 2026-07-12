#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
exec .venv/bin/uvicorn kundli_kombat.main:app --app-dir src --host 0.0.0.0 --port 8000 --reload

