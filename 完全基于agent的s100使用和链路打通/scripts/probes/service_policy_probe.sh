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
report="$out_dir/service_policy_$stamp.md"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

listeners_file="$tmp_dir/listeners.txt"
services_file="$tmp_dir/services.txt"
rpcinfo_file="$tmp_dir/rpcinfo.txt"

ss -ltnp 2>/dev/null > "$listeners_file" || true
systemctl --no-pager --plain --type=service --state=running 2>/dev/null > "$services_file" || true
rpcinfo -p 2>/dev/null > "$rpcinfo_file" || true

has_listener() {
  local pattern="$1"
  grep -Eq "$pattern" "$listeners_file" 2>/dev/null
}

has_service() {
  local pattern="$1"
  grep -Eiq "$pattern" "$services_file" 2>/dev/null
}

status_for() {
  local kind="$1"
  case "$kind" in
    ssh)
      if has_listener '(^|[[:space:]])(0\.0\.0\.0|\[::\]):22[[:space:]]'; then echo "present"; else echo "absent"; fi
      ;;
    openclaw-gateway)
      if has_listener '127\.0\.0\.1:18789|\[::1\]:18789'; then echo "loopback"; elif has_listener ':18789[[:space:]]'; then echo "public"; else echo "absent"; fi
      ;;
    nfs-rpc)
      if has_service 'nfs|rpcbind|rpc-statd|nfs-mountd' || grep -Eq '[[:space:]](nfs|mountd|portmapper|nlockmgr|status)$' "$rpcinfo_file"; then echo "present"; else echo "absent"; fi
      ;;
    x11vnc)
      if has_listener ':5900[[:space:]]|x11vnc'; then echo "present"; else echo "absent"; fi
      ;;
    iiod)
      if has_listener ':30431[[:space:]]|iiod' || has_service '^iiod\.service'; then echo "present"; else echo "absent"; fi
      ;;
    *)
      echo "unknown"
      ;;
  esac
}

policy_row() {
  local component="$1"
  local observed="$2"
  local baseline_policy="$3"
  local recommendation="$4"
  local manual_command="$5"
  printf '| %s | %s | %s | %s | `%s` |\n' "$component" "$observed" "$baseline_policy" "$recommendation" "$manual_command"
}

ssh_status="$(status_for ssh)"
gateway_status="$(status_for openclaw-gateway)"
nfs_status="$(status_for nfs-rpc)"
vnc_status="$(status_for x11vnc)"
iiod_status="$(status_for iiod)"

{
  echo "# S100P Service Policy Plan"
  echo
  echo "- generated_at: $(date -Is)"
  echo "- hostname: $(hostname 2>/dev/null || true)"
  echo "- report: $report"
  echo "- mode: read-only; no services were changed"
  echo
  echo "## Policy Matrix"
  echo
  echo "| Component | Observed | Baseline policy | Recommendation | Manual command |"
  echo "| --- | --- | --- | --- | --- |"
  policy_row "OpenClaw Gateway" "$gateway_status" "Must stay loopback/LAN-gated" "Keep current loopback binding; fail if it becomes public" "ss -ltnp | grep 18789"
  policy_row "SSH" "$ssh_status" "Allowed management entry on trusted LAN/Tailscale" "Keep for now; move to key auth and restrict network later" "sudo systemctl status ssh"
  policy_row "NFS/RPC server stack" "$nfs_status" "Not required if TS-264C is the NAS and S100P is only a client" "Disable after confirming S100P is not exporting NFS shares" "sudo systemctl disable --now nfs-server nfs-mountd rpcbind rpc-statd"
  policy_row "x11vnc" "$vnc_status" "Only needed for desktop remoting" "Disable after confirming RDK Studio terminal/file access is enough" "sudo systemctl disable --now x11vnc"
  policy_row "iiod" "$iiod_status" "Only needed for IIO hardware tooling" "Keep if sensors/tools require it; otherwise disable or firewall" "sudo systemctl disable --now iiod"
  echo
  echo "## Firewall Alternative"
  echo
  echo "If services must remain installed, restrict them to a trusted subnet instead of exposing them broadly."
  echo
  echo '```bash'
  echo "# Example only. Adjust subnet before applying."
  echo "sudo ufw allow from 192.168.137.0/24 to any port 22 proto tcp"
  echo "sudo ufw deny 5900/tcp"
  echo "sudo ufw deny 111"
  echo "sudo ufw deny 2049"
  echo "sudo ufw deny 30431/tcp"
  echo '```'
  echo
  echo "## Evidence"
  echo
  echo "### Listening TCP sockets"
  echo
  echo '```text'
  cat "$listeners_file"
  echo '```'
  echo
  echo "### Running service matches"
  echo
  echo '```text'
  grep -Ei 'nfs|rpc|vnc|ssh|iiod|openclaw' "$services_file" 2>/dev/null || true
  echo '```'
  echo
  echo "### RPC map"
  echo
  echo '```text'
  if [[ -s "$rpcinfo_file" ]]; then
    cat "$rpcinfo_file"
  else
    echo "rpcinfo unavailable or no RPC services reported"
  fi
  echo '```'
  echo
  echo "## Current Decision Needed"
  echo
  echo "- Decide whether S100P should serve NFS. If not, the NFS/RPC stack can be disabled."
  echo "- Decide whether RDK Studio needs x11vnc desktop access. If not, x11vnc can be disabled."
  echo "- Decide whether IIO tooling is needed. If not, iiod can be disabled or firewalled."
} > "$report"

echo "$report"
