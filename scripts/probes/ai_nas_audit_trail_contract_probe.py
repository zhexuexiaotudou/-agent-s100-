#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from ai_nas_action_approval_manifest_probe import (
    blocked_destructive_actions,
    build_approval_actions,
    hash_payload,
)
from ai_nas_action_execute_copy_probe import execute_action
from ai_nas_action_rollback_copy_probe import rollback_action
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
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    search_photo_semantic_index,
    search_sqlite_index,
    sha256_file,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_audit_trail_contract"
QUERY = "2024 renovation payment contract invoice receipt chat screenshot"


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
        "Renovation contract 2024. Deposit 20000 CNY on 2024-03-01. Final payment 8000 CNY on 2024-05-20.\n",
        encoding="utf-8",
    )
    (docs / "2024_renovation_invoice_receipt.txt").write_text(
        "Invoice receipt for renovation reimbursement. Amount 12000 CNY. Date 2024-04-15.\n",
        encoding="utf-8",
    )
    write_fixture_image(
        photos / "2024_renovation_chat_invoice_screenshot.jpg",
        (245, 245, 238),
        "chat screenshot invoice paid 5000 CNY 2024-04-20",
    )
    return personal


def canonical_hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def append_event(events: list[dict], trace_id: str, event_type: str, tool_id: str, outcome: str, detail: dict) -> dict:
    previous_hash = events[-1]["event_hash"] if events else None
    event = {
        "event_index": len(events) + 1,
        "generated_at": iso_now(),
        "trace_id": trace_id,
        "event_type": event_type,
        "tool_id": tool_id,
        "actor": "ai_nas_audit_trail_contract_probe",
        "outcome": outcome,
        "previous_event_hash": previous_hash,
        "detail": detail,
    }
    event["event_hash"] = canonical_hash(event)
    events.append(event)
    return event


def build_case_packet(personal_root: Path, sqlite_index_path: Path, limit: int) -> dict:
    image_upsert = ensure_image_embeddings_for_photos(sqlite_index_path)
    merged: dict[str, dict] = {}
    for match in search_sqlite_index(sqlite_index_path, QUERY, limit):
        merge_match(merged, match, "sqlite_text_fts_metadata")
    for match in search_embedding_index(sqlite_index_path, QUERY, limit):
        merge_match(merged, match, "local_hash_embedding")
    for match in search_photo_semantic_index(sqlite_index_path, f"{QUERY} invoice screenshot receipt", limit):
        merge_match(merged, match, "photo_semantic_local_visual")
    candidates = sorted(
        merged.values(),
        key=lambda item: (item["confidence"], item["score"], item["relative_path"]),
        reverse=True,
    )
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
            "grounding_policy": "all claims come from indexed metadata/text/photo evidence; gaps are explicit",
        },
    }


