#!/usr/bin/env bash
set -u

DRY_RUN=1
INSTALL_ROOT="/opt/digua-ai-nas"
BACKUP_ROOT=""
ROLLBACK_FROM=""
SOURCE_ROOT=""
SYSTEMD_MODE="system"
SKIP_SYSTEMD=0
JSON_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --backup-root) BACKUP_ROOT="${2:-}"; shift 2 ;;
    --rollback-from) ROLLBACK_FROM="${2:-}"; shift 2 ;;
    --source-root) SOURCE_ROOT="${2:-}"; shift 2 ;;
    --systemd-mode) SYSTEMD_MODE="${2:-}"; shift 2 ;;
    --skip-systemd) SKIP_SYSTEMD=1; shift ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

BACKUP_ROOT="${BACKUP_ROOT:-${INSTALL_ROOT}_backup_$(date +%Y%m%d-%H%M%S)}"
blockers=()
[[ "$INSTALL_ROOT" == /* && "$INSTALL_ROOT" != "/" && "$INSTALL_ROOT" != "/opt" ]] || blockers+=("unsafe_install_root")
[[ "$SYSTEMD_MODE" == "user" || "$SYSTEMD_MODE" == "system" ]] || blockers+=("unsupported_systemd_mode")
[[ -d "$INSTALL_ROOT" || "$DRY_RUN" == "1" ]] || blockers+=("install_root_missing")
operation="backup"
if [[ -n "$ROLLBACK_FROM" ]]; then
  operation="rollback"
  [[ "$ROLLBACK_FROM" == /* && "$ROLLBACK_FROM" != "/" && "$ROLLBACK_FROM" != "$INSTALL_ROOT" ]] || blockers+=("unsafe_rollback_root")
  [[ -d "$ROLLBACK_FROM" || "$DRY_RUN" == "1" ]] || blockers+=("rollback_root_missing")
elif [[ -n "$SOURCE_ROOT" ]]; then
  operation="upgrade"
  [[ -d "$SOURCE_ROOT" || "$DRY_RUN" == "1" ]] || blockers+=("source_root_missing")
fi

systemctl_cmd=(systemctl); [[ "$SYSTEMD_MODE" == "user" ]] && systemctl_cmd=(systemctl --user)
units=(openclaw-gateway.service qwen25-local-openai-gateway.service digua-ai-index-worker.service digua-product-access.service)
remote_unit="digua-product-remote-ingress.service"
remote_was_active=0
failed_copy="${INSTALL_ROOT}_failed_$(date +%Y%m%d-%H%M%S)"
if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  if [[ "$SKIP_SYSTEMD" == "0" ]]; then
    if "${systemctl_cmd[@]}" is-active --quiet "$remote_unit"; then remote_was_active=1; "${systemctl_cmd[@]}" stop "$remote_unit" || blockers+=("remote_service_stop_failed"); fi
    "${systemctl_cmd[@]}" stop "${units[@]}" || blockers+=("service_stop_failed")
  fi
  if [[ "${#blockers[@]}" -eq 0 && "$operation" == "rollback" ]]; then
    mv "$INSTALL_ROOT" "$failed_copy" || blockers+=("current_install_preserve_failed")
    if [[ "${#blockers[@]}" -eq 0 ]] && ! cp -a "$ROLLBACK_FROM" "$INSTALL_ROOT"; then
      mv "$failed_copy" "$INSTALL_ROOT" 2>/dev/null || true
      blockers+=("rollback_restore_failed")
    fi
  else
    mkdir -p "$BACKUP_ROOT"
    cp -a "$INSTALL_ROOT/." "$BACKUP_ROOT/" || blockers+=("backup_failed")
    if [[ "$operation" == "upgrade" && "${#blockers[@]}" -eq 0 ]]; then
      staging="${INSTALL_ROOT}_staging_$$"
      cp -a "$SOURCE_ROOT" "$staging" || blockers+=("upgrade_staging_failed")
      if [[ "${#blockers[@]}" -eq 0 ]]; then
        if ! mv "$INSTALL_ROOT" "$failed_copy"; then
          blockers+=("upgrade_current_preserve_failed")
        elif ! mv "$staging" "$INSTALL_ROOT"; then
          mv "$failed_copy" "$INSTALL_ROOT" 2>/dev/null || true
          blockers+=("upgrade_swap_failed")
        fi
      fi
    fi
  fi
  if [[ "$SKIP_SYSTEMD" == "0" ]]; then
    "${systemctl_cmd[@]}" start "${units[@]}" || blockers+=("service_restart_failed")
    if [[ "$remote_was_active" == "1" ]]; then "${systemctl_cmd[@]}" start "$remote_unit" || blockers+=("remote_service_restart_failed"); fi
  fi
fi

ok=1; [[ "${#blockers[@]}" -eq 0 ]] || ok=0
blockers_json="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(BLOCKERS_JSON="$blockers_json" OPERATION="$operation" INSTALL_ROOT="$INSTALL_ROOT" BACKUP_ROOT="$BACKUP_ROOT" ROLLBACK_FROM="$ROLLBACK_FROM" FAILED_COPY="$failed_copy" python3 - <<PY
import json, os
print(json.dumps({
  "ok": bool($ok), "dry_run": bool($DRY_RUN), "operation": os.environ["OPERATION"],
  "install_root": os.environ["INSTALL_ROOT"], "backup_root": os.environ["BACKUP_ROOT"],
  "rollback_from": os.environ["ROLLBACK_FROM"], "failed_install_preserved_at": os.environ["FAILED_COPY"],
  "nas_data_removed": False, "db_migration_destructive": False,
  "remote_ingress_was_active": bool($remote_was_active),
  "rollback_command": "bash release/install/upgrade_s100p.sh --apply --rollback-from " + os.environ["BACKUP_ROOT"] + " --install-root " + os.environ["INSTALL_ROOT"],
  "blockers": json.loads(os.environ["BLOCKERS_JSON"]),
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
