#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import shutil
from pathlib import Path

from ai_nas_action_approval_manifest_probe import hash_payload, stable_action_id
from ai_nas_action_execute_copy_probe import verify_manifest
from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text, sha256_file


TOOL_ID = "ai_nas_action_manifest_integrity"


def prepare_fixture(root: Path) -> tuple[Path, Path]:
    if root.exists():
        shutil.rmtree(root)
    personal = root / "Personal"
    docs = personal / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    source = docs / "2024_renovation_contract.txt"
    source.write_text(
        "Renovation contract fixture for approval manifest integrity checks.\n",
        encoding="utf-8",
    )
    return personal, source


def signed_manifest(personal_root: Path, source: Path) -> dict:
    source_relative = source.relative_to(personal_root).as_posix()
    target_relative = "Collections/integrity/2024_renovation_contract.txt"
    action_id = stable_action_id("copy", source_relative, target_relative)
    manifest_id = "apm-integrity0001"
    payload = {
        "generated_at": iso_now(),
        "tool_id": "ai_nas_action_approval_manifest",
        "manifest_id": manifest_id,
        "status": "awaiting_human_confirmation",
        "personal_root": str(personal_root),
        "proposed_actions": [
            {
                "action_id": action_id,
                "action_type": "copy",
                "status": "proposed_requires_human_confirmation",
                "source_relative_path": source_relative,
                "source_absolute_path": str(source),
                "source_sha256": sha256_file(source),
                "target_relative_path": target_relative,
                "target_absolute_path": str(personal_root / target_relative),
                "requires_human_confirmation": True,
                "destructive": False,
            }
        ],
        "approval": {
            "required": True,
            "approval_phrase": f"APPROVE {manifest_id}",
            "execution_allowed_by_this_tool": False,
        },
    }
    payload["manifest_sha256"] = hash_payload(payload)
    return payload


def expect_acceptance(manifest: dict, approval_phrase: str) -> dict:
    try:
        verify_manifest(manifest, approval_phrase)
        return {"accepted": True, "error": None}
    except Exception as exc:
        return {"accepted": False, "error": f"{type(exc).__name__}:{exc}"}


def expect_refusal(name: str, manifest: dict, approval_phrase: str) -> dict:
    try:
        verify_manifest(manifest, approval_phrase)
        return {"name": name, "refused": False, "unexpected": "manifest accepted"}
    except Exception as exc:
        return {
            "name": name,
            "refused": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS approval manifest integrity and tamper-refusal contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "action_manifest_integrity")
    fixture_root = args.fixture_root or (run_dir / "fixture")
    personal_root, source = prepare_fixture(fixture_root)
    valid = signed_manifest(personal_root, source)
    approval_phrase = valid["approval"]["approval_phrase"]
    valid_acceptance = expect_acceptance(valid, approval_phrase)

    tampered_target = copy.deepcopy(valid)
    tampered_target["proposed_actions"][0]["target_relative_path"] = "Collections/integrity/tampered.txt"

    stale_action_id = copy.deepcopy(valid)
    stale_action_id["proposed_actions"][0]["target_relative_path"] = "Collections/integrity/tampered-rehashed.txt"
    stale_action_id["manifest_sha256"] = hash_payload({k: v for k, v in stale_action_id.items() if k != "manifest_sha256"})

    missing_source_hash = copy.deepcopy(valid)
    missing_source_hash["proposed_actions"][0]["source_sha256"] = None
    missing_source_hash["manifest_sha256"] = hash_payload({k: v for k, v in missing_source_hash.items() if k != "manifest_sha256"})

    wrong_approval_phrase = copy.deepcopy(valid)

    refusals = [
        expect_refusal("target_tampered_without_rehash", tampered_target, approval_phrase),
        expect_refusal("target_tampered_with_stale_action_id", stale_action_id, approval_phrase),
        expect_refusal("missing_source_hash_with_rehash", missing_source_hash, approval_phrase),
        expect_refusal("approval_phrase_mismatch", wrong_approval_phrase, "APPROVE wrong-manifest"),
    ]
    failures = []
    if not valid_acceptance["accepted"]:
        failures.append(f"valid_manifest_rejected:{valid_acceptance['error']}")
    for item in refusals:
        if not item.get("refused"):
            failures.append(f"{item['name']}:not_refused")
    source_preserved = source.exists() and sha256_file(source) == valid["proposed_actions"][0]["source_sha256"]
    if not source_preserved:
        failures.append("source_not_preserved")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_action_manifest_integrity" if not failures else "failed_ai_nas_action_manifest_integrity",
        "scope": "bounded approval manifest integrity contract for AI-NAS copy execution",
        "fixture": {
            "personal_root": str(personal_root),
            "source_relative_path": valid["proposed_actions"][0]["source_relative_path"],
            "source_sha256": valid["proposed_actions"][0]["source_sha256"],
        },
        "valid_manifest": {
            "manifest_id": valid["manifest_id"],
            "manifest_sha256": valid["manifest_sha256"],
            "accepted": valid_acceptance,
        },
        "tamper_tests": refusals,
        "summary": {
            "valid_manifest_accepted": valid_acceptance["accepted"],
            "tamper_refusal_count": sum(1 for item in refusals if item.get("refused")),
            "tamper_test_count": len(refusals),
            "source_preserved": source_preserved,
            "failures": failures,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "copy_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "writes": "isolated fixture source file plus Markdown/JSON manifest integrity report only",
        },
        "production_gap": "This validates executor-side manifest hash and action-id tamper refusal on a bounded fixture; production still requires operator custody of signed manifests and audit retention.",
    }

    json_path = run_dir / "action_manifest_integrity.json"
    md_path = run_dir / "action_manifest_integrity.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Action Manifest Integrity",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- valid_manifest_accepted: `{payload['summary']['valid_manifest_accepted']}`",
        f"- tamper_refusal_count: `{payload['summary']['tamper_refusal_count']}` / `{payload['summary']['tamper_test_count']}`",
        f"- source_preserved: `{source_preserved}`",
        f"- failures: `{failures}`",
        "- policy: manifest integrity verification only; no copy, delete, move, overwrite, or service action",
        "",
        "## Tamper Tests",
        "",
    ]
    for item in refusals:
        lines.append(f"- `{item['name']}` refused `{item['refused']}` error `{item.get('error')}`")
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
