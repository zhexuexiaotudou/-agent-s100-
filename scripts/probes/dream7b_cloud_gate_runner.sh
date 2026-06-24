#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data}"
WORK_ROOT="${WORK_ROOT:-$DATA_ROOT/dream7b-cloud}"
BUNDLE_ROOT="${BUNDLE_ROOT:-$WORK_ROOT/bundle}"
MODEL_DIR="${MODEL_DIR:-$WORK_ROOT/input/dream7b-hf}"
SDK_OELLM_BUILD="${SDK_OELLM_BUILD:-$WORK_ROOT/input/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build}"
VENV_DIR="${VENV_DIR:-$WORK_ROOT/venvs/oellm}"
WORKSPACE_PY="${WORKSPACE_PY:-$BUNDLE_ROOT/tmp/wsl_compile_dream_full_forward.py}"
REPORT_ROOT="${REPORT_ROOT:-$WORK_ROOT/reports/cloud_gates_$(date +%Y%m%d-%H%M%S)}"
MARCH="${MARCH:-nash-e}"

mkdir -p "$REPORT_ROOT"
exec > >(tee -a "$REPORT_ROOT/gate_runner.log") 2>&1

write_gate_json() {
  local name="$1"
  local status="$2"
  local details="$3"
  python3.10 - "$REPORT_ROOT/${name}.json" "$name" "$status" "$details" <<'PY'
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path, name, status, details = sys.argv[1:5]
payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "gate": name,
    "status": status,
    "details": details,
}
Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
}

require_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "ERROR: venv python missing: $VENV_DIR/bin/python" >&2
    exit 2
  fi
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
}

