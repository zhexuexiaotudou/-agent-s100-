#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text, sha256_file


TOOL_ID = "ai_nas_action_rollback_copy"


def load_manifest(path: Path) -> dict:
    if not path.exists() or not path.is_file():
        raise ValueError(f"rollback_manifest_not_found:{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_collections_relative(relative_path: str) -> None:
    rel = Path(relative_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe_relative_path:{relative_path}")
    normalized = relative_path.replace("\\", "/")
    if not normalized.startswith("Collections/"):
        raise ValueError(f"path_outside_collections:{relative_path}")


def ensure_target_path(action: dict) -> Path:
    target_relative = action.get("target_relative_path") or ""
    target_absolute = action.get("target_absolute_path") or ""
    ensure_collections_relative(target_relative)
    target = Path(target_absolute)
    if not target_absolute:
        raise ValueError(f"missing_target_absolute_path:{target_relative}")
    normalized = target_absolute.replace("\\", "/")
    if "/Collections/" not in normalized and not normalized.startswith("Collections/"):
        raise ValueError(f"target_absolute_not_under_collections:{target_absolute}")
    if target.name in {"", ".", ".."}:
        raise ValueError(f"unsafe_target_name:{target_absolute}")
    return target


def verify_manifest(manifest: dict, rollback_phrase: str) -> str:
    if manifest.get("source_execution_tool") != "ai_nas_action_execute_copy":
        raise ValueError("unsupported_source_execution_tool")
    if manifest.get("rollback_allowed") is not True:
        raise ValueError("rollback_not_allowed")
    manifest_id = str(manifest.get("manifest_id") or "").strip()
    if not manifest_id.startswith("apm-"):
        raise ValueError("invalid_manifest_id")
    expected = f"ROLLBACK {manifest_id}"
    if rollback_phrase.strip() != expected:
        raise ValueError("rollback_phrase_mismatch")
    return manifest_id


def rollback_action(action: dict) -> dict:
    target = ensure_target_path(action)
    target_relative = action["target_relative_path"]
    expected_digest = action.get("expected_target_sha256")
    if not expected_digest:
        raise ValueError(f"missing_expected_target_sha256:{target_relative}")
    if not target.exists():
        return {
            "action_id": action.get("action_id"),
            "status": "skipped_missing_target",
            "target_relative_path": target_relative,
            "target_absolute_path": str(target),
            "expected_target_sha256": expected_digest,
        }
    if not target.is_file() or target.is_symlink():
        raise ValueError(f"target_not_regular_file:{target_relative}")
    actual_digest = sha256_file(target)
    if actual_digest != expected_digest:
        raise ValueError(f"target_sha256_mismatch:{target_relative}")
    target.unlink()
    return {
        "action_id": action.get("action_id"),
        "status": "removed_copied_target",
        "target_relative_path": target_relative,
        "target_absolute_path": str(target),
        "expected_target_sha256": expected_digest,
        "actual_target_sha256": actual_digest,
    }


def source_audit(action: dict) -> dict:
    source_path = action.get("source_absolute_path")
    if not source_path:
        return {
            "source_relative_path": action.get("source_relative_path"),
            "status": "source_path_not_in_manifest",
        }
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        return {
            "source_relative_path": action.get("source_relative_path"),
            "source_absolute_path": str(source),
            "status": "source_missing_or_not_file",
        }
    expected = action.get("source_sha256")
    actual = sha256_file(source)
    return {
        "source_relative_path": action.get("source_relative_path"),
        "source_absolute_path": str(source),
        "status": "source_hash_checked" if expected == actual else "source_hash_changed",
        "expected_source_sha256": expected,
        "actual_source_sha256": actual,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback approved AI-NAS copy-only actions by removing copied targets only.")
    parser.add_argument("rollback_manifest_path", type=Path)
    parser.add_argument("rollback_phrase")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()

    manifest = load_manifest(args.rollback_manifest_path)
    manifest_id = verify_manifest(manifest, args.rollback_phrase)
    actions = manifest.get("rollback_actions") or []
    if not isinstance(actions, list):
        raise ValueError("rollback_actions_must_be_list")

    removed = []
    skipped = []
    failed = []
    source_audits = []
    for action in actions:
        if not isinstance(action, dict):
            failed.append({"action_id": None, "error": "invalid_action_entry"})
            continue
        source_audits.append(source_audit(action))
        try:
            result = rollback_action(action)
            if result["status"] == "removed_copied_target":
                removed.append(result)
            else:
                skipped.append(result)
        except Exception as exc:
            failed.append(
                {
                    "action_id": action.get("action_id"),
                    "target_relative_path": action.get("target_relative_path"),
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "rollback_manifest_path": str(args.rollback_manifest_path),
        "manifest_id": manifest_id,
        "rollback_phrase_accepted": True,
        "status": "completed" if removed and not failed else "completed_with_skips" if skipped and not failed else "failed",
        "requested_rollback_count": len(actions),
        "removed_count": len(removed),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "removed_actions": removed,
        "skipped_actions": skipped,
        "failed_actions": failed,
        "source_audit": source_audits,
        "audit": {
            "source_files_modified": False,
            "copied_target_delete_performed": bool(removed),
            "source_delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "directories_removed": False,
            "writes": "removed hash-verified copied target files plus Markdown/JSON rollback execution reports",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "action_rollback_copy")
    json_path = run_dir / "action_rollback_copy.json"
    md_path = run_dir / "action_rollback_copy.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Approved Copy Rollback",
        "",
        f"- status: `{payload['status']}`",
        f"- manifest_id: `{payload['manifest_id']}`",
        f"- removed_count: `{payload['removed_count']}`",
        f"- skipped_count: `{payload['skipped_count']}`",
        f"- failed_count: `{payload['failed_count']}`",
        "- policy: remove only copied target files after SHA256 verification; no source delete, no move, no overwrite",
        "",
        "## Removed Targets",
        "",
    ]
    if not removed:
        lines.append("- No targets were removed.")
    for item in removed:
        lines.append(f"- `{item['action_id']}` removed `{item['target_relative_path']}`")
        lines.append(f"  - sha256: `{item['actual_target_sha256']}`")
    lines.extend(["", "## Skipped Targets", ""])
    if not skipped:
        lines.append("- No skipped targets.")
    for item in skipped:
        lines.append(f"- `{item.get('action_id')}`: `{item.get('status')}` for `{item.get('target_relative_path')}`")
    lines.extend(["", "## Failed Targets", ""])
    if not failed:
        lines.append("- No failed targets.")
    for item in failed:
        lines.append(f"- `{item.get('action_id')}`: `{item.get('error')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if removed and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
