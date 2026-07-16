#!/usr/bin/env bash
set -u

DRY_RUN=0
INSTALL_ROOT="/opt/digua-ai-nas"
NAS_PROTOCOL="local"
NAS_HOST=""
NAS_SHARE=""
MOUNT_POINT="/mnt/nas/openclaw"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
SYSTEMD_MODE="user"
SKIP_PIP=0
SKIP_SYSTEMD=0
REPORT_OUT=""
MIN_DISK_KB=262144

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --nas-protocol) NAS_PROTOCOL="${2:-}"; shift 2 ;;
    --nas-host) NAS_HOST="${2:-}"; shift 2 ;;
    --nas-share) NAS_SHARE="${2:-}"; shift 2 ;;
    --mount-point|--nas-mount) MOUNT_POINT="${2:-}"; shift 2 ;;
    --personal-root) PERSONAL_ROOT="${2:-}"; shift 2 ;;
    --systemd-mode) SYSTEMD_MODE="${2:-}"; shift 2 ;;
    --skip-pip) SKIP_PIP=1; shift ;;
    --skip-systemd) SKIP_SYSTEMD=1; shift ;;
    --report-out) REPORT_OUT="${2:-}"; shift 2 ;;
    --min-disk-kb) MIN_DISK_KB="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_DIR="${REPORT_OUT:-${MOUNT_POINT}/reports/release_install/install_report_$(date +%Y%m%d-%H%M%S).json}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ "$DRY_RUN" == "0" ]]; then
  mkdir -p "$MOUNT_POINT" "$(dirname "$PERSONAL_ROOT")"
fi

run_json() {
  local name="$1"; shift
  local out="$TMP_DIR/${name}.json"
  local script="$1"; shift
  if bash "$script" "$@" --json-out "$out" >/tmp/digua_release_${name}.log 2>&1; then
    :
  else
    :
  fi
  if [[ -f "$out" ]]; then cat "$out"; else printf '{"ok":false,"blockers":["missing_report:%s"]}\n' "$name"; fi
}

preflight="$(run_json preflight "$ROOT_DIR/release/install/preflight_check.sh" --nas-host "$NAS_HOST" --mount-point "$MOUNT_POINT" --personal-root "$PERSONAL_ROOT" --min-disk-kb "$MIN_DISK_KB")"
nas_config="$(run_json nas "$ROOT_DIR/release/install/configure_nas_mount.sh" --dry-run --nas-protocol "$NAS_PROTOCOL" --nas-host "$NAS_HOST" --nas-share "$NAS_SHARE" --mount-point "$MOUNT_POINT" --personal-root "$PERSONAL_ROOT")"
models="$(run_json models "$ROOT_DIR/release/install/configure_models.sh" --dry-run --model-manifest "$ROOT_DIR/release/configs/model_manifest.yaml")"
systemd_plan="$(run_json systemd "$ROOT_DIR/release/install/install_systemd_units.sh" --dry-run --mode "$SYSTEMD_MODE" --unit-dir "$ROOT_DIR/release/systemd" --install-root "$INSTALL_ROOT" --personal-root "$PERSONAL_ROOT" --report-root "$MOUNT_POINT/reports/qwen25_ai_nas")"

