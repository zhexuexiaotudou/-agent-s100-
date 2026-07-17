from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd


NAME = "stage10_release_clean_install_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release installer into a clean temporary root.")
    add_stage10_args(parser)
    args = parser.parse_args()
    tmp_parent = args.report_root / "_stage10_clean_install_tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="digua_stage10_install_", dir=str(tmp_parent)))
    try:
        install_root = temp / "opt" / "digua-ai-nas"
        mount = temp / "mnt" / "nas" / "openclaw"
        personal = mount / "Personal"
        fixtures = temp / "model-fixtures"
        (fixtures / "qwen").mkdir(parents=True)
        (fixtures / "lib").mkdir()
        (fixtures / "runtime").write_text("fixture\n", encoding="utf-8")
        (fixtures / "runtime").chmod(0o755)
        (fixtures / "runtime.json").write_text("{}\n", encoding="utf-8")
        (fixtures / "qwen.hbm").write_text("fixture\n", encoding="utf-8")
        env = dict(os.environ)
        env.update({
            "DIGUA_ADMIN_PASSWORD": "ci-only-strong-password",
            "DIGUA_QWEN_MODEL_DIR": str(fixtures / "qwen"),
            "QWEN25_RUNTIME_BIN": str(fixtures / "runtime"),
            "QWEN25_RUNTIME_CONFIG": str(fixtures / "runtime.json"),
            "QWEN25_RUNTIME_LIB_DIR": str(fixtures / "lib"),
            "QWEN25_ACTIVE_HBM_PATH": str(fixtures / "qwen.hbm"),
        })
        out = args.report_root / f"{NAME}_install.json"
        cmd = ["bash", "release/install/install_s100p.sh", "--simulate-root", str(temp), "--nas-protocol", "nfs", "--nas-host", "192.0.2.10", "--nas-share", "/digua", "--skip-pip", "--defer-admin-claim", "--min-disk-kb", "10240", "--report-out", str(out)]
        run = run_cmd(cmd, timeout=180, env=env)
        result = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        identity_db = temp / "var" / "lib" / "digua-ai-nas" / "identity.sqlite3"
        access_db = temp / "var" / "lib" / "digua-ai-nas" / "product_access.sqlite3"
        user_count = -1
        if identity_db.exists():
            con = sqlite3.connect(identity_db)
            try:
                user_count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            finally:
                con.close()
        checks = [
            check("clean install report exists", bool(result), run.get("stderr")),
            check("clean install ok", result.get("ok") is True, result.get("blockers")),
            check("simulation explicitly labeled", result.get("simulation") is True and result.get("production_verified") is False, result),
            check("venv target created", (install_root / "venv").exists(), str(install_root / "venv")),
            check("personal root created", personal.exists(), str(personal)),
            check("application source copied", (install_root / "app" / "src" / "product_jobs" / "worker.py").exists(), str(install_root / "app")),
            check("portal entrypoint copied", (install_root / "app" / "scripts" / "probes" / "ai_nas_operator_portal_server.py").exists(), str(install_root / "app")),
            check("web UI copied", (install_root / "app" / "web" / "ai_nas_desktop_v2.html").exists(), str(install_root / "app")),
            check("requirements copied", (install_root / "app" / "requirements.txt").exists(), str(install_root / "app")),
            check("system python untouched", result.get("system_python_modified") is False, result),
            check("identity store initialized for LAN claim", identity_db.exists() and user_count == 0, {"identity_db": str(identity_db), "user_count": user_count}),
            check("stable product access store initialized", access_db.exists(), str(access_db)),
            check("no disconnected admin token file", not (install_root / "secrets" / "admin_token").exists(), str(install_root)),
            check("simulated fstab generated", (temp / "etc" / "fstab").exists(), str(temp / "etc" / "fstab")),
            check("systemd units rendered", (temp / "etc" / "systemd" / "system" / "openclaw-gateway.service").exists(), str(temp)),
            check("LAN facade rendered and remote ingress remains disabled", (temp / "etc" / "systemd" / "system" / "digua-product-access.service").exists() and result.get("steps", {}).get("systemd", {}).get("remote_ingress_default_enabled") is False, result.get("steps", {}).get("systemd")),
        ]
        payload = gate_payload("ok_stage10_release_clean_install_gate", "blocked_stage10_release_clean_install_gate", checks, {"installer": result, "run": run})
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 0 if payload["ok"] else 1
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
