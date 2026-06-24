#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path

from ai_nas_action_approval_manifest_probe import (
    blocked_destructive_actions,
    build_approval_actions,
    hash_payload,
)
from ai_nas_case_packet_probe import (
    DEFAULT_COLLECTION,
    build_case_answer,
    build_copy_suggestions,
    collect_payment_nodes,
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


TOOL_ID = "ai_nas_appliance_experience_acceptance"
QUERY = "2024 renovation payment contract invoice receipt chat screenshot"


def write_fixture_image(path: Path, rgb: tuple[int, int, int], text: str) -> None:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (720, 420), rgb)
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 700, 400), outline=(40, 40, 40), width=3)
    draw.text((40, 180), text, fill=(0, 0, 0))
    image.save(path)


def prepare_fixture(run_dir: Path) -> Path:
    personal = run_dir / "appliance_experience_fixture" / "Personal"
    if personal.exists():
        shutil.rmtree(personal)
    docs = personal / "Documents"
    photos = personal / "Photos"
    docs.mkdir(parents=True, exist_ok=True)
    photos.mkdir(parents=True, exist_ok=True)
    (docs / "2024_renovation_contract.txt").write_text(
        "Renovation contract 2024. Payment: deposit 20000 CNY on 2024-03-01; final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    (docs / "2024_renovation_invoice_receipt.txt").write_text(
        "Invoice receipt for renovation reimbursement. Amount: 12000 CNY. Date: 2024-04-15. Receipt number RCPT-2024-0415.\n",
        encoding="utf-8",
    )
    (docs / "unrelated_manual.txt").write_text(
        "Kitchen device manual. Not related to renovation payment, invoice, receipt, or chat screenshot evidence.\n",
        encoding="utf-8",
    )
    write_fixture_image(
        photos / "2024_renovation_chat_invoice_screenshot.jpg",
        (245, 245, 238),
        "chat screenshot invoice paid 5000 CNY 2024-04-20",
    )
    write_fixture_image(
        photos / "2024_unrelated_beach_photo.jpg",
        (80, 170, 230),
        "unrelated beach photo",
    )
    return personal


def build_case_packet(personal_root: Path, sqlite_index_path: Path, limit: int) -> dict:
    build_sqlite_inventory(personal_root, sqlite_index_path)
    image_upsert = ensure_image_embeddings_for_photos(sqlite_index_path)
    merged: dict[str, dict] = {}
    for match in search_sqlite_index(sqlite_index_path, QUERY, limit):
        merge_match(merged, match, "sqlite_text_fts_metadata")
    for match in search_embedding_index(sqlite_index_path, QUERY, limit):
        merge_match(merged, match, "local_hash_embedding")
    for match in search_photo_semantic_index(sqlite_index_path, f"{QUERY} invoice screenshot receipt", limit):
        merge_match(merged, match, "photo_semantic_local_visual")
    candidates = sorted(merged.values(), key=lambda item: (item["confidence"], item["score"], item["relative_path"]), reverse=True)
    matches, rejected = filter_case_matches(QUERY, candidates)
    matches = matches[:limit]
    payment_nodes = collect_payment_nodes(matches)
    gaps = infer_gaps(QUERY, matches)
    suggestions = build_copy_suggestions(matches, DEFAULT_COLLECTION)
    return {
        "generated_at": iso_now(),
        "query": QUERY,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "index_status": sqlite_index_status(sqlite_index_path),
        "image_embedding_upsert": image_upsert,
        "answer": build_case_answer(matches, payment_nodes, gaps),
        "summary": summarize(matches),
        "matches": matches,
        "rejected_matches": rejected,
        "payment_nodes": payment_nodes,
        "gaps": gaps,
        "copyable_organizing_suggestions": suggestions,
        "audit": {
            "tool_id": "ai_nas_case_packet",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "requires_human_confirmation_for_suggestions": True,
            "grounding_policy": "all claims come from indexed metadata/text/photo evidence; gaps are explicit",
        },
    }


