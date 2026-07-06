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
systemd_plan="$(run_json systemd "$ROOT_DIR/release/install/install_systemd_units.sh" --dry-run --mode "$SYSTEMD_MODE" --unit-dir "$ROOT_DIR/release/systemd")"

blocker=""
if [[ "$DRY_RUN" == "0" ]]; then
  mkdir -p "$INSTALL_ROOT" "$MOUNT_POINT" "$PERSONAL_ROOT"
  python3 -m venv "$INSTALL_ROOT/venv" || blocker="venv_create_failed"
  if [[ -z "$blocker" && "$SKIP_PIP" == "0" ]]; then
    if [[ -f "$ROOT_DIR/requirements.txt" ]]; then
      "$INSTALL_ROOT/venv/bin/pip" install -r "$ROOT_DIR/requirements.txt" || blocker="pip_install_failed"
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
fi

payload="$(python3 - <<PY
import json
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
