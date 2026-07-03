#!/usr/bin/env bash
set -euo pipefail

out_dir="${1:-${OPENCLAW_PROBE_DIR:-/root/.openclaw/workspace/logs/probes}}"

case "$out_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $out_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$out_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$out_dir/service_hardening_plan_$stamp.md"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

listeners="$tmp_dir/listeners.txt"
services="$tmp_dir/services.txt"
rpcmap="$tmp_dir/rpcinfo.txt"

ss -ltnp 2>/dev/null > "$listeners" || true
systemctl --no-pager --plain --type=service --state=running 2>/dev/null > "$services" || true
rpcinfo -p 2>/dev/null > "$rpcmap" || true

has_listener() {
  grep -Eiq "$1" "$listeners" 2>/dev/null
}

has_service() {
  grep -Eiq "$1" "$services" 2>/dev/null
}

is_present() {
  local component="$1"
  case "$component" in
    nfs-rpc)
      has_service 'nfs|rpcbind|rpc-statd|nfs-mountd' || grep -Eq '[[:space:]](nfs|mountd|portmapper|nlockmgr|status)$' "$rpcmap" 2>/dev/null
      ;;
    x11vnc)
      has_listener ':5900[[:space:]]|x11vnc' || has_service 'x11vnc'
      ;;
    iiod)
      has_listener ':30431[[:space:]]|iiod' || has_service '^iiod\.service|iiod'
      ;;
    ssh)
      has_listener '(^|[[:space:]])(0\.0\.0\.0|\[::\]):22[[:space:]]|sshd'
      ;;
    *)
      return 1
      ;;
  esac
}

status_text() {
  if is_present "$1"; then
    echo "present"
  else
    echo "absent"
  fi
}

nfs_status="$(status_text nfs-rpc)"
vnc_status="$(status_text x11vnc)"
iiod_status="$(status_text iiod)"
ssh_status="$(status_text ssh)"

gateway_status="unknown"
if has_listener '127\.0\.0\.1:18789|\[::1\]:18789'; then
  gateway_status="loopback"
elif has_listener ':18789[[:space:]]'; then
  gateway_status="public"
else
  gateway_status="absent"
fi

{
  echo "# S100P Service Hardening Dry-Run Plan"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- report: $report"
  echo "- mode: dry-run; no service or firewall changes were made"
  echo
  echo "## Current Service Decisions"
  echo
  echo "| Component | Observed | Suggested decision | Why |"
  echo "| --- | --- | --- | --- |"
  echo "| OpenClaw Gateway | $gateway_status | keep-loopback | Gateway should remain local to OpenClaw. |"
  echo "| SSH | $ssh_status | keep-trusted-management | Needed for RDK Studio and board administration. |"
  echo "| NFS/RPC server stack | $nfs_status | disable-if-client-only | TS-264C is intended to be the NAS; S100P should normally be a client. |"
  echo "| x11vnc | $vnc_status | disable-if-unused | Desktop VNC is unnecessary if RDK Studio terminal/file access is enough. |"
  echo "| iiod | $iiod_status | keep-or-firewall | Keep only when IIO hardware tooling is needed. |"
  echo
  echo "## Operator Confirmation Needed"
  echo
  echo "Do not run the commands below until these choices are confirmed:"
  echo
  echo "- S100P is not exporting NFS shares."
  echo "- RDK Studio does not require x11vnc desktop access."
  echo "- IIO tooling is not required, or its port can be firewall-restricted."
  echo
  echo "## Disable Plan"
  echo
  echo '```bash'
  echo "# Dry-run plan only. Review before applying."
  if [[ "$nfs_status" == "present" ]]; then
    echo "sudo systemctl disable --now nfs-server nfs-mountd rpcbind rpc-statd || true"
    echo "sudo systemctl mask nfs-server nfs-mountd rpcbind rpc-statd || true"
  else
    echo "# NFS/RPC server stack appears absent; no disable command needed."
  fi
  if [[ "$vnc_status" == "present" ]]; then
    echo "sudo systemctl disable --now x11vnc || true"
    echo "sudo systemctl mask x11vnc || true"
  else
    echo "# x11vnc appears absent; no disable command needed."
  fi
  if [[ "$iiod_status" == "present" ]]; then
    echo "# If IIO tooling is not needed:"
    echo "sudo systemctl disable --now iiod || true"
    echo "sudo systemctl mask iiod || true"
  else
    echo "# iiod appears absent; no disable command needed."
  fi
  echo '```'
  echo
  echo "## Firewall-Only Alternative"
  echo
  echo '```bash'
  echo "# Example only. Adjust trusted subnet before applying."
  echo "sudo ufw allow from 192.168.137.0/24 to any port 22 proto tcp"
  [[ "$vnc_status" == "present" ]] && echo "sudo ufw deny 5900/tcp"
  [[ "$nfs_status" == "present" ]] && echo "sudo ufw deny 111 && sudo ufw deny 2049"
  [[ "$iiod_status" == "present" ]] && echo "sudo ufw deny 30431/tcp"
  echo '```'
  echo
  echo "## Post-Change Verification Commands"
  echo
  echo '```bash'
  echo "ss -ltnp"
  echo "systemctl --no-pager --plain --type=service --state=running | grep -Ei 'nfs|rpc|vnc|iiod|ssh|openclaw' || true"
  echo "bash /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh security_audit_probe /root/.openclaw/workspace/logs/probes"
  echo "bash /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh service_policy_probe /root/.openclaw/workspace/logs/probes"
  echo '```'
  echo
  echo "## Evidence"
  echo
  echo "### Listening TCP sockets"
  echo
  echo '```text'
  cat "$listeners"
  echo '```'
  echo
  echo "### Matching running services"
  echo
  echo '```text'
  grep -Ei 'nfs|rpc|vnc|ssh|iiod|openclaw' "$services" 2>/dev/null || true
  echo '```'
  echo
  echo "### RPC map"
  echo
  echo '```text'
  if [[ -s "$rpcmap" ]]; then
    cat "$rpcmap"
  else
    echo "rpcinfo unavailable or no RPC services reported"
  fi
  echo '```'
} > "$report"

echo "$report"