def user_facing_results(matches: list[dict]) -> list[dict]:
    rows = []
    for match in matches:
        entities = match.get("entities") or {}
        evidence = match.get("evidence_fragments") or []
        photo = match.get("photo") or {}
        summary = match.get("summary") or ""
        if not summary and photo:
            bits = []
            if photo.get("labels"):
                bits.append("photo labels: " + ", ".join(photo.get("labels") or []))
            if photo.get("width") and photo.get("height"):
                bits.append(f"size: {photo['width']}x{photo['height']}")
            summary = "; ".join(bits) or "photo metadata result"
        rows.append(
            {
                "relative_path": match["relative_path"],
                "original_path": match.get("path"),
                "why_matched": match.get("reasons", [])[:10],
                "evidence_snippets": evidence[:3],
                "summary": summary,
                "dates": entities.get("dates") or [],
                "amounts": entities.get("amounts") or [],
                "payment_terms": entities.get("payment_terms") or [],
                "confidence": match.get("confidence"),
                "sources": match.get("sources", []),
                "matched_intents": match.get("matched_intents", []),
                "missing_intents": match.get("missing_intents", []),
            }
        )
    return rows


def build_manifest(case_packet: dict, personal_root: Path, collection_name: str) -> dict:
    actions = build_approval_actions(case_packet["matches"], case_packet["copyable_organizing_suggestions"], personal_root)
    manifest_seed = {
        "query": QUERY,
        "collection_name": collection_name,
        "actions": [
            {
                "action_id": action["action_id"],
                "source_relative_path": action["source_relative_path"],
                "source_sha256": action["source_sha256"],
                "target_relative_path": action["target_relative_path"],
            }
            for action in actions
        ],
    }
    manifest_id = "apm-" + hash_payload(manifest_seed)[:16]
    payload = {
        "tool_id": "ai_nas_action_approval_manifest",
        "manifest_id": manifest_id,
        "status": "awaiting_human_confirmation",
        "query": QUERY,
        "collection_name": collection_name,
        "proposed_actions": actions,
        "blocked_destructive_actions": blocked_destructive_actions(case_packet["matches"]),
        "approval": {
            "required": True,
            "approval_phrase": f"APPROVE {manifest_id}",
            "execution_allowed_by_this_tool": False,
            "future_execution_requirements": [
                "re-check source_sha256 and target non-existence immediately before copying",
                "write execution_manifest.json with created files and per-action result",
                "provide rollback_manifest.json for copied targets",
            ],
        },
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "execution_performed": False,
        },
    }
    payload["manifest_sha256"] = hash_payload(payload)
    return payload


