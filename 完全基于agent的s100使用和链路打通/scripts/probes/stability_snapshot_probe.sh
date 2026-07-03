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
report="$out_dir/stability_snapshot_$stamp.md"

openclaw_bin() {
  PATH=/root/.local/lib/node-v24.16.0-linux-arm64/bin:/root/.npm-global/bin:$PATH command openclaw "$@"
}

gateway_status="unknown"
if systemctl is-active --quiet openclaw-gateway.service 2>/dev/null; then
  gateway_status="active"
elif systemctl --user is-active --quiet openclaw-gateway.service 2>/dev/null; then
  gateway_status="active-user"
elif ss -ltnp 2>/dev/null | grep -qE '127\.0\.0\.1:18789|\[::1\]:18789'; then
  gateway_status="active-listening"
else
  gateway_status="inactive"
fi

nas_status="not_mounted"
nas_fstype="$(findmnt -rn -o FSTYPE --target /mnt/nas/openclaw 2>/dev/null | head -1 || true)"
case "$nas_fstype" in
  nfs|nfs4|cifs|smb3)
    nas_status="mounted"
    ;;
  autofs)
    nas_status="autofs_not_reached"
    ;;
esac
if [[ "$nas_status" == "not_mounted" && -d /mnt/nas/openclaw ]]; then
  nas_status="directory_exists_not_mounted"
fi

reboot_count="$(last -x reboot 2>/dev/null | grep -c '^reboot' || true)"
oom_count="$(journalctl -k --since '24 hours ago' 2>/dev/null | grep -Eci 'out of memory|oom-killer|killed process' || true)"
gateway_error_count="$(journalctl -u openclaw-gateway.service --since '24 hours ago' 2>/dev/null | grep -Eci 'error|exception|failed|fatal' || true)"

{
  echo "# S100P Stability Snapshot"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- hostname: $(hostname 2>/dev/null || true)"
  echo "- report: $report"
  echo "- mode: point-in-time snapshot; not a 7-day endurance result"
  echo
  echo "## Summary"
  echo
  echo "| Check | Value |"
  echo "| --- | --- |"
  echo "| Gateway status | $gateway_status |"
  echo "| NAS workspace | $nas_status |"
  echo "| NAS fstype | ${nas_fstype:-missing} |"
  echo "| Reboot records visible | $reboot_count |"
  echo "| Kernel OOM matches in last 24h | $oom_count |"
  echo "| Gateway error-like log matches in last 24h | $gateway_error_count |"
  echo
  echo "## Uptime And Load"
  echo
  echo '```text'
  uptime -p 2>/dev/null || true
  uptime -s 2>/dev/null || true
  uptime 2>/dev/null || true
  echo '```'
  echo
  echo "## Memory"
  echo
  echo '```text'
  free -h 2>/dev/null || true
  echo '```'
  echo
  echo "## Disk"
  echo
  echo '```text'
  df -h / /root/.openclaw /root/.openclaw/workspace 2>&1 || true
  if [[ "$nas_status" == "mounted" ]]; then
    df -h /mnt/nas/openclaw 2>&1 || true
  else
    echo "/mnt/nas/openclaw skipped because NAS workspace is $nas_status"
  fi
  echo '```'
  echo
  echo "## OpenClaw Config"
  echo
  echo '```text'
  openclaw_bin config validate 2>&1 || true
  openclaw_bin plugins list 2>/dev/null | grep -E 'Tavily|S100P|loaded' || true
  echo '```'
  echo
  echo "## OpenClaw Gateway Status"
  echo
  echo '```text'
  systemctl --no-pager --full status openclaw-gateway.service 2>&1 | sed -n '1,40p' || true
  systemctl --user --no-pager --full status openclaw-gateway.service 2>&1 | sed -n '1,40p' || true
  ss -ltnp 2>/dev/null | grep -E '18789|18791' || true
  echo '```'
  echo
  echo "## Process Snapshot"
  echo
  echo '```text'
  ps -eo pid,ppid,etime,%mem,%cpu,comm,args --sort=-%mem 2>/dev/null | sed -n '1,25p' || true
  echo '```'
  echo
  echo "## Recent Gateway Error-Like Logs"
  echo
  echo '```text'
  journalctl -u openclaw-gateway.service --since '24 hours ago' --no-pager 2>/dev/null \
    | grep -Ei 'error|exception|failed|fatal' \
    | tail -n 40 || true
  echo '```'
  echo
  echo "## Recent Kernel OOM-Like Logs"
  echo
  echo '```text'
  journalctl -k --since '24 hours ago' --no-pager 2>/dev/null \
    | grep -Ei 'out of memory|oom-killer|killed process' \
    | tail -n 40 || true
  echo '```'
  echo
  echo "## 7x24 Acceptance Gap"
  echo
  echo "- This report proves the snapshot command works."
  echo "- A-010 is not verified until this snapshot is collected on a schedule for 7 days and summarized."
  echo "- NAS-backed acceptance additionally requires reports under /mnt/nas/openclaw/logs/probes."
} > "$report"

echo "$report"
