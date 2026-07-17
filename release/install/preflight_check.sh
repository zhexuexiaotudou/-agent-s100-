#!/usr/bin/env bash
set -u

NAS_HOST=""
MOUNT_POINT="/mnt/nas/openclaw"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
JSON_OUT=""
MIN_DISK_KB=262144
WARN_DISK_KB=1048576
SIMULATION=0
STRICT_DEVICE=0
REQUIRE_NAS=0
NAS_PROTOCOL="local"
SYSTEMD_MODE="system"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --nas-host) NAS_HOST="${2:-}"; shift 2 ;;
    --mount-point|--nas-mount) MOUNT_POINT="${2:-}"; shift 2 ;;
    --personal-root) PERSONAL_ROOT="${2:-}"; shift 2 ;;
    --json-out) JSON_OUT="${2:-}"; shift 2 ;;
    --min-disk-kb) MIN_DISK_KB="${2:-}"; shift 2 ;;
    --simulate) SIMULATION=1; shift ;;
    --strict-device) STRICT_DEVICE=1; shift ;;
    --require-nas) REQUIRE_NAS=1; shift ;;
    --nas-protocol) NAS_PROTOCOL="${2:-}"; shift 2 ;;
    --systemd-mode) SYSTEMD_MODE="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
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
systemd_system_ok=0; systemctl list-unit-files >/dev/null 2>&1 && systemd_system_ok=1
network_ok=0; ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 2 223.5.5.5 >/dev/null 2>&1; [[ $? -eq 0 ]] && network_ok=1
nas_reachable=0
if [[ -n "$NAS_HOST" ]]; then
  if [[ "$NAS_HOST" =~ ^[A-Za-z0-9._-]+$ ]]; then
    ping -c 1 -W 2 "$NAS_HOST" >/dev/null 2>&1 && nas_reachable=1
    if [[ "$nas_reachable" == "0" ]] && command -v timeout >/dev/null 2>&1; then
      nas_port=2049; [[ "$NAS_PROTOCOL" == "smb" || "$NAS_PROTOCOL" == "cifs" ]] && nas_port=445
      timeout 2 bash -c "</dev/tcp/${NAS_HOST}/${nas_port}" >/dev/null 2>&1 && nas_reachable=1
    fi
  else
    warnings+=("nas_host_contains_unsafe_characters")
  fi
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

if [[ "$SIMULATION" == "0" ]]; then
  [[ "$arch" == "aarch64" ]] || blockers+=("arch_not_aarch64:$arch")
  [[ "$python_ok" == "1" ]] || blockers+=("python_3_10_missing")
  [[ "$venv_ok" == "1" ]] || blockers+=("python_venv_missing")
  if [[ "$SYSTEMD_MODE" == "user" ]]; then
    [[ "$systemd_user_ok" == "1" ]] || blockers+=("systemd_user_unavailable")
  elif [[ "$SYSTEMD_MODE" == "system" ]]; then
    [[ "$systemd_system_ok" == "1" ]] || blockers+=("systemd_system_unavailable")
  else
    blockers+=("unsupported_systemd_mode:$SYSTEMD_MODE")
  fi
  [[ "$disk_ok" == "1" ]] || blockers+=("disk_free_below_min:${MIN_DISK_KB}")
  if [[ "$STRICT_DEVICE" == "1" ]]; then
    [[ "$s100p_detected" == "1" ]] || blockers+=("s100p_not_detected")
    [[ "$bpu_available" == "1" ]] || blockers+=("s100p_bpu_unavailable")
  fi
  if [[ "$REQUIRE_NAS" == "1" ]]; then
    [[ "$NAS_PROTOCOL" != "local" ]] || blockers+=("nas_protocol_local_not_allowed")
    [[ "$nas_reachable" == "1" ]] || blockers+=("nas_unreachable:$NAS_HOST")
    if [[ "$NAS_PROTOCOL" == "nfs" ]]; then command -v mount.nfs >/dev/null 2>&1 || blockers+=("mount_nfs_helper_missing"); fi
    if [[ "$NAS_PROTOCOL" == "smb" || "$NAS_PROTOCOL" == "cifs" ]]; then command -v mount.cifs >/dev/null 2>&1 || blockers+=("mount_cifs_helper_missing"); fi
  fi
else
  warnings+=("simulated_preflight_hardware_not_verified")
fi
[[ "$ports_available" == "1" ]] || warnings+=("ports_8765_or_18080_already_listening")

ok=1
[[ "${#blockers[@]}" -eq 0 ]] || ok=0

blockers_json="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
warnings_json="$(printf '%s\n' "${warnings[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"

payload="$(BLOCKERS_JSON="$blockers_json" WARNINGS_JSON="$warnings_json" python3 - <<PY
import json, os
payload = {
  "ok": bool($ok),
  "simulation": bool($SIMULATION),
  "production_verified": False,
  "strict_device": bool($STRICT_DEVICE),
  "require_nas": bool($REQUIRE_NAS),
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
  "systemd_system_ok": bool($systemd_system_ok),
  "systemd_mode": "$SYSTEMD_MODE",
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
