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
  "scripts/probes/dream7b_bpu_fine_forward_window_batch_probe.sh"
  "scripts/probes/dream7b_bpu_fine_batch_forward_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_runner_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_drain_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_control_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_service_probe.sh"
  "scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh"
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
  "install-dream7b-bpu-queue-service"
  "dream7b-bpu-batch-queue-systemd-probe"
  "dream7b-bpu-batch-queue.service"
  "dream7b-bpu-text-forward"
  "dream7b-bpu-diffusion-loop-probe"
  "DREAM7B_BPU_FINE_CHILD_RUNTIME_MODE"
  "DREAM7B_BPU_FINE_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_FINE_BATCH_WINDOW_EXECUTION_MODE"
  "DREAM7B_BPU_BATCH_QUEUE_RUNNER_SCRIPT"
  "DREAM7B_BPU_BATCH_QUEUE_SERVICE_SCRIPT"
  "--child-runtime-mode"
  "--window-execution-mode"
  "--tokens-batch-json"
  "--drain-all"
  "--bpu-lock-path"
  "--bpu-lock-timeout-sec"
  "request_id"
  "tokens"
  "cancelled"
  "not_after_epoch_ms"
  "durable_state"
  "bpu_lock"
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
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260603-221324/systemd_probe.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/service_summary.md"
  "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json"
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
