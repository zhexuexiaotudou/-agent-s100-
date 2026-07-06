#!/usr/bin/env bash
set -u

DRY_RUN=1
INSTALL_ROOT="/opt/digua-ai-nas"
BACKUP_ROOT=""
JSON_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --backup-root) BACKUP_ROOT="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

BACKUP_ROOT="${BACKUP_ROOT:-${INSTALL_ROOT}_backup_$(date +%Y%m%d-%H%M%S)}"
blockers=()
[[ -d "$INSTALL_ROOT" || "$DRY_RUN" == "1" ]] || blockers+=("install_root_missing")
if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  mkdir -p "$BACKUP_ROOT"
  cp -a "$INSTALL_ROOT/." "$BACKUP_ROOT/" || blockers+=("backup_failed")
fi
ok=1
[[ "${#blockers[@]}" -eq 0 ]] || ok=0
blockers_json="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(BLOCKERS_JSON="$blockers_json" python3 - <<PY
import json, os
payload={
  "ok": bool($ok),
  "dry_run": bool($DRY_RUN),
  "install_root": "$INSTALL_ROOT",
  "backup_root": "$BACKUP_ROOT",
  "config_backup_required": True,
  "rollback_command": "bash release/install/upgrade_s100p.sh --rollback-from $BACKUP_ROOT",
  "db_migration_destructive": False,
  "blockers": json.loads(os.environ["BLOCKERS_JSON"]),
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
