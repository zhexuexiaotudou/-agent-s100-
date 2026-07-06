from __future__ import annotations

import argparse
from pathlib import Path

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import fixture_file, gate_payload, has_raw_path, sha256_file, status_checks

from src.openclaw.routes.auto_organizer_routes import auto_organizer_route_response


NAME = "stage8_auto_organize_move_rename_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate controlled Auto Organizer move+rename execution.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.personal_root:
        payload = gate_payload("ok_stage8_auto_organize_move_rename_gate", "blocked_stage8_auto_organize_move_rename_gate", [check("personal root configured", False, "missing")])
        paths = write_gate(args.report_root, NAME, payload)
        print(paths[1])
        print(paths[0])
        return 1

    personal_root = Path(args.personal_root)
    source_rel = "Uploads/stage8_auto_organize_move/white_shirt_person_stage8.jpg"
    source = fixture_file(personal_root, source_rel, b"stage8 controlled move rename fixture\n")
    source_sha = sha256_file(source)
    status_code, status = auto_organizer_route_response("/api/auto-organize/status", report_root=args.report_root, personal_root=personal_root)
    _code, plan = auto_organizer_route_response(
        "/api/auto-organize/plan",
        method="POST",
        payload={"mode": "move_and_rename", "source_root": "Uploads", "source_rel_paths": [source_rel], "limit": 1},
        report_root=args.report_root,
        personal_root=personal_root,
    )
    _code, dry_run = auto_organizer_route_response("/api/auto-organize/dry-run", method="POST", payload={"plan_id": plan.get("plan_id")}, report_root=args.report_root, personal_root=personal_root)
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
    item = (executed.get("items") or [{}])[0] if isinstance(executed.get("items"), list) else {}
    target = personal_root / str(item.get("target_rel") or "")
    rollback_manifest = args.report_root / str(executed.get("rollback_manifest") or "")
    checks = [
        check("status HTTP equivalent ok", status_code == 200 and status.get("ok") is True, status.get("error")),
        *status_checks(status),
        check("plan created one item", plan.get("ok") is True and plan.get("item_count") == 1, plan),
        check("dry run would execute", dry_run.get("ok") is True and (dry_run.get("items") or [{}])[0].get("would_execute") is True, dry_run),
        check("typed approval token issued", approved.get("ok") is True and bool(approved.get("approval_token")), approved),
        check("execute succeeded", executed.get("ok") is True and executed.get("executed_count") == 1, executed),
        check("source moved away", not source.exists(), source_rel),
        check("target exists", target.exists() and target.is_file(), item.get("target_rel")),
        check("sha256 preserved", target.exists() and sha256_file(target) == source_sha, item.get("target_sha256")),
        check("controlled move flagged", executed.get("move_allowed_controlled") is True, executed.get("move_allowed_controlled")),
        check("controlled rename flagged", executed.get("rename_allowed_controlled") is True, executed.get("rename_allowed_controlled")),
        check("delete still blocked", executed.get("delete_allowed") is False, executed.get("delete_allowed")),
        check("overwrite still blocked", executed.get("overwrite_allowed") is False, executed.get("overwrite_allowed")),
        check("rollback manifest written", rollback_manifest.exists(), str(executed.get("rollback_manifest"))),
        check("Qwen has no execution authority", executed.get("qwen_execution_authority") is False, executed.get("qwen_execution_authority")),
        check("raw path not returned", not has_raw_path({"plan": plan, "dry_run": dry_run, "executed": executed}), "redacted"),
    ]
    payload = gate_payload("ok_stage8_auto_organize_move_rename_gate", "blocked_stage8_auto_organize_move_rename_gate", checks, {"plan": plan, "dry_run": dry_run, "approved": approved, "executed": executed})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
