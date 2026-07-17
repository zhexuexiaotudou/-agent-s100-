#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-./validation-results}"
ARCHIVE="${2:-product_access_s100p_results_$(date -u +%Y%m%dT%H%M%SZ).tar.gz}"
[[ -d "$OUT" ]] || { printf 'missing result directory: %s\n' "$OUT" >&2; exit 2; }
if grep -RIEq --exclude='*.sha256' '(-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer[[:space:]]+[A-Za-z0-9._-]{16,}|password[[:space:]]*[:=][[:space:]]*[^<[:space:]]+|cloudflared.*token[[:space:]]+[A-Za-z0-9._-]{16,})' "$OUT"; then
  printf 'possible secret found; inspect and redact before collection\n' >&2
  exit 3
fi
tar -czf "$ARCHIVE" "$OUT"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
printf '%s\n' "$ARCHIVE"
