#!/usr/bin/env bash
set -u

DRY_RUN=1
SIMULATION=0
PROTOCOL="local"
NAS_HOST=""
NAS_SHARE=""
MOUNT_POINT="/mnt/nas/openclaw"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
CREDENTIALS_FILE=""
FSTAB_PATH="/etc/fstab"
ALLOW_LOCAL=0
WRITE_USER=""
JSON_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --simulate) SIMULATION=1; DRY_RUN=0; shift ;;
    --nas-protocol|--protocol) PROTOCOL="${2:-}"; shift 2 ;;
    --nas-host) NAS_HOST="${2:-}"; shift 2 ;;
    --nas-share) NAS_SHARE="${2:-}"; shift 2 ;;
    --mount-point|--nas-mount) MOUNT_POINT="${2:-}"; shift 2 ;;
    --personal-root) PERSONAL_ROOT="${2:-}"; shift 2 ;;
    --credentials-file) CREDENTIALS_FILE="${2:-}"; shift 2 ;;
    --fstab-path) FSTAB_PATH="${2:-}"; shift 2 ;;
    --allow-local-storage) ALLOW_LOCAL=1; shift ;;
    --write-user) WRITE_USER="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

blockers=()
warnings=()
[[ -z "$WRITE_USER" || "$WRITE_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || blockers+=("write_user_contains_unsafe_characters")
case "$PROTOCOL" in nfs|smb|cifs|local) ;; *) blockers+=("unsupported_protocol:$PROTOCOL") ;; esac
[[ "$MOUNT_POINT" == /* && "$MOUNT_POINT" != "/" ]] || blockers+=("unsafe_mount_point")
[[ "$PERSONAL_ROOT" == "$MOUNT_POINT"/* ]] || blockers+=("personal_root_outside_mount")
[[ "$MOUNT_POINT" != *[[:space:]]* && "$PERSONAL_ROOT" != *[[:space:]]* ]] || blockers+=("mount_paths_must_not_contain_whitespace")
[[ "$MOUNT_POINT" =~ ^/[A-Za-z0-9._/-]+$ && "$PERSONAL_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]] || blockers+=("mount_paths_contain_unsafe_characters")
if [[ "$PROTOCOL" == "local" ]]; then
  [[ "$ALLOW_LOCAL" == "1" || "$SIMULATION" == "1" || "$DRY_RUN" == "1" ]] || blockers+=("local_storage_requires_explicit_allow")
  warnings+=("local_storage_is_not_nas")
else
  [[ -n "$NAS_HOST" ]] || blockers+=("nas_host_required")
  [[ -n "$NAS_SHARE" ]] || blockers+=("nas_share_required")
  [[ "$NAS_HOST" != *[[:space:]]* && "$NAS_SHARE" != *[[:space:]]* ]] || blockers+=("nas_source_must_not_contain_whitespace")
  [[ "$NAS_HOST" =~ ^[A-Za-z0-9._-]+$ ]] || blockers+=("nas_host_contains_unsafe_characters")
  if [[ "$PROTOCOL" == "nfs" ]]; then
    [[ "$NAS_SHARE" =~ ^/[A-Za-z0-9._/-]+$ ]] || blockers+=("nfs_share_contains_unsafe_characters")
  else
    [[ "$NAS_SHARE" =~ ^/?[A-Za-z0-9._/-]+$ ]] || blockers+=("smb_share_contains_unsafe_characters")
  fi
fi
if [[ "$PROTOCOL" == "smb" || "$PROTOCOL" == "cifs" ]]; then
  [[ -n "$CREDENTIALS_FILE" ]] || blockers+=("smb_credentials_file_required")
  [[ "$CREDENTIALS_FILE" != *[[:space:]]* ]] || blockers+=("credentials_path_must_not_contain_whitespace")
  [[ "$CREDENTIALS_FILE" =~ ^/[A-Za-z0-9._/-]+$ ]] || blockers+=("credentials_path_contains_unsafe_characters")
  if [[ "$DRY_RUN" == "0" && "$SIMULATION" == "0" ]]; then
    [[ -f "$CREDENTIALS_FILE" ]] || blockers+=("smb_credentials_file_missing")
    mode="$(stat -c '%a' "$CREDENTIALS_FILE" 2>/dev/null || echo unknown)"
    [[ "$mode" == "600" || "$mode" == "400" ]] || blockers+=("smb_credentials_permissions_must_be_600_or_400:$mode")
  fi
fi

fstab_line=""
if [[ "$PROTOCOL" == "nfs" ]]; then
  fstab_line="${NAS_HOST}:${NAS_SHARE} ${MOUNT_POINT} nfs4 rw,nofail,_netdev,x-systemd.automount 0 0"
elif [[ "$PROTOCOL" == "smb" || "$PROTOCOL" == "cifs" ]]; then
  fstab_line="//${NAS_HOST}/${NAS_SHARE#/} ${MOUNT_POINT} cifs credentials=${CREDENTIALS_FILE},rw,nofail,_netdev,x-systemd.automount,iocharset=utf8 0 0"
fi

mounted_verified=0
write_verified=0
fstab_updated=0
backup_path=""
if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  mkdir -p "$MOUNT_POINT" || blockers+=("mount_point_create_failed")
  if [[ "$PROTOCOL" != "local" && "${#blockers[@]}" -eq 0 ]]; then
    if [[ "$SIMULATION" == "1" ]]; then
      mkdir -p "$(dirname "$FSTAB_PATH")"
    else
      [[ "${EUID:-$(id -u)}" == "0" ]] || blockers+=("root_required_for_nas_mount")
      command -v findmnt >/dev/null 2>&1 || blockers+=("findmnt_missing")
      command -v mount >/dev/null 2>&1 || blockers+=("mount_command_missing")
      [[ "$PROTOCOL" != "nfs" ]] || command -v mount.nfs >/dev/null 2>&1 || blockers+=("mount_nfs_helper_missing")
      [[ "$PROTOCOL" == "nfs" ]] || command -v mount.cifs >/dev/null 2>&1 || blockers+=("mount_cifs_helper_missing")
    fi
  fi

  if [[ -n "$fstab_line" && "${#blockers[@]}" -eq 0 ]]; then
    [[ -e "$FSTAB_PATH" ]] || : > "$FSTAB_PATH"
    backup_path="${FSTAB_PATH}.digua-backup-$(date +%Y%m%d-%H%M%S)"
    cp -a "$FSTAB_PATH" "$backup_path" || blockers+=("fstab_backup_failed")
    if [[ "${#blockers[@]}" -eq 0 ]]; then
      DIGUA_FSTAB_PATH="$FSTAB_PATH" DIGUA_FSTAB_LINE="$fstab_line" python3 - <<'PY' || blockers+=("fstab_update_failed")
import os
from pathlib import Path

path = Path(os.environ["DIGUA_FSTAB_PATH"])
start, end = "# BEGIN DIGUA-AI-NAS", "# END DIGUA-AI-NAS"
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out, skipping = [], False
for line in lines:
    if line.strip() == start:
        skipping = True
        continue
    if line.strip() == end:
        skipping = False
        continue
    if not skipping:
        out.append(line)
out.extend([start, os.environ["DIGUA_FSTAB_LINE"], end])
tmp = path.with_suffix(path.suffix + ".digua.tmp")
tmp.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
tmp.replace(path)
PY
      [[ "${#blockers[@]}" -gt 0 ]] || fstab_updated=1
    fi
  fi

  if [[ "${#blockers[@]}" -eq 0 && "$PROTOCOL" != "local" ]]; then
    if [[ "$SIMULATION" == "1" ]]; then
      printf '{"simulation":true,"nas_backed":false,"protocol":"%s"}\n' "$PROTOCOL" > "$MOUNT_POINT/.digua-simulated-mount.json"
      mounted_verified=1
    else
      current_source="$(findmnt -n -o SOURCE --target "$MOUNT_POINT" 2>/dev/null || true)"
      if [[ -n "$current_source" && "$current_source" != *"$NAS_HOST"* ]]; then
        blockers+=("mount_source_mismatch:$current_source")
      elif [[ -z "$current_source" ]] && ! mount "$MOUNT_POINT"; then
        blockers+=("mount_failed")
      fi
      if [[ "${#blockers[@]}" -eq 0 ]]; then
        current_source="$(findmnt -n -o SOURCE --target "$MOUNT_POINT" 2>/dev/null || true)"
        current_fstype="$(findmnt -n -o FSTYPE --target "$MOUNT_POINT" 2>/dev/null || true)"
        source_ok=0; fstype_ok=0
        [[ "$current_source" == *"$NAS_HOST"* ]] && source_ok=1
        [[ "$current_fstype" == nfs* || "$current_fstype" == "cifs" ]] && fstype_ok=1
        if [[ "$source_ok" == "1" && "$fstype_ok" == "1" ]]; then
          mounted_verified=1
        else
          blockers+=("mounted_source_or_type_unverified:${current_source}:${current_fstype}")
        fi
      fi
    fi
  elif [[ "${#blockers[@]}" -eq 0 ]]; then
    mounted_verified=1
  fi

  if [[ "${#blockers[@]}" -eq 0 ]]; then
    mkdir -p "$PERSONAL_ROOT" || blockers+=("personal_root_create_failed")
    test_file="$PERSONAL_ROOT/.digua_write_test_$$"
    if [[ -n "$WRITE_USER" && "$SIMULATION" == "0" && "${EUID:-$(id -u)}" == "0" ]]; then
      if command -v runuser >/dev/null 2>&1 && runuser -u "$WRITE_USER" -- sh -c 'printf "digua-write-test\n" > "$1"' sh "$test_file" 2>/dev/null; then write_ok=1; else write_ok=0; fi
    elif printf 'digua-write-test\n' > "$test_file" 2>/dev/null; then
      write_ok=1
    else
      write_ok=0
    fi
    if [[ "$write_ok" == "1" ]]; then
      rm -f "$test_file"
      write_verified=1
    else
      blockers+=("personal_root_not_writable")
    fi
  fi
fi

ok=1; [[ "${#blockers[@]}" -eq 0 ]] || ok=0
blockers_json="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
warnings_json="$(printf '%s\n' "${warnings[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(BLOCKERS_JSON="$blockers_json" WARNINGS_JSON="$warnings_json" PROTOCOL="$PROTOCOL" NAS_HOST="$NAS_HOST" NAS_SHARE="$NAS_SHARE" MOUNT_POINT="$MOUNT_POINT" PERSONAL_ROOT="$PERSONAL_ROOT" FSTAB_LINE="$fstab_line" FSTAB_PATH="$FSTAB_PATH" BACKUP_PATH="$backup_path" python3 - <<PY
import json, os
print(json.dumps({
  "ok": bool($ok), "dry_run": bool($DRY_RUN), "simulation": bool($SIMULATION),
  "production_verified": bool($mounted_verified and $write_verified and not $SIMULATION),
  "protocol": os.environ["PROTOCOL"], "nas_backed": os.environ["PROTOCOL"] != "local" and not bool($SIMULATION),
  "nas_host": os.environ["NAS_HOST"], "nas_share": os.environ["NAS_SHARE"],
  "mount_point": os.environ["MOUNT_POINT"], "personal_root": os.environ["PERSONAL_ROOT"],
  "mounted_verified": bool($mounted_verified), "write_verified": bool($write_verified),
  "fstab_updated": bool($fstab_updated), "fstab_path": os.environ["FSTAB_PATH"],
  "fstab_backup": os.environ["BACKUP_PATH"], "redacted_fstab_fragment": os.environ["FSTAB_LINE"],
  "password_logged": False, "blockers": json.loads(os.environ["BLOCKERS_JSON"]),
  "warnings": json.loads(os.environ["WARNINGS_JSON"]),
}, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
