#!/usr/bin/env bash
set -u

DRY_RUN=0
SIM_ROOT=""
INSTALL_ROOT="/opt/digua-ai-nas"
NAS_PROTOCOL=""
NAS_HOST=""
NAS_SHARE=""
MOUNT_POINT="/mnt/nas/openclaw"
PERSONAL_ROOT="/mnt/nas/openclaw/Personal"
CREDENTIALS_FILE=""
SYSTEMD_MODE="system"
SKIP_PIP=0
SKIP_SYSTEMD=0
ALLOW_LOCAL=0
REPORT_OUT=""
MIN_DISK_KB=262144
ADMIN_USERNAME="admin"
PASSWORD_ENV="DIGUA_ADMIN_PASSWORD"
WHEELHOUSE=""
SERVICE_USER="${SUDO_USER:-$(id -un)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --simulate-root) SIM_ROOT="${2:-}"; shift 2 ;;
    --install-root) INSTALL_ROOT="${2:-}"; shift 2 ;;
    --nas-protocol) NAS_PROTOCOL="${2:-}"; shift 2 ;;
    --nas-host) NAS_HOST="${2:-}"; shift 2 ;;
    --nas-share) NAS_SHARE="${2:-}"; shift 2 ;;
    --mount-point|--nas-mount) MOUNT_POINT="${2:-}"; shift 2 ;;
    --personal-root) PERSONAL_ROOT="${2:-}"; shift 2 ;;
    --credentials-file) CREDENTIALS_FILE="${2:-}"; shift 2 ;;
    --systemd-mode) SYSTEMD_MODE="${2:-}"; shift 2 ;;
    --skip-pip) SKIP_PIP=1; shift ;;
    --skip-systemd) SKIP_SYSTEMD=1; shift ;;
    --allow-local-storage) ALLOW_LOCAL=1; shift ;;
    --report-out) REPORT_OUT="${2:-}"; shift 2 ;;
    --min-disk-kb) MIN_DISK_KB="${2:-}"; shift 2 ;;
    --admin-username) ADMIN_USERNAME="${2:-}"; shift 2 ;;
    --password-env) PASSWORD_ENV="${2:-}"; shift 2 ;;
    --wheelhouse) WHEELHOUSE="${2:-}"; shift 2 ;;
    --service-user) SERVICE_USER="${2:-}"; shift 2 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SIMULATION=0
