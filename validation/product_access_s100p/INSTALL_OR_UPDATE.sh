#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${DIGUA_VALIDATION_OUT:-./validation-results}"
mkdir -p "$OUT/raw"
if [[ -d /opt/digua-ai-nas/app ]]; then
  sudo bash "$ROOT_DIR/deploy/product_access/upgrade.sh" --apply --source-root "$ROOT_DIR" --install-root /opt/digua-ai-nas | tee "$OUT/raw/upgrade.txt"
else
  printf 'Fresh install needs NAS and model arguments. Example:\n' | tee "$OUT/raw/install.txt"
  printf 'sudo deploy/product_access/install.sh --nas-protocol nfs --nas-host <NAS-IP> --nas-share <EXPORT> ...\n' | tee -a "$OUT/raw/install.txt"
  printf 'Run the reviewed command manually so credentials and model paths are not captured by this bundle.\n' | tee -a "$OUT/raw/install.txt"
  exit 2
fi
