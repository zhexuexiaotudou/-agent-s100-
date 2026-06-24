#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_operator_approval_inbox"


def hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fixture_action(source: str, target: str, suffix: str) -> dict:
    return {
        "action_id": f"copy-{suffix}",
        "action_type": "copy",
        "status": "proposed_requires_human_confirmation",
        "source_relative_path": source,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "target_relative_path": target,
        "target_exists_now": False,
        "requires_human_confirmation": True,
        "destructive": False,
        "confidence": 0.91,
        "evidence_sources": ["sqlite_text_fts_metadata", "local_hash_embedding"],
        "rollback_plan": [
            "remove only the copied target created by the future execution manifest",
            "verify copied target sha256 before rollback",
            "append rollback audit event",
        ],
    }


def blocked_destructive_actions(candidate_count: int) -> list[dict]:
    return [
        {
            "action_type": action_type,
            "status": "blocked_not_generated",
            "candidate_file_count": candidate_count,
            "required_gate": "suggestion -> human confirmation -> bounded execution -> rollback/manifest",
        }
        for action_type in ["move", "delete", "overwrite", "rename"]
    ]


def make_manifest(manifest_id: str, status: str, action_count: int, complete: bool = True) -> dict:
    actions = [
        fixture_action(
            f"Documents/2024_renovation_contract_{idx}.txt",
            f"Collections/2024_Renovation/Documents/2024_renovation_contract_{idx}.txt",
            f"{manifest_id[-6:]}{idx}",
        )
        for idx in range(action_count)
    ]
    if not complete and actions:
        actions[0] = copy.deepcopy(actions[0])
        actions[0]["source_sha256"] = None
        actions[0]["rollback_plan"] = []
    payload = {
        "generated_at": iso_now(),
        "tool_id": "ai_nas_action_approval_manifest",
        "manifest_id": manifest_id,
        "status": status,
        "query": "2024 renovation payment contract invoice receipt chat screenshot",
        "collection_name": "2024_Renovation_Payment_Evidence",
        "proposed_actions": actions,
        "blocked_destructive_actions": blocked_destructive_actions(action_count),
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
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "execution_performed": False,
        },
    }
    payload["manifest_sha256"] = hash_payload(payload)
    return payload


def prepare_fixture(root: Path) -> list[Path]:
    if root.exists():
        shutil.rmtree(root)
    paths = []
    fixture_manifests = [
        make_manifest("apm-pending12345678", "awaiting_human_confirmation", 2, complete=True),
        make_manifest("apm-needsreview1234", "awaiting_human_confirmation", 1, complete=False),
        make_manifest("apm-approved123456", "approved_for_execution", 1, complete=True),
    ]
    for payload in fixture_manifests:
        manifest_dir = root / payload["manifest_id"]
        manifest_dir.mkdir(parents=True, exist_ok=True)
        path = manifest_dir / "action_approval_manifest.json"
        safe_write_json(path, payload)
        paths.append(path)
    return paths


def load_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": f"{type(exc).__name__}:{exc}", "_path": str(path)}


