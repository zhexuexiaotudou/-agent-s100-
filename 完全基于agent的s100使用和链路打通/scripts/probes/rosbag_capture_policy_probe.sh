#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:-${OPENCLAW_PROBE_DIR:-/root/.openclaw/workspace/logs/probes}}"

case "$output_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $output_dir" >&2
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

mkdir -p "$output_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$output_dir/rosbag_capture_policy_$stamp.md"
policy_json="$output_dir/rosbag_capture_policy_$stamp.json"

available_topics="$(ros2 topic list 2>/dev/null | sort || true)"
allowed_topics=()
blocked_topics=()
for topic in /rosout /parameter_events /tf /tf_static /joint_states /diagnostics; do
  if printf '%s\n' "$available_topics" | grep -Fxq "$topic"; then
    allowed_topics+=("$topic")
  fi
done

while IFS= read -r topic; do
  [[ -z "$topic" ]] && continue
  case "$topic" in
    /rosout|/parameter_events|/tf|/tf_static|/joint_states|/diagnostics) ;;
    /cmd_vel|/cmd_vel_*|*/cmd_vel|*/command|*/control|*/set_*|*/goal|*/cancel)
      blocked_topics+=("$topic")
      ;;
  esac
done <<< "$available_topics"

allowed_joined="$(printf '%s\n' "${allowed_topics[@]:-}" | sed '/^$/d' | paste -sd ' ' -)"
blocked_joined="$(printf '%s\n' "${blocked_topics[@]:-}" | sed '/^$/d' | paste -sd ' ' -)"
[[ -n "$allowed_joined" ]] || allowed_joined="none_detected"
[[ -n "$blocked_joined" ]] || blocked_joined="none_detected"

python3 - "$policy_json" "$allowed_joined" "$blocked_joined" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, allowed_raw, blocked_raw = sys.argv[1:4]
allowed = [] if allowed_raw == "none_detected" else allowed_raw.split()
blocked = [] if blocked_raw == "none_detected" else blocked_raw.split()
payload = {
    "version": 1,
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "policy_state": "draft_readonly",
    "session_name_regex": "^[a-z0-9][a-z0-9_-]{2,63}$",
    "default_duration_seconds": 300,
    "max_duration_seconds": 1800,
    "allowed_topics_detected": allowed,
    "blocked_command_like_topics_detected": blocked,
    "approved_topic_set": [
        "/rosout",
        "/parameter_events",
        "/tf",
        "/tf_static",
        "/joint_states",
        "/diagnostics",
    ],
    "retention": {
        "max_age_days": 14,
        "max_total_size_gb": 20,
        "cleanup_mode": "report_only_until_operator_approved",
    },
    "safety": {
        "starts_robot_motion": False,
        "allows_arbitrary_topics": False,
        "requires_named_session": True,
        "requires_bounded_duration": True,
        "writes_dataset_card": True,
    },
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# ROS Bag Named Capture Policy"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only policy and topic classification"
  echo "- policy_json: $policy_json"
  echo "- verdict: draft_policy_ready"
  echo
  echo "## Capture Contract"
  echo
  echo "| Field | Policy |"
  echo "| --- | --- |"
  echo "| Session name | Must match \`^[a-z0-9][a-z0-9_-]{2,63}$\` |"
  echo "| Default duration | 300 seconds |"
  echo "| Maximum duration | 1800 seconds |"
  echo "| Output root | \`/mnt/nas/openclaw/robot_datasets/<session_id>\` when NAS is mounted |"
  echo "| Required sidecar | \`DATASET_CARD.md\` |"
  echo "| Retention | 14 days or 20 GB, report-only cleanup until approved |"
  echo "| Robot motion | Never sends commands; capture only |"
  echo
  echo "## Approved Topic Set"
  echo
  echo '```text'
  printf '%s\n' /rosout /parameter_events /tf /tf_static /joint_states /diagnostics
  echo '```'
  echo
  echo "## Approved Topics Detected Now"
  echo
  echo '```text'
  if [[ "${allowed_topics[*]:-}" ]]; then
    printf '%s\n' "${allowed_topics[@]}"
  else
    echo "none"
  fi
  echo '```'
  echo
  echo "## Command-like Topics Detected And Excluded"
  echo
  echo '```text'
  if [[ "${blocked_topics[*]:-}" ]]; then
    printf '%s\n' "${blocked_topics[@]}"
  else
    echo "none"
  fi
  echo '```'
  echo
  echo "## Available Topics"
  echo
  echo '```text'
  printf '%s\n' "$available_topics"
  echo '```'
  echo
  echo "## A-009 Acceptance Meaning"
  echo
  echo "- This policy closes the named-capture design gap without launching a long recording."
  echo "- Final A-009 verification still requires one operator-approved named capture using the policy."
  echo "- Until cleanup is approved, retention cleanup is report-only and must not delete bags."
} > "$report"

echo "$report"
