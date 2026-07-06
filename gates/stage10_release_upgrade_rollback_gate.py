from __future__ import annotations

import argparse
import json

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd


NAME = "stage10_release_upgrade_rollback_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release upgrade and uninstall rollback dry-runs.")
    add_stage10_args(parser)
    args = parser.parse_args()
    upgrade_out = args.report_root / f"{NAME}_upgrade.json"
    uninstall_out = args.report_root / f"{NAME}_uninstall.json"
    upgrade = run_cmd(["bash", "release/install/upgrade_s100p.sh", "--dry-run", "--json-out", str(upgrade_out)], timeout=60)
    uninstall = run_cmd(["bash", "release/install/uninstall_s100p.sh", "--dry-run", "--json-out", str(uninstall_out)], timeout=60)
    upgrade_payload = json.loads(upgrade_out.read_text(encoding="utf-8")) if upgrade_out.exists() else {}
    uninstall_payload = json.loads(uninstall_out.read_text(encoding="utf-8")) if uninstall_out.exists() else {}
    checks = [
        check("upgrade dry-run ok", upgrade_payload.get("ok") is True, upgrade_payload.get("blockers") or upgrade.get("stderr")),
        check("upgrade is dry-run", upgrade_payload.get("dry_run") is True, upgrade_payload),
        check("backup planned", bool(upgrade_payload.get("backup_root")), upgrade_payload),
        check("uninstall dry-run ok", uninstall_payload.get("ok") is True, uninstall.get("stderr")),
        check("uninstall does not remove NAS data", uninstall_payload.get("nas_data_removed") is False and uninstall_payload.get("personal_data_removed") is False, uninstall_payload),
    ]
    payload = gate_payload("ok_stage10_release_upgrade_rollback_gate", "blocked_stage10_release_upgrade_rollback_gate", checks, {"upgrade": upgrade_payload, "uninstall": uninstall_payload, "runs": {"upgrade": upgrade, "uninstall": uninstall}})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

