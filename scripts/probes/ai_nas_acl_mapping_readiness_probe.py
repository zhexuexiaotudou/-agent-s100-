#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)


TOOL_ID = "ai_nas_acl_mapping_readiness"
DEFAULT_MAPPING_CONFIGS = [
    Path("/mnt/nas/openclaw/config/ai_nas_principal_acl_map.json"),
    Path("/root/.openclaw/workspace/config/ai_nas_principal_acl_map.json"),
]


def tool_paths() -> dict:
    names = ["getfacl", "stat", "id", "getent", "smbstatus", "wbinfo", "net", "icacls"]
    return {name: shutil.which(name) for name in names}


def owner_group_names(st: os.stat_result) -> tuple[str | None, str | None]:
    owner = None
    group = None
    if os.name != "nt":
        try:
            import grp
            import pwd

            owner = pwd.getpwuid(st.st_uid).pw_name
            group = grp.getgrgid(st.st_gid).gr_name
        except Exception:
            owner = None
            group = None
    return owner, group


def sample_entries(root: Path, limit: int = 24) -> tuple[list[dict], list[dict]]:
    samples: list[dict] = []
    failures: list[dict] = []
    if not root.exists():
        return samples, [{"path": str(root), "error": "personal_root_missing"}]
    candidates = [root]
    try:
        for path in root.rglob("*"):
            candidates.append(path)
            if len(candidates) >= limit:
                break
    except Exception as exc:
        failures.append({"path": str(root), "error": f"walk_failed:{type(exc).__name__}:{exc}"})
    for path in candidates[:limit]:
        try:
            st = path.stat()
            owner, group = owner_group_names(st)
            rel = "." if path == root else path.relative_to(root).as_posix()
            samples.append(
                {
                    "relative_path": rel,
                    "kind": "dir" if path.is_dir() else "file",
                    "mode_octal": oct(stat.S_IMODE(st.st_mode)),
                    "uid": getattr(st, "st_uid", None),
                    "gid": getattr(st, "st_gid", None),
                    "owner": owner,
                    "group": group,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
        except Exception as exc:
            failures.append({"path": str(path), "error": f"stat_failed:{type(exc).__name__}:{exc}"})
    return samples, failures


def mapping_configs(paths: list[Path]) -> list[dict]:
    configs = []
    for path in paths:
        error = None
        exists = False
        size = None
        parse_ok = False
        schema_version = None
        principal_count = 0
        try:
            exists = path.exists()
            if exists:
                size = path.stat().st_size
                payload = json.loads(path.read_text(encoding="utf-8"))
                schema_version = payload.get("schema_version")
                principals = payload.get("principals")
                if isinstance(principals, list):
                    principal_count = sum(1 for item in principals if isinstance(item, dict) and item.get("principal"))
                parse_ok = isinstance(payload, dict)
        except PermissionError as exc:
            error = f"permission_denied:{exc}"
        except json.JSONDecodeError as exc:
            error = f"json_decode_error:{exc}"
        except OSError as exc:
            error = f"os_error:{type(exc).__name__}:{exc}"
        configs.append(
            {
                "path": str(path),
                "exists": exists,
                "size": size,
                "error": error,
                "parse_ok": parse_ok,
                "schema_version": schema_version,
                "principal_count": principal_count,
            }
        )
    return configs


def evaluate_readiness(personal_root: Path, samples: list[dict], failures: list[dict], tools: dict, configs: list[dict]) -> dict:
    root_exists = personal_root.exists()
    config_exists = any(item["exists"] for item in configs)
    config_present = any(item["exists"] and item.get("parse_ok") and item.get("principal_count", 0) > 0 for item in configs)
    posix_acl_tool = bool(tools.get("getfacl"))
    identity_tool = bool(tools.get("id") or tools.get("getent") or tools.get("wbinfo"))
    smb_tool = bool(tools.get("smbstatus") or tools.get("wbinfo") or tools.get("net"))
    windows_acl_tool = bool(tools.get("icacls"))
    uid_gid_seen = any(item.get("uid") is not None and item.get("gid") is not None for item in samples)
    named_owner_seen = any(item.get("owner") or item.get("group") for item in samples)
    blockers = []
    warnings = []
    if not root_exists:
        blockers.append("personal_root_missing")
    if not samples:
        blockers.append("no_acl_sample_entries")
    if os.name == "nt":
        warnings.append("windows_local_dev_cannot_verify_linux_nas_posix_acl")
        if not windows_acl_tool:
            warnings.append("icacls_not_available_for_windows_acl_sampling")
    if root_exists and not posix_acl_tool:
        blockers.append("getfacl_not_available_for_posix_acl_capture")
    if root_exists and not identity_tool:
        blockers.append("identity_mapping_tool_missing_id_getent_or_wbinfo")
    if root_exists and not smb_tool:
        warnings.append("smb_session_mapping_tool_missing_smbstatus_wbinfo_or_net")
    if root_exists and not config_exists:
        blockers.append("principal_to_acl_mapping_config_missing")
    if root_exists and config_exists and not config_present:
        blockers.append("principal_to_acl_mapping_config_invalid_or_empty")
    if samples and not uid_gid_seen:
        blockers.append("sample_entries_missing_uid_gid")
    if samples and os.name != "nt" and not named_owner_seen:
        warnings.append("uid_gid_present_but_owner_group_names_not_resolved")
    ready = root_exists and samples and posix_acl_tool and identity_tool and config_present and uid_gid_seen
    return {
        "production_nas_acl_ready": bool(ready),
        "root_exists": root_exists,
        "sample_count": len(samples),
        "stat_failure_count": len(failures),
        "posix_acl_tool_ready": posix_acl_tool,
        "identity_mapping_tool_ready": identity_tool,
        "smb_user_mapping_tool_ready": smb_tool,
        "windows_acl_tool_ready": windows_acl_tool,
        "principal_mapping_config_present": config_present,
        "uid_gid_seen": uid_gid_seen,
        "named_owner_seen": named_owner_seen,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AI-NAS production NAS ACL/user mapping readiness report.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--mapping-config", action="append", type=Path, default=[])
    args = parser.parse_args()

    config_paths = args.mapping_config or DEFAULT_MAPPING_CONFIGS
    tools = tool_paths()
    samples, failures = sample_entries(args.personal_root)
    configs = mapping_configs(config_paths)
    readiness = evaluate_readiness(args.personal_root, samples, failures, tools, configs)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ready_ai_nas_acl_mapping" if readiness["production_nas_acl_ready"] else "limited_ai_nas_acl_mapping_readiness",
        "scope": "read-only readiness for replacing local permission overlay with real NAS ACL/user mapping",
        "platform": {
            "system": platform.system(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "os_name": os.name,
        },
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": sqlite_index_status(args.sqlite_index_path) if args.sqlite_index_path.exists() else {"exists": False},
        "tools": tools,
        "mapping_configs": configs,
        "readiness": readiness,
        "sample_entries": samples,
        "stat_failures": failures,
        "production_contract": {
            "required_before_claiming_real_acl": [
                "NAS Personal root mounted and readable from the AI appliance",
                "per-file owner/group/mode or ACL entries captured without modifying files",
                "principal-to-NAS-user/group mapping config present",
                "SMB/session/user mapping evidence available when serving multiple users",
                "permission-aware search decisions sourced from real ACL mapping instead of local_policy_overlay_v1",
            ],
            "current_permission_search_policy": "local_policy_overlay_v1",
            "production_nas_acl_verified": False,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON readiness reports only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "acl_mapping_readiness")
    json_path = run_dir / "acl_mapping_readiness.json"
    md_path = run_dir / "acl_mapping_readiness.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS ACL Mapping Readiness",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- personal_root: `{args.personal_root}`",
        f"- production_nas_acl_ready: `{readiness['production_nas_acl_ready']}`",
        f"- sample_count: `{readiness['sample_count']}`",
        f"- blockers: `{readiness['blockers']}`",
        f"- warnings: `{readiness['warnings']}`",
        "- policy: read-only ACL/user-mapping readiness; no permission changes and no Personal source mutation",
        "",
        "## Tooling",
        "",
    ]
    for name, path in tools.items():
        lines.append(f"- {name}: `{path}`")
    lines.extend(["", "## Mapping Configs", ""])
    for item in configs:
        lines.append(f"- `{item['path']}` exists `{item['exists']}` size `{item['size']}`")
    lines.extend(["", "## Sample Entries", ""])
    if not samples:
        lines.append("- No entries sampled.")
    for item in samples[:12]:
        lines.append(
            f"- `{item['relative_path']}` kind `{item['kind']}` mode `{item['mode_octal']}` "
            f"uid `{item['uid']}` gid `{item['gid']}` owner `{item['owner']}` group `{item['group']}`"
        )
    lines.extend(["", "## Production Contract", ""])
    for requirement in payload["production_contract"]["required_before_claiming_real_acl"]:
        lines.append(f"- {requirement}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
