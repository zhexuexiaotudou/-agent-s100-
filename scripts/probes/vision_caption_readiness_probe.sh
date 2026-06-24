#!/usr/bin/env bash
set -euo pipefail

photos_dir="${1:-/mnt/nas/openclaw/photos}"
report_dir="${2:-/mnt/nas/openclaw/reports/image-captions}"

case "$photos_dir" in
  /tmp/*|/mnt/nas/openclaw/photos|/mnt/nas/openclaw/photos/*|/root/.openclaw/workspace/photos|/root/.openclaw/workspace/photos/*) ;;
  *)
    echo "Refusing input path outside approved photo directories: $photos_dir" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/vision_caption_readiness_$stamp.md"
json="$report_dir/vision_caption_readiness_$stamp.json"

image_count=0
if [[ -d "$photos_dir" ]]; then
  image_count="$(find "$photos_dir" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.gif' -o -iname '*.webp' -o -iname '*.bmp' \) 2>/dev/null | wc -l | tr -d ' ')"
fi

cmd_status() {
  command -v "$1" >/dev/null 2>&1 && echo yes || echo no
}

python_module_status() {
  python3 - "$1" <<'PY' >/dev/null 2>&1 && echo yes || echo no
import importlib.util
import sys
print("yes" if importlib.util.find_spec(sys.argv[1]) else "no")
PY
}

python3_available="$(cmd_status python3)"
node_available="$(cmd_status node)"
pil_available="$(python_module_status PIL)"
cv2_available="$(python_module_status cv2)"
torch_available="$(python_module_status torch)"
transformers_available="$(python_module_status transformers)"
onnxruntime_available="$(python_module_status onnxruntime)"
openvino_available="$(python_module_status openvino)"

model_dirs=(
  "/mnt/nas/openclaw/models"
  "/mnt/nas/openclaw/models/vision"
  "/root/.openclaw/workspace/models"
  "/root/.openclaw/workspace/models/vision"
)

model_file_count=0
model_dir_lines=""
for dir in "${model_dirs[@]}"; do
  if [[ -d "$dir" ]]; then
    count="$(find "$dir" -type f \( -iname '*.onnx' -o -iname '*.safetensors' -o -iname '*.bin' -o -iname '*.gguf' -o -iname '*.pt' -o -iname '*.pth' \) 2>/dev/null | wc -l | tr -d ' ')"
    model_file_count=$((model_file_count + count))
    model_dir_lines+="$dir: $count model-like files"$'\n'
  else
    model_dir_lines+="$dir: missing"$'\n'
  fi
done

semantic_runtime="no"
if [[ "$torch_available" == "yes" && "$transformers_available" == "yes" && "$model_file_count" -gt 0 ]]; then
  semantic_runtime="candidate_torch_transformers_local_model"
elif [[ "$onnxruntime_available" == "yes" && "$model_file_count" -gt 0 ]]; then
  semantic_runtime="candidate_onnxruntime_local_model"
elif [[ "$openvino_available" == "yes" && "$model_file_count" -gt 0 ]]; then
  semantic_runtime="candidate_openvino_local_model"
fi

verdict="blocked_no_semantic_runtime"
if [[ "$image_count" == "0" ]]; then
  verdict="blocked_no_images"
elif [[ "$semantic_runtime" != "no" ]]; then
  verdict="candidate_semantic_caption_ready"
fi

python3 - "$json" \
  "$photos_dir" "$report" "$image_count" "$python3_available" "$node_available" \
  "$pil_available" "$cv2_available" "$torch_available" "$transformers_available" \
  "$onnxruntime_available" "$openvino_available" "$model_file_count" "$semantic_runtime" "$verdict" <<'PY'
import json
import sys
from datetime import datetime, timezone

(
    path, photos_dir, report, image_count, python3_available, node_available,
    pil_available, cv2_available, torch_available, transformers_available,
    onnxruntime_available, openvino_available, model_file_count,
    semantic_runtime, verdict,
) = sys.argv[1:]

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "mode": "read-only semantic vision caption readiness",
    "photos_dir": photos_dir,
    "report": report,
    "image_count": int(image_count),
    "python3_available": python3_available == "yes",
    "node_available": node_available == "yes",
    "python_modules": {
        "PIL": pil_available == "yes",
        "cv2": cv2_available == "yes",
        "torch": torch_available == "yes",
        "transformers": transformers_available == "yes",
        "onnxruntime": onnxruntime_available == "yes",
        "openvino": openvino_available == "yes",
    },
    "model_file_count": int(model_file_count),
    "semantic_runtime": semantic_runtime,
    "verdict": verdict,
}

with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# Semantic Vision Caption Readiness"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only semantic vision caption readiness"
  echo "- photos_dir: $photos_dir"
  echo "- report: $report"
  echo "- json: $json"
  echo "- verdict: $verdict"
  echo
  echo "## Summary"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Image files | $image_count |"
  echo "| Python 3 | $python3_available |"
  echo "| Node.js | $node_available |"
  echo "| PIL/Pillow | $pil_available |"
  echo "| OpenCV cv2 | $cv2_available |"
  echo "| torch | $torch_available |"
  echo "| transformers | $transformers_available |"
  echo "| onnxruntime | $onnxruntime_available |"
  echo "| openvino | $openvino_available |"
  echo "| Local model-like files | $model_file_count |"
  echo "| Semantic runtime | $semantic_runtime |"
  echo
  echo "## Model Directories Checked"
  echo
  echo '```text'
  printf '%s' "$model_dir_lines"
  echo '```'
  echo
  echo "## B-003 Meaning"
  echo
  echo "- Metadata caption and JSONL indexing can be verified independently by \`image_caption_probe\`."
  echo "- Semantic vision captioning needs a local vision model/runtime or an explicit baseline scope decision."
  if [[ "$verdict" == "candidate_semantic_caption_ready" ]]; then
    echo "- This board has enough local runtime evidence to attempt a semantic caption smoke test without external API calls."
  elif [[ "$verdict" == "blocked_no_images" ]]; then
    echo "- Add images under the approved photos directory before semantic caption testing."
  else
    echo "- Current evidence does not show a local semantic vision runtime/model; keep B-003 as metadata-only unless a model is installed or mounted."
  fi
} > "$report"

echo "$report"
