#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# -lt 1 ]]; then printf 'usage: %s <backup-root> [upgrade options]\n' "$0" >&2; exit 2; fi
backup="$1"; shift
exec bash "$ROOT_DIR/release/install/upgrade_s100p.sh" --apply --rollback-from "$backup" "$@"
