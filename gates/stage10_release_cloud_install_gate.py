from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd


NAME = "stage10_release_cloud_install_gate"
FIXTURE_SECRET = "ci-cloud-key-must-never-appear-in-reports"


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a clean cloud-provider S100P installation.")
    add_stage10_args(parser)
    args = parser.parse_args()
    tmp_parent = args.report_root / "_stage10_cloud_install_tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="digua_stage10_cloud_", dir=str(tmp_parent)))
    try:
        out = args.report_root / f"{NAME}_install.json"
        env = dict(os.environ)
        env["DIGUA_CLOUD_API_KEY"] = FIXTURE_SECRET
        cmd = [
            "bash", "release/install/install_s100p.sh",
            "--simulate-root", str(temp),
            "--nas-protocol", "nfs", "--nas-host", "192.0.2.20", "--nas-share", "/digua",
            "--model-mode", "cloud", "--cloud-base-url", "http://127.0.0.1:9/v1",
            "--cloud-model", "fixture-cloud-model", "--allow-insecure-cloud-endpoint",
            "--skip-pip", "--defer-admin-claim", "--min-disk-kb", "10240", "--report-out", str(out),
        ]
        run = run_cmd(cmd, timeout=180, env=env)
        result = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        report_text = out.read_text(encoding="utf-8") if out.exists() else ""
        env_file = temp / "etc" / "digua-ai-nas" / "digua.env"
        key_file = temp / "etc" / "digua-ai-nas" / "cloud-api-key"
        env_text = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
        checks = [
            check("cloud clean install report exists", bool(result), run.get("stderr")),
            check("cloud clean install ok", result.get("ok") is True, result.get("blockers")),
            check("cloud mode selected", result.get("model_mode") == "cloud", result),
            check("cloud provider contract ready", ((result.get("steps") or {}).get("models") or {}).get("provider", {}).get("mode") == "cloud", (result.get("steps") or {}).get("models")),
            check("local Qwen paths not required in cloud mode", not any("qwen" in str(item).lower() for item in result.get("blockers") or []), result.get("blockers")),
            check("cloud key stored in protected dedicated file", key_file.is_file(), str(key_file)),
            check("cloud key never stored in report or environment file", FIXTURE_SECRET not in report_text and FIXTURE_SECRET not in env_text, {"report": str(out), "env": str(env_file)}),
            check("environment references key file and disables private raw egress", "DIGUA_CLOUD_API_KEY_FILE=" in env_text and result.get("cloud_private_raw_egress") is False, env_text),
            check("simulation cannot claim production", result.get("simulation") is True and result.get("production_verified") is False, result),
        ]
        payload = gate_payload("ok_stage10_release_cloud_install_gate", "blocked_stage10_release_cloud_install_gate", checks, {"installer": result, "run": run})
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 0 if payload["ok"] else 1
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
