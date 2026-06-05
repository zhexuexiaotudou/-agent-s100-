#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-/tmp/project_docs_consistency}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac

mkdir -p "$report_root"

required_files=(
  "README.md"
  "docs/project_reference.md"
  "docs/documentation_audit_runbook.md"
  "docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md"
  "scripts/dream7b-bpu-forward.sh"
  "scripts/dream7b-bpu-fine-forward.sh"
  "scripts/dream7b-bpu-fine-batch-forward.sh"
  "scripts/dream7b-bpu-batch-queue-runner.sh"
  "scripts/dream7b_bpu_batch_queue_runner.py"
  "scripts/dream7b-bpu-batch-queue-service.sh"
  "scripts/dream7b_bpu_batch_queue_service.py"
  "scripts/install_dream7b_bpu_queue_service.sh"
  "scripts/dream7b-bpu-text-forward.sh"
  "scripts/probes/dream7b_segmented_hbm_python_forward.py"
  "scripts/probes/dream7b_bpu_diffusion_loop_probe.sh"
  "scripts/probes/dream7b_bpu_fine_forward_repeat_probe.sh"
  "scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh"
  "scripts/probes/dream7b_bpu_fine_forward_window_batch_probe.sh"
  "scripts/probes/dream7b_bpu_fine_batch_forward_probe.sh"
  "scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh"
  "scripts/probes/dream7b_bpu_batch_capacity_probe.sh"
  "scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_runner_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_drain_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_control_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_service_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh"
  "scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh"
  "scripts/startup_link_check/link-check.config.json"
  "scripts/tool_allowlist.json"
)

required_readme_strings=(
  "docs/project_reference.md"
  "docs/documentation_audit_runbook.md"
  "scripts/probes/project_docs_consistency_probe.sh"
)

