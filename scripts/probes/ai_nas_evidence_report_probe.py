#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sqlite_index_status,
)


DEFAULT_QUERY = "2024 renovation payment contract invoice screenshot"


def collect_payment_nodes(matches: list[dict]) -> list[dict]:
    nodes = []
    for match in matches:
        entities = match.get("entities") or {}
        dates = entities.get("dates") or []
        amounts = entities.get("amounts") or []
        terms = entities.get("payment_terms") or []
        if not dates and not amounts and not terms:
            continue
        nodes.append(
            {
                "relative_path": match["relative_path"],
                "document_class": match.get("document_class"),
                "dates": dates,
                "amounts": amounts,
                "payment_terms": terms,
                "confidence": match.get("confidence"),
            }
        )
    return nodes


def build_organizing_suggestions(matches: list[dict], collection_name: str) -> list[dict]:
    suggestions = []
    for match in matches:
        doc_class = match.get("document_class")
        photo_labels = ((match.get("photo") or {}).get("labels") or [])
        bucket = doc_class or (photo_labels[0] if photo_labels else match.get("type", "Other"))
        target = f"Collections/{collection_name}/{bucket}/{Path(match['relative_path']).name}"
        suggestions.append(
            {
                "action": "copy_suggestion_only",
                "source_relative_path": match["relative_path"],
                "suggested_target_relative_path": target,
                "requires_human_confirmation": True,
                "delete_source": False,
                "overwrite": False,
            }
        )
    return suggestions


def summarize_matches(matches: list[dict]) -> dict:
    by_type = Counter(match.get("type", "Unknown") for match in matches)
    by_doc_class = Counter(match.get("document_class") for match in matches if match.get("document_class"))
    photo_labels = Counter(
        label
        for match in matches
        for label in ((match.get("photo") or {}).get("labels") or [])
    )
    return {
        "match_count": len(matches),
        "type_counts": dict(sorted(by_type.items())),
        "document_class_counts": dict(sorted(by_doc_class.items())),
        "photo_label_counts": dict(sorted(photo_labels.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an auditable AI-NAS evidence report from a natural-language query.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--collection-name", default="query_evidence")
    args = parser.parse_args()

    if not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    matches = search_sqlite_index(args.sqlite_index_path, args.query, args.limit)
    payment_nodes = collect_payment_nodes(matches)
    suggestions = build_organizing_suggestions(matches, args.collection_name)
    index_status = sqlite_index_status(args.sqlite_index_path)
    payload = {
        "generated_at": iso_now(),
        "query": args.query,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": index_status,
        "summary": summarize_matches(matches),
        "matches": matches,
        "payment_nodes": payment_nodes,
        "copyable_organizing_suggestions": suggestions,
        "audit": {
            "tool_id": "ai_nas_evidence_report",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON report only",
            "requires_human_confirmation_for_suggestions": True,
        },
    }

    run_dir = ensure_report_dir(args.report_root, "evidence_report")
    json_path = run_dir / "evidence_report.json"
    md_path = run_dir / "evidence_report.md"
    safe_write_json(json_path, payload)

    lines = [
        "# AI-NAS Evidence Report",
        "",
        f"- query: `{args.query}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- match_count: `{payload['summary']['match_count']}`",
        f"- index_status: `{index_status.get('status')}`",
        "- policy: report only; no delete, no move, no overwrite",
        "",
        "## Summary",
        "",
        f"- type_counts: `{payload['summary']['type_counts']}`",
        f"- document_class_counts: `{payload['summary']['document_class_counts']}`",
        f"- photo_label_counts: `{payload['summary']['photo_label_counts']}`",
        "",
        "## Evidence Files",
        "",
    ]
    if not matches:
        lines.append("- No indexed evidence matched this query.")
    for match in matches:
        lines.append(
            f"- `{match['relative_path']}` | confidence `{match['confidence']}` | "
            f"type `{match.get('type')}` | source `{match.get('source')}`"
        )
        if match.get("document_class"):
            lines.append(f"  - document_class: `{match['document_class']}`")
        photo = match.get("photo") or {}
        if photo.get("labels"):
            lines.append(f"  - photo_labels: `{', '.join(photo['labels'])}`")
        lines.append(f"  - evidence: {match.get('evidence', '')}")
        lines.append(f"  - reasons: {', '.join(match.get('reasons', []))}")

    lines.extend(["", "## Payment Nodes", ""])
    if not payment_nodes:
        lines.append("- No structured payment/date/amount nodes were extracted from matched files.")
    for node in payment_nodes:
        lines.append(f"- `{node['relative_path']}`")
        if node["dates"]:
            lines.append(f"  - dates: `{', '.join(node['dates'])}`")
        if node["amounts"]:
            lines.append(f"  - amounts: `{', '.join(node['amounts'])}`")
        for term in node["payment_terms"]:
            lines.append(f"  - payment_term: {term}")

    lines.extend(["", "## Copyable Organizing Suggestions", ""])
    if not suggestions:
        lines.append("- No suggestions because no evidence files matched.")
    for suggestion in suggestions:
        lines.append(
            f"- copy `{suggestion['source_relative_path']}` -> "
            f"`{suggestion['suggested_target_relative_path']}`"
        )
    lines.extend(
        [
            "",
            "## Audit",
            "",
            "- source_files_modified: `False`",
            "- delete_performed: `False`",
            "- move_performed: `False`",
            "- overwrite_performed: `False`",
            "- suggestions_require_human_confirmation: `True`",
        ]
    )
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
