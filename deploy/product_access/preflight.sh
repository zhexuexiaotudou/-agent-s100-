#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$ROOT_DIR/release/install/product_access_preflight.sh" "$@"
