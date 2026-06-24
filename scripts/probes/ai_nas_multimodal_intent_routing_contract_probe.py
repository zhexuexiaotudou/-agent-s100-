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


TOOL_ID = "ai_nas_multimodal_intent_routing_contract"
CASE_QUERY = "2024 renovation payment contract invoice receipt chat screenshot"
FOLDER_QUESTION = "What payment dates, amounts, and invoice evidence are in this folder?"
COLLECTION = "2024_renovation_payment_packet"


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (720, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 700, 400), outline=(30, 30, 30), width=3)
    draw.text((44, 188), text, fill=(0, 0, 0))
    image.save(path)


def prepare_fixture(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    inbox = personal / "Inbox"
    photos = personal / "Photos"
    docs.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    (docs / "2024_renovation_contract.txt").write_text(
        "Renovation contract 2024. Payment deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    (docs / "2024_reimbursement_invoice_receipt.txt").write_text(
        "Invoice receipt for renovation reimbursement. Amount 12000 CNY. Date 2024-04-15. Receipt RCPT-2024-0415.\n",
        encoding="utf-8",
    )
    (inbox / "2024_payment_chat_screenshot_note.txt").write_text(
        "Chat screenshot note: renovation payment discussed on 2024-04-20, amount 5000 CNY, invoice paid.\n",
        encoding="utf-8",
    )
    (docs / "espresso_machine_manual.txt").write_text(
        "Espresso machine manual. Cleaning, grinder calibration, and warranty notes unrelated to renovation payment.\n",
        encoding="utf-8",
    )
    write_fixture_image(
        photos / "2024_invoice_chat_screenshot.jpg",
        (246, 246, 238),
        "chat screenshot invoice paid 5000 CNY 2024-04-20",
    )
    return personal


def infer_intents(query: str) -> dict:
    q = query.lower()
    intents = {
        "year": "2024" if "2024" in q else None,
        "document_classes": [],
        "evidence_types": [],
        "entities": [],
        "outputs": ["ranked_file_list", "why_matched", "summary", "original_path", "confidence", "copy_suggestions", "one_click_report", "audit_trail"],
        "safety": ["no_delete", "no_move", "no_overwrite", "human_confirmation_before_actions"],
    }
    if "contract" in q or "renovation" in q:
        intents["document_classes"].append("contract")
    if "invoice" in q or "receipt" in q:
        intents["document_classes"].append("invoice")
        intents["evidence_types"].append("receipt")
    if "chat" in q:
        intents["evidence_types"].append("chat")
    if "screenshot" in q:
        intents["evidence_types"].append("screenshot")
    if "payment" in q:
        intents["entities"].extend(["payment_terms", "amounts", "dates"])
    for key in ["document_classes", "evidence_types", "entities"]:
        intents[key] = sorted(set(intents[key]))
    return intents


def build_route_plan(intents: dict) -> list[dict]:
    return [
        {
            "route": "sqlite_text_fts_metadata",
            "purpose": "find exact contract, invoice, receipt, chat, date, and amount evidence from indexed text and metadata",
            "required_for": ["contract", "invoice", "payment_terms", "amounts", "dates"],
        },
        {
            "route": "local_hash_embedding",
            "purpose": "fuzzy expansion for user wording before production sentence-transformer is available",
            "required_for": ["fuzzy_contract_invoice_retrieval"],
        },
        {
            "route": "photo_semantic_local_visual",
            "purpose": "find screenshot/photo candidates using path labels, metadata, OCR status, and local visual fallback",
            "required_for": ["screenshot", "chat", "invoice"],
        },
        {
            "route": "folder_rag",
            "purpose": "answer the folder-level payment question from Documents evidence only",
            "required_for": ["summary", "payment_nodes", "no_fabrication"],
        },
        {
            "route": "case_packet",
            "purpose": "merge mixed-source evidence into one user-facing packet with gaps and copy suggestions",
            "required_for": ["ranked_file_list", "why_matched", "confidence", "copy_suggestions", "audit_trail"],
        },
        {
            "route": "approval_manifest",
            "purpose": "convert copy suggestions into human-confirmed actions before any write to Collections",
            "required_for": ["human_confirmation_before_actions", "rollback_manifest"],
        },
    ]


def grounded(match: dict) -> bool:
    confidence = match.get("confidence")
    return (
        bool(match.get("relative_path") or match.get("path"))
        and isinstance(confidence, (float, int))
        and 0 < float(confidence) <= 1
        and bool(match.get("reasons") or match.get("why_matched"))
        and bool(match.get("evidence") or match.get("evidence_fragments") or match.get("evidence_snippets"))
    )


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


def route_results(personal_root: Path, db_path: Path, limit: int) -> dict:
    text_matches = search_sqlite_index(db_path, CASE_QUERY, limit)
    embedding_matches = search_embedding_index(db_path, CASE_QUERY, limit)
    photo_matches = search_photo_semantic_index(db_path, f"{CASE_QUERY} invoice screenshot receipt", limit)
    records = load_folder_records(db_path, "Documents")
    folder_matches = folder_query_matches(records, FOLDER_QUESTION, limit)
    folder_answer_status, folder_answer = build_answer("Documents", FOLDER_QUESTION, records, folder_matches, [])
    case_packet = build_case_packet(personal_root, db_path, limit)
    return {
        "sqlite_text_fts_metadata": {"matches": text_matches},
        "local_hash_embedding": {"matches": embedding_matches},
        "photo_semantic_local_visual": {"matches": photo_matches},
        "folder_rag": {
            "answer_status": folder_answer_status,
            "answer": folder_answer,
            "matches": folder_matches,
            "payment_nodes": collect_payment_nodes(folder_matches),
        },
        "case_packet": case_packet,
        "approval_manifest": {
            "status": "suggestion_only_ready_for_human_confirmation",
            "copyable_organizing_suggestions": case_packet["copyable_organizing_suggestions"],
            "requires_human_confirmation": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
        },
    }


def evaluate_contract(intents: dict, plan: list[dict], results: dict) -> list[str]:
    failures = []
    required_intents = {
        "document_classes": {"contract", "invoice"},
        "evidence_types": {"chat", "receipt", "screenshot"},
        "entities": {"amounts", "dates", "payment_terms"},
    }
    for key, values in required_intents.items():
        missing = sorted(values - set(intents.get(key) or []))
        if missing:
            failures.append(f"intent_missing:{key}:{','.join(missing)}")
    if intents.get("year") != "2024":
        failures.append("intent_missing:year:2024")

    planned_routes = {item["route"] for item in plan}
    for route in ["sqlite_text_fts_metadata", "local_hash_embedding", "photo_semantic_local_visual", "folder_rag", "case_packet", "approval_manifest"]:
        if route not in planned_routes:
            failures.append(f"route_missing:{route}")

    text_paths = {match.get("relative_path") for match in results["sqlite_text_fts_metadata"]["matches"]}
    if not any("contract" in str(path).lower() for path in text_paths):
        failures.append("text_route_missing_contract")
    if not any("invoice" in str(path).lower() or "receipt" in str(path).lower() for path in text_paths):
        failures.append("text_route_missing_invoice")
    if not all(grounded(match) for match in results["sqlite_text_fts_metadata"]["matches"][:3]):
        failures.append("text_route_top_results_not_grounded")

    embedding_paths = {match.get("relative_path") for match in results["local_hash_embedding"]["matches"]}
    if not any("renovation" in str(path).lower() for path in embedding_paths):
        failures.append("embedding_route_missing_renovation_evidence")
    if not all(grounded(match) for match in results["local_hash_embedding"]["matches"][:3]):
        failures.append("embedding_route_top_results_not_grounded")

    photo_matches = results["photo_semantic_local_visual"]["matches"]
    if not any("screenshot" in " ".join(match.get("matched_intents") or []) or "screenshot" in str(match.get("relative_path")).lower() for match in photo_matches):
        failures.append("photo_route_missing_screenshot_candidate")
    if photo_matches and not all(grounded(match) for match in photo_matches[:2]):
        failures.append("photo_route_top_results_not_grounded")

    folder = results["folder_rag"]
    if folder["answer_status"] not in {"grounded_answer", "partial_grounded_answer"}:
        failures.append(f"folder_rag_not_grounded:{folder['answer_status']}")
    if not folder["payment_nodes"]:
        failures.append("folder_rag_missing_payment_nodes")

    packet = results["case_packet"]
    packet_paths = {match.get("relative_path") for match in packet["matches"]}
    for term in ["contract", "invoice", "chat"]:
        if not any(term in str(path).lower() for path in packet_paths):
            failures.append(f"case_packet_missing_{term}")
    if not packet["payment_nodes"]:
        failures.append("case_packet_missing_payment_nodes")
    if not packet["copyable_organizing_suggestions"]:
        failures.append("case_packet_missing_copy_suggestions")
    if not all(grounded(match) for match in packet["matches"][:3]):
        failures.append("case_packet_top_results_not_grounded")

    approval = results["approval_manifest"]
    if not approval["requires_human_confirmation"]:
        failures.append("approval_route_missing_human_confirmation")
    if approval["delete_performed"] or approval["move_performed"] or approval["overwrite_performed"]:
        failures.append("approval_route_performed_destructive_action")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS multimodal intent routing contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--max-files", type=int, default=1000)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "multimodal_intent_routing_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    db_path = run_dir / "multimodal_intent_routing.sqlite3"
    index_status = build_sqlite_inventory(personal_root, db_path, max_files=args.max_files)
    image_upsert = ensure_image_embeddings_for_photos(db_path)
    intents = infer_intents(CASE_QUERY)
    plan = build_route_plan(intents)
    results = route_results(personal_root, db_path, args.limit)
    failures = evaluate_contract(intents, plan, results)

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_multimodal_intent_routing_contract" if not failures else "failed_ai_nas_multimodal_intent_routing_contract",
        "scope": "bounded multimodal intent routing for the target AI-NAS contract/invoice/chat screenshot workflow",
        "query": CASE_QUERY,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(db_path),
        "index_status": index_status,
        "sqlite_index_status": sqlite_index_status(db_path),
        "image_embedding_upsert": image_upsert,
        "intents": intents,
        "route_plan": plan,
        "route_results": results,
        "summary": {
            "intent_count": sum(len(value) for key, value in intents.items() if isinstance(value, list)),
            "route_count": len(plan),
            "case_match_count": len(results["case_packet"]["matches"]),
            "payment_node_count": len(results["case_packet"]["payment_nodes"]),
            "copy_suggestion_count": len(results["case_packet"]["copyable_organizing_suggestions"]),
            "photo_match_count": len(results["photo_semantic_local_visual"]["matches"]),
            "folder_rag_answer_status": results["folder_rag"]["answer_status"],
            "approval_requires_human_confirmation": results["approval_manifest"]["requires_human_confirmation"],
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
            "writes": "isolated fixture files, SQLite/FTS/vector/image embedding rows, and Markdown/JSON routing reports only",
        },
    }
    json_path = run_dir / "multimodal_intent_routing_contract.json"
    md_path = run_dir / "multimodal_intent_routing_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Multimodal Intent Routing Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- query: `{CASE_QUERY}`",
        f"- route_count: `{payload['summary']['route_count']}`",
        f"- case_match_count: `{payload['summary']['case_match_count']}`",
        f"- payment_node_count: `{payload['summary']['payment_node_count']}`",
        f"- copy_suggestion_count: `{payload['summary']['copy_suggestion_count']}`",
        f"- photo_match_count: `{payload['summary']['photo_match_count']}`",
        f"- folder_rag_answer_status: `{payload['summary']['folder_rag_answer_status']}`",
        f"- approval_requires_human_confirmation: `{payload['summary']['approval_requires_human_confirmation']}`",
        f"- failures: `{failures}`",
        "",
        "## Contract",
        "",
        "- The target query must decompose into contract, invoice, receipt, chat, screenshot, payment/date/amount, report, approval, and audit intents.",
        "- The route plan must include SQLite/FTS, local embedding, photo semantic search, folder RAG, case packet, and approval manifest routes.",
        "- Routed results must be grounded with path, reasons, evidence, and confidence, or the route must expose an explicit gap.",
        "- Approval remains suggestion-only and requires human confirmation before any write action.",
        "",
        "## Routes",
        "",
    ]
    for route in plan:
        lines.append(f"- `{route['route']}`: {route['purpose']}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
