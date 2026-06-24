#!/usr/bin/env bash
set -euo pipefail

# Compile static true-batch Dream7B segment HBM artifacts.
# Run on an x86_64 Linux host with the S100 LLM SDK and Dream HF model available.
# Outputs intentionally default to NAS paths, not the Windows project tree.

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: hbdk4 compiler requires x86_64 Linux, current arch is $(uname -m)." >&2
  exit 2
fi

BATCH_SIZE="${BATCH_SIZE:-2}"
SEQ_LEN="${SEQ_LEN:-16}"
W_BITS="${W_BITS:-8}"
LM_HEAD_W_BITS="${LM_HEAD_W_BITS:-0}"
FINAL_LOGITS_MODE="${FINAL_LOGITS_MODE:-full}"
MARCH="${MARCH:-nash-e}"
NAS_ROOT="${NAS_ROOT:-/mnt/nas/openclaw}"
MODEL_DIR="${MODEL_DIR:-$NAS_ROOT/models/dream7b-hf}"
SDK_OELLM_BUILD="${SDK_OELLM_BUILD:-$NAS_ROOT/toolchains/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build}"
VENV_DIR="${VENV_DIR:-/opt/digua/dream-s100-oellm-venv}"
WORKSPACE_PY="${WORKSPACE_PY:-$NAS_ROOT/scripts/probes/wsl_compile_dream_full_forward.py}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$NAS_ROOT/models/dream7b-hbm/true-batch-seq${SEQ_LEN}-b${BATCH_SIZE}}"
REPORT_ROOT="${REPORT_ROOT:-$NAS_ROOT/reports/models/dream7b_true_batch_compile_$(date +%Y%m%d-%H%M%S)}"
STOP_AFTER_GB="${STOP_AFTER_GB:-100}"
SEGMENTS="${SEGMENTS:-0:1 1:2}"

mkdir -p "$OUTPUT_ROOT" "$REPORT_ROOT"
LOG_PATH="$REPORT_ROOT/compile.log"
MANIFEST_PATH="$REPORT_ROOT/manifest.tsv"
exec > >(tee -a "$LOG_PATH") 2>&1

echo "report_root=$REPORT_ROOT"
echo "output_root=$OUTPUT_ROOT"
echo "batch_size=$BATCH_SIZE seq_len=$SEQ_LEN segments=$SEGMENTS final_logits_mode=$FINAL_LOGITS_MODE"

test -d "$MODEL_DIR"
test -f "$MODEL_DIR/config.json"
test -f "$MODEL_DIR/model-00001-of-00004.safetensors"
test -d "$SDK_OELLM_BUILD"
test -f "$SDK_OELLM_BUILD"/hbdk4_compiler-*.whl
test -f "$SDK_OELLM_BUILD"/leap_llm-*.whl
test -f "$WORKSPACE_PY"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3.10 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
if [[ "${SKIP_PIP_INSTALL:-0}" != "1" ]]; then
  python -m pip install --upgrade pip
  python -m pip install -r "$SDK_OELLM_BUILD/requirements.txt"
  python -m pip install "$SDK_OELLM_BUILD"/hbdk4_compiler-*.whl "$SDK_OELLM_BUILD"/leap_llm-*.whl
else
  python - <<'PY'
import hbdk4  # noqa: F401
import leap_llm  # noqa: F401
print("skip_pip_install=1 imports_ok")
PY
fi

printf "segment\toutput_dir\tbytes\n" > "$MANIFEST_PATH"
start_bytes="$(du -sb "$OUTPUT_ROOT" | awk '{print $1}')"
limit_bytes=$((STOP_AFTER_GB * 1024 * 1024 * 1024))

for spec in $SEGMENTS; do
  s="${spec%:*}"
  e="${spec#*:}"
  out_dir="$(printf '%s/seg%02d_%02d' "$OUTPUT_ROOT" "$s" "$e")"
  if [[ "$BATCH_SIZE" == "1" ]]; then
    base_name="dream7b_segment_${s}_${e}_seq${SEQ_LEN}_q${W_BITS}"
  else
    base_name="dream7b_segment_${s}_${e}_seq${SEQ_LEN}_b${BATCH_SIZE}_q${W_BITS}"
  fi
  compiler_extra_args=()
  if [[ "$LM_HEAD_W_BITS" != "0" && "$LM_HEAD_W_BITS" != "$W_BITS" ]]; then
    compiler_extra_args+=(--lm-head-w-bits "$LM_HEAD_W_BITS")
    base_name="${base_name}_lmheadq${LM_HEAD_W_BITS}"
  fi
  if [[ "$FINAL_LOGITS_MODE" != "full" ]]; then
    compiler_extra_args+=(--final-logits-mode "$FINAL_LOGITS_MODE")
    if [[ "$FINAL_LOGITS_MODE" == "last-token" ]]; then
      base_name="${base_name}_last_token_logits"
    fi
  fi
  echo "===COMPILE_TRUE_BATCH_SEGMENT $s $e $out_dir"
  rm -rf "$out_dir"
  mkdir -p "$out_dir"
  python -X faulthandler "$WORKSPACE_PY" \
    --model-dir "$MODEL_DIR" \
    --output-dir "$out_dir" \
    --seq-len "$SEQ_LEN" \
    --batch-size "$BATCH_SIZE" \
    --segment-start "$s" \
    --segment-end "$e" \
    --dtype float32 \
    --march "$MARCH" \
    --w-bits "$W_BITS" \
    "${compiler_extra_args[@]}"
  hbo_path="$out_dir/${base_name}.hbo"
  hbm_path="$out_dir/${base_name}.hbm"
  if [[ -f "$hbo_path" ]]; then
    python - "$hbo_path" "$hbm_path" <<'PY'
from hbdk4.compiler import link
from hbdk4.compiler.hbm import Hbo
import sys

hbo_path, hbm_path = sys.argv[1:3]
link([Hbo(hbo_path)], hbm_path)
print(f"HBM: {hbm_path}")
PY
  fi
  segment_bytes="$(du -sb "$out_dir" | awk '{print $1}')"
  printf "%s:%s\t%s\t%s\n" "$s" "$e" "$out_dir" "$segment_bytes" >> "$MANIFEST_PATH"
  current_bytes="$(du -sb "$OUTPUT_ROOT" | awk '{print $1}')"
  produced_bytes=$((current_bytes - start_bytes))
  echo "produced_bytes=$produced_bytes stop_after_bytes=$limit_bytes"
  if (( produced_bytes >= limit_bytes )); then
    echo "STOP: produced at least ${STOP_AFTER_GB}GB in this batch."
    break
  fi
done

find "$OUTPUT_ROOT" -type f \( -name '*.bc' -o -name '*.hbo' -o -name '*.hbm' \) -printf '%p\t%s\n' | sort > "$REPORT_ROOT/artifacts.tsv"
echo "verdict=true_batch_compile_driver_finished"
