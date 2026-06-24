#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_INDEX_PATH,
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    ensure_report_dir,
    load_index,
    safe_write_json,
    safe_write_text,
    similar_photo_groups,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report pHash-based similar photo groups; never modifies photos.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--max-distance", type=int, default=8)
    args = parser.parse_args()

    index = load_index(args.index_path, args.personal_root, args.report_root)
    groups = similar_photo_groups(index.get("records", []), max_distance=args.max_distance)
    payload = {
        "generated_from_index_at": index.get("generated_at"),
        "index_path": str(args.index_path),
        "algorithm": "64-bit DCT perceptual hash",
        "max_distance": args.max_distance,
        "group_count": len(groups),
        "delete_performed": False,
        "move_performed": False,
        "requires_human_confirmation": True,
        "groups": groups,
    }
    run_dir = ensure_report_dir(args.report_root, "photo_similarity")
    json_path = run_dir / "photo_similarity.json"
    md_path = run_dir / "photo_similarity.md"
    safe_write_json(json_path, payload)

    lines = [
        "# AI-NAS Photo Similarity",
        "",
        f"- algorithm: `{payload['algorithm']}`",
        f"- max_distance: `{args.max_distance}`",
        f"- group_count: `{len(groups)}`",
        "- policy: report only; no delete, no move; cleanup requires human confirmation",
        "",
        "## Groups",
        "",
    ]
    if not groups:
        lines.append("- No pHash-similar photo groups found.")
    for idx, group in enumerate(groups, start=1):
        lines.append(f"### Group {idx}")
        lines.append("")
        for item in group["files"]:
            labels = ", ".join(item.get("labels", []))
            lines.append(f"- `{item['relative_path']}` | phash `{item['phash']}` | labels `{labels}`")
        for edge in group["edges"]:
            lines.append(f"  - edge `{edge['left']}` <-> `{edge['right']}` distance `{edge['phash_distance']}`")
        lines.append("")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
