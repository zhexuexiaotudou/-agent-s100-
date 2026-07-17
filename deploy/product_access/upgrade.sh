#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "$(cat /etc/digua-ai-nas/install-mode 2>/dev/null || true)" == "access-only" ]]; then
  exec bash "$ROOT_DIR/release/install/install_product_access_only.sh" --apply "$@"
fi
exec bash "$ROOT_DIR/release/install/upgrade_s100p.sh" "$@"