required_reference_strings=(
  "dream7b-bpu-forward"
  "dream7b-bpu-fine-forward"
  "dream7b-bpu-fine-batch-forward"
  "dream7b-bpu-batch-queue-runner"
  "dream7b-bpu-batch-queue-service"
  "dream7b-bpu-fine-batch-size-sweep-probe"
  "dream7b-bpu-fine-forward-long-repeat-probe"
  "dream7b-bpu-batch-capacity-probe"
  "dream7b-bpu-runtime-telemetry-probe"
  "dream7b-bpu-hbm-artifact-inventory-probe"
  "install-dream7b-bpu-queue-service"
  "dream7b-bpu-batch-queue-systemd-probe"
  "dream7b-bpu-batch-queue-systemd-soak-probe"
  "dream7b-bpu-batch-queue-systemd-batch-probe"
  "dream7b-bpu-batch-queue-systemd-drain-probe"
  "dream7b-bpu-batch-queue-systemd-canary-probe"
  "dream7b-bpu-batch-queue-systemd-telemetry-probe"
  "dream7b-bpu-batch-queue-retention-probe"
  "dream7b-bpu-deployment-acceptance-probe"
  "dream7b-bpu-batch-queue.service"
  "dream7b-bpu-text-forward"
  "dream7b-bpu-diffusion-loop-probe"
  "DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE"
  "DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_FINE_BATCH_SWEEP_COUNTS"
  "DREAM7B_BPU_FINE_BATCH_SWEEP_TIMEOUT_SEC"
  "DREAM7B_BPU_FINE_BATCH_SWEEP_TOP_K"
  "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT"
  "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO"
  "DREAM7B_BPU_BATCH_CAPACITY_COUNTS"
  "DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC"
  "DREAM7B_BPU_BATCH_CAPACITY_TOP_K"
  "DREAM7B_BPU_TELEMETRY_BATCH_COUNT"
  "DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS"
  "DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_TELEMETRY_TOP_K"
  "DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_FORWARD_SCRIPT"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_FINE_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_FINE_HBM_DIR"
  "DREAM7B_BPU_ARTIFACT_INVENTORY_VERIFY_MANIFEST"
  "DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT"
  "DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT"
  "DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE"
  "DREAM7B_BPU_QUEUE_DRAIN_ALL"
  "DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_DRAIN_TIMEOUT_SEC"
  "DREAM7B_BPU_SYSTEMD_DRAIN_POLL_INTERVAL_SEC"
  "DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC"
  "DREAM7B_BPU_SYSTEMD_CANARY_POLL_INTERVAL_SEC"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS"
  "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT"
  "DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS"
  "DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS"
  "DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES"
  "DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES"
  "DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST"
  "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY"
  "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS"
  "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS"
  "DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT"
  "--child-runtime-mode"
  "--window-execution-mode"
  "--tokens-batch-json"
  "--max-batch-size 16"
  "--drain-all"
  "--bpu-lock-path"
  "--bpu-lock-timeout-sec"
  "request_id"
  "tokens"
  "cancelled"
  "not_after_epoch_ms"
  "durable_state"
  "bpu_lock"
  "drain_all"
  "batch_run_count"
  "batch_counts"
  "amortized_wall_ms_per_forward"
  "amortized_load_ms_per_forward"
  "amortized_run_ms_per_forward"
  "load_share"
  "hrt_ucp_monitor"
  "bpu_loading_sample_count"
  "nonzero_bpu_loading_sample_count"
  "max_bpu_loading"
  "avg_bpu_loading"
  "hbm_artifact_inventory"
  "expected_artifact_count"
  "expected_base_count"
  "expected_fine_count"
  "nas_existing_count"
  "local_existing_count"
  "size_match_count"
  "manifest_expected_count"
  "manifest_verified_count"
  "required_manifest_expected_count"
  "policy_mode"
  "apply_supported"
  "archive_plan"
  "pending_stale_count"
  "processing_stale_count"
  "done_archive_candidate_count"
  "failed_archive_candidate_count"
  "deployment_acceptance_probe"
  "passed_check_count"
  "systemd_service"
  "batch_capacity"
  "systemd_batch"
  "systemd_drain"
  "systemd_canary"
  "systemd_telemetry"
  "long_repeat"
  "queue_retention"
  "/run/lock/dream7b_bpu_batch_queue_runner.lock"
  "pending"
  "processing"
  "done"
  "failed"
  "accepted_requests.jsonl"
  "deferred_requests.jsonl"
  "skipped_requests.jsonl"
  "results.jsonl"
  "scripts/startup_link_check/link-check.config.json"
  "scripts/tool_allowlist.json"
  "docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/fine_forward_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-174745/summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_repeat_20260603-180108/summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/long_repeat_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/long_repeat_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/repeat/dream7b_bpu_fine_forward_repeat_20260605-140733/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_1/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_2/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_4/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_8/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_capacity_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_8/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_12/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_16/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/runtime_telemetry_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/runtime_telemetry_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/forward/summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260603-221324/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/service_summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_20260604-131223/systemd_soak_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_001/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_002/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-133034/systemd_batch_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-133034/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-174953/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-174953/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-174953/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-180557/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-180557/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-233926/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-235205/systemd_batch_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-235205/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-235302/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-235302/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260605-131550/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260605-131550/systemd_batch_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260605-131550/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260605-131621/systemd_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260605-131621/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_canary_20260605-151715/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_001/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_002/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_003/queue_summary.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.json"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.json"
  "/etc/systemd/system/dream7b-bpu-batch-queue.service"
  "/mnt/nas/openclaw/queues/dream7b-bpu"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-183906/fine_forward_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md"
)

errors=()

for path in "${required_files[@]}"; do
  if [[ ! -e "$path" ]]; then
    errors+=("missing file: $path")
  fi
done

if [[ -f README.md ]]; then
  for text in "${required_readme_strings[@]}"; do
    if ! grep -F -- "$text" README.md >/dev/null; then
      errors+=("README.md missing string: $text")
    fi
  done
fi

