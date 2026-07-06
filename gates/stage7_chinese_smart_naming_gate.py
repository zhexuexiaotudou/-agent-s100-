from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate
from src.openclaw.routes.ai_space_routes import ai_space_route_response
from src.openclaw.routes.multimodal_search_routes import multimodal_route_response
from src.openclaw.routes.person_attribute_routes import person_attribute_route_response
from src.openclaw.routes.smart_classification_routes import smart_classification_route_response
from src.openclaw.routes.smart_naming_routes import smart_naming_route_response
from src.openclaw.routes.yolo_index_routes import yolo_route_response

REPO_ROOT = Path(__file__).resolve().parents[1]
scripts_dir = REPO_ROOT / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from product_demo_seed_data import create_images  # noqa: E402


NAME = "stage7_chinese_smart_naming_gate"
SELECTED_DEMO_IMAGE_NAMES = (
    "white_shirt_person.jpg",
    "cat_indoor.jpg",
    "laptop_desk.jpg",
    "invoice_photo.jpg",
)
ILLEGAL_RE = re.compile(r'[\\/:*?"<>|\r\n\t]')
PHONE_OR_ID_RE = re.compile(r"(?<!\d)(?:1[3-9]\d{9}|\d{15,18}[\dXx]?)(?!\d)")
FORMAT_RE = re.compile(r"^[^_]+_[^_]+_[^_]+_\d{8}_\d{3}$")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Gate safe Chinese smart naming without physical rename.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.no_rebuild:
        multimodal_roots: list[str] = []
        yolo_roots: list[str] = []
        if args.personal_root:
            photo_dir = Path(args.personal_root) / "Photos" / "stage7_smart_album_demo"
            photo_dir.mkdir(parents=True, exist_ok=True)
            create_images(photo_dir)
            selected_files = [photo_dir / name for name in SELECTED_DEMO_IMAGE_NAMES if (photo_dir / name).exists()]
            multimodal_roots = [str(path) for path in selected_files]
            yolo_roots = [str(path) for path in selected_files]
        multimodal_payload = {"roots": multimodal_roots, "max_files": len(multimodal_roots)} if multimodal_roots else {}
        yolo_payload = {"roots": yolo_roots, "max_files": len(yolo_roots), "include_video": False} if yolo_roots else {}
        _log_step("multimodal rebuild", multimodal_payload)
        multimodal_route_response("/api/multimodal-index/rebuild", method="POST", payload=multimodal_payload, report_root=args.report_root, personal_root=args.personal_root)
        _log_step("yolo rebuild", yolo_payload)
        yolo_route_response("/api/yolo-index/rebuild", method="POST", payload=yolo_payload, report_root=args.report_root, personal_root=args.personal_root)
        _log_step("person attribute rebuild", yolo_payload)
        person_attribute_route_response("/api/person-attribute/rebuild", method="POST", payload=yolo_payload, report_root=args.report_root, personal_root=args.personal_root)
        _log_step("smart classification rebuild", {})
        smart_classification_route_response("/api/smart-classification/rebuild", method="POST", payload={}, report_root=args.report_root, personal_root=args.personal_root)
    _log_step("smart naming batch generate", {"limit": 10000})
    _code, batch = smart_naming_route_response("/api/smart-naming/batch-generate", method="POST", payload={"limit": 10000}, report_root=args.report_root, personal_root=args.personal_root)
    _code, assets_payload = ai_space_route_response("/api/ai-space/assets", method="GET", payload={"limit": 10000}, report_root=args.report_root, personal_root=args.personal_root)
    items = batch.get("items") or []
    names = [str(item.get("display_name_zh") or "") for item in items]
    filenames = [str(item.get("suggested_filename_zh") or "") for item in items]
    encoded = json.dumps({"items": items, "assets": assets_payload.get("assets") or []}, ensure_ascii=False)

    expected_terms = {
        "person_white": any("人物照片" in name and "白色上衣" in name for name in names),
        "cat": any("猫咪" in name or "宠物动物" in name for name in names),
        "invoice": any("票据发票" in name or "票据" in name for name in names),
        "electronics": any("电子设备" in name or "笔记本电脑" in name for name in names),
    }
    risk_ok = all(not (item.get("risk_flags") or {}).get(flag) for item in items for flag in ["identity_inference_used", "face_recognition_used", "age_gender_race_emotion_health_inferred", "physical_file_renamed", "cloud_used"])
    checks = [
        check("batch generate ok", bool(batch.get("ok")), batch.get("error")),
        check("generated_count > 0", int(batch.get("generated_count") or 0) > 0, batch.get("generated_count")),
        check("format 主类别_核心特征_场景或属性_日期_序号", all(FORMAT_RE.match(name) for name in names[:100]), names[:5]),
        check("suggested filenames have no illegal chars", all(not ILLEGAL_RE.search(filename) for filename in filenames[:100]), filenames[:5]),
        check("no phone/id sensitive numbers", all(not PHONE_OR_ID_RE.search(name + filename) for name, filename in zip(names, filenames)), names[:5]),
        check("person white name generated", expected_terms["person_white"], expected_terms),
        check("cat or pet name generated", expected_terms["cat"], expected_terms),
        check("invoice name generated", expected_terms["invoice"], expected_terms),
        check("electronics name generated", expected_terms["electronics"], expected_terms),
        check("risk flags stay safe", risk_ok, "identity/face/sensitive/rename/cloud false"),
        check("no physical rename", all(item.get("physical_file_renamed") is False for item in items), "metadata only"),
        check("raw path not returned", all(marker not in encoded for marker in ["/mnt/nas/", "C:\\", "F:\\", "/home/", "/root/"]), "redacted"),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_chinese_smart_naming_gate", "blocked_stage7_chinese_smart_naming_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "batch": batch,
        "sample_assets": (assets_payload.get("assets") or [])[:20],
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


_STEP_START = time.perf_counter()


def _log_step(label: str, payload: dict[str, Any]) -> None:
    elapsed = time.perf_counter() - _STEP_START
    print(f"[{NAME}] +{elapsed:.1f}s {label}: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
