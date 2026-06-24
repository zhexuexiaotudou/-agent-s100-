#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    _record_from_sqlite_row,
    build_sqlite_inventory,
    ensure_report_dir,
    image_embedding_runtime_status,
    image_embedding_summary,
    iso_now,
    open_index_db,
    run_image_embedding_for_record,
    safe_write_json,
    safe_write_text,
    search_photo_semantic_index,
    similar_photo_groups,
    sqlite_index_status,
    upsert_image_embedding_result,
)


TOOL_ID = "ai_nas_photo_pipeline_acceptance"


def module_status() -> dict:
    modules = ["PIL", "torch", "transformers", "clip", "open_clip"]
    return {name: importlib.util.find_spec(name) is not None for name in modules}


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str, taken_at: str | None = None) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 620, 400), outline=(40, 40, 40), width=3)
    draw.text((40, 190), text, fill=(0, 0, 0))
    if taken_at:
        exif = Image.Exif()
        exif[306] = taken_at  # DateTime
        exif[36867] = taken_at  # DateTimeOriginal
        image.save(path, exif=exif)
    else:
        image.save(path)


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "photo_pipeline_fixture" / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    photos = personal / "Photos"
    write_fixture_image_with_gps(
        photos / "2024_child_beach_photo.jpg",
        (120, 190, 235),
        "child beach photo 2024",
        taken_at="2024:07:12 09:30:00",
    )
    shutil.copy2(photos / "2024_child_beach_photo.jpg", photos / "2024_child_beach_photo_copy.jpg")
    write_fixture_image(
        photos / "2024_white_car_photo.jpg",
        (238, 238, 232),
        "white car photo 2024",
        taken_at="2024:08:05 16:20:00",
    )
    write_fixture_image(
        photos / "2024_invoice_screenshot.jpg",
        (250, 250, 250),
        "invoice screenshot amount 5000 CNY",
        taken_at="2024:04:15 10:00:00",
    )
    write_fixture_image(
        photos / "2024_family_meal_photo.jpg",
        (210, 160, 120),
        "family meal dinner 2024",
        taken_at="2024:02:10 19:00:00",
    )
    return personal


def write_fixture_image_with_gps(path: Path, rgb: tuple[int, int, int], text: str, taken_at: str) -> None:
    from PIL import Image, ImageDraw
    from PIL.TiffImagePlugin import IFDRational

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 620, 400), outline=(40, 40, 40), width=3)
    draw.text((40, 190), text, fill=(0, 0, 0))
    exif = Image.Exif()
    exif[306] = taken_at
    exif[36867] = taken_at
    exif[34853] = {
        1: "N",
        2: (IFDRational(31, 1), IFDRational(13, 1), IFDRational(0, 1)),
        3: "E",
        4: (IFDRational(121, 1), IFDRational(28, 1), IFDRational(0, 1)),
    }
    image.save(path, exif=exif)


def load_photo_records(db_path: Path) -> list[dict]:
    con = open_index_db(db_path)
    try:
        rows = con.execute("SELECT * FROM records WHERE type = 'Photos' ORDER BY relative_path").fetchall()
        return [_record_from_sqlite_row(row) for row in rows]
    finally:
        con.close()


def run_photo_embeddings(db_path: Path, records: list[dict]) -> list[dict]:
    results = []
    for record in records:
        result = run_image_embedding_for_record(record)
        upsert_image_embedding_result(db_path, result)
        results.append(result)
    return results


def evaluate_metadata(records: list[dict]) -> dict:
    failures = []
    rows = []
    taken_at_count = 0
    place_label_count = 0
    phash_count = 0
    sha_count = 0
    gps_count = 0
    for record in records:
        photo = (record.get("metadata") or {}).get("photo") or {}
        labels = photo.get("labels") or []
        if photo.get("taken_at"):
            taken_at_count += 1
        if photo.get("gps"):
            gps_count += 1
        if set(labels) & {"beach", "meal", "car", "invoice", "screenshot"} or photo.get("gps"):
            place_label_count += 1
        if photo.get("phash"):
            phash_count += 1
        if record.get("sha256"):
            sha_count += 1
        rows.append(
            {
                "relative_path": record["relative_path"],
                "taken_at": photo.get("taken_at"),
                "gps": photo.get("gps"),
                "labels": labels,
                "phash": photo.get("phash"),
                "sha256": record.get("sha256"),
                "width": photo.get("width"),
                "height": photo.get("height"),
                "parse_error": record.get("parse_error"),
            }
        )
        if record.get("parse_error"):
            failures.append(f"photo_parse_error:{record['relative_path']}:{record.get('parse_error')}")
    if len(records) < 5:
        failures.append("missing_fixture_photo_records")
    if taken_at_count < 3:
        failures.append("insufficient_exif_time_metadata")
    if place_label_count < 4:
        failures.append("insufficient_location_or_folder_label_metadata")
    if gps_count < 1:
        failures.append("missing_gps_exif_location_metadata")
    if phash_count != len(records):
        failures.append("missing_phash_values")
    if sha_count != len(records):
        failures.append("missing_sha256_values")
    return {
        "passed": not failures,
        "failures": failures,
        "photo_count": len(records),
        "taken_at_count": taken_at_count,
        "place_label_or_gps_count": place_label_count,
        "gps_count": gps_count,
        "phash_count": phash_count,
        "sha256_count": sha_count,
        "records": rows,
    }


