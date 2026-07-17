#!/usr/bin/env bash
set -euo pipefail

JSON_OUT=""
SIMULATE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    --simulate) SIMULATE=1; shift ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

python_bin="$(command -v python3 || true)"
systemctl_bin="$(command -v systemctl || true)"
avahi_bin="$(command -v avahi-daemon || true)"
tailscale_bin="$(command -v tailscale || true)"
cloudflared_bin="$(command -v cloudflared || true)"
blockers=()
warnings=()
arch="$(uname -m 2>/dev/null || true)"
os_id="$(. /etc/os-release 2>/dev/null && printf '%s' "${ID:-unknown}" || printf unknown)"
[[ -n "$python_bin" ]] || blockers+=("python3_missing")
if [[ "$SIMULATE" == "0" ]]; then
  [[ "$(uname -s)" == "Linux" ]] || blockers+=("linux_required")
  [[ "$arch" == "aarch64" || "$arch" == "arm64" ]] || blockers+=("arm64_required")
  [[ "$os_id" == "ubuntu" ]] || blockers+=("ubuntu_required")
  [[ -n "$systemctl_bin" ]] || blockers+=("systemd_missing")
  command -v nmcli >/dev/null || blockers+=("networkmanager_missing")
  [[ -n "$avahi_bin" ]] || warnings+=("avahi_will_be_installed")
fi

payload="$(SIMULATE="$SIMULATE" ARCH="$arch" OS_ID="$os_id" PYTHON_BIN="$python_bin" SYSTEMCTL_BIN="$systemctl_bin" AVAHI_BIN="$avahi_bin" TAILSCALE_BIN="$tailscale_bin" CLOUDFLARED_BIN="$cloudflared_bin" BLOCKERS="$(printf '%s\n' "${blockers[@]-}")" WARNINGS="$(printf '%s\n' "${warnings[@]-}")" python3 - <<'PY'
import json, os
blockers=[x for x in os.environ['BLOCKERS'].splitlines() if x]
print(json.dumps({
  'ok': not blockers,
  'simulation': bool(int(os.environ.get('SIMULATE','0'))),
  'production_verified': False,
  'architecture': os.environ['ARCH'], 'os_id': os.environ['OS_ID'],
  'required': {'python3': bool(os.environ['PYTHON_BIN']), 'systemd': bool(os.environ['SYSTEMCTL_BIN'])},
  'optional': {'avahi': bool(os.environ['AVAHI_BIN']), 'tailscale': bool(os.environ['TAILSCALE_BIN']), 'cloudflared': bool(os.environ['CLOUDFLARED_BIN'])},
  'remote_access_default_enabled': False,
  'blockers': blockers,
  'warnings': [x for x in os.environ['WARNINGS'].splitlines() if x],
}, ensure_ascii=False, indent=2))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
[[ "${#blockers[@]}" -eq 0 ]]
