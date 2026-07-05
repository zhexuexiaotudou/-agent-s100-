#!/usr/bin/env bash
set -euo pipefail

if [[ "${AI_NAS_OPERATOR_APPROVED_S100P_YOLO_DEPLOYMENT:-}" != "1" ]]; then
  echo "refusing_restart_without_AI_NAS_OPERATOR_APPROVED_S100P_YOLO_DEPLOYMENT=1" >&2
  exit 2
fi

systemctl --user restart openclaw-gateway.service
systemctl --user is-active openclaw-gateway.service
curl -fsS http://127.0.0.1:8765/api/yolo-index/status
echo