if [[ -f docs/project_reference.md ]]; then
  for text in "${required_reference_strings[@]}"; do
    if ! grep -F -- "$text" docs/project_reference.md >/dev/null; then
      errors+=("docs/project_reference.md missing string: $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_segmented_hbm_python_forward.py ]]; then
  if ! grep -F -- "--child-runtime-mode" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
    errors+=("dream7b_segmented_hbm_python_forward.py missing --child-runtime-mode")
  fi
  if ! grep -F -- "--window-execution-mode" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
    errors+=("dream7b_segmented_hbm_python_forward.py missing --window-execution-mode")
  fi
  if ! grep -F -- "--tokens-batch-json" scripts/probes/dream7b_segmented_hbm_python_forward.py >/dev/null; then
    errors+=("dream7b_segmented_hbm_python_forward.py missing --tokens-batch-json")
  fi
fi

if [[ -f scripts/dream7b-bpu-fine-forward.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE" scripts/dream7b-bpu-fine-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-forward.sh missing DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE" scripts/dream7b-bpu-fine-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-forward.sh missing DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE")
  fi
fi

if [[ -f scripts/dream7b-bpu-fine-batch-forward.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE" scripts/dream7b-bpu-fine-batch-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-batch-forward.sh missing DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE")
  fi
  if ! grep -F -- "DREAM7B_BPU_TOKENS_BATCH_JSON" scripts/dream7b-bpu-fine-batch-forward.sh >/dev/null; then
    errors+=("dream7b-bpu-fine-batch-forward.sh missing DREAM7B_BPU_TOKENS_BATCH_JSON")
  fi
fi

if [[ -f scripts/dream7b-bpu-batch-queue-runner.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT" scripts/dream7b-bpu-batch-queue-runner.sh >/dev/null; then
    errors+=("dream7b-bpu-batch-queue-runner.sh missing DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT")
  fi
fi

if [[ -f scripts/dream7b-bpu-batch-queue-service.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT" scripts/dream7b-bpu-batch-queue-service.sh >/dev/null; then
    errors+=("dream7b-bpu-batch-queue-service.sh missing DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT")
  fi
fi

if [[ -f scripts/dream7b_bpu_batch_queue_runner.py ]]; then
  if ! grep -F -- "request_id" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing request_id")
  fi
  if ! grep -F -- "tokens" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing tokens")
  fi
  if ! grep -F -- "--drain-all" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing --drain-all")
  fi
  if ! grep -F -- "cancelled" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing cancelled")
  fi
  if ! grep -F -- "not_after_epoch_ms" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing not_after_epoch_ms")
  fi
  if ! grep -F -- "durable_state" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing durable_state")
  fi
  if ! grep -F -- "--bpu-lock-path" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing --bpu-lock-path")
  fi
  if ! grep -F -- "--bpu-lock-timeout-sec" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing --bpu-lock-timeout-sec")
  fi
  if ! grep -F -- "bpu_lock" scripts/dream7b_bpu_batch_queue_runner.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_runner.py missing bpu_lock")
  fi
fi

if [[ -f scripts/dream7b_bpu_batch_queue_service.py ]]; then
  if ! grep -F -- "pending" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing pending")
  fi
  if ! grep -F -- "processing" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing processing")
  fi
  if ! grep -F -- "done" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing done")
  fi
  if ! grep -F -- "failed" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing failed")
  fi
  if ! grep -F -- "service_summary.json" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing service_summary.json")
  fi
  if ! grep -F -- "build_summary_payload" scripts/dream7b_bpu_batch_queue_service.py >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_service.py missing build_summary_payload")
  fi
fi

if [[ -f scripts/install_dream7b_bpu_queue_service.sh ]]; then
  if ! grep -F -- "dream7b-bpu-batch-queue.service" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing dream7b-bpu-batch-queue.service")
  fi
  if ! grep -F -- "/mnt/nas/openclaw/queues/dream7b-bpu" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing /mnt/nas/openclaw/queues/dream7b-bpu")
  fi
  if ! grep -F -- "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing systemd output directory")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_DRAIN_ALL" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing DREAM7B_BPU_QUEUE_DRAIN_ALL")
  fi
  if ! grep -F -- 'DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE:-16' scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing default DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE:-16")
  fi
  if ! grep -F -- "--max-batch-size" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing --max-batch-size")
  fi
  if ! grep -F -- "--drain-all" scripts/install_dream7b_bpu_queue_service.sh >/dev/null; then
    errors+=("install_dream7b_bpu_queue_service.sh missing --drain-all")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh ]]; then
  if ! grep -F -- "dream7b-bpu-batch-queue.service" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing dream7b-bpu-batch-queue.service")
  fi
  if ! grep -F -- "service_status" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing service_status")
  fi
  if ! grep -F -- "service_enabled" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing service_enabled")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
  if ! grep -F -- "--drain-all" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing --drain-all")
  fi
  if ! grep -F -- "--max-batch-size 16" scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_probe.sh missing --max-batch-size 16")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_SOAK_JOB_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing DREAM7B_BPU_SYSTEMD_SOAK_JOB_COUNT")
  fi
  if ! grep -F -- "completed_job_count" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing completed_job_count")
  fi
  if ! grep -F -- "processed_request_count" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing processed_request_count")
  fi
  if ! grep -F -- "final_shape" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing final_shape")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_soak_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT:-16' scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing default DREAM7B_BPU_SYSTEMD_BATCH_REQUEST_COUNT:-16")
  fi
  if ! grep -F -- "--max-batch-size 16" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing --max-batch-size 16")
  fi
  if ! grep -F -- "batch_count" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing batch_count")
  fi
  if ! grep -F -- "accepted_count" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing accepted_count")
  fi
  if ! grep -F -- "deferred_count" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing deferred_count")
  fi
  if ! grep -F -- "amortized_wall_ms_per_processed_request" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing amortized_wall_ms_per_processed_request")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_batch_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT:-16' scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing default DREAM7B_BPU_SYSTEMD_DRAIN_REQUEST_COUNT:-16")
  fi
  if ! grep -F -- "expected_max_batch_size=16" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing expected_max_batch_size=16")
  fi
  if ! grep -F -- "expected_batch_counts" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing expected_batch_counts")
  fi
  if ! grep -F -- "batch_counts" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing batch_counts")
  fi
  if ! grep -F -- "batch_run_count" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing batch_run_count")
  fi
  if ! grep -F -- "drain_all" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing drain_all")
  fi
  if ! grep -F -- "--drain-all" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing --drain-all")
  fi
  if ! grep -F -- "--max-batch-size 16" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing --max-batch-size 16")
  fi
  if ! grep -F -- "/run/lock/dream7b_bpu_batch_queue_runner.lock" scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_drain_probe.sh missing /run/lock/dream7b_bpu_batch_queue_runner.lock")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_SWEEP_COUNTS" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing DREAM7B_BPU_FINE_BATCH_SWEEP_COUNTS")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_SWEEP_TIMEOUT_SEC" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing DREAM7B_BPU_FINE_BATCH_SWEEP_TIMEOUT_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_BATCH_SWEEP_TOP_K" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing DREAM7B_BPU_FINE_BATCH_SWEEP_TOP_K")
  fi
  if ! grep -F -- "amortized_wall_ms_per_forward" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing amortized_wall_ms_per_forward")
  fi
  if ! grep -F -- "amortized_load_ms_per_forward" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing amortized_load_ms_per_forward")
  fi
  if ! grep -F -- "amortized_run_ms_per_forward" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing amortized_run_ms_per_forward")
  fi
  if ! grep -F -- "load_share" scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_batch_size_sweep_probe.sh missing load_share")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_capacity_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_BATCH_CAPACITY_COUNTS" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing DREAM7B_BPU_BATCH_CAPACITY_COUNTS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_BATCH_CAPACITY_COUNTS:-8 12 16' scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing default DREAM7B_BPU_BATCH_CAPACITY_COUNTS:-8 12 16")
  fi
  if ! grep -F -- "DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing DREAM7B_BPU_BATCH_CAPACITY_TIMEOUT_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_BATCH_CAPACITY_TOP_K" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing DREAM7B_BPU_BATCH_CAPACITY_TOP_K")
  fi
  if ! grep -F -- "max_passing_count" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing max_passing_count")
  fi
  if ! grep -F -- "amortized_wall_ms_per_forward" scripts/probes/dream7b_bpu_batch_capacity_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_capacity_probe.sh missing amortized_wall_ms_per_forward")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_BATCH_COUNT" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_BATCH_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_TELEMETRY_BATCH_COUNT:-16' scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing default DREAM7B_BPU_TELEMETRY_BATCH_COUNT:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_MONITOR_DELAY_MS")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_MONITOR_SAMPLE_COUNT")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_TOP_K" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_TOP_K")
  fi
  if ! grep -F -- "DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing DREAM7B_BPU_TELEMETRY_TIMEOUT_SEC")
  fi
  if ! grep -F -- "hrt_ucp_monitor" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing hrt_ucp_monitor")
  fi
  if ! grep -F -- "bpu_loading_sample_count" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing bpu_loading_sample_count")
  fi
  if ! grep -F -- "max_bpu_loading" scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_runtime_telemetry_probe.sh missing max_bpu_loading")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh ]]; then
  for text in \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_FORWARD_SCRIPT" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_NAS_FINE_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_LOCAL_FINE_HBM_DIR" \
    "DREAM7B_BPU_ARTIFACT_INVENTORY_VERIFY_MANIFEST" \
    "/mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py" \
    "/mnt/nas/openclaw/models/dream7b-hbm/segments6" \
    "/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/segments6" \
    "/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16" \
    "SEGMENTS6" \
    "FINE_ADJACENT_SEGMENTS" \
    "hbm_artifact_inventory_probe.json" \
    "hbm_artifact_inventory_probe.md" \
    "ok_dream7b_bpu_hbm_artifact_inventory_probe" \
    "expected_artifact_count" \
    "expected_base_count" \
    "expected_fine_count" \
    "nas_existing_count" \
    "local_existing_count" \
    "size_match_count" \
    "manifest_expected_count" \
    "manifest_verified_count" \
    "required_manifest_expected_count"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_hbm_artifact_inventory_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT:-6' scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing default DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_COUNT:-6")
  fi
  if ! grep -F -- "DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing DREAM7B_BPU_FINE_FORWARD_LONG_REPEAT_MAX_WALL_SPREAD_RATIO")
  fi
  if ! grep -F -- "dream7b-bpu-fine-forward-repeat-probe" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing dream7b-bpu-fine-forward-repeat-probe")
  fi
  if ! grep -F -- "failure_count" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing failure_count")
  fi
  if ! grep -F -- "wall_spread_ratio" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing wall_spread_ratio")
  fi
  if ! grep -F -- "repeat_summary_json" scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_fine_forward_long_repeat_probe.sh missing repeat_summary_json")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT:-3' scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing default DREAM7B_BPU_SYSTEMD_TELEMETRY_JOB_COUNT:-3")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT:-16' scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing default DREAM7B_BPU_SYSTEMD_TELEMETRY_REQUEST_COUNT:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_TIMEOUT_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_POLL_INTERVAL_SEC")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_DELAY_MS")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing DREAM7B_BPU_SYSTEMD_TELEMETRY_MONITOR_SAMPLE_COUNT")
  fi
  if ! grep -F -- "hrt_ucp_monitor" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing hrt_ucp_monitor")
  fi
  if ! grep -F -- "batch_counts" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing batch_counts")
  fi
  if ! grep -F -- "processed_request_count" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing processed_request_count")
  fi
  if ! grep -F -- "max_bpu_loading" scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_telemetry_probe.sh missing max_bpu_loading")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS:-14' scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing default DREAM7B_BPU_QUEUE_RETENTION_DONE_DAYS:-14")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS:-30' scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing default DREAM7B_BPU_QUEUE_RETENTION_FAILED_DAYS:-30")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_PENDING_STALE_MINUTES")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_PROCESSING_STALE_MINUTES")
  fi
  if ! grep -F -- "DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing DREAM7B_BPU_QUEUE_RETENTION_MAX_LIST")
  fi
  if ! grep -F -- "policy_mode" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing policy_mode")
  fi
  if ! grep -F -- "report_only" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing report_only")
  fi
  if ! grep -F -- "apply_supported" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing apply_supported")
  fi
  if ! grep -F -- "archive_plan" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing archive_plan")
  fi
  if ! grep -F -- "pending_stale_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing pending_stale_count")
  fi
  if ! grep -F -- "processing_stale_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing processing_stale_count")
  fi
  if ! grep -F -- "done_archive_candidate_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing done_archive_candidate_count")
  fi
  if ! grep -F -- "failed_archive_candidate_count" scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_retention_probe.sh missing failed_archive_candidate_count")
  fi
