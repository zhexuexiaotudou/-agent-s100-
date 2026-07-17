#!/usr/bin/env bash
set -euo pipefail

APPLY=0
SOURCE_ROOT=""
TARGET="${HOME}/.config/systemd/user/openclaw-gateway.service"
BACKUP_BASE="/mnt/nas/openclaw/reports/product_delivery/openclaw_unit_backups"
SERVICE="openclaw-gateway.service"
PORTAL_HEALTH="http://127.0.0.1:8765/api/health"
QWEN_HEALTH="http://127.0.0.1:18080/health"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --source-root) SOURCE_ROOT="${2:-}"; shift 2 ;;
    --target) TARGET="${2:-}"; shift 2 ;;
    --backup-base) BACKUP_BASE="${2:-}"; shift 2 ;;
    --service) SERVICE="${2:-}"; shift 2 ;;
    --portal-health) PORTAL_HEALTH="${2:-}"; shift 2 ;;
    --qwen-health) QWEN_HEALTH="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -n "$SOURCE_ROOT" ]] || SOURCE_ROOT="$ROOT_DIR"
SOURCE="$SOURCE_ROOT/configs/systemd/openclaw-gateway.service"

[[ "$TARGET" == /* && "$TARGET" != "/" ]] || { printf 'unsafe target\n' >&2; exit 2; }
[[ "$BACKUP_BASE" == /* && "$BACKUP_BASE" != "/" ]] || { printf 'unsafe backup base\n' >&2; exit 2; }
[[ "$SERVICE" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || { printf 'unsafe service name\n' >&2; exit 2; }

blockers=()
[[ -r "$SOURCE" ]] || blockers+=("source_missing")
[[ -f "$TARGET" ]] || blockers+=("target_missing")
command -v sha256sum >/dev/null || blockers+=("sha256sum_missing")
command -v curl >/dev/null || blockers+=("curl_missing")
command -v systemctl >/dev/null || blockers+=("systemctl_missing")
command -v python3 >/dev/null || blockers+=("python3_missing")
if [[ -r "$SOURCE" ]]; then
  grep -Fq -- '--qwen-gateway-url http://127.0.0.1:18080' "$SOURCE" || blockers+=("canonical_qwen_route_missing")
  grep -Fq -- '--openclaw-model-gateway-url http://127.0.0.1:18080' "$SOURCE" || blockers+=("canonical_model_route_missing")
  if grep -Fq -- '127.0.0.1:8082' "$SOURCE"; then blockers+=("retired_qwen_route_present"); fi
fi
if ! curl -fsS --max-time 3 "$QWEN_HEALTH" >/dev/null 2>&1; then blockers+=("qwen_18080_unhealthy"); fi

source_sha=""
target_sha=""
[[ -r "$SOURCE" ]] && source_sha="$(sha256sum "$SOURCE" | awk '{print $1}')"
[[ -f "$TARGET" ]] && target_sha="$(sha256sum "$TARGET" | awk '{print $1}')"
already_current=0
[[ -n "$source_sha" && "$source_sha" == "$target_sha" ]] && already_current=1

emit() {
  local applied="$1" backup_root="${2:-}"
  APPLY_RESULT="$applied" BACKUP_ROOT="$backup_root" SOURCE_SHA="$source_sha" TARGET_SHA="$target_sha" SERVICE_NAME="$SERVICE" \
    ALREADY_CURRENT="$already_current" BLOCKERS="$(printf '%s\n' "${blockers[@]-}")" python3 - <<'PY'
import json, os
print(json.dumps({
    "ok": not [x for x in os.environ["BLOCKERS"].splitlines() if x],
    "applied": os.environ["APPLY_RESULT"] == "1",
    "already_current": os.environ["ALREADY_CURRENT"] == "1",
    "source_sha256": os.environ["SOURCE_SHA"] or None,
    "previous_target_sha256": os.environ["TARGET_SHA"] or None,
    "backup_root": os.environ["BACKUP_ROOT"] or None,
    "service": os.environ["SERVICE_NAME"],
    "service_scope": "user",
    "desired_qwen_route": "http://127.0.0.1:18080",
    "backend_units_touched": ["openclaw-gateway.service"] if os.environ["APPLY_RESULT"] == "1" else [],
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

backup_root="$BACKUP_BASE/$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$backup_root/openclaw-gateway.service"
mkdir -p "$backup_root"
cp -a "$TARGET" "$backup_file"

restore_previous() {
  cp -a "$backup_file" "$TARGET"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  systemctl --user restart "$SERVICE" >/dev/null 2>&1 || true
}

tmp="$(mktemp "${TARGET}.tmp.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
cp "$SOURCE" "$tmp"
chmod 0644 "$tmp"
mv "$tmp" "$TARGET"

if ! systemctl --user daemon-reload || ! systemctl --user restart "$SERVICE"; then
  restore_previous
  printf 'user service reload or restart failed; restored previous unit\n' >&2
  exit 1
fi

healthy=0
for _ in $(seq 1 30); do
  if systemctl --user is-active --quiet "$SERVICE" \
    && curl -fsS --max-time 3 "$PORTAL_HEALTH" >/dev/null \
    && curl -fsS --max-time 3 "$QWEN_HEALTH" >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
if [[ "$healthy" != "1" ]]; then
  restore_previous
  printf 'portal or Qwen health check failed; restored previous unit\n' >&2
  exit 1
fi

deployed_sha="$(sha256sum "$TARGET" | awk '{print $1}')"
if [[ "$deployed_sha" != "$source_sha" ]]; then
  restore_previous
  printf 'OpenClaw unit hash mismatch; restored previous unit\n' >&2
  exit 1
fi

emit 1 "$backup_root"
