#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.config_io import filename_stamp, load_json_yaml, safe_write_json, safe_write_text, utc_stamp
from ai_nas_harness.context_builder import build_context, estimate_baseline_context_size
from ai_nas_harness.memory_store import MemoryStore
from ai_nas_harness.runtime_trace_writer import RuntimeTraceWriter
from ai_nas_harness.tool_filter import ToolExposureFilter


SCENARIOS = [
    {
        "id": "nas_search_read_only",
        "user_request": "Find renovation invoice evidence in my NAS without changing files.",
        "expected_workspace": "nas_search",
        "attempt_tools": ["ai_nas_permission_aware_search", "ai_nas_action_execute_copy"],
        "memory_scope": "nas_search",
        "max_privacy": "high",
    },
    {
        "id": "nas_denied_acl_search",
        "user_request": "As guest, search for payment contracts and show denied results safely.",
        "expected_workspace": "nas_search",
        "attempt_tools": ["ai_nas_permission_aware_search", "ai_nas_audit_trail_contract"],
        "memory_scope": "nas_search",
        "max_privacy": "high",
    },
    {
        "id": "nas_destructive_action_requires_approval",
        "user_request": "Delete an old invoice screenshot from Personal/Inbox.",
        "expected_workspace": "nas_action",
        "attempt_tools": ["ai_nas_action_approval_manifest", "ai_nas_action_execute_copy", "ai_nas_file_search"],
        "memory_scope": "nas_action",
        "max_privacy": "high",
    },
    {
        "id": "document_report_generation",
        "user_request": "Generate a grounded report for my Documents folder.",
        "expected_workspace": "document_rag",
        "attempt_tools": ["ai_nas_folder_rag", "ai_nas_evidence_report", "ai_nas_photo_semantic_search"],
        "memory_scope": "document_rag",
        "max_privacy": "high",
    },
    {
        "id": "web_cloud_research_redacted",
        "user_request": "Compare public AI-NAS market trends; redact my invoice, family photo, and /mnt/nas/Personal paths first.",
        "expected_workspace": "web_cloud_research",
        "attempt_tools": ["ai_nas_edge_cloud_router", "ai_nas_evidence_catalog_contract", "ai_nas_file_search"],
        "memory_scope": "web_cloud_research",
        "max_privacy": "none",
    },
    {
        "id": "ops_health_check",
        "user_request": "Check AI-NAS service health without changing model routes.",
        "expected_workspace": "ops_recovery",
        "attempt_tools": ["ai_nas_index_daemon_readiness", "ai_nas_task_queue", "dream7b_perf_identity"],
        "memory_scope": "ops_recovery",
        "max_privacy": "medium",
    },
]


def select_workspace(user_request: str) -> tuple[str, str, float, list[str]]:
    text = user_request.lower()
    if any(term in text for term in ["delete", "copy", "rollback", "manifest", "approval"]):
        return "nas_action", "write or destructive action request", 0.92, ["nas_search", "admin_audit"]
    if any(term in text for term in ["public", "market", "trend", "cloud", "redact"]):
        return "web_cloud_research", "public research with explicit redaction/cloud framing", 0.9, ["main_router", "document_rag"]
    if any(term in text for term in ["document", "report", "rag", "grounded"]):
        return "document_rag", "document report or RAG request", 0.88, ["nas_search", "admin_audit"]
    if any(term in text for term in ["health", "service", "route", "ops", "daemon", "queue"]):
        return "ops_recovery", "operational health or recovery request", 0.88, ["admin_audit", "main_router"]
    if any(term in text for term in ["photo", "movie", "image", "screenshot"]):
        return "media_photo", "media/photo request", 0.78, ["nas_search", "document_rag"]
    return "nas_search", "default local read-only NAS search", 0.74, ["main_router", "document_rag"]


