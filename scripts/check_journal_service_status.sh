#!/usr/bin/env sh
set -eu

BASE_URL="${JOURNAL_BASE_URL:-http://127.0.0.1:8765}"
curl -fsS "$BASE_URL/api/journal/health"
