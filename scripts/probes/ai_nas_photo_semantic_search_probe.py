#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    IMAGE_EMBEDDING_DIM,
    IMAGE_EMBEDDING_MODEL_ID,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    image_embedding_runtime_status,
    image_embedding_summary,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_photo_semantic_index,
    sqlite_index_status,
)


DEFAULT_QUERY = "找孩子海边照片 白色车 发票截图"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded photo semantic search over indexed Personal photos with explicit evidence and limitations."
    )
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--no-refresh-index", action="store_true")
    args = parser.parse_args()

    if not args.no_refresh_index:
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)
    elif not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    embedding_upsert = ensure_image_embeddings_for_photos(args.sqlite_index_path)
    matches = search_photo_semantic_index(args.sqlite_index_path, args.query, args.limit)
    runtime = image_embedding_runtime_status()
    payload = {
        "generated_at": iso_now(),
        "query": args.query,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "match_count": len(matches),
        "matches": matches,
        "image_embedding": {
            "model_id": IMAGE_EMBEDDING_MODEL_ID,
            "dim": IMAGE_EMBEDDING_DIM,
            "backend": "PIL histogram local visual embedding plus metadata/path/OCR-status scoring",
            "production_clip_ready": runtime["production_clip_ready"],
            "production_clip_or_transformer": False,
            "limitations": [
                "This search uses indexed EXIF/path labels, OCR status/text when available, and local_visual_embedding_v1 color hints.",
                "It is not CLIP and cannot robustly verify objects, scenes, people, or faces.",
                "Missing intents are reported explicitly instead of inventing visual evidence.",
            ],
            "upsert_summary": embedding_upsert,
            "status_summary": image_embedding_summary(args.sqlite_index_path),
        },
        "index_status": sqlite_index_status(args.sqlite_index_path),
        "audit": {
            "tool_id": "ai_nas_photo_semantic_search",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "SQLite image_embeddings rows if missing plus Markdown/JSON report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "photo_semantic_search")
    json_path = run_dir / "photo_semantic_search.json"
    md_path = run_dir / "photo_semantic_search.md"
    safe_write_json(json_path, payload)

    lines = [
        "# AI-NAS Photo Semantic Search",
        "",
        f"- query: `{args.query}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- match_count: `{len(matches)}`",
        f"- image_embedding_model: `{IMAGE_EMBEDDING_MODEL_ID}`",
        f"- production_clip_ready: `{runtime['production_clip_ready']}`",
        "- backend: metadata/path/OCR-status scoring plus local_visual_embedding_v1 color hints",
        "- limitation: not CLIP; missing visual/person concepts are reported explicitly",
        "- policy: report/index only; no delete, no move, no overwrite",
        "",
        "## Matches",
        "",
    ]
    if not matches:
        lines.append("- No indexed photo matched the bounded metadata/local-visual criteria.")
    for match in matches:
        lines.append(
            f"- `{match['relative_path']}` | confidence `{match['confidence']}` | score `{match['score']}`"
        )
        lines.append(f"  - matched_intents: `{', '.join(match.get('matched_intents', []))}`")
        lines.append(f"  - missing_intents: `{', '.join(match.get('missing_intents', []))}`")
        lines.append(f"  - evidence: {match.get('evidence', '')}")
        lines.append(f"  - reasons: {', '.join(match.get('reasons', []))}")
        ocr = match.get("ocr") or {}
        if ocr.get("status"):
            lines.append(f"  - ocr_status: `{ocr['status']}`")
    lines.extend(
        [
            "",
            "## Image Embedding Status",
            "",
            f"- upsert_summary: `{embedding_upsert}`",
            f"- status_counts: `{payload['image_embedding']['status_summary']['status_counts']}`",
            "",
            "## Audit",
            "",
        ]
    )
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
