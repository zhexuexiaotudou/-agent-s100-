#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${AI_NAS_BASE_URL:-http://127.0.0.1:8765}"
QWEN_URL="${AI_NAS_QWEN_URL:-http://127.0.0.1:18080}"
AUX_URL="${AI_NAS_AUX_URL:-http://127.0.0.1:18766}"
TIMEOUT="${AI_NAS_CURL_TIMEOUT_SECONDS:-8}"

curl_json() {
  local name="$1"
  local url="$2"
  local status
  status="$(curl -sS -m "$TIMEOUT" -o /tmp/digua_status_probe.json -w "%{http_code}" "$url")"
  if [[ "$status" != 2* ]]; then
    printf '{"ok":false,"name":"%s","url":"%s","status":%s}\n' "$name" "$url" "$status"
    return 1
  fi
  printf '{"ok":true,"name":"%s","url":"%s","status":%s}\n' "$name" "$url" "$status"
}

echo "# digua ai-nas production status"
date -Is
id || true
hostname || true
ip -brief addr || true

if command -v systemctl >/dev/null 2>&1; then
  systemctl is-active openclaw-gateway.service || true
  systemctl is-active qwen25-local-openai-gateway.service || true
fi

curl_json "openclaw_health" "$BASE_URL/api/health"
curl_json "harness_status" "$BASE_URL/api/harness/status"
curl_json "agent_runtime_status" "$BASE_URL/api/agent-runtime/status"
curl_json "journal_health" "$BASE_URL/api/journal/health"
curl_json "qwen_health" "$QWEN_URL/health"
curl_json "qwen_models" "$QWEN_URL/v1/models"
curl_json "aux_health" "$AUX_URL/api/health" || true

if command -v ss >/dev/null 2>&1; then
  ss -lntp | grep -E '(:8765|:18080|:18766)' || true
fi
