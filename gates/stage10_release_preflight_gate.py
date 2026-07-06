from __future__ import annotations

import argparse
import json

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd


NAME = "stage10_release_preflight_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S100P release preflight.")
    add_stage10_args(parser)
    args = parser.parse_args()
    out = args.report_root / f"{NAME}_preflight.json"
    cmd = ["bash", "release/install/preflight_check.sh", "--mount-point", "/mnt/nas/openclaw", "--personal-root", "/mnt/nas/openclaw/Personal", "--json-out", str(out)]
    run = run_cmd(cmd, timeout=60)
    payload = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    checks = [
        check("preflight script ran", bool(payload), run.get("stderr")),
        check("preflight ok", payload.get("ok") is True, payload.get("blockers")),
        check("arch aarch64", payload.get("arch") == "aarch64", payload.get("arch")),
        check("systemd user ok", payload.get("systemd_user_ok") is True, payload),
    ]
    gate = gate_payload("ok_stage10_release_preflight_gate", "blocked_stage10_release_preflight_gate", checks, {"preflight": payload, "run": run})
    json_path, md_path = write_gate(args.report_root, NAME, gate)
    print(md_path)
    print(json_path)
    return 0 if gate["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

