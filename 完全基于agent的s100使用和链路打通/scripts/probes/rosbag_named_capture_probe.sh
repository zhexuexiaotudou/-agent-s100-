#!/usr/bin/env bash
set -euo pipefail

dataset_root="${1:-${OPENCLAW_ROSBAG_DIR:-/mnt/nas/openclaw/robot_datasets}}"
report_dir="${2:-${OPENCLAW_PROBE_DIR:-/mnt/nas/openclaw/logs/probes}}"
duration="${ROSBAG_NAMED_CAPTURE_SECONDS:-300}"

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
  ''|*[!0-9]*) echo "ROSBAG_NAMED_CAPTURE_SECONDS must be an integer" >&2; exit 2 ;;
esac

if (( duration < 30 || duration > 1800 )); then
  echo "ROSBAG_NAMED_CAPTURE_SECONDS must be between 30 and 1800" >&2
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
session_id="approved_named_capture_$timestamp"
bag_dir="$dataset_root/$session_id"
report="$report_dir/rosbag_named_capture_$timestamp.md"
state_dir="$report_dir/rosbag_named_captures"
record_log="$report_dir/rosbag_named_capture_$timestamp.record.log"
bag_info="$report_dir/rosbag_named_capture_$timestamp.bag_info.txt"
ros_log_dir="$report_dir/rosbag_named_capture_$timestamp.ros_logs"
pid_file="$state_dir/$session_id.pid"
state_file="$state_dir/$session_id.state"

export HOME="${HOME:-/root}"
export ROS_LOG_DIR="$ros_log_dir"
mkdir -p "$state_dir" "$ros_log_dir"

available_topics="$(ros2 topic list 2>/dev/null | sort || true)"
topics=()
for topic in /rosout /parameter_events /tf /tf_static /joint_states /diagnostics; do
  if printf '%s\n' "$available_topics" | grep -Fxq "$topic"; then
    topics+=("$topic")
  fi
done

start_status="not_started"
status_after_start="not_checked"
stop_status="not_run"
record_exit="not_run"
verdict="not_run"
record_pid=""

if [[ ${#topics[@]} -eq 0 ]]; then
  verdict="blocked_no_approved_topics"
else
  {
    echo "session_id=$session_id"
    echo "bag_dir=$bag_dir"
    echo "topics=${topics[*]}"
    echo "duration_seconds=$duration"
    echo "operator_approval=chat_approved_2026-05-28"
    echo "started_at=$(date -Is)"
  } > "$state_file"

  set +e
  ros2 bag record -o "$bag_dir" "${topics[@]}" >"$record_log" 2>&1 &
  record_pid=$!
  set -e
  echo "$record_pid" > "$pid_file"
  start_status="started"

  sleep 2
  if kill -0 "$record_pid" 2>/dev/null; then
    status_after_start="running"
  else
    status_after_start="exited_early"
  fi

  sleep "$duration"
  if kill -0 "$record_pid" 2>/dev/null; then
    kill -INT "$record_pid" 2>/dev/null || true
    stop_status="sent_sigint"
  else
    stop_status="already_exited"
  fi

  set +e
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$record_pid" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if kill -0 "$record_pid" 2>/dev/null; then
    kill -TERM "$record_pid" 2>/dev/null || true
    stop_status="${stop_status}_then_sigterm"
  fi
  wait "$record_pid"
  record_exit="$?"
  set -e

  {
    echo "stopped_at=$(date -Is)"
    echo "record_exit=$record_exit"
    echo "stop_status=$stop_status"
  } >> "$state_file"

  if [[ -f "$bag_dir/metadata.yaml" ]]; then
    verdict="ok"
  else
    verdict="record_failed"
  fi
fi

if [[ -f "$bag_dir/metadata.yaml" ]]; then
  ros2 bag info "$bag_dir" >"$bag_info" 2>&1 || true
fi

dataset_card="$bag_dir/DATASET_CARD.md"
if [[ -d "$bag_dir" ]]; then
  {
    echo "# Dataset Card: $session_id"
    echo
    echo "## Summary"
    echo
    echo "- generated_at: $(date -Is)"
    echo "- capture_type: approved_named_rosbag_capture"
    echo "- dataset_id: $session_id"
    echo "- bag_dir: $bag_dir"
    echo "- duration_seconds: $duration"
    echo "- topics: ${topics[*]:-none}"
    echo "- operator_approval: chat_approved_2026-05-28"
    echo "- start_status: $start_status"
    echo "- status_after_start: $status_after_start"
    echo "- stop_status: $stop_status"
    echo "- metadata_exists: $([[ -f "$bag_dir/metadata.yaml" ]] && echo yes || echo no)"
    echo "- verdict: $verdict"
    echo
    echo "## Safety Boundary"
    echo
    echo "- This named capture uses a fixed generated session name."
    echo "- No robot motion command is sent."
    echo "- Only approved low-risk ROS status topics are recorded."
    echo "- Duration is bounded by ROSBAG_NAMED_CAPTURE_SECONDS and capped at 1800 seconds."
    echo
    echo "## Files"
    find "$bag_dir" -maxdepth 2 -type f -printf '- `%P` %s bytes\n' | sort
    if [[ -f "$bag_info" ]]; then
      echo
      echo "## Bag Info"
      echo
      echo '```text'
      sed -n '1,200p' "$bag_info"
      echo '```'
    fi
  } > "$dataset_card"
fi

{
  echo "# ROS Bag Approved Named Capture"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- session_id: $session_id"
  echo "- dataset_root: $dataset_root"
  echo "- bag_dir: $bag_dir"
  echo "- report_dir: $report_dir"
  echo "- state_dir: $state_dir"
  echo "- pid_file: $pid_file"
  echo "- state_file: $state_file"
  echo "- duration_seconds: $duration"
  echo "- operator_approval: chat_approved_2026-05-28"
  echo "- topics_requested: ${topics[*]:-none}"
  echo "- start_status: $start_status"
  echo "- status_after_start: $status_after_start"
  echo "- stop_status: $stop_status"
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
  echo "## State File"
  echo
  echo '```text'
  sed -n '1,120p' "$state_file" 2>/dev/null || true
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
  sed -n '1,220p' "$record_log" 2>/dev/null || true
  echo '```'
  if [[ -f "$bag_info" ]]; then
    echo
    echo "## Bag Info"
    echo
    echo '```text'
    sed -n '1,220p' "$bag_info"
    echo '```'
  fi
} > "$report"

echo "$report"
