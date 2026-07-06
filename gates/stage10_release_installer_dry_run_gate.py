from __future__ import annotations

import argparse
import json

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd


NAME = "stage10_release_installer_dry_run_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release installer dry-run.")
    add_stage10_args(parser)
    args = parser.parse_args()
    out = args.report_root / f"{NAME}_install.json"
    cmd = ["bash", "release/install/install_s100p.sh", "--dry-run", "--report-out", str(out)]
    run = run_cmd(cmd, timeout=120)
    result = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    checks = [
        check("installer dry-run wrote report", bool(result), run.get("stderr")),
        check("dry-run flag true", result.get("dry_run") is True, result),
        check("system python untouched", result.get("system_python_modified") is False, result),
        check("no public exposure", result.get("public_exposure_enabled") is False, result),
        check("installer plan ok", result.get("ok") is True, result.get("blockers")),
    ]
    payload = gate_payload("ok_stage10_release_installer_dry_run_gate", "blocked_stage10_release_installer_dry_run_gate", checks, {"installer": result, "run": run})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

