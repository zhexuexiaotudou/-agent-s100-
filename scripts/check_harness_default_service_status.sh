#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8765}"
curl -fsS "$base_url/api/health" >/dev/null
curl -fsS "$base_url/api/harness/status"
