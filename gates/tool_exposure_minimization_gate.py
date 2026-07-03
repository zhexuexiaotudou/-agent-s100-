#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness_gate_common import check, dispatcher_tool_ids, gate_payload, load_latest_shadow_probe, load_registry_policy, write_gate_report


GATE_ID = "tool_exposure_minimization_gate"


def run_gate(report_root: str | Path | None = None) -> dict[str, Any]:
    _, policy = load_registry_policy()
    probe = load_latest_shadow_probe(report_root)
    dispatcher_count = len(dispatcher_tool_ids())
    workspaces = policy.get("workspaces") or {}
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    after_sizes: list[int] = []
    before_sizes: list[int] = []

    scenarios = probe.get("scenario_results") or []
    check(checks, failures, "six shadow scenarios executed", len(scenarios) == 6, len(scenarios))
    for item in scenarios:
        scenario_id = item.get("scenario_id")
        workspace_id = item.get("selected_workspace")
        allowed = set((workspaces.get(workspace_id) or {}).get("allowed_tool_ids") or [])
        exposed = set(item.get("exposed_tools") or [])
        denied = item.get("denied_tools") or []
        before = int(item.get("context_size_before_chars") or 0)
        after = int(item.get("context_size_after_chars") or 0)
        before_sizes.append(before)
        after_sizes.append(after)
        check(checks, failures, f"{scenario_id} exposes subset of workspace tools", exposed.issubset(allowed), sorted(exposed - allowed))
        check(checks, failures, f"{scenario_id} denies at least one out-of-scope or unapproved tool", len(denied) > 0, denied)
        check(checks, failures, f"{scenario_id} has no unauthorized context tools", not item.get("unauthorized_tools_in_context"), item.get("unauthorized_tools_in_context"))
        check(checks, failures, f"{scenario_id} context smaller than all-tools baseline", after < before, {"before": before, "after": after})
        check(checks, failures, f"{scenario_id} exposed tool count below dispatcher total", len(exposed) < dispatcher_count, {"exposed": len(exposed), "dispatcher": dispatcher_count})

    destructive = next((item for item in scenarios if item.get("scenario_id") == "nas_destructive_action_requires_approval"), {})
    exec_copy = [
        result for result in destructive.get("attempt_results", [])
        if result.get("tool_id") == "ai_nas_action_execute_copy"
    ]
    check(
        checks,
        failures,
        "destructive/copy action denied without approval",
        bool(exec_copy) and exec_copy[0].get("status") == "denied" and exec_copy[0].get("reason") == "approval_required",
        exec_copy[0] if exec_copy else None,
    )

    ops = next((item for item in scenarios if item.get("scenario_id") == "ops_health_check"), {})
    check(checks, failures, "Dream7B attempted tool denied in ops scenario", "dream7b_perf_identity" in (ops.get("denied_tools") or []), ops.get("denied_tools"))
    check(checks, failures, "probe did not bypass dispatcher", probe.get("dispatcher_bypassed") is False)
    check(checks, failures, "probe did not attach Dream7B foreground", probe.get("dream7b_foreground_attached") is False)
    check(checks, failures, "probe did not modify protected ports", probe.get("ports_modified") == [])

    avg_before = round(sum(before_sizes) / len(before_sizes), 1) if before_sizes else 0
    avg_after = round(sum(after_sizes) / len(after_sizes), 1) if after_sizes else 0
    check(checks, failures, "average context size reduced", avg_after < avg_before, {"before": avg_before, "after": avg_after})

    return gate_payload(
        GATE_ID,
        checks,
        failures,
        {
            "dispatcher_tool_count": dispatcher_count,
            "avg_context_before_chars": avg_before,
            "avg_context_after_chars": avg_after,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 1 tool exposure minimization.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    payload = run_gate(args.report_root)
    paths = write_gate_report(payload, args.report_root)
    print(paths["json"])
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
