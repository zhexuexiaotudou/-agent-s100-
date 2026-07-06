#!/usr/bin/env bash
set -u

DRY_RUN=1
PROTOCOL="local"
NAS_HOST=""
NAS_SHARE=""
MOUNT_POINT="/mnt/nas/openclaw"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
CREDENTIALS_FILE=""
JSON_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --nas-protocol|--protocol) PROTOCOL="${2:-}"; shift 2 ;;
    --nas-host) NAS_HOST="${2:-}"; shift 2 ;;
    --nas-share) NAS_SHARE="${2:-}"; shift 2 ;;
    --mount-point|--nas-mount) MOUNT_POINT="${2:-}"; shift 2 ;;
    --personal-root) PERSONAL_ROOT="${2:-}"; shift 2 ;;
    --credentials-file) CREDENTIALS_FILE="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

blockers=()
case "$PROTOCOL" in
  nfs|smb|cifs|local) ;;
  *) blockers+=("unsupported_protocol:$PROTOCOL") ;;
esac
[[ "$MOUNT_POINT" == /mnt/nas/openclaw* || "$PROTOCOL" == "local" ]] || blockers+=("mount_point_outside_allowlist")
if [[ "$PROTOCOL" != "local" ]]; then
  [[ -n "$NAS_HOST" ]] || blockers+=("nas_host_required")
  [[ -n "$NAS_SHARE" ]] || blockers+=("nas_share_required")
fi

if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  mkdir -p "$MOUNT_POINT" "$PERSONAL_ROOT"
  touch "$MOUNT_POINT/.digua_mount_write_test" 2>/dev/null || blockers+=("mount_not_writable")
  rm -f "$MOUNT_POINT/.digua_mount_write_test" 2>/dev/null || true
fi

fstab="local-directory-mode"
if [[ "$PROTOCOL" == "nfs" ]]; then
  fstab="${NAS_HOST}:${NAS_SHARE} ${MOUNT_POINT} nfs4 rw,nofail,x-systemd.automount 0 0"
elif [[ "$PROTOCOL" == "smb" || "$PROTOCOL" == "cifs" ]]; then
  fstab="//${NAS_HOST}/${NAS_SHARE} ${MOUNT_POINT} cifs credentials=${CREDENTIALS_FILE:-/etc/digua-ai-nas/smb.credentials},rw,nofail,x-systemd.automount 0 0"
fi

ok=1
[[ "${#blockers[@]}" -eq 0 ]] || ok=0
blockers_json="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
payload="$(BLOCKERS_JSON="$blockers_json" python3 - <<PY
import json, os
payload = {
  "ok": bool($ok),
  "dry_run": bool($DRY_RUN),
  "protocol": "$PROTOCOL",
  "nas_host": "$NAS_HOST",
  "nas_share": "$NAS_SHARE",
  "mount_point": "$MOUNT_POINT",
  "personal_root": "$PERSONAL_ROOT",
  "credential_file_supplied": bool("${CREDENTIALS_FILE}" != ""),
  "redacted_fstab_fragment": "$fstab",
  "password_logged": False,
  "loopback_or_lan_only": True,
  "blockers": json.loads(os.environ["BLOCKERS_JSON"])
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"
if [[ -n "$JSON_OUT" ]]; then mkdir -p "$(dirname "$JSON_OUT")"; printf '%s\n' "$payload" > "$JSON_OUT"; fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
