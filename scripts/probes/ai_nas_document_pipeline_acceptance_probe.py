#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    _record_from_sqlite_row,
    build_sqlite_inventory,
    ensure_report_dir,
    iso_now,
    ocr_candidate_record,
    ocr_engine_status,
    ocr_results_summary,
    open_index_db,
    run_ocr_for_record,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
    upsert_ocr_result,
)
from ai_nas_folder_rag_probe import build_answer, collect_payment_nodes, folder_query_matches, load_folder_records


TOOL_ID = "ai_nas_document_pipeline_acceptance"


def module_status() -> dict:
    modules = ["pypdf", "pdfplumber", "reportlab", "fitz", "PIL", "pytesseract"]
    return {name: importlib.util.find_spec(name) is not None for name in modules}


def write_text_pdf(path: Path, lines: list[str]) -> bool:
    if importlib.util.find_spec("reportlab") is None:
        return False
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 72
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.save()
    return True


def write_scanned_pdf(path: Path, text: str) -> bool:
    if importlib.util.find_spec("reportlab") is None or importlib.util.find_spec("PIL") is None:
        return False
    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    image_path = path.with_suffix(".scan.png")
    image = Image.new("RGB", (900, 260), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((24, 100), text, fill=(0, 0, 0))
    image.save(image_path)
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    c.drawImage(str(image_path), 72, height - 260, width=420, height=130)
    c.save()
    return True


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "document_pipeline_fixture" / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    documents = personal / "Documents"
    documents.mkdir(parents=True, exist_ok=True)
    (documents / "2024_renovation_contract.txt").write_text(
        "Renovation contract 2024. Payment: deposit 20000 CNY on 2024-03-01; final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    (documents / "2024_reimbursement_invoice.txt").write_text(
        "Invoice and receipt for reimbursement. Amount: 12000 CNY. Date: 2024-04-15. Tax invoice number INV-2024-0415.\n",
        encoding="utf-8",
    )
    (documents / "research_paper_notes.txt").write_text(
        "Research paper. Abstract: local AI NAS retrieval evaluation. References include reproducibility and indexing.\n",
        encoding="utf-8",
    )
    (documents / "device_manual.txt").write_text(
        "User manual and instruction guide. Setup steps, troubleshooting, and safety instructions.\n",
        encoding="utf-8",
    )
    write_text_pdf(
        documents / "2024_contract_pdf_text.pdf",
        [
            "Renovation contract PDF text layer.",
            "Payment amount: 30000 CNY.",
            "Payment date: 2024-06-01.",
        ],
    )
    write_scanned_pdf(
        documents / "2024_scanned_invoice_requires_ocr.pdf",
        "Scanned invoice image only. Amount 5000 CNY.",
    )
    return personal


def all_document_records(db_path: Path) -> list[dict]:
    con = open_index_db(db_path)
    try:
        rows = con.execute("SELECT * FROM records WHERE type = 'Documents' ORDER BY relative_path").fetchall()
        return [_record_from_sqlite_row(row) for row in rows]
    finally:
        con.close()


def run_ocr_candidates(db_path: Path, records: list[dict]) -> list[dict]:
    candidates = [record for record in records if ocr_candidate_record(record, include_images=False)]
    results = []
    for record in candidates:
        result = run_ocr_for_record(record, max_pages=2)
        upsert_ocr_result(db_path, result)
        results.append(result)
    return results


def evaluate_records(records: list[dict]) -> dict:
    by_path = {record["relative_path"]: record for record in records}
    class_counts: dict[str, int] = {}
    parse_failures = []
    ocr_required = []
    for record in records:
        metadata = record.get("metadata") or {}
        doc_class = metadata.get("document_class")
        if doc_class:
            class_counts[doc_class] = class_counts.get(doc_class, 0) + 1
        if record.get("parse_error"):
            parse_failures.append({"relative_path": record["relative_path"], "parse_error": record.get("parse_error")})
        if (metadata.get("ocr") or {}).get("required") is True:
            ocr_required.append({"relative_path": record["relative_path"], "ocr": metadata.get("ocr"), "pdf": metadata.get("pdf")})
    pdf_text = by_path.get("Documents/2024_contract_pdf_text.pdf")
    scanned_pdf = by_path.get("Documents/2024_scanned_invoice_requires_ocr.pdf")
    failures = []
    for required_class in ["contract", "invoice", "paper", "manual"]:
        if class_counts.get(required_class, 0) <= 0:
            failures.append(f"missing_document_class:{required_class}")
    if not pdf_text or pdf_text.get("parse_error"):
        failures.append("text_pdf_not_extracted")
    if not scanned_pdf:
        failures.append("scanned_pdf_not_indexed")
    else:
        metadata = scanned_pdf.get("metadata") or {}
        ocr = metadata.get("ocr") or {}
        if ocr.get("required") is not True:
            failures.append("scanned_pdf_not_marked_ocr_required")
        if not scanned_pdf.get("parse_error") and not ocr:
            failures.append("scanned_pdf_missing_explicit_parse_or_ocr_status")
    return {
        "passed": not failures,
        "failures": failures,
        "document_class_counts": class_counts,
        "parse_failures": parse_failures,
        "ocr_required": ocr_required,
    }


def evaluate_no_fabrication(records: list[dict], ocr_results: list[dict], rag_eval: dict) -> dict:
    scanned_path = "Documents/2024_scanned_invoice_requires_ocr.pdf"
    by_path = {record["relative_path"]: record for record in records}
    scanned_pdf = by_path.get(scanned_path)
    ocr_by_path = {item["relative_path"]: item for item in ocr_results}
    ocr_result = ocr_by_path.get(scanned_path)
    failures = []
    summary = (scanned_pdf or {}).get("summary", "")
    ocr_status = (ocr_result or {}).get("status")
    ocr_text = (ocr_result or {}).get("text_preview") or ""
    completed_ocr = ocr_status == "ocr_completed" and bool(ocr_text.strip())
    leaked_terms = ["5000", "Scanned invoice image only"]

    if scanned_pdf and ((scanned_pdf.get("metadata") or {}).get("ocr") or {}).get("required") is True and not ocr_result:
        failures.append("scanned_pdf_missing_ocr_attempt")
    if scanned_pdf and not completed_ocr:
        if summary != "content_not_extracted":
            failures.append("scanned_pdf_summary_not_explicit_failure")
        if any(term.lower() in summary.lower() for term in leaked_terms):
            failures.append("scanned_pdf_summary_contains_unextracted_scan_text")
        for node in rag_eval.get("payment_nodes", []):
            node_text = " ".join(
                [
                    node.get("relative_path", ""),
                    " ".join(node.get("amounts") or []),
                    " ".join(node.get("payment_terms") or []),
                ]
            )
            if node.get("relative_path") == scanned_path or any(term.lower() in node_text.lower() for term in leaked_terms):
                failures.append("scanned_pdf_payment_node_without_completed_ocr")
                break
    return {
        "passed": not failures,
        "failures": failures,
        "scanned_pdf_path": scanned_path,
        "scanned_pdf_summary": summary,
        "ocr_status": ocr_status,
        "ocr_text_preview_present": bool(ocr_text.strip()),
        "policy": "scanned-image text cannot appear in summary or payment nodes unless OCR completes with extracted text",
    }


def evaluate_folder_rag(db_path: Path) -> dict:
    folder = "Documents"
    records = load_folder_records(db_path, folder)
    question = "What payment dates, amounts, and invoice evidence are in this folder?"
    matches = folder_query_matches(records, question, limit=12)
    parse_failures = [
        {"relative_path": record["relative_path"], "parse_error": record.get("parse_error")}
        for record in records
        if record.get("parse_error") and record.get("type") == "Documents"
    ]
    answer_status, answer = build_answer(folder, question, records, matches, parse_failures)
    payment_nodes = collect_payment_nodes(matches)
    no_answer_question = "What passport identifier Z9Q8X7 is in this folder?"
    no_answer_matches = folder_query_matches(records, no_answer_question, limit=12)
    no_answer_status, no_answer = build_answer(folder, no_answer_question, records, no_answer_matches, parse_failures=[])
    failures = []
    if answer_status not in {"grounded_answer", "partial_grounded_answer"}:
        failures.append(f"folder_rag_not_grounded:{answer_status}")
    if not payment_nodes:
        failures.append("folder_rag_missing_payment_nodes")
    for match in matches:
        if not match.get("reasons") or not match.get("evidence") or match.get("confidence") is None:
            failures.append(f"folder_rag_match_missing_grounding:{match.get('relative_path')}")
    no_answer_core_terms = {"passport", "z9q8x7"}
    no_answer_grounded = [
        match
        for match in no_answer_matches
        if any(term in (match.get("evidence") or "").lower() for term in no_answer_core_terms)
        or any(term in (match.get("summary") or "").lower() for term in no_answer_core_terms)
        or any(term in match.get("relative_path", "").lower() for term in no_answer_core_terms)
    ]
    if no_answer_grounded:
        failures.append("no_answer_question_found_unexpected_grounding")
    if no_answer_status not in {"no_grounded_answer", "no_grounded_answer_with_failures"}:
        failures.append(f"no_answer_question_not_explicit:{no_answer_status}")
    return {
        "passed": not failures,
        "failures": failures,
        "question": question,
        "answer_status": answer_status,
        "answer": answer,
        "match_count": len(matches),
        "payment_nodes": payment_nodes,
        "no_answer_question": no_answer_question,
        "no_answer_status": no_answer_status,
        "no_answer": no_answer,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS document extraction/OCR/folder-RAG acceptance over a bounded fixture.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--sqlite-index-path", type=Path, default=None)
    parser.add_argument("--use-existing-personal", action="store_true")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "document_pipeline_acceptance")
    personal_root = args.personal_root if args.use_existing_personal and args.personal_root else prepare_fixture(run_dir)
    sqlite_index_path = args.sqlite_index_path or (run_dir / "document_pipeline_acceptance.sqlite3")
    build_sqlite_inventory(personal_root, sqlite_index_path)
    records = all_document_records(sqlite_index_path)
    ocr_results = run_ocr_candidates(sqlite_index_path, records)
    record_eval = evaluate_records(records)
    rag_eval = evaluate_folder_rag(sqlite_index_path)
    no_fabrication_eval = evaluate_no_fabrication(records, ocr_results, rag_eval)
    failed_ocr = [item for item in ocr_results if item.get("status") == "ocr_failed"]
    allowed_ocr_statuses = {"ocr_completed", "ocr_completed_no_text", "blocked_missing_ocr_engine"}
    unexpected_ocr = [item for item in ocr_results if item.get("status") not in allowed_ocr_statuses]
    failures = []
    failures.extend(record_eval["failures"])
    failures.extend(rag_eval["failures"])
    failures.extend(no_fabrication_eval["failures"])
    if failed_ocr:
        failures.append("ocr_failed:" + ",".join(item["relative_path"] for item in failed_ocr))
    if unexpected_ocr:
        failures.append("unexpected_ocr_status:" + ",".join(item["status"] for item in unexpected_ocr))

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_document_pipeline_acceptance" if not failures else "failed_ai_nas_document_pipeline_acceptance",
        "scope": "bounded fixture acceptance for PDF text extraction, OCR-required scanned PDFs, document classification, folder RAG, and explicit no-answer handling",
        "runtime": {
            "modules": module_status(),
            "ocr": ocr_engine_status(),
        },
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "index_status": sqlite_index_status(sqlite_index_path),
        "document_record_count": len(records),
        "document_records": [
            {
                "relative_path": record["relative_path"],
                "document_class": (record.get("metadata") or {}).get("document_class"),
                "parse_error": record.get("parse_error"),
                "ocr": (record.get("metadata") or {}).get("ocr"),
                "summary": record.get("summary", "")[:240],
            }
            for record in records
        ],
        "classification": record_eval,
        "ocr_results": ocr_results,
        "ocr_summary": ocr_results_summary(sqlite_index_path),
        "folder_rag": rag_eval,
        "no_fabrication": no_fabrication_eval,
        "failures": failures,
        "audit": {
            "source_files_modified": False,
            "real_personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "invent_content": False,
            "writes": "bounded fixture documents, SQLite index/OCR rows, and Markdown/JSON acceptance reports",
            "grounding_policy": "PDF/OCR/folder-RAG claims must come from extracted/indexed evidence; missing OCR/runtime produces explicit blocked or no-answer status",
        },
    }

    json_path = run_dir / "document_pipeline_acceptance.json"
    md_path = run_dir / "document_pipeline_acceptance.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Document Pipeline Acceptance",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- document_record_count: `{len(records)}`",
        f"- failures: `{failures}`",
        "- policy: bounded fixture/index/OCR report only; no real Personal mutation and no invented content",
        "",
        "## Classification",
        "",
        f"- document_class_counts: `{record_eval['document_class_counts']}`",
        f"- parse_failures: `{record_eval['parse_failures']}`",
        f"- ocr_required: `{record_eval['ocr_required']}`",
        "",
        "## OCR Results",
        "",
    ]
    if not ocr_results:
        lines.append("- No OCR candidates were found.")
    for item in ocr_results:
        lines.append(f"- `{item['relative_path']}` status `{item['status']}` engine `{item.get('engine')}` error `{item.get('error')}`")
    lines.extend(["", "## Folder RAG", ""])
    lines.append(f"- answer_status: `{rag_eval['answer_status']}`")
    lines.append(f"- match_count: `{rag_eval['match_count']}`")
    lines.append(f"- payment_node_count: `{len(rag_eval['payment_nodes'])}`")
    lines.append(f"- no_answer_status: `{rag_eval['no_answer_status']}`")
    lines.append("")
    lines.append(rag_eval["answer"])
    lines.extend(["", "## No Fabrication", ""])
    lines.append(f"- passed: `{no_fabrication_eval['passed']}`")
    lines.append(f"- ocr_status: `{no_fabrication_eval['ocr_status']}`")
    lines.append(f"- scanned_pdf_summary: `{no_fabrication_eval['scanned_pdf_summary']}`")
    lines.append(f"- failures: `{no_fabrication_eval['failures']}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
