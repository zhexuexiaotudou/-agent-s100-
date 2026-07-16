from __future__ import annotations

import argparse
import json
import shutil
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
        out = args.report_root / f"{NAME}_install.json"
        cmd = ["bash", "release/install/install_s100p.sh", "--install-root", str(install_root), "--mount-point", str(mount), "--personal-root", str(personal), "--nas-protocol", "local", "--skip-pip", "--skip-systemd", "--min-disk-kb", "10240", "--report-out", str(out)]
        run = run_cmd(cmd, timeout=180)
        result = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        checks = [
            check("clean install report exists", bool(result), run.get("stderr")),
            check("clean install ok", result.get("ok") is True, result.get("blockers")),
            check("venv target created", (install_root / "venv").exists(), str(install_root / "venv")),
            check("personal root created", personal.exists(), str(personal)),
            check("application source copied", (install_root / "app" / "src" / "product_jobs" / "worker.py").exists(), str(install_root / "app")),
            check("portal entrypoint copied", (install_root / "app" / "scripts" / "probes" / "ai_nas_operator_portal_server.py").exists(), str(install_root / "app")),
            check("web UI copied", (install_root / "app" / "web" / "ai_nas_desktop_v2.html").exists(), str(install_root / "app")),
            check("requirements copied", (install_root / "app" / "requirements.txt").exists(), str(install_root / "app")),
            check("system python untouched", result.get("system_python_modified") is False, result),
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
