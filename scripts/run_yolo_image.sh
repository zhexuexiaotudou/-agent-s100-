#!/usr/bin/env bash
set -euo pipefail

INPUT_IMAGE="${1:-test.jpg}"
OUTPUT_IMAGE="${2:-render_result.jpeg}"
WORKDIR="${YOLO_WORKDIR:-/home/sunrise/yolo_s100p_run}"

source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

cd "$WORKDIR"

pkill -f "ros2 launch dnn_node_example" 2>/dev/null || true
pkill -f "/opt/tros/humble/lib/dnn_node_example/example" 2>/dev/null || true

rm -f render_feedback_0_0.jpeg "$OUTPUT_IMAGE"

timeout 25 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:=config/yolov8workconfig.json \
  dnn_example_image:="$INPUT_IMAGE" || true

if [ ! -f render_feedback_0_0.jpeg ]; then
  echo "YOLO failed: render_feedback_0_0.jpeg not generated" >&2
  exit 1
fi

cp render_feedback_0_0.jpeg "$OUTPUT_IMAGE"
echo "Result: $WORKDIR/$OUTPUT_IMAGE"
