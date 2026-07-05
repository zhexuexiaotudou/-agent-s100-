#!/usr/bin/env bash
set -euo pipefail

SERVICE="${AI_NAS_OPENCLAW_SERVICE:-openclaw-gateway.service}"
BASE_URL="${AI_NAS_BASE_URL:-http://127.0.0.1:8765}"

echo "# digua ai-nas ui v2 production deployment"
date -Is
echo "service=$SERVICE"
echo "base_url=$BASE_URL"

if [[ "${AI_NAS_OPERATOR_APPROVED_PRODUCTION_DEPLOYMENT:-0}" != "1" ]]; then
  echo "dry_run=true"
  echo "Set AI_NAS_OPERATOR_APPROVED_PRODUCTION_DEPLOYMENT=1 on the S100P host to restart the default service after review."
  curl -sS -m 8 "$BASE_URL/api/health" >/dev/null
  curl -sS -m 8 "$BASE_URL/ui" >/dev/null
  exit 0
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl_not_available"
  exit 2
fi

systemctl is-active "$SERVICE"
systemctl restart "$SERVICE"
sleep 3
systemctl is-active "$SERVICE"
curl -sS -m 8 "$BASE_URL/api/health" >/dev/null
curl -sS -m 8 "$BASE_URL/ui" >/dev/null
echo "deployment_restart_completed=true"
