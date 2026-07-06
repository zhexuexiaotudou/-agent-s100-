from __future__ import annotations

import argparse
from pathlib import Path

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import fixture_file, gate_payload, status_checks

from src.openclaw.routes.auto_organizer_routes import auto_organizer_route_response


NAME = "stage8_auto_organize_delete_block_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Auto Organizer delete and overwrite blocking.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.personal_root:
        payload = gate_payload("ok_stage8_auto_organize_delete_block_gate", "blocked_stage8_auto_organize_delete_block_gate", [check("personal root configured", False, "missing")])
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 1

    personal_root = Path(args.personal_root)
    source_rel = "Uploads/stage8_auto_organize_delete_block/receipt_stage8.txt"
    source = fixture_file(personal_root, source_rel, b"receipt stage8 overwrite guard\n")
    _code, status = auto_organizer_route_response("/api/auto-organize/status", report_root=args.report_root, personal_root=personal_root)
    _code, delete_plan = auto_organizer_route_response(
        "/api/auto-organize/plan",
        method="POST",
        payload={"mode": "move_and_rename", "source_root": "Uploads", "source_rel_paths": [source_rel], "delete_original": True},
        report_root=args.report_root,
        personal_root=personal_root,
    )
    _code, plan = auto_organizer_route_response(
        "/api/auto-organize/plan",
        method="POST",
        payload={"mode": "move_and_rename", "source_root": "Uploads", "source_rel_paths": [source_rel], "limit": 1},
        report_root=args.report_root,
        personal_root=personal_root,
    )
    target_rel = ((plan.get("items") or [{}])[0] or {}).get("target_rel")
    target = personal_root / str(target_rel or "")
    if target_rel:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("pre-existing target must not be overwritten\n", encoding="utf-8")
    _code, approved = auto_organizer_route_response(
        "/api/auto-organize/approve",
        method="POST",
        payload={"plan_id": plan.get("plan_id"), "approval_phrase": plan.get("approval_phrase"), "approved_by": "stage8_gate"},
        report_root=args.report_root,
        personal_root=personal_root,
    )
    _code, executed = auto_organizer_route_response(
        "/api/auto-organize/execute",
        method="POST",
        payload={"plan_id": plan.get("plan_id"), "approval_token": approved.get("approval_token")},
        report_root=args.report_root,
        personal_root=personal_root,
    )
    executed_target_rel = ((executed.get("items") or [{}])[0] or {}).get("target_rel")
    executed_target = personal_root / str(executed_target_rel or "")
    checks = [
        *status_checks(status),
        check("delete-original plan rejected", delete_plan.get("ok") is False and delete_plan.get("error") == "delete_original_forbidden", delete_plan),
        check("conflict execute succeeds by suffixing", executed.get("ok") is True and executed.get("executed_count") == 1, executed),
        check("existing target preserved", target.exists() and "pre-existing target" in target.read_text(encoding="utf-8"), target_rel),
        check("executed target is suffixed", bool(executed_target_rel) and executed_target_rel != target_rel, executed_target_rel),
        check("suffixed target exists", executed_target.exists() and executed_target.is_file(), executed_target_rel),
        check("source moved only through controlled route", not source.exists(), source_rel),
        check("delete flag remains false", status.get("delete_enabled") is False, status.get("delete_enabled")),
        check("overwrite flag remains false", status.get("overwrite_enabled") is False, status.get("overwrite_enabled")),
    ]
    payload = gate_payload("ok_stage8_auto_organize_delete_block_gate", "blocked_stage8_auto_organize_delete_block_gate", checks, {"status": status, "delete_plan": delete_plan, "plan": plan, "executed": executed})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
