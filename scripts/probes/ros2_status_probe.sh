#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-}"
if [[ -z "$out_dir" ]]; then
  if [[ -d /mnt/nas/openclaw/logs/probes && -w /mnt/nas/openclaw/logs/probes ]]; then
    out_dir="/mnt/nas/openclaw/logs/probes"
  else
    out_dir="/tmp/openclaw-probes"
  fi
fi

case "$out_dir" in
  ""|"/"|"/mnt"|"/mnt/nas"|"/home"|"/root")
    echo "Refusing unsafe output directory: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/ros2_status_$stamp.md"

ros_setup='export TERM=dumb; test -f /opt/ros/humble/setup.bash && source /opt/ros/humble/setup.bash >/dev/null 2>&1 || true; test -f /opt/tros/humble/setup.bash && source /opt/tros/humble/setup.bash >/dev/null 2>&1 || true'

run_ros() {
  local title="$1"
  local cmd="$2"
  {
    echo "## $title"
    echo
    echo '```text'
    if command -v timeout >/dev/null 2>&1; then
      timeout 12 bash -c "$ros_setup; $cmd" 2>&1 || true
    else
      bash -c "$ros_setup; $cmd" 2>&1 || true
    fi
    echo '```'
    echo
  } >> "$report"
}

{
  echo "# ROS2 Status"
  echo
  echo "- timestamp: $(date -Is)"
  echo "- hostname: $(hostname 2>/dev/null || true)"
  echo "- kernel: $(uname -a)"
  echo
  echo "## Install Paths"
  echo
  echo '```text'
  ls -ld /opt/ros/humble /opt/tros/humble 2>&1 || true
  echo '```'
  echo
} > "$report"

run_ros "ros2 command" "command -v ros2 || true; ros2 --help | sed -n '1,24p'"
run_ros "ros2 node list" "ros2 node list"
run_ros "ros2 topic list" "ros2 topic list"
run_ros "ros2 service list" "ros2 service list"
run_ros "ROS package hints" "ros2 pkg list | grep -E '^(dnn_node|dnn_node_example|hobot|hobot_|ai_msgs|img_msgs|mipi|websocket)' || true"
run_ros "ROS package prefixes" "for p in dnn_node_example dnn_node hobot_dnn ai_msgs img_msgs; do echo \"\$p:\"; ros2 pkg prefix \"\$p\" 2>&1 || true; done"

echo "$report"
