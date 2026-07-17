#!/usr/bin/env bash
set -euo pipefail

APPLY=0
SOURCE_ROOT=""
TARGET_ROOT="/mnt/nas/openclaw/scripts/probes"
BACKUP_BASE="/mnt/nas/openclaw/reports/product_delivery/album_runtime_backups"
SERVICE="openclaw-gateway.service"
PORTAL_HEALTH="http://127.0.0.1:8765/api/health"
ROLLBACK_FROM=""
FILES=(ai_nas_media.py ai_nas_operator_portal_server.py)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --source-root) SOURCE_ROOT="${2:-}"; shift 2 ;;
    --target-root) TARGET_ROOT="${2:-}"; shift 2 ;;
    --backup-base) BACKUP_BASE="${2:-}"; shift 2 ;;
    --service) SERVICE="${2:-}"; shift 2 ;;
    --portal-health) PORTAL_HEALTH="${2:-}"; shift 2 ;;
    --rollback-from) ROLLBACK_FROM="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -n "$SOURCE_ROOT" ]] || SOURCE_ROOT="$ROOT_DIR"
SOURCE_DIR="$SOURCE_ROOT/scripts/probes"
[[ -z "$ROLLBACK_FROM" ]] || SOURCE_DIR="$ROLLBACK_FROM"

[[ "$TARGET_ROOT" == /* && "$TARGET_ROOT" != "/" ]] || { printf 'unsafe target root\n' >&2; exit 2; }
[[ "$BACKUP_BASE" == /* && "$BACKUP_BASE" != "/" ]] || { printf 'unsafe backup base\n' >&2; exit 2; }
[[ "$SERVICE" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || { printf 'unsafe service name\n' >&2; exit 2; }

blockers=()
command -v sha256sum >/dev/null || blockers+=("sha256sum_missing")
command -v curl >/dev/null || blockers+=("curl_missing")
command -v systemctl >/dev/null || blockers+=("systemctl_missing")
command -v python3 >/dev/null || blockers+=("python3_missing")
for name in "${FILES[@]}"; do
  [[ -r "$SOURCE_DIR/$name" ]] || blockers+=("source_missing:$name")
  [[ -f "$TARGET_ROOT/$name" ]] || blockers+=("target_missing:$name")
done

hash_manifest() {
  local root="$1" name
  for name in "${FILES[@]}"; do
    [[ -f "$root/$name" ]] && printf '%s:%s\n' "$name" "$(sha256sum "$root/$name" | awk '{print $1}')"
  done
}

source_hashes="$(hash_manifest "$SOURCE_DIR")"
target_hashes="$(hash_manifest "$TARGET_ROOT")"
already_current=0
[[ -n "$source_hashes" && "$source_hashes" == "$target_hashes" ]] && already_current=1

emit() {
  local applied="$1" backup_root="${2:-}"
  APPLY_RESULT="$applied" BACKUP_ROOT="$backup_root" SOURCE_HASHES="$source_hashes" TARGET_HASHES="$target_hashes" \
    SERVICE_NAME="$SERVICE" ALREADY_CURRENT="$already_current" BLOCKERS="$(printf '%s\n' "${blockers[@]-}")" python3 - <<'PY'
import json, os
print(json.dumps({
    "ok": not [x for x in os.environ["BLOCKERS"].splitlines() if x],
    "applied": os.environ["APPLY_RESULT"] == "1",
    "already_current": os.environ["ALREADY_CURRENT"] == "1",
    "source_hashes": os.environ["SOURCE_HASHES"].splitlines(),
    "previous_target_hashes": os.environ["TARGET_HASHES"].splitlines(),
    "backup_root": os.environ["BACKUP_ROOT"] or None,
    "service": os.environ["SERVICE_NAME"],
    "service_scope": "user",
    "backend_units_touched": ["openclaw-gateway.service"] if os.environ["APPLY_RESULT"] == "1" else [],
    "qwen_units_touched": [],
    "blockers": [x for x in os.environ["BLOCKERS"].splitlines() if x],
}, ensure_ascii=False, indent=2))
PY
}

if [[ "$APPLY" == "0" || "${#blockers[@]}" -gt 0 ]]; then
  emit 0
  [[ "${#blockers[@]}" -eq 0 ]]
  exit
fi
if [[ "$already_current" == "1" ]]; then emit 0; exit 0; fi

python3 - "$SOURCE_DIR" "${FILES[@]}" <<'PY'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in sys.argv[2:]:
    source = (root / name).read_text(encoding="utf-8")
    compile(source, str(root / name), "exec")
PY

backup_root="$BACKUP_BASE/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_root"
for name in "${FILES[@]}"; do cp -a "$TARGET_ROOT/$name" "$backup_root/$name"; done

restore_previous() {
  local name
  for name in "${FILES[@]}"; do cp -a "$backup_root/$name" "$TARGET_ROOT/$name"; done
  systemctl --user restart "$SERVICE" >/dev/null 2>&1 || true
}

stage_root="$(mktemp -d)"
trap 'rm -rf "$stage_root"' EXIT
for name in "${FILES[@]}"; do
  cp "$SOURCE_DIR/$name" "$stage_root/$name"
  chmod 0644 "$stage_root/$name"
  mv "$stage_root/$name" "$TARGET_ROOT/$name"
done

if ! systemctl --user restart "$SERVICE"; then
  restore_previous
  printf 'user service restart failed; restored previous album runtime\n' >&2
  exit 1
fi

healthy=0
for _ in $(seq 1 20); do
  if systemctl --user is-active --quiet "$SERVICE" && curl -fsS --max-time 3 "$PORTAL_HEALTH" >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
if [[ "$healthy" != "1" ]]; then
  restore_previous
  printf 'portal health check failed; restored previous album runtime\n' >&2
  exit 1
fi

deployed_hashes="$(hash_manifest "$TARGET_ROOT")"
if [[ "$deployed_hashes" != "$source_hashes" ]]; then
  restore_previous
  printf 'album runtime hash mismatch; restored previous runtime\n' >&2
  exit 1
fi

emit 1 "$backup_root"
