#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-${OPENCLAW_PROBE_DIR:-/tmp/openclaw-probes}}"

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
report="$out_dir/sandbox_status_$(date +%Y%m%d-%H%M%S).md"

cmd_path() {
  if command -v "$1" >/dev/null 2>&1; then
    command -v "$1"
  else
    echo "missing"
  fi
}

service_state() {
  systemctl is-active "$1" 2>/dev/null || echo "unknown"
}

pkg_line() {
  dpkg-query -W -f='${Package} ${Version}\n' "$1" 2>/dev/null || true
}

{
  echo "# Sandbox Status"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- host: $(hostname 2>/dev/null || echo unknown)"
  echo "- kernel: $(uname -a)"
  echo
  echo "## Runtime Commands"
  echo
  echo "| Runtime | Path |"
  echo "| --- | --- |"
  echo "| docker | $(cmd_path docker) |"
  echo "| podman | $(cmd_path podman) |"
  echo "| runc | $(cmd_path runc) |"
  echo "| containerd | $(cmd_path containerd) |"
  echo "| ctr | $(cmd_path ctr) |"
  echo
  echo "## Service State"
  echo
  echo "| Service | State |"
  echo "| --- | --- |"
  echo "| docker | $(service_state docker) |"
  echo "| containerd | $(service_state containerd) |"
  echo
  echo "## Installed Packages"
  echo
  pkg_line docker.io
  pkg_line docker-ce
  pkg_line podman
  pkg_line containerd
  pkg_line runc
  echo
  echo "## Kernel Namespace Support"
  echo
  if [[ -d /proc/self/ns ]]; then
    ls -1 /proc/self/ns | sort | sed 's/^/- /'
  else
    echo "- /proc/self/ns missing"
  fi
  echo
  echo "## Cgroup"
  echo
  if [[ -f /proc/filesystems ]]; then
    grep -E 'cgroup|cgroup2' /proc/filesystems | sed 's/^/- /' || true
  fi
  if [[ -f /proc/self/cgroup ]]; then
    echo
    echo '```text'
    sed -n '1,20p' /proc/self/cgroup
    echo '```'
  fi
  echo
  echo "## A-006 Verdict"
  echo
  if command -v docker >/dev/null 2>&1 && systemctl is-active docker >/dev/null 2>&1; then
    echo "- runtime_available: yes"
    echo "- isolation_verdict: not_tested"
    echo "- next_check: run a container with only a temporary bind mount and prove sensitive host paths are not writable."
  elif command -v podman >/dev/null 2>&1; then
    echo "- runtime_available: yes"
    echo "- isolation_verdict: not_tested"
    echo "- next_check: run a rootless container with only a temporary bind mount and prove sensitive host paths are not writable."
  else
    echo "- runtime_available: no"
    echo "- isolation_verdict: blocked"
    echo "- reason: Docker/Podman/runc are not installed or not available."
  fi
} > "$report"

echo "$report"
