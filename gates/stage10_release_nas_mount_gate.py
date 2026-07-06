from __future__ import annotations

import argparse
import json

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd


NAME = "stage10_release_nas_mount_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NAS mount release configuration in safe dry-run mode.")
    add_stage10_args(parser)
    args = parser.parse_args()
    out = args.report_root / f"{NAME}_nas.json"
    cmd = ["bash", "release/install/configure_nas_mount.sh", "--dry-run", "--nas-protocol", "local", "--mount-point", "/mnt/nas/openclaw", "--personal-root", "/mnt/nas/openclaw/Personal", "--json-out", str(out)]
    run = run_cmd(cmd, timeout=60)
    result = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    checks = [
        check("NAS config report exists", bool(result), run.get("stderr")),
        check("NAS config ok", result.get("ok") is True, result.get("blockers")),
        check("password not logged", result.get("password_logged") is False, result),
        check("loopback or LAN only", result.get("loopback_or_lan_only") is True, result),
        check("Personal root scoped", str(result.get("personal_root") or "").startswith("/mnt/nas/openclaw"), result),
    ]
    payload = gate_payload("ok_stage10_release_nas_mount_gate", "blocked_stage10_release_nas_mount_gate", checks, {"nas": result, "run": run})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

