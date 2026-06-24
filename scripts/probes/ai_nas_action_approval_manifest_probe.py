#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ai_nas_case_packet_probe import (
    DEFAULT_COLLECTION,
    DEFAULT_QUERY,
    build_case_answer,
    build_copy_suggestions,
    collect_payment_nodes,
    filter_case_matches,
    infer_gaps,
    merge_match,
    summarize,
)
from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    search_photo_semantic_index,
    search_sqlite_index,
    sha256_file,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_action_approval_manifest"


def stable_action_id(action_type: str, source_relative_path: str, target_relative_path: str) -> str:
    raw = f"{action_type}\0{source_relative_path}\0{target_relative_path}".encode("utf-8")
    return f"{action_type}-{hashlib.sha256(raw).hexdigest()[:16]}"


def hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def collect_case_matches(args: argparse.Namespace) -> tuple[list[dict], list[dict], dict]:
    if not args.no_refresh_index:
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)
    elif not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    image_upsert = ensure_image_embeddings_for_photos(args.sqlite_index_path)
    merged: dict[str, dict] = {}
    for match in search_sqlite_index(args.sqlite_index_path, args.query, args.limit):
        merge_match(merged, match, "sqlite_text_fts_metadata")
    for match in search_embedding_index(args.sqlite_index_path, args.query, args.limit):
        merge_match(merged, match, "local_hash_embedding")
    photo_query = f"{args.query} invoice screenshot receipt"
    for match in search_photo_semantic_index(args.sqlite_index_path, photo_query, args.limit):
        merge_match(merged, match, "photo_semantic_local_visual")

    candidates = sorted(
        merged.values(),
        key=lambda item: (item["confidence"], item["score"], item["relative_path"]),
        reverse=True,
    )
    matches, rejected = filter_case_matches(args.query, candidates)
    return matches[: args.limit], rejected, {"image_embedding_upsert": image_upsert}


def build_approval_actions(matches: list[dict], suggestions: list[dict], personal_root: Path) -> list[dict]:
    by_relative_path = {match["relative_path"]: match for match in matches}
    actions = []
    for suggestion in suggestions:
        source_relative = suggestion["source_relative_path"]
        target_relative = suggestion["suggested_target_relative_path"]
        match = by_relative_path.get(source_relative) or {}
        source_path = Path(match.get("path") or personal_root / source_relative)
        target_path = personal_root / target_relative
        source_exists = source_path.exists()
        source_digest = sha256_file(source_path) if source_exists and source_path.is_file() else None
        target_exists = target_path.exists()
        action_id = stable_action_id("copy", source_relative, target_relative)
        actions.append(
            {
                "action_id": action_id,
                "action_type": "copy",
                "status": "proposed_requires_human_confirmation",
                "source_relative_path": source_relative,
                "source_absolute_path": str(source_path),
                "source_sha256": source_digest,
                "target_relative_path": target_relative,
                "target_absolute_path": str(target_path),
                "target_exists_now": target_exists,
                "confidence": match.get("confidence"),
                "evidence_sources": match.get("sources", []),
                "reason": "copy matched evidence into a case collection without modifying the original file",
                "permission_level_required": "bounded-personal-copy",
                "requires_human_confirmation": True,
                "destructive": False,
                "write_effect": "create one copied file only if the exact target path does not already exist",
                "preconditions": [
                    "operator explicitly approves this manifest and action_id",
                    "source path exists and source_sha256 still matches",
                    "target path is under Personal/Collections",
                    "target path does not already exist",
                    "no source delete, move, rename, or overwrite is allowed",
                ],
                "rollback_plan": [
                    "remove only the copied target created by the future execution manifest",
                    "rollback must verify target sha256 equals the approved source_sha256 before removal",
                    "rollback must append its own audit event and never touch the source file",
                ],
            }
        )
    return actions


