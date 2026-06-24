#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from ai_nas_case_packet_probe import DEFAULT_QUERY, filter_case_matches, merge_match
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
    sqlite_index_status,
)


TOOL_ID = "ai_nas_permission_aware_search"
DEFAULT_PRINCIPAL = "family_member"
VALID_PRINCIPALS = {"admin", "family_member", "accountant", "guest", "child"}
SENSITIVE_CLASSES = {"contract", "invoice"}
SENSITIVE_LABELS = {"invoice", "receipt", "screenshot"}


def stable_redaction_id(relative_path: str) -> str:
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]
    return f"redacted-{digest}"


def classify_sensitivity(match: dict) -> dict:
    relative_path = match.get("relative_path", "")
    doc_class = match.get("document_class")
    labels = set(((match.get("photo") or {}).get("labels") or []))
    lower_path = relative_path.lower()
    reasons = []
    sensitivity = "personal_standard"
    if doc_class in SENSITIVE_CLASSES:
        sensitivity = "financial_private"
        reasons.append(f"document_class:{doc_class}")
    if labels & SENSITIVE_LABELS:
        sensitivity = "financial_private"
        reasons.append("photo_label:" + ",".join(sorted(labels & SENSITIVE_LABELS)))
    if any(term in lower_path for term in ["contract", "invoice", "receipt", "payment", "reimbursement"]):
        sensitivity = "financial_private"
        reasons.append("path_keyword:financial")
    if "research" in lower_path or doc_class == "paper":
        sensitivity = "research_internal"
        reasons.append("path_or_class:research")
    if match.get("type") == "Photos" and sensitivity == "personal_standard":
        sensitivity = "personal_photo"
        reasons.append("type:photo")
    if not reasons:
        reasons.append("default:personal_standard")
    return {"sensitivity": sensitivity, "reasons": sorted(set(reasons))}


def principal_permissions(principal: str) -> dict:
    table = {
        "admin": {
            "allowed_sensitivities": {"financial_private", "research_internal", "personal_photo", "personal_standard"},
            "path_prefixes": ["Documents/", "Photos/", "Movies/", "Inbox/"],
        },
        "family_member": {
            "allowed_sensitivities": {"financial_private", "personal_photo", "personal_standard"},
            "path_prefixes": ["Documents/", "Photos/", "Movies/", "Inbox/"],
        },
        "accountant": {
            "allowed_sensitivities": {"financial_private"},
            "path_prefixes": ["Documents/", "Photos/", "Inbox/"],
        },
        "guest": {
            "allowed_sensitivities": {"personal_photo"},
            "path_prefixes": ["Photos/"],
        },
        "child": {
            "allowed_sensitivities": {"personal_photo"},
            "path_prefixes": ["Photos/"],
        },
    }
    return table[principal]


def evaluate_permission(match: dict, principal: str) -> dict:
    sensitivity = classify_sensitivity(match)
    policy = principal_permissions(principal)
    relative_path = match.get("relative_path", "")
    prefix_allowed = any(relative_path.startswith(prefix) for prefix in policy["path_prefixes"])
    sensitivity_allowed = sensitivity["sensitivity"] in policy["allowed_sensitivities"]
    allowed = bool(prefix_allowed and sensitivity_allowed)
    matched_rules = []
    if prefix_allowed:
        matched_rules.append("path_prefix_allowed")
    else:
        matched_rules.append("path_prefix_denied")
    if sensitivity_allowed:
        matched_rules.append(f"sensitivity_allowed:{sensitivity['sensitivity']}")
    else:
        matched_rules.append(f"sensitivity_denied:{sensitivity['sensitivity']}")
    return {
        "principal": principal,
        "decision": "allow" if allowed else "deny",
        "sensitivity": sensitivity["sensitivity"],
        "sensitivity_reasons": sensitivity["reasons"],
        "matched_rules": matched_rules,
        "policy_source": "local_policy_overlay_v1",
        "production_nas_acl_verified": False,
        "reason": "allowed by local role/path/sensitivity policy" if allowed else "denied by local role/path/sensitivity policy",
    }


