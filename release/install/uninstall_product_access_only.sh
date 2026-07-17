#!/usr/bin/env bash
set -euo pipefail
INSTALL_ROOT="/opt/digua-ai-nas"
KEEP_APP=0
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --keep-app) KEEP_APP=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
[[ "$INSTALL_ROOT" == /* && "$INSTALL_ROOT" != "/" ]] || { printf 'unsafe install root\n' >&2; exit 2; }
[[ "${EUID:-$(id -u)}" -eq 0 || "$DRY_RUN" == "1" ]] || { printf 'uninstall requires root\n' >&2; exit 2; }
if [[ "$DRY_RUN" == "0" ]]; then
  systemctl disable --now digua-product-access.service digua-product-remote-ingress.service >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/digua-product-access.service /etc/systemd/system/digua-product-remote-ingress.service
  rm -f /etc/avahi/services/digua-ai-nas.service /usr/local/bin/digua-access /usr/local/bin/digua-doctor
  rm -f /etc/digua-ai-nas/install-mode /etc/digua-ai-nas/digua.env
  [[ "$KEEP_APP" == "1" ]] || rm -rf "$INSTALL_ROOT"
  systemctl daemon-reload
fi
python3 - <<PY
import json
print(json.dumps({'ok':True,'dry_run':bool($DRY_RUN),'mode':'access-only','backend_units_touched':[],'state_preserved':'/var/lib/digua-ai-nas','nas_data_touched':False},indent=2))
PY
