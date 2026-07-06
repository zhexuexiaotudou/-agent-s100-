from __future__ import annotations

import argparse
from pathlib import Path

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import fixture_file, gate_payload, sha256_file

from src.openclaw.routes.auto_organizer_routes import auto_organizer_route_response


NAME = "stage8_auto_organize_rollback_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Auto Organizer rollback restores moved files.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.personal_root:
        payload = gate_payload("ok_stage8_auto_organize_rollback_gate", "blocked_stage8_auto_organize_rollback_gate", [check("personal root configured", False, "missing")])
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 1

    personal_root = Path(args.personal_root)
    source_rel = "Uploads/stage8_auto_organize_rollback/white_shirt_person_rollback.jpg"
    source = fixture_file(personal_root, source_rel, b"stage8 rollback fixture\n")
    source_sha = sha256_file(source)
    _code, plan = auto_organizer_route_response(
        "/api/auto-organize/plan",
        method="POST",
        payload={
            "mode": "move_and_rename",
            "source_root": "Uploads",
            "source_rel_paths": [source_rel],
            "limit": 1,
            "allow_filename_fallback_for_diagnostic": True,
        },
        report_root=args.report_root,
        personal_root=personal_root,
    )
    _code, approved = auto_organizer_route_response("/api/auto-organize/approve", method="POST", payload={"plan_id": plan.get("plan_id"), "approval_phrase": plan.get("approval_phrase"), "approved_by": "stage8_gate"}, report_root=args.report_root, personal_root=personal_root)
    _code, executed = auto_organizer_route_response("/api/auto-organize/execute", method="POST", payload={"plan_id": plan.get("plan_id"), "approval_token": approved.get("approval_token")}, report_root=args.report_root, personal_root=personal_root)
    target_rel = ((executed.get("items") or [{}])[0] or {}).get("target_rel")
    target = personal_root / str(target_rel or "")
    target_existed_before_rollback = target.exists()
    _code, rolled_back = auto_organizer_route_response("/api/auto-organize/rollback", method="POST", payload={"plan_id": plan.get("plan_id")}, report_root=args.report_root, personal_root=personal_root)
    checks = [
        check("execute before rollback succeeded", executed.get("ok") is True and target_existed_before_rollback, executed),
        check("rollback succeeded", rolled_back.get("ok") is True and rolled_back.get("rollback_verified") is True, rolled_back),
        check("source restored", source.exists() and sha256_file(source) == source_sha, source_rel),
        check("target removed by rollback move", not target.exists(), target_rel),
        check("rollback manifest written", (args.report_root / str(rolled_back.get("rollback_manifest") or "")).exists(), rolled_back.get("rollback_manifest")),
        check("raw path not returned", rolled_back.get("raw_path_returned") is False, rolled_back.get("raw_path_returned")),
    ]
    payload = gate_payload("ok_stage8_auto_organize_rollback_gate", "blocked_stage8_auto_organize_rollback_gate", checks, {"plan": plan, "executed": executed, "rolled_back": rolled_back})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
