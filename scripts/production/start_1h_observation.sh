#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${AI_NAS_BASE_URL:-http://127.0.0.1:8765}"
QWEN_URL="${AI_NAS_QWEN_URL:-http://127.0.0.1:18080}"
DURATION_SECONDS="${AI_NAS_OBSERVATION_DURATION_SECONDS:-3600}"
INTERVAL_SECONDS="${AI_NAS_OBSERVATION_INTERVAL_SECONDS:-60}"
OUT="${AI_NAS_OBSERVATION_OUTPUT:-evidence/production_delivery/soak_trace.jsonl}"

mkdir -p "$(dirname "$OUT")"
echo "# production observation (${DURATION_SECONDS}s): $BASE_URL" >&2
end_time=$(( $(date +%s) + DURATION_SECONDS ))
iteration=0
failures=0

while [[ "$(date +%s)" -lt "$end_time" ]]; do
  iteration=$((iteration + 1))
  ts="$(date -Is)"
  openclaw_status="$(curl -sS -m 8 -o /tmp/digua_observe_openclaw.json -w "%{http_code}" "$BASE_URL/api/health" || true)"
  harness_status="$(curl -sS -m 8 -o /tmp/digua_observe_harness.json -w "%{http_code}" "$BASE_URL/api/harness/status" || true)"
  qwen_status="$(curl -sS -m 8 -o /tmp/digua_observe_qwen.json -w "%{http_code}" "$QWEN_URL/health" || true)"
  ok=true
  [[ "$openclaw_status" == 2* ]] || ok=false
  [[ "$harness_status" == 2* ]] || ok=false
  [[ "$qwen_status" == 2* ]] || ok=false
  [[ "$ok" == true ]] || failures=$((failures + 1))
  printf '{"ts":"%s","iteration":%s,"ok":%s,"openclaw_status":%s,"harness_status":%s,"qwen_status":%s}\n' \
    "$ts" "$iteration" "$ok" "${openclaw_status:-0}" "${harness_status:-0}" "${qwen_status:-0}" >> "$OUT"
  sleep "$INTERVAL_SECONDS"
done

echo "iterations=$iteration failures=$failures output=$OUT"
test "$failures" -eq 0
