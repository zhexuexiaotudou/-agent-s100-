#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
report_dir="${DIGUA_UI_V2_REPORT_DIR:-$repo_root/reports}"
service_name="${DIGUA_UI_V2_SERVICE_NAME:-digua-ai-nas-ui-v2.service}"
approval="${DIGUA_UI_V2_DISABLE_APPROVAL:-}"
mkdir -p "$report_dir"

status="blocked"
message="DIGUA_UI_V2_DISABLE_APPROVAL must equal I_APPROVE_DISABLE_8765"
performed=false

if [ "$approval" = "I_APPROVE_DISABLE_8765" ]; then
  if [ "$(id -u)" != "0" ]; then
    status="blocked"
    message="root is required to disable a systemd service"
  elif ! command -v systemctl >/dev/null 2>&1; then
    status="blocked"
    message="systemctl is unavailable"
  else
    systemctl disable --now "$service_name" || true
    status="ok"
    message="service disabled or was already absent"
    performed=true
  fi
fi

python3 - "$report_dir" "$service_name" "$status" "$message" "$performed" <<'PY'
import datetime
import json
import pathlib
import sys

report_dir = pathlib.Path(sys.argv[1])
payload = {
    "ok": sys.argv[3] == "ok",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "service_name": sys.argv[2],
    "status": sys.argv[3],
    "message": sys.argv[4],
    "production_disable_performed": sys.argv[5] == "true",
}
(report_dir / "ui_v2_default_service_disable_attempt.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
(report_dir / "ui_v2_default_service_disable_attempt.md").write_text(
    "# UI v2 default service disable attempt\n\n"
    f"- ok: {payload['ok']}\n"
    f"- service_name: `{payload['service_name']}`\n"
    f"- status: {payload['status']}\n"
    f"- message: {payload['message']}\n"
    f"- production_disable_performed: {str(payload['production_disable_performed']).lower()}\n",
    encoding="utf-8",
)
print(json.dumps(payload, ensure_ascii=False))
PY

[ "$status" = "ok" ]
