from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .config_io import load_json_yaml, repo_root, resolve_repo_path
from .runtime_trace_writer import RuntimeTraceWriter


DEFAULT_POLICY_PATH = repo_root() / "config" / "workspace_tool_policy.yaml"


class ToolExposureFilter:
    def __init__(
        self,
        policy_path: str | Path = DEFAULT_POLICY_PATH,
        *,
        trace_writer: RuntimeTraceWriter | None = None,
        trace_db_path: str | Path | None = None,
    ):
        self.policy_path = Path(policy_path)
        self.policy = load_json_yaml(self.policy_path)
        self.trace_writer = trace_writer or (RuntimeTraceWriter(trace_db_path) if trace_db_path else None)
        self.dispatcher_path = resolve_repo_path(self.policy["dispatcher"]["local_path"])
        self.dispatcher_remote_path = self.policy["dispatcher"].get("remote_path", "")
        self.all_tool_ids = set(self.policy.get("tool_catalog", {}).keys())

    def workspace_policy(self, workspace_id: str) -> dict[str, Any]:
        workspaces = self.policy.get("workspaces") or {}
        if workspace_id not in workspaces:
            raise KeyError(f"unknown_workspace:{workspace_id}")
        return workspaces[workspace_id]

    def allowed_tool_ids(self, workspace_id: str) -> list[str]:
        return list(self.workspace_policy(workspace_id).get("allowed_tool_ids") or [])

    def approval_required_tools(self, workspace_id: str) -> set[str]:
        return set(self.workspace_policy(workspace_id).get("approval_required_tools") or [])

    def filter_tools(self, workspace_id: str, requested_tool_ids: list[str] | None = None) -> dict[str, Any]:
        allowed = self.allowed_tool_ids(workspace_id)
        requested = requested_tool_ids or allowed
        exposed = [tool_id for tool_id in requested if tool_id in allowed]
        denied = [tool_id for tool_id in requested if tool_id not in allowed]
        return {"workspace_id": workspace_id, "exposed_tool_ids": exposed, "denied_tool_ids": denied}

    def validate_tool_id(self, tool_id: str) -> bool:
        if not re.match(r"^[A-Za-z0-9_]+$", tool_id):
            return False
        return tool_id in self.all_tool_ids

    def call_tool(
        self,
        workspace_id: str,
        tool_id: str,
        args: list[str] | None = None,
        *,
        run_id: str | None = None,
        approval_token: str | None = None,
        dry_run: bool = True,
        timeout: int = 120,
    ) -> dict[str, Any]:
        args = args or []
        if not self.validate_tool_id(tool_id):
            return self._deny(run_id, workspace_id, tool_id, "invalid_or_unknown_tool_id", args)
        if tool_id not in self.allowed_tool_ids(workspace_id):
            return self._deny(run_id, workspace_id, tool_id, "tool_not_allowed_in_workspace", args)
        if tool_id in self.approval_required_tools(workspace_id) and not approval_token:
            return self._deny(run_id, workspace_id, tool_id, "approval_required", args)
        if dry_run:
            result = {
                "status": "allowed_dry_run",
                "workspace_id": workspace_id,
                "tool_id": tool_id,
                "dispatcher_path": str(self.dispatcher_path),
                "dispatcher_remote_path": self.dispatcher_remote_path,
                "args": args,
            }
            if self.trace_writer and run_id:
                self.trace_writer.add_tool_call(run_id, workspace_id, tool_id, "allowed_dry_run", args=args, result=result)
            return result

        if os.environ.get("AI_NAS_HARNESS_SHADOW", "0") != "1":
            return self._deny(run_id, workspace_id, tool_id, "harness_shadow_disabled", args)
        if not self.dispatcher_path.exists():
            return self._deny(run_id, workspace_id, tool_id, "local_dispatcher_missing", args)

        started = time.perf_counter()
        completed = subprocess.run(
            ["bash", str(self.dispatcher_path), tool_id, *args],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        result = {
            "status": "executed",
            "returncode": completed.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
        if self.trace_writer and run_id:
            self.trace_writer.add_tool_call(run_id, workspace_id, tool_id, "executed", args=args, result=result, elapsed_ms=elapsed_ms)
        return result

    def _deny(self, run_id: str | None, workspace_id: str, tool_id: str, reason: str, args: list[str]) -> dict[str, Any]:
        payload = {"status": "denied", "workspace_id": workspace_id, "tool_id": tool_id, "reason": reason, "args": args}
        if self.trace_writer and run_id:
            self.trace_writer.add_policy_denial(run_id, workspace_id, tool_id, reason, args)
            self.trace_writer.add_tool_call(run_id, workspace_id, tool_id, "denied", args=args, result=payload)
        return payload

