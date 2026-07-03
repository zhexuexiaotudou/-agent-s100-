#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install_dream7b_bpu_segment_major_load_once_candidate_service.sh plan [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_segment_major_load_once_candidate_service.sh install [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_segment_major_load_once_candidate_service.sh status
  scripts/install_dream7b_bpu_segment_major_load_once_candidate_service.sh uninstall

Installs an isolated Dream 7B segment-major/load-once candidate queue service.
It does not replace the default Dream 7B service or the selected-pair 50pct service.

Environment:
  DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_NAME          Default: dream7b-bpu-segment-major-load-once-candidate.service.
  DREAM7B_BPU_SEGMENT_MAJOR_REPO_DIR              Default: /mnt/nas/openclaw/tmp/cross_job_queue_repo.
  DREAM7B_BPU_SEGMENT_MAJOR_MIN_JOB_COUNT         Default: 2.
  DREAM7B_BPU_SEGMENT_MAJOR_MAX_JOB_COUNT         Default: 12.
  DREAM7B_BPU_SEGMENT_MAJOR_MAX_JOB_COUNT_LIMIT   Default: 24.
  DREAM7B_BPU_SEGMENT_MAJOR_MAX_BATCH_SIZE        Default: 192.
  DREAM7B_BPU_SEGMENT_MAJOR_MAX_BATCH_SIZE_LIMIT  Default: 256.
  DREAM7B_BPU_SEGMENT_MAJOR_TOP_K                 Default: 3.
  DREAM7B_BPU_SEGMENT_MAJOR_TIMEOUT_SEC           Default: 1800.
  DREAM7B_BPU_SEGMENT_MAJOR_BPU_LOCK_PATH         Default: /run/lock/dream7b_bpu_batch_queue_runner.lock.
  DREAM7B_BPU_SEGMENT_MAJOR_POLL_INTERVAL_SEC     Default: 1.
  DREAM7B_BPU_SEGMENT_MAJOR_SINGLE_JOB_FLUSH_TIMEOUT_SEC
                                                    Default: 30.
  DREAM7B_BPU_SEGMENT_MAJOR_RUNTIME_OWNER         Default: ${SUDO_USER:-current user}.
  DREAM7B_BPU_SEGMENT_MAJOR_HBM_PYTHON            Default: /mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python.
  DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL             Default: 0. Set 1 to skip final full-logits float32 materialization.
EOF
}

action="${1:-}"
if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
  usage
  exit 0
fi
shift || true

service_name="${DREAM7B_BPU_SEGMENT_MAJOR_SERVICE_NAME:-dream7b-bpu-segment-major-load-once-candidate.service}"
service_path="/etc/systemd/system/$service_name"
repo_dir="${DREAM7B_BPU_SEGMENT_MAJOR_REPO_DIR:-/mnt/nas/openclaw/tmp/cross_job_queue_repo}"
default_queue_dir="/mnt/nas/openclaw/queues/dream7b-bpu-segment-major-load-once-candidate"
default_output_dir="/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_load_once_candidate_service"
queue_dir="${1:-$default_queue_dir}"
output_dir="${2:-$default_output_dir}"
min_job_count="${DREAM7B_BPU_SEGMENT_MAJOR_MIN_JOB_COUNT:-2}"
max_job_count="${DREAM7B_BPU_SEGMENT_MAJOR_MAX_JOB_COUNT:-12}"
max_job_count_limit="${DREAM7B_BPU_SEGMENT_MAJOR_MAX_JOB_COUNT_LIMIT:-24}"
max_batch_size="${DREAM7B_BPU_SEGMENT_MAJOR_MAX_BATCH_SIZE:-192}"
max_batch_size_limit="${DREAM7B_BPU_SEGMENT_MAJOR_MAX_BATCH_SIZE_LIMIT:-256}"
top_k="${DREAM7B_BPU_SEGMENT_MAJOR_TOP_K:-3}"
timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_TIMEOUT_SEC:-1800}"
bpu_lock_path="${DREAM7B_BPU_SEGMENT_MAJOR_BPU_LOCK_PATH:-/run/lock/dream7b_bpu_batch_queue_runner.lock}"
poll_interval_sec="${DREAM7B_BPU_SEGMENT_MAJOR_POLL_INTERVAL_SEC:-1}"
single_job_flush_timeout_sec="${DREAM7B_BPU_SEGMENT_MAJOR_SINGLE_JOB_FLUSH_TIMEOUT_SEC:-30}"
runtime_owner="${DREAM7B_BPU_SEGMENT_MAJOR_RUNTIME_OWNER:-${SUDO_USER:-$(id -un)}}"
hbm_python="${DREAM7B_BPU_SEGMENT_MAJOR_HBM_PYTHON:-/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python}"
raw_final="${DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL:-0}"
skip_explicit_gc="${DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC:-0}"

validate_service_name() {
  case "$1" in
    dream7b-bpu-segment-major-load-once-candidate.service|dream7b-bpu-segment-major-load-once-candidate-*.service) ;;
    *)
      echo "Refusing unexpected segment-major candidate service name: $1" >&2
      exit 2
      ;;
  esac
}

