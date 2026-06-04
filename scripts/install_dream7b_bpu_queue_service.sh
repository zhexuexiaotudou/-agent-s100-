#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install_dream7b_bpu_queue_service.sh plan [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_queue_service.sh install [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_queue_service.sh status
  scripts/install_dream7b_bpu_queue_service.sh uninstall

Installs a systemd service for the Dream 7B BPU directory-backed queue loop.

Environment:
  DREAM7B_BPU_QUEUE_POLL_INTERVAL_SEC  Poll interval in seconds. Default: 1.
  DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE     Runner max batch size. Default: 4.
  DREAM7B_BPU_QUEUE_TOP_K              Runner top-k output. Default: 3.
  DREAM7B_BPU_QUEUE_LOCK_PATH          Runner BPU lock path. Default: /run/lock/dream7b_bpu_batch_queue_runner.lock.
  DREAM7B_BPU_QUEUE_REPO_DIR           Runtime workspace for systemd WorkingDirectory. Default: /mnt/nas/openclaw.
EOF
}

action="${1:-}"
if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
  usage
  exit 0
fi
shift || true

default_repo_dir="/mnt/nas/openclaw"
repo_dir="${DREAM7B_BPU_QUEUE_REPO_DIR:-$default_repo_dir}"
service_name="dream7b-bpu-batch-queue.service"
service_path="/etc/systemd/system/$service_name"
default_queue_dir="/mnt/nas/openclaw/queues/dream7b-bpu"
default_output_dir="/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd"
queue_dir="${1:-$default_queue_dir}"
output_dir="${2:-$default_output_dir}"
poll_interval_sec="${DREAM7B_BPU_QUEUE_POLL_INTERVAL_SEC:-1}"
max_batch_size="${DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE:-4}"
top_k="${DREAM7B_BPU_QUEUE_TOP_K:-3}"
bpu_lock_path="${DREAM7B_BPU_QUEUE_LOCK_PATH:-/run/lock/dream7b_bpu_batch_queue_runner.lock}"

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
    /mnt/nas/openclaw|/root/.openclaw/workspace|/tmp/*) ;;
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

validate_number() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "$name must be a non-negative number." >&2
    exit 2
  fi
}

require_root_for_mutation() {
  if [[ "$(id -u)" != "0" ]]; then
    echo "This action must run as root because it writes systemd unit files." >&2
    exit 4
  fi
}

require_runtime() {
  if ! command -v dream7b-bpu-batch-queue-service >/dev/null 2>&1; then
    echo "Missing deployed command: dream7b-bpu-batch-queue-service" >&2
    exit 3
  fi
  if ! command -v dream7b-bpu-batch-queue-runner >/dev/null 2>&1; then
    echo "Missing deployed command: dream7b-bpu-batch-queue-runner" >&2
    exit 3
  fi
}

show_plan() {
  cat <<EOF
Dream 7B BPU queue service plan

service: $service_name
service_path: $service_path
queue_dir: $queue_dir
output_dir: $output_dir
poll_interval_sec: $poll_interval_sec
max_batch_size: $max_batch_size
top_k: $top_k
bpu_lock_path: $bpu_lock_path
working_directory: $repo_dir

The service is long-running and consumes JSONL jobs from queue_dir/pending.
It keeps runner-level durable_state and bpu_lock semantics authoritative.
EOF
}

validate_queue_dir "$queue_dir"
validate_output_dir "$output_dir"
validate_repo_dir "$repo_dir"
validate_number "DREAM7B_BPU_QUEUE_POLL_INTERVAL_SEC" "$poll_interval_sec"
validate_number "DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE" "$max_batch_size"
validate_number "DREAM7B_BPU_QUEUE_TOP_K" "$top_k"

case "$action" in
  plan)
    require_runtime
    show_plan
    ;;
  install)
    require_root_for_mutation
    require_runtime
    mkdir -p "$queue_dir/pending" "$queue_dir/processing" "$queue_dir/done" "$queue_dir/failed" "$output_dir"
    cat > "$service_path" <<EOF
[Unit]
Description=Dream 7B BPU batch queue service
Documentation=file:///usr/local/bin/install-dream7b-bpu-queue-service
After=network-online.target
Wants=network-online.target
RequiresMountsFor=/mnt/nas/openclaw

[Service]
Type=simple
WorkingDirectory=$repo_dir
Environment=DREAM7B_BPU_QUEUE_DIR=$queue_dir
Environment=DREAM7B_BPU_QUEUE_OUTPUT_DIR=$output_dir
ExecStart=/usr/local/bin/dream7b-bpu-batch-queue-service $queue_dir $output_dir --poll-interval-sec $poll_interval_sec --max-batch-size $max_batch_size --top-k $top_k --bpu-lock-path $bpu_lock_path
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
