#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/root/.openclaw/workspace/reports/rosbag}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

set +u
if [[ -f /opt/ros/humble/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
fi
if [[ -f /opt/tros/humble/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /opt/tros/humble/setup.bash
fi
set -u

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/rosbag_named_capture_request_$stamp.md"
json="$report_dir/rosbag_named_capture_request_$stamp.json"

available_topics="$(ros2 topic list 2>/dev/null | sort || true)"
approved_topics=()
for topic in /rosout /parameter_events /tf /tf_static /joint_states /diagnostics; do
  if printf '%s\n' "$available_topics" | grep -Fxq "$topic"; then
    approved_topics+=("$topic")
  fi
done

command_like_topics=()
while IFS= read -r topic; do
  [[ -z "$topic" ]] && continue
  case "$topic" in
    /cmd_vel|/cmd_vel_*|*/cmd_vel|*/command|*/control|*/set_*|*/goal|*/cancel)
      command_like_topics+=("$topic")
      ;;
  esac
done <<< "$available_topics"

latest_policy="$(find /root/.openclaw/workspace/logs/probes -maxdepth 1 -type f -name 'rosbag_capture_policy_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"
latest_session="$(find /root/.openclaw/workspace/logs/probes -maxdepth 1 -type f -name 'rosbag_session_*.md' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')"

approved_joined="$(printf '%s\n' "${approved_topics[@]:-}" | sed '/^$/d' | paste -sd ' ' -)"
command_joined="$(printf '%s\n' "${command_like_topics[@]:-}" | sed '/^$/d' | paste -sd ' ' -)"
[[ -n "$approved_joined" ]] || approved_joined="none_detected"
[[ -n "$command_joined" ]] || command_joined="none_detected"

python3 - "$json" "$report" "$approved_joined" "$command_joined" "${latest_policy:-missing}" "${latest_session:-missing}" <<'PY'
import json
import sys
from datetime import datetime

json_path, report, approved_raw, command_raw, latest_policy, latest_session = sys.argv[1:]
approved = [] if approved_raw == "none_detected" else approved_raw.split()
command_like = [] if command_raw == "none_detected" else command_raw.split()

payload = {
    "version": 1,
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only named capture request template; no rosbag record started",
    "report": report,
    "latest_policy": latest_policy,
    "latest_session": latest_session,
    "request_template": {
        "session_name": "replace_with_reviewed_session_name",
        "duration_seconds": 300,
        "topics": approved,
        "dataset_root": "/root/.openclaw/workspace/robot_datasets",
        "requires_operator_approval": True,
        "approval_record": {
            "operator": "",
            "approved_at": "",
            "reason": "",
            "scope_confirmed": False,
        },
    },
    "blocked_topics_detected": command_like,
    "execution_boundary": [
        "does not start ros2 bag record",
        "does not create a dataset directory",
        "does not delete or clean existing bags",
        "does not send robot commands",
    ],
}

with open(json_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

topics_json="$(python3 - "$approved_joined" <<'PY'
import json
import sys
raw = sys.argv[1]
print(json.dumps([] if raw == "none_detected" else raw.split()))
PY
)"

{
  echo "# A-009 ROS Bag Named Capture Request Template"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only named capture request template; no rosbag record started"
  echo "- report: $report"
  echo "- json: $json"
  echo "- latest_policy: ${latest_policy:-missing}"
  echo "- latest_session: ${latest_session:-missing}"
  echo
  echo "## Current Topic Signals"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Approved topics detected | ${approved_joined} |"
  echo "| Command-like topics excluded | ${command_joined} |"
  echo
  echo "## Request Template"
  echo
  echo '```json'
  cat <<JSON
{
  "session_name": "replace_with_reviewed_session_name",
  "duration_seconds": 300,
  "topics": $topics_json,
  "dataset_root": "/root/.openclaw/workspace/robot_datasets",
  "requires_operator_approval": true,
  "approval_record": {
    "operator": "",
    "approved_at": "",
    "reason": "",
    "scope_confirmed": false
  }
}
JSON
  echo '```'
  echo
  echo "## Available Topics"
  echo
  echo '```text'
  printf '%s\n' "$available_topics"
  echo '```'
  echo
  echo "## Boundary"
  echo
  echo "- This probe does not start ros2 bag record."
  echo "- This probe does not create a dataset directory."
  echo "- This probe does not delete or clean existing bags."
  echo "- This probe does not send robot commands."
  echo "- A-009 final verification still requires one deliberately approved named capture."
} > "$report"

echo "$report"
