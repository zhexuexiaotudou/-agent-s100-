#!/usr/bin/env bash
set -euo pipefail

report_root="${1:-${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_REPORT_ROOT:-/mnt/nas/openclaw/reports/models}}"
repo_dir="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_REPO_DIR:-$(pwd)}"
runtime_dir="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_RUNTIME_DIR:-/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default}"
service_name="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_SERVICE_NAME:-dream7b-bpu-batch-queue.service}"
candidate_service_name="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_CANDIDATE_SERVICE_NAME:-dream7b-bpu-segment-major-load-once-candidate-24job-b256.service}"
queue_dir="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_QUEUE_DIR:-/mnt/nas/openclaw/queues/dream7b-bpu}"
output_dir="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_OUTPUT_DIR:-/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd}"
bpu_lock_path="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_BPU_LOCK_PATH:-/run/lock/dream7b_bpu_batch_queue_runner.lock}"
single_job_flush_timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_SINGLE_JOB_FLUSH_TIMEOUT_SEC:-30}"
timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_TIMEOUT_SEC:-3000}"
poll_interval_sec="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_POLL_INTERVAL_SEC:-1}"
top_k="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_TOP_K:-3}"
min_job_count="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_MIN_JOB_COUNT:-2}"
max_job_count="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_MAX_JOB_COUNT:-24}"
max_batch_size="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_MAX_BATCH_SIZE:-256}"
smoke_timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_SMOKE_TIMEOUT_SEC:-1200}"
raw_final="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_RAW_FINAL:-0}"
skip_explicit_gc="${DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_SKIP_EXPLICIT_GC:-0}"

case "$report_root" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_root" >&2
    exit 2
    ;;
