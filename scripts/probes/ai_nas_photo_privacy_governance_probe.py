#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    image_embedding_runtime_status,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_photo_semantic_index,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_photo_privacy_governance"


def module_status(names: list[str]) -> dict:
    return {name: importlib.util.find_spec(name) is not None for name in names}


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (640, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 620, 400), outline=(40, 40, 40), width=3)
    draw.text((40, 190), text, fill=(0, 0, 0))
    image.save(path)


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    photos = personal / "Photos"
    write_fixture_image(photos / "2024_child_beach_photo.jpg", (120, 190, 235), "child beach metadata label")
    write_fixture_image(photos / "2024_family_meal_photo.jpg", (210, 160, 120), "family meal metadata label")
    write_fixture_image(photos / "2024_white_car_photo.jpg", (245, 245, 245), "white car metadata label")
    return personal


def evaluate_match_privacy(matches: list[dict]) -> list[str]:
    failures = []
    if not matches:
        failures.append("no_photo_matches")
        return failures
    for match in matches:
        label = match.get("relative_path") or "unknown"
        privacy = match.get("privacy") or {}
        if privacy.get("face_recognition_performed") is not False:
            failures.append(f"{label}:face_recognition_flag_not_false")
        if privacy.get("person_identity_verified") is not False:
            failures.append(f"{label}:person_identity_verified_not_false")
        if privacy.get("requires_privacy_review_before_face_model") is not True:
            failures.append(f"{label}:missing_privacy_review_gate")
        if privacy.get("person_or_child_terms_source") != "path_metadata_labels_only":
            failures.append(f"{label}:person_terms_source_not_metadata_only")
        if not privacy.get("limitations"):
            failures.append(f"{label}:missing_privacy_limitations")
        if "child" in (match.get("matched_intents") or []):
            reason_text = " ".join(match.get("reasons") or []).lower()
            if "face recognition is not performed" not in reason_text:
                failures.append(f"{label}:child_match_missing_no_face_recognition_reason")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS photo privacy governance contract for face/person recognition deferral.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "photo_privacy_governance")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    sqlite_index_path = run_dir / "photo_privacy_governance.sqlite3"
    build_sqlite_inventory(personal_root, sqlite_index_path)
    image_upsert = ensure_image_embeddings_for_photos(sqlite_index_path)
    runtime = image_embedding_runtime_status()
    optional_face_modules = module_status(["face_recognition", "deepface", "insightface"])
    queries = {
        "child_beach": "child beach photo 2024",
        "person_face": "person face child photo",
        "white_car": "white car photo 2024",
    }
    results = {key: search_photo_semantic_index(sqlite_index_path, query, limit=5) for key, query in queries.items()}
    failures = []
    for key, matches in results.items():
        failures.extend(f"{key}:{failure}" for failure in evaluate_match_privacy(matches))
    if any(optional_face_modules.values()):
        # Importability alone is not a failure, but it must not translate into executed face recognition.
        face_runtime_note = "optional face runtime importable but disabled by policy"
    else:
        face_runtime_note = "no optional face runtime importable"
    if not any(
        "child" in (match.get("matched_intents") or [])
        and (match.get("privacy") or {}).get("face_recognition_performed") is False
        for match in results["child_beach"]
    ):
        failures.append("child_query_missing_metadata_only_child_match")
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_photo_privacy_governance" if not failures else "failed_ai_nas_photo_privacy_governance",
        "scope": "bounded photo privacy governance contract; face recognition and person identity remain disabled",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "runtime": {
            "image_embedding": runtime,
            "optional_face_modules": optional_face_modules,
            "face_runtime_note": face_runtime_note,
        },
        "image_embedding_upsert": image_upsert,
        "queries": queries,
        "results": results,
        "summary": {
            "query_count": len(queries),
            "face_recognition_performed": False,
            "person_identity_verified": False,
            "child_person_terms_metadata_only": True,
            "privacy_review_required_before_face_model": True,
            "failures": failures,
        },
        "index_status": sqlite_index_status(sqlite_index_path),
        "audit": {
            "source_files_modified": False,
            "real_personal_source_modified": False,
            "fixture_only": True,
            "face_recognition_performed": False,
            "face_embedding_created": False,
            "person_identity_verified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "bounded fixture photos, SQLite index/image_embeddings rows, and Markdown/JSON privacy governance reports",
        },
        "production_gap": "Face/person recognition remains intentionally out of scope until a separate privacy, consent, retention, and compliance review is approved.",
    }
    json_path = run_dir / "photo_privacy_governance.json"
    md_path = run_dir / "photo_privacy_governance.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Photo Privacy Governance",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- face_recognition_performed: `{payload['summary']['face_recognition_performed']}`",
        f"- person_identity_verified: `{payload['summary']['person_identity_verified']}`",
        f"- child_person_terms_metadata_only: `{payload['summary']['child_person_terms_metadata_only']}`",
        f"- privacy_review_required_before_face_model: `{payload['summary']['privacy_review_required_before_face_model']}`",
        f"- failures: `{failures}`",
        "- policy: no face embedding, clustering, recognition, identity matching, network call, or real Personal mutation",
        "",
        "## Queries",
        "",
    ]
    for key, matches in results.items():
        top = matches[0] if matches else {}
        privacy = top.get("privacy") or {}
        lines.append(
            f"- `{key}` matches `{len(matches)}` top `{top.get('relative_path')}` "
            f"face_recognition `{privacy.get('face_recognition_performed')}` identity_verified `{privacy.get('person_identity_verified')}`"
        )
    lines.extend(["", "## Optional Face Runtime", ""])
    for key, value in optional_face_modules.items():
        lines.append(f"- {key}: `{value}`")
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