def evaluate_similarity(records: list[dict]) -> dict:
    groups = similar_photo_groups(records, max_distance=4)
    has_beach_duplicate = any(
        {"Photos/2024_child_beach_photo.jpg", "Photos/2024_child_beach_photo_copy.jpg"}
        <= {item["relative_path"] for item in group.get("files", [])}
        for group in groups
    )
    failures = [] if has_beach_duplicate else ["missing_beach_duplicate_phash_group"]
    return {"passed": not failures, "failures": failures, "group_count": len(groups), "groups": groups}


def evaluate_searches(db_path: Path) -> dict:
    queries = {
        "beach": "child beach photo 2024",
        "white_car": "white car photo 2024",
        "invoice_screenshot": "invoice screenshot 2024",
        "meal": "family meal dinner 2024",
    }
    expectations = {
        "beach": {"beach"},
        "white_car": {"white", "car"},
        "invoice_screenshot": {"invoice", "screenshot"},
        "meal": {"meal"},
    }
    results = {}
    failures = []
    for key, query in queries.items():
        matches = search_photo_semantic_index(db_path, query, limit=5)
        top = matches[0] if matches else None
        if not top:
            failures.append(f"missing_photo_search_match:{key}")
        else:
            matched = set(top.get("matched_intents") or [])
            if not expectations[key] <= matched:
                failures.append(f"photo_search_missing_intents:{key}:{sorted(expectations[key] - matched)}")
            if not top.get("reasons") or not top.get("evidence") or top.get("confidence") is None:
                failures.append(f"photo_search_missing_grounding:{key}")
        results[key] = {"query": query, "match_count": len(matches), "top": top}
    return {"passed": not failures, "failures": failures, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS bounded photo metadata/pHash/semantic-search acceptance.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--sqlite-index-path", type=Path, default=None)
    parser.add_argument("--use-existing-personal", action="store_true")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "photo_pipeline_acceptance")
    personal_root = args.personal_root if args.use_existing_personal and args.personal_root else prepare_fixture(run_dir)
    sqlite_index_path = args.sqlite_index_path or (run_dir / "photo_pipeline_acceptance.sqlite3")
    build_sqlite_inventory(personal_root, sqlite_index_path)
    records = load_photo_records(sqlite_index_path)
    embedding_results = run_photo_embeddings(sqlite_index_path, records)
    metadata_eval = evaluate_metadata(records)
    similarity_eval = evaluate_similarity(records)
    search_eval = evaluate_searches(sqlite_index_path)
    runtime = image_embedding_runtime_status()
    failed_embeddings = [item for item in embedding_results if item.get("status") == "image_embedding_failed"]
    failures = []
    failures.extend(metadata_eval["failures"])
    failures.extend(similarity_eval["failures"])
    failures.extend(search_eval["failures"])
    if failed_embeddings:
        failures.append("image_embedding_failed:" + ",".join(item["relative_path"] for item in failed_embeddings))
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_photo_pipeline_acceptance" if not failures else "failed_ai_nas_photo_pipeline_acceptance",
        "scope": "bounded fixture acceptance for photo EXIF/time/place labels, SHA256, pHash similarity, local visual embedding rows, and grounded photo semantic search",
        "runtime": {
            "modules": module_status(),
            "image_embedding": runtime,
        },
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "index_status": sqlite_index_status(sqlite_index_path),
        "metadata": metadata_eval,
        "similarity": similarity_eval,
        "embedding_results": embedding_results,
        "image_embedding_summary": image_embedding_summary(sqlite_index_path),
        "search": search_eval,
        "failures": failures,
        "audit": {
            "source_files_modified": False,
            "real_personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "face_recognition_performed": False,
            "production_clip_claimed": False,
            "writes": "bounded fixture photos, SQLite index/image_embeddings rows, and Markdown/JSON acceptance reports",
            "grounding_policy": "photo search claims must come from indexed EXIF/path labels, pHash/local visual metadata, OCR status when present, and explicit CLIP/person limitations",
        },
        "production_gap": "This validates metadata/pHash/local-visual plumbing and bounded photo search; production CLIP/object/person semantics still require local CLIP/open_clip/transformers runtime and model files.",
    }
    json_path = run_dir / "photo_pipeline_acceptance.json"
    md_path = run_dir / "photo_pipeline_acceptance.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Photo Pipeline Acceptance",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- photo_count: `{metadata_eval['photo_count']}`",
        f"- failures: `{failures}`",
        f"- production_clip_ready: `{runtime['production_clip_ready']}`",
        "- policy: bounded fixture/index/image-embedding report only; no real Personal mutation; no face recognition; no production CLIP claim",
        "",
        "## Metadata",
        "",
        f"- taken_at_count: `{metadata_eval['taken_at_count']}`",
        f"- place_label_or_gps_count: `{metadata_eval['place_label_or_gps_count']}`",
        f"- gps_count: `{metadata_eval['gps_count']}`",
        f"- phash_count: `{metadata_eval['phash_count']}`",
        f"- sha256_count: `{metadata_eval['sha256_count']}`",
        "",
        "## Similarity",
        "",
        f"- group_count: `{similarity_eval['group_count']}`",
        f"- failures: `{similarity_eval['failures']}`",
        "",
        "## Search",
        "",
    ]
    for key, result in search_eval["results"].items():
        top = result.get("top") or {}
        lines.append(
            f"- {key}: match_count `{result['match_count']}` top `{top.get('relative_path')}` "
            f"confidence `{top.get('confidence')}` intents `{top.get('matched_intents')}`"
        )
        if top.get("evidence"):
            lines.append(f"  - evidence: {top['evidence']}")
    lines.extend(["", "## Image Embedding", ""])
    lines.append(f"- status_counts: `{payload['image_embedding_summary']['status_counts']}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
