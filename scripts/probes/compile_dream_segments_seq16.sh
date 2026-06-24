#!/usr/bin/env bash
set -euo pipefail

source /opt/digua/dream-s100-oellm-venv/bin/activate
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for spec in 0:4 4:7 21:24 24:28; do
  s="${spec%:*}"
  e="${spec#*:}"
  dir="$(printf '/opt/digua/dream7b-segments-seq16/seg%02d_%02d' "$s" "$e")"
  echo "===COMPILE_SEGMENT $s $e $dir"
  rm -rf "$dir"
  python -X faulthandler "$script_dir/compile_dream_segmented_full_forward.py" \
    --model-dir /opt/digua/dream_hf \
    --output-dir "$dir" \
    --seq-len 16 \
    --segment-start "$s" \
    --segment-end "$e" \
    --dtype float32 \
    --march nash-e \
    --w-bits 8
done
