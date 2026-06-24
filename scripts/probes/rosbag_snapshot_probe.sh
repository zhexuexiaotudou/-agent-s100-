#!/usr/bin/env bash
set -euo pipefail

dataset_root="${1:-${OPENCLAW_ROSBAG_DIR:-/root/.openclaw/workspace/robot_datasets}}"
report_dir="${2:-${OPENCLAW_PROBE_DIR:-/root/.openclaw/workspace/logs/probes}}"
duration="${ROSBAG_SNAPSHOT_SECONDS:-5}"

case "$dataset_root" in
  /tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
  *)
    echo "Refusing dataset path outside approved robot dataset directories: $dataset_root" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing report path outside approved probe directories: $report_dir" >&2
    exit 2
    ;;
esac

case "$duration" in
  ''|*[!0-9]*) echo "ROSBAG_SNAPSHOT_SECONDS must be an integer" >&2; exit 2 ;;
esac

if (( duration < 1 || duration > 30 )); then
  echo "ROSBAG_SNAPSHOT_SECONDS must be between 1 and 30" >&2
  exit 2
fi

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

mkdir -p "$dataset_root" "$report_dir"

timestamp="$(date +%Y%m%d-%H%M%S)"
run_id="rosbag_snapshot_$timestamp"
bag_dir="$dataset_root/$run_id"
report="$report_dir/${run_id}.md"
record_log="$report_dir/${run_id}.record.log"
ros_log_dir="$report_dir/${run_id}.ros_logs"

export HOME="${HOME:-/root}"
export ROS_LOG_DIR="$ros_log_dir"
mkdir -p "$ros_log_dir"

available_topics="$(ros2 topic list 2>/dev/null | sort || true)"
topics=()
for topic in /rosout /parameter_events; do
  if printf '%s\n' "$available_topics" | grep -Fxq "$topic"; then
    topics+=("$topic")
  fi
done

verdict="not_run"
record_exit="not_run"

if [[ ${#topics[@]} -eq 0 ]]; then
  verdict="blocked_no_topics"
else
  set +e
  timeout "$((duration + 10))" ros2 bag record -o "$bag_dir" "${topics[@]}" >"$record_log" 2>&1 &
  record_pid=$!
  sleep "$duration"
  if kill -0 "$record_pid" 2>/dev/null; then
    kill -INT "$record_pid" 2>/dev/null || true
  fi
  wait "$record_pid"
  code=$?
  set -e
  record_exit="$code"
  if [[ -f "$bag_dir/metadata.yaml" ]]; then
    verdict="ok"
  else
    verdict="record_failed"
  fi
fi

bag_info="$report_dir/${run_id}.bag_info.txt"
if [[ -f "$bag_dir/metadata.yaml" ]]; then
  ros2 bag info "$bag_dir" >"$bag_info" 2>&1 || true
fi

dataset_card="$bag_dir/DATASET_CARD.md"
if [[ -d "$bag_dir" ]]; then
  {
    echo "# Dataset Card: $run_id"
    echo
    echo "## Summary"
    echo
    echo "- generated_at: $(date -Is)"
    echo "- capture_type: bounded_rosbag_snapshot"
    echo "- dataset_id: $run_id"
    echo "- bag_dir: $bag_dir"
    echo "- duration_seconds: $duration"
    echo "- topics: ${topics[*]:-none}"
    echo "- metadata_exists: $([[ -f "$bag_dir/metadata.yaml" ]] && echo yes || echo no)"
    echo "- verdict: $verdict"
    echo
    echo "## Safety Boundary"
    echo
    echo "- No robot motion command is sent by this probe."
    echo "- Only low-risk ROS status topics are recorded in the first baseline."
    echo "- The probe is bounded to 1-30 seconds."
    echo
    echo "## Files"
    echo
    find "$bag_dir" -maxdepth 2 -type f -printf '- `%P` %s bytes\n' | sort
    echo
    echo "## Available Topics At Capture"
    echo
    echo '```text'
    printf '%s\n' "$available_topics"
    echo '```'
    if [[ -f "$bag_info" ]]; then
      echo
      echo "## Bag Info"
      echo
      echo '```text'
      sed -n '1,160p' "$bag_info"
      echo '```'
    fi
    echo
    echo "## Reproduce"
    echo
    echo '```bash'
    echo "ros2 bag info '$bag_dir'"
    echo '```'
  } > "$dataset_card"
fi

{
  echo "# ROS Bag Snapshot"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- run_id: $run_id"
  echo "- dataset_root: $dataset_root"
  echo "- bag_dir: $bag_dir"
  echo "- report_dir: $report_dir"
  echo "- duration_seconds: $duration"
  echo "- topics_requested: ${topics[*]:-none}"
  echo "- record_exit: $record_exit"
  echo "- metadata_exists: $([[ -f "$bag_dir/metadata.yaml" ]] && echo yes || echo no)"
  echo "- dataset_card: $([[ -f "$dataset_card" ]] && echo "$dataset_card" || echo none)"
  echo "- verdict: $verdict"
  echo
  echo "## Available Topics"
  echo
  echo '```text'
  printf '%s\n' "$available_topics"
  echo '```'
  echo
  echo "## Bag Files"
  echo
  if [[ -d "$bag_dir" ]]; then
    find "$bag_dir" -maxdepth 2 -type f -printf '%P %s bytes\n' | sort
  else
    echo "bag directory missing"
  fi
  echo
  echo "## Record Log"
  echo
  echo '```text'
  sed -n '1,120p' "$record_log" 2>/dev/null || true
  echo '```'
  if [[ -f "$bag_info" ]]; then
    echo
    echo "## Bag Info"
    echo
    echo '```text'
    sed -n '1,160p' "$bag_info"
    echo '```'
  fi
} > "$report"

echo "$report"
