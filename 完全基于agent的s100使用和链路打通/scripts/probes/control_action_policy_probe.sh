#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-}"
if [[ -z "$out_dir" ]]; then
  if [[ -d /mnt/nas/openclaw/logs/probes && -w /mnt/nas/openclaw/logs/probes ]]; then
    out_dir="/mnt/nas/openclaw/logs/probes"
  else
    out_dir="/root/.openclaw/workspace/logs/probes"
  fi
fi

case "$out_dir" in
  ""|"/"|"/mnt"|"/mnt/nas"|"/home"|"/root")
    echo "Refusing unsafe output directory: $out_dir" >&2
    exit 2
    ;;
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/control_action_policy_$stamp.md"

workspace="/root/.openclaw/workspace"
policy_file="$workspace/config/control_action_allowlist.json"
audit_dir="$workspace/logs/control-audit"

policy_status="missing"
policy_action_count="0"
policy_enabled_count="0"
policy_confirm_count="0"
policy_errors="not_checked"
audit_log_count="0"
pending_count="0"
approved_count="0"
executed_count="0"
verdict="blocked_no_policy"

if [[ -f "$policy_file" ]]; then
  policy_status="present"
  policy_json="$(python3 - "$policy_file" <<'PY' 2>&1 || true
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    actions = data.get("actions", [])
    errors = []
    if not isinstance(actions, list):
        errors.append("actions must be a list")
        actions = []
    enabled = 0
    confirmed = 0
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            errors.append(f"actions[{idx}] must be an object")
            continue
        action_id = action.get("id")
        if not action_id or not isinstance(action_id, str):
            errors.append(f"actions[{idx}].id missing")
        if action.get("enabled") is True:
            enabled += 1
        if isinstance(action.get("confirm_phrase"), str) and action.get("confirm_phrase"):
            confirmed += 1
        if action.get("requires_approval") is not True:
            errors.append(f"{action_id or 'unknown'} requires_approval must be true")
        if action.get("mode") not in ("dry-run", "manual-only"):
            errors.append(f"{action_id or 'unknown'} mode must be dry-run or manual-only")
    print(f"action_count={len(actions)}")
    print(f"enabled_count={enabled}")
    print(f"confirm_count={confirmed}")
    print("errors=" + ("; ".join(errors) if errors else "none"))
except Exception as exc:
    print("action_count=0")
    print("enabled_count=0")
    print("confirm_count=0")
    print("errors=" + str(exc))
PY
)"
  policy_action_count="$(printf '%s\n' "$policy_json" | awk -F= '$1=="action_count"{print $2; exit}')"
  policy_enabled_count="$(printf '%s\n' "$policy_json" | awk -F= '$1=="enabled_count"{print $2; exit}')"
  policy_confirm_count="$(printf '%s\n' "$policy_json" | awk -F= '$1=="confirm_count"{print $2; exit}')"
  policy_errors="$(printf '%s\n' "$policy_json" | awk -F= '$1=="errors"{print $2; exit}')"
  if [[ "$policy_errors" == "none" && "${policy_action_count:-0}" != "0" ]]; then
    verdict="policy_ready_no_execution"
  else
    verdict="blocked_policy_invalid"
  fi
fi

if [[ -d "$audit_dir" ]]; then
  audit_log_count="$(find "$audit_dir" -type f -name '*.jsonl' 2>/dev/null | wc -l | tr -d ' ')"
  pending_count="$({ grep -Rhs '"status"[[:space:]]*:[[:space:]]*"pending"' "$audit_dir"/*.jsonl 2>/dev/null || true; } | wc -l | tr -d ' ')"
  approved_count="$({ grep -Rhs '"status"[[:space:]]*:[[:space:]]*"approved"' "$audit_dir"/*.jsonl 2>/dev/null || true; } | wc -l | tr -d ' ')"
  executed_count="$({ grep -Rhs '"status"[[:space:]]*:[[:space:]]*"executed"' "$audit_dir"/*.jsonl 2>/dev/null || true; } | wc -l | tr -d ' ')"
fi

{
  echo "# Control Action Policy Probe"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- output: $report"
  echo "- mode: read-only policy and audit preflight"
  echo "- action_executed: no"
  echo "- control_endpoint_called: no"
  echo
  echo "## Policy"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Policy file | $policy_file |"
  echo "| Policy status | $policy_status |"
  echo "| Action count | ${policy_action_count:-0} |"
  echo "| Enabled action count | ${policy_enabled_count:-0} |"
  echo "| Actions with confirm phrase | ${policy_confirm_count:-0} |"
  echo "| Policy errors | ${policy_errors:-not_checked} |"
  echo
  echo "## Audit Log"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Audit directory | $audit_dir |"
  echo "| Audit JSONL files | $audit_log_count |"
  echo "| Pending records | $pending_count |"
  echo "| Approved records | $approved_count |"
  echo "| Executed records | $executed_count |"
  echo "| Verdict | $verdict |"
  echo
  echo "## Required Policy Shape"
  echo
  echo '```json'
  cat <<'JSON'
{
  "version": 1,
  "actions": [
    {
      "id": "ha.light.turn_on.desk",
      "enabled": false,
      "mode": "manual-only",
      "target": "home_assistant",
      "domain": "light",
      "service": "turn_on",
      "entity_id": "light.desk",
      "requires_approval": true,
      "confirm_phrase": "CONFIRM ha.light.turn_on.desk",
      "risk": "low",
      "notes": "Example only. Keep disabled until reviewed."
    }
  ]
}
JSON
  echo '```'
  echo
  echo "## Next Actions"
  if [[ "$verdict" == "blocked_no_policy" ]]; then
    echo "1. Create $policy_file with only low-risk manual-only actions."
    echo "2. Keep each action disabled until reviewed."
    echo "3. Re-run this probe; it still will not execute actions."
  elif [[ "$verdict" == "policy_ready_no_execution" ]]; then
    echo "1. Keep this as the B-009 preflight gate."
    echo "2. Implement a separate request/approve/execute path only after approval wording and audit retention are agreed."
  else
    echo "1. Fix the policy errors above."
    echo "2. Ensure every action has requires_approval=true and a confirm_phrase."
  fi
} > "$report"

echo "$report"
