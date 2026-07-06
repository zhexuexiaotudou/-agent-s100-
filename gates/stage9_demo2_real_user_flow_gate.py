from __future__ import annotations

import argparse
import base64
import os
import time
from pathlib import Path

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload, has_raw_path, http_get_json, http_post_json


NAME = "stage9_demo2_real_user_flow_gate"
TINY_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Al//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Demo2 real user AI-NAS flow over live product APIs.")
    add_common_args(parser)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--auth-token", default=os.environ.get("DIGUA_DEMO_AUTH_TOKEN", ""))
    parser.add_argument("--demo-image", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    auth_token = str(args.auth_token or "").strip()
    checks = [
        check("auth token configured", bool(auth_token), "set --auth-token or DIGUA_DEMO_AUTH_TOKEN"),
        check("personal root configured", bool(args.personal_root), str(args.personal_root)),
    ]
    if not auth_token or not args.personal_root:
        payload = gate_payload("ok_stage9_demo2_real_user_flow_gate", "blocked_stage9_demo2_real_user_flow_gate", checks)
        json_path, md_path = write_gate(args.report_root, NAME, payload)
        print(md_path)
        print(json_path)
        return 1

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"IMG_0001_{timestamp}.jpg"
    target_dir = "Uploads/stage9_demo2"
    source_rel = f"{target_dir}/{filename}"
    content_b64, fixture_only = demo_image_base64(args.demo_image)
    upload = http_post_json(
        args.base_url,
        "/api/media/upload",
        {
            "filename": filename,
            "target_dir": target_dir,
            "content_base64": content_b64,
            "auto_process": True,
            "upload_scope_only": True,
        },
        timeout=args.timeout,
        auth_token=auth_token,
    )
    upload_payload = upload.get("payload") or {}
    asset_id = upload_payload.get("asset_id")
    ai_space_queries = {
        "white_person": http_post_json(args.base_url, "/api/ai-space/search", {"query": "穿白色上衣的人", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
        "computer": http_post_json(args.base_url, "/api/ai-space/search", {"query": "有电脑的照片", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
        "pet": http_post_json(args.base_url, "/api/ai-space/search", {"query": "宠物照片", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
    }
    multimodal = {
        "white_person": http_post_json(args.base_url, "/api/multimodal-search/query", {"query": "找穿白色上衣的人", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
        "computer": http_post_json(args.base_url, "/api/multimodal-search/query", {"query": "找有电脑的照片", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
        "pet": http_post_json(args.base_url, "/api/multimodal-search/query", {"query": "找宠物照片", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
        "video_person": http_post_json(args.base_url, "/api/multimodal-search/query", {"query": "视频里有人", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
    }
    person = {
        "white_person": http_post_json(args.base_url, "/api/person-attribute/search", {"query": "找穿白色上衣的人", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
        "identity_block": http_post_json(args.base_url, "/api/person-attribute/search", {"query": "这个人是谁", "top_k": 8}, timeout=args.timeout, auth_token=auth_token),
    }
    yolo = http_post_json(args.base_url, "/api/yolo-index/search", {"query": "person laptop cat dog", "top_k": 8}, timeout=args.timeout, auth_token=auth_token)
    naming = http_get_json(args.base_url, f"/api/smart-naming/item/{asset_id}", timeout=args.timeout) if asset_id else {"ok": False, "payload": {}}
    ocr_status = http_get_json(args.base_url, "/api/ocr/status", timeout=args.timeout)
    rag = http_post_json(args.base_url, "/api/document-rag/query", {"query": "这张票据里的金额和日期是什么？", "path": "Documents"}, timeout=args.timeout, auth_token=auth_token)
    plan = http_post_json(args.base_url, "/api/auto-organize/plan", {"mode": "move_and_rename", "source_root": "Uploads", "source_rel_paths": [source_rel], "limit": 1}, timeout=args.timeout, auth_token=auth_token)
    plan_payload = plan.get("payload") or {}
    dry_run = http_post_json(args.base_url, "/api/auto-organize/dry-run", {"plan_id": plan_payload.get("plan_id")}, timeout=args.timeout, auth_token=auth_token)
    approve = http_post_json(
        args.base_url,
        "/api/auto-organize/approve",
        {"plan_id": plan_payload.get("plan_id"), "approval_phrase": plan_payload.get("approval_phrase"), "approved_by": "stage9_demo2_gate"},
        timeout=args.timeout,
        auth_token=auth_token,
    )
    execute = http_post_json(
        args.base_url,
        "/api/auto-organize/execute",
        {"plan_id": plan_payload.get("plan_id"), "approval_token": (approve.get("payload") or {}).get("approval_token")},
        timeout=args.timeout,
        auth_token=auth_token,
    )
    rollback = http_post_json(args.base_url, "/api/auto-organize/rollback", {"plan_id": plan_payload.get("plan_id")}, timeout=args.timeout, auth_token=auth_token)
    all_payloads = {
        "upload": upload,
        "ai_space_queries": ai_space_queries,
        "multimodal": multimodal,
        "person": person,
        "yolo": yolo,
        "naming": naming,
        "ocr_status": ocr_status,
        "rag": rag,
        "plan": plan,
        "dry_run": dry_run,
        "approve": approve,
        "execute": execute,
        "rollback": rollback,
    }
    upload_item = upload_payload.get("smart_naming") if isinstance(upload_payload.get("smart_naming"), dict) else {}
    plan_item = ((plan_payload.get("items") or [{}])[0] if isinstance(plan_payload.get("items"), list) else {}) or {}
    basis = plan_item.get("classification_basis") if isinstance(plan_item.get("classification_basis"), dict) else {}
    checks.extend(
        [
            check("upload ok", upload.get("ok") is True and upload_payload.get("ok") is True and bool(asset_id), upload_payload.get("error")),
            check("upload pipeline jobs completed", all((job or {}).get("status") == "completed" for job in upload_payload.get("jobs") or []), upload_payload.get("jobs")),
            check("upload cloud false", upload_payload.get("cloud_used") is False, upload_payload.get("cloud_used")),
            check("smart naming present", bool(upload_item or ((naming.get("payload") or {}).get("item"))), {"upload": upload_item, "naming": naming.get("payload")}),
            check("ai space query APIs ok", all(item.get("ok") is True and (item.get("payload") or {}).get("ok") is True for item in ai_space_queries.values()), ai_space_queries),
            check("multimodal query APIs ok", all(item.get("ok") is True and (item.get("payload") or {}).get("ok") is True for item in multimodal.values()), multimodal),
            check("person attribute white query ok", person["white_person"].get("ok") is True and (person["white_person"].get("payload") or {}).get("ok") is True, person["white_person"]),
            check("identity query blocked", (person["identity_block"].get("payload") or {}).get("blocked") is True, person["identity_block"]),
            check("person unsafe features disabled", all((person["identity_block"].get("payload") or {}).get(flag) is False for flag in ["face_identification_enabled", "biometric_recognition_enabled", "sensitive_attribute_inference_enabled"]), person["identity_block"].get("payload")),
            check("yolo search ok", yolo.get("ok") is True and (yolo.get("payload") or {}).get("ok") is True, yolo),
            check("ocr status ok", ocr_status.get("ok") is True and (ocr_status.get("payload") or {}).get("ok") is True, ocr_status),
            check("rag grounded or explicitly refused", (rag.get("payload") or {}).get("ok") is True or (rag.get("payload") or {}).get("no_grounded_answer") is True, rag),
            check("auto organizer plan ok", plan.get("ok") is True and plan_payload.get("ok") is True and plan_payload.get("item_count") == 1, plan_payload),
            check("auto organizer ai-driven basis", basis.get("source") not in {"", "fallback_filename_heuristic", "local_filename_and_existing_naming_policy"} and basis.get("fallback_used") is False, basis),
            check("dry run ok", dry_run.get("ok") is True and (dry_run.get("payload") or {}).get("ok") is True, dry_run),
            check("approval ok", approve.get("ok") is True and (approve.get("payload") or {}).get("ok") is True, approve),
            check("execute ok", execute.get("ok") is True and (execute.get("payload") or {}).get("ok") is True and (execute.get("payload") or {}).get("executed_count") == 1, execute),
            check("rollback ok", rollback.get("ok") is True and (rollback.get("payload") or {}).get("ok") is True and (rollback.get("payload") or {}).get("rollback_verified") is True, rollback),
            check("delete blocked", (execute.get("payload") or {}).get("delete_allowed") is False, execute.get("payload")),
            check("overwrite blocked", (execute.get("payload") or {}).get("overwrite_allowed") is False, execute.get("payload")),
            check("qwen no execution authority", (execute.get("payload") or {}).get("qwen_execution_authority") is False, execute.get("payload")),
            check("no raw path in flow", not has_raw_path(all_payloads), "redacted"),
        ]
    )
    payload = gate_payload(
        "ok_stage9_demo2_real_user_flow_gate",
        "blocked_stage9_demo2_real_user_flow_gate",
        checks,
        {
            "base_url": args.base_url,
            "source_rel": source_rel,
            "asset_id": asset_id,
            "fixture_only_for_ci": fixture_only,
            "production_demo_requires_real_user_asset": fixture_only,
            "recording_script_parameters": {
                "target_dir": target_dir,
                "filename": filename,
                "queries": ["穿白色上衣的人", "有电脑的照片", "宠物照片", "这个人是谁", "这张票据里的金额和日期是什么？"],
            },
            "flow": all_payloads,
        },
    )
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


def demo_image_base64(path: Path | None) -> tuple[str, bool]:
    if path and path.exists() and path.is_file():
        return base64.b64encode(path.read_bytes()).decode("ascii"), False
    return TINY_JPEG_BASE64, True


if __name__ == "__main__":
    raise SystemExit(main())
