#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/root/.openclaw/workspace/reports/control}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/control_action_template_$stamp.md"
json="$report_dir/control_action_template_$stamp.json"

runtime_policy="/root/.openclaw/workspace/config/control_action_allowlist.json"
audit_dir="/root/.openclaw/workspace/logs/control-audit"
ha_env="/root/.openclaw/workspace/config/home_assistant.env"

policy_status="missing"
if [[ -f "$runtime_policy" ]]; then
  policy_status="present"
fi

ha_config_status="missing"
if [[ -f "$ha_env" ]]; then
  ha_config_status="present"
fi

audit_status="missing"
if [[ -d "$audit_dir" ]]; then
  audit_status="present"
fi

python3 - "$json" "$stamp" "$policy_status" "$ha_config_status" "$audit_status" <<'PY'
import json
import sys
from datetime import datetime

json_path, stamp, policy_status, ha_config_status, audit_status = sys.argv[1:]
payload = {
    "version": 1,
    "generated_at": datetime.now().astimezone().isoformat(),
    "stamp": stamp,
    "mode": "read-only template artifact; not a runtime control allowlist",
    "target_runtime_policy": "/root/.openclaw/workspace/config/control_action_allowlist.json",
    "signals": {
        "runtime_policy": policy_status,
        "home_assistant_config": ha_config_status,
        "audit_directory": audit_status,
    },
    "template": {
        "version": 1,
        "policy_state": "draft_template",
        "description": "Draft B-009 reviewed control action template. Copy only after Home Assistant and approval wording are reviewed.",
        "audit": {
            "directory": "/root/.openclaw/workspace/logs/control-audit",
            "retention_days": 30,
            "records": ["requested", "approved", "executed", "rejected"],
        },
        "actions": [
            {
                "id": "ha.light.turn_on.reviewed_example",
                "enabled": False,
                "mode": "manual-only",
                "target": "home_assistant",
                "domain": "light",
                "service": "turn_on",
                "entity_id": "light.reviewed_example",
                "requires_approval": True,
                "confirm_phrase": "CONFIRM ha.light.turn_on.reviewed_example",
                "risk": "low",
                "review": {
                    "reviewer": "",
                    "reviewed_at": "",
                    "scope": "example only; replace after Home Assistant entity review",
                },
                "notes": "Template only. Keep disabled until reviewed and backed by a real HA entity.",
            }
        ],
    },
    "request_record_template": {
        "version": 1,
        "action_id": "ha.light.turn_on.reviewed_example",
        "status": "requested",
        "requested_by": "",
        "requested_at": "",
        "confirm_phrase": "",
        "parameters": {},
    },
    "approval_record_template": {
        "version": 1,
        "action_id": "ha.light.turn_on.reviewed_example",
        "status": "approved",
        "approved_by": "",
        "approved_at": "",
        "confirm_phrase_matched": False,
    },
}

with open(json_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# B-009 Control Action Template"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only template artifact; not a runtime control allowlist"
  echo "- report: $report"
  echo "- json: $json"
  echo "- target_runtime_policy: $runtime_policy"
  echo
  echo "## Current Signals"
  echo
  echo "| Signal | Value |"
  echo "| --- | --- |"
  echo "| runtime_policy | $policy_status |"
  echo "| home_assistant_config | $ha_config_status |"
  echo "| audit_directory | $audit_status |"
  echo
  echo "## Required Control Gates"
  echo
  echo "| Gate | Required State |"
  echo "| --- | --- |"
  echo "| runtime allowlist | reviewed real actions only; examples must stay disabled |"
  echo "| action enabled flag | false until Home Assistant entity, risk, and approval wording are reviewed |"
  echo "| approval | request, approve, execute, and reject records in JSONL audit |"
  echo "| execution | unavailable from this probe; this probe never calls Home Assistant |"
  echo
  echo "## Draft Runtime Policy"
  echo
  echo "This is intentionally not written to the runtime policy path."
  echo
  echo '```json'
  python3 - "$json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as fh:
    print(json.dumps(json.load(fh)["template"], ensure_ascii=False, indent=2))
PY
  echo '```'
  echo
  echo "## Audit Record Templates"
  echo
  echo '```json'
  python3 - "$json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)
print(json.dumps({
    "request": payload["request_record_template"],
    "approval": payload["approval_record_template"],
}, ensure_ascii=False, indent=2))
PY
  echo '```'
  echo
  echo "## Boundary"
  echo
  echo "- This probe does not write $runtime_policy."
  echo "- This probe does not call Home Assistant or any device control API."
  echo "- B-009 remains blocked until real reviewed actions and approval audit records exist."
} > "$report"

echo "$report"
