from __future__ import annotations

import argparse

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate
from src.openclaw.routes.smart_classification_routes import smart_classification_route_response


NAME = "stage7_smart_classification_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate virtual smart classification.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.no_rebuild:
        smart_classification_route_response("/api/smart-classification/rebuild", method="POST", payload={}, report_root=args.report_root, personal_root=args.personal_root)
    _code, status = smart_classification_route_response("/api/smart-classification/status", method="GET", report_root=args.report_root, personal_root=args.personal_root)
    _code, categories = smart_classification_route_response("/api/smart-classification/categories", method="GET", report_root=args.report_root, personal_root=args.personal_root)
    first_category = (categories.get("categories") or [{}])[0].get("category_id")
    copy_plan = {"ok": False}
    if first_category:
        _code, copy_plan = smart_classification_route_response(
            f"/api/smart-classification/category/{first_category}/materialize-copy-plan",
            method="POST",
            payload={},
            report_root=args.report_root,
            personal_root=args.personal_root,
        )
    evidence_ok = True
    for category in categories.get("categories") or []:
        if not category.get("item_count"):
            continue
        _code, items = smart_classification_route_response(
            f"/api/smart-classification/category/{category['category_id']}/items",
            method="GET",
            report_root=args.report_root,
            personal_root=args.personal_root,
        )
        for item in items.get("items") or []:
            evidence_ok = evidence_ok and bool(item.get("matched_by")) and bool(item.get("evidence_refs"))
    checks = [
        check("category_count >= 5", int(status.get("category_count") or 0) >= 5, status.get("category_count")),
        check("hit_category_count >= 3", int(status.get("hit_category_count") or 0) >= 3, status.get("hit_category_count")),
        check("membership_count > 0", int(status.get("membership_count") or 0) > 0, status.get("membership_count")),
        check("matched_by and evidence_ref exist", evidence_ok, "membership rows"),
        check("no physical file move", status.get("physical_file_moved") is False, status.get("physical_file_moved")),
        check("materialize is plan only", copy_plan.get("plan_only") is True and copy_plan.get("execute_requires_harness") is True, copy_plan),
        check("destructive_actions_enabled == false", status.get("destructive_actions_enabled") is False, status.get("destructive_actions_enabled")),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_smart_classification_gate", "blocked_stage7_smart_classification_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "status": status,
        "categories": categories,
        "copy_plan": copy_plan,
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
