#!/usr/bin/env bash
set -euo pipefail

report_dir="${1:-/root/.openclaw/workspace/logs/probes}"
target_ip="${2:-169.254.110.209}"

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/logs/probes|/mnt/nas/openclaw/logs/probes/*|/root/.openclaw/workspace/logs/probes|/root/.openclaw/workspace/logs/probes/*) ;;
  *)
    echo "Refusing output path outside approved probe directories: $report_dir" >&2
    exit 2
    ;;
esac

case "$target_ip" in
  169.254.*|192.168.*|10.*|172.16.*|172.17.*|172.18.*|172.19.*|172.20.*|172.21.*|172.22.*|172.23.*|172.24.*|172.25.*|172.26.*|172.27.*|172.28.*|172.29.*|172.30.*|172.31.*) ;;
  *)
    echo "Refusing target outside private/link-local ranges: $target_ip" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/nas_link_blocker_$stamp.md"
json="$report_dir/nas_link_blocker_$stamp.json"

route_line="$(ip route get "$target_ip" 2>/dev/null | head -1 || true)"
iface="unknown"
if [[ -n "$route_line" ]]; then
  iface="$(awk '{for (i=1; i<=NF; i++) if ($i == "dev") {print $(i+1); exit}}' <<<"$route_line")"
  [[ -z "$iface" ]] && iface="unknown"
fi

iface_addr="unknown"
if [[ "$iface" != "unknown" ]]; then
  iface_addr="$(ip -brief addr show dev "$iface" 2>/dev/null || echo unknown)"
fi

mount_fstype="$(findmnt -rn -o FSTYPE --target /mnt/nas/openclaw 2>/dev/null | head -1 || true)"
mount_source="$(findmnt -rn -o SOURCE --target /mnt/nas/openclaw 2>/dev/null | head -1 || true)"
mount_status="not_mounted"
case "$mount_fstype" in
  nfs|nfs4|cifs|smb3) mount_status="real_mount" ;;
  autofs) mount_status="autofs_not_reached" ;;
  "")
    [[ -d /mnt/nas/openclaw ]] && mount_status="directory_exists_not_mounted"
    ;;
  *) mount_status="mounted_other_fstype:$mount_fstype" ;;
esac

neighbor_before="$(ip neigh show "$target_ip" 2>/dev/null || true)"
ping_output="$(ping -c 1 -W 2 "$target_ip" 2>&1 || true)"
neighbor_after="$(ip neigh show "$target_ip" 2>/dev/null || true)"

ping_status="fail"
if grep -qE '1 received|1 packets received' <<<"$ping_output"; then
  ping_status="ok"
fi

neighbor_state="missing"
if [[ -n "$neighbor_after" ]]; then
  neighbor_state="$(awk '{print $NF}' <<<"$neighbor_after" | tail -1)"
fi

verdict="review"
if [[ "$mount_status" == "real_mount" ]]; then
  verdict="ok_real_mount_present"
elif [[ "$ping_status" == "ok" ]]; then
  verdict="link_reachable_mount_not_verified"
elif [[ "$neighbor_state" == "FAILED" || "$neighbor_state" == "INCOMPLETE" || "$neighbor_state" == "missing" ]]; then
  verdict="blocked_l2_no_neighbor"
else
  verdict="blocked_ping_failed"
fi

python3 - "$json" "$report" "$target_ip" "$iface" "$iface_addr" "$route_line" "$mount_status" "$mount_fstype" "$mount_source" "$ping_status" "$neighbor_state" "$verdict" <<'PY'
import json
import sys
from datetime import datetime

(
    json_path, report, target_ip, iface, iface_addr, route_line, mount_status,
    mount_fstype, mount_source, ping_status, neighbor_state, verdict,
) = sys.argv[1:]

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only NAS link blocker probe; no login, mount, scan, or credential use",
    "report": report,
    "target_ip": target_ip,
    "route": route_line,
    "interface": iface,
    "interface_addr": iface_addr,
    "mount": {
        "status": mount_status,
        "fstype": mount_fstype or None,
        "source": mount_source or None,
    },
    "ping_status": ping_status,
    "neighbor_state": neighbor_state,
    "verdict": verdict,
}

with open(json_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

{
  echo "# NAS Link Blocker Probe"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- mode: read-only NAS link blocker probe; no login, mount, scan, or credential use"
  echo "- report: $report"
  echo "- json: $json"
  echo "- target_ip: $target_ip"
  echo "- verdict: $verdict"
  echo
  echo "## Summary"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Target IP | $target_ip |"
  echo "| Route interface | $iface |"
  echo "| Mount status | $mount_status |"
  echo "| Mount fstype | ${mount_fstype:-missing} |"
  echo "| Mount source | ${mount_source:-missing} |"
  echo "| Ping status | $ping_status |"
  echo "| Neighbor state | $neighbor_state |"
  echo "| Verdict | $verdict |"
  echo
  echo "## Route"
  echo
  echo '```text'
  printf '%s\n' "${route_line:-missing}"
  echo '```'
  echo
  echo "## Interface"
  echo
  echo '```text'
  printf '%s\n' "$iface_addr"
  echo '```'
  echo
  echo "## Neighbor Before Ping"
  echo
  echo '```text'
  printf '%s\n' "${neighbor_before:-missing}"
  echo '```'
  echo
  echo "## Ping"
  echo
  echo '```text'
  printf '%s\n' "$ping_output"
  echo '```'
  echo
  echo "## Neighbor After Ping"
  echo
  echo '```text'
  printf '%s\n' "${neighbor_after:-missing}"
  echo '```'
  echo
  echo "## Boundary"
  echo
  echo "- This probe does not log in to NAS."
  echo "- This probe does not mount or unmount anything."
  echo "- This probe does not scan the network."
  echo "- This probe does not use or print credentials."
} > "$report"

echo "$report"
