#!/usr/bin/env bash
set -euo pipefail

APPLY=0
INSTALL_ROOT="/opt/digua-ai-nas"
AVAHI_TARGET="/etc/avahi/services/digua-ai-nas.service"
JSON_OUT=""
ACCESS_DB="/var/lib/digua-ai-nas/product_access.sqlite3"
PREFERRED_HOSTNAME="digua"
HOSTS_FILE="/etc/hosts"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --avahi-target) AVAHI_TARGET="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    --access-db) ACCESS_DB="${2:-}"; shift 2 ;;
    --hostname) PREFERRED_HOSTNAME="${2:-}"; shift 2 ;;
    --hosts-file) HOSTS_FILE="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
blockers=()
hosts_updated=0
avahi_restarted=0
[[ "$INSTALL_ROOT" == /* && "$INSTALL_ROOT" != "/" ]] || blockers+=("unsafe_install_root")
[[ "$PREFERRED_HOSTNAME" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,62}$ ]] || blockers+=("invalid_hostname")
[[ "$HOSTS_FILE" == /* ]] || blockers+=("hosts_file_must_be_absolute")
if [[ "$APPLY" == "1" ]]; then command -v systemctl >/dev/null || blockers+=("systemctl_missing"); fi
chosen_hostname="$PREFERRED_HOSTNAME"
if command -v avahi-resolve-host-name >/dev/null 2>&1; then
  resolved_ip="$(avahi-resolve-host-name -4 "$PREFERRED_HOSTNAME.local" 2>/dev/null | awk '{print $2}' | head -n1 || true)"
  local_ips="$(hostname -I 2>/dev/null || true)"
  if [[ -n "$resolved_ip" && " $local_ips " != *" $resolved_ip "* ]]; then
    short_id="$(python3 - "$ACCESS_DB" <<'PY'
import sqlite3, sys
try:
    con=sqlite3.connect(sys.argv[1]); value=con.execute("SELECT value FROM product_meta WHERE key='device_id'").fetchone()[0]; print(value.replace('-','')[:8])
except Exception:
    print('device')
PY
)"
    chosen_hostname="digua-$short_id"
  fi
fi
if [[ "$APPLY" == "1" && "${#blockers[@]}" -eq 0 ]]; then
  hostnamectl set-hostname "$chosen_hostname"
  hosts_tmp="$(mktemp "$(dirname "$HOSTS_FILE")/.hosts.XXXXXX")"
  awk -v host="$chosen_hostname" '
    BEGIN { updated=0 }
    $1 == "127.0.1.1" { print "127.0.1.1\t" host; updated=1; next }
    { print }
    END { if (!updated) print "127.0.1.1\t" host }
  ' "$HOSTS_FILE" > "$hosts_tmp"
  chmod --reference="$HOSTS_FILE" "$hosts_tmp"; chown --reference="$HOSTS_FILE" "$hosts_tmp"; mv "$hosts_tmp" "$HOSTS_FILE"
  hosts_updated=1
  python3 - "$ACCESS_DB" "$chosen_hostname" <<'PY'
import json, sqlite3, sys
con=sqlite3.connect(sys.argv[1])
con.execute("INSERT INTO product_meta(key,value,updated_at) VALUES('hostname',?,datetime('now')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",(sys.argv[2],))
con.execute("INSERT INTO endpoints(channel,url,enabled,verified,details_json,updated_at) VALUES('lan_mdns',?,1,0,?,datetime('now')) ON CONFLICT(channel) DO UPDATE SET url=excluded.url,enabled=1,verified=0,details_json=excluded.details_json,updated_at=excluded.updated_at",(f"http://{sys.argv[2]}.local/",json.dumps({'fallback':'device IPv4 address'})))
con.commit()
PY
  install -d -m 0755 "$(dirname "$AVAHI_TARGET")"
  install -m 0644 "$ROOT_DIR/release/avahi/digua-ai-nas.service" "$AVAHI_TARGET"
  systemctl enable --now digua-product-access.service
  if systemctl list-unit-files avahi-daemon.service >/dev/null 2>&1; then
    systemctl enable --now avahi-daemon.service
    systemctl restart avahi-daemon.service
    avahi_restarted=1
  fi
fi

blockers_json="$(printf '%s\n' "${blockers[@]-}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(BLOCKERS_JSON="$blockers_json" python3 - <<PY
import json, os
print(json.dumps({
  'ok': not json.loads(os.environ['BLOCKERS_JSON']), 'applied': bool($APPLY),
  'lan_url': 'http://$chosen_hostname.local/', 'preferred_hostname': '$PREFERRED_HOSTNAME', 'chosen_hostname': '$chosen_hostname', 'fallback': 'http://<S100P-LAN-IP>/',
  'backend': 'http://127.0.0.1:8765', 'router_port_forwarding_changed': False,
  'upnp_changed': False, 'production_verified': False,
  'hosts_entry_synchronized': bool($hosts_updated), 'avahi_restarted': bool($avahi_restarted),
  'blockers': json.loads(os.environ['BLOCKERS_JSON']),
}, ensure_ascii=False, indent=2))
PY
)"
[[ -z "$JSON_OUT" ]] || { mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; }
printf '%s\n' "$payload"
[[ "${#blockers[@]}" -eq 0 ]]
