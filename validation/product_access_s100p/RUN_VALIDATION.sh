#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-./validation-results}"
mkdir -p "$OUT/raw"
failed=0
run() { local name="$1"; shift; if "$@" >"$OUT/raw/$name.txt" 2>&1; then printf 'PASS %s\n' "$name"; else printf 'PENDING/FAIL %s\n' "$name"; failed=1; fi; }
service_status() {
  local unit="$1"
  if systemctl is-active --quiet "$unit"; then
    printf 'scope=system\n'
    systemctl status --no-pager "$unit"
  elif systemctl --user is-active --quiet "$unit"; then
    printf 'scope=user\n'
    systemctl --user status --no-pager "$unit"
  else
    printf 'inactive in system and user scopes\n' >&2
    systemctl status --no-pager "$unit" || true
    systemctl --user status --no-pager "$unit" || true
    return 1
  fi
}
run uname uname -a
run architecture uname -m
run network nmcli device status
run address ip -brief address
run nas_mount findmnt /mnt/nas/openclaw
run portal_loopback curl -fsS http://127.0.0.1:8765/api/health
run facade_health curl -fsS http://127.0.0.1/healthz
run facade_ready curl -fsS http://127.0.0.1/readyz
run lan_home curl -fsS http://digua.local/
run avahi avahi-browse -art
run service_access service_status digua-product-access.service
run service_portal service_status openclaw-gateway.service
run service_qwen service_status qwen25-local-openai-gateway.service
run sockets ss -lntp
run doctor digua-doctor
if command -v tailscale >/dev/null; then run tailscale_version tailscale version; run tailscale_status tailscale status --json; run tailscale_serve tailscale serve status --json; fi
if command -v cloudflared >/dev/null; then run cloudflared_version cloudflared version; run cloudflared_status systemctl status --no-pager cloudflared.service; fi
printf 'Automated validation completed. Manual phone, deny-path, reboot, outage and rollback drills remain required.\n'
exit "$failed"
