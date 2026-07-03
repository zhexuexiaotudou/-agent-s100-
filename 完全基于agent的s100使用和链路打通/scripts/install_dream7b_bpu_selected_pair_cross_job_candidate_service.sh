#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh plan [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh install [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh status
  scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh uninstall

Installs an isolated Dream 7B selected-pair cross-job candidate queue service.
It does not replace dream7b-bpu-batch-queue.service.

Environment:
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_SERVICE_NAME        Default: dream7b-bpu-selected-pair-cross-job-candidate.service.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_REPO_DIR            Default: /mnt/nas/openclaw.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_MIN_JOB_COUNT       Default: 2.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_JOB_COUNT       Default: 12.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE      Default: 16.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE_LIMIT
                                                          Default: 16.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_TOP_K               Default: 3.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_BPU_LOCK_PATH       Default: /run/lock/dream7b_bpu_batch_queue_runner.lock.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_POLL_INTERVAL_SEC   Default: 1.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_SINGLE_JOB_FLUSH_TIMEOUT_SEC
                                                          Default: 2.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_TIMEOUT_SEC         Default: 3600.
  DREAM7B_BPU_CROSS_JOB_CANDIDATE_RUNTIME_OWNER       Default: ${SUDO_USER:-current user}.
EOF
}

action="${1:-}"
if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
  usage
  exit 0
fi
shift || true

service_name="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_SERVICE_NAME:-dream7b-bpu-selected-pair-cross-job-candidate.service}"
service_path="/etc/systemd/system/$service_name"
repo_dir="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_REPO_DIR:-/mnt/nas/openclaw}"
default_queue_dir="/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-cross-job-candidate"
default_output_dir="/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_service"
queue_dir="${1:-$default_queue_dir}"
output_dir="${2:-$default_output_dir}"
min_job_count="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_MIN_JOB_COUNT:-2}"
max_job_count="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_JOB_COUNT:-12}"
max_batch_size="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE:-16}"
max_batch_size_limit="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE_LIMIT:-16}"
top_k="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_TOP_K:-3}"
bpu_lock_path="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_BPU_LOCK_PATH:-/run/lock/dream7b_bpu_batch_queue_runner.lock}"
poll_interval_sec="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_POLL_INTERVAL_SEC:-1}"
single_job_flush_timeout_sec="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_SINGLE_JOB_FLUSH_TIMEOUT_SEC:-2}"
timeout_sec="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_TIMEOUT_SEC:-3600}"
runtime_owner="${DREAM7B_BPU_CROSS_JOB_CANDIDATE_RUNTIME_OWNER:-${SUDO_USER:-$(id -un)}}"

validate_service_name() {
  case "$1" in
    dream7b-bpu-selected-pair-cross-job-candidate.service|dream7b-bpu-selected-pair-cross-job-candidate-*.service) ;;
    *)
      echo "Refusing unexpected cross-job candidate service name: $1" >&2
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
validate_integer "DREAM7B_BPU_CROSS_JOB_CANDIDATE_MIN_JOB_COUNT" "$min_job_count"
validate_integer "DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_JOB_COUNT" "$max_job_count"
validate_integer "DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE" "$max_batch_size"
validate_integer "DREAM7B_BPU_CROSS_JOB_CANDIDATE_MAX_BATCH_SIZE_LIMIT" "$max_batch_size_limit"
validate_integer "DREAM7B_BPU_CROSS_JOB_CANDIDATE_TOP_K" "$top_k"
validate_integer "DREAM7B_BPU_CROSS_JOB_CANDIDATE_TIMEOUT_SEC" "$timeout_sec"
validate_integer "DREAM7B_BPU_CROSS_JOB_CANDIDATE_SINGLE_JOB_FLUSH_TIMEOUT_SEC" "$single_job_flush_timeout_sec"

exec_start="/usr/bin/python3 $repo_dir/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py $queue_dir $output_dir --runner-cmd '/usr/bin/python3 $repo_dir/scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py' --forward-probe-cmd 'bash $repo_dir/scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh' --min-job-count $min_job_count --max-job-count $max_job_count --max-batch-size $max_batch_size --max-batch-size-limit $max_batch_size_limit --top-k $top_k --timeout-sec $timeout_sec --bpu-lock-path $bpu_lock_path --poll-interval-sec $poll_interval_sec --single-job-flush-timeout-sec $single_job_flush_timeout_sec"

show_plan() {
  cat <<EOF
Dream 7B selected-pair cross-job candidate service plan

service: $service_name
service_path: $service_path
queue_dir: $queue_dir
output_dir: $output_dir
repo_dir: $repo_dir
min_job_count: $min_job_count
max_job_count: $max_job_count
max_batch_size: $max_batch_size
max_batch_size_limit: $max_batch_size_limit
top_k: $top_k
bpu_lock_path: $bpu_lock_path
timeout_sec: $timeout_sec
poll_interval_sec: $poll_interval_sec
single_job_flush_timeout_sec: $single_job_flush_timeout_sec
runtime_owner: $runtime_owner
default_service_replaced: false
default_service_name: dream7b-bpu-batch-queue.service
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
Description=Dream 7B BPU selected-pair cross-job candidate queue service
Documentation=file://$repo_dir/scripts/install_dream7b_bpu_selected_pair_cross_job_candidate_service.sh
After=network-online.target
Wants=network-online.target
RequiresMountsFor=/mnt/nas/openclaw

[Service]
Type=simple
WorkingDirectory=$repo_dir
Environment=DREAM7B_BPU_CROSS_JOB_CANDIDATE_QUEUE_DIR=$queue_dir
Environment=DREAM7B_BPU_CROSS_JOB_CANDIDATE_OUTPUT_DIR=$output_dir
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
