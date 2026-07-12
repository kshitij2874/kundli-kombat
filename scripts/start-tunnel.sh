#!/usr/bin/env bash
set -euo pipefail
exec cloudflared tunnel --protocol http2 --url http://localhost:8000