blocker=""
if [[ "$DRY_RUN" == "0" ]]; then
  if [[ -z "$INSTALL_ROOT" || "$INSTALL_ROOT" != /* || "$INSTALL_ROOT" == "/" ]]; then
    blocker="unsafe_install_root"
  elif ! mkdir -p "$INSTALL_ROOT" "$MOUNT_POINT" "$PERSONAL_ROOT"; then
    blocker="install_directory_create_failed"
  fi
  app_root="$INSTALL_ROOT/app"
  if [[ -z "$blocker" && "$ROOT_DIR" != "$app_root" ]]; then
    mkdir -p "$app_root" || blocker="application_directory_create_failed"
    for entry in src web scripts configs release requirements.txt LICENSE; do
      if [[ -z "$blocker" && -e "$ROOT_DIR/$entry" ]]; then
        rm -rf "$app_root/$entry" || blocker="application_replace_failed:$entry"
        if [[ -z "$blocker" ]]; then
          cp -a "$ROOT_DIR/$entry" "$app_root/$entry" || blocker="application_copy_failed:$entry"
        fi
      fi
    done
  fi
  if [[ -z "$blocker" ]]; then
    python3 -m venv "$INSTALL_ROOT/venv" || blocker="venv_create_failed"
  fi
  if [[ -z "$blocker" && "$SKIP_PIP" == "0" ]]; then
    if [[ -f "$app_root/requirements.txt" ]]; then
      "$INSTALL_ROOT/venv/bin/pip" install -r "$app_root/requirements.txt" || blocker="pip_install_failed"
    else
      blocker="requirements_txt_missing"
    fi
  fi
  mkdir -p "$HOME/.config/digua-ai-nas"
  {
    echo "DIGUA_INSTALL_ROOT=$INSTALL_ROOT"
    echo "DIGUA_NAS_MOUNT=$MOUNT_POINT"
    echo "DIGUA_PERSONAL_ROOT=$PERSONAL_ROOT"
    echo "DIGUA_OPENCLAW_BASE_URL=http://127.0.0.1:8765"
    echo "DIGUA_QWEN_BASE_URL=http://127.0.0.1:18080"
  } > "$HOME/.config/digua-ai-nas/digua.env"
  if [[ -z "$blocker" && "$SKIP_SYSTEMD" == "0" ]]; then
    systemd_apply="$(run_json systemd_apply "$app_root/release/install/install_systemd_units.sh" --apply --mode "$SYSTEMD_MODE" --unit-dir "$app_root/release/systemd" --install-root "$INSTALL_ROOT" --personal-root "$PERSONAL_ROOT" --report-root "$MOUNT_POINT/reports/qwen25_ai_nas")"
    if ! SYSTEMD_APPLY_JSON="$systemd_apply" python3 -c 'import json,os,sys; sys.exit(0 if json.loads(os.environ["SYSTEMD_APPLY_JSON"]).get("ok") else 1)'; then
      blocker="systemd_install_failed"
    fi
  fi
fi

payload="$(python3 - <<PY
import json, os
preflight=json.loads('''$preflight''')
nas=json.loads('''$nas_config''')
models=json.loads('''$models''')
systemd=json.loads('''$systemd_plan''')
blocker="$blocker"
blockers=[]
for name,payload in [('preflight',preflight),('nas',nas),('models',models),('systemd',systemd)]:
    if not payload.get('ok'):
        blockers.extend([f"{name}:{item}" for item in payload.get('blockers', [])] or [f"{name}:not_ok"])
if blocker:
    blockers.append(blocker)
payload={
  "ok": not blockers,
  "dry_run": bool($DRY_RUN),
  "install_root": "$INSTALL_ROOT",
  "nas_mount": "$MOUNT_POINT",
  "personal_root": "$PERSONAL_ROOT",
  "venv_target": "$INSTALL_ROOT/venv",
  "app_root": "$INSTALL_ROOT/app",
  "application_copied": os.path.isfile("$INSTALL_ROOT/app/scripts/probes/ai_nas_operator_portal_server.py") and os.path.isdir("$INSTALL_ROOT/app/src") and os.path.isdir("$INSTALL_ROOT/app/web"),
  "pip_executed": bool($DRY_RUN == 0 and $SKIP_PIP == 0),
  "system_python_modified": False,
  "public_exposure_enabled": False,
  "preflight": preflight,
  "nas": nas,
  "models": models,
  "systemd": systemd,
  "blockers": blockers,
  "next_commands": {
    "verify": "python3 release/scripts/verify_install.py --base-url http://127.0.0.1:8765",
    "smoke": "python3 scripts/product_smoke_test.py --base-url http://127.0.0.1:8765 --report-root ${DIGUA_NAS_MOUNT:-/mnt/nas/openclaw}/reports/product_delivery",
    "uninstall": "bash release/install/uninstall_s100p.sh --dry-run"
  }
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
)"

mkdir -p "$(dirname "$REPORT_DIR")"
printf '%s\n' "$payload" > "$REPORT_DIR"
printf '%s\n' "$payload"
python3 - <<PY
import json
raise SystemExit(0 if json.loads('''$payload''').get('ok') else 1)
PY
