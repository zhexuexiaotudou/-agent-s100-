from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "probes"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from ai_nas_operator_portal_server import PortalState  # noqa: E402
from product_demo_seed_data import create_images  # noqa: E402
from src.openclaw.routes.smart_classification_routes import smart_classification_route_response  # noqa: E402


NAME = "stage7_upload_auto_classify_gate"


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Gate upload -> NAS save -> queue -> classify -> Chinese naming.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.personal_root:
        payload = _payload([check("personal_root configured", False, "missing")], {})
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 1

    personal_root = Path(args.personal_root)
    source_dir = personal_root / "Photos" / "stage7_smart_album_demo"
    source_dir.mkdir(parents=True, exist_ok=True)
    create_images(source_dir)
    source = source_dir / "white_shirt_person.jpg"
    if not source.exists():
        payload = _payload([check("white_shirt_person fixture exists", False, str(source))], {})
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 1

    state = PortalState(
        report_root=args.report_root,
        evidence_roots=[args.report_root],
        refresh_on_start=False,
        personal_root=personal_root,
        nas_portal=True,
    )
    username = "stage7_upload_gate"
    if state.identity_store:
        state.identity_store.create_user(username, "stage7-upload-gate", "user")
        state.identity_store.set_acl("Uploads", "user", username, "write")
        state.identity_store.set_acl("Photos", "user", username, "read")
        state.identity_store.set_acl("", "user", username, "read")
    user = {"username": username, "role": "user"}

    payload = {
        "filename": "white_shirt_person.jpg",
        "target_dir": "Uploads/stage7_auto_classify",
        "content_base64": base64.b64encode(source.read_bytes()).decode("ascii"),
        "auto_process": True,
        "upload_scope_only": True,
    }
    status_code, result = state.media_upload_photo(payload, user)
    asset_id = str(result.get("asset_id") or "")

    _code, person_items = smart_classification_route_response(
        "/api/smart-classification/category/cat_person_photos/items",
        method="GET",
        report_root=args.report_root,
        personal_root=personal_root,
    )
    _code, white_items = smart_classification_route_response(
        "/api/smart-classification/category/cat_white_upper/items",
        method="GET",
        report_root=args.report_root,
        personal_root=personal_root,
    )
    person_hit = any(item.get("asset_id") == asset_id for item in person_items.get("items") or [])
    white_hit = any(item.get("asset_id") == asset_id for item in white_items.get("items") or [])
    jobs = result.get("jobs") if isinstance(result.get("jobs"), list) else []
    job_types = {job.get("job_type") for job in jobs}
    encoded = json.dumps(result, ensure_ascii=False)
    checks = [
        check("upload API returned 200", status_code == 200 and bool(result.get("ok")), {"status_code": status_code, "error": result.get("error")}),
        check("asset_id returned", bool(asset_id), asset_id),
        check("media upload job recorded", "media_upload" in job_types, sorted(job_types)),
        check("classification job recorded", "smart_classification_rebuild" in job_types, sorted(job_types)),
        check("smart naming job recorded", "smart_naming_generate" in job_types, sorted(job_types)),
        check("人物照片 category hit", person_hit, asset_id),
        check("白色上衣 category hit", white_hit, asset_id),
        check("Chinese naming generated", bool((result.get("smart_naming") or {}).get("display_name_zh")), result.get("smart_naming")),
        check("original not renamed", (result.get("upload_event") or {}).get("original_file_renamed") is False, result.get("upload_event")),
        check("no physical move", result.get("physical_file_moved") is False, result.get("physical_file_moved")),
        check("cloud not used", result.get("cloud_used") is False, result.get("cloud_used")),
        check("raw path not returned", all(marker not in encoded for marker in ["/mnt/nas/", "C:\\", "F:\\", "/home/", "/root/"]), "redacted"),
    ]
    gate_payload = _payload(checks, {"upload": result, "person_items": person_items, "white_items": white_items})
    json_path, md_path = write_gate(args.report_root, NAME, gate_payload)
    print(md_path)
    print(json_path)
    return 0 if gate_payload["ok"] else 1


def _payload(checks: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_upload_auto_classify_gate", "blocked_stage7_upload_auto_classify_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "evidence": evidence,
    }


if __name__ == "__main__":
    raise SystemExit(main())
