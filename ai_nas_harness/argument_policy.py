from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .config_io import load_json_yaml, repo_root
from .redaction import detect_private_leaks


DEFAULT_ARG_POLICY_PATH = repo_root() / "config" / "workspace_arg_policy.yaml"
WRITE_TERMS = {"delete", "remove", "move", "rename", "copy", "write", "chmod", "chown", "rollback", "execute", "rm"}


def stable_args_hash(args: list[str] | dict[str, Any] | str) -> str:
    raw = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _flatten_args(args: list[str] | dict[str, Any] | str | None) -> str:
    if args is None:
        return ""
    if isinstance(args, str):
        return args
    return json.dumps(args, ensure_ascii=False, sort_keys=True)


class ArgumentPolicyFilter:
    def __init__(self, policy_path: str | Path = DEFAULT_ARG_POLICY_PATH):
        self.policy_path = Path(policy_path)
        self.policy = load_json_yaml(self.policy_path) if self.policy_path.exists() else {"workspaces": {}}

    def workspace_policy(self, workspace_id: str) -> dict[str, Any]:
        return dict((self.policy.get("workspaces") or {}).get(workspace_id) or {})

    def validate(self, workspace_id: str, tool_id: str, args: list[str] | None = None) -> dict[str, Any]:
        args = args or []
        policy = self.workspace_policy(workspace_id)
        text = _flatten_args(args)
        lowered = text.lower()
        args_hash = stable_args_hash(args)
        reasons: list[str] = []
        leaks = detect_private_leaks(text)

        if policy.get("read_only") and any(term in lowered for term in WRITE_TERMS):
            reasons.append("write_or_destructive_arg_in_read_only_workspace")
        if not policy.get("write_allowed", False) and any(term in lowered for term in {"delete", "remove", "move", "rename", "chmod", "chown", "rm"}):
            reasons.append("destructive_arg_not_allowed")
        if not policy.get("allow_path_traversal", False) and re.search(r"(^|[\\/])\.\.([\\/]|$)", text):
            reasons.append("path_traversal_denied")
        if not policy.get("allow_absolute_path", False) and re.search(r"(?i)(?:/mnt/|/home/|[A-Za-z]:\\|\\\\)", text):
            reasons.append("absolute_path_denied")
        if not policy.get("allow_private_snippet", False) and leaks:
            reasons.append("private_snippet_or_path_denied")
        if tool_id in set(policy.get("denied_tools") or []):
            reasons.append("tool_denied_by_arg_policy")

        allowed_roots = [str(item).lower() for item in policy.get("allowed_path_roots") or []]
        denied_roots = [str(item).lower() for item in policy.get("denied_path_roots") or []]
        for denied in denied_roots:
            if denied and denied in lowered:
                reasons.append("denied_path_root")
        if allowed_roots and re.search(r"(?i)(?:/mnt/|/home/|[A-Za-z]:\\|\\\\)", text):
            if not any(root in lowered for root in allowed_roots):
                reasons.append("outside_allowed_path_roots")

        return {
            "allowed": not reasons,
            "reason_code": "ok" if not reasons else reasons[0],
            "reasons": sorted(set(reasons)),
            "args_hash": args_hash,
            "leak_count": len(leaks),
            "leak_markers": leaks,
            "trace_args": {"args_hash": args_hash, "arg_count": len(args), "leak_count": len(leaks)},
            "policy": {
                "read_only": bool(policy.get("read_only")),
                "write_allowed": bool(policy.get("write_allowed")),
                "allow_cloud_egress": bool(policy.get("allow_cloud_egress")),
                "required_acl_check": bool(policy.get("required_acl_check")),
            },
        }
