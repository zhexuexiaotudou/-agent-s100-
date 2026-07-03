#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_INDEX_PATH,
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    copy_movies_non_destructive,
    duplicate_groups,
    ensure_report_dir,
    load_index,
    safe_write_json,
    safe_write_text,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enhanced non-destructive movie organization report for AI-NAS MVP.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--copy", action="store_true", help="Copy movies into Personal/Sorted/Movies without overwriting.")
    args = parser.parse_args()

    index = load_index(args.index_path, args.personal_root, args.report_root)
    movies = [record for record in index.get("records", []) if record["type"] == "Movies"]
    run_dir = ensure_report_dir(args.report_root, "movie_sort_enhanced")
    manifest = copy_movies_non_destructive(movies, args.personal_root, run_dir) if args.copy else None
    payload = {
        "generated_from_index_at": index.get("generated_at"),
        "movie_count": len(movies),
        "copy_sort_executed": bool(args.copy),
        "manifest_path": str(run_dir / "movie_sort_manifest.json") if manifest else None,
        "duplicates": duplicate_groups(movies),
        "naming_suggestions": [
            {
                "relative_path": record["relative_path"],
                "suggested_pattern": "{Title}.{Year}.{Genre}",
                "year": record.get("year"),
                "tags": record.get("tags", []),
            }
            for record in movies
        ],
        "directory_suggestions": [
            "Personal/Sorted/Movies/<Year>/<Genre>/",
            "Keep Personal/Movies as the raw ingest directory.",
            "Only copy reviewed files; never move or delete originals automatically.",
        ],
    }
    json_path = run_dir / "movie_sort_enhanced.json"
    md_path = run_dir / "movie_sort_enhanced.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Movie Organization Report",
        "",
        f"- movie_count: `{payload['movie_count']}`",
        f"- copy_sort_executed: `{payload['copy_sort_executed']}`",
        "- policy: non-destructive copy; no source delete, move, overwrite",
        "",
        "## Naming Suggestions",
        "",
    ]
    for item in payload["naming_suggestions"]:
        lines.append(f"- `{item['relative_path']}` -> pattern `{item['suggested_pattern']}` | year `{item['year']}` | tags `{', '.join(item['tags'])}`")
    lines.extend(["", "## Directory Suggestions", ""])
    for item in payload["directory_suggestions"]:
        lines.append(f"- {item}")
    if payload["duplicates"]:
        lines.extend(["", "## Duplicate Movies", ""])
        for group in payload["duplicates"]:
            lines.append(f"- `{group['sha256'][:16]}...`: {group['count']} copies")
    if manifest:
        lines.extend(["", "## Copy Manifest", "", f"- `{run_dir / 'movie_sort_manifest.md'}`"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
