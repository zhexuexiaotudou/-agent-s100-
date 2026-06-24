#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


REQUIRED_FIELDS = {
    "id",
    "script",
    "mode",
    "inputSchema",
    "permissionLevel",
    "writesFiles",
    "requiresConfirmation",
    "reportPathPolicy",
    "approvedOutputPrefixes",
    "description",
}
DESTRUCTIVE_TERMS = ("delete", "move", "overwrite", "remove", "rm ", "unlink", "rmdir")
NON_DESTRUCTIVE_TERMS = (
    "never",
    "no delete",
    "no source delete",
    "no move",
    "no source",
    "copy-only",
    "non-destructive",
    "preserve originals",
    "suggestions",
    "without deleting",
    "without modifying",
    "never modifies",
)


def default_deploy_root() -> Path:
    return Path(__file__).resolve().parents[2] / "tmp" / "ai_nas_deploy"


def default_source_root(deploy_root: Path) -> Path:
    candidate = deploy_root.parent.parent
    if (candidate / "scripts" / "probes").exists():
        return candidate
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def text_or_empty(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def script_parity(tool: dict, source_root: Path, deploy_root: Path) -> dict:
    script = tool.get("script")
    if not isinstance(script, str) or not script:
        return {
            "source_exists": False,
            "deploy_exists": False,
            "source_path": None,
            "deploy_path": None,
            "same_sha256": False,
        }
    source_path = source_root / script
    deploy_path = deploy_root / script
    source_sha = sha256_file(source_path)
    deploy_sha = sha256_file(deploy_path)
    return {
        "source_exists": source_path.exists(),
        "deploy_exists": deploy_path.exists(),
        "source_path": str(source_path),
        "deploy_path": str(deploy_path),
        "source_sha256": source_sha,
        "deploy_sha256": deploy_sha,
        "same_sha256": bool(source_sha and deploy_sha and source_sha == deploy_sha),
    }


def validate_schema(schema: object) -> list[str]:
    issues: list[str] = []
    if not isinstance(schema, dict):
        return ["inputSchema must be an object"]
    if schema.get("type") != "object":
        issues.append("inputSchema.type must be object")
    if schema.get("additionalProperties") is not False:
        issues.append("inputSchema.additionalProperties must be false")
    props = schema.get("properties")
    if not isinstance(props, dict):
        issues.append("inputSchema.properties must be an object")
    for name, prop in (props or {}).items():
        if not isinstance(prop, dict):
            issues.append(f"inputSchema.properties.{name} must be an object")
            continue
        if prop.get("type") != "string":
            issues.append(f"inputSchema.properties.{name}.type must be string")
        if name == "query":
            if prop.get("maxLength", 0) > 240 or prop.get("maxLength") is None:
                issues.append("query maxLength must be <= 240")
        if name == "folder":
            if prop.get("maxLength", 0) > 160 or prop.get("maxLength") is None:
                issues.append("folder maxLength must be <= 160")
    return issues


def runner_exposes(runner_text: str, tool_id: str) -> bool:
    return bool(re.search(rf"(^|\W){re.escape(tool_id)}(\||\)|\s)", runner_text))


def plugin_map_exposes(plugin_text: str, tool_id: str) -> bool:
    return bool(re.search(rf'\["{re.escape(tool_id)}"\s*,', plugin_text))


def plugin_query_enabled(plugin_text: str, tool_id: str) -> bool:
    query_set_match = re.search(r"const queryEnabledToolIds = new Set\(\[(.*?)\]\);", plugin_text, re.S)
    if not query_set_match:
        return False
    return f'"{tool_id}"' in query_set_match.group(1)


def audit_tool(tool: dict, runner_text: str, plugin_text: str, source_root: Path, deploy_root: Path) -> dict:
    tool_id = tool.get("id", "")
    issues: list[str] = []
    warnings: list[str] = []
    missing = sorted(field for field in REQUIRED_FIELDS if field not in tool)
    for field in missing:
        issues.append(f"missing required field `{field}`")

    issues.extend(validate_schema(tool.get("inputSchema")))
    if not isinstance(tool.get("permissionLevel"), str) or not tool.get("permissionLevel"):
        issues.append("permissionLevel must be a non-empty string")
    if not isinstance(tool.get("writesFiles"), bool):
        issues.append("writesFiles must be boolean")
    if not isinstance(tool.get("requiresConfirmation"), bool):
        issues.append("requiresConfirmation must be boolean")
    if not isinstance(tool.get("reportPathPolicy"), str) or "approvedOutputPrefixes" not in tool.get("reportPathPolicy", ""):
        issues.append("reportPathPolicy must mention approvedOutputPrefixes")
    if not isinstance(tool.get("approvedOutputPrefixes"), list) or not tool.get("approvedOutputPrefixes"):
        issues.append("approvedOutputPrefixes must be a non-empty list")
    if "Personal" in " ".join(str(tool.get(key, "")) for key in ("mode", "description", "reportPathPolicy")):
        if not isinstance(tool.get("approvedInputPrefixes"), list) or not tool.get("approvedInputPrefixes"):
            issues.append("Personal-scoped tool must declare approvedInputPrefixes")

    combined_text = " ".join(str(tool.get(key, "")) for key in ("id", "mode", "description", "reportPathPolicy")).lower()
    mentions_destructive = any(term in combined_text for term in DESTRUCTIVE_TERMS)
    has_non_destructive_guard = any(term in combined_text for term in NON_DESTRUCTIVE_TERMS)
    if mentions_destructive and not (tool.get("requiresConfirmation") is True or has_non_destructive_guard):
        issues.append("destructive wording must be guarded by requiresConfirmation=true or explicit non-destructive policy")

    if not runner_exposes(runner_text, tool_id):
        issues.append("runner does not expose canonical tool id")
    if not tool_id.endswith("_probe") and not runner_exposes(runner_text, f"{tool_id}_probe"):
        warnings.append("runner does not expose _probe alias")
    if not plugin_map_exposes(plugin_text, tool_id):
        issues.append("OpenClaw plugin map does not expose canonical tool id")
    if not tool_id.endswith("_probe") and not plugin_map_exposes(plugin_text, f"{tool_id}_probe"):
        warnings.append("OpenClaw plugin map does not expose _probe alias")

    schema_props = (tool.get("inputSchema") or {}).get("properties") or {}
    schema_has_query = "query" in schema_props
    plugin_has_query = plugin_query_enabled(plugin_text, tool_id)
    plugin_alias_has_query = plugin_query_enabled(plugin_text, f"{tool_id}_probe")
    if schema_has_query and not plugin_has_query:
        issues.append("inputSchema declares query but OpenClaw plugin does not enable canonical query")
    if schema_has_query and not tool_id.endswith("_probe") and not plugin_alias_has_query:
        warnings.append("inputSchema declares query but OpenClaw plugin does not enable alias query")
    if plugin_has_query and not schema_has_query:
        issues.append("OpenClaw plugin enables query but inputSchema does not declare query")

    parity = script_parity(tool, source_root, deploy_root)
    if not parity["deploy_exists"]:
        issues.append("allowlisted script missing from deploy root")
    if not parity["source_exists"]:
        issues.append("allowlisted script missing from source root")

    return {
        "id": tool_id,
        "script": tool.get("script"),
        "permissionLevel": tool.get("permissionLevel"),
        "writesFiles": tool.get("writesFiles"),
        "requiresConfirmation": tool.get("requiresConfirmation"),
        "script_parity": parity,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit AI-NAS allowlist governance metadata and OpenClaw exposure.")
    parser.add_argument("--deploy-root", type=Path, default=default_deploy_root())
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()

    source_root = args.source_root or default_source_root(args.deploy_root)
    allowlist_path = args.deploy_root / "scripts" / "tool_allowlist.json"
    runner_path = args.deploy_root / "scripts" / "run_allowlisted_tool.sh"
    plugin_path = args.deploy_root / "openclaw-plugins" / "s100p-allowlisted-tools" / "index.js"
    allowlist = load_json(allowlist_path)
    runner_text = text_or_empty(runner_path)
    plugin_text = text_or_empty(plugin_path)
    tools = allowlist.get("tools") or []
    ai_nas_tools = [tool for tool in tools if str(tool.get("id", "")).startswith("ai_nas_")]
    ids = [tool.get("id") for tool in ai_nas_tools]
    duplicate_ids = sorted({tool_id for tool_id in ids if ids.count(tool_id) > 1})
    audits = [audit_tool(tool, runner_text, plugin_text, source_root, args.deploy_root) for tool in ai_nas_tools]
    hard_issues = []
    for duplicate_id in duplicate_ids:
        hard_issues.append({"id": duplicate_id, "issue": "duplicate ai_nas tool id"})
    for item in audits:
        for issue in item["issues"]:
            hard_issues.append({"id": item["id"], "issue": issue})
    warnings = [
        {"id": item["id"], "warning": warning}
        for item in audits
        for warning in item["warnings"]
    ]
    payload = {
        "generated_at": iso_now(),
        "verdict": "ok_ai_nas_allowlist_governance" if not hard_issues else "failed_ai_nas_allowlist_governance",
        "source_root": str(source_root),
        "deploy_root": str(args.deploy_root),
        "allowlist_path": str(allowlist_path),
        "runner_path": str(runner_path),
        "plugin_path": str(plugin_path),
        "tool_count": len(ai_nas_tools),
        "hard_issue_count": len(hard_issues),
        "warning_count": len(warnings),
        "source_deploy_parity": {
            "source_exists_count": sum(1 for item in audits if item["script_parity"].get("source_exists")),
            "deploy_exists_count": sum(1 for item in audits if item["script_parity"].get("deploy_exists")),
            "same_sha256_count": sum(1 for item in audits if item["script_parity"].get("same_sha256")),
            "different_sha256_count": sum(
                1
                for item in audits
                if item["script_parity"].get("source_exists")
                and item["script_parity"].get("deploy_exists")
                and not item["script_parity"].get("same_sha256")
            ),
        },
        "hard_issues": hard_issues,
        "warnings": warnings,
        "tools": audits,
        "policy": {
            "scope": "canonical ai_nas_* allowlist entries",
            "required_fields": sorted(REQUIRED_FIELDS),
            "destructive_action_rule": "destructive wording requires explicit non-destructive policy or requiresConfirmation=true",
            "plugin_alignment": "canonical IDs must be exposed by runner and OpenClaw plugin; query-enabled plugin IDs must match query schemas",
            "source_deploy_parity": "canonical scripts must exist in both source and deploy roots; sha256 differences are reported for review",
        },
        "audit": {
            "tool_id": "ai_nas_allowlist_governance_audit",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON governance report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "allowlist_governance_audit")
    json_path = run_dir / "allowlist_governance_audit.json"
    md_path = run_dir / "allowlist_governance_audit.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Allowlist Governance Audit",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- tool_count: `{payload['tool_count']}`",
        f"- hard_issue_count: `{payload['hard_issue_count']}`",
        f"- warning_count: `{payload['warning_count']}`",
        f"- source_exists_count: `{payload['source_deploy_parity']['source_exists_count']}`",
        f"- deploy_exists_count: `{payload['source_deploy_parity']['deploy_exists_count']}`",
        f"- same_sha256_count: `{payload['source_deploy_parity']['same_sha256_count']}`",
        f"- different_sha256_count: `{payload['source_deploy_parity']['different_sha256_count']}`",
        "- scope: canonical `ai_nas_*` allowlist entries",
        "- policy: schema, permission, write/confirmation flags, report path policy, approved prefixes, runner exposure, OpenClaw plugin exposure, and source/deploy script parity",
        "",
        "## Hard Issues",
        "",
    ]
    if not hard_issues:
        lines.append("- No hard governance issues found.")
    for issue in hard_issues:
        lines.append(f"- `{issue['id']}`: {issue['issue']}")
    lines.extend(["", "## Warnings", ""])
    if not warnings:
        lines.append("- No governance warnings found.")
    for warning in warnings:
        lines.append(f"- `{warning['id']}`: {warning['warning']}")
    lines.extend(["", "## Tool Summary", ""])
    for item in audits:
        lines.append(
            f"- `{item['id']}` permission `{item['permissionLevel']}` writes `{item['writesFiles']}` "
            f"confirmation `{item['requiresConfirmation']}` issues `{item['issue_count']}` warnings `{item['warning_count']}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not hard_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
