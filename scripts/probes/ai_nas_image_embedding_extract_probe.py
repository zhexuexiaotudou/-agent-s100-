#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    _record_from_sqlite_row,
    build_sqlite_inventory,
    image_embedding_runtime_status,
    image_embedding_summary,
    open_index_db,
    run_image_embedding_for_record,
    safe_write_json,
    safe_write_text,
    ensure_report_dir,
    upsert_image_embedding_result,
)


def load_photo_records(db_path: Path, limit: int) -> list[dict]:
    con = open_index_db(db_path)
    try:
        rows = con.execute("SELECT * FROM records WHERE type = 'Photos' ORDER BY relative_path LIMIT ?", (limit,)).fetchall()
        return [_record_from_sqlite_row(row) for row in rows]
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local visual image embeddings and report production CLIP readiness.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--no-refresh-index", action="store_true")
    args = parser.parse_args()

    if not args.no_refresh_index:
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)
    elif not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    runtime = image_embedding_runtime_status()
    records = load_photo_records(args.sqlite_index_path, max(1, args.limit))
    results = []
    for record in records:
        result = run_image_embedding_for_record(record)
        upsert_image_embedding_result(args.sqlite_index_path, result)
        results.append(result)
    summary = image_embedding_summary(args.sqlite_index_path)
    completed = [item for item in results if item["status"] == "local_visual_embedding_completed"]
    failed = [item for item in results if item["status"] == "image_embedding_failed"]
    payload = {
        "verdict": "ok_ai_nas_image_embedding_extract" if not failed else "limited_ai_nas_image_embedding_extract",
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "runtime": runtime,
        "photo_count": len(records),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "production_clip_ready": runtime["production_clip_ready"],
        "local_visual_embedding_ready": runtime["local_visual_embedding_ready"],
        "model": {
            "model_id": "local_visual_embedding_v1",
            "production_clip_or_transformer": False,
            "replaceable_backend": True,
            "limitations": [
                "This is a local color/brightness visual vector for plumbing and similarity readiness.",
                "It is not CLIP and cannot provide robust object/person/place semantic understanding.",
                "Install a production CLIP/open_clip/transformers runtime to replace this backend.",
            ],
        },
        "results": results,
        "image_embedding_summary": summary,
        "audit": {
            "tool_id": "ai_nas_image_embedding_extract",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "SQLite image_embeddings rows plus Markdown/JSON report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "image_embedding_extract")
    json_path = run_dir / "image_embedding_extract.json"
    md_path = run_dir / "image_embedding_extract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Image Embedding Extract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- production_clip_ready: `{runtime['production_clip_ready']}`",
        f"- local_visual_embedding_ready: `{runtime['local_visual_embedding_ready']}`",
        f"- photo_count: `{len(records)}`",
        f"- completed_count: `{len(completed)}`",
        f"- failed_count: `{len(failed)}`",
        "- limitation: local_visual_embedding_v1 is not CLIP; it is a replaceable plumbing backend",
        "",
        "## Results",
        "",
    ]
    if not results:
        lines.append("- No indexed photos found.")
    for item in results:
        lines.append(f"- `{item['relative_path']}` | status `{item['status']}` | engine `{item.get('engine')}`")
        meta = item.get("metadata") or {}
        if meta.get("production_clip_status"):
            lines.append(f"  - production_clip_status: `{meta['production_clip_status']}`")
        if meta.get("mean_rgb"):
            lines.append(f"  - mean_rgb: `{meta['mean_rgb']}`")
        if item.get("error"):
            lines.append(f"  - error: `{item['error']}`")
    lines.extend(["", "## Status Summary", ""])
    lines.append(f"- status_counts: `{summary['status_counts']}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
