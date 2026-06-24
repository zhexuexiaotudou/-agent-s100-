#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    evidence_snippet,
    ensure_report_dir,
    is_document_parse_failure,
    open_index_db,
    safe_write_json,
    safe_write_text,
    score_record,
    sqlite_index_status,
    _record_from_sqlite_row,
)


DEFAULT_QUESTION = "What payment dates, amounts, and invoice evidence are in this folder?"


def normalize_folder(folder: str) -> str:
    cleaned = folder.strip().replace("\\", "/").strip("/")
    if not cleaned:
        return "Documents"
    parts = [part for part in cleaned.split("/") if part and part not in {".", ".."}]
    return "/".join(parts) if parts else "Documents"


def load_folder_records(db_path: Path, folder: str) -> list[dict]:
    prefix = normalize_folder(folder).lower()
    con = open_index_db(db_path)
    try:
        rows = con.execute("SELECT * FROM records ORDER BY relative_path").fetchall()
    finally:
        con.close()
    records = []
    for row in rows:
        record = _record_from_sqlite_row(row)
        rel = record["relative_path"].lower()
        if rel == prefix or rel.startswith(prefix + "/"):
            records.append(record)
    return records


def collect_payment_nodes(matches: list[dict]) -> list[dict]:
    nodes = []
    for match in matches:
        entities = match.get("entities") or {}
        dates = entities.get("dates") or []
        amounts = entities.get("amounts") or []
        terms = entities.get("payment_terms") or []
        if dates or amounts or terms:
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


def folder_query_matches(records: list[dict], question: str, limit: int) -> list[dict]:
    matches = []
    for record in records:
        score, reasons = score_record(record, question)
        combined_text = " ".join(
            [
                record.get("summary", ""),
                " ".join(record.get("keywords", [])),
                " ".join(record.get("tags", [])),
            ]
        ).lower()
        negative_context = bool(re.search(r"\b(unrelated|not related|irrelevant)\b.{0,80}\b(payment|invoice|amount|date|renovation)\b", combined_text))
        if negative_context:
            score -= 8
            reasons.append("explicit negative context near query terms")
        metadata = record.get("metadata") or {}
        entities = metadata.get("entities") or {}
        if negative_context and not entities.get("dates") and not entities.get("amounts"):
            continue
        photo = metadata.get("photo") or {}
        if entities.get("dates") or entities.get("amounts") or entities.get("payment_terms"):
            if any(term in question.lower() for term in ["payment", "pay", "invoice", "amount", "date", "付款", "发票", "票据", "金额", "日期"]):
                score += 3
                reasons.append("structured date/amount/payment metadata available")
        if photo and any(term in question.lower() for term in ["photo", "image", "照片", "图片", "截图"]):
            score += 2
            reasons.append("photo metadata available")
        if score <= 0:
            continue
        matches.append(
            {
                "path": record["path"],
                "relative_path": record["relative_path"],
                "type": record["type"],
                "score": round(score, 2),
                "confidence": min(0.93, round(0.25 + score / 45, 2)),
                "reasons": sorted(set(reasons))[:10],
                "evidence": evidence_snippet(record, question),
                "summary": record.get("summary", ""),
                "document_class": metadata.get("document_class"),
                "entities": entities,
                "photo": photo,
                "parse_error": record.get("parse_error"),
                "source": "sqlite_folder_rag",
            }
        )
    matches.sort(key=lambda item: (item["score"], item["relative_path"]), reverse=True)
    return matches[:limit]