if [[ -n "$SIM_ROOT" ]]; then
  SIMULATION=1
  [[ "$SIM_ROOT" == /* && "$SIM_ROOT" != "/" ]] || { printf 'unsafe --simulate-root\n' >&2; exit 2; }
  INSTALL_ROOT="$SIM_ROOT/opt/digua-ai-nas"
  MOUNT_POINT="$SIM_ROOT/mnt/nas/openclaw"
  PERSONAL_ROOT="$MOUNT_POINT/Personal"
fi
[[ -n "$NAS_PROTOCOL" ]] || { printf '%s\n' 'missing required --nas-protocol (nfs, smb, or explicit local simulation)' >&2; exit 2; }
[[ "$SERVICE_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || { printf 'unsafe service user\n' >&2; exit 2; }
for path_value in "$INSTALL_ROOT" "$MOUNT_POINT" "$PERSONAL_ROOT"; do
  [[ "$path_value" =~ ^/[A-Za-z0-9._/-]+$ ]] || { printf 'unsafe path value: %s\n' "$path_value" >&2; exit 2; }
done

REPORT_FILE="${REPORT_OUT:-${MOUNT_POINT}/reports/release_install/install_report_$(date +%Y%m%d-%H%M%S).json}"
TMP_DIR="$(mktemp -d)"
chmod 711 "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT
blockers=()

run_step() {
  local name="$1"; shift
  local out="$TMP_DIR/${name}.json"
  if ! "$@" --json-out "$out" >"$TMP_DIR/${name}.log" 2>&1; then
    blockers+=("${name}_failed")
  fi
  [[ -f "$out" ]] || printf '{"ok":false,"blockers":["missing_step_report"]}\n' > "$out"
}

preflight_args=(bash "$ROOT_DIR/release/install/preflight_check.sh" --nas-host "$NAS_HOST" --nas-protocol "$NAS_PROTOCOL" --systemd-mode "$SYSTEMD_MODE" --mount-point "$MOUNT_POINT" --personal-root "$PERSONAL_ROOT" --min-disk-kb "$MIN_DISK_KB")
if [[ "$SIMULATION" == "1" ]]; then
  preflight_args+=(--simulate)
else
  preflight_args+=(--strict-device)
  [[ "$ALLOW_LOCAL" == "1" ]] || preflight_args+=(--require-nas)
fi
run_step preflight "${preflight_args[@]}"

nas_args=(bash "$ROOT_DIR/release/install/configure_nas_mount.sh" --nas-protocol "$NAS_PROTOCOL" --nas-host "$NAS_HOST" --nas-share "$NAS_SHARE" --mount-point "$MOUNT_POINT" --personal-root "$PERSONAL_ROOT")
[[ "$SIMULATION" == "0" ]] && nas_args+=(--write-user "$SERVICE_USER")
[[ -n "$CREDENTIALS_FILE" ]] && nas_args+=(--credentials-file "$CREDENTIALS_FILE")
[[ "$ALLOW_LOCAL" == "1" ]] && nas_args+=(--allow-local-storage)
if [[ "$DRY_RUN" == "1" || "${#blockers[@]}" -gt 0 ]]; then
  nas_args+=(--dry-run)
elif [[ "$SIMULATION" == "1" ]]; then
  nas_args+=(--simulate --fstab-path "$SIM_ROOT/etc/fstab")
else
  nas_args+=(--apply)
fi
run_step nas "${nas_args[@]}"

if [[ "$SYSTEMD_MODE" == "system" ]]; then
  ENV_FILE="/etc/digua-ai-nas/digua.env"
  [[ "$SIMULATION" == "1" ]] && ENV_FILE="$SIM_ROOT/etc/digua-ai-nas/digua.env"
else
  ENV_FILE="$HOME/.config/digua-ai-nas/digua.env"
fi
if [[ "$SIMULATION" == "0" && "$DRY_RUN" == "0" ]]; then
  if [[ "$SYSTEMD_MODE" == "system" && "${EUID:-$(id -u)}" != "0" ]]; then blockers+=("system_mode_requires_root"); fi
  if [[ "$SYSTEMD_MODE" == "user" && "${EUID:-$(id -u)}" == "0" ]]; then blockers+=("user_mode_must_not_run_as_root"); fi
fi

models_args=(bash "$ROOT_DIR/release/install/configure_models.sh" --model-manifest "$ROOT_DIR/release/configs/model_manifest.yaml" --env-out "$ENV_FILE")
if [[ "$DRY_RUN" == "1" || "${#blockers[@]}" -gt 0 ]]; then models_args+=(--dry-run --strict); else models_args+=(--apply --strict); fi
run_step models "${models_args[@]}"

if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  if [[ -z "$INSTALL_ROOT" || "$INSTALL_ROOT" != /* || "$INSTALL_ROOT" == "/" ]]; then
    blockers+=("unsafe_install_root")
  elif ! mkdir -p "$INSTALL_ROOT/app" "$PERSONAL_ROOT" "$(dirname "$ENV_FILE")"; then
    blockers+=("install_directory_create_failed")
  fi
fi

if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  app_root="$INSTALL_ROOT/app"
  for entry in src web scripts configs release requirements.txt LICENSE; do
    if [[ -e "$ROOT_DIR/$entry" ]]; then
      rm -rf "$app_root/$entry"
      cp -a "$ROOT_DIR/$entry" "$app_root/$entry" || blockers+=("application_copy_failed:$entry")
    fi
  done
  if [[ "${#blockers[@]}" -eq 0 ]]; then python3 -m venv "$INSTALL_ROOT/venv" || blockers+=("venv_create_failed"); fi
  if [[ "${#blockers[@]}" -eq 0 && "$SKIP_PIP" == "0" ]]; then
    pip_args=("$INSTALL_ROOT/venv/bin/pip" install -r "$app_root/requirements.txt")
    [[ -z "$WHEELHOUSE" ]] || pip_args+=(--no-index --find-links "$WHEELHOUSE")
    "${pip_args[@]}" || blockers+=("pip_install_failed")
  fi
  if [[ "${#blockers[@]}" -eq 0 ]]; then
    {
      printf 'DIGUA_INSTALL_ROOT=%s\n' "$INSTALL_ROOT"
      printf 'DIGUA_NAS_MOUNT=%s\n' "$MOUNT_POINT"
      printf 'DIGUA_PERSONAL_ROOT=%s\n' "$PERSONAL_ROOT"
      printf 'AI_NAS_PERSONAL_ROOT=%s\n' "$PERSONAL_ROOT"
      printf 'AI_NAS_REPORT_ROOT=%s\n' "$MOUNT_POINT/reports/qwen25_ai_nas"
      printf 'QWEN25_TOOL_DISPATCHER=%s\n' "$INSTALL_ROOT/app/scripts/probes/ai_nas_allowlisted_tool.sh"
      printf 'QWEN25_GATEWAY_REPORT_ROOT=%s\n' "$MOUNT_POINT/reports/qwen25_gateway"
      printf 'DIGUA_OPENCLAW_BASE_URL=http://127.0.0.1:8765\n'
      printf 'DIGUA_QWEN_BASE_URL=http://127.0.0.1:18080\n'
      grep -E '^(DIGUA_|QWEN25_)' "$ENV_FILE" 2>/dev/null | grep -v -E '^(DIGUA_INSTALL_ROOT|DIGUA_NAS_MOUNT|DIGUA_PERSONAL_ROOT|DIGUA_OPENCLAW_BASE_URL|DIGUA_QWEN_BASE_URL)=' || true
    } > "$TMP_DIR/digua.env"
    mv "$TMP_DIR/digua.env" "$ENV_FILE"
    chmod 644 "$ENV_FILE"
    if [[ "$SIMULATION" == "0" && "$SYSTEMD_MODE" == "system" ]]; then
      if ! command -v runuser >/dev/null 2>&1; then
        blockers+=("runuser_missing")
      elif ! runuser -u "$SERVICE_USER" -- mkdir -p "$MOUNT_POINT/reports/qwen25_ai_nas" "$MOUNT_POINT/reports/qwen25_gateway"; then
        blockers+=("service_user_report_root_not_writable")
      fi
    else
      mkdir -p "$MOUNT_POINT/reports/qwen25_ai_nas" "$MOUNT_POINT/reports/qwen25_gateway" || blockers+=("report_root_create_failed")
    fi
  fi
fi

systemd_args=(bash "$ROOT_DIR/release/install/install_systemd_units.sh" --mode "$SYSTEMD_MODE" --unit-dir "$ROOT_DIR/release/systemd" --install-root "$INSTALL_ROOT" --personal-root "$PERSONAL_ROOT" --report-root "$MOUNT_POINT/reports/qwen25_ai_nas" --env-file "$ENV_FILE" --service-user "$SERVICE_USER")
if [[ "$DRY_RUN" == "1" || "$SKIP_SYSTEMD" == "1" || "${#blockers[@]}" -gt 0 ]]; then
  systemd_args+=(--dry-run)
elif [[ "$SIMULATION" == "1" ]]; then
  systemd_args+=(--simulate --target-dir "$SIM_ROOT/etc/systemd/system")
else
  systemd_args+=(--apply)
fi
run_step systemd "${systemd_args[@]}"

first_run_status="$TMP_DIR/first_run.json"
if [[ "$DRY_RUN" == "0" && "${#blockers[@]}" -eq 0 ]]; then
  wizard_args=(python3 "$INSTALL_ROOT/app/release/install/first_run_wizard.py" --install-root "$INSTALL_ROOT" --app-root "$INSTALL_ROOT/app" --nas-mount "$MOUNT_POINT" --personal-root "$PERSONAL_ROOT" --report-root "$MOUNT_POINT/reports/qwen25_ai_nas" --wizard-report-out "$first_run_status" --admin-username "$ADMIN_USERNAME" --password-env "$PASSWORD_ENV")
  [[ "$SIMULATION" == "1" ]] && wizard_args+=(--simulation)
  if [[ "$SIMULATION" == "0" && "$SYSTEMD_MODE" == "system" ]]; then
    touch "$first_run_status" && chown "$SERVICE_USER" "$first_run_status"
    if ! runuser --preserve-environment -u "$SERVICE_USER" -- "${wizard_args[@]}" >"$TMP_DIR/first_run.log" 2>&1; then blockers+=("first_run_failed"); fi
  elif ! "${wizard_args[@]}" >"$TMP_DIR/first_run.log" 2>&1; then
    blockers+=("first_run_failed")
  fi
fi
[[ -f "$first_run_status" ]] || printf '{"ok":null,"status":"not_run"}\n' > "$first_run_status"

BLOCKERS_JSON="$(printf '%s\n' "${blockers[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
BLOCKERS_JSON="$BLOCKERS_JSON" REPORT_DIR="$TMP_DIR" INSTALL_ROOT="$INSTALL_ROOT" MOUNT_POINT="$MOUNT_POINT" PERSONAL_ROOT="$PERSONAL_ROOT" ENV_FILE="$ENV_FILE" ADMIN_USERNAME="$ADMIN_USERNAME" python3 - <<PY > "$TMP_DIR/final.json"
import json, os
root = os.environ["REPORT_DIR"]
load = lambda name: json.load(open(os.path.join(root, name + ".json"), encoding="utf-8"))
steps = {name: load(name) for name in ("preflight", "nas", "models", "systemd", "first_run")}
blockers = json.loads(os.environ["BLOCKERS_JSON"])
for name, result in steps.items():
    if result.get("ok") is False and f"{name}_failed" not in blockers:
        blockers.append(f"{name}_not_ok")
payload = {
  "schema": "digua_clean_install_v2", "ok": not blockers, "dry_run": bool($DRY_RUN),
  "simulation": bool($SIMULATION), "production_verified": False,
  "install_root": os.environ["INSTALL_ROOT"], "nas_mount": os.environ["MOUNT_POINT"],
  "personal_root": os.environ["PERSONAL_ROOT"], "env_file": os.environ["ENV_FILE"],
  "application_copied": os.path.isfile(os.path.join(os.environ["INSTALL_ROOT"], "app/scripts/probes/ai_nas_operator_portal_server.py")),
  "venv_created": os.path.isfile(os.path.join(os.environ["INSTALL_ROOT"], "venv/bin/python")),
  "system_python_modified": False, "public_exposure_enabled": False,
  "steps": steps, "blockers": blockers,
  "next_commands": {
    "verify": "read -rsp 'Admin password: ' DIGUA_ADMIN_PASSWORD; export DIGUA_ADMIN_PASSWORD; python3 release/scripts/verify_install.py --username " + os.environ["ADMIN_USERNAME"],
    "access": "ssh -N -L 8765:127.0.0.1:8765 <s100p-user>@<s100p-ip>",
    "rollback": "bash release/install/upgrade_s100p.sh --rollback-from <backup> --install-root " + os.environ["INSTALL_ROOT"],
  },
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY

mkdir -p "$(dirname "$REPORT_FILE")"
cp "$TMP_DIR/final.json" "$REPORT_FILE"
cat "$REPORT_FILE"
python3 -c 'import json,sys; raise SystemExit(0 if json.load(open(sys.argv[1], encoding="utf-8")).get("ok") else 1)' "$REPORT_FILE"