fi

if [[ -f scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT:-1' scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing default DREAM7B_BPU_SYSTEMD_CANARY_REQUEST_COUNT:-1")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC")
  fi
  if ! grep -F -- 'DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC:-180' scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing default DREAM7B_BPU_SYSTEMD_CANARY_TIMEOUT_SEC:-180")
  fi
  if ! grep -F -- "DREAM7B_BPU_SYSTEMD_CANARY_POLL_INTERVAL_SEC" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing DREAM7B_BPU_SYSTEMD_CANARY_POLL_INTERVAL_SEC")
  fi
  for text in \
    "systemd_canary_probe.json" \
    "systemd_canary_probe.md" \
    "ok_dream7b_bpu_batch_queue_systemd_canary_probe" \
    "dream7b-bpu-batch-queue.service" \
    "/mnt/nas/openclaw/queues/dream7b-bpu" \
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd" \
    "/run/lock/dream7b_bpu_batch_queue_runner.lock" \
    "--max-batch-size 16" \
    "--drain-all" \
    "final_shapes" \
    "bpu_lock_path" \
    "pair_window_batch" \
    "window-batch"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_batch_queue_systemd_canary_probe.sh missing $text")
    fi
  done
fi

if [[ -f scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh ]]; then
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY:-16' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_BATCH_CAPACITY:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS:-16' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_BATCH_REQUESTS:-16")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS:-48' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_SYSTEMD_TELEMETRY_REQUESTS:-48")
  fi
  if ! grep -F -- "DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT")
  fi
  if ! grep -F -- 'DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT:-6' scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
    errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing default DREAM7B_BPU_ACCEPTANCE_MIN_LONG_REPEAT_COUNT:-6")
  fi
  for text in \
    "dream7b_bpu_batch_queue_systemd_*/systemd_probe.json" \
    "dream7b_bpu_batch_capacity_*/batch_capacity_probe.json" \
    "dream7b_bpu_hbm_artifact_inventory_*/hbm_artifact_inventory_probe.json" \
    "dream7b_bpu_batch_queue_systemd_batch_*/systemd_batch_probe.json" \
    "dream7b_bpu_batch_queue_systemd_drain_*/systemd_drain_probe.json" \
    "dream7b_bpu_batch_queue_systemd_canary_*/systemd_canary_probe.json" \
    "dream7b_bpu_batch_queue_systemd_telemetry_*/systemd_telemetry_probe.json" \
    "dream7b_bpu_fine_forward_long_repeat_*/long_repeat_probe.json" \
    "dream7b_bpu_batch_queue_retention_*/queue_retention_probe.json" \
    "systemd_service" \
    "batch_capacity" \
    "hbm_artifact_inventory" \
    "systemd_batch" \
    "systemd_drain" \
    "systemd_canary" \
    "systemd_telemetry" \
    "long_repeat" \
    "queue_retention" \
    "deployment_acceptance_probe.json" \
    "deployment_acceptance_probe.md" \
    "ok_dream7b_bpu_deployment_acceptance_probe" \
    "passed_check_count" \
    "check_count" \
    "max_bpu_loading"; do
    if ! grep -F -- "$text" scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh >/dev/null; then
      errors+=("dream7b_bpu_deployment_acceptance_probe.sh missing $text")
    fi
  done
fi

summary_json="$report_root/summary.json"
summary_md="$report_root/summary.md"

python3 - "$summary_json" "$summary_md" "${errors[@]}" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

summary_json = Path(sys.argv[1])
summary_md = Path(sys.argv[2])
errors = list(sys.argv[3:])
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_project_docs_consistency_probe" if not errors else "failed_project_docs_consistency_probe",
    "errors": errors,
}
summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Project Documentation Consistency Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    "",
    "## Errors",
    "",
]
if errors:
    lines.extend(f"- {item}" for item in errors)
else:
    lines.append("- none")
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
if errors:
    raise SystemExit("; ".join(errors))
PY
