#!/usr/bin/env bash
set -euo pipefail

base_hbm_dir="${DREAM7B_BPU_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/segments6}"
fine_hbm_dir="${DREAM7B_BPU_FINE_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16}"
resplit_hbm_dir="${DREAM7B_BPU_RESPLIT_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-seq16}"
topwindow_hbm_dir="${DREAM7B_BPU_TOPWINDOW_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/resplit-topwindow-seq16}"
phase1_hbm_dir="${DREAM7B_BPU_PHASE1_HBM_DIR:-/home/sunrise/.cache/openclaw/dream7b-hbm/phase1-topload-seq16}"
segment_plan="${DREAM7B_BPU_RESPLIT_SEGMENT_PLAN:-resplit-adjacent}"
window_size="${DREAM7B_BPU_RESPLIT_BATCH_WINDOW_SIZE:-2}"
child_window_mode="${DREAM7B_BPU_RESPLIT_BATCH_CHILD_WINDOW_MODE:-pair}"
child_runtime_mode="${DREAM7B_BPU_RESPLIT_BATCH_CHILD_RUNTIME_MODE:-packed}"
window_execution_mode="${DREAM7B_BPU_RESPLIT_BATCH_WINDOW_EXECUTION_MODE:-window-batch}"
tokens_batch_json="${DREAM7B_BPU_RESPLIT_TOKENS_BATCH_JSON:-}"

args=("$@")
has_hbm_dir=0
has_fine_hbm_dir=0
has_resplit_hbm_dir=0
has_topwindow_hbm_dir=0
has_phase1_hbm_dir=0
has_segment_plan=0
has_window_size=0
has_child_window_mode=0
has_child_runtime_mode=0
has_window_execution_mode=0
has_tokens_batch_json=0

for arg in "${args[@]}"; do
  [[ "$arg" == "--hbm-dir" || "$arg" == --hbm-dir=* ]] && has_hbm_dir=1
  [[ "$arg" == "--fine-hbm-dir" || "$arg" == --fine-hbm-dir=* ]] && has_fine_hbm_dir=1
  [[ "$arg" == "--resplit-hbm-dir" || "$arg" == --resplit-hbm-dir=* ]] && has_resplit_hbm_dir=1
  [[ "$arg" == "--topwindow-hbm-dir" || "$arg" == --topwindow-hbm-dir=* ]] && has_topwindow_hbm_dir=1
  [[ "$arg" == "--phase1-hbm-dir" || "$arg" == --phase1-hbm-dir=* ]] && has_phase1_hbm_dir=1
  [[ "$arg" == "--segment-plan" || "$arg" == --segment-plan=* ]] && has_segment_plan=1
  [[ "$arg" == "--residency-window-size" || "$arg" == --residency-window-size=* ]] && has_window_size=1
  [[ "$arg" == "--child-window-mode" || "$arg" == --child-window-mode=* ]] && has_child_window_mode=1
  [[ "$arg" == "--child-runtime-mode" || "$arg" == --child-runtime-mode=* ]] && has_child_runtime_mode=1
  [[ "$arg" == "--window-execution-mode" || "$arg" == --window-execution-mode=* ]] && has_window_execution_mode=1
  [[ "$arg" == "--tokens-batch-json" || "$arg" == --tokens-batch-json=* ]] && has_tokens_batch_json=1
done

if [[ "$has_hbm_dir" -eq 0 ]]; then
  args=(--hbm-dir "$base_hbm_dir" "${args[@]}")
fi

if [[ "$has_fine_hbm_dir" -eq 0 ]]; then
  args=(--fine-hbm-dir "$fine_hbm_dir" "${args[@]}")
fi

if [[ "$has_resplit_hbm_dir" -eq 0 ]]; then
  args=(--resplit-hbm-dir "$resplit_hbm_dir" "${args[@]}")
fi

if [[ "$has_topwindow_hbm_dir" -eq 0 ]]; then
  args=(--topwindow-hbm-dir "$topwindow_hbm_dir" "${args[@]}")
fi

if [[ "$has_phase1_hbm_dir" -eq 0 ]]; then
  args=(--phase1-hbm-dir "$phase1_hbm_dir" "${args[@]}")
fi

if [[ "$has_segment_plan" -eq 0 ]]; then
  args=(--segment-plan "$segment_plan" "${args[@]}")
fi

if [[ "$has_window_size" -eq 0 ]]; then
  args=(--residency-window-size "$window_size" "${args[@]}")
fi

if [[ "$has_child_window_mode" -eq 0 ]]; then
  args=(--child-window-mode "$child_window_mode" "${args[@]}")
fi

if [[ "$has_child_runtime_mode" -eq 0 ]]; then
  args=(--child-runtime-mode "$child_runtime_mode" "${args[@]}")
fi

if [[ "$has_window_execution_mode" -eq 0 ]]; then
  args=(--window-execution-mode "$window_execution_mode" "${args[@]}")
fi

if [[ "$has_tokens_batch_json" -eq 0 && -n "$tokens_batch_json" ]]; then
  args=(--tokens-batch-json "$tokens_batch_json" "${args[@]}")
fi

exec dream7b-bpu-forward "${args[@]}"
