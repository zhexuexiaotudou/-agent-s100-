#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:-${OPENCLAW_PROBE_DIR:-/mnt/nas/openclaw/logs/probes}}"
report_dir="${2:-/mnt/nas/openclaw/reports/security}"

case "$input_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing input path outside approved probe directories: $input_dir" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing output path outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

latest_file() {
  local pattern="$1"
  find "$input_dir" -maxdepth 1 -type f -name "$pattern" -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | awk 'NR==1 {$1=""; sub(/^ /, ""); print}'
}

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/service_convergence_decision_$stamp.md"

security_report="$(latest_file 'security_audit_*.md')"
service_policy_report="$(latest_file 'service_policy_*.md')"
hardening_plan_report="$(latest_file 'service_hardening_plan_*.md')"

listener_snapshot="$(ss -ltnp 2>/dev/null || true)"
running_services="$(systemctl --no-pager --plain --type=service --state=running 2>/dev/null || true)"

has_listener() {
  local pattern="$1"
  printf '%s\n' "$listener_snapshot" | grep -Eiq "$pattern" && echo yes || echo no
}

has_service() {
  local pattern="$1"
  printf '%s\n' "$running_services" | grep -Eiq "$pattern" && echo yes || echo no
}

gateway_loopback="no"
if printf '%s\n' "$listener_snapshot" | grep -Eq '127\.0\.0\.1:18789|\[::1\]:18789'; then
  gateway_loopback="yes"
fi

nfs_rpc_present="$(has_service 'nfs|rpcbind|rpc-statd|rpc-statd-notify|nfs-mountd')"
x11vnc_present="$(has_service 'x11vnc')"
iiod_present="$(has_service 'iiod')"
ssh_present="$(has_service '^ssh\.service| ssh\.service')"
vnc_listening="$(has_listener '(:5900|x11vnc)')"
iiod_listening="$(has_listener '(:30431|iiod)')"

{
  echo "# B-010 Service Convergence Decision Pack"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only decision pack; no service or firewall changes executed"
  echo "- input_dir: $input_dir"
  echo "- report: $report"
  echo "- latest_security_audit: ${security_report:-missing}"
  echo "- latest_service_policy: ${service_policy_report:-missing}"
  echo "- latest_hardening_plan: ${hardening_plan_report:-missing}"
  echo
  echo "## Current Signals"
  echo
  echo "| Signal | Value | Meaning |"
  echo "| --- | --- | --- |"
  echo "| OpenClaw Gateway loopback | $gateway_loopback | Must remain loopback-only. |"
  echo "| SSH service present | $ssh_present | Keep for RDK Studio and board administration. |"
  echo "| NFS/RPC server stack present | $nfs_rpc_present | Usually unnecessary when S100P is only an NFS client of TS-264C. |"
  echo "| x11vnc service present | $x11vnc_present | Disable if RDK Studio terminal/file access is enough. |"
  echo "| VNC port/listener present | $vnc_listening | Public LAN VNC should not remain open unless explicitly needed. |"
  echo "| iiod service present | $iiod_present | Keep only if IIO hardware tooling is needed. |"
  echo "| iiod port/listener present | $iiod_listening | Firewall or disable if unused. |"
  echo
  echo "## Recommended Decision"
  echo
  echo "| Component | Recommendation | Required confirmation before execution |"
  echo "| --- | --- | --- |"
  echo "| OpenClaw Gateway | keep-loopback | Confirm no non-loopback Gateway listener appears in security audit. |"
  echo "| SSH | keep-trusted-management | Confirm SSH is key-based or restricted to trusted direct/LAN management network later. |"
  echo "| NFS/RPC server stack | disable-if-client-only | Confirm S100P is not exporting NFS shares to any other host. |"
  echo "| x11vnc | disable-if-unused | Confirm RDK Studio terminal/file access is enough and no desktop VNC workflow is needed. |"
  echo "| iiod | keep-or-firewall | Confirm whether D-Robotics/IIO hardware tools depend on it. |"
  echo
  echo "## Candidate Execution Commands"
  echo
  echo "Do not run these until the required confirmations above are true."
  echo
  echo '```bash'
  echo "# NFS/RPC server stack, only if S100P is client-only"
  echo "sudo systemctl disable --now nfs-server nfs-mountd rpcbind rpc-statd rpc-statd-notify || true"
  echo
  echo "# VNC desktop, only if unused"
  echo "sudo systemctl disable --now x11vnc || true"
  echo "sudo systemctl mask x11vnc || true"
  echo
  echo "# IIO daemon, only if unused by hardware tooling"
  echo "sudo systemctl disable --now iiod || true"
  echo "sudo systemctl mask iiod || true"
  echo '```'
  echo
  echo "## Rollback Commands"
  echo
  echo '```bash'
  echo "sudo systemctl unmask x11vnc iiod || true"
  echo "sudo systemctl enable --now x11vnc || true"
  echo "sudo systemctl enable --now iiod || true"
  echo "sudo systemctl enable --now nfs-server nfs-mountd rpcbind rpc-statd rpc-statd-notify || true"
  echo '```'
  echo
  echo "## Post-Change Verification"
  echo
  echo '```bash'
  echo "ss -ltnp | grep -E '18789|5900|30431|2049|111' || true"
  echo "systemctl --no-pager --plain --type=service --state=running | grep -Ei 'openclaw|ssh|nfs|rpc|x11vnc|iiod' || true"
  echo "findmnt /mnt/nas/openclaw"
  echo "test -w /mnt/nas/openclaw && echo NAS_WRITABLE"
  echo '```'
  echo
  echo "## Current Listener Snapshot"
  echo
  echo '```text'
  printf '%s\n' "$listener_snapshot"
  echo '```'
  echo
  echo "## Current Service Snapshot"
  echo
  echo '```text'
  printf '%s\n' "$running_services" | grep -Ei 'openclaw|ssh|nfs|rpc|x11vnc|iiod' || true
  echo '```'
  echo
  echo "## B-010 Tracking Impact"
  echo
  echo "- This pack is evidence for a reviewable B-010 service convergence decision."
  echo "- B-010 remains doing until the operator confirms and executes keep/disable/firewall decisions, followed by a clean post-change audit."
} > "$report"

echo "$report"
