#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data}"
WORK_ROOT="${WORK_ROOT:-$DATA_ROOT/dream7b-cloud}"
BUNDLE_ROOT="${BUNDLE_ROOT:-$WORK_ROOT/bundle}"
MODEL_DIR="${MODEL_DIR:-$WORK_ROOT/input/dream7b-hf}"
SDK_OELLM_BUILD="${SDK_OELLM_BUILD:-$WORK_ROOT/input/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build}"
VENV_DIR="${VENV_DIR:-$WORK_ROOT/venvs/oellm}"
WORKSPACE_PY="${WORKSPACE_PY:-$BUNDLE_ROOT/tmp/wsl_compile_dream_full_forward.py}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$WORK_ROOT/outputs/hbm/seq128_b1_lmheadq16_lasttoken_full}"
REPORT_ROOT="${REPORT_ROOT:-$WORK_ROOT/reports/cloud_parallel_seq128_$(date +%Y%m%d-%H%M%S)}"
MAX_JOBS="${MAX_JOBS:-8}"
SEQ_LEN="${SEQ_LEN:-128}"
BATCH_SIZE="${BATCH_SIZE:-1}"
W_BITS="${W_BITS:-8}"
MARCH="${MARCH:-nash-e}"
STOP_AFTER_GB="${STOP_AFTER_GB:-250}"
SEGMENTS="${SEGMENTS:-}"

if [[ -z "$SEGMENTS" ]]; then
  SEGMENTS="$(seq 1 26 | awk '{printf "%d:%d ", $1, $1 + 1}')"
fi

mkdir -p "$OUTPUT_ROOT" "$REPORT_ROOT/status"
exec > >(tee -a "$REPORT_ROOT/parallel.log") 2>&1

echo "report_root=$REPORT_ROOT"
echo "output_root=$OUTPUT_ROOT"
echo "max_jobs=$MAX_JOBS seq_len=$SEQ_LEN batch_size=$BATCH_SIZE segments=$SEGMENTS"

compile_one() {
  local spec="$1"
  local safe="${spec/:/_}"
  local seg_report="$REPORT_ROOT/seg${safe}"
  mkdir -p "$seg_report"
  echo "START segment=$spec report=$seg_report"
  env \
    DATA_ROOT="$DATA_ROOT" \
    WORK_ROOT="$WORK_ROOT" \
    BUNDLE_ROOT="$BUNDLE_ROOT" \
    MODEL_DIR="$MODEL_DIR" \
    SDK_OELLM_BUILD="$SDK_OELLM_BUILD" \
    VENV_DIR="$VENV_DIR" \
    WORKSPACE_PY="$WORKSPACE_PY" \
    OUTPUT_ROOT="$OUTPUT_ROOT" \
    REPORT_ROOT="$seg_report" \
    BATCH_SIZE="$BATCH_SIZE" \
    SEQ_LEN="$SEQ_LEN" \
    W_BITS="$W_BITS" \
    LM_HEAD_W_BITS=0 \
    FINAL_LOGITS_MODE=full \
    MARCH="$MARCH" \
    STOP_AFTER_GB="$STOP_AFTER_GB" \
    SEGMENTS="$spec" \
    SKIP_PIP_INSTALL=1 \
    bash "$BUNDLE_ROOT/scripts/probes/compile_dream_true_batch_segments.sh"
  echo "PASS segment=$spec" | tee "$REPORT_ROOT/status/seg${safe}.pass"
}

active=0
failed=0
for spec in $SEGMENTS; do
  (
    set +e
    compile_one "$spec"
    rc=$?
    safe="${spec/:/_}"
    echo "$rc" > "$REPORT_ROOT/status/seg${safe}.exit"
    exit "$rc"
  ) &
  active=$((active + 1))
  if (( active >= MAX_JOBS )); then
    if ! wait -n; then
      failed=1
    fi
    active=$((active - 1))
  fi
done

while (( active > 0 )); do
  if ! wait -n; then
    failed=1
  fi
  active=$((active - 1))
done

find "$OUTPUT_ROOT" -maxdepth 2 -type f \( -name '*.hbm' -o -name '*.hbo' -o -name '*.bc' \) -printf '%p\t%s\n' | sort > "$REPORT_ROOT/artifacts.tsv"
if (( failed )); then
  echo "verdict=parallel_compile_failed"
  exit 1
fi
echo "verdict=parallel_compile_finished"
