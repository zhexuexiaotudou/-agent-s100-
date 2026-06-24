#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from ai_nas_action_approval_manifest_probe import hash_payload, stable_action_id
from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text, sha256_file


TOOL_ID = "ai_nas_action_execute_copy"


def load_manifest(path: Path) -> dict:
    if not path.exists() or not path.is_file():
        raise ValueError(f"manifest_not_found:{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_relative_inside(relative_path: str, required_prefix: str) -> None:
    rel = Path(relative_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe_relative_path:{relative_path}")
    normalized = relative_path.replace("\\", "/")
    if not normalized.startswith(required_prefix):
        raise ValueError(f"path_outside_required_prefix:{relative_path}")


def verify_manifest(manifest: dict, approval_phrase: str) -> None:
    if manifest.get("tool_id") != "ai_nas_action_approval_manifest":
        raise ValueError("unsupported_manifest_tool_id")
    if manifest.get("status") != "awaiting_human_confirmation":
        raise ValueError("manifest_status_not_awaiting_confirmation")
    claimed_hash = manifest.get("manifest_sha256")
    if not isinstance(claimed_hash, str) or len(claimed_hash) != 64:
        raise ValueError("manifest_sha256_missing_or_invalid")
    unsigned_manifest = dict(manifest)
    unsigned_manifest.pop("manifest_sha256", None)
    actual_hash = hash_payload(unsigned_manifest)
    if claimed_hash != actual_hash:
        raise ValueError("manifest_sha256_mismatch")
    expected = ((manifest.get("approval") or {}).get("approval_phrase") or "").strip()
    if approval_phrase.strip() != expected:
        raise ValueError("approval_phrase_mismatch")
    if (manifest.get("approval") or {}).get("execution_allowed_by_this_tool") is not False:
        raise ValueError("unexpected_manifest_execution_flag")
    proposed_actions = manifest.get("proposed_actions")
    if not isinstance(proposed_actions, list):
        raise ValueError("proposed_actions_must_be_list")
    for action in proposed_actions:
        if not isinstance(action, dict):
            raise ValueError("proposed_action_must_be_object")
        if action.get("action_type") != "copy":
            raise ValueError(f"unsupported_manifest_action_type:{action.get('action_type')}")
        source_relative = action.get("source_relative_path") or ""
        target_relative = action.get("target_relative_path") or ""
        expected_action_id = stable_action_id("copy", source_relative, target_relative)
        if action.get("action_id") != expected_action_id:
            raise ValueError(f"action_id_mismatch:{action.get('action_id')}")
        source_sha256 = action.get("source_sha256")
        if not isinstance(source_sha256, str) or len(source_sha256) != 64:
            raise ValueError(f"source_sha256_missing_or_invalid:{action.get('action_id')}")


def execute_action(action: dict, personal_root: Path) -> dict:
    if action.get("action_type") != "copy":
        raise ValueError(f"unsupported_action_type:{action.get('action_type')}")
    if action.get("destructive") is not False:
        raise ValueError(f"refusing_destructive_action:{action.get('action_id')}")
    if action.get("requires_human_confirmation") is not True:
        raise ValueError(f"action_missing_confirmation_requirement:{action.get('action_id')}")

    source_relative = action["source_relative_path"]
    target_relative = action["target_relative_path"]
    ensure_relative_inside(source_relative, "")
    ensure_relative_inside(target_relative, "Collections/")

    source = Path(action.get("source_absolute_path") or (personal_root / source_relative))
    target = personal_root / target_relative
    target_parent = target.parent
    if not source.exists() or not source.is_file():
        raise ValueError(f"source_missing:{source_relative}")
    expected_digest = action.get("source_sha256")
    actual_digest = sha256_file(source)
    if expected_digest != actual_digest:
        raise ValueError(f"source_sha256_mismatch:{source_relative}")
    if target.exists():
        raise ValueError(f"target_exists_no_overwrite:{target_relative}")
    target_parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    copied_digest = sha256_file(target)
    if copied_digest != expected_digest:
        target.unlink(missing_ok=True)
        raise ValueError(f"copied_sha256_mismatch:{target_relative}")
    return {
        "action_id": action["action_id"],
        "status": "copied",
        "source_relative_path": source_relative,
        "source_absolute_path": str(source),
        "target_relative_path": target_relative,
        "source_sha256": expected_digest,
        "target_sha256": copied_digest,
        "target_absolute_path": str(target),
        "delete_source": False,
        "move_source": False,
        "overwrite": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute approved AI-NAS copy-only actions from an approval manifest.")
    parser.add_argument("manifest_path", type=Path)
    parser.add_argument("approval_phrase")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest_path)
    verify_manifest(manifest, args.approval_phrase)
    personal_root = Path(manifest["personal_root"])
    proposed_actions = manifest.get("proposed_actions") or []
    executed = []
    failed = []
    for action in proposed_actions:
        try:
            executed.append(execute_action(action, personal_root))
        except Exception as exc:
            failed.append(
                {
                    "action_id": action.get("action_id"),
                    "source_relative_path": action.get("source_relative_path"),
                    "target_relative_path": action.get("target_relative_path"),
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )

    rollback_manifest = {
        "generated_at": iso_now(),
        "source_execution_tool": TOOL_ID,
        "manifest_id": manifest.get("manifest_id"),
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
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "manifest_path": str(args.manifest_path),
        "manifest_id": manifest.get("manifest_id"),
        "approval_phrase_accepted": True,
        "status": "completed" if executed and not failed else "completed_with_failures" if executed else "failed",
        "personal_root": str(personal_root),
        "requested_action_count": len(proposed_actions),
        "executed_count": len(executed),
        "failed_count": len(failed),
        "executed_actions": executed,
        "failed_actions": failed,
        "rollback_manifest": rollback_manifest,
        "audit": {
            "source_files_modified": False,
            "copy_performed": bool(executed),
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "copied files under Personal/Collections plus Markdown/JSON execution and rollback manifests",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "action_execute_copy")
    json_path = run_dir / "action_execute_copy.json"
    md_path = run_dir / "action_execute_copy.md"
    rollback_path = run_dir / "rollback_manifest.json"
    safe_write_json(json_path, payload)
    safe_write_json(rollback_path, rollback_manifest)
    lines = [
        "# AI-NAS Approved Copy Execution",
        "",
        f"- status: `{payload['status']}`",
        f"- manifest_id: `{payload['manifest_id']}`",
        f"- executed_count: `{payload['executed_count']}`",
        f"- failed_count: `{payload['failed_count']}`",
        "- policy: copy-only; no source delete, no source move, no overwrite",
        f"- rollback_manifest: `{rollback_path}`",
        "",
        "## Executed Actions",
        "",
    ]
    if not executed:
        lines.append("- No actions were copied.")
    for item in executed:
        lines.append(
            f"- `{item['action_id']}` copied `{item['source_relative_path']}` -> `{item['target_relative_path']}`"
        )
        lines.append(f"  - sha256: `{item['target_sha256']}`")
    lines.extend(["", "## Failed Actions", ""])
    if not failed:
        lines.append("- No failed actions.")
    for item in failed:
        lines.append(f"- `{item.get('action_id')}`: `{item.get('error')}`")
    lines.extend(["", "## Rollback Contract", ""])
    lines.append("- rollback may remove only the copied target files listed in `rollback_manifest.json`")
    lines.append("- rollback must verify target sha256 before removal")
    lines.append("- rollback must never touch source files")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if executed and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
