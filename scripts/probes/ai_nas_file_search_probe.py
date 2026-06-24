#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_INDEX_PATH,
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    evidence_snippet,
    ensure_report_dir,
    load_index,
    safe_write_json,
    safe_write_text,
    score_record,
    search_sqlite_index,
    sqlite_index_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Natural-language file search over the AI-NAS Personal inventory.")
    parser.add_argument("query", nargs="?", default="找一下 2019 年的犯罪电影")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    search_engine = "sqlite_fts5"
    matches = search_sqlite_index(args.sqlite_index_path, args.query, args.limit)
    status = sqlite_index_status(args.sqlite_index_path)

    if not matches:
        search_engine = "json_fallback"
        index = load_index(args.index_path, args.personal_root, args.report_root)
        fallback_matches = []
        for record in index.get("records", []):
            score, reasons = score_record(record, args.query)
            if score <= 0:
                continue
            fallback_matches.append(
                {
                    "path": record["path"],
                    "relative_path": record["relative_path"],
                    "type": record["type"],
                    "score": round(score, 2),
                    "confidence": min(0.95, round(0.35 + score / 24, 2)),
                    "reasons": reasons[:8],
                    "evidence": evidence_snippet(record, args.query),
                    "summary": record.get("summary", ""),
                    "document_class": (record.get("metadata") or {}).get("document_class"),
                    "entities": (record.get("metadata") or {}).get("entities", {}),
                    "photo": (record.get("metadata") or {}).get("photo", {}),
                    "source": "json_metadata",
                }
            )
        fallback_matches.sort(key=lambda item: (item["score"], item["relative_path"]), reverse=True)
        matches = fallback_matches[: args.limit]

    payload = {
        "query": args.query,
        "index_path": str(args.index_path),
        "sqlite_index_path": str(args.sqlite_index_path),
        "search_engine": search_engine,
        "generated_from_index_at": status.get("last_scan_finished_at"),
        "index_status": status,
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
        f"- search_engine: `{search_engine}`",
        f"- index_path: `{args.sqlite_index_path}`",
        f"- index_status: `{status.get('status')}`",
        "",
        "## Matches",
        "",
    ]
    if not matches:
        lines.append("- No deterministic metadata/content match. Run inventory first or add embeddings later.")
    for match in matches:
        doc_class = match.get("document_class")
        doc_text = f" | doc_class `{doc_class}`" if doc_class else ""
        lines.append(f"- `{match['relative_path']}` | confidence `{match['confidence']}` | source `{match['source']}`{doc_text}")
        lines.append(f"  - evidence: {match['evidence']}")
        lines.append(f"  - reasons: {', '.join(match['reasons'])}")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
