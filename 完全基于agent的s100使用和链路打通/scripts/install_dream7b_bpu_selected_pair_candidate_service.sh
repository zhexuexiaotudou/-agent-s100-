#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install_dream7b_bpu_selected_pair_candidate_service.sh plan [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_selected_pair_candidate_service.sh install [queue_dir] [output_dir]
  scripts/install_dream7b_bpu_selected_pair_candidate_service.sh status
  scripts/install_dream7b_bpu_selected_pair_candidate_service.sh uninstall

Installs a guarded Dream 7B selected-pair candidate queue service.
This service uses a separate systemd unit, queue directory, and output directory.
It does not replace dream7b-bpu-batch-queue.service.

Environment:
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_NAME               Default: dream7b-bpu-selected-pair-candidate.service.
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_POLL_INTERVAL_SEC    Default: 1.
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE       Default: 16.
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_TOP_K                Default: 3.
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_LOCK_PATH            Default: /run/lock/dream7b_bpu_batch_queue_runner.lock.
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_REPO_DIR             Default: /mnt/nas/openclaw.
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD                Default: dream7b-bpu-selected-pair-batch-forward.
  DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_DRAIN_ALL            Default: 1.
EOF
}

action="${1:-}"
if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
  usage
  exit 0
fi
shift || true

service_name="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_SERVICE_NAME:-dream7b-bpu-selected-pair-candidate.service}"
service_path="/etc/systemd/system/$service_name"
default_repo_dir="/mnt/nas/openclaw"
repo_dir="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_REPO_DIR:-$default_repo_dir}"
default_queue_dir="/mnt/nas/openclaw/queues/dream7b-bpu-selected-pair-candidate"
default_output_dir="/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_candidate_service_systemd"
queue_dir="${1:-$default_queue_dir}"
output_dir="${2:-$default_output_dir}"
poll_interval_sec="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_POLL_INTERVAL_SEC:-1}"
max_batch_size="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE:-16}"
top_k="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_TOP_K:-3}"
bpu_lock_path="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_LOCK_PATH:-/run/lock/dream7b_bpu_batch_queue_runner.lock}"
forward_cmd="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD:-dream7b-bpu-selected-pair-batch-forward}"
drain_all="${DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_DRAIN_ALL:-1}"

validate_service_name() {
  case "$1" in
    dream7b-bpu-selected-pair-candidate.service|dream7b-bpu-selected-pair-candidate-*.service) ;;
    *)
      echo "Refusing unexpected selected-pair candidate service name: $1" >&2
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

validate_forward_cmd() {
  case "$1" in
    dream7b-bpu-selected-pair-batch-forward|/usr/local/bin/dream7b-bpu-selected-pair-batch-forward) ;;
    *)
      echo "Refusing non-selected-pair candidate forward command: $1" >&2
      exit 2
      ;;
  esac
}

validate_number() {
  local name="$1"
  local value="$2"
  if ! [[ "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "$name must be a non-negative number." >&2
    exit 2
  fi
}

normalize_bool() {
  local name="$1"
  local value="$2"
  case "$value" in
    1|true|TRUE|yes|YES|on|ON)
      echo "true"
      ;;
    0|false|FALSE|no|NO|off|OFF)
      echo "false"
      ;;
    *)
      echo "$name must be one of 1,true,yes,on,0,false,no,off." >&2
      exit 2
      ;;
  esac
}

require_root_for_mutation() {
  if [[ "$(id -u)" != "0" ]]; then
    echo "This action must run as root because it writes systemd unit files." >&2
    exit 4
  fi
}

require_runtime() {
  for cmd in dream7b-bpu-batch-queue-service dream7b-bpu-batch-queue-runner "$forward_cmd"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      echo "Missing deployed command: $cmd" >&2
      exit 3
    fi
  done
}

validate_service_name "$service_name"
validate_queue_dir "$queue_dir"
validate_output_dir "$output_dir"
validate_repo_dir "$repo_dir"
validate_forward_cmd "$forward_cmd"
validate_number "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_POLL_INTERVAL_SEC" "$poll_interval_sec"
validate_number "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_MAX_BATCH_SIZE" "$max_batch_size"
validate_number "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_TOP_K" "$top_k"
drain_all_enabled="$(normalize_bool "DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_DRAIN_ALL" "$drain_all")"
exec_start="/usr/local/bin/dream7b-bpu-batch-queue-service $queue_dir $output_dir --poll-interval-sec $poll_interval_sec --max-batch-size $max_batch_size --top-k $top_k --forward-cmd $forward_cmd --bpu-lock-path $bpu_lock_path"
if [[ "$drain_all_enabled" == "true" ]]; then
  exec_start="$exec_start --drain-all"
fi

show_plan() {
  cat <<EOF
Dream 7B selected-pair candidate queue service plan

service: $service_name
service_path: $service_path
queue_dir: $queue_dir
output_dir: $output_dir
poll_interval_sec: $poll_interval_sec
max_batch_size: $max_batch_size
top_k: $top_k
forward_cmd: $forward_cmd
bpu_lock_path: $bpu_lock_path
drain_all: $drain_all_enabled
working_directory: $repo_dir
default_service_replaced: false
default_service_name: dream7b-bpu-batch-queue.service
EOF
}

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
Description=Dream 7B BPU selected-pair candidate queue service
Documentation=file:///usr/local/bin/install-dream7b-bpu-selected-pair-candidate-service
After=network-online.target
Wants=network-online.target
RequiresMountsFor=/mnt/nas/openclaw

[Service]
Type=simple
WorkingDirectory=$repo_dir
Environment=DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_DIR=$queue_dir
Environment=DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_QUEUE_OUTPUT_DIR=$output_dir
Environment=DREAM7B_BPU_SELECTED_PAIR_CANDIDATE_FORWARD_CMD=$forward_cmd
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
