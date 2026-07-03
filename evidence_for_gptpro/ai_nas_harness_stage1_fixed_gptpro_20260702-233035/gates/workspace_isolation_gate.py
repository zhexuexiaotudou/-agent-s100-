#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.context_builder import build_context
from harness_gate_common import REQUIRED_WORKSPACES, check, dispatcher_tool_ids, gate_payload, load_registry_policy, write_gate_report


GATE_ID = "workspace_isolation_gate"
REQUIRED_REGISTRY_FIELDS = {
    "prompt_file",
    "default_model",
    "allow_cloud",
    "allow_write",
    "approval_required_tools",
    "allowed_tool_ids",
    "data_scope",
    "trace_requirements",
}


def run_gate(report_root: str | Path | None = None) -> dict[str, Any]:
    registry, policy = load_registry_policy()
    dispatcher_ids = set(dispatcher_tool_ids())
    catalog_ids = set((policy.get("tool_catalog") or {}).keys())
    registry_workspaces = registry.get("workspaces") or {}
    policy_workspaces = policy.get("workspaces") or {}
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    check(checks, failures, "shadow default disabled in registry", registry.get("shadow_default_enabled") is False)
    check(checks, failures, "shadow default disabled in policy", policy.get("shadow_default_enabled") is False)
    check(checks, failures, "dispatcher forbids arbitrary script path", bool(policy.get("dispatcher", {}).get("forbid_arbitrary_script_path")))
    check(checks, failures, "dispatcher local path is fixed allowlisted script", policy.get("dispatcher", {}).get("local_path") == "scripts/probes/ai_nas_allowlisted_tool.sh")
    check(checks, failures, "policy tool catalog is subset of dispatcher", catalog_ids.issubset(dispatcher_ids), sorted(catalog_ids - dispatcher_ids))
    check(checks, failures, "registry protects Dream7B foreground", registry.get("production_invariants", {}).get("dream7b_foreground_allowed") is False)
    check(checks, failures, "policy denies Dream7B ports", set(policy.get("global_denies", {}).get("ports") or []) == {18888, 18889})

    for workspace_id in REQUIRED_WORKSPACES:
        reg = registry_workspaces.get(workspace_id)
        pol = policy_workspaces.get(workspace_id)
        check(checks, failures, f"{workspace_id} exists in registry", isinstance(reg, dict))
        check(checks, failures, f"{workspace_id} exists in policy", isinstance(pol, dict))
        if not isinstance(reg, dict) or not isinstance(pol, dict):
            continue
        missing_fields = sorted(REQUIRED_REGISTRY_FIELDS - set(reg.keys()))
        allowed = set(pol.get("allowed_tool_ids") or [])
        registry_allowed = set(reg.get("allowed_tool_ids") or [])
        approvals = set(pol.get("approval_required_tools") or [])
        registry_approvals = set(reg.get("approval_required_tools") or [])
        check(checks, failures, f"{workspace_id} registry fields complete", not missing_fields, missing_fields)
        check(checks, failures, f"{workspace_id} registry and policy allowed tools match", registry_allowed == allowed, sorted(registry_allowed ^ allowed))
        check(checks, failures, f"{workspace_id} registry and policy approvals match", registry_approvals == approvals, sorted(registry_approvals ^ approvals))
        check(checks, failures, f"{workspace_id} allowed tools are cataloged", allowed.issubset(catalog_ids), sorted(allowed - catalog_ids))
        check(checks, failures, f"{workspace_id} allowed tools are dispatcher exposed", allowed.issubset(dispatcher_ids), sorted(allowed - dispatcher_ids))
        check(checks, failures, f"{workspace_id} approval tools are allowed subset", approvals.issubset(allowed), sorted(approvals - allowed))
        context = build_context(
            f"shadow isolation check for {workspace_id}",
            workspace_id,
            [{"role": "user", "content": "shadow isolation check"}],
            [],
            sorted(allowed),
        )
        exposed = set(context["exposed_tool_ids"])
        check(checks, failures, f"{workspace_id} context exposes only workspace tools", exposed == allowed, sorted(exposed ^ allowed))

    allowed_anywhere = {
        tool_id
        for workspace in policy_workspaces.values()
        for tool_id in (workspace.get("allowed_tool_ids") or [])
        if isinstance(workspace, dict)
    }
    check(checks, failures, "Dream7B dispatcher id is not exposed to any workspace", "dream7b_perf_identity" not in allowed_anywhere)
    check(checks, failures, "no workspace sees the full dispatcher catalog", all(len(ws.get("allowed_tool_ids") or []) < len(dispatcher_ids) for ws in policy_workspaces.values()))

    return gate_payload(
        GATE_ID,
        checks,
        failures,
        {
            "dispatcher_tool_count": len(dispatcher_ids),
            "catalog_tool_count": len(catalog_ids),
            "workspace_count": len(policy_workspaces),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 1 workspace isolation.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    payload = run_gate(args.report_root)
    paths = write_gate_report(payload, args.report_root)
    print(paths["json"])
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
