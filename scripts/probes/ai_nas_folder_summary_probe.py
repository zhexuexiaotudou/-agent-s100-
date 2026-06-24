#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ai_nas_common import (
    DEFAULT_INDEX_PATH,
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    ensure_report_dir,
    load_index,
    safe_write_json,
    safe_write_text,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate folder summary and deterministic Q&A evidence for AI-NAS MVP.")
    parser.add_argument("folder", nargs="?", default="Documents")
    parser.add_argument("question", nargs="?", default="这个文件夹里主要有什么？")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    args = parser.parse_args()

    index = load_index(args.index_path, args.personal_root, args.report_root)
    folder_prefix = args.folder.strip("/").lower()
    records = [
        record for record in index.get("records", [])
        if record["relative_path"].lower().startswith(folder_prefix + "/")
        or record["relative_path"].lower() == folder_prefix
    ]
    type_counts = Counter(record["type"] for record in records)
    keyword_counts = Counter(keyword for record in records for keyword in record.get("keywords", []))
    parse_failures = [record for record in records if record.get("parse_error")]
    payment_lines = [
        record for record in records
        if "payment" in record.get("summary", "").lower()
        or "付款" in record.get("summary", "")
        or "invoice" in record.get("summary", "").lower()
    ]
    answer_parts = []
    if records:
        answer_parts.append(f"{args.folder} contains {len(records)} indexed files.")
        if keyword_counts:
            answer_parts.append("Top keywords: " + ", ".join(word for word, _ in keyword_counts.most_common(8)) + ".")
        if payment_lines:
            answer_parts.append("Payment/invoice-related files: " + ", ".join(item["relative_path"] for item in payment_lines[:6]) + ".")
    else:
        answer_parts.append("No indexed files matched this folder.")
    if parse_failures:
        answer_parts.append(f"{len(parse_failures)} files had extraction limitations; see report.")

    payload = {
        "folder": args.folder,
        "question": args.question,
        "generated_from_index_at": index.get("generated_at"),
        "file_count": len(records),
        "type_counts": dict(type_counts),
        "top_keywords": keyword_counts.most_common(12),
        "answer": " ".join(answer_parts),
        "parse_failures": [
            {"relative_path": record["relative_path"], "parse_error": record.get("parse_error")}
            for record in parse_failures
        ],
        "records": records,
    }
    run_dir = ensure_report_dir(args.report_root, "folder_summary")
    json_path = run_dir / "folder_summary.json"
    md_path = run_dir / "folder_summary.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Folder Summary",
        "",
        f"- folder: `{args.folder}`",
        f"- question: `{args.question}`",
        f"- file_count: `{payload['file_count']}`",
        f"- type_counts: `{payload['type_counts']}`",
        "",
        "## Answer",
        "",
        payload["answer"],
        "",
        "## Files",
        "",
    ]
    for record in records:
        lines.append(f"- `{record['relative_path']}`: {record.get('summary', '')}")
    if parse_failures:
        lines.extend(["", "## Extraction Limitations", ""])
        for failure in payload["parse_failures"]:
            lines.append(f"- `{failure['relative_path']}`: `{failure['parse_error']}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
