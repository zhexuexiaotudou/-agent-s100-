#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.argument_policy import stable_args_hash
from ai_nas_harness.config_io import safe_write_json, safe_write_text, utc_stamp
from ai_nas_harness.privacy_filter import redact_cloud_payload
from ai_nas_harness.tool_filter import ToolExposureFilter


NAS_SEARCH_TOOLS = {"ai_nas_permission_aware_search", "ai_nas_file_search", "ai_nas_index_status"}
DOCUMENT_RAG_TOOLS = {
    "ai_nas_folder_rag",
    "ai_nas_evidence_report",
    "ai_nas_folder_summary",
    "ai_nas_ocr_readiness",
    "ai_nas_ocr_extract",
}
FORBIDDEN_TERMS = {"delete", "remove", "move", "rename", "chmod", "chown", "recovery", "admin", "dream7b"}


def choose_tool(workspace_id: str, prompt: str) -> str:
    text = prompt.lower()
    if workspace_id == "nas_search":
        if "status" in text or "metadata" in text:
            return "ai_nas_index_status"
        if "acl" in text or "denied" in text:
            return "ai_nas_permission_aware_search"
        return "ai_nas_file_search"
    if workspace_id == "document_rag":
        if "ocr" in text:
            return "ai_nas_ocr_readiness"
        if "summary" in text or "summarize" in text:
            return "ai_nas_folder_summary"
        if "report" in text:
            return "ai_nas_evidence_report"
        return "ai_nas_folder_rag"
    raise ValueError(f"unsupported workspace {workspace_id}")


def run_bridge(workspace_id: str, prompts: list[str], *, execute: bool = False) -> dict:
    tool_filter = ToolExposureFilter()
    runs = []
    for index, prompt in enumerate(prompts, start=1):
        tool_id = choose_tool(workspace_id, prompt)
        lower = prompt.lower()
        forbidden = sorted(term for term in FORBIDDEN_TERMS if term in lower)
        redaction = redact_cloud_payload(prompt)
        args = [prompt]
        if forbidden:
            result = {
                "status": "denied",
                "reason": "forbidden_readonly_sidecar_term",
                "forbidden_terms": forbidden,
                "args_hash": stable_args_hash(args),
            }
        else:
            result = tool_filter.call_tool(workspace_id, tool_id, args, dry_run=not execute)
        runs.append(
            {
                "run_id": f"{workspace_id}-{index:02d}",
                "workspace_id": workspace_id,
                "prompt_hash": stable_args_hash(prompt),
                "tool_id": tool_id,
                "allowed_tool_scope": sorted(NAS_SEARCH_TOOLS if workspace_id == "nas_search" else DOCUMENT_RAG_TOOLS),
                "dispatcher_used": result.get("dispatcher_path", "").endswith("ai_nas_allowlisted_tool.sh") or result.get("status") == "executed",
                "result_status": result.get("status"),
                "deny_reason": result.get("reason"),
                "args_hash": stable_args_hash(args),
                "redaction_applied": redaction.redaction_applied,
                "leak_count_after_redaction": redaction.leak_count,
                "cloud_called": False,
                "raw_args_recorded": False,
            }
        )
    failures = []
    for run in runs:
        if run["tool_id"] not in (NAS_SEARCH_TOOLS if workspace_id == "nas_search" else DOCUMENT_RAG_TOOLS):
            failures.append(f"{run['run_id']}:tool_out_of_scope")
        if run["cloud_called"]:
            failures.append(f"{run['run_id']}:cloud_called")
        if run["raw_args_recorded"]:
            failures.append(f"{run['run_id']}:raw_args_recorded")
    return {
        "generated_at": utc_stamp(),
        "workspace_id": workspace_id,
        "execute_real_dispatcher": execute,
        "run_count": len(runs),
        "runs": runs,
        "failure_count": len(failures),
        "failures": failures,
        "verdict": "ok_stage2_readonly_bridge" if not failures else "failed_stage2_readonly_bridge",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 2 read-only sidecar bridge.")
    parser.add_argument("--workspace-id", choices=["nas_search", "document_rag"], required=True)
    parser.add_argument("--prompts-json", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    prompts = json.loads(args.prompts_json.read_text(encoding="utf-8"))
    payload = run_bridge(args.workspace_id, prompts, execute=args.execute)
    safe_write_json(args.out_json, payload)
    lines = [
        f"# Stage 2 Read-only Bridge {args.workspace_id}",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- run_count: `{payload['run_count']}`",
        f"- failure_count: `{payload['failure_count']}`",
    ]
    for run in payload["runs"]:
        lines.append(f"- `{run['run_id']}` tool `{run['tool_id']}` status `{run['result_status']}`")
    safe_write_text(args.out_md, "\n".join(lines) + "\n")
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