def blocked_destructive_actions(matches: list[dict]) -> list[dict]:
    return [
        {
            "action_type": action_type,
            "status": "blocked_not_generated",
            "reason": "destructive actions require a separate operator-approved execution tool, backup/retention policy, exact source hash checks, and rollback manifest",
            "candidate_file_count": len(matches),
            "required_gate": "suggestion -> human confirmation -> bounded execution -> rollback/manifest",
        }
        for action_type in ["move", "delete", "overwrite", "rename"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a dry-run AI-NAS action approval manifest.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION)
    parser.add_argument("--no-refresh-index", action="store_true")
    args = parser.parse_args()

    matches, rejected_matches, runtime = collect_case_matches(args)
    payment_nodes = collect_payment_nodes(matches)
    gaps = infer_gaps(args.query, matches)
    suggestions = build_copy_suggestions(matches, args.collection_name)
    actions = build_approval_actions(matches, suggestions, args.personal_root)
    generated_at = iso_now()
    manifest_seed = {
        "query": args.query,
        "collection_name": args.collection_name,
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
        "generated_at": generated_at,
        "tool_id": TOOL_ID,
        "manifest_id": manifest_id,
        "status": "awaiting_human_confirmation",
        "query": args.query,
        "collection_name": args.collection_name,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": sqlite_index_status(args.sqlite_index_path),
        "runtime": runtime,
        "answer": build_case_answer(matches, payment_nodes, gaps),
        "summary": summarize(matches),
        "matches": matches,
        "rejected_matches": rejected_matches,
        "payment_nodes": payment_nodes,
        "gaps": gaps,
        "proposed_actions": actions,
        "blocked_destructive_actions": blocked_destructive_actions(matches),
        "approval": {
            "required": True,
            "approval_phrase": f"APPROVE {manifest_id}",
            "approval_scope": "copy-only actions listed in proposed_actions by exact action_id",
            "execution_allowed_by_this_tool": False,
            "future_execution_requirements": [
                "accept only this manifest_id and explicit action_ids",
                "re-check source_sha256 and target non-existence immediately before copying",
                "write execution_manifest.json with created files and per-action result",
                "provide rollback_manifest.json for copied targets",
            ],
        },
        "audit": {
            "tool_id": TOOL_ID,
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "execution_performed": False,
            "writes": "Markdown/JSON approval manifest only; may refresh SQLite index and image embedding rows",
            "grounding_policy": "actions are derived only from matched evidence and copyable organizing suggestions",
        },
    }
    payload["manifest_sha256"] = hash_payload(payload)

    run_dir = ensure_report_dir(args.report_root, "action_approval_manifest")
    json_path = run_dir / "action_approval_manifest.json"
    md_path = run_dir / "action_approval_manifest.md"
    safe_write_json(json_path, payload)

    lines = [
        "# AI-NAS Action Approval Manifest",
        "",
        f"- manifest_id: `{manifest_id}`",
        f"- manifest_sha256: `{payload['manifest_sha256']}`",
        f"- status: `{payload['status']}`",
        f"- query: `{args.query}`",
        f"- generated_at: `{generated_at}`",
        f"- proposed_action_count: `{len(actions)}`",
        "- policy: dry-run approval manifest only; no source delete, no move, no overwrite, no execution",
        f"- approval_phrase: `{payload['approval']['approval_phrase']}`",
        "",
        "## Answer",
        "",
        payload["answer"],
        "",
        "## Proposed Actions",
        "",
    ]
    if not actions:
        lines.append("- No copy actions proposed because no grounded evidence matched.")
    for action in actions:
        lines.append(
            f"- `{action['action_id']}` copy `{action['source_relative_path']}` -> `{action['target_relative_path']}`"
        )
        lines.append(f"  - source_sha256: `{action['source_sha256']}`")
        lines.append(f"  - confidence: `{action['confidence']}`")
        lines.append(f"  - target_exists_now: `{action['target_exists_now']}`")
        lines.append(f"  - requires_human_confirmation: `{action['requires_human_confirmation']}`")
        lines.append("  - rollback: verify copied target hash, remove copied target only, append rollback audit")

    lines.extend(["", "## Blocked Destructive Actions", ""])
    for action in payload["blocked_destructive_actions"]:
        lines.append(f"- `{action['action_type']}`: {action['reason']}")

    lines.extend(["", "## Evidence Gaps", ""])
    if not gaps:
        lines.append("- No explicit evidence gap detected for this bounded query.")
    for gap in gaps:
        lines.append(f"- {gap}")

    lines.extend(["", "## Approval Contract", ""])
    for key, value in payload["approval"].items():
        if isinstance(value, list):
            lines.append(f"- {key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
