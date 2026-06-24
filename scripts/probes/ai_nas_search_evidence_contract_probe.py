#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ai_nas_case_packet_probe import (
    build_case_answer,
    build_copy_suggestions,
    collect_payment_nodes as collect_case_payment_nodes,
    filter_case_matches,
    infer_gaps,
    merge_match,
    summarize,
)
from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    search_photo_semantic_index,
    search_sqlite_index,
    sqlite_index_status,
)
from ai_nas_folder_rag_probe import build_answer, collect_payment_nodes, folder_query_matches, load_folder_records


TOOL_ID = "ai_nas_search_evidence_contract"
CASE_QUERY = "2024 renovation payment contract invoice receipt chat screenshot"
FOLDER_QUESTION = "What payment dates, amounts, and invoice evidence are in this folder?"
COLLECTION = "2024_renovation_evidence_contract"


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (720, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 700, 400), outline=(40, 40, 40), width=3)
    draw.text((40, 180), text, fill=(0, 0, 0))
    image.save(path)


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    photos = personal / "Photos"
    docs.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    (docs / "2024_renovation_contract.txt").write_text(
        "Renovation contract 2024. Payment deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    (docs / "2024_renovation_invoice_receipt.txt").write_text(
        "Invoice receipt for renovation reimbursement. Amount 12000 CNY. Date 2024-04-15. Receipt RCPT-2024-0415.\n",
        encoding="utf-8",
    )
    (docs / "unrelated_manual.txt").write_text(
        "Kitchen device manual. Not related to renovation payment invoice receipt evidence.\n",
        encoding="utf-8",
    )
    write_fixture_image(
        photos / "2024_renovation_chat_invoice_screenshot.jpg",
        (245, 245, 238),
        "chat screenshot invoice paid 5000 CNY 2024-04-20",
    )
    write_fixture_image(
        photos / "2024_family_beach_meal_photo.jpg",
        (80, 170, 230),
        "family beach meal photo 2024",
    )
    return personal


def contract_failures(source: str, matches: list[dict], *, require_summary: bool = False, require_original_path: bool = False) -> list[str]:
    failures = []
    if not matches:
        return [f"{source}:no_results"]
    for idx, match in enumerate(matches):
        label = match.get("relative_path") or match.get("original_path") or f"row_{idx}"
        if not (match.get("relative_path") or match.get("original_path")):
            failures.append(f"{source}:{label}:missing_relative_or_original_path")
        if require_original_path and not match.get("original_path"):
            failures.append(f"{source}:{label}:missing_original_path")
        confidence = match.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0 < float(confidence) <= 1):
            failures.append(f"{source}:{label}:invalid_confidence")
        reasons = match.get("reasons") or match.get("why_matched") or []
        if not isinstance(reasons, list) or not reasons:
            failures.append(f"{source}:{label}:missing_reasons")
        evidence = match.get("evidence")
        evidence_fragments = match.get("evidence_fragments")
        evidence_snippets = match.get("evidence_snippets")
        if isinstance(evidence, str):
            has_evidence = bool(evidence.strip())
        elif isinstance(evidence, list):
            has_evidence = bool(evidence)
        else:
            has_evidence = bool(evidence_fragments or evidence_snippets)
        if not has_evidence:
            failures.append(f"{source}:{label}:missing_evidence")
        if require_summary and not match.get("summary"):
            failures.append(f"{source}:{label}:missing_summary")
    return failures


def build_case_packet(personal_root: Path, db_path: Path, limit: int) -> dict:
    ensure_image_embeddings_for_photos(db_path)
    merged: dict[str, dict] = {}
    for match in search_sqlite_index(db_path, CASE_QUERY, limit):
        merge_match(merged, match, "sqlite_text_fts_metadata")
    for match in search_embedding_index(db_path, CASE_QUERY, limit):
        merge_match(merged, match, "local_hash_embedding")
    for match in search_photo_semantic_index(db_path, f"{CASE_QUERY} invoice screenshot receipt", limit):
        merge_match(merged, match, "photo_semantic_local_visual")
    candidates = sorted(merged.values(), key=lambda item: (item["confidence"], item["score"], item["relative_path"]), reverse=True)
    matches, rejected = filter_case_matches(CASE_QUERY, candidates)
    matches = matches[:limit]
    payment_nodes = collect_case_payment_nodes(matches)
    gaps = infer_gaps(CASE_QUERY, matches)
    return {
        "query": CASE_QUERY,
        "answer": build_case_answer(matches, payment_nodes, gaps),
        "summary": summarize(matches),
        "matches": matches,
        "rejected_matches": rejected,
        "payment_nodes": payment_nodes,
        "gaps": gaps,
        "copyable_organizing_suggestions": build_copy_suggestions(matches, COLLECTION),
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
    }


