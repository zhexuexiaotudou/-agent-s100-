#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_report_dir,
    is_document_parse_failure,
    iso_now,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)
from ai_nas_folder_rag_probe import build_answer, collect_payment_nodes, folder_query_matches, load_folder_records


TOOL_ID = "ai_nas_folder_rag_grounding_contract"
FOLDER = "Documents"
PAYMENT_QUESTION = "What payment dates, amounts, and invoice evidence are in this folder?"
UNKNOWN_QUESTION = "What passport identifier Z9Q8X7 and bank account are in this folder?"


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / FOLDER
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "2024_renovation_contract.txt").write_text(
        "\n".join(
            [
                "Renovation contract 2024.",
                "Payment deposit 20000 CNY on 2024-03-01.",
                "Final payment 8000 CNY on 2024-05-20.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs / "2024_reimbursement_invoice.txt").write_text(
        "\n".join(
            [
                "Invoice receipt for renovation reimbursement.",
                "Amount 12000 CNY. Date 2024-04-15.",
                "Tax invoice number INV-2024-0415.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs / "2024_payment_chat_screenshot_note.txt").write_text(
        "Chat screenshot note: renovation payment discussed on 2024-04-20, amount 5000 CNY.\n",
        encoding="utf-8",
    )
    (docs / "espresso_machine_manual.txt").write_text(
        "Espresso machine manual. Cleaning cycle, grinder calibration, and warranty notes.\n",
        encoding="utf-8",
    )
    (docs / "unreadable_office_attachment.docx").write_bytes(b"not-a-real-office-document")
    return personal


def values_are_covered(node: dict, match: dict) -> list[str]:
    failures = []
    evidence = " ".join(
        [
            str(match.get("relative_path") or ""),
            str(match.get("evidence") or ""),
            str(match.get("summary") or ""),
            " ".join(match.get("reasons") or []),
        ]
    ).lower()
    for value in node.get("dates") or []:
        if value.lower() not in evidence:
            failures.append(f"date_not_covered:{node.get('relative_path')}:{value}")
    for value in node.get("amounts") or []:
        if value.lower() not in evidence:
            failures.append(f"amount_not_covered:{node.get('relative_path')}:{value}")
    return failures


def evaluate_grounded_answer(db_path: Path) -> dict:
    records = load_folder_records(db_path, FOLDER)
    parse_failures = [
        {"relative_path": record["relative_path"], "parse_error": record.get("parse_error")}
        for record in records
        if is_document_parse_failure(record)
    ]
    matches = folder_query_matches(records, PAYMENT_QUESTION, limit=12)
    answer_status, answer = build_answer(FOLDER, PAYMENT_QUESTION, records, matches, parse_failures)
    payment_nodes = collect_payment_nodes(matches)
    by_path = {match["relative_path"]: match for match in matches}
    failures = []
    if answer_status not in {"grounded_answer", "partial_grounded_answer"}:
        failures.append(f"payment_answer_not_grounded:{answer_status}")
    if len(payment_nodes) < 3:
        failures.append("payment_nodes_lt_3")
    for match in matches:
        label = match.get("relative_path") or "unknown"
        if not match.get("reasons"):
            failures.append(f"{label}:missing_reasons")
        if not match.get("evidence"):
            failures.append(f"{label}:missing_evidence")
        if not isinstance(match.get("confidence"), (float, int)) or not (0 < float(match["confidence"]) <= 1):
            failures.append(f"{label}:invalid_confidence")
    for node in payment_nodes:
        match = by_path.get(node["relative_path"])
        if not match:
            failures.append(f"payment_node_without_match:{node['relative_path']}")
            continue
        failures.extend(values_are_covered(node, match))
    if not parse_failures:
        failures.append("parse_failure_not_explicitly_recorded")
    if "unreadable_office_attachment.docx" not in " ".join(failure["relative_path"] for failure in parse_failures):
        failures.append("office_parse_failure_missing_from_answer_context")
    return {
        "passed": not failures,
        "failures": failures,
        "folder": FOLDER,
        "question": PAYMENT_QUESTION,
        "answer_status": answer_status,
        "answer": answer,
        "match_count": len(matches),
        "matches": matches,
        "payment_nodes": payment_nodes,
        "parse_failures": parse_failures,
    }


def evaluate_no_answer(db_path: Path) -> dict:
    records = load_folder_records(db_path, FOLDER)
    parse_failures = [
        {"relative_path": record["relative_path"], "parse_error": record.get("parse_error")}
        for record in records
        if is_document_parse_failure(record)
    ]
    matches = folder_query_matches(records, UNKNOWN_QUESTION, limit=12)
    answer_status, answer = build_answer(FOLDER, UNKNOWN_QUESTION, records, matches, parse_failures)
    leaked_terms = ["z9q8x7", "passport identifier", "bank account"]
    answer_lower = answer.lower()
    grounded_unknown_matches = [
        match
        for match in matches
        if any(term in " ".join([match.get("relative_path", ""), match.get("evidence", ""), match.get("summary", "")]).lower() for term in leaked_terms)
    ]
    failures = []
    if matches and not grounded_unknown_matches:
        failures.append("unknown_question_returned_ungrounded_matches")
    if answer_status not in {"no_grounded_answer", "no_grounded_answer_with_failures"}:
        failures.append(f"unknown_question_not_explicit_no_answer:{answer_status}")
    if any(term in answer_lower for term in leaked_terms) and "no indexed evidence" not in answer_lower:
        failures.append("unknown_identifier_appears_as_claim")
    if parse_failures and answer_status != "no_grounded_answer_with_failures":
        failures.append("no_answer_did_not_surface_parse_failures")
    return {
        "passed": not failures,
        "failures": failures,
        "folder": FOLDER,
        "question": UNKNOWN_QUESTION,
        "answer_status": answer_status,
        "answer": answer,
        "match_count": len(matches),
        "matches": matches,
        "parse_failures": parse_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS folder RAG grounding and no-fabrication contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=1000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "folder_rag_grounding_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = run_dir / "folder_rag_grounding_contract.sqlite3"
    index_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    grounded = evaluate_grounded_answer(db_path)
    no_answer = evaluate_no_answer(db_path)
    failures = grounded["failures"] + no_answer["failures"]

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_folder_rag_grounding_contract" if not failures else "failed_ai_nas_folder_rag_grounding_contract",
        "scope": "bounded folder-level RAG grounding, citation coverage, explicit parse failures, and no-answer refusal",
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "index_status": index_status,
        "sqlite_index_status": sqlite_index_status(db_path),
        "grounded_answer_case": grounded,
        "no_answer_case": no_answer,
        "summary": {
            "grounded_answer_passed": grounded["passed"],
            "no_answer_passed": no_answer["passed"],
            "payment_node_count": len(grounded["payment_nodes"]),
            "match_count": grounded["match_count"],
            "parse_failure_count": len(grounded["parse_failures"]),
            "unknown_match_count": no_answer["match_count"],
            "all_payment_nodes_have_evidence": not any(failure.startswith(("date_not_covered", "amount_not_covered")) for failure in failures),
            "no_answer_explicit": no_answer["answer_status"] in {"no_grounded_answer", "no_grounded_answer_with_failures"},
            "failures": failures,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "invent_content": False,
            "writes": "isolated fixture documents, SQLite/FTS rows, and Markdown/JSON folder-RAG grounding reports only",
        },
    }
    json_path = run_dir / "folder_rag_grounding_contract.json"
    md_path = run_dir / "folder_rag_grounding_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Folder RAG Grounding Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- grounded_answer_passed: `{payload['summary']['grounded_answer_passed']}`",
        f"- no_answer_passed: `{payload['summary']['no_answer_passed']}`",
        f"- payment_node_count: `{payload['summary']['payment_node_count']}`",
        f"- parse_failure_count: `{payload['summary']['parse_failure_count']}`",
        f"- unknown_match_count: `{payload['summary']['unknown_match_count']}`",
        f"- all_payment_nodes_have_evidence: `{payload['summary']['all_payment_nodes_have_evidence']}`",
        f"- no_answer_explicit: `{payload['summary']['no_answer_explicit']}`",
        f"- failures: `{failures}`",
        "",
        "## Contract",
        "",
        "- Folder-level answers must be grounded in indexed files from the requested folder.",
        "- Every payment/date/amount node must map back to a matched file with reasons, evidence, and confidence.",
        "- Parse failures must be visible instead of silently omitted.",
        "- Unsupported identifier questions must return explicit no-answer status instead of fabricated content.",
        "",
        "## Audit",
        "",
    ]
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
