#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    IMAGE_CAPTION_STATUS_COMPLETED,
    build_sqlite_inventory,
    ensure_image_captions_for_photos,
    ensure_report_dir,
    image_caption_summary,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_photo_semantic_index,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_llm_caption_visual_search_gate"
OK = "ok_ai_nas_llm_caption_visual_search_gate"
FAILED = "failed_ai_nas_llm_caption_visual_search_gate"


def write_fixture_image(path: Path, rgb: tuple[int, int, int], label: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 610, 390), outline=(28, 62, 70), width=4)
    draw.text((56, 188), label, fill=(10, 20, 25))
    image.save(path, quality=92)


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "caption_visual_search_fixture" / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    photos = personal / "Photos"
    write_fixture_image(photos / "person_white_top.jpg", (215, 224, 230), "generic person wearing white top")
    write_fixture_image(photos / "person_blue_top.jpg", (118, 160, 225), "generic person wearing blue top")
    write_fixture_image(photos / "white_car.jpg", (242, 242, 236), "white car")
    write_fixture_image(photos / "white_wall_room.jpg", (245, 245, 241), "white wall room")
    write_fixture_image(photos / "white_document_screenshot.jpg", (250, 250, 250), "white document screenshot")
    return personal


def fixture_caption_provider(record: dict) -> dict:
    rel = str(record.get("relative_path") or "")
    if "person_white_top" in rel:
        return {
            "provider": "fixture_llm_caption_provider",
            "model_id": "fixture-large-vision-caption",
            "caption": "A generic person is wearing a white shirt and white upper garment.",
            "objects": ["person"],
            "people": [
                {
                    "role": "generic_person",
                    "clothing": {
                        "upper_color": "white",
                        "upper_garment": "shirt top",
                        "evidence_terms": ["person", "wearing", "white", "shirt", "top"],
                    },
                }
            ],
            "attributes": {"colors": ["white"], "scene": ["portrait"]},
            "scene": "generic portrait photo",
            "visible_text": [],
        }
    if "person_blue_top" in rel:
        return {
            "provider": "fixture_llm_caption_provider",
            "model_id": "fixture-large-vision-caption",
            "caption": "A generic person is wearing a blue shirt and blue top.",
            "objects": ["person"],
            "people": [
                {
                    "role": "generic_person",
                    "clothing": {
                        "upper_color": "blue",
                        "upper_garment": "shirt top",
                        "evidence_terms": ["person", "wearing", "blue", "shirt", "top"],
                    },
                }
            ],
            "attributes": {"colors": ["blue"], "scene": ["portrait"]},
            "scene": "generic portrait photo",
            "visible_text": [],
        }
    if "white_car" in rel:
        return {
            "provider": "fixture_llm_caption_provider",
            "model_id": "fixture-large-vision-caption",
            "caption": "A white car parked outdoors. No person or clothing is visible.",
            "objects": ["white car", "vehicle"],
            "people": [],
            "attributes": {"colors": ["white"], "scene": ["outdoor vehicle"]},
            "scene": "vehicle photo",
            "visible_text": [],
        }
    if "white_wall" in rel:
        return {
            "provider": "fixture_llm_caption_provider",
            "model_id": "fixture-large-vision-caption",
            "caption": "A mostly white wall in an empty room. No person or clothing is visible.",
            "objects": ["wall", "room"],
            "people": [],
            "attributes": {"colors": ["white"], "scene": ["indoor room"]},
            "scene": "empty room",
            "visible_text": [],
        }
    return {
        "provider": "fixture_llm_caption_provider",
        "model_id": "fixture-large-vision-caption",
        "caption": "A white document screenshot with text. No person or clothing is visible.",
        "objects": ["document", "screenshot"],
        "people": [],
        "attributes": {"colors": ["white"], "scene": ["document screenshot"]},
        "scene": "document screenshot",
        "visible_text": ["sample document"],
    }


def evaluate_query(db_path: Path, query: str) -> dict:
    matches = search_photo_semantic_index(db_path, query, limit=5)
    top_paths = [item.get("relative_path") for item in matches[:5]]
    expected = "Photos/person_white_top.jpg"
    false_positive_needles = ("white_car", "white_wall", "white_document", "person_blue_top")
    failures = []
    if not matches or matches[0].get("relative_path") != expected:
        failures.append(f"top_result_not_white_top:{query}:{top_paths[:3]}")
    if any(any(needle in str(path) for needle in false_positive_needles) for path in top_paths):
        failures.append(f"false_positive_in_top5:{query}:{top_paths}")
    top = matches[0] if matches else {}
    caption = top.get("image_caption") or {}
    if caption.get("status") != IMAGE_CAPTION_STATUS_COMPLETED or "white" not in " ".join(top.get("matched_intents") or []):
        failures.append(f"missing_caption_grounding:{query}")
    return {
        "query": query,
        "passed": not failures,
        "failures": failures,
        "top_paths": top_paths,
        "top": top,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate LLM-caption-first visual search for clothing/color queries.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "llm_caption_visual_search_gate")
    personal_root = prepare_fixture(run_dir)
    sqlite_index_path = run_dir / "llm_caption_visual_search.sqlite3"

    build_sqlite_inventory(personal_root, sqlite_index_path)
    caption_update = ensure_image_captions_for_photos(sqlite_index_path, limit=20, caption_provider=fixture_caption_provider)
    caption_summary = image_caption_summary(sqlite_index_path)
    query_results = [
        evaluate_query(sqlite_index_path, "穿白色上衣的照片"),
        evaluate_query(sqlite_index_path, "photos of people wearing white tops"),
    ]
    failures = []
    if caption_update.get("completed", 0) < 5:
        failures.append("caption_provider_did_not_complete_all_fixtures")
    for result in query_results:
        failures.extend(result["failures"])

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "index_status": sqlite_index_status(sqlite_index_path),
        "caption_update": caption_update,
        "caption_summary": caption_summary,
        "queries": query_results,
        "failures": failures,
        "acceptance": {
            "caption_first": True,
            "white_top_query_requires_clothing_caption": True,
            "whole_image_white_fallback_not_sufficient": True,
            "face_recognition_performed": False,
        },
    }
    json_path = run_dir / "llm_caption_visual_search_gate.json"
    md_path = run_dir / "llm_caption_visual_search_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS LLM Caption Visual Search Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- caption_completed: `{caption_update.get('completed')}`",
        f"- failures: `{failures}`",
        "",
        "## Queries",
        "",
    ]
    for item in query_results:
        top = item.get("top") or {}
        lines.append(
            f"- `{item['query']}` -> top `{top.get('relative_path')}` "
            f"confidence `{top.get('confidence')}` intents `{top.get('matched_intents')}`"
        )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
