#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then printf 'run with sudo: sudo %s\n' "$0" >&2; exit 2; fi
if [[ "${DIGUA_SKIP_OS_PACKAGES:-0}" != "1" ]]; then
  command -v apt-get >/dev/null || { printf 'apt-get is required unless DIGUA_SKIP_OS_PACKAGES=1\n' >&2; exit 2; }
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y python3 python3-venv avahi-daemon avahi-utils libnss-mdns network-manager nfs-common cifs-utils curl
fi
bash "$ROOT_DIR/release/install/product_access_preflight.sh"
if [[ "${1:-}" == "--access-only" ]]; then
  shift
  exec bash "$ROOT_DIR/release/install/install_product_access_only.sh" --apply "$@"
fi
if [[ $# -eq 0 ]]; then
  exec python3 "$ROOT_DIR/release/install/deploy_wizard.py" --product-access
fi
install_root="${DIGUA_INSTALL_ROOT:-/opt/digua-ai-nas}"
mount_point="${DIGUA_NAS_MOUNT:-/mnt/nas/openclaw}"
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  case "${args[$i]}" in
    --install-root) install_root="${args[$((i+1))]:-}" ;;
    --mount-point|--nas-mount) mount_point="${args[$((i+1))]:-}" ;;
  esac
done
bash "$ROOT_DIR/release/install/install_s100p.sh" --defer-admin-claim "$@"
access_db="${DIGUA_ACCESS_DB:-/var/lib/digua-ai-nas/product_access.sqlite3}"
identity_db="${DIGUA_IDENTITY_DB:-/var/lib/digua-ai-nas/identity.sqlite3}"
bash "$ROOT_DIR/release/install/configure_lan_access.sh" --apply --install-root "$install_root" --access-db "$access_db"
(cd "$install_root/app" && "$install_root/venv/bin/python" -m src.product_access.cli --access-db "$access_db" --identity-db "$identity_db" claim-create --qr-out /var/lib/digua-ai-nas/claim-qr.svg)
(cd "$install_root/app" && "$install_root/venv/bin/python" -m src.product_access.cli --access-db "$access_db" --identity-db "$identity_db" card --output /var/lib/digua-ai-nas/access-card.html)
printf 'Open http://digua.local/setup from a phone on the same LAN. Claim text was displayed once above.\n'
