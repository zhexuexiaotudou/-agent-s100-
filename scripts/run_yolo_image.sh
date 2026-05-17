#!/usr/bin/env bash
set -euo pipefail

INPUT_IMAGE="${1:-test.jpg}"
OUTPUT_IMAGE="${2:-render_result.jpeg}"
WORKDIR="${YOLO_WORKDIR:-/home/sunrise/yolo_s100p_run}"
CONFIG_FILE="${YOLO_CONFIG_FILE:-config/yolov8workconfig.json}"
LAUNCH_TIMEOUT="${YOLO_LAUNCH_TIMEOUT:-25}"
RUN_LOG="${YOLO_RUN_LOG:-yolo_run.log}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

resolve_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    readlink -m "$path"
  else
    readlink -m "$WORKDIR/$path"
  fi
}

[[ -f /opt/ros/humble/setup.bash ]] || fail "Missing /opt/ros/humble/setup.bash"
[[ -f /opt/tros/humble/setup.bash ]] || fail "Missing /opt/tros/humble/setup.bash"
[[ -d "$WORKDIR" ]] || fail "Missing YOLO workdir: $WORKDIR"

INPUT_PATH="$(resolve_path "$INPUT_IMAGE")"
OUTPUT_PATH="$(resolve_path "$OUTPUT_IMAGE")"
FEEDBACK_PATH="$WORKDIR/render_feedback_0_0.jpeg"
CONFIG_PATH="$(resolve_path "$CONFIG_FILE")"

[[ -f "$INPUT_PATH" ]] || fail "Input image not found: $INPUT_PATH"
[[ -f "$CONFIG_PATH" ]] || fail "Config file not found: $CONFIG_PATH"
[[ "$INPUT_PATH" != "$OUTPUT_PATH" ]] || fail "Input and output paths must differ: $INPUT_PATH"
[[ "$INPUT_PATH" != "$(readlink -m "$FEEDBACK_PATH")" ]] || fail "Input image cannot be render_feedback_0_0.jpeg"
[[ -d "$(dirname "$OUTPUT_PATH")" ]] || fail "Output directory does not exist: $(dirname "$OUTPUT_PATH")"

source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash
command -v ros2 >/dev/null 2>&1 || fail "ros2 is not available after sourcing ROS setup files"
ros2 pkg prefix dnn_node_example >/dev/null 2>&1 || fail "ROS package dnn_node_example is not available"

cd "$WORKDIR"
rm -f "$FEEDBACK_PATH" "$OUTPUT_PATH" "$RUN_LOG"

set +e
timeout "$LAUNCH_TIMEOUT" ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:="$CONFIG_FILE" \
  dnn_example_image:="$INPUT_PATH" >"$RUN_LOG" 2>&1
status=$?
set -e

if [[ ! -f "$FEEDBACK_PATH" ]]; then
  tail -n 120 "$RUN_LOG" >&2 || true
  fail "YOLO failed: render_feedback_0_0.jpeg was not generated"
fi

if [[ "$status" -ne 0 && "$status" -ne 124 ]]; then
  tail -n 120 "$RUN_LOG" >&2 || true
  fail "YOLO launch exited with status $status"
fi

cp "$FEEDBACK_PATH" "$OUTPUT_PATH"
echo "Result: $OUTPUT_PATH"
echo "Log: $WORKDIR/$RUN_LOG"