def user_facing_case_results(matches: list[dict]) -> list[dict]:
    rows = []
    for match in matches:
        photo = match.get("photo") or {}
        evidence = match.get("evidence_fragments") or []
        summary = match.get("summary") or ""
        if not summary and photo:
            bits = []
            if photo.get("labels"):
                bits.append("labels: " + ", ".join(photo["labels"]))
            if photo.get("taken_at"):
                bits.append("taken_at: " + str(photo["taken_at"]))
            summary = "; ".join(bits) or "photo metadata result"
        rows.append(
            {
                "relative_path": match.get("relative_path"),
                "original_path": match.get("path"),
                "why_matched": match.get("reasons", [])[:10],
                "evidence_snippets": evidence[:3],
                "summary": summary,
                "confidence": match.get("confidence"),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS bounded search evidence contract acceptance.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--max-files", type=int, default=1000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "search_evidence_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = run_dir / "search_evidence_contract.sqlite3"
    index_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    image_upsert = ensure_image_embeddings_for_photos(db_path)

    text_matches = search_sqlite_index(db_path, CASE_QUERY, args.limit)
    embedding_matches = search_embedding_index(db_path, CASE_QUERY, args.limit)
    photo_matches = search_photo_semantic_index(db_path, "invoice screenshot beach meal", args.limit)
    folder_records = load_folder_records(db_path, "Documents")
    folder_matches = folder_query_matches(folder_records, FOLDER_QUESTION, args.limit)
    folder_answer_status, folder_answer = build_answer(
        "Documents",
        FOLDER_QUESTION,
        folder_records,
        folder_matches,
        [],
    )
    case_packet = build_case_packet(personal_root, db_path, args.limit)
    user_results = user_facing_case_results(case_packet["matches"])

    checks = {
        "sqlite_text_search": contract_failures("sqlite_text_search", text_matches[:3]),
        "local_hash_embedding_search": contract_failures("local_hash_embedding_search", embedding_matches[:3]),
        "photo_semantic_search": contract_failures("photo_semantic_search", photo_matches[:3]),
        "folder_rag": contract_failures("folder_rag", folder_matches[:3]),
        "case_packet": contract_failures("case_packet", case_packet["matches"][:3]),
        "user_facing_case_results": contract_failures(
            "user_facing_case_results",
            user_results,
            require_summary=True,
            require_original_path=True,
        ),
    }
    failures = [failure for failures in checks.values() for failure in failures]
    if "Documents/unrelated_manual.txt" in {match.get("relative_path") for match in case_packet["matches"]}:
        failures.append("case_packet:unrelated_manual_not_rejected")
    if not case_packet["payment_nodes"]:
        failures.append("case_packet:missing_payment_nodes")
    if not case_packet["copyable_organizing_suggestions"]:
        failures.append("case_packet:missing_copyable_organizing_suggestions")
    if folder_answer_status not in {"grounded_answer", "partial_grounded_answer"}:
        failures.append(f"folder_rag:answer_not_grounded:{folder_answer_status}")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_search_evidence_contract" if not failures else "failed_ai_nas_search_evidence_contract",
        "scope": "bounded fixture contract that every returned search/case result carries path, reasons, evidence, and confidence",
        "fixture": {
            "personal_root": str(personal_root),
            "case_query": CASE_QUERY,
            "folder_question": FOLDER_QUESTION,
        },
        "sqlite_index_path": str(db_path),
        "index_status": index_status,
        "image_embedding_upsert": image_upsert,
        "results": {
            "sqlite_text_search": text_matches,
            "local_hash_embedding_search": embedding_matches,
            "photo_semantic_search": photo_matches,
            "folder_rag": {
                "answer_status": folder_answer_status,
                "answer": folder_answer,
                "matches": folder_matches,
                "payment_nodes": collect_payment_nodes(folder_matches),
            },
            "case_packet": case_packet,
            "user_facing_case_results": user_results,
        },
        "summary": {
            "text_match_count": len(text_matches),
            "embedding_match_count": len(embedding_matches),
            "photo_match_count": len(photo_matches),
            "folder_match_count": len(folder_matches),
            "case_match_count": len(case_packet["matches"]),
            "user_facing_result_count": len(user_results),
            "payment_node_count": len(case_packet["payment_nodes"]),
            "copyable_suggestion_count": len(case_packet["copyable_organizing_suggestions"]),
            "all_checked_results_have_path_reason_evidence_confidence": not failures,
            "failures": failures,
        },
        "contract_checks": checks,
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "isolated fixture files, SQLite/FTS and image embedding rows, Markdown/JSON reports only",
            "grounding_policy": "result rows are accepted only with reasons, evidence, confidence, and source/original path; gaps remain explicit",
        },
        "production_gap": "This verifies the result contract on a bounded fixture. Production still needs real corpus coverage and production embedding/CLIP/OCR runtimes.",
    }

    json_path = run_dir / "search_evidence_contract.json"
    md_path = run_dir / "search_evidence_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Search Evidence Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- case_query: `{CASE_QUERY}`",
        f"- text_match_count: `{payload['summary']['text_match_count']}`",
        f"- embedding_match_count: `{payload['summary']['embedding_match_count']}`",
        f"- photo_match_count: `{payload['summary']['photo_match_count']}`",
        f"- folder_match_count: `{payload['summary']['folder_match_count']}`",
        f"- case_match_count: `{payload['summary']['case_match_count']}`",
        f"- user_facing_result_count: `{payload['summary']['user_facing_result_count']}`",
        f"- all_checked_results_have_path_reason_evidence_confidence: `{payload['summary']['all_checked_results_have_path_reason_evidence_confidence']}`",
        f"- failures: `{failures}`",
        "",
        "## Contract",
        "",
        "- Every accepted result must include path/original path, reasons, evidence snippets, and confidence.",
        "- User-facing case results must also include summary and original path.",
        "- Negative or unrelated files must not be promoted into the case packet.",
        "",
        "## Audit",
        "",
        "- Isolated fixture only; no real Personal files, services, network calls, source moves, deletes, or overwrites.",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