def collect_matches(args: argparse.Namespace) -> tuple[list[dict], list[dict], dict]:
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
    photo_query = f"{args.query} invoice screenshot receipt beach car photo"
    for match in search_photo_semantic_index(args.sqlite_index_path, photo_query, args.limit):
        merge_match(merged, match, "photo_semantic_local_visual")
    candidates = sorted(
        merged.values(),
        key=lambda item: (item["confidence"], item["score"], item["relative_path"]),
        reverse=True,
    )
    filtered, rejected = filter_case_matches(args.query, candidates)
    return filtered[: args.limit], rejected, {"image_embedding_upsert": image_upsert}


def redact_denied_match(match: dict, permission: dict) -> dict:
    return {
        "redacted_result_id": stable_redaction_id(match.get("relative_path", "")),
        "type": match.get("type"),
        "confidence": match.get("confidence"),
        "permission": permission,
        "redaction_policy": "path, evidence snippet, summary, entities, and source path are hidden for denied results",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Permission-aware AI-NAS search with redacted denied results.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("principal", nargs="?", default=DEFAULT_PRINCIPAL)
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--no-refresh-index", action="store_true")
    args = parser.parse_args()

    if args.principal not in VALID_PRINCIPALS:
        raise SystemExit(f"principal must be one of: {', '.join(sorted(VALID_PRINCIPALS))}")
    if not args.query:
        args.query = DEFAULT_QUERY

    matches, rejected_matches, runtime = collect_matches(args)
    allowed_matches = []
    denied_matches = []
    for match in matches:
        permission = evaluate_permission(match, args.principal)
        if permission["decision"] == "allow":
            allowed = dict(match)
            allowed["permission"] = permission
            allowed_matches.append(allowed)
        else:
            denied_matches.append(redact_denied_match(match, permission))

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "query": args.query,
        "principal": args.principal,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": sqlite_index_status(args.sqlite_index_path),
        "runtime": runtime,
        "policy": {
            "policy_source": "local_policy_overlay_v1",
            "production_nas_acl_verified": False,
            "valid_principals": sorted(VALID_PRINCIPALS),
            "denied_result_redaction": "Denied results do not expose path, evidence, summary, entities, or source snippets.",
            "limitation": "This is an application-layer policy overlay until real NAS ACL/user mapping is integrated.",
        },
        "summary": {
            "candidate_count": len(matches),
            "allowed_count": len(allowed_matches),
            "denied_count": len(denied_matches),
            "rejected_candidate_count": len(rejected_matches),
        },
        "matches": allowed_matches,
        "denied_matches": denied_matches,
        "rejected_matches": rejected_matches,
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON permission-aware search report plus SQLite index refresh only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "permission_aware_search")
    json_path = run_dir / "permission_aware_search.json"
    md_path = run_dir / "permission_aware_search.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Permission-Aware Search",
        "",
        f"- query: `{args.query}`",
        f"- principal: `{args.principal}`",
        f"- allowed_count: `{len(allowed_matches)}`",
        f"- denied_count: `{len(denied_matches)}`",
        f"- policy_source: `{payload['policy']['policy_source']}`",
        f"- production_nas_acl_verified: `{payload['policy']['production_nas_acl_verified']}`",
        "- policy: report/index only; denied results are redacted; no delete, no move, no overwrite",
        "",
        "## Allowed Matches",
        "",
    ]
    if not allowed_matches:
        lines.append("- No matched result is visible to this principal.")
    for match in allowed_matches:
        permission = match["permission"]
        lines.append(
            f"- `{match['relative_path']}` | confidence `{match['confidence']}` | "
            f"sensitivity `{permission['sensitivity']}`"
        )
        lines.append(f"  - evidence: {match.get('evidence_fragments', [''])[0] if match.get('evidence_fragments') else ''}")
        lines.append(f"  - permission: {permission['reason']}; rules `{', '.join(permission['matched_rules'])}`")
        lines.append(f"  - reasons: {', '.join(match.get('reasons', [])[:10])}")

    lines.extend(["", "## Denied Matches", ""])
    if not denied_matches:
        lines.append("- No candidate result was denied.")
    for item in denied_matches:
        permission = item["permission"]
        lines.append(
            f"- `{item['redacted_result_id']}` | type `{item.get('type')}` | "
            f"confidence `{item.get('confidence')}` | sensitivity `{permission['sensitivity']}`"
        )
        lines.append(f"  - decision: `{permission['decision']}` | reason: {permission['reason']}")
        lines.append("  - redaction: path/evidence/summary/entities hidden")

    lines.extend(["", "## Policy Limitations", ""])
    lines.append(f"- {payload['policy']['limitation']}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
