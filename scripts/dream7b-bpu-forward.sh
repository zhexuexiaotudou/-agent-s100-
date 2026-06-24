#!/usr/bin/env bash
set -euo pipefail

venv="${DREAM7B_BPU_VENV:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv}"
script="${DREAM7B_BPU_FORWARD_SCRIPT:-/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py}"
hbm_dir="${DREAM7B_BPU_HBM_DIR:-/mnt/nas/openclaw/models/dream7b-hbm/segments6}"
report_root="${DREAM7B_BPU_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}"

if [[ ! -x "$venv/bin/python" ]]; then
  echo "Missing Dream 7B BPU runtime venv: $venv" >&2
  exit 4
fi

if [[ ! -f "$script" ]]; then
  echo "Missing Dream 7B BPU forward script: $script" >&2
  exit 4
fi

if [[ ! -d "$hbm_dir" ]]; then
  echo "Missing Dream 7B segmented HBM directory: $hbm_dir" >&2
  exit 4
fi

args=("$@")
has_output_dir=0
has_hbm_dir=0
for arg in "${args[@]}"; do
  [[ "$arg" == "--output-dir" || "$arg" == --output-dir=* ]] && has_output_dir=1
  [[ "$arg" == "--hbm-dir" || "$arg" == --hbm-dir=* ]] && has_hbm_dir=1
done

if [[ "$has_hbm_dir" -eq 0 ]]; then
  args=(--hbm-dir "$hbm_dir" "${args[@]}")
fi

if [[ "$has_output_dir" -eq 0 ]]; then
  stamp="$(date +%Y%m%d-%H%M%S)"
  args=(--output-dir "$report_root/dream7b_bpu_forward_$stamp" "${args[@]}")
fi

source "$venv/bin/activate"
exec python "$script" "${args[@]}"
