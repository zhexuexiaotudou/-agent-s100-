#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/root/.openclaw/workspace/reports/home-assistant}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/home_assistant_config_template_$stamp.md"
json="$report_dir/home_assistant_config_template_$stamp.json"
target_env="/root/.openclaw/workspace/config/home_assistant.env"

config_status="missing"
if [[ -f "$target_env" ]]; then
  config_status="present"
fi

python3 - "$json" "$stamp" "$config_status" <<'PY'
import json
import sys
from datetime import datetime

json_path, stamp, config_status = sys.argv[1:]
payload = {
    "version": 1,
    "generated_at": datetime.now().astimezone().isoformat(),
    "stamp": stamp,
    "mode": "read-only template artifact; not a credentials file",
    "target_runtime_config": "/root/.openclaw/workspace/config/home_assistant.env",
    "signals": {
        "runtime_config": config_status,
    },
    "env_template": {
        "HOME_ASSISTANT_URL": "http://homeassistant.local:8123",
        "HOME_ASSISTANT_TOKEN": "replace_with_long_lived_access_token",
    },
    "readonly_api_contract": [
        "GET /api/",
        "GET /api/states",
    ],
    "forbidden_api_contract": [
        "POST /api/services/*",
        "POST /api/states/*",
        "WebSocket control commands",
    ],
}
with open(json_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# B-008 Home Assistant Config Template"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only template artifact; not a credentials file"
  echo "- report: $report"
  echo "- json: $json"
  echo "- target_runtime_config: $target_env"
  echo
  echo "## Current Signals"
  echo
  echo "| Signal | Value |"
  echo "| --- | --- |"
  echo "| runtime_config | $config_status |"
  echo
  echo "## Runtime Env Template"
  echo
  echo "This is intentionally not written to the runtime config path."
  echo
  echo '```env'
  echo "HOME_ASSISTANT_URL=http://homeassistant.local:8123"
  echo "HOME_ASSISTANT_TOKEN=replace_with_long_lived_access_token"
  echo '```'
  echo
  echo "## Read-Only Contract"
  echo
  echo "| API | Allowed |"
  echo "| --- | --- |"
  echo "| GET /api/ | yes |"
  echo "| GET /api/states | yes |"
  echo "| POST /api/services/* | no |"
  echo "| POST /api/states/* | no |"
  echo "| WebSocket control commands | no |"
  echo
  echo "## Boundary"
  echo
  echo "- This probe does not write $target_env."
  echo "- This probe does not print, store, or validate a real token."
  echo "- This probe does not call Home Assistant."
  echo "- B-008 remains blocked until the runtime config is deliberately filled and the read-only status probe returns ok."
} > "$report"

echo "$report"
