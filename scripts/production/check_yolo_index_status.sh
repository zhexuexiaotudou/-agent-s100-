#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${DIGUA_YOLO_BASE_URL:-http://127.0.0.1:8765}"
curl -fsS "${BASE_URL}/api/yolo-index/status"
echo