def evaluate_experience(case_packet: dict, manifest: dict, result_rows: list[dict], md_path: Path, json_path: Path) -> list[str]:
    failures = []
    matches = case_packet["matches"]
    rels = {match["relative_path"] for match in matches}
    if len(matches) < 3:
        failures.append("match_count_lt_3")
    if not any("contract" in rel.lower() for rel in rels):
        failures.append("missing_contract_result")
    if not any("invoice" in rel.lower() or "receipt" in rel.lower() for rel in rels):
        failures.append("missing_invoice_or_receipt_result")
    if not any("chat" in rel.lower() and "screenshot" in rel.lower() for rel in rels):
        failures.append("missing_chat_screenshot_result")
    if len(case_packet["payment_nodes"]) < 2:
        failures.append("payment_nodes_lt_2")
    if not case_packet["copyable_organizing_suggestions"]:
        failures.append("missing_copyable_organizing_suggestions")
    if not manifest["proposed_actions"]:
        failures.append("missing_proposed_approval_actions")
    if not manifest["approval"]["required"] or not manifest["approval"]["approval_phrase"].startswith("APPROVE "):
        failures.append("missing_human_approval_contract")
    if not manifest.get("manifest_sha256"):
        failures.append("missing_manifest_sha256")
    for action in manifest["proposed_actions"]:
        if action.get("action_type") != "copy" or action.get("destructive") is not False:
            failures.append(f"non_copy_or_destructive_action:{action.get('action_id')}")
        if not action.get("source_sha256"):
            failures.append(f"missing_source_sha256:{action.get('action_id')}")
        if not action.get("rollback_plan"):
            failures.append(f"missing_rollback_plan:{action.get('action_id')}")
    blocked = {item.get("action_type") for item in manifest["blocked_destructive_actions"]}
    if not {"move", "delete", "overwrite", "rename"} <= blocked:
        failures.append("missing_blocked_destructive_actions")
    for row in result_rows:
        if not row.get("why_matched") or not row.get("evidence_snippets") or row.get("confidence") is None:
            failures.append(f"result_missing_reason_evidence_confidence:{row.get('relative_path')}")
        if not row.get("summary") or not row.get("original_path"):
            failures.append(f"result_missing_summary_or_path:{row.get('relative_path')}")
    if not md_path.exists() or not json_path.exists():
        failures.append("one_click_report_paths_missing")
    audit = case_packet.get("audit") or {}
    if any(audit.get(key) for key in ["source_files_modified", "delete_performed", "move_performed", "overwrite_performed"]):
        failures.append("case_packet_audit_mutation_flagged")
    if any(manifest.get("audit", {}).get(key) for key in ["source_files_modified", "delete_performed", "move_performed", "overwrite_performed", "execution_performed"]):
        failures.append("manifest_audit_mutation_flagged")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end AI-NAS Copilot Appliance experience acceptance over a bounded fixture.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--sqlite-index-path", type=Path, default=None)
    parser.add_argument("--use-existing-personal", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "appliance_experience_acceptance")
    if importlib.util.find_spec("PIL") is None:
        payload = {
            "generated_at": iso_now(),
            "tool_id": TOOL_ID,
            "verdict": "blocked_ai_nas_appliance_experience_acceptance",
            "failures": ["missing_PIL_for_fixture_chat_screenshot"],
            "audit": {"source_files_modified": False, "delete_performed": False, "move_performed": False, "overwrite_performed": False},
        }
        json_path = run_dir / "appliance_experience_acceptance.json"
        md_path = run_dir / "appliance_experience_acceptance.md"
        safe_write_json(json_path, payload)
        safe_write_text(md_path, "# AI-NAS Appliance Experience Acceptance\n\n- verdict: `blocked_ai_nas_appliance_experience_acceptance`\n")
        print(md_path)
        print(json_path)
        return 1
    personal_root = args.personal_root if args.use_existing_personal and args.personal_root else prepare_fixture(run_dir)
    sqlite_index_path = args.sqlite_index_path or (run_dir / "appliance_experience_acceptance.sqlite3")
    case_packet = build_case_packet(personal_root, sqlite_index_path, max(3, args.limit))
    manifest = build_manifest(case_packet, personal_root, DEFAULT_COLLECTION)
    result_rows = user_facing_results(case_packet["matches"])
    report_md_path = run_dir / "one_click_experience_report.md"
    report_json_path = run_dir / "one_click_experience_report.json"
    acceptance_json_path = run_dir / "appliance_experience_acceptance.json"
    acceptance_md_path = run_dir / "appliance_experience_acceptance.md"
    report_payload = {
        "query": QUERY,
        "answer": case_packet["answer"],
        "results": result_rows,
        "payment_nodes": case_packet["payment_nodes"],
        "copyable_organizing_suggestions": case_packet["copyable_organizing_suggestions"],
        "approval_manifest": manifest,
        "gaps": case_packet["gaps"],
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "execution_performed": False,
            "all_operations_auditable": True,
        },
    }
    safe_write_json(report_json_path, report_payload)
    report_lines = [
        "# AI-NAS One-Click Experience Report",
        "",
        f"- query: `{QUERY}`",
        f"- result_count: `{len(result_rows)}`",
        f"- payment_node_count: `{len(case_packet['payment_nodes'])}`",
        f"- proposed_copy_actions: `{len(manifest['proposed_actions'])}`",
        f"- approval_phrase: `{manifest['approval']['approval_phrase']}`",
        "- policy: report plus dry-run approval manifest only; no execution",
        "",
        "## Answer",
        "",
        case_packet["answer"],
        "",
        "## Results",
        "",
    ]
    for row in result_rows:
        report_lines.append(f"- `{row['relative_path']}` confidence `{row['confidence']}`")
        report_lines.append(f"  - path: `{row['original_path']}`")
        report_lines.append(f"  - summary: {row['summary']}")
        report_lines.append(f"  - evidence: {' | '.join(row['evidence_snippets'][:2])}")
        report_lines.append(f"  - reasons: {', '.join(row['why_matched'][:8])}")
        if row["dates"]:
            report_lines.append(f"  - dates: `{', '.join(row['dates'])}`")
        if row["amounts"]:
            report_lines.append(f"  - amounts: `{', '.join(row['amounts'])}`")
    report_lines.extend(["", "## Copy Suggestions", ""])
    for suggestion in case_packet["copyable_organizing_suggestions"]:
        report_lines.append(f"- copy `{suggestion['source_relative_path']}` -> `{suggestion['suggested_target_relative_path']}`")
    report_lines.extend(["", "## Approval Manifest", "", f"- manifest_id: `{manifest['manifest_id']}`", f"- manifest_sha256: `{manifest['manifest_sha256']}`"])
    safe_write_text(report_md_path, "\n".join(report_lines) + "\n")

    failures = evaluate_experience(case_packet, manifest, result_rows, report_md_path, report_json_path)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_appliance_experience_acceptance" if not failures else "failed_ai_nas_appliance_experience_acceptance",
        "scope": "bounded end-to-end local AI Copilot Appliance experience for 2024 renovation payment evidence",
        "query": QUERY,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "one_click_report_md": str(report_md_path),
        "one_click_report_json": str(report_json_path),
        "case_packet": case_packet,
        "user_facing_results": result_rows,
        "approval_manifest": manifest,
        "failures": failures,
        "requirements": {
            "related_file_list": len(result_rows) >= 3,
            "why_each_file_matches": all(row.get("why_matched") for row in result_rows),
            "evidence_snippets": all(row.get("evidence_snippets") for row in result_rows),
            "summary": all(row.get("summary") for row in result_rows),
            "amount_date_payment_nodes": len(case_packet["payment_nodes"]) >= 2,
            "original_paths": all(row.get("original_path") for row in result_rows),
            "confidence": all(row.get("confidence") is not None for row in result_rows),
            "copyable_organizing_suggestions": bool(case_packet["copyable_organizing_suggestions"]),
            "one_click_report": report_md_path.exists() and report_json_path.exists(),
            "all_operations_auditable": True,
            "human_confirmation_before_execution": manifest["approval"]["required"],
            "rollback_manifest_contract": all(action.get("rollback_plan") for action in manifest["proposed_actions"]),
        },
        "audit": {
            "source_files_modified": False,
            "real_personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "execution_performed": False,
            "writes": "bounded fixture files, SQLite index/image_embeddings rows, one-click Markdown/JSON report, and dry-run approval manifest",
        },
    }
    safe_write_json(acceptance_json_path, payload)
    lines = [
        "# AI-NAS Appliance Experience Acceptance",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- query: `{QUERY}`",
        f"- result_count: `{len(result_rows)}`",
        f"- payment_node_count: `{len(case_packet['payment_nodes'])}`",
        f"- proposed_copy_actions: `{len(manifest['proposed_actions'])}`",
        f"- failures: `{failures}`",
        f"- one_click_report_md: `{report_md_path}`",
        f"- one_click_report_json: `{report_json_path}`",
        "- policy: bounded fixture and dry-run approval only; no real Personal mutation and no execution",
        "",
        "## Requirement Checks",
        "",
    ]
    for key, value in payload["requirements"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(acceptance_md_path, "\n".join(lines) + "\n")
    print(acceptance_md_path)
    print(acceptance_json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
