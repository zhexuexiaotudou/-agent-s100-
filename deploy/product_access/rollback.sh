#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# -lt 1 ]]; then printf 'usage: %s <backup-root> [upgrade options]\n' "$0" >&2; exit 2; fi
backup="$1"; shift
if [[ "$(cat /etc/digua-ai-nas/install-mode 2>/dev/null || true)" == "access-only" ]]; then
  exec bash "$ROOT_DIR/release/install/install_product_access_only.sh" --apply --rollback-from "$backup" "$@"
fi
exec bash "$ROOT_DIR/release/install/upgrade_s100p.sh" --apply --rollback-from "$backup" "$@"