esac
case "$runtime_dir" in
  /mnt/nas/openclaw/runtimes/*|/tmp/*|/root/.openclaw/workspace/runtimes/*) ;;
  *)
    echo "Refusing runtime path outside approved runtime directories: $runtime_dir" >&2
    exit 2
    ;;
esac
case "$queue_dir" in
  /mnt/nas/openclaw/queues|/mnt/nas/openclaw/queues/*|/tmp/*|/root/.openclaw/workspace/queues/*) ;;
  *)
    echo "Refusing queue path outside approved queue directories: $queue_dir" >&2
    exit 2
    ;;
esac
case "$output_dir" in
  /mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/tmp/*|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $output_dir" >&2
    exit 2
    ;;
esac
if [[ "$(id -u)" != "0" ]]; then
  echo "This probe must run as root because it writes systemd unit files." >&2
  exit 4
fi
if [[ ! -d "$repo_dir/scripts" ]]; then
  echo "Missing repo scripts directory: $repo_dir/scripts" >&2
  exit 2
fi
if [[ "$raw_final" != "0" && "$raw_final" != "1" ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_RAW_FINAL must be 0 or 1." >&2
  exit 2
fi
if [[ "$skip_explicit_gc" != "0" && "$skip_explicit_gc" != "1" ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_SKIP_EXPLICIT_GC must be 0 or 1." >&2
  exit 2
fi
if ! [[ "$min_job_count" =~ ^[1-9][0-9]*$ ]] || (( min_job_count < 2 || min_job_count > 24 )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_MIN_JOB_COUNT must be 2..24." >&2
  exit 2
fi
if ! [[ "$max_job_count" =~ ^[1-9][0-9]*$ ]] || (( max_job_count < min_job_count || max_job_count > 24 )); then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_PROMOTION_MAX_JOB_COUNT must be min_job_count..24." >&2
  exit 2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_dir="$report_root/dream7b_bpu_segment_major_default_promotion_$stamp"
mkdir -p "$run_dir" "$output_dir" "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed"

service_path="/etc/systemd/system/$service_name"
if [[ ! -f "$service_path" ]]; then
  echo "Missing default service unit: $service_path" >&2
  exit 2
fi

pending_count="$(find "$queue_dir/pending" -maxdepth 1 -type f -name '*.jsonl' | wc -l)"
if [[ "$pending_count" != "0" ]]; then
  echo "Refusing promotion smoke while default queue has pending jobs: $pending_count" >&2
  exit 3
fi

original_unit="$run_dir/original_${service_name}"
promoted_unit="$run_dir/promoted_${service_name}"
cp "$service_path" "$original_unit"
cp "$service_path" "/etc/systemd/system/${service_name}.pre_segment_major_promotion_${stamp}.bak"

if [[ -d "$runtime_dir" ]]; then
  archived_runtime="${runtime_dir}.pre_${stamp}"
  mv "$runtime_dir" "$archived_runtime"
else
  archived_runtime=""
fi
mkdir -p "$runtime_dir"
cp -a "$repo_dir/scripts" "$runtime_dir/"

runner_cmd="/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python $runtime_dir/scripts/dream7b_bpu_segment_major_load_once_queue_runner.py"
exec_start="/usr/bin/python3 $runtime_dir/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py $queue_dir $output_dir --runner-cmd '$runner_cmd' --forward-probe-cmd 'segment-major-load-once' --expected-runner-verdict ok_dream7b_bpu_segment_major_load_once_queue_runner --summary-stem segment_major_queue --min-job-count $min_job_count --max-job-count $max_job_count --max-job-count-limit 24 --max-batch-size $max_batch_size --max-batch-size-limit 256 --top-k $top_k --timeout-sec $timeout_sec --bpu-lock-path $bpu_lock_path --poll-interval-sec $poll_interval_sec --single-job-flush-timeout-sec $single_job_flush_timeout_sec"

cat > "$promoted_unit" <<EOF
[Unit]
Description=Dream 7B BPU batch queue service (segment-major load-once 24x256 default)
Documentation=file://$runtime_dir/scripts/probes/dream7b_bpu_segment_major_default_promotion_probe.sh
After=network-online.target
Wants=network-online.target
RequiresMountsFor=/mnt/nas/openclaw

[Service]
Type=simple
WorkingDirectory=$runtime_dir
Environment=DREAM7B_BPU_QUEUE_DIR=$queue_dir
Environment=DREAM7B_BPU_QUEUE_OUTPUT_DIR=$output_dir
Environment=DREAM7B_BPU_SEGMENT_MAJOR_DEFAULT_RUNTIME_DIR=$runtime_dir
Environment=DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL=$raw_final
Environment=DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC=$skip_explicit_gc
ExecStart=$exec_start
Restart=always
RestartSec=5
Nice=5
IOSchedulingClass=best-effort
IOSchedulingPriority=6

[Install]
WantedBy=multi-user.target
EOF

install_unit() {
  local source_unit="$1"
  cp "$source_unit" "$service_path"
  systemctl daemon-reload
  systemctl enable "$service_name" >/dev/null
  systemctl restart "$service_name"
}

service_active() {
  [[ "$(systemctl is-active "$1" 2>/dev/null || true)" == "active" ]]
}

service_enabled() {
  [[ "$(systemctl is-enabled "$1" 2>/dev/null || true)" == "enabled" ]]
}

wait_for_smoke() {
  local request_id="$1"
  local started
  started="$(date +%s)"
  while true; do
    if grep -R "\"request_id\": \"$request_id\"\\|\"request_id\":\"$request_id\"" "$queue_dir/done" >/dev/null 2>&1; then
      return 0
    fi
    if grep -R "\"request_id\": \"$request_id\"\\|\"request_id\":\"$request_id\"" "$queue_dir/failed" >/dev/null 2>&1; then
      return 5
    fi
    if (( $(date +%s) - started >= smoke_timeout_sec )); then
      return 6
    fi
    sleep 1
  done
}

errors=()
install_unit "$promoted_unit"
promoted_exec_start="$(systemctl show "$service_name" -p ExecStart --value)"
if ! service_active "$service_name"; then errors+=("promoted_default_service_not_active"); fi
if ! service_enabled "$service_name"; then errors+=("promoted_default_service_not_enabled"); fi
if [[ "$promoted_exec_start" != *"dream7b_bpu_segment_major_load_once_queue_runner.py"* ]]; then errors+=("promoted_execstart_missing_segment_major_runner"); fi
if [[ "$promoted_exec_start" != *"$queue_dir"* ]]; then errors+=("promoted_execstart_missing_default_queue"); fi
if [[ "$promoted_exec_start" != *"--min-job-count $min_job_count"* ]]; then errors+=("promoted_execstart_missing_min_job_count"); fi
if [[ "$promoted_exec_start" != *"--max-batch-size 256"* ]]; then errors+=("promoted_execstart_missing_256_batch"); fi
promoted_environment="$(systemctl show "$service_name" -p Environment --value)"
if [[ "$raw_final" == "1" && "$promoted_environment" != *"DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL=1"* ]]; then errors+=("promoted_environment_missing_raw_final"); fi
if [[ "$skip_explicit_gc" == "1" && "$promoted_environment" != *"DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC=1"* ]]; then errors+=("promoted_environment_missing_skip_explicit_gc"); fi

smoke_request_id="segment-major-default-smoke-$stamp"
python3 - "$queue_dir/pending" "$stamp" "$smoke_request_id" "$min_job_count" <<'PY'
import json
import sys
from pathlib import Path

pending_dir = Path(sys.argv[1])
stamp = sys.argv[2]
request_id = sys.argv[3]
job_count = int(sys.argv[4])
for job_index in range(job_count):
    rows = []
    for request_index in range(2):
        base = 2000 + job_index * 100 + request_index * 16
        rows.append(
            {
                "request_id": request_id if job_index == 0 and request_index == 0 else f"{request_id}-{job_index + 1}-{request_index + 1}",
                "tokens": [base + offset for offset in range(16)],
            }
        )
    tmp = pending_dir / f"segment_major_default_smoke_{stamp}_{job_index + 1:03d}.jsonl.tmp"
    final = pending_dir / f"segment_major_default_smoke_{stamp}_{job_index + 1:03d}.jsonl"
    tmp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    tmp.replace(final)
PY
if ! wait_for_smoke "$smoke_request_id"; then
  errors+=("promoted_default_smoke_failed_or_timed_out")
fi

install_unit "$original_unit"
rollback_exec_start="$(systemctl show "$service_name" -p ExecStart --value)"
rollback_verified=true
if ! service_active "$service_name"; then rollback_verified=false; errors+=("rollback_default_service_not_active"); fi
if ! service_enabled "$service_name"; then rollback_verified=false; errors+=("rollback_default_service_not_enabled"); fi
if ! cmp -s "$service_path" "$original_unit"; then rollback_verified=false; errors+=("rollback_unit_does_not_match_original_backup"); fi

install_unit "$promoted_unit"
final_exec_start="$(systemctl show "$service_name" -p ExecStart --value)"
final_environment="$(systemctl show "$service_name" -p Environment --value)"
default_service_replaced=true
if [[ "$final_exec_start" != *"dream7b_bpu_segment_major_load_once_queue_runner.py"* ]]; then default_service_replaced=false; errors+=("final_default_execstart_missing_segment_major_runner"); fi
if [[ "$final_exec_start" != *"$queue_dir"* ]]; then default_service_replaced=false; errors+=("final_default_execstart_missing_default_queue"); fi
if [[ "$final_exec_start" != *"--min-job-count $min_job_count"* ]]; then default_service_replaced=false; errors+=("final_default_execstart_missing_min_job_count"); fi
if [[ "$final_exec_start" != *"--max-batch-size 256"* ]]; then default_service_replaced=false; errors+=("final_default_execstart_missing_256_batch"); fi
if [[ "$raw_final" == "1" && "$final_environment" != *"DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL=1"* ]]; then default_service_replaced=false; errors+=("final_default_environment_missing_raw_final"); fi
if [[ "$skip_explicit_gc" == "1" && "$final_environment" != *"DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC=1"* ]]; then default_service_replaced=false; errors+=("final_default_environment_missing_skip_explicit_gc"); fi
if ! service_active "$service_name"; then default_service_replaced=false; errors+=("final_default_service_not_active"); fi
if ! service_enabled "$service_name"; then default_service_replaced=false; errors+=("final_default_service_not_enabled"); fi

candidate_status="$(systemctl is-active "$candidate_service_name" 2>/dev/null || true)"
candidate_enabled="$(systemctl is-enabled "$candidate_service_name" 2>/dev/null || true)"

python3 - "$run_dir" "$service_name" "$candidate_service_name" "$queue_dir" "$output_dir" "$runtime_dir" "$original_unit" "$promoted_unit" "$archived_runtime" "$smoke_request_id" "$promoted_exec_start" "$rollback_exec_start" "$final_exec_start" "$promoted_environment" "$final_environment" "$raw_final" "$skip_explicit_gc" "$top_k" "$min_job_count" "$rollback_verified" "$default_service_replaced" "$candidate_status" "$candidate_enabled" "${errors[@]}" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

(
    run_dir,
    service_name,
    candidate_service_name,
    queue_dir,
    output_dir,
    runtime_dir,
    original_unit,
    promoted_unit,
    archived_runtime,
    smoke_request_id,
    promoted_exec_start,
    rollback_exec_start,
    final_exec_start,
    promoted_environment,
    final_environment,
    raw_final,
    skip_explicit_gc,
    top_k,
    min_job_count,
    rollback_verified,
    default_service_replaced,
    candidate_status,
    candidate_enabled,
    *errors,
) = sys.argv[1:]
payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "verdict": "ok_dream7b_bpu_segment_major_default_promotion_probe" if not errors else "failed_dream7b_bpu_segment_major_default_promotion_probe",
    "run_dir": run_dir,
    "service_name": service_name,
    "candidate_service_name": candidate_service_name,
    "queue_dir": queue_dir,
    "output_dir": output_dir,
    "runtime_dir": runtime_dir,
    "original_unit_backup": original_unit,
    "promoted_unit": promoted_unit,
    "archived_runtime": archived_runtime,
    "smoke_request_id": smoke_request_id,
    "promoted_exec_start": promoted_exec_start,
    "rollback_exec_start": rollback_exec_start,
    "final_exec_start": final_exec_start,
    "promoted_environment": promoted_environment,
    "final_environment": final_environment,
    "raw_final": raw_final == "1",
    "skip_explicit_gc": skip_explicit_gc == "1",
    "top_k": int(top_k),
    "min_job_count": int(min_job_count),
    "rollback_verified": rollback_verified == "true",
    "default_service_replaced": default_service_replaced == "true",
    "candidate_status": candidate_status,
    "candidate_enabled": candidate_enabled,
    "rollback_commands": [
        f"sudo cp {original_unit} /etc/systemd/system/{service_name}",
        "sudo systemctl daemon-reload",
        f"sudo systemctl enable {service_name}",
        f"sudo systemctl restart {service_name}",
        f"systemctl is-active {service_name}",
        f"systemctl is-enabled {service_name}",
    ],
    "repromote_commands": [
        f"sudo cp {promoted_unit} /etc/systemd/system/{service_name}",
        "sudo systemctl daemon-reload",
        f"sudo systemctl enable {service_name}",
        f"sudo systemctl restart {service_name}",
    ],
    "errors": errors,
}
path = Path(run_dir)
(path / "segment_major_default_promotion_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Dream 7B Segment-Major Default Promotion Probe",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- verdict: {payload['verdict']}",
    f"- default_service_replaced: {payload['default_service_replaced']}",
    f"- rollback_verified: {payload['rollback_verified']}",
    f"- raw_final: {payload['raw_final']}",
    f"- skip_explicit_gc: {payload['skip_explicit_gc']}",
    f"- top_k: {payload['top_k']}",
    f"- smoke_request_id: {payload['smoke_request_id']}",
    f"- runtime_dir: {payload['runtime_dir']}",
    f"- queue_dir: {payload['queue_dir']}",
    "",
    "## Rollback Commands",
    "",
]
lines.extend(f"- `{item}`" for item in payload["rollback_commands"])
lines.extend(["", "## Repromote Commands", ""])
lines.extend(f"- `{item}`" for item in payload["repromote_commands"])
lines.extend(["", "## Errors", ""])
lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
(path / "segment_major_default_promotion_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(path / "segment_major_default_promotion_probe.md")
if errors:
    raise SystemExit("; ".join(errors))
PY
