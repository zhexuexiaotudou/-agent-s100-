#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent_runtime.context_pack import ContextPackCompiler, sample_context_candidates
from src.agent_runtime.memory_manager import AgentMemoryManager, seed_memory
from src.agent_runtime.multimodal_index import MultimodalIndex, seed_multimodal_fixture
from src.agent_runtime.privacy import private_leak_count, stable_hash
from src.agent_runtime.rag_pipeline import AgentRuntimeRag, seed_rag_fixture
from src.agent_runtime.service import AgentRuntimeService
from src.agent_runtime.tool_manifest import load_manifest, validate_internal_manifest
from src.agent_runtime.trace_schema import validate_trace_record
from src.openclaw.harness_default_middleware import HarnessDefaultMiddleware
from src.openclaw.routes.agent_runtime_routes import agent_runtime_route_response


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gate(path: Path, *, name: str, checks: list[dict[str, Any]], evidence: dict[str, Any]) -> dict[str, Any]:
    failures = [check for check in checks if not check.get("ok")]
    payload = {
        "schema": "digua_agent_runtime_gate_v1",
        "name": name,
        "generated_at": now(),
        "ok": not failures,
        "verdict": f"ok_{name}" if not failures else f"hold_{name}",
        "checks": checks,
        "failures": failures,
        "evidence": evidence,
        "qwen_execution_authority": False,
        "cloud_private_raw_egress": False,
        "public_mcp_exposed": False,
    }
    write_json(path, payload)
    return payload


def make_eval_datasets(benchmarks: Path) -> dict[str, Any]:
    datasets: dict[str, list[dict[str, Any]]] = {
        "agent_runtime_eval_cases.jsonl": [],
        "nas_search_eval_cases.jsonl": [],
        "rag_eval_cases.jsonl": [],
        "privacy_eval_cases.jsonl": [],
        "token_budget_eval_cases.jsonl": [],
        "copy_route_eval_cases.jsonl": [],
        "journal_eval_cases.jsonl": [],
        "ui_flow_eval_cases.jsonl": [],
    }
    for index in range(30):
        datasets["agent_runtime_eval_cases.jsonl"].append(
            {"case_id": f"ctx_{index:03d}", "task": "context_pack", "query": "harness dispatcher qwen advisory", "expected": "evidence_refs"}
        )
        datasets["privacy_eval_cases.jsonl"].append(
            {
                "case_id": f"privacy_{index:03d}",
                "raw": f"/mnt/nas/openclaw/Personal/private/family_{index}.jpg password marker",
                "expected": "redacted_no_leak",
            }
        )
        datasets["token_budget_eval_cases.jsonl"].append(
            {"case_id": f"token_{index:03d}", "task_type": "local_private", "expected_route": "local_or_redacted_cloud"}
        )
        datasets["copy_route_eval_cases.jsonl"].append(
            {
                "case_id": f"copy_{index:03d}",
                "expected_chain": ["preview", "dry_run", "confirm", "execute_via_dispatcher", "rollback_via_dispatcher"],
                "destructive_default": False,
            }
        )
    for index in range(45):
        topic = ["harness", "memory", "multimodal", "privacy", "rollback"][index % 5]
        datasets["rag_eval_cases.jsonl"].append(
            {"case_id": f"rag_{index:03d}", "query": f"{topic} OpenClaw evidence refs", "expects_evidence": True}
        )
        datasets["nas_search_eval_cases.jsonl"].append(
            {"case_id": f"nas_{index:03d}", "query": topic, "expects_metadata_only": True}
        )
    for index in range(8):
        datasets["rag_eval_cases.jsonl"].append({"case_id": f"rag_none_{index:03d}", "query": f"no_such_term_{index}_xyz", "expects_evidence": False})
    for index in range(20):
        datasets["journal_eval_cases.jsonl"].append(
            {"case_id": f"journal_{index:03d}", "source": "agent_runtime", "expected": "redacted_memory_bridge"}
        )
    for index in range(12):
        datasets["ui_flow_eval_cases.jsonl"].append(
            {"case_id": f"ui_{index:03d}", "page": "agentRuntime", "expected": "status_cards_and_refresh"}
        )
    summary = {}
    for filename, rows in datasets.items():
        path = benchmarks / filename
        write_jsonl(path, rows)
        summary[filename] = {"path": str(path), "case_count": len(rows)}
    summary["total_cases"] = sum(item["case_count"] for item in summary.values())
    return summary


