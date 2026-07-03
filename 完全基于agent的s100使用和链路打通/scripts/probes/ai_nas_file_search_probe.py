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
    score_record,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Natural-language file search over the AI-NAS Personal inventory.")
    parser.add_argument("query", nargs="?", default="找一下 2019 年的犯罪电影")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    index = load_index(args.index_path, args.personal_root, args.report_root)
    matches = []
    for record in index.get("records", []):
        score, reasons = score_record(record, args.query)
        if score <= 0:
            continue
        matches.append(
            {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "type": record["type"],
                "score": round(score, 2),
                "confidence": min(0.95, round(0.35 + score / 20, 2)),
                "reasons": reasons[:6],
                "summary": record.get("summary", ""),
            }
        )
    matches.sort(key=lambda item: (item["score"], item["relative_path"]), reverse=True)
    matches = matches[: args.limit]

    payload = {
        "query": args.query,
        "index_path": str(args.index_path),
        "generated_from_index_at": index.get("generated_at"),
        "match_count": len(matches),
        "matches": matches,
    }
    run_dir = ensure_report_dir(args.report_root, "file_search")
    json_path = run_dir / "file_search.json"
    md_path = run_dir / "file_search.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS File Search",
        "",
        f"- query: `{args.query}`",
        f"- match_count: `{len(matches)}`",
        f"- index_path: `{args.index_path}`",
        "",
        "## Matches",
        "",
    ]
    if not matches:
        lines.append("- No deterministic metadata/content match. Run inventory first or add embeddings later.")
    for match in matches:
        lines.append(f"- `{match['relative_path']}` | confidence `{match['confidence']}` | {match['summary']}")
        lines.append(f"  - reasons: {', '.join(match['reasons'])}")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
