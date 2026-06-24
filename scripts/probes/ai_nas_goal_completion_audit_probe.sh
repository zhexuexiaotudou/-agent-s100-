#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
default_services_json="/mnt/nas/openclaw/reports/ai_nas_mvp/operator_portal_server_services_validation2/services.json"
has_service_status_json=0
for arg in "$@"; do
  if [[ "$arg" == "--service-status-json" ]]; then
    has_service_status_json=1
    break
  fi
done
if [[ "$has_service_status_json" -eq 0 && -f "$default_services_json" ]]; then
  exec python3 "$script_dir/ai_nas_goal_completion_audit_probe.py" --service-status-json "$default_services_json" "$@"
fi
exec python3 "$script_dir/ai_nas_goal_completion_audit_probe.py" "$@"