validate_queue_dir() {
  case "$1" in
    /tmp/*|/mnt/nas/openclaw/queues|/mnt/nas/openclaw/queues/*|/root/.openclaw/workspace/queues|/root/.openclaw/workspace/queues/*) ;;
    *)
      echo "Refusing queue path outside approved queue directories: $1" >&2
      exit 2
      ;;
  esac
}

validate_output_dir() {
  case "$1" in
    /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
    *)
      echo "Refusing output path outside approved report directories: $1" >&2
      exit 2
      ;;
  esac
}

validate_repo_dir() {
  case "$1" in
    /mnt/nas/openclaw|/mnt/nas/openclaw/tmp/*|/root/.openclaw/workspace|/tmp/*) ;;
    *)
      echo "Refusing repo path outside approved workspace directories: $1" >&2
      exit 2
      ;;
  esac
  if [[ ! -d "$1" ]]; then
    echo "Runtime workspace does not exist: $1" >&2
    exit 2
  fi
}

validate_integer() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "$name must be a positive integer." >&2
    exit 2
  fi
}

require_root_for_mutation() {
  if [[ "$(id -u)" != "0" ]]; then
    echo "This action must run as root because it writes systemd unit files." >&2
    exit 4
  fi
}

validate_service_name "$service_name"
validate_queue_dir "$queue_dir"
validate_output_dir "$output_dir"
validate_repo_dir "$repo_dir"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_MIN_JOB_COUNT" "$min_job_count"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_MAX_JOB_COUNT" "$max_job_count"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_MAX_JOB_COUNT_LIMIT" "$max_job_count_limit"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_MAX_BATCH_SIZE" "$max_batch_size"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_MAX_BATCH_SIZE_LIMIT" "$max_batch_size_limit"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_TOP_K" "$top_k"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_TIMEOUT_SEC" "$timeout_sec"
validate_integer "DREAM7B_BPU_SEGMENT_MAJOR_SINGLE_JOB_FLUSH_TIMEOUT_SEC" "$single_job_flush_timeout_sec"
if [[ "$raw_final" != "0" && "$raw_final" != "1" ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL must be 0 or 1." >&2
  exit 2
fi
if [[ "$skip_explicit_gc" != "0" && "$skip_explicit_gc" != "1" ]]; then
  echo "DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC must be 0 or 1." >&2
  exit 2
fi

if [[ ! -x "$hbm_python" ]]; then
  echo "HBM runtime Python is not executable: $hbm_python" >&2
  exit 2
fi

runner_cmd="$hbm_python $repo_dir/scripts/dream7b_bpu_segment_major_load_once_queue_runner.py"
exec_start="/usr/bin/python3 $repo_dir/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py $queue_dir $output_dir --runner-cmd '$runner_cmd' --forward-probe-cmd 'segment-major-load-once' --expected-runner-verdict ok_dream7b_bpu_segment_major_load_once_queue_runner --summary-stem segment_major_queue --min-job-count $min_job_count --max-job-count $max_job_count --max-job-count-limit $max_job_count_limit --max-batch-size $max_batch_size --max-batch-size-limit $max_batch_size_limit --top-k $top_k --timeout-sec $timeout_sec --bpu-lock-path $bpu_lock_path --poll-interval-sec $poll_interval_sec --single-job-flush-timeout-sec $single_job_flush_timeout_sec"

show_plan() {
  cat <<EOF
Dream 7B segment-major/load-once candidate service plan

service: $service_name
service_path: $service_path
queue_dir: $queue_dir
output_dir: $output_dir
repo_dir: $repo_dir
runner_cmd: $runner_cmd
min_job_count: $min_job_count
max_job_count: $max_job_count
max_job_count_limit: $max_job_count_limit
max_batch_size: $max_batch_size
max_batch_size_limit: $max_batch_size_limit
top_k: $top_k
timeout_sec: $timeout_sec
bpu_lock_path: $bpu_lock_path
poll_interval_sec: $poll_interval_sec
single_job_flush_timeout_sec: $single_job_flush_timeout_sec
runtime_owner: $runtime_owner
raw_final: $raw_final
skip_explicit_gc: $skip_explicit_gc
default_service_replaced: false
rollback_command: sudo systemctl disable --now $service_name
EOF
}

case "$action" in
  plan)
    show_plan
    ;;
  install)
    require_root_for_mutation
    mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed" "$output_dir"
    if id "$runtime_owner" >/dev/null 2>&1; then
      chown -R "$runtime_owner:$runtime_owner" "$queue_dir" "$output_dir"
    fi
    cat > "$service_path" <<EOF
[Unit]
Description=Dream 7B BPU segment-major load-once candidate queue service
Documentation=file://$repo_dir/scripts/install_dream7b_bpu_segment_major_load_once_candidate_service.sh
After=network-online.target
Wants=network-online.target
RequiresMountsFor=/mnt/nas/openclaw

[Service]
Type=simple
WorkingDirectory=$repo_dir
Environment=DREAM7B_BPU_SEGMENT_MAJOR_QUEUE_DIR=$queue_dir
Environment=DREAM7B_BPU_SEGMENT_MAJOR_OUTPUT_DIR=$output_dir
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
    systemctl daemon-reload
    systemctl enable "$service_name"
    systemctl restart "$service_name"
    systemctl --no-pager --full status "$service_name" | sed -n '1,40p'
    ;;
  status)
    systemctl --no-pager --full status "$service_name" 2>&1 | sed -n '1,80p' || true
    systemctl is-enabled "$service_name" 2>&1 || true
    ;;
  uninstall)
    require_root_for_mutation
    systemctl disable --now "$service_name" 2>/dev/null || true
    rm -f "$service_path"
    systemctl daemon-reload
    echo "Removed $service_name"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