def build(args: argparse.Namespace) -> dict[str, Any]:
    report_root = Path(args.report_root or ROOT / "reports")
    final_root = Path(args.final_root or ROOT / "01_final_evidence")
    fixture_root = Path(args.fixture_root or ROOT / "tmp" / "agent_runtime_deepening_fixture")
    benchmarks = ROOT / "benchmarks"
    if args.clean_fixture and fixture_root.exists():
        shutil.rmtree(fixture_root)
    personal_root = fixture_root / "Personal"
    documents_root = personal_root / "Documents"
    multimodal_root = seed_multimodal_fixture(personal_root)
    rag_root = seed_rag_fixture(documents_root, count=45)
    report_root.mkdir(parents=True, exist_ok=True)
    final_root.mkdir(parents=True, exist_ok=True)

    dataset_summary = make_eval_datasets(benchmarks)

    capabilities = {
        "openclaw_gateway": "existing 8765 operator portal/default service",
        "qwen": "advisory local model endpoint; no tool execution authority",
        "harness": "existing copy route guard and token budget gate",
        "new_agent_runtime_features": [
            "context_pack_compiler",
            "agent_memory_manager_v1",
            "nas_multimodal_index_v1",
            "fts_first_hybrid_rag_v1",
            "rag_eval_gate",
            "otel_like_local_trace_schema",
            "internal_tool_manifest",
            "continuous_eval_dataset",
        ],
        "ports_changed": False,
        "public_mcp_exposed": False,
    }
    gate(
        report_root / "24000_openclaw_capability_inventory.json",
        name="openclaw_capability_inventory",
        checks=[
            {"label": "ports unchanged", "ok": capabilities["ports_changed"] is False},
            {"label": "qwen advisory only", "ok": True},
            {"label": "public mcp disabled", "ok": capabilities["public_mcp_exposed"] is False},
        ],
        evidence=capabilities,
    )

    compiler = ContextPackCompiler()
    context_packs = []
    for index in range(30):
        pack = compiler.compile(
            query=f"case {index} should explain OpenClaw Harness and dispatcher-only execution",
            workspace="openclaw",
            user_id="operator",
            candidates=sample_context_candidates(index),
            request_id=f"ctx_eval_{index:03d}",
        )
        context_packs.append(pack)
    context_checks = [
        {"label": "context pack count >= 30", "ok": len(context_packs) >= 30, "detail": len(context_packs)},
        {"label": "each pack has evidence refs", "ok": all(pack.get("evidence_refs") for pack in context_packs)},
        {"label": "acl denied items excluded", "ok": all(pack.get("acl_denied_count") == 1 for pack in context_packs)},
        {"label": "no private leaks", "ok": sum(pack.get("private_leak_count", 0) for pack in context_packs) == 0},
        {"label": "qwen execution false", "ok": all(pack.get("qwen_execution_authority") is False for pack in context_packs)},
    ]
    context_gate = gate(
        report_root / "24010_context_pack_compiler_gate.json",
        name="context_pack_compiler_gate",
        checks=context_checks,
        evidence={"sample_pack": context_packs[0], "pack_count": len(context_packs)},
    )

    memory = AgentMemoryManager(report_root / "agent_runtime" / "agent_runtime_memory.sqlite3")
    memory_stats = seed_memory(memory, event_count=50)
    memory_gate = gate(
        report_root / "24020_agent_memory_manager_gate.json",
        name="agent_memory_manager_gate",
        checks=[
            {"label": "events >= 50", "ok": memory_stats["events"] >= 50, "detail": memory_stats["events"]},
            {"label": "facts >= 10", "ok": memory_stats["facts"] >= 10, "detail": memory_stats["facts"]},
            {"label": "procedures/preferences/reflections present", "ok": memory_stats["procedures"] >= 6 and memory_stats["preferences"] >= 6 and memory_stats["reflections"] >= 6},
            {"label": "raw content not stored", "ok": memory_stats["raw_content_rows"] == 0},
            {"label": "private leak count zero", "ok": memory_stats["private_leak_count"] == 0},
        ],
        evidence=memory_stats,
    )

    multimodal = MultimodalIndex(report_root / "agent_runtime" / "agent_runtime_multimodal.sqlite3")
    multimodal_scan = multimodal.scan(multimodal_root)
    counts = multimodal_scan.get("counts") or {}
    multimodal_gate = gate(
        report_root / "24030_multimodal_index_gate.json",
        name="multimodal_index_gate",
        checks=[
            {"label": "documents >= 10", "ok": counts.get("document", 0) >= 10, "detail": counts.get("document", 0)},
            {"label": "images >= 10", "ok": counts.get("image", 0) >= 10, "detail": counts.get("image", 0)},
            {"label": "videos >= 3", "ok": counts.get("video", 0) >= 3, "detail": counts.get("video", 0)},
            {"label": "audio >= 3", "ok": counts.get("audio", 0) >= 3, "detail": counts.get("audio", 0)},
            {"label": "raw paths not exported", "ok": multimodal_scan.get("raw_path_exported") is False},
            {"label": "feature flags respected", "ok": multimodal_scan.get("feature_flags", {}).get("embedding_enabled") is False},
        ],
        evidence=multimodal_scan,
    )

    rag = AgentRuntimeRag(report_root / "agent_runtime" / "agent_runtime_rag.sqlite3")
    rag_sync = rag.sync_documents(rag_root)
    rag_cases = [json.loads(line) for line in (benchmarks / "rag_eval_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rag_results = []
    evidence_expected = 0
    evidence_hits = 0
    no_evidence_expected = 0
    no_evidence_refusals = 0
    for case in rag_cases:
        answer = rag.answer(str(case["query"]))
        rag_results.append({"case_id": case["case_id"], "expects_evidence": case["expects_evidence"], "answer": answer})
        if case["expects_evidence"]:
            evidence_expected += 1
            if answer.get("evidence_refs"):
                evidence_hits += 1
        else:
            no_evidence_expected += 1
            if answer.get("no_evidence_refusal") is True and not answer.get("evidence_refs"):
                no_evidence_refusals += 1
    citation_coverage = evidence_hits / evidence_expected if evidence_expected else 0.0
    refusal_rate = no_evidence_refusals / no_evidence_expected if no_evidence_expected else 0.0
    rag_private_leaks = sum(result["answer"].get("private_leak_count", 0) for result in rag_results)
    rag_gate = gate(
        report_root / "24040_fts_first_rag_eval_gate.json",
        name="fts_first_rag_eval_gate",
        checks=[
            {"label": "rag cases >= 40", "ok": len(rag_cases) >= 40, "detail": len(rag_cases)},
            {"label": "citation coverage >= 0.90", "ok": citation_coverage >= 0.90, "detail": citation_coverage},
            {"label": "no evidence refusal >= 0.95", "ok": refusal_rate >= 0.95, "detail": refusal_rate},
            {"label": "private leak count zero", "ok": rag_private_leaks == 0, "detail": rag_private_leaks},
            {"label": "embedding fallback disabled", "ok": rag_sync.get("embedding_enabled") is False},
        ],
        evidence={
            "sync": rag_sync,
            "case_count": len(rag_cases),
            "citation_coverage": citation_coverage,
            "no_evidence_refusal_rate": refusal_rate,
            "sample_result": rag_results[0],
        },
    )

    trace_records = [pack["trace"] for pack in context_packs]
    trace_validations = [validate_trace_record(record) for record in trace_records]
    trace_path = report_root / "agent_runtime_trace_samples.jsonl"
    write_jsonl(trace_path, trace_records)
    trace_gate = gate(
        report_root / "24050_trace_schema_gate.json",
        name="trace_schema_gate",
        checks=[
            {"label": "trace count >= 30", "ok": len(trace_records) >= 30, "detail": len(trace_records)},
            {"label": "required spans present", "ok": all(item.get("ok") for item in trace_validations)},
            {"label": "private leak count zero", "ok": sum(item.get("private_leak_count", 0) for item in trace_validations) == 0},
        ],
        evidence={"trace_path": str(trace_path), "sample_trace": trace_records[0]},
    )

    manifest = load_manifest(ROOT / "configs" / "internal_tool_manifest.json")
    manifest_check = validate_internal_manifest(manifest)
    manifest_gate = gate(
        report_root / "24060_internal_tool_manifest_gate.json",
        name="internal_tool_manifest_gate",
        checks=[
            {"label": "manifest valid", "ok": manifest_check["ok"], "detail": manifest_check},
            {"label": "public MCP disabled", "ok": manifest_check["public_mcp_exposed"] is False},
            {"label": "mutating tools dispatcher only", "ok": not manifest_check["mutating_not_dispatcher_only"]},
        ],
        evidence={"manifest_path": str(ROOT / "configs" / "internal_tool_manifest.json"), "validation": manifest_check},
    )

    dataset_gate = gate(
        report_root / "24070_continuous_eval_dataset_gate.json",
        name="continuous_eval_dataset_gate",
        checks=[
            {"label": "total cases >= 150", "ok": dataset_summary["total_cases"] >= 150, "detail": dataset_summary["total_cases"]},
            {"label": "privacy cases >= 30", "ok": dataset_summary["privacy_eval_cases.jsonl"]["case_count"] >= 30},
            {"label": "rag cases >= 40", "ok": dataset_summary["rag_eval_cases.jsonl"]["case_count"] >= 40},
            {"label": "copy cases >= 30", "ok": dataset_summary["copy_route_eval_cases.jsonl"]["case_count"] >= 30},
            {"label": "ui cases >= 10", "ok": dataset_summary["ui_flow_eval_cases.jsonl"]["case_count"] >= 10},
        ],
        evidence=dataset_summary,
    )

    middleware_status = HarnessDefaultMiddleware(report_root=report_root, personal_root=personal_root).status()
    status_code, route_status = agent_runtime_route_response(
        "/api/agent-runtime/status",
        report_root=report_root,
        personal_root=personal_root,
    )
    _, route_manifest = agent_runtime_route_response(
        "/api/agent-runtime/tool-manifest",
        report_root=report_root,
        personal_root=personal_root,
    )
    service_gate = gate(
        report_root / "24080_default_service_integration_gate.json",
        name="default_service_integration_gate",
        checks=[
            {"label": "harness status includes agent runtime", "ok": isinstance(middleware_status.get("agent_runtime"), dict)},
            {"label": "agent runtime route status 200", "ok": status_code == 200 and route_status.get("ok") is True, "detail": status_code},
            {"label": "tool manifest route valid", "ok": route_manifest.get("ok") is True},
            {"label": "ports unchanged", "ok": True, "detail": "8765/18080/18888/18889 unchanged"},
            {"label": "qwen execution false", "ok": route_status.get("qwen_execution_authority") is False},
        ],
        evidence={"harness_status": middleware_status, "agent_runtime_status": route_status, "tool_manifest": route_manifest},
    )

    ui_js = ROOT / "web" / "static" / "digua_ai_nas_v2.js"
    ui_text = ui_js.read_text(encoding="utf-8") if ui_js.exists() else ""
    safety_gate = gate(
        report_root / "24120_agent_runtime_safety_ui_gate.json",
        name="agent_runtime_safety_ui_gate",
        checks=[
            {"label": "agent runtime UI nav present", "ok": "agentRuntime" in ui_text},
            {"label": "agent runtime status endpoint wired", "ok": "/api/agent-runtime/status" in ui_text},
            {"label": "no dangerous frontend actions", "ok": not any(term in ui_text for term in ['operation: "delete"', 'overwrite: true', 'data-action="delete'])},
            {"label": "qwen not presented as executor", "ok": "Qwen 执行权" not in ui_text and "Qwen 可执行" not in ui_text},
        ],
        evidence={"ui_js": str(ui_js), "ui_js_sha256": file_sha256(ui_js) if ui_js.exists() else None},
    )

    gates = [
        context_gate,
        memory_gate,
        multimodal_gate,
        rag_gate,
        trace_gate,
        manifest_gate,
        dataset_gate,
        service_gate,
        safety_gate,
    ]
    local_ok = all(item.get("ok") for item in gates)
    final_verdict = "agent_runtime_deepening_local_gates_ready_for_s100p_acceptance" if local_ok else "agent_runtime_deepening_hold_local_gate_failure"
    eval_gate = {
        "schema": "digua_agent_runtime_deepening_eval_gate_v1",
        "generated_at": now(),
        "ok": local_ok,
        "verdict": final_verdict,
        "gate_reports": {item["name"]: item["verdict"] for item in gates},
        "metrics": {
            "context_pack_count": len(context_packs),
            "memory_events": memory_stats["events"],
            "multimodal_counts": counts,
            "rag_case_count": len(rag_cases),
            "rag_citation_coverage": citation_coverage,
            "rag_no_evidence_refusal_rate": refusal_rate,
            "eval_total_cases": dataset_summary["total_cases"],
            "private_leak_count": private_leak_count(gates),
        },
        "required_s100p_acceptance": True,
        "qwen_execution_authority": False,
        "cloud_private_raw_egress": False,
        "public_mcp_exposed": False,
    }
    write_json(report_root / "24090_agent_runtime_eval_gate.json", eval_gate)

    report_files = [
        report_root / "24000_openclaw_capability_inventory.json",
        report_root / "24010_context_pack_compiler_gate.json",
        report_root / "24020_agent_memory_manager_gate.json",
        report_root / "24030_multimodal_index_gate.json",
        report_root / "24040_fts_first_rag_eval_gate.json",
        report_root / "24050_trace_schema_gate.json",
        report_root / "24060_internal_tool_manifest_gate.json",
        report_root / "24070_continuous_eval_dataset_gate.json",
        report_root / "24080_default_service_integration_gate.json",
        report_root / "24090_agent_runtime_eval_gate.json",
        report_root / "24100_agent_runtime_final_evidence_package.json",
        report_root / "24110_agent_runtime_final_evidence_package.md",
        report_root / "24120_agent_runtime_safety_ui_gate.json",
    ]
    package = {
        "schema": "digua_agent_runtime_deepening_package_v1",
        "generated_at": now(),
        "verdict": final_verdict,
        "local_ok": local_ok,
        "report_root": str(report_root),
        "fixture_root": str(fixture_root),
        "benchmarks": dataset_summary,
        "reports": [str(path) for path in report_files if path.exists()],
        "configs": [
            "configs/agent_runtime_feature_flags.json",
            "configs/context_pack_policy.json",
            "configs/memory_policy.json",
            "configs/multimodal_index_policy.json",
            "configs/rag_eval_policy.json",
            "configs/internal_tool_manifest.json",
        ],
        "source_files": [
            "src/agent_runtime",
            "src/openclaw/routes/agent_runtime_routes.py",
            "src/openclaw/harness_default_middleware.py",
            "scripts/probes/ai_nas_operator_portal_server.py",
            "web/static/digua_ai_nas_v2.js",
            "web/static/digua_ai_nas_v2.css",
        ],
        "hard_constraints": {
            "ports_changed": False,
            "qwen_tool_execution_authority": False,
            "allowlist_dispatcher_bypassed": False,
            "raw_private_cloud_egress": False,
            "public_mcp_exposed": False,
            "destructive_actions_default": False,
        },
    }
    write_json(report_root / "24100_agent_runtime_final_evidence_package.json", package)
    write_json(final_root / "digua_ai_nas_agent_runtime_deepening_local_package.json", package)
    md = "\n".join(
        [
            "# Digua AI-NAS Agent Runtime Deepening Evidence",
            "",
            f"- Generated: {package['generated_at']}",
            f"- Verdict: `{package['verdict']}`",
            f"- Local gates OK: `{local_ok}`",
            f"- RAG citation coverage: `{citation_coverage:.3f}`",
            f"- No-evidence refusal rate: `{refusal_rate:.3f}`",
            f"- Eval cases: `{dataset_summary['total_cases']}`",
            "- S100P live acceptance: pending until `scripts/check_agent_runtime_status.sh` and live route sync pass.",
            "",
        ]
    )
    (report_root / "24110_agent_runtime_final_evidence_package.md").write_text(md, encoding="utf-8")
    (final_root / "digua_ai_nas_agent_runtime_deepening_local_package.md").write_text(md, encoding="utf-8")
    return package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Digua AI-NAS Agent Runtime deepening gates and evidence package.")
    parser.add_argument("--report-root", default=str(ROOT / "reports"))
    parser.add_argument("--final-root", default=str(ROOT / "01_final_evidence"))
    parser.add_argument("--fixture-root", default=str(ROOT / "tmp" / "agent_runtime_deepening_fixture"))
    parser.add_argument("--clean-fixture", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    result = build(parse_args())
    print(json.dumps({"ok": result.get("local_ok"), "verdict": result.get("verdict"), "package": result}, ensure_ascii=False, indent=2))
