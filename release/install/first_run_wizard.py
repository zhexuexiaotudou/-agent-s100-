#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def load_identity_store(app_root: Path):
    module_path = app_root / "scripts" / "probes" / "ai_nas_identity.py"
    spec = importlib.util.spec_from_file_location("digua_release_identity", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"identity_module_unloadable:{module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.IdentityStore


def load_product_access_store(app_root: Path):
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    from src.product_access.store import ProductAccessStore
    return ProductAccessStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the real Digua identity store and verify first run.")
    parser.add_argument("--install-root", type=Path, default=Path("/opt/digua-ai-nas"))
    parser.add_argument("--app-root", type=Path)
    parser.add_argument("--nas-mount", type=Path, default=Path("/mnt/nas/openclaw"))
    parser.add_argument("--personal-root", type=Path, default=Path("/mnt/nas/openclaw/Personal"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--report-root", type=Path, default=Path("/mnt/nas/openclaw/reports/qwen25_ai_nas"))
    parser.add_argument("--wizard-report-out", type=Path)
    parser.add_argument("--identity-db", type=Path)
    parser.add_argument("--access-db", type=Path)
    parser.add_argument("--admin-username", default=os.environ.get("DIGUA_ADMIN_USERNAME", "admin"))
    parser.add_argument("--password-env", default="DIGUA_ADMIN_PASSWORD")
    parser.add_argument("--simulation", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--defer-admin-claim", action="store_true", help="Initialize identity storage but require one-time LAN claim for the first admin.")
    args = parser.parse_args()

    app_root = args.app_root or args.install_root / "app"
    identity_db = args.identity_db or args.report_root / "identity.sqlite3"
    access_db = args.access_db or args.install_root / "state" / "product_access.sqlite3"
    password = os.environ.get(args.password_env, "")
    blockers: list[str] = []
    auth: dict[str, Any] = {"ok": False, "username": args.admin_username, "token_redacted": True}
    token = ""

    if args.defer_admin_claim:
        try:
            store = load_identity_store(app_root)(identity_db)
            load_product_access_store(app_root)(access_db)
            users = store.list_users()
            if users:
                blockers.append("claim_mode_requires_empty_identity_store")
            auth.update({"ok": True, "created": False, "claim_pending": True, "role": None})
        except Exception as exc:
            blockers.append(f"identity_initialization_failed:{type(exc).__name__}:{exc}")
    elif not password:
        blockers.append(f"admin_password_missing_env:{args.password_env}")
    else:
        try:
            store = load_identity_store(app_root)(identity_db)
            users = store.list_users()
            existing = next((item for item in users if item["username"] == args.admin_username), None)
            created = False
            if not existing:
                result = store.create_user(args.admin_username, password, role="admin")
                created = bool(result.get("ok"))
                if not created:
                    blockers.append(f"admin_create_failed:{result.get('error')}")
            login = store.login(args.admin_username, password)
            token = str(login.get("token") or "")
            auth.update({"ok": bool(login.get("ok")), "created": created, "role": (login.get("user") or {}).get("role")})
            if not login.get("ok"):
                blockers.append(f"admin_login_failed:{login.get('error')}")
        except Exception as exc:
            blockers.append(f"identity_bootstrap_failed:{type(exc).__name__}:{exc}")

    checks: dict[str, Any] = {
        "nas_mount_exists": args.nas_mount.exists(),
        "nas_mount_writable": os.access(args.nas_mount, os.W_OK) if args.nas_mount.exists() else False,
        "personal_root_exists": args.personal_root.exists(),
        "install_root_exists": args.install_root.exists(),
        "identity_db_exists": identity_db.exists(),
        "models": model_status(),
    }
    for key in ("nas_mount_exists", "nas_mount_writable", "personal_root_exists", "install_root_exists", "identity_db_exists"):
        if not checks[key]:
            blockers.append(key)

    if args.defer_admin_claim:
        readiness = {"ok": None, "status": "deferred_until_lan_claim"}
        smoke = {"ok": None, "status": "deferred_until_lan_claim", "production_verified": False}
    elif args.simulation or args.skip_smoke:
        readiness = {"ok": None, "status": "deferred_simulation" if args.simulation else "skipped"}
        smoke = {"ok": None, "status": "deferred_simulation" if args.simulation else "skipped", "production_verified": False}
    elif token:
        readiness = wait_for_services(args.base_url, "http://127.0.0.1:18080/health", timeout=45)
        if not readiness.get("ok"):
            blockers.append("services_not_ready")
            smoke = {"ok": False, "status": "not_run_services_unready"}
        else:
            smoke = run_smoke(app_root, args.base_url, args.report_root, token)
            if not smoke.get("ok"):
                blockers.append("authenticated_product_smoke_failed_or_unreachable")
    else:
        readiness = {"ok": False, "error": "admin_session_unavailable"}
        smoke = {"ok": False, "error": "admin_session_unavailable"}

    payload = {
        "ok": not blockers,
        "simulation": args.simulation,
        "production_verified": False if args.simulation else bool(smoke.get("ok")),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": checks,
        "authentication": auth,
        "claim_mode": args.defer_admin_claim,
        "claim_token_stored_in_report": False,
        "identity_db": str(identity_db),
        "access_db": str(access_db),
        "access_db_exists": access_db.exists(),
        "openclaw_url": args.base_url,
        "qwen_health": "http://127.0.0.1:18080/health",
        "smoke": smoke,
        "service_readiness": readiness,
        "blockers": blockers,
    }
    report = args.wizard_report_out or args.report_root / f"first_run_wizard_{time.strftime('%Y%m%d-%H%M%S')}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


def model_status() -> dict[str, Any]:
    mode = os.environ.get("DIGUA_MODEL_MODE", "local")
    envs = [
        "DIGUA_QWEN_MODEL_DIR", "QWEN25_RUNTIME_BIN", "QWEN25_RUNTIME_CONFIG",
        "QWEN25_RUNTIME_LIB_DIR", "QWEN25_ACTIVE_HBM_PATH", "DIGUA_CLIP_MODEL_DIR",
        "DIGUA_YOLO_MODEL_PATH", "DIGUA_OCR_MODEL_DIR", "DIGUA_ASR_MODEL_DIR",
    ]
    paths = {name: {"configured": bool(os.environ.get(name)), "exists": Path(os.environ.get(name, "")).exists() if os.environ.get(name) else False} for name in envs}
    if mode == "cloud":
        key_file = Path(os.environ.get("DIGUA_CLOUD_API_KEY_FILE", "")) if os.environ.get("DIGUA_CLOUD_API_KEY_FILE") else None
        return {
            "mode": "cloud",
            "cloud_base_url_configured": bool(os.environ.get("DIGUA_CLOUD_BASE_URL")),
            "cloud_model": os.environ.get("DIGUA_CLOUD_MODEL", ""),
            "cloud_api_key_file_present": bool(key_file and key_file.is_file()),
            "cloud_private_raw_egress": False,
            "optional_local_features": paths,
        }
    return {"mode": "local", "paths": paths}


def run_smoke(app_root: Path, base_url: str, report_root: Path, token: str) -> dict[str, Any]:
    script = app_root / "scripts" / "product_smoke_test.py"
    if not script.exists():
        return {"ok": False, "error": f"product_smoke_missing:{script}"}
    env = dict(os.environ)
    env["DIGUA_ADMIN_TOKEN"] = token
    completed = subprocess.run(
        [sys.executable, str(script), "--base-url", base_url, "--report-root", str(report_root), "--timeout", "20", "--token-env", "DIGUA_ADMIN_TOKEN"],
        text=True, capture_output=True, check=False, env=env,
    )
    return {"ok": completed.returncode == 0, "returncode": completed.returncode, "stdout_tail": completed.stdout[-1000:], "stderr_tail": completed.stderr[-1000:], "token_redacted": True}


def wait_for_services(base_url: str, qwen_url: str, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = {}
        for name, url in {"portal": base_url.rstrip("/") + "/api/health", "qwen": qwen_url}.items():
            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    last[name] = {"ok": response.status == 200 and payload.get("ok") is True, "status": response.status, "inference_ready": payload.get("inference_ready")}
            except Exception as exc:
                last[name] = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
        if all(item.get("ok") for item in last.values()):
            return {"ok": True, "checks": last}
        time.sleep(1)
    return {"ok": False, "checks": last, "timeout_seconds": timeout}


if __name__ == "__main__":
    raise SystemExit(main())