def build_answer(folder: str, question: str, records: list[dict], matches: list[dict], parse_failures: list[dict]) -> tuple[str, str]:
    if not records:
        return "no_folder_records", f"No indexed files were found under `{folder}`."
    if not matches:
        if parse_failures:
            return (
                "no_grounded_answer_with_failures",
                f"No indexed evidence in `{folder}` answered the question. {len(parse_failures)} files had extraction failures, so the answer may be incomplete.",
            )
        return "no_grounded_answer", f"No indexed evidence in `{folder}` answered the question."

    payment_nodes = collect_payment_nodes(matches)
    lines = [f"Answer is grounded in {len(matches)} matched files from `{folder}`."]
    if payment_nodes:
        for node in payment_nodes[:8]:
            bits = []
            if node["dates"]:
                bits.append("dates " + ", ".join(node["dates"][:4]))
            if node["amounts"]:
                bits.append("amounts " + ", ".join(node["amounts"][:4]))
            if node["payment_terms"]:
                bits.append("payment terms " + " | ".join(node["payment_terms"][:2]))
            if bits:
                lines.append(f"{node['relative_path']}: " + "; ".join(bits) + ".")
    else:
        for match in matches[:5]:
            lines.append(f"{match['relative_path']}: {match['evidence']}")
    if parse_failures:
        lines.append(f"{len(parse_failures)} files in the folder had extraction failures and are listed separately.")
        return "partial_grounded_answer", " ".join(lines)
    return "grounded_answer", " ".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-grounded folder-level RAG over the AI-NAS SQLite inventory.")
    parser.add_argument("folder", nargs="?", default="Documents")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    folder = normalize_folder(args.folder)
    if not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)
    records = load_folder_records(args.sqlite_index_path, folder)
    matches = folder_query_matches(records, args.question, args.limit)
    parse_failures = [
        {"relative_path": record["relative_path"], "parse_error": record.get("parse_error")}
        for record in records
        if is_document_parse_failure(record)
    ]
    answer_status, answer = build_answer(folder, args.question, records, matches, parse_failures)
    payment_nodes = collect_payment_nodes(matches)
    type_counts = Counter(record["type"] for record in records)
    doc_class_counts = Counter(
        (record.get("metadata") or {}).get("document_class")
        for record in records
        if (record.get("metadata") or {}).get("document_class")
    )
    payload = {
        "folder": folder,
        "question": args.question,
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": sqlite_index_status(args.sqlite_index_path),
        "answer_status": answer_status,
        "answer": answer,
        "file_count": len(records),
        "match_count": len(matches),
        "type_counts": dict(sorted(type_counts.items())),
        "document_class_counts": dict(sorted(doc_class_counts.items())),
        "matches": matches,
        "payment_nodes": payment_nodes,
        "parse_failures": parse_failures,
        "audit": {
            "tool_id": "ai_nas_folder_rag",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "grounding_policy": "answers only from indexed folder evidence; unanswered gaps are explicit",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "folder_rag")
    json_path = run_dir / "folder_rag.json"
    md_path = run_dir / "folder_rag.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Folder RAG",
        "",
        f"- folder: `{folder}`",
        f"- question: `{args.question}`",
        f"- answer_status: `{answer_status}`",
        f"- file_count: `{len(records)}`",
        f"- match_count: `{len(matches)}`",
        "- policy: folder-scoped evidence only; no invented content; no file mutation",
        "",
        "## Answer",
        "",
        answer,
        "",
        "## Evidence",
        "",
    ]
    if not matches:
        lines.append("- No matching indexed evidence.")
    for match in matches:
        lines.append(f"- `{match['relative_path']}` | confidence `{match['confidence']}` | source `{match['source']}`")
        if match.get("document_class"):
            lines.append(f"  - document_class: `{match['document_class']}`")
        lines.append(f"  - evidence: {match['evidence']}")
        lines.append(f"  - reasons: {', '.join(match['reasons'])}")
    lines.extend(["", "## Payment Nodes", ""])
    if not payment_nodes:
        lines.append("- No structured date/amount/payment nodes found in matched files.")
    for node in payment_nodes:
        lines.append(f"- `{node['relative_path']}`")
        if node["dates"]:
            lines.append(f"  - dates: `{', '.join(node['dates'])}`")
        if node["amounts"]:
            lines.append(f"  - amounts: `{', '.join(node['amounts'])}`")
        for term in node["payment_terms"]:
            lines.append(f"  - payment_term: {term}")
    if parse_failures:
        lines.extend(["", "## Extraction Failures", ""])
        for failure in parse_failures:
            lines.append(f"- `{failure['relative_path']}`: `{failure['parse_error']}`")
    lines.extend(["", "## Audit", "", "- source_files_modified: `False`", "- delete_performed: `False`", "- move_performed: `False`", "- overwrite_performed: `False`"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
