from __future__ import annotations

import argparse
import base64
import hashlib
import shutil
from pathlib import Path

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload, has_raw_path

from src.openclaw.routes.ai_space_routes import ai_space_route_response
from src.openclaw.routes.auto_organizer_routes import auto_organizer_route_response
from src.openclaw.routes.multimodal_search_routes import multimodal_route_response
from src.openclaw.routes.person_attribute_routes import person_attribute_route_response
from src.openclaw.routes.smart_classification_routes import smart_classification_route_response
from src.openclaw.routes.yolo_index_routes import yolo_route_response


NAME = "stage9_auto_organizer_ai_driven_gate"
TINY_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Al//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Auto Organizer classification is AI-index driven, not filename-driven.")
    add_common_args(parser)
    parser.add_argument("--demo-image", type=Path, default=None)
    parser.add_argument("--source-rel", default="Uploads/stage9_ai_driven/IMG_0001.jpg")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if not args.personal_root:
        payload = gate_payload("ok_stage9_auto_organizer_ai_driven_gate", "blocked_stage9_auto_organizer_ai_driven_gate", [check("personal root configured", False, "missing")])
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 1

    personal_root = Path(args.personal_root)
    source_rel = args.source_rel.replace("\\", "/").strip("/")
    source = personal_root / source_rel
    fixture_only = seed_neutral_demo_image(source, args.demo_image)
    source_sha_before = sha256_file(source)
    rebuild_payload = {"roots": [str(source.parent)], "max_files": 20, "include_video": False}
    rebuilds = {
        "multimodal": multimodal_route_response("/api/multimodal-index/rebuild", method="POST", payload=rebuild_payload, report_root=args.report_root, personal_root=personal_root)[1],
        "yolo": yolo_route_response("/api/yolo-index/rebuild", method="POST", payload=rebuild_payload, report_root=args.report_root, personal_root=personal_root)[1],
        "person_attribute": person_attribute_route_response("/api/person-attribute/rebuild", method="POST", payload=rebuild_payload, report_root=args.report_root, personal_root=personal_root)[1],
        "smart_classification": smart_classification_route_response("/api/smart-classification/rebuild", method="POST", payload={}, report_root=args.report_root, personal_root=personal_root)[1],
        "ai_space": ai_space_route_response("/api/ai-space/rebuild", method="POST", payload={}, report_root=args.report_root, personal_root=personal_root)[1],
    }
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
        payload={"plan_id": plan.get("plan_id"), "approval_phrase": plan.get("approval_phrase"), "approved_by": "stage9_auto_organizer_ai_driven_gate"},
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
    _code, rolled_back = auto_organizer_route_response("/api/auto-organize/rollback", method="POST", payload={"plan_id": plan.get("plan_id")}, report_root=args.report_root, personal_root=personal_root)
    unindexed_rel = "Uploads/stage9_ai_driven_unindexed/IMG_9999.jpg"
    unindexed = personal_root / unindexed_rel
    seed_neutral_demo_image(unindexed, None)
    _code, fallback_plan = auto_organizer_route_response(
        "/api/auto-organize/plan",
        method="POST",
        payload={"mode": "move_and_rename", "source_root": "Uploads", "source_rel_paths": [unindexed_rel], "limit": 1},
        report_root=args.report_root,
        personal_root=personal_root,
    )
    item = (plan.get("items") or [{}])[0] if isinstance(plan.get("items"), list) else {}
    basis = item.get("classification_basis") if isinstance(item.get("classification_basis"), dict) else {}
    source_name = str(basis.get("source") or "")
    checks = [
        check("neutral filename used", Path(source_rel).name.lower().startswith("img_0001"), source_rel),
        check("source file exists", source.exists() and source.is_file(), source_rel),
        check("multimodal rebuild ok", rebuilds["multimodal"].get("ok") is True, rebuilds["multimodal"].get("error")),
        check("yolo rebuild ok", rebuilds["yolo"].get("ok") is True, rebuilds["yolo"].get("error")),
        check("person attribute rebuild ok", rebuilds["person_attribute"].get("ok") is True, rebuilds["person_attribute"].get("error")),
        check("smart classification rebuild ok", rebuilds["smart_classification"].get("ok") is True, rebuilds["smart_classification"].get("error")),
        check("ai space rebuild ok", rebuilds["ai_space"].get("ok") is True, rebuilds["ai_space"].get("error")),
        check("plan created one item", plan.get("ok") is True and plan.get("item_count") == 1, plan.get("error")),
        check("plan item top-level ai-driven", item.get("ai_driven") is True, item),
        check("plan item fallback false", item.get("fallback_used") is False, item),
        check("plan item resolution source real", str(item.get("resolution_source") or "") not in {"", "fallback_filename", "fallback_filename_heuristic"}, item.get("resolution_source")),
        check("classification source not fallback", source_name not in {"", "fallback_filename_heuristic", "local_filename_and_existing_naming_policy"}, basis),
        check("classification marked ai-driven", basis.get("fallback_used") is False, basis),
        check("classification has evidence refs", bool(basis.get("evidence_refs")), basis.get("evidence_refs")),
        check("category generated", bool(item.get("target_category_zh")), item.get("target_category_zh")),
        check("suggested Chinese filename generated", bool(item.get("suggested_filename_zh")) and not str(item.get("suggested_filename_zh")).lower().startswith("img_0001"), item.get("suggested_filename_zh")),
        check("dry run ok", dry_run.get("ok") is True and (dry_run.get("items") or [{}])[0].get("would_execute") is True, dry_run),
        check("approval ok", approved.get("ok") is True and bool(approved.get("approval_token")), approved),
        check("execute ok", executed.get("ok") is True and executed.get("executed_count") == 1, executed),
        check("rollback ok", rolled_back.get("ok") is True and rolled_back.get("rollback_verified") is True, rolled_back),
        check("rollback preserved sha256", source.exists() and sha256_file(source) == source_sha_before, source_rel),
        check("delete false", executed.get("delete_allowed") is False, executed),
        check("overwrite false", executed.get("overwrite_allowed") is False, executed),
        check("unindexed fallback blocked", fallback_plan.get("ok") is False and fallback_plan.get("blocker") == "ai_index_missing_for_asset" and fallback_plan.get("fallback_available") is True, fallback_plan),
        check("raw path not returned", not has_raw_path({"plan": plan, "dry_run": dry_run, "approved": approved, "executed": executed, "rolled_back": rolled_back, "fallback_plan": fallback_plan, "rebuilds": rebuilds}), "redacted"),
    ]
    payload = gate_payload(
        "ok_stage9_auto_organizer_ai_driven_gate",
        "blocked_stage9_auto_organizer_ai_driven_gate",
        checks,
        {
            "fixture_only_for_ci": fixture_only,
            "production_demo_requires_real_user_asset": fixture_only,
            "source_rel": source_rel,
            "classification_basis": basis,
            "plan": plan,
            "dry_run": dry_run,
            "approved": approved,
            "executed": executed,
            "rolled_back": rolled_back,
            "fallback_plan": fallback_plan,
            "rebuilds": rebuilds,
        },
    )
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


def seed_neutral_demo_image(target: Path, demo_image: Path | None) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    if demo_image and demo_image.exists() and demo_image.is_file():
        shutil.copy2(demo_image, target)
        return False
    if not target.exists():
        target.write_bytes(base64.b64decode(TINY_JPEG_BASE64))
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
