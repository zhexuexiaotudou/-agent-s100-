#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-}"
PROJECT_DIR="${S100P_PROJECT_DIR:-/mnt/nas/openclaw}"

if [[ -z "${BACKUP_DIR}" || ! -d "${BACKUP_DIR}" ]]; then
  echo "usage: rollback_yolo_index_service.sh <backup_dir>" >&2
  exit 2
fi

cp "${BACKUP_DIR}/ai_nas_operator_portal_server.py" "${PROJECT_DIR}/scripts/probes/ai_nas_operator_portal_server.py"
if [[ -d "${BACKUP_DIR}/src" ]]; then
  cp -a "${BACKUP_DIR}/src/." "${PROJECT_DIR}/src/"
fi
systemctl --user restart openclaw-gateway.service
systemctl --user is-active openclaw-gateway.service