def find_manifests(scan_roots: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for root in scan_roots:
        if root.exists():
            paths.extend(root.rglob("action_approval_manifest.json"))
    return sorted(set(paths), key=lambda path: str(path))


def action_failures(action: dict) -> list[str]:
    failures = []
    action_id = action.get("action_id") or "unknown"
    if action.get("action_type") != "copy":
        failures.append(f"{action_id}:non_copy_action")
    if action.get("destructive") is not False:
        failures.append(f"{action_id}:destructive_not_false")
    if action.get("requires_human_confirmation") is not True:
        failures.append(f"{action_id}:missing_confirmation_flag")
    if not action.get("source_sha256"):
        failures.append(f"{action_id}:missing_source_sha256")
    if not action.get("target_relative_path"):
        failures.append(f"{action_id}:missing_target_relative_path")
    if not action.get("rollback_plan"):
        failures.append(f"{action_id}:missing_rollback_plan")
    return failures


def summarize_manifest(path: Path, payload: dict) -> tuple[dict, list[str]]:
    failures: list[str] = []
    if payload.get("_load_error"):
        return {
            "path": str(path),
            "manifest_id": None,
            "status": "unreadable",
            "risk_level": "blocked",
            "failure_count": 1,
            "decision_options": ["fix_manifest_json"],
        }, [f"{path}:load_error:{payload['_load_error']}"]

    manifest_id = payload.get("manifest_id")
    status = payload.get("status") or "unknown"
    approval = payload.get("approval") or {}
    actions = payload.get("proposed_actions") or []
    blocked = payload.get("blocked_destructive_actions") or []
    blocked_types = {item.get("action_type") for item in blocked}
    expected_hash = payload.get("manifest_sha256")
    if payload.get("tool_id") != "ai_nas_action_approval_manifest":
        failures.append("wrong_tool_id")
    if not manifest_id:
        failures.append("missing_manifest_id")
    if not expected_hash:
        failures.append("missing_manifest_sha256")
    if approval.get("required") is not True:
        failures.append("approval_not_required")
    if approval.get("execution_allowed_by_this_tool") is not False:
        failures.append("execution_allowed_by_manifest_tool_not_false")
    if approval.get("approval_phrase") != f"APPROVE {manifest_id}":
        failures.append("approval_phrase_not_exact_manifest_id")
    if not actions:
        failures.append("missing_proposed_actions")
    for action in actions:
        failures.extend(action_failures(action))
    if not {"move", "delete", "overwrite", "rename"} <= blocked_types:
        failures.append("missing_blocked_destructive_actions")

    risk_level = "ready_for_operator_review"
    if failures:
        risk_level = "needs_manifest_repair"
    elif status not in {"awaiting_human_confirmation", "approved_for_execution", "rejected_by_operator"}:
        risk_level = "unknown_status_review"
    decision_options = ["approve_with_exact_phrase", "reject", "needs_review"]
    if risk_level == "needs_manifest_repair":
        decision_options = ["needs_manifest_repair"]
    row = {
        "path": str(path),
        "manifest_id": manifest_id,
        "status": status,
        "query": payload.get("query"),
        "collection_name": payload.get("collection_name"),
        "generated_at": payload.get("generated_at"),
        "approval_phrase": approval.get("approval_phrase"),
        "action_count": len(actions),
        "blocked_destructive_action_types": sorted(blocked_types),
        "source_hash_complete": all(bool(action.get("source_sha256")) for action in actions),
        "rollback_plan_complete": all(bool(action.get("rollback_plan")) for action in actions),
        "execution_allowed_by_manifest_tool": approval.get("execution_allowed_by_this_tool"),
        "risk_level": risk_level,
        "failure_count": len(failures),
        "failures": failures,
        "decision_options": decision_options,
    }
    return row, [f"{manifest_id}:{failure}" for failure in failures]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a report-only AI-NAS operator approval inbox from approval manifests.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--scan-root", action="append", type=Path, default=[])
    parser.add_argument("--fixture-root", type=Path, default=None)
    parser.add_argument("--use-existing", action="store_true")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "operator_approval_inbox")
    if args.use_existing:
        scan_roots = args.scan_root or [args.report_root]
        manifest_paths = find_manifests(scan_roots)
        fixture_only = False
    else:
        fixture_root = args.fixture_root or (run_dir / "fixture_manifests")
        manifest_paths = prepare_fixture(fixture_root)
        scan_roots = [fixture_root]
        fixture_only = True

    rows = []
    manifest_issues: list[str] = []
    failures: list[str] = []
    for path in manifest_paths:
        row, row_failures = summarize_manifest(path, load_manifest(path))
        rows.append(row)
        manifest_issues.extend(row_failures)

    pending = [row for row in rows if row.get("status") == "awaiting_human_confirmation"]
    ready_pending = [row for row in pending if row.get("risk_level") == "ready_for_operator_review"]
    needs_repair = [row for row in rows if row.get("risk_level") == "needs_manifest_repair"]
    if not rows:
        failures.append("no_action_approval_manifests_found")
    if fixture_only and not ready_pending:
        failures.append("fixture_missing_ready_pending_manifest")
    if fixture_only and not needs_repair:
        failures.append("fixture_missing_needs_repair_manifest")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_operator_approval_inbox" if not failures else "failed_ai_nas_operator_approval_inbox",
        "scope": "report-only approval inbox for copy-only AI-NAS action manifests",
        "scan_roots": [str(root) for root in scan_roots],
        "fixture_only": fixture_only,
        "summary": {
            "manifest_count": len(rows),
            "pending_count": len(pending),
            "ready_pending_count": len(ready_pending),
            "needs_repair_count": len(needs_repair),
            "approved_count": sum(1 for row in rows if row.get("status") == "approved_for_execution"),
            "rejected_count": sum(1 for row in rows if row.get("status") == "rejected_by_operator"),
            "failure_count": len(failures),
            "manifest_issue_count": len(manifest_issues),
            "execution_performed": False,
            "all_ready_rows_have_exact_approval_phrase": all(
                row.get("approval_phrase") == f"APPROVE {row.get('manifest_id')}" for row in ready_pending
            ),
            "all_ready_rows_have_rollback_plan": all(row.get("rollback_plan_complete") for row in ready_pending),
            "all_ready_rows_block_destructive_actions": all(
                {"move", "delete", "overwrite", "rename"} <= set(row.get("blocked_destructive_action_types") or [])
                for row in ready_pending
            ),
        },
        "inbox": rows,
        "failures": failures,
        "manifest_issues": manifest_issues,
        "audit": {
            "source_files_modified": False,
            "real_personal_source_modified": False,
            "approval_execution_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "bounded fixture manifests when not using --use-existing plus Markdown/JSON approval inbox reports",
        },
        "production_gap": "Production UI or chat surface should render this inbox and require an exact operator decision before execution tools are invoked.",
    }
    json_path = run_dir / "operator_approval_inbox.json"
    md_path = run_dir / "operator_approval_inbox.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Operator Approval Inbox",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- manifest_count: `{payload['summary']['manifest_count']}`",
        f"- pending_count: `{payload['summary']['pending_count']}`",
        f"- ready_pending_count: `{payload['summary']['ready_pending_count']}`",
        f"- needs_repair_count: `{payload['summary']['needs_repair_count']}`",
        f"- failure_count: `{payload['summary']['failure_count']}`",
        f"- manifest_issue_count: `{payload['summary']['manifest_issue_count']}`",
        "- policy: report-only approval inbox; no action execution",
        "",
        "## Pending Decisions",
        "",
    ]
    for row in pending:
        lines.append(
            f"- `{row.get('manifest_id')}` status `{row.get('status')}` risk `{row.get('risk_level')}` "
            f"actions `{row.get('action_count')}`"
        )
        lines.append(f"  - approval_phrase: `{row.get('approval_phrase')}`")
        lines.append(f"  - decisions: `{', '.join(row.get('decision_options') or [])}`")
        if row.get("failures"):
            lines.append(f"  - failures: `{', '.join(row['failures'])}`")
    lines.extend(["", "## All Manifests", ""])
    for row in rows:
        lines.append(f"- `{row.get('manifest_id')}` {row.get('status')} {row.get('risk_level')} `{row.get('path')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
