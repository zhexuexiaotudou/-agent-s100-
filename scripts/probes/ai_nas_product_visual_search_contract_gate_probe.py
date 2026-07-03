#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_nas_common import (
    IMAGE_CAPTION_STATUS_COMPLETED,
    build_sqlite_inventory,
    ensure_image_captions_for_photos,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
)
from ai_nas_vision_index import ensure_photo_visual_states
from ai_nas_vision_runtime import vision_product_runtime_status
from ai_nas_vision_search import search_product_visual_index


TOOL_ID = "ai_nas_product_visual_search_contract_gate"
OK = "ok_ai_nas_product_visual_search_contract_gate"
FAILED = "failed_ai_nas_product_visual_search_contract_gate"


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((32, 32, 608, 388), outline=(30, 60, 70), width=4)
    draw.text((62, 190), text, fill=(12, 18, 20))
    image.save(path, quality=92)


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    photos = personal / "Photos"
    write_fixture_image(photos / "person_white_top.jpg", (215, 224, 230), "person white top")
    write_fixture_image(photos / "person_blue_top.jpg", (118, 160, 225), "person blue top")
    write_fixture_image(photos / "white_car.jpg", (242, 242, 236), "white car")
    write_fixture_image(photos / "white_wall_room.jpg", (245, 245, 241), "white wall")
    write_fixture_image(photos / "white_document_screenshot.jpg", (250, 250, 250), "white document")
    return personal


def fixture_caption_provider(record: dict) -> dict:
    rel = str(record.get("relative_path") or "")
    if "person_white_top" in rel:
        return {
            "provider": "fixture_vlm_caption",
            "model_id": "fixture-qwen-vl-product",
            "caption": "A generic person is wearing a white shirt and white upper clothing.",
            "objects": ["person"],
            "people": [{"role": "generic_person", "clothing": {"upper_color": "white", "upper_garment": "shirt"}}],
            "attributes": {"colors": ["white"], "upper_clothing.color": "white"},
            "scene": "portrait",
            "visible_text": [],
        }
    if "person_blue_top" in rel:
        return {
            "provider": "fixture_vlm_caption",
            "model_id": "fixture-qwen-vl-product",
            "caption": "A generic person is wearing a blue shirt and blue upper clothing.",
            "objects": ["person"],
            "people": [{"role": "generic_person", "clothing": {"upper_color": "blue", "upper_garment": "shirt"}}],
            "attributes": {"colors": ["blue"], "upper_clothing.color": "blue"},
            "scene": "portrait",
            "visible_text": [],
        }
    if "white_car" in rel:
        return {
            "provider": "fixture_vlm_caption",
            "model_id": "fixture-qwen-vl-product",
            "caption": "A white car with no visible person and no clothing.",
            "objects": ["white car"],
            "people": [],
            "attributes": {"colors": ["white"]},
            "scene": "vehicle",
            "visible_text": [],
        }
    if "white_wall" in rel:
        return {
            "provider": "fixture_vlm_caption",
            "model_id": "fixture-qwen-vl-product",
            "caption": "A white wall in a room. No person or clothing is visible.",
            "objects": ["wall"],
            "people": [],
            "attributes": {"colors": ["white"]},
            "scene": "room",
            "visible_text": [],
        }
    return {
        "provider": "fixture_vlm_caption",
        "model_id": "fixture-qwen-vl-product",
        "caption": "A white document screenshot with text. No person or clothing is visible.",
        "objects": ["document", "screenshot"],
        "people": [],
        "attributes": {"colors": ["white"]},
        "scene": "document",
        "visible_text": ["sample document"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate final product-shaped visual search response contract.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_visual_search_contract_gate_local"))
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "product_visual_search_contract_gate")
    personal_root = prepare_fixture(run_dir)
    db_path = run_dir / "personal_inventory.sqlite3"
    index_status = build_sqlite_inventory(personal_root, db_path)
    caption_update = ensure_image_captions_for_photos(db_path, limit=20, caption_provider=fixture_caption_provider)
    embedding_update = ensure_image_embeddings_for_photos(db_path, limit=20)

    from ai_nas_common import open_index_db, _record_from_sqlite_row

    con = open_index_db(db_path)
    try:
        records = [_record_from_sqlite_row(row) for row in con.execute("SELECT * FROM records ORDER BY relative_path").fetchall()]
    finally:
        con.close()
    state_update = ensure_photo_visual_states(db_path, records, runtime=vision_product_runtime_status())
    search = search_product_visual_index(db_path, "找穿白色上衣的照片", limit=5)
    results = search.get("matches") or []
    top_paths = [item.get("relative_path") for item in results]

    failures: list[str] = []
    if caption_update.get("completed", 0) < 5:
        failures.append("fixture_caption_provider_incomplete")
    if embedding_update.get("completed", 0) < 5:
        failures.append("legacy_embedding_incomplete")
    if not results or results[0].get("relative_path") != "Photos/person_white_top.jpg":
        failures.append(f"top_result_not_person_white_top:{top_paths[:3]}")
    false_positive_needles = ("white_car", "white_wall", "white_document", "person_blue_top")
    if any(any(needle in str(path) for needle in false_positive_needles) for path in top_paths):
        failures.append(f"false_positive_in_top5:{top_paths}")
    plan = search.get("query_plan") or {}
    if plan.get("search_kind") != "region_attribute_visual" or not plan.get("strict_attributes"):
        failures.append(f"bad_query_plan:{plan}")
    top = results[0] if results else {}
    if not top.get("evidence_items") or not top.get("evidence_chips"):
        failures.append("missing_structured_evidence")
    if not top.get("visual_state"):
        failures.append("missing_visual_state")
    if top.get("image_caption", {}).get("status") != IMAGE_CAPTION_STATUS_COMPLETED:
        failures.append("top_result_not_caption_grounded")
    if top.get("confidence_kind") != "degradation_capped":
        failures.append(f"expected_degradation_capped_confidence:{top.get('confidence_kind')}")
    if not top.get("degraded"):
        failures.append("expected_degraded_until_region_models_configured")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "index_status": index_status,
        "caption_update": caption_update,
        "embedding_update": embedding_update,
        "state_update": state_update,
        "search": search,
        "top_paths": top_paths,
        "failures": failures,
        "acceptance": {
            "query_plan_shape": True,
            "structured_evidence_shape": True,
            "white_background_car_document_not_clothing": True,
            "degraded_until_region_attribute_models_exist": True,
        },
    }
    json_path = run_dir / "product_visual_search_contract_gate.json"
    md_path = run_dir / "product_visual_search_contract_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Product Visual Search Contract Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- top_paths: `{top_paths}`",
        f"- query_plan: `{plan}`",
        f"- failures: `{failures}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
