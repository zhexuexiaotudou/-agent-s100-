#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from ai_nas_action_approval_manifest_probe import build_approval_actions, blocked_destructive_actions
from ai_nas_action_execute_copy_probe import execute_action as execute_copy_action
from ai_nas_action_rollback_copy_probe import rollback_action, verify_manifest as verify_rollback_manifest
from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text, sha256_file


TOOL_ID = "ai_nas_destructive_action_governance"


def prepare_fixture(root: Path) -> tuple[Path, Path]:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    source = docs / "2024_renovation_contract.txt"
    source.write_text(
        "Renovation contract source file. This file must survive destructive-action governance checks.\n",
        encoding="utf-8",
    )
    return personal, source


def expect_refusal(name: str, func, *args) -> dict:
    try:
        result = func(*args)
        return {"name": name, "refused": False, "unexpected_result": result}
    except Exception as exc:
        return {
            "name": name,
            "refused": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS destructive-action governance contract acceptance.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "destructive_action_governance")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root, source = prepare_fixture(fixture_root)
    source_relative = "Documents/2024_renovation_contract.txt"
    copy_target_relative = "Collections/governance/2024_renovation_contract.txt"
    source_digest_before = sha256_file(source)

    match = {
        "relative_path": source_relative,
        "path": str(source),
        "confidence": 0.91,
        "sources": ["governance_fixture"],
    }
    suggestions = [
        {
            "source_relative_path": source_relative,
            "suggested_target_relative_path": copy_target_relative,
        }
    ]
    proposed_actions = build_approval_actions([match], suggestions, personal_root)
    blocked = blocked_destructive_actions([match])

    copy_contract_failures = []
    for action in proposed_actions:
        if action.get("action_type") != "copy":
            copy_contract_failures.append(f"{action.get('action_id')}:action_type_not_copy")
        if action.get("destructive") is not False:
            copy_contract_failures.append(f"{action.get('action_id')}:destructive_not_false")
        if action.get("requires_human_confirmation") is not True:
            copy_contract_failures.append(f"{action.get('action_id')}:missing_confirmation")
        if not action.get("rollback_plan"):
            copy_contract_failures.append(f"{action.get('action_id')}:missing_rollback_plan")
        if not action.get("preconditions"):
            copy_contract_failures.append(f"{action.get('action_id')}:missing_preconditions")
        if action.get("source_sha256") != source_digest_before:
            copy_contract_failures.append(f"{action.get('action_id')}:source_hash_missing_or_wrong")

    blocked_types = {item.get("action_type") for item in blocked}
    required_blocked = {"move", "delete", "overwrite", "rename"}
    blocked_contract_failures = []
    if blocked_types != required_blocked:
        blocked_contract_failures.append(f"blocked_types_mismatch:{sorted(blocked_types)}")
    for item in blocked:
        if item.get("status") != "blocked_not_generated":
            blocked_contract_failures.append(f"{item.get('action_type')}:status_not_blocked")
        if "suggestion -> human confirmation -> bounded execution -> rollback/manifest" not in item.get("required_gate", ""):
            blocked_contract_failures.append(f"{item.get('action_type')}:missing_required_gate")

    destructive_execute_refusals = [
        expect_refusal(
            "execute_delete_action",
            execute_copy_action,
            {
                "action_id": "delete-forbidden",
                "action_type": "delete",
                "destructive": True,
                "requires_human_confirmation": True,
                "source_relative_path": source_relative,
                "target_relative_path": copy_target_relative,
                "source_sha256": source_digest_before,
            },
            personal_root,
        ),
        expect_refusal(
            "execute_copy_marked_destructive",
            execute_copy_action,
            {
                "action_id": "copy-marked-destructive",
                "action_type": "copy",
                "destructive": True,
                "requires_human_confirmation": True,
                "source_relative_path": source_relative,
                "target_relative_path": copy_target_relative,
                "source_sha256": source_digest_before,
            },
            personal_root,
        ),
        expect_refusal(
            "execute_copy_outside_collections",
            execute_copy_action,
            {
                "action_id": "copy-outside-collections",
                "action_type": "copy",
                "destructive": False,
                "requires_human_confirmation": True,
                "source_relative_path": source_relative,
                "target_relative_path": "Documents/unsafe_copy.txt",
                "source_sha256": source_digest_before,
            },
            personal_root,
        ),
    ]

    rollback_refusals = [
        expect_refusal(
            "rollback_wrong_phrase",
            verify_rollback_manifest,
            {
                "source_execution_tool": "ai_nas_action_execute_copy",
                "rollback_allowed": True,
                "manifest_id": "apm-governance0001",
                "rollback_actions": [],
            },
            "ROLLBACK wrong-id",
        ),
        expect_refusal(
            "rollback_outside_collections",
            rollback_action,
            {
                "action_id": "rollback-outside",
                "target_relative_path": source_relative,
                "target_absolute_path": str(source),
                "expected_target_sha256": source_digest_before,
            },
        ),
    ]

    source_digest_after = sha256_file(source)
    forbidden_target = personal_root / "Documents" / "unsafe_copy.txt"
    failures = []
    failures.extend(copy_contract_failures)
    failures.extend(blocked_contract_failures)
    for item in destructive_execute_refusals + rollback_refusals:
        if not item.get("refused"):
            failures.append(f"{item['name']}:not_refused")
    if source_digest_after != source_digest_before:
        failures.append("source_hash_changed")
    if not source.exists():
        failures.append("source_missing_after_negative_tests")
    if forbidden_target.exists():
        failures.append("forbidden_target_created")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_destructive_action_governance" if not failures else "failed_ai_nas_destructive_action_governance",
        "scope": "bounded destructive-action governance contract for OpenClaw AI-NAS action tools",
        "fixture": {
            "personal_root": str(personal_root),
            "source_relative_path": source_relative,
            "source_sha256_before": source_digest_before,
            "source_sha256_after": source_digest_after,
        },
        "copy_contract": {
            "proposed_actions": proposed_actions,
            "failures": copy_contract_failures,
        },
        "blocked_destructive_actions": blocked,
        "blocked_contract_failures": blocked_contract_failures,
        "negative_execution_tests": destructive_execute_refusals,
        "negative_rollback_tests": rollback_refusals,
        "summary": {
            "copy_action_count": len(proposed_actions),
            "blocked_destructive_action_count": len(blocked),
            "negative_execution_refusal_count": sum(1 for item in destructive_execute_refusals if item.get("refused")),
            "negative_rollback_refusal_count": sum(1 for item in rollback_refusals if item.get("refused")),
            "source_preserved": source.exists() and source_digest_after == source_digest_before,
            "forbidden_target_created": forbidden_target.exists(),
            "failures": failures,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "copy_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "isolated fixture source file plus Markdown/JSON governance report only",
            "required_gate": "suggestion -> human confirmation -> bounded execution -> rollback/manifest",
        },
        "production_gap": "This validates destructive-action refusal on a bounded fixture. Real destructive tools remain out of scope until separate backup, retention, approval, and rollback contracts exist.",
    }

    json_path = run_dir / "destructive_action_governance.json"
    md_path = run_dir / "destructive_action_governance.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Destructive Action Governance",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- copy_action_count: `{payload['summary']['copy_action_count']}`",
        f"- blocked_destructive_action_count: `{payload['summary']['blocked_destructive_action_count']}`",
        f"- negative_execution_refusal_count: `{payload['summary']['negative_execution_refusal_count']}`",
        f"- negative_rollback_refusal_count: `{payload['summary']['negative_rollback_refusal_count']}`",
        f"- source_preserved: `{payload['summary']['source_preserved']}`",
        f"- failures: `{failures}`",
        "",
        "## Required Gate",
        "",
        "- suggestion -> human confirmation -> bounded execution -> rollback/manifest",
        "",
        "## Blocked Destructive Actions",
        "",
    ]
    for item in blocked:
        lines.append(f"- `{item['action_type']}`: `{item['status']}`")
    lines.extend(["", "## Negative Execution Tests", ""])
    for item in destructive_execute_refusals:
        lines.append(f"- `{item['name']}` refused `{item['refused']}` error `{item.get('error')}`")
    lines.extend(["", "## Negative Rollback Tests", ""])
    for item in rollback_refusals:
        lines.append(f"- `{item['name']}` refused `{item['refused']}` error `{item.get('error')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
