#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${AI_NAS_PRODUCTION_EVIDENCE_DIR:-evidence/production_delivery/manual_collect}"
BASE_URL="${AI_NAS_BASE_URL:-http://127.0.0.1:8765}"
QWEN_URL="${AI_NAS_QWEN_URL:-http://127.0.0.1:18080}"
mkdir -p "$OUT_DIR"

date -Is > "$OUT_DIR/collected_at.txt"
id > "$OUT_DIR/id.txt" 2>&1 || true
hostname > "$OUT_DIR/hostname.txt" 2>&1 || true
ip -brief addr > "$OUT_DIR/ip_addr.txt" 2>&1 || true
ss -lntp > "$OUT_DIR/ports.txt" 2>&1 || true
systemctl status openclaw-gateway.service --no-pager > "$OUT_DIR/openclaw_gateway_status.txt" 2>&1 || true
systemctl status qwen25-local-openai-gateway.service --no-pager > "$OUT_DIR/qwen_gateway_status.txt" 2>&1 || true
journalctl -u openclaw-gateway.service -n 200 --no-pager > "$OUT_DIR/openclaw_gateway_journal_tail.txt" 2>&1 || true
journalctl -u qwen25-local-openai-gateway.service -n 200 --no-pager > "$OUT_DIR/qwen_gateway_journal_tail.txt" 2>&1 || true

curl -sS -m 8 "$BASE_URL/api/health" > "$OUT_DIR/api_health.json"
curl -sS -m 8 "$BASE_URL/api/harness/status" > "$OUT_DIR/api_harness_status.json"
curl -sS -m 8 "$BASE_URL/api/agent-runtime/status" > "$OUT_DIR/api_agent_runtime_status.json"
curl -sS -m 8 "$BASE_URL/api/journal/health" > "$OUT_DIR/api_journal_health.json"
curl -sS -m 8 "$QWEN_URL/health" > "$OUT_DIR/qwen_health.json"
curl -sS -m 8 "$QWEN_URL/v1/models" > "$OUT_DIR/qwen_models.json"

echo "evidence_dir=$OUT_DIR"
