#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/root/.openclaw/workspace/logs/probes}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/nas_discovery_$stamp.md"

tool_status() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf 'ok'
  else
    printf 'missing'
  fi
}

mount_status="not_mounted"
if mountpoint -q /mnt/nas/openclaw 2>/dev/null; then
  mount_status="mounted"
elif [[ -d /mnt/nas/openclaw ]]; then
  mount_status="directory_exists_not_mounted"
fi

neighbor_count="$(ip neigh show 2>/dev/null | wc -l | tr -d ' ')"
default_routes="$(ip route show default 2>/dev/null | wc -l | tr -d ' ')"

{
  echo "# NAS Discovery Probe"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- report: $report"
  echo "- mode: passive/read-only network and NAS readiness discovery"
  echo
  echo "## Summary"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| /mnt/nas/openclaw | $mount_status |"
  echo "| Default routes | $default_routes |"
  echo "| Neighbor entries | $neighbor_count |"
  echo "| mount.cifs | $(tool_status mount.cifs) |"
  echo "| mount.nfs | $(tool_status mount.nfs) |"
  echo "| smbclient | $(tool_status smbclient) |"
  echo "| showmount | $(tool_status showmount) |"
  echo "| rpcinfo | $(tool_status rpcinfo) |"
  echo "| avahi-browse | $(tool_status avahi-browse) |"
  echo
  echo "## Network Interfaces"
  echo
  echo '```text'
  ip -brief addr 2>/dev/null || true
  echo '```'
  echo
  echo "## Routes"
  echo
  echo '```text'
  ip route 2>/dev/null || true
  echo '```'
  echo
  echo "## Neighbor Table"
  echo
  echo '```text'
  ip neigh show 2>/dev/null || true
  echo '```'
  echo
  echo "## Current NAS Mount State"
  echo
  echo '```text'
  findmnt /mnt/nas/openclaw 2>&1 || true
  ls -ld /mnt /mnt/nas /mnt/nas/openclaw 2>&1 || true
  echo '```'
  echo
  echo "## Local SMB/NFS Tooling"
  echo
  echo '```text'
  command -v mount.cifs || true
  command -v mount.nfs || true
  command -v smbclient || true
  command -v showmount || true
  command -v rpcinfo || true
  command -v avahi-browse || true
  dpkg-query -W cifs-utils nfs-common smbclient avahi-utils 2>/dev/null || true
  echo '```'
  echo
  echo "## Passive Service Hints"
  echo
  echo '```text'
  if command -v avahi-browse >/dev/null 2>&1; then
    timeout 5 avahi-browse -art 2>/dev/null | grep -Ei 'smb|nfs|nas|qnap|ts-264|workstation|file' || true
  else
    echo "avahi-browse missing; mDNS service discovery not available"
  fi
  echo '```'
  echo
  echo "## A-003 Remaining Inputs"
  echo
  echo "- NAS host or fixed IP."
  echo "- Protocol: smb or nfs."
  echo "- SMB share name or NFS export path."
  echo "- Dedicated NAS account with read/write access only to the OpenClaw workspace share."
  echo "- Credential delivery method that does not write secrets into this repo."
} > "$report"

echo "$report"