gate_env() {
  echo "== gate_env =="
  local errors=()
  [[ "$(uname -m)" == "x86_64" ]] || errors+=("arch_not_x86_64")
  python3.10 --version || errors+=("python3.10_missing")
  [[ -d "$MODEL_DIR" ]] || errors+=("model_dir_missing")
  [[ -f "$MODEL_DIR/config.json" ]] || errors+=("model_config_missing")
  [[ -f "$MODEL_DIR/model-00001-of-00004.safetensors" ]] || errors+=("model_shard_missing")
  [[ -d "$SDK_OELLM_BUILD" ]] || errors+=("sdk_oellm_build_missing")
  [[ -f "$WORKSPACE_PY" ]] || errors+=("workspace_py_missing")
  df -hT "$DATA_ROOT" "$WORK_ROOT" /
  free -h
  if (( ${#errors[@]} )); then
    write_gate_json "gate_env" "fail" "${errors[*]}"
    return 2
  fi
  write_gate_json "gate_env" "pass" "environment_inputs_present"
}

gate_hbdk_import() {
  echo "== gate_hbdk_import =="
  require_venv
  python - <<'PY'
import platform
import hbdk4
import leap_llm
print("python", platform.python_version(), platform.machine())
print("hbdk4", getattr(hbdk4, "__version__", "unknown"))
print("leap_llm imported")
PY
  write_gate_json "gate_hbdk_import" "pass" "hbdk4_and_leap_llm_imported"
}

state_dict_report() {
  local name="$1"
  local seg_start="$2"
  local seg_end="$3"
  local seq_len="$4"
  local batch_size="${5:-1}"
  local w_bits="${6:-8}"
  local lm_head_w_bits="${7:-0}"
  local final_logits_mode="${8:-full}"
  require_venv
  local out_dir="$WORK_ROOT/outputs/state_dict/${name}"
  mkdir -p "$out_dir"
  local extra=()
  if [[ "$lm_head_w_bits" != "0" ]]; then
    extra+=(--lm-head-w-bits "$lm_head_w_bits")
  fi
  if [[ "$final_logits_mode" != "full" ]]; then
    extra+=(--final-logits-mode "$final_logits_mode")
  fi
  /usr/bin/time -v "$VENV_DIR/bin/python" -X faulthandler "$WORKSPACE_PY" \
    --model-dir "$MODEL_DIR" \
    --output-dir "$out_dir" \
    --seq-len "$seq_len" \
    --batch-size "$batch_size" \
    --segment-start "$seg_start" \
    --segment-end "$seg_end" \
    --dtype float32 \
    --march "$MARCH" \
    --w-bits "$w_bits" \
    "${extra[@]}" \
    --state-dict-report-only \
    > "$REPORT_ROOT/${name}.stdout.log" \
    2> "$REPORT_ROOT/${name}.time.log"
  write_gate_json "$name" "pass" "state_dict_report_completed"
}

compile_segment() {
  local name="$1"
  local segments="$2"
  local seq_len="$3"
  local batch_size="${4:-1}"
  local w_bits="${5:-8}"
  local lm_head_w_bits="${6:-0}"
  local stop_after_gb="${7:-250}"
  local final_logits_mode="${8:-full}"
  require_venv
  local output_root="$WORK_ROOT/outputs/hbm/${name}"
  local report_root="$REPORT_ROOT/${name}_compile"
  mkdir -p "$output_root" "$report_root"
  env \
    BATCH_SIZE="$batch_size" \
    SEQ_LEN="$seq_len" \
    W_BITS="$w_bits" \
    LM_HEAD_W_BITS="$lm_head_w_bits" \
    FINAL_LOGITS_MODE="$final_logits_mode" \
    MARCH="$MARCH" \
    NAS_ROOT="$WORK_ROOT" \
    MODEL_DIR="$MODEL_DIR" \
    SDK_OELLM_BUILD="$SDK_OELLM_BUILD" \
    VENV_DIR="$VENV_DIR" \
    WORKSPACE_PY="$WORKSPACE_PY" \
    OUTPUT_ROOT="$output_root" \
    REPORT_ROOT="$report_root" \
    STOP_AFTER_GB="$stop_after_gb" \
    SEGMENTS="$segments" \
    /usr/bin/time -v bash "$BUNDLE_ROOT/scripts/probes/compile_dream_true_batch_segments.sh" \
    > "$REPORT_ROOT/${name}.stdout.log" \
    2> "$REPORT_ROOT/${name}.time.log"
  write_gate_json "$name" "pass" "compile_segment_completed"
}

case "${1:-}" in
  env)
    gate_env
    ;;
  hbdk-import)
    gate_hbdk_import
    ;;
  state-seq16-last)
    state_dict_report "state_seq16_last_lmheadq16" 27 28 16 1 8 16 "last-token"
    ;;
  state-seq128-last)
    state_dict_report "state_seq128_last_lmheadq16" 27 28 128 1 8 16 "last-token"
    ;;
  state-seq256-last)
    state_dict_report "state_seq256_last_lmheadq16" 27 28 256 1 8 16 "last-token"
    ;;
  compile-seq128-last)
    compile_segment "compile_seq128_last_lmheadq16" "27:28" 128 1 8 16 350 "last-token"
    ;;
  compile-seq128-hidden)
    compile_segment "compile_seq128_hidden_mid" "5:6" 128 1 8 0 250
    ;;
  compile-seq128-embed)
    compile_segment "compile_seq128_embed" "0:1" 128 1 8 0 250
    ;;
  *)
    cat <<'EOF'
Usage:
  dream7b_cloud_gate_runner.sh env
  dream7b_cloud_gate_runner.sh hbdk-import
  dream7b_cloud_gate_runner.sh state-seq16-last
  dream7b_cloud_gate_runner.sh state-seq128-last
  dream7b_cloud_gate_runner.sh state-seq256-last
  dream7b_cloud_gate_runner.sh compile-seq128-last
  dream7b_cloud_gate_runner.sh compile-seq128-hidden
  dream7b_cloud_gate_runner.sh compile-seq128-embed

Important env:
  DATA_ROOT=/data
  WORK_ROOT=/data/dream7b-cloud
  BUNDLE_ROOT=/data/dream7b-cloud/bundle
  MODEL_DIR=/data/dream7b-cloud/input/dream7b-hf
  SDK_OELLM_BUILD=/data/dream7b-cloud/input/s100_llm_sdk/D-Robotics_LLM_S100_1.0.0_SDK/oellm_build
  VENV_DIR=/data/dream7b-cloud/venvs/oellm
EOF
    exit 2
    ;;
esac
