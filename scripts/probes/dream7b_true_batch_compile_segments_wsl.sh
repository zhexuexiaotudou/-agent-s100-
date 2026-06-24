#!/usr/bin/env bash
set -euo pipefail

SEGMENTS="${SEGMENTS:-}"
BATCH_SIZE="${BATCH_SIZE:-4}"
SEQ_LEN="${SEQ_LEN:-16}"
W_BITS="${W_BITS:-8}"
LM_HEAD_W_BITS="${LM_HEAD_W_BITS:-0}"
MARCH="${MARCH:-nash-e}"
FINAL_LOGITS_MODE="${FINAL_LOGITS_MODE:-full}"
MODEL_DIR="${MODEL_DIR:-/mnt/f/Project/Digua/tmp/true_batch_inputs/dream7b-hf}"
COMPILER_PY="${COMPILER_PY:-/mnt/f/Project/Digua/tmp/wsl_compile_dream_full_forward.py}"
STAGE_ROOT="${STAGE_ROOT:-/mnt/f/Project/Digua/tmp/true_batch_hbm_stage}"
LOG_DIR="${LOG_DIR:-$STAGE_ROOT/logs}"

if [[ -z "$SEGMENTS" ]]; then
  echo "SEGMENTS is required, for example SEGMENTS='7:8,8:9'" >&2
  exit 2
fi

source /opt/digua/dream-true-batch-venv/bin/activate
mkdir -p "$STAGE_ROOT" "$LOG_DIR"

IFS=', ' read -r -a segment_specs <<< "$SEGMENTS"
for spec in "${segment_specs[@]}"; do
  [[ -z "$spec" ]] && continue
  if [[ ! "$spec" =~ ^([0-9]+):([0-9]+)$ ]]; then
    echo "invalid segment spec: $spec" >&2
    exit 2
  fi
  start="${BASH_REMATCH[1]}"
  end="${BASH_REMATCH[2]}"
  if (( end <= start )); then
    echo "segment end must be greater than start: $spec" >&2
    exit 2
  fi
  if [[ "$FINAL_LOGITS_MODE" != "full" ]] && { [[ "$start" != "27" ]] || [[ "$end" != "28" ]]; }; then
    echo "FINAL_LOGITS_MODE=$FINAL_LOGITS_MODE is only valid for final segment 27:28" >&2
    exit 2
  fi

  segment_name="$(printf 'seg%02d_%02d' "$start" "$end")"
  base_name="dream7b_segment_${start}_${end}_seq${SEQ_LEN}_b${BATCH_SIZE}_q${W_BITS}"
  compiler_extra_args=()
  if [[ "$LM_HEAD_W_BITS" != "0" && "$LM_HEAD_W_BITS" != "$W_BITS" ]]; then
    compiler_extra_args+=(--lm-head-w-bits "$LM_HEAD_W_BITS")
    base_name="${base_name}_lmheadq${LM_HEAD_W_BITS}"
  fi
  if [[ "$FINAL_LOGITS_MODE" != "full" ]]; then
    compiler_extra_args+=(--final-logits-mode "$FINAL_LOGITS_MODE")
    base_name="${base_name}_last_token_logits"
  fi
  out_dir="$STAGE_ROOT/$segment_name"
  log_path="$LOG_DIR/compile_${segment_name}_b${BATCH_SIZE}_$(date +%Y%m%d-%H%M%S).log"

  rm -rf "$out_dir"
  mkdir -p "$out_dir"
  echo "COMPILE $segment_name B=$BATCH_SIZE seq=$SEQ_LEN"
  python -X faulthandler "$COMPILER_PY" \
    --model-dir "$MODEL_DIR" \
    --output-dir "$out_dir" \
    --seq-len "$SEQ_LEN" \
    --batch-size "$BATCH_SIZE" \
    --segment-start "$start" \
    --segment-end "$end" \
    --dtype float32 \
    --march "$MARCH" \
    --w-bits "$W_BITS" \
    "${compiler_extra_args[@]}" 2>&1 | tee "$log_path"

  python - "$out_dir" "$base_name" <<'PY'
from hbdk4.compiler import link
from hbdk4.compiler.hbm import Hbo
from pathlib import Path
import sys

base = Path(sys.argv[1])
name = sys.argv[2]
hbo_path = base / f"{name}.hbo"
hbm_path = base / f"{name}.hbm"
if not hbo_path.exists():
    raise SystemExit(f"missing HBO: {hbo_path}")
link([Hbo(str(hbo_path))], str(hbm_path))
print(f"HBM: {hbm_path}")
print(f"HBM_SIZE: {hbm_path.stat().st_size}")
PY

  (
    cd "$out_dir"
    sha256sum "$base_name.bc" "${base_name}_convert.bc" "${base_name}_convert_removed.bc" "$base_name.hbo" "$base_name.hbm" > manifest.sha256
    sha256sum -c manifest.sha256
    du -sb .
  )
done