def redact_for_cloud(text: str, terms: list[str], replacement: str) -> dict[str, Any]:
    redacted = text
    hits = []
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(redacted):
            hits.append(term)
            redacted = pattern.sub(replacement, redacted)
    return {
        "redacted_text": redacted,
        "redacted_terms": sorted(set(hits)),
        "redaction_applied": bool(hits),
        "contains_private_terms_after_redaction": any(term.lower() in redacted.lower() for term in terms),
    }


def trace_complete_for_run(db_path: Path, run_id: str) -> dict[str, Any]:
    required = {
        "harness_steps": "run_id = ?",
        "workspace_decisions": "run_id = ?",
        "tool_calls": "run_id = ?",
        "memory_reads": "run_id = ?",
        "gate_results": "run_id = ?",
    }
    with sqlite3.connect(db_path) as con:
        counts = {
            table: int(con.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", (run_id,)).fetchone()[0])
            for table, where in required.items()
        }
    return {"complete": all(value > 0 for value in counts.values()), "counts": counts}


def seed_memory(store: MemoryStore) -> None:
    store.seed_memory("person", "global", "User prefers evidence-backed AI-NAS decisions and no production route surprises.", privacy_level="low")
    store.seed_memory("case", "nas_search", "Recent case: renovation invoice search must preserve denied-result redaction.", privacy_level="high")
    store.seed_memory("case", "document_rag", "Document reports must cite source paths and explicit evidence fragments.", privacy_level="medium")
    store.seed_memory("experience", "global", "Use allowlist dispatcher only; never invoke arbitrary shell or script paths.", privacy_level="none")
    store.seed_memory("experience", "ops_recovery", "Health checks must not alter Dream7B ports 18888/18889 or foreground traffic.", privacy_level="medium")


def existing_gate_presence(root: Path) -> dict[str, Any]:
    checks = {
        "qwen_gateway": root / "scripts" / "qwen25_openai_gateway.py",
        "dispatcher": root / "scripts" / "probes" / "ai_nas_allowlisted_tool.sh",
        "openclaw_nas_control_gate": root / "scripts" / "probes" / "ai_nas_openclaw_nas_control_gate_probe.py",
        "edge_cloud_router_gate": root / "scripts" / "probes" / "ai_nas_edge_cloud_router_probe.py",
        "qwen_acceptance_packet": root / "scripts" / "probes" / "qwen25_ai_nas_acceptance_packet.py",
        "openclaw_service": root / "configs" / "systemd" / "openclaw-gateway.service",
        "qwen_service": root / "configs" / "systemd" / "qwen25-local-openai-gateway.service",
    }
    details = {name: str(path) for name, path in checks.items()}
    missing = [name for name, path in checks.items() if not path.exists()]
    return {
        "status": "pass" if not missing else "fail",
        "missing": missing,
        "details": details,
        "note": "Shadow probe checks that existing gate/service assets are still present. It does not reroute production traffic.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 1 shadow Workspace Harness probe.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--trace-db", type=Path, default=None)
    parser.add_argument("--memory-db", type=Path, default=None)
    args = parser.parse_args()

    run_dir = args.report_root / f"harness_shadow_probe_{filename_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_db = args.trace_db or (run_dir / "harness_runtime_trace.sqlite3")
    memory_db = args.memory_db or (run_dir / "harness_memory.sqlite3")

    registry = load_json_yaml(ROOT / "config" / "workspace_registry.yaml")
    policy = load_json_yaml(ROOT / "config" / "workspace_tool_policy.yaml")
    all_tool_ids = sorted((policy.get("tool_catalog") or {}).keys())
    writer = RuntimeTraceWriter(trace_db)
    tool_filter = ToolExposureFilter(trace_writer=writer)
    memory = MemoryStore(memory_db)
    seed_memory(memory)

    gate_presence = existing_gate_presence(ROOT)
    scenario_results = []
    for scenario in SCENARIOS:
        selected, reason, confidence, alternatives = select_workspace(scenario["user_request"])
        run_id = writer.start_run(scenario["id"], scenario["user_request"], selected, {"expected_workspace": scenario["expected_workspace"]})
        writer.add_workspace_decision(run_id, selected, reason, confidence, alternatives)

        workspace_policy = (registry.get("workspaces") or {})[selected]
        allowed_tool_ids = tool_filter.allowed_tool_ids(selected)
        filter_result = tool_filter.filter_tools(selected, scenario["attempt_tools"])
        scoped_memory = memory.read_memory(scope=scenario["memory_scope"], max_privacy_level=scenario["max_privacy"], limit=6)
        writer.add_memory_read(run_id, selected, "mixed", scenario["memory_scope"], scenario["max_privacy"], len(scoped_memory))
        context = build_context(
            scenario["user_request"],
            selected,
            [{"role": "user", "content": scenario["user_request"]}],
            scoped_memory,
            filter_result["exposed_tool_ids"],
        )
        baseline_size = estimate_baseline_context_size(all_tool_ids, [{"role": "user", "content": scenario["user_request"]}])

        attempted = []
        for tool_id in scenario["attempt_tools"]:
            attempted.append(
                tool_filter.call_tool(
                    selected,
                    tool_id,
                    ["shadow_probe"],
                    run_id=run_id,
                    dry_run=True,
                )
            )
        cloud_allowed = bool(workspace_policy.get("allow_cloud"))
        cloud_payload = None
        if selected == "web_cloud_research":
            redaction = redact_for_cloud(
                scenario["user_request"],
                policy["cloud_redaction"]["private_terms"],
                policy["cloud_redaction"]["replacement"],
            )
            cloud_payload = {
                "allowed": cloud_allowed,
                "egress_preview": redaction["redacted_text"],
                "redaction_applied": redaction["redaction_applied"],
                "redacted_terms": redaction["redacted_terms"],
                "contains_private_terms_after_redaction": redaction["contains_private_terms_after_redaction"],
            }
        writer.add_step(
            run_id,
            "context_built",
            "ok",
            {
                "context_hash": context["context_hash"],
                "exposed_tool_ids": context["exposed_tool_ids"],
                "denied_tool_ids": filter_result["denied_tool_ids"],
                "context_size_chars": context["context_size_chars"],
                "baseline_context_size_chars": baseline_size,
            },
        )
        writer.add_gate_result(run_id, "existing_ai_nas_gate_presence", "ok" if gate_presence["status"] == "pass" else "failed", gate_presence)

        writer.finish_run(
            run_id,
            "ok",
            {
                "selected_workspace": selected,
                "exposed_tools": filter_result["exposed_tool_ids"],
                "denied_tools": filter_result["denied_tool_ids"],
            },
        )
        trace_status = trace_complete_for_run(trace_db, run_id)
        unauthorized_in_context = [
            item for item in scenario["attempt_tools"]
            if item not in allowed_tool_ids and item in context["exposed_tool_ids"]
        ]
        scenario_results.append(
            {
                "scenario_id": scenario["id"],
                "user_request": scenario["user_request"],
                "expected_workspace": scenario["expected_workspace"],
                "selected_workspace": selected,
                "workspace_match": selected == scenario["expected_workspace"],
                "selection_reason": reason,
                "exposed_tools": filter_result["exposed_tool_ids"],
                "denied_tools": filter_result["denied_tool_ids"],
                "attempt_results": attempted,
                "unauthorized_tools_in_context": unauthorized_in_context,
                "cloud_allowed": cloud_allowed,
                "cloud_payload": cloud_payload,
                "memory_scope": {
                    "requested_scope": scenario["memory_scope"],
                    "max_privacy": scenario["max_privacy"],
                    "records": [
                        {
                            "memory_type": item["memory_type"],
                            "scope": item["scope"],
                            "privacy_level": item["privacy_level"],
                            "content_preview": item["content"][:100],
                        }
                        for item in scoped_memory
                    ],
                },
                "context_hash": context["context_hash"],
                "context_size_before_chars": baseline_size,
                "context_size_after_chars": context["context_size_chars"]["total"],
                "context_reduction_chars": baseline_size - context["context_size_chars"]["total"],
                "runtime_trace_complete": trace_status["complete"],
                "runtime_trace_counts": trace_status["counts"],
                "existing_gates_still_pass": gate_presence["status"] == "pass",
            }
        )

    trace_report = writer.export_report(run_dir / "harness_runtime_trace.json", run_dir / "harness_runtime_trace.md")
    failures = []
    for item in scenario_results:
        if not item["workspace_match"]:
            failures.append(f"{item['scenario_id']}:workspace_mismatch")
        if item["unauthorized_tools_in_context"]:
            failures.append(f"{item['scenario_id']}:unauthorized_tool_in_context")
        if not item["runtime_trace_complete"]:
            failures.append(f"{item['scenario_id']}:runtime_trace_incomplete")
        if item["scenario_id"] == "web_cloud_research_redacted":
            payload = item.get("cloud_payload") or {}
            if not payload.get("allowed") or not payload.get("redaction_applied") or payload.get("contains_private_terms_after_redaction"):
                failures.append(f"{item['scenario_id']}:cloud_redaction_failed")
        elif item["cloud_allowed"]:
            failures.append(f"{item['scenario_id']}:unexpected_cloud_allowed")

    payload = {
        "generated_at": utc_stamp(),
        "tool_id": "harness_shadow_probe",
        "verdict": "ok_harness_shadow_probe" if not failures else "failed_harness_shadow_probe",
        "shadow_enabled_default": False,
        "env_flag": "AI_NAS_HARNESS_SHADOW",
        "production_path_modified": False,
        "dispatcher_bypassed": False,
        "arbitrary_script_path_allowed": False,
        "dream7b_foreground_attached": False,
        "ports_modified": [],
        "trace_db": str(trace_db),
        "memory_db": str(memory_db),
        "existing_gate_presence": gate_presence,
        "scenario_results": scenario_results,
        "trace_report": trace_report,
        "summary": {
            "scenario_count": len(scenario_results),
            "failure_count": len(failures),
            "failures": failures,
            "total_tool_catalog_count": len(all_tool_ids),
            "avg_context_before_chars": round(sum(item["context_size_before_chars"] for item in scenario_results) / len(scenario_results), 1),
            "avg_context_after_chars": round(sum(item["context_size_after_chars"] for item in scenario_results) / len(scenario_results), 1),
        },
    }
    json_path = run_dir / "harness_shadow_probe.json"
    md_path = run_dir / "harness_shadow_probe.md"
    safe_write_json(json_path, payload)
    lines = [
        "# Harness Shadow Probe",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- production_path_modified: `{payload['production_path_modified']}`",
        f"- dispatcher_bypassed: `{payload['dispatcher_bypassed']}`",
        f"- dream7b_foreground_attached: `{payload['dream7b_foreground_attached']}`",
        f"- trace_db: `{trace_db}`",
        "",
        "## Scenarios",
        "",
    ]
    for item in scenario_results:
        lines.append(
            f"- `{item['scenario_id']}` workspace `{item['selected_workspace']}` "
            f"exposed `{len(item['exposed_tools'])}` denied `{len(item['denied_tools'])}` "
            f"cloud `{item['cloud_allowed']}` trace `{item['runtime_trace_complete']}`"
        )
        lines.append(f"  - context before/after: `{item['context_size_before_chars']}` -> `{item['context_size_after_chars']}`")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in failures] or ["- none"])
    safe_write_text(md_path, "\n".join(lines) + "\n")

    latest_json = args.report_root / "harness_shadow_probe_latest.json"
    latest_md = args.report_root / "harness_shadow_probe_latest.md"
    safe_write_json(latest_json, payload)
    safe_write_text(latest_md, "\n".join(lines) + "\n")
    print(json_path)
    print(md_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
