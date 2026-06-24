#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_INDEX_PATH,
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    duplicate_groups,
    ensure_report_dir,
    load_index,
    safe_write_json,
    safe_write_text,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Duplicate-file report for AI-NAS MVP; never deletes files.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    args = parser.parse_args()

    index = load_index(args.index_path, args.personal_root, args.report_root)
    groups = duplicate_groups(index.get("records", []))
    payload = {
        "generated_from_index_at": index.get("generated_at"),
        "duplicate_group_count": len(groups),
        "potential_reclaim_bytes": sum(group["potential_reclaim_bytes"] for group in groups),
        "delete_performed": False,
        "move_performed": False,
        "requires_human_confirmation": True,
        "groups": groups,
    }
    run_dir = ensure_report_dir(args.report_root, "duplicate_report")
    json_path = run_dir / "duplicate_report.json"
    md_path = run_dir / "duplicate_report.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Duplicate File Report",
        "",
        f"- duplicate_group_count: `{payload['duplicate_group_count']}`",
        f"- potential_reclaim_bytes: `{payload['potential_reclaim_bytes']}`",
        "- policy: report only; no delete, no move; cleanup requires human confirmation",
        "",
        "## Groups",
        "",
    ]
    if not groups:
        lines.append("- No SHA256 duplicate groups found.")
    for group in groups:
        lines.append(f"- sha256 `{group['sha256'][:16]}...` | count `{group['count']}` | reclaim `{group['potential_reclaim_bytes']}` bytes")
        for file_item in group["files"]:
            lines.append(f"  - `{file_item['relative_path']}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
