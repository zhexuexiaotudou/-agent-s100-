#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install_stability_sampler.sh plan [output_dir]
  scripts/install_stability_sampler.sh install [output_dir]
  scripts/install_stability_sampler.sh status
  scripts/install_stability_sampler.sh run-once [output_dir]
  scripts/install_stability_sampler.sh uninstall

Installs a low-frequency systemd timer for A-010 stability evidence collection.
The timer runs stability_snapshot_probe.sh on the S100P and writes reports to an
approved probe directory.

Environment:
  OPENCLAW_STABILITY_INTERVAL_SEC  Sampling interval in seconds. Default: 1800.
EOF
}

action="${1:-}"
if [[ -z "$action" || "$action" == "-h" || "$action" == "--help" || "$action" == "help" ]]; then
  usage
  exit 0
fi
shift || true

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"
probe="$repo_dir/scripts/probes/stability_snapshot_probe.sh"

service_name="openclaw-stability-sampler.service"
timer_name="openclaw-stability-sampler.timer"
service_path="/etc/systemd/system/$service_name"
timer_path="/etc/systemd/system/$timer_name"
state_dir="/var/lib/openclaw-stability-sampler"
default_output_dir="/root/.openclaw/workspace/logs/probes"
output_dir="${1:-$default_output_dir}"
interval_sec="${OPENCLAW_STABILITY_INTERVAL_SEC:-1800}"

validate_output_dir() {
  case "$1" in
    /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
    *)
      echo "Refusing output path outside approved probe directories: $1" >&2
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

require_probe() {
  if [[ ! -f "$probe" ]]; then
    echo "Missing stability probe: $probe" >&2
    exit 3
  fi
}

validate_interval() {
  if ! [[ "$interval_sec" =~ ^[0-9]+$ ]]; then
    echo "OPENCLAW_STABILITY_INTERVAL_SEC must be an integer number of seconds." >&2
    exit 2
  fi
  if (( interval_sec < 300 )); then
    echo "Refusing interval below 300 seconds for a stability sampler." >&2
    exit 2
  fi
}

show_plan() {
  cat <<EOF
Stability sampler plan

service: $service_path
timer: $timer_path
probe: $probe
output_dir: $output_dir
interval_sec: $interval_sec
state_dir: $state_dir

The service is oneshot. The timer uses OnBootSec=2min and OnUnitActiveSec=${interval_sec}s.
The existing stability_snapshot_probe.sh still owns the report format and path checks.
EOF
}

case "$action" in
  plan)
    validate_output_dir "$output_dir"
    validate_interval
    require_probe
    show_plan
    ;;
  run-once)
    validate_output_dir "$output_dir"
    require_probe
    exec bash "$probe" "$output_dir"
    ;;
  install)
    validate_output_dir "$output_dir"
    validate_interval
    require_probe
    require_root_for_mutation
    mkdir -p "$state_dir" "$output_dir"
    cat > "$service_path" <<EOF
[Unit]
Description=OpenClaw A-010 stability snapshot sampler
Documentation=file://$repo_dir/docs/stability_snapshot_runbook.md
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$repo_dir
Environment=OPENCLAW_PROBE_DIR=$output_dir
ExecStart=/usr/bin/env bash $probe $output_dir
StateDirectory=openclaw-stability-sampler
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF
    cat > "$timer_path" <<EOF
[Unit]
Description=Run OpenClaw A-010 stability snapshots every ${interval_sec}s

[Timer]
OnBootSec=2min
OnUnitActiveSec=${interval_sec}s
AccuracySec=30s
Persistent=true
Unit=$service_name

[Install]
WantedBy=timers.target
EOF
    systemctl daemon-reload
    systemctl enable --now "$timer_name"
    systemctl start "$service_name"
    systemctl --no-pager --full status "$timer_name" | sed -n '1,30p'
    ;;
  status)
    systemctl --no-pager --full status "$timer_name" 2>&1 | sed -n '1,50p' || true
    systemctl --no-pager --full status "$service_name" 2>&1 | sed -n '1,70p' || true
    systemctl list-timers --all "$timer_name" 2>&1 || true
    ;;
  uninstall)
    require_root_for_mutation
    systemctl disable --now "$timer_name" 2>/dev/null || true
    rm -f "$service_path" "$timer_path"
    systemctl daemon-reload
    echo "Removed $service_name and $timer_name"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
