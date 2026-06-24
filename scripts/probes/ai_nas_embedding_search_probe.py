#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    EMBEDDING_DIM,
    EMBEDDING_MODEL_ID,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    sqlite_index_status,
)


DEFAULT_QUERY = "2024 renovation payment contract invoice screenshot"


def main() -> int:
    parser = argparse.ArgumentParser(description="Local lightweight embedding search over the AI-NAS SQLite inventory.")
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

    matches = search_embedding_index(args.sqlite_index_path, args.query, args.limit)
    status = sqlite_index_status(args.sqlite_index_path)
    payload = {
        "generated_at": iso_now(),
        "query": args.query,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": status,
        "embedding": {
            "model_id": EMBEDDING_MODEL_ID,
            "dim": EMBEDDING_DIM,
            "backend": "deterministic local feature hashing",
            "production_clip_or_transformer": False,
            "replaceable_backend": True,
            "limitations": [
                "This is a local hash embedding interface for ranking and evidence plumbing.",
                "It is not CLIP, not a sentence-transformer, and not a substitute for a production semantic model.",
                "Use it to validate SQLite vector storage, cosine ranking, and audit reports before adding real models.",
            ],
        },
        "match_count": len(matches),
        "matches": matches,
        "audit": {
            "tool_id": "ai_nas_embedding_search",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON report plus SQLite index refresh only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "embedding_search")
    json_path = run_dir / "embedding_search.json"
    md_path = run_dir / "embedding_search.md"
    safe_write_json(json_path, payload)

    lines = [
        "# AI-NAS Embedding Search",
        "",
        f"- query: `{args.query}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- match_count: `{len(matches)}`",
        f"- model_id: `{EMBEDDING_MODEL_ID}`",
        f"- dim: `{EMBEDDING_DIM}`",
        "- backend: deterministic local feature hashing",
        "- limitation: not CLIP, not sentence-transformer; replaceable backend for production embeddings",
        "- policy: report/index only; no delete, no move, no overwrite",
        "",
        "## Matches",
        "",
    ]
    if not matches:
        lines.append("- No embedding candidate passed the deterministic local threshold.")
    for match in matches:
        lines.append(
            f"- `{match['relative_path']}` | confidence `{match['confidence']}` | "
            f"embedding `{match['embedding_similarity']}` | lexical `{match['lexical_score']}`"
        )
        if match.get("document_class"):
            lines.append(f"  - document_class: `{match['document_class']}`")
        photo = match.get("photo") or {}
        if photo.get("labels"):
            lines.append(f"  - photo_labels: `{', '.join(photo['labels'])}`")
        lines.append(f"  - evidence: {match.get('evidence', '')}")
        lines.append(f"  - reasons: {', '.join(match.get('reasons', []))}")
    lines.extend(
        [
            "",
            "## Audit",
            "",
            "- source_files_modified: `False`",
            "- delete_performed: `False`",
            "- move_performed: `False`",
            "- overwrite_performed: `False`",
        ]
    )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
