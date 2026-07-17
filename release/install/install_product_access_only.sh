#!/usr/bin/env bash
set -euo pipefail

APPLY=0
SOURCE_ROOT=""
INSTALL_ROOT="/opt/digua-ai-nas"
NAS_MOUNT="/mnt/nas/openclaw"
SERVICE_USER="${SUDO_USER:-$(id -un)}"
SKIP_PIP=0
SIM_ROOT=""
ROLLBACK_FROM=""
JSON_OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --source-root) SOURCE_ROOT="${2:-}"; shift 2 ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --nas-mount|--mount-point) NAS_MOUNT="${2:-}"; shift 2 ;;
    --service-user) SERVICE_USER="${2:-}"; shift 2 ;;
    --skip-pip) SKIP_PIP=1; shift ;;
    --simulate-root) SIM_ROOT="${2:-}"; APPLY=1; SKIP_PIP=1; shift 2 ;;
    --rollback-from) ROLLBACK_FROM="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -n "$SOURCE_ROOT" ]] || SOURCE_ROOT="$ROOT_DIR"
[[ "$INSTALL_ROOT" == /* && "$INSTALL_ROOT" != "/" ]] || { printf 'unsafe install root\n' >&2; exit 2; }
[[ "$NAS_MOUNT" == /* && "$NAS_MOUNT" != "/" ]] || { printf 'unsafe NAS mount\n' >&2; exit 2; }
[[ "$SERVICE_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || { printf 'unsafe service user\n' >&2; exit 2; }
if [[ -n "$SIM_ROOT" ]]; then
  [[ "$SIM_ROOT" == /* && "$SIM_ROOT" != "/" ]] || { printf 'unsafe simulation root\n' >&2; exit 2; }
  INSTALL_ROOT="$SIM_ROOT/opt/digua-ai-nas"
  ENV_FILE="$SIM_ROOT/etc/digua-ai-nas/digua.env"
  MODE_FILE="$SIM_ROOT/etc/digua-ai-nas/install-mode"
  STATE_DIR="$SIM_ROOT/var/lib/digua-ai-nas"
  UNIT_DIR="$SIM_ROOT/etc/systemd/system"
  AVAHI_TARGET="$SIM_ROOT/etc/avahi/services/digua-ai-nas.service"
else
  ENV_FILE="/etc/digua-ai-nas/digua.env"
  MODE_FILE="/etc/digua-ai-nas/install-mode"
  STATE_DIR="/var/lib/digua-ai-nas"
  UNIT_DIR="/etc/systemd/system"
  AVAHI_TARGET="/etc/avahi/services/digua-ai-nas.service"
fi

if [[ "$APPLY" == "1" && -z "$SIM_ROOT" && "${EUID:-$(id -u)}" -ne 0 ]]; then
  printf 'access-only apply requires root\n' >&2; exit 2
fi
if [[ -n "$ROLLBACK_FROM" ]]; then
  [[ -d "$ROLLBACK_FROM/app" ]] || { printf 'invalid access-only backup: %s\n' "$ROLLBACK_FROM" >&2; exit 2; }
  SOURCE_ROOT="$ROLLBACK_FROM/app"
fi

required=(
  src/product_access scripts/probes/ai_nas_identity.py scripts/digua-access scripts/digua-doctor
  web/ai_nas_desktop_v2.html web/static/digua_ai_nas_v2.css web/static/digua_ai_nas_v2.js
  web/static/pwa-icon-192.svg web/static/pwa-icon-512.svg requirements.txt
  release/systemd/digua-product-access.service release/systemd/digua-product-remote-ingress.service
  release/avahi/digua-ai-nas.service release/install/configure_lan_access.sh
)
blockers=()
remote_was_active=0
if [[ -z "$SIM_ROOT" ]] && systemctl is-active --quiet digua-product-remote-ingress.service 2>/dev/null; then remote_was_active=1; fi
for rel in "${required[@]}"; do [[ -e "$SOURCE_ROOT/$rel" ]] || blockers+=("missing_source:$rel"); done
if [[ -z "$SIM_ROOT" ]]; then
  curl -fsS http://127.0.0.1:8765/api/health >/dev/null || blockers+=("existing_portal_8765_unhealthy")
  findmnt "$NAS_MOUNT" >/dev/null || blockers+=("nas_mount_missing")
fi
if [[ "$APPLY" == "0" || "${#blockers[@]}" -gt 0 ]]; then
  BLOCKERS="$(printf '%s\n' "${blockers[@]-}")" python3 - <<PY
import json, os
b=[x for x in os.environ['BLOCKERS'].splitlines() if x]
print(json.dumps({'ok':not b,'applied':False,'mode':'access-only','existing_backend_preserved':True,'blockers':b},ensure_ascii=False,indent=2))
PY
  [[ "${#blockers[@]}" -eq 0 ]]; exit
fi

backup_root=""
if [[ -z "$SIM_ROOT" && -d "$INSTALL_ROOT/app" && -z "$ROLLBACK_FROM" ]]; then
  backup_root="/var/backups/digua-ai-nas/access-only-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$backup_root"
  cp -a "$INSTALL_ROOT/app" "$backup_root/app"
fi
mkdir -p "$INSTALL_ROOT/app" "$STATE_DIR" "$(dirname "$ENV_FILE")" "$UNIT_DIR" "$(dirname "$AVAHI_TARGET")"
for rel in "${required[@]}"; do
  target="$INSTALL_ROOT/app/$rel"
  mkdir -p "$(dirname "$target")"
  rm -rf "$target"
  cp -a "$SOURCE_ROOT/$rel" "$target"
done

if [[ ! -x "$INSTALL_ROOT/venv/bin/python" ]]; then python3 -m venv --system-site-packages "$INSTALL_ROOT/venv"; fi
if [[ "$SKIP_PIP" == "0" ]]; then "$INSTALL_ROOT/venv/bin/pip" install -r "$INSTALL_ROOT/app/requirements.txt"; fi

env_tmp="$(mktemp)"
{
  printf 'DIGUA_INSTALL_ROOT=%s\n' "$INSTALL_ROOT"
  printf 'DIGUA_NAS_MOUNT=%s\n' "$NAS_MOUNT"
  printf 'DIGUA_PERSONAL_ROOT=%s/Personal\n' "$NAS_MOUNT"
  printf 'AI_NAS_PERSONAL_ROOT=%s/Personal\n' "$NAS_MOUNT"
  printf 'AI_NAS_REPORT_ROOT=%s/reports/qwen25_ai_nas\n' "$NAS_MOUNT"
  printf 'DIGUA_OPENCLAW_BASE_URL=http://127.0.0.1:8765\n'
  printf 'DIGUA_QWEN_BASE_URL=http://127.0.0.1:18080\n'
  printf 'DIGUA_ACCESS_DB=%s/product_access.sqlite3\n' "$STATE_DIR"
  printf 'DIGUA_IDENTITY_DB=%s/identity.sqlite3\n' "$STATE_DIR"
  printf 'DIGUA_UPSTREAM_IDENTITY_DB=%s/reports/qwen25_ai_nas/identity.sqlite3\n' "$NAS_MOUNT"
  printf 'DIGUA_LAN_URL=http://digua.local/\n'
  printf 'DIGUA_REMOTE_ACCESS_ENABLED=0\n'
  grep -E '^(DIGUA_CF_TEAM_DOMAIN|DIGUA_CF_AUDIENCE)=' "$ENV_FILE" 2>/dev/null || true
} > "$env_tmp"
mv "$env_tmp" "$ENV_FILE"; chmod 0644 "$ENV_FILE"
printf 'access-only\n' > "$MODE_FILE"; chmod 0644 "$MODE_FILE"

legacy_identity="$NAS_MOUNT/reports/qwen25_ai_nas/identity.sqlite3"
if [[ ! -f "$STATE_DIR/identity.sqlite3" && -f "$legacy_identity" ]]; then cp -a "$legacy_identity" "$STATE_DIR/identity.sqlite3"; fi
PYTHONPATH="$INSTALL_ROOT/app" "$INSTALL_ROOT/venv/bin/python" -m src.product_access.cli --access-db "$STATE_DIR/product_access.sqlite3" --identity-db "$STATE_DIR/identity.sqlite3" status >/dev/null

render_unit() {
  local name="$1"
  sed -e "s|@DIGUA_INSTALL_ROOT@|$INSTALL_ROOT|g" -e "s|@DIGUA_PERSONAL_ROOT@|$NAS_MOUNT/Personal|g" \
    -e "s|@DIGUA_REPORT_ROOT@|$NAS_MOUNT/reports/qwen25_ai_nas|g" -e "s|@DIGUA_ENV_FILE@|$ENV_FILE|g" \
    -e "s|@DIGUA_USER_DIRECTIVE@|User=$SERVICE_USER|g" "$INSTALL_ROOT/app/release/systemd/$name" > "$UNIT_DIR/$name"
}
render_unit digua-product-access.service
render_unit digua-product-remote-ingress.service
cp "$INSTALL_ROOT/app/release/avahi/digua-ai-nas.service" "$AVAHI_TARGET"

if [[ -z "$SIM_ROOT" ]]; then
  chown -R "$SERVICE_USER" "$STATE_DIR"
  chmod 0755 "$INSTALL_ROOT/app/scripts/digua-access" "$INSTALL_ROOT/app/scripts/digua-doctor"
  ln -sfn "$INSTALL_ROOT/app/scripts/digua-access" /usr/local/bin/digua-access
  ln -sfn "$INSTALL_ROOT/app/scripts/digua-doctor" /usr/local/bin/digua-doctor
  systemctl daemon-reload
  systemctl enable --now digua-product-access.service
  if [[ "$remote_was_active" == "1" ]]; then
    systemctl start digua-product-remote-ingress.service
  else
    systemctl disable --now digua-product-remote-ingress.service >/dev/null 2>&1 || true
  fi
  bash "$INSTALL_ROOT/app/release/install/configure_lan_access.sh" --apply --install-root "$INSTALL_ROOT" --access-db "$STATE_DIR/product_access.sqlite3" >/dev/null
  PYTHONPATH="$INSTALL_ROOT/app" "$INSTALL_ROOT/venv/bin/python" -m src.product_access.cli --access-db "$STATE_DIR/product_access.sqlite3" --identity-db "$STATE_DIR/identity.sqlite3" card --output "$STATE_DIR/access-card.html" >/dev/null
fi

payload="$(BACKUP_ROOT="$backup_root" python3 - <<PY
import json, os
print(json.dumps({'ok':True,'applied':True,'mode':'access-only','simulation':bool('$SIM_ROOT'),'install_root':'$INSTALL_ROOT','nas_mount':'$NAS_MOUNT','service_user':'$SERVICE_USER','existing_backend_preserved':True,'backend_units_touched':[],'remote_ingress_was_active':bool($remote_was_active),'remote_ingress_default_enabled':False,'backup_root':os.environ['BACKUP_ROOT'] or None,'production_verified':False},ensure_ascii=False,indent=2))
PY
)"
[[ -z "$JSON_OUT" ]] || { mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; }
printf '%s\n' "$payload"
