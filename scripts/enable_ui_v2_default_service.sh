#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_dir="${DIGUA_UI_V2_REPORT_DIR:-$repo_root/reports}"
service_name="${DIGUA_UI_V2_SERVICE_NAME:-digua-ai-nas-ui-v2.service}"
bind="${DIGUA_UI_V2_BIND:-127.0.0.1}"
port="${DIGUA_UI_V2_PORT:-8765}"
personal_root="${DIGUA_UI_V2_PERSONAL_ROOT:-/mnt/nas/openclaw/Personal}"
report_root="${DIGUA_UI_V2_RUNTIME_REPORT_ROOT:-/mnt/nas/openclaw/reports/ai_nas_mvp}"
approval="${DIGUA_UI_V2_ALLOW_8765_ROLLOUT:-}"
mkdir -p "$report_dir"

status="blocked"
message="DIGUA_UI_V2_ALLOW_8765_ROLLOUT must equal I_APPROVE_PRODUCTION_8765"
performed=false

if [ "$approval" = "I_APPROVE_PRODUCTION_8765" ]; then
  if [ "$(id -u)" != "0" ]; then
    status="blocked"
    message="root is required to install a systemd service"
  elif ! command -v systemctl >/dev/null 2>&1; then
    status="blocked"
    message="systemctl is unavailable"
  else
    cat >"/etc/systemd/system/$service_name" <<SERVICE
[Unit]
Description=Digua AI-NAS UI v2 default service
After=network.target

[Service]
Type=simple
WorkingDirectory=$repo_root
ExecStart=/usr/bin/env python3 scripts/probes/ai_nas_operator_portal_server.py --bind $bind --port $port --no-refresh --report-root $report_root --personal-root $personal_root --sqlite-index-path $report_root/personal_inventory.sqlite3 --operation-db-path $report_root/operator_portal_operations.sqlite3 --document-fts-db-path $report_root/document_fts.sqlite3
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE
    systemctl daemon-reload
    systemctl enable --now "$service_name"
    status="ok"
    message="service enabled"
    performed=true
  fi
fi

python3 - "$report_dir" "$service_name" "$bind" "$port" "$status" "$message" "$performed" <<'PY'
import datetime
import json
import pathlib
import sys

report_dir = pathlib.Path(sys.argv[1])
payload = {
    "ok": sys.argv[5] == "ok",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "service_name": sys.argv[2],
    "bind": sys.argv[3],
    "port": int(sys.argv[4]),
    "status": sys.argv[5],
    "message": sys.argv[6],
    "production_rollout_performed": sys.argv[7] == "true",
}
(report_dir / "ui_v2_default_service_enable_attempt.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
(report_dir / "ui_v2_default_service_enable_attempt.md").write_text(
    "# UI v2 default service enable attempt\n\n"
    f"- ok: {payload['ok']}\n"
    f"- service_name: `{payload['service_name']}`\n"
    f"- port: {payload['port']}\n"
    f"- status: {payload['status']}\n"
    f"- message: {payload['message']}\n"
    f"- production_rollout_performed: {str(payload['production_rollout_performed']).lower()}\n",
    encoding="utf-8",
)
print(json.dumps(payload, ensure_ascii=False))
PY

[ "$status" = "ok" ]