def build_manifest(case_packet: dict, personal_root: Path) -> dict:
    actions = build_approval_actions(case_packet["matches"], case_packet["copyable_organizing_suggestions"], personal_root)
    seed = {
        "query": QUERY,
        "collection_name": DEFAULT_COLLECTION,
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
    manifest_id = "apm-" + hash_payload(seed)[:16]
    payload = {
        "generated_at": iso_now(),
        "tool_id": "ai_nas_action_approval_manifest",
        "manifest_id": manifest_id,
        "status": "awaiting_human_confirmation",
        "query": QUERY,
        "collection_name": DEFAULT_COLLECTION,
        "personal_root": str(personal_root),
        "proposed_actions": actions,
        "blocked_destructive_actions": blocked_destructive_actions(case_packet["matches"]),
        "approval": {
            "required": True,
            "approval_phrase": f"APPROVE {manifest_id}",
            "execution_allowed_by_this_tool": False,
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


def write_ledger(db_path: Path, jsonl_path: Path, events: list[dict]) -> dict:
    jsonl_path.write_text("\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events) + "\n", encoding="utf-8")
    con = open_sqlite_connection(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_index INTEGER PRIMARY KEY,
                trace_id TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                previous_event_hash TEXT,
                event_hash TEXT NOT NULL,
                detail_json TEXT NOT NULL
            )
            """
        )
        con.execute("DELETE FROM audit_events")
        for event in events:
            con.execute(
                """
                INSERT INTO audit_events(
                    event_index, trace_id, generated_at, event_type, tool_id, outcome,
                    previous_event_hash, event_hash, detail_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_index"],
                    event["trace_id"],
                    event["generated_at"],
                    event["event_type"],
                    event["tool_id"],
                    event["outcome"],
                    event["previous_event_hash"],
                    event["event_hash"],
                    json.dumps(event["detail"], ensure_ascii=False, sort_keys=True),
                ),
            )
        con.commit()
        counts = {
            row[0]: row[1]
            for row in con.execute("SELECT event_type, COUNT(*) FROM audit_events GROUP BY event_type")
        }
        total = con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        return {"sqlite_event_count": total, "event_type_counts": counts}
    finally:
        con.close()


def verify_ledger(events: list[dict], personal_root: Path, source_hashes_before: dict[str, str]) -> list[str]:
    failures = []
    required_event_types = {
        "query_received",
        "index_refreshed",
        "case_packet_built",
        "approval_manifest_created",
        "destructive_actions_blocked",
        "copy_executed",
        "rollback_manifest_created",
        "rollback_executed",
        "final_report_written",
    }
    seen_types = {event["event_type"] for event in events}
    for event_type in sorted(required_event_types - seen_types):
        failures.append(f"missing_event_type:{event_type}")
    previous_hash = None
    for event in events:
        if event.get("previous_event_hash") != previous_hash:
            failures.append(f"hash_chain_previous_mismatch:{event.get('event_index')}")
        event_hash = event.get("event_hash")
        expected = canonical_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event_hash != expected:
            failures.append(f"event_hash_mismatch:{event.get('event_index')}")
        previous_hash = event_hash
        for field in ["event_index", "generated_at", "trace_id", "event_type", "tool_id", "actor", "outcome", "detail"]:
            if field not in event:
                failures.append(f"event_missing_field:{event.get('event_index')}:{field}")
    for rel, before_hash in source_hashes_before.items():
        path = personal_root / rel
        if not path.exists():
            failures.append(f"source_missing_after_audit_flow:{rel}")
            continue
        after_hash = sha256_file(path)
        if before_hash != after_hash:
            failures.append(f"source_hash_changed:{rel}")
    copied_targets = list((personal_root / "Collections").rglob("*")) if (personal_root / "Collections").exists() else []
    remaining_files = [path for path in copied_targets if path.is_file()]
    if remaining_files:
        failures.append("rollback_left_copied_targets:" + ",".join(path.relative_to(personal_root).as_posix() for path in remaining_files))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS cross-step audit trail contract with hash-chained JSONL/SQLite ledger.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "audit_trail_contract")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root = prepare_fixture(fixture_root)
    sqlite_index_path = run_dir / "audit_trail_contract.sqlite3"
    ledger_db_path = run_dir / "audit_trail_ledger.sqlite3"
    ledger_jsonl_path = run_dir / "audit_trail_ledger.jsonl"
    trace_seed = f"{QUERY}|{personal_root}|{iso_now()}"
    trace_id = "trace-" + hashlib.sha256(trace_seed.encode("utf-8")).hexdigest()[:16]
    events: list[dict] = []

    append_event(events, trace_id, "query_received", "openclaw_chat_entry", "accepted", {"query": QUERY})
    index_status = build_sqlite_inventory(personal_root, sqlite_index_path)
    append_event(
        events,
        trace_id,
        "index_refreshed",
        "ai_nas_personal_inventory",
        "completed",
        {"sqlite_index_path": str(sqlite_index_path), "status": index_status.get("status"), "file_count": index_status.get("file_count")},
    )
    case_packet = build_case_packet(personal_root, sqlite_index_path, args.limit)
    case_packet_path = run_dir / "case_packet_for_audit.json"
    safe_write_json(case_packet_path, case_packet)
    append_event(
        events,
        trace_id,
        "case_packet_built",
        "ai_nas_case_packet",
        "completed",
        {
            "report_path": str(case_packet_path),
            "match_count": len(case_packet["matches"]),
            "payment_node_count": len(case_packet["payment_nodes"]),
            "copy_suggestion_count": len(case_packet["copyable_organizing_suggestions"]),
        },
    )
    manifest = build_manifest(case_packet, personal_root)
    manifest_path = run_dir / "action_approval_manifest_for_audit.json"
    safe_write_json(manifest_path, manifest)
    append_event(
        events,
        trace_id,
        "approval_manifest_created",
        "ai_nas_action_approval_manifest",
        "awaiting_human_confirmation",
        {
            "manifest_path": str(manifest_path),
            "manifest_id": manifest["manifest_id"],
            "manifest_sha256": manifest["manifest_sha256"],
            "approval_phrase": manifest["approval"]["approval_phrase"],
            "proposed_action_count": len(manifest["proposed_actions"]),
        },
    )
    append_event(
        events,
        trace_id,
        "destructive_actions_blocked",
        "ai_nas_action_approval_manifest",
        "blocked",
        {
            "blocked_action_types": [item["action_type"] for item in manifest["blocked_destructive_actions"]],
            "required_gate": "suggestion -> human confirmation -> bounded execution -> rollback/manifest",
        },
    )

    executed = []
    failed = []
    source_hashes_before = {
        action["source_relative_path"]: action["source_sha256"]
        for action in manifest["proposed_actions"]
        if action.get("source_sha256")
    }
    for action in manifest["proposed_actions"]:
        try:
            executed.append(execute_action(action, personal_root))
        except Exception as exc:
            failed.append({"action_id": action.get("action_id"), "error": f"{type(exc).__name__}:{exc}"})
    append_event(
        events,
        trace_id,
        "copy_executed",
        "ai_nas_action_execute_copy",
        "completed" if executed and not failed else "completed_with_failures",
        {
            "manifest_id": manifest["manifest_id"],
            "executed_count": len(executed),
            "failed_count": len(failed),
            "executed_actions": executed,
            "failed_actions": failed,
        },
    )
    rollback_manifest = {
        "generated_at": iso_now(),
        "source_execution_tool": "ai_nas_action_execute_copy",
        "manifest_id": manifest["manifest_id"],
        "rollback_allowed": True,
        "rollback_policy": "remove only copied targets listed here after verifying target_sha256; never touch source files",
        "rollback_actions": [
            {
                "action_id": item["action_id"],
                "target_relative_path": item["target_relative_path"],
                "target_absolute_path": item["target_absolute_path"],
                "expected_target_sha256": item["target_sha256"],
                "source_relative_path": item["source_relative_path"],
                "source_absolute_path": item["source_absolute_path"],
                "source_sha256": item["source_sha256"],
            }
            for item in executed
        ],
    }
    rollback_manifest_path = run_dir / "rollback_manifest_for_audit.json"
    safe_write_json(rollback_manifest_path, rollback_manifest)
    append_event(
        events,
        trace_id,
        "rollback_manifest_created",
        "ai_nas_action_execute_copy",
        "completed",
        {
            "rollback_manifest_path": str(rollback_manifest_path),
            "manifest_id": manifest["manifest_id"],
            "rollback_action_count": len(rollback_manifest["rollback_actions"]),
        },
    )
    rolled_back = []
    rollback_failed = []
    for action in rollback_manifest["rollback_actions"]:
        try:
            rolled_back.append(rollback_action(action))
        except Exception as exc:
            rollback_failed.append({"action_id": action.get("action_id"), "error": f"{type(exc).__name__}:{exc}"})
    append_event(
        events,
        trace_id,
        "rollback_executed",
        "ai_nas_action_rollback_copy",
        "completed" if rolled_back and not rollback_failed else "completed_with_failures",
        {
            "manifest_id": manifest["manifest_id"],
            "removed_count": len([item for item in rolled_back if item.get("status") == "removed_copied_target"]),
            "failed_count": len(rollback_failed),
            "rolled_back_actions": rolled_back,
            "failed_actions": rollback_failed,
        },
    )

    report_path = run_dir / "audit_trail_contract_report.json"
    append_event(
        events,
        trace_id,
        "final_report_written",
        TOOL_ID,
        "completed",
        {"report_path": str(report_path), "ledger_jsonl_path": str(ledger_jsonl_path), "ledger_db_path": str(ledger_db_path)},
    )
    ledger_status = write_ledger(ledger_db_path, ledger_jsonl_path, events)
    failures = verify_ledger(events, personal_root, source_hashes_before)
    if ledger_status["sqlite_event_count"] != len(events):
        failures.append("sqlite_event_count_mismatch")
    if not ledger_jsonl_path.exists() or ledger_jsonl_path.stat().st_size <= 0:
        failures.append("ledger_jsonl_missing_or_empty")
    if failed:
        failures.append(f"copy_failures:{len(failed)}")
    if rollback_failed:
        failures.append(f"rollback_failures:{len(rollback_failed)}")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_audit_trail_contract" if not failures else "failed_ai_nas_audit_trail_contract",
        "scope": "bounded cross-step audit trail for query -> report -> approval -> copy execution -> rollback",
        "trace_id": trace_id,
        "personal_root": str(personal_root),
        "sqlite_index_path": str(sqlite_index_path),
        "ledger": {
            "jsonl_path": str(ledger_jsonl_path),
            "sqlite_path": str(ledger_db_path),
            "event_count": len(events),
            "final_event_hash": events[-1]["event_hash"] if events else None,
            **ledger_status,
        },
        "summary": {
            "event_count": len(events),
            "required_event_types_present": not any(failure.startswith("missing_event_type:") for failure in failures),
            "hash_chain_valid": not any("hash" in failure for failure in failures),
            "copy_executed_count": len(executed),
            "rollback_removed_count": len([item for item in rolled_back if item.get("status") == "removed_copied_target"]),
            "source_preserved": not any(failure.startswith("source_") for failure in failures),
            "rollback_left_no_copied_targets": not any(failure.startswith("rollback_left_copied_targets") for failure in failures),
            "failures": failures,
        },
        "events": events,
        "final_index_status": sqlite_index_status(sqlite_index_path),
        "audit": {
            "real_personal_source_modified": False,
            "fixture_only": True,
            "copy_performed": bool(executed),
            "rollback_performed": bool(rolled_back),
            "source_delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "isolated fixture files, hash-chained JSONL/SQLite audit ledger, and Markdown/JSON audit contract reports",
        },
        "production_gap": "This proves audit continuity on a bounded fixture. Production still needs durable ledger retention and principal identity mapping on a mounted NAS/OpenClaw deployment.",
    }
    safe_write_json(report_path, payload)
    md_path = run_dir / "audit_trail_contract.md"
    lines = [
        "# AI-NAS Audit Trail Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- trace_id: `{trace_id}`",
        f"- event_count: `{len(events)}`",
        f"- final_event_hash: `{payload['ledger']['final_event_hash']}`",
        f"- hash_chain_valid: `{payload['summary']['hash_chain_valid']}`",
        f"- source_preserved: `{payload['summary']['source_preserved']}`",
        f"- rollback_left_no_copied_targets: `{payload['summary']['rollback_left_no_copied_targets']}`",
        f"- ledger_jsonl_path: `{ledger_jsonl_path}`",
        f"- ledger_sqlite_path: `{ledger_db_path}`",
        f"- failures: `{failures}`",
        "- policy: fixture-only copy and rollback; no real Personal mutation, source delete, move, overwrite, network call, or service start",
        "",
        "## Events",
        "",
    ]
    for event in events:
        lines.append(
            f"- `{event['event_index']}` `{event['event_type']}` via `{event['tool_id']}` outcome `{event['outcome']}` hash `{event['event_hash'][:12]}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(report_path)
    print(ledger_jsonl_path)
    print(ledger_db_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
