#!/usr/bin/env bash
set -u

NAS_HOST=""
MOUNT_POINT="/mnt/nas/openclaw"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
JSON_OUT=""
MIN_DISK_KB=262144
WARN_DISK_KB=1048576

while [[ $# -gt 0 ]]; do
  case "$1" in
    --nas-host) NAS_HOST="${2:-}"; shift 2 ;;
    --mount-point|--nas-mount) MOUNT_POINT="${2:-}"; shift 2 ;;
    --personal-root) PERSONAL_ROOT="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    --min-disk-kb) MIN_DISK_KB="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

json_bool() {
  if [[ "$1" == "1" ]]; then printf "true"; else printf "false"; fi
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

blockers=()
warnings=()
arch="$(uname -m 2>/dev/null || echo unknown)"
os_release="$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}" || echo unknown)"
python_ok=0
python_version=""
if has_cmd python3; then
  python_version="$(python3 - <<'PY'
import sys
print(".".join(map(str, sys.version_info[:3])))
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
)"
  [[ $? -eq 0 ]] && python_ok=1
fi

pip_ok=0; has_cmd pip3 && pip_ok=1
venv_ok=0; python3 -m venv --help >/dev/null 2>&1 && venv_ok=1
sqlite_ok=0; has_cmd sqlite3 && sqlite_ok=1
ffmpeg_ok=0; has_cmd ffmpeg && ffmpeg_ok=1
systemd_user_ok=0; systemctl --user list-unit-files >/dev/null 2>&1 && systemd_user_ok=1
network_ok=0; ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 2 223.5.5.5 >/dev/null 2>&1; [[ $? -eq 0 ]] && network_ok=1
nas_reachable=0
if [[ -n "$NAS_HOST" ]]; then
  ping -c 1 -W 2 "$NAS_HOST" >/dev/null 2>&1 && nas_reachable=1
elif [[ -d "$MOUNT_POINT" ]]; then
  nas_reachable=1
else
  warnings+=("nas_host_not_supplied")
fi
mount_writable=0
if [[ -d "$MOUNT_POINT" && -w "$MOUNT_POINT" ]]; then mount_writable=1; fi
personal_root_ok=0
if [[ -d "$PERSONAL_ROOT" || -d "$(dirname "$PERSONAL_ROOT")" ]]; then personal_root_ok=1; fi
ports_available=1
if has_cmd ss; then
  if ss -ltn | awk '{print $4}' | grep -Eq ':(8765|18080)$'; then ports_available=0; fi
fi
disk_free_kb="$(df -Pk "$(dirname "$MOUNT_POINT")" 2>/dev/null | awk 'NR==2{print $4}' || echo 0)"
disk_ok=0
if [[ "${disk_free_kb:-0}" -ge "$MIN_DISK_KB" ]]; then disk_ok=1; fi
if [[ "${disk_free_kb:-0}" -lt "$WARN_DISK_KB" ]]; then warnings+=("disk_free_below_1g"); fi
s100p_detected=0
if [[ "$arch" == "aarch64" ]] && [[ -e /dev/hobot ]]; then s100p_detected=1; fi
if [[ "$arch" == "aarch64" ]] && { ls /usr/lib 2>/dev/null | grep -qi hobot || command -v hrt_model_exec >/dev/null 2>&1 || command -v hb_model_verifier >/dev/null 2>&1; }; then s100p_detected=1; fi
bpu_available=0
if command -v hrt_model_exec >/dev/null 2>&1 || command -v hb_model_verifier >/dev/null 2>&1 || [[ -d /usr/lib/hobot ]]; then bpu_available=1; fi

[[ "$arch" == "aarch64" ]] || blockers+=("arch_not_aarch64:$arch")
[[ "$python_ok" == "1" ]] || blockers+=("python_3_10_missing")
[[ "$pip_ok" == "1" ]] || blockers+=("pip3_missing")
[[ "$venv_ok" == "1" ]] || blockers+=("python_venv_missing")
[[ "$systemd_user_ok" == "1" ]] || blockers+=("systemd_user_unavailable")
[[ "$disk_ok" == "1" ]] || blockers+=("disk_free_below_min:${MIN_DISK_KB}")
[[ "$ports_available" == "1" ]] || warnings+=("ports_8765_or_18080_already_listening")

ok=1
[[ "${#blockers[@]}" -eq 0 ]] || ok=0

blockers_json="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
warnings_json="$(printf '%s\n' "${warnings[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"

payload="$(BLOCKERS_JSON="$blockers_json" WARNINGS_JSON="$warnings_json" python3 - <<PY
import json, os
payload = {
  "ok": bool($ok),
  "arch": "$arch",
  "os_release": "$os_release",
  "s100p_detected": bool($s100p_detected),
  "bpu_available": bool($bpu_available),
  "python_ok": bool($python_ok),
  "python_version": "$python_version",
  "pip_ok": bool($pip_ok),
  "venv_ok": bool($venv_ok),
  "sqlite3_ok": bool($sqlite_ok),
  "ffmpeg_ok": bool($ffmpeg_ok),
  "systemd_user_ok": bool($systemd_user_ok),
  "network_ok": bool($network_ok),
  "nas_reachable": bool($nas_reachable),
  "mount_writable": bool($mount_writable),
  "personal_root_ok": bool($personal_root_ok),
  "ports_available": bool($ports_available),
  "disk_free_kb": int("${disk_free_kb:-0}"),
  "min_disk_kb": int("${MIN_DISK_KB:-0}"),
  "warn_disk_kb": int("${WARN_DISK_KB:-0}"),
  "blockers": json.loads(os.environ["BLOCKERS_JSON"]),
  "warnings": json.loads(os.environ["WARNINGS_JSON"])
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"

if [[ -n "$JSON_OUT" ]]; then
  mkdir -p "$(dirname "$JSON_OUT")"
  printf '%s\n' "$payload" > "$JSON_OUT"
fi
printf '%s\n' "$payload"
exit $(( ok ? 0 : 1 ))
