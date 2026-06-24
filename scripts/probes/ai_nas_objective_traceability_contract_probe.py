#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_objective_traceability_contract"


OBJECTIVE_ROWS = [
    {
        "id": "bpu_headroom_not_100",
        "area": "runtime_slo",
        "requirement": "Keep BPU around proven 93-95 percent with scheduling headroom instead of chasing 100 percent average utilization.",
        "must_have": ["bpu_headroom_slo"],
        "supporting": ["operational_slo_rollup_contract", "production_readiness_gate"],
        "accepted_verdicts": {
            "bpu_headroom_slo": ["ok_ai_nas_bpu_headroom_slo"],
            "operational_slo_rollup_contract": ["ok_ai_nas_operational_slo_rollup_contract"],
        },
    },
    {
        "id": "p95_p99_user_latency",
        "area": "runtime_slo",
        "requirement": "Track and gate P95/P99 user-facing latency across search, embedding, photo search, folder RAG, and case packet flows.",
        "must_have": ["user_facing_tail_latency", "operational_slo_rollup_contract"],
        "supporting": ["queue_backpressure_slo", "continuous_task_soak", "production_readiness_gate"],
        "accepted_verdicts": {
            "user_facing_tail_latency": ["ok_ai_nas_user_facing_tail_latency"],
            "operational_slo_rollup_contract": ["ok_ai_nas_operational_slo_rollup_contract"],
        },
    },
    {
        "id": "continuous_throughput_and_queueing",
        "area": "runtime_slo",
        "requirement": "Prove continuous task throughput, queue backpressure, checkpoint resume, and multi-task queue behavior.",
        "must_have": ["continuous_task_soak", "nas_backed_long_soak", "queue_backpressure_slo", "soak_checkpoint_resume"],
        "supporting": ["operational_slo_rollup_contract"],
        "accepted_verdicts": {
            "continuous_task_soak": ["ok_ai_nas_continuous_task_soak"],
            "nas_backed_long_soak": ["ok_ai_nas_nas_backed_long_soak"],
            "queue_backpressure_slo": ["ok_ai_nas_queue_backpressure_slo"],
            "soak_checkpoint_resume": ["ok_ai_nas_soak_checkpoint_resume"],
        },
    },
    {
        "id": "model_service_recovery",
        "area": "runtime_slo",
        "requirement": "Record model-service crash recovery evidence and keep unsafe restart actions behind approval manifests.",
        "must_have": ["model_service_recovery_drill", "model_service_recovery_manifest", "model_service_real_recovery_drill"],
        "supporting": ["operational_slo_rollup_contract", "production_dependency_bundle", "production_readiness_gate"],
        "accepted_verdicts": {
            "model_service_recovery_drill": ["ok_model_service_recovery_drill"],
            "model_service_recovery_manifest": ["ok_ai_nas_model_service_recovery_manifest"],
            "model_service_real_recovery_drill": ["ok_ai_nas_model_service_real_recovery_drill"],
        },
    },
    {
        "id": "index_chat_concurrency",
        "area": "runtime_slo",
        "requirement": "Show index tasks and dialogue/search tasks remain stable when they run concurrently.",
        "must_have": ["index_search_isolation_slo"],
        "supporting": ["operational_slo_rollup_contract", "concurrency_stability", "production_readiness_gate"],
        "accepted_verdicts": {
            "index_search_isolation_slo": ["ok_ai_nas_index_search_isolation_slo"],
        },
    },
    {
        "id": "index_productization",
        "area": "indexing",
        "requirement": "Use SQLite/FTS or equivalent index state instead of pure JSON, support incremental scan, change detection, and queryable status.",
        "must_have": [
            "sqlite_index_integrity_contract",
            "incremental_scan_efficiency_contract",
            "index_observability_contract",
            "index_rename_detection",
            "index_daemon_resident",
            "index_systemd_daemon_install",
        ],
        "supporting": ["index_daemon_readiness", "evidence_catalog_contract", "production_readiness_gate"],
        "accepted_verdicts": {
            "sqlite_index_integrity_contract": ["ok_ai_nas_sqlite_index_integrity_contract"],
            "incremental_scan_efficiency_contract": ["ok_ai_nas_incremental_scan_efficiency_contract"],
            "index_observability_contract": ["ok_ai_nas_index_observability_contract"],
            "index_rename_detection": ["ok_ai_nas_index_rename_detection"],
            "index_daemon_resident": ["ok_ai_nas_index_daemon_resident"],
            "index_systemd_daemon_install": ["ok_ai_nas_index_systemd_daemon_install"],
        },
    },
    {
        "id": "semantic_search_evidence",
        "area": "search",
        "requirement": "Support fuzzy natural-language queries with embedding evidence, reasons, snippets, and confidence.",
        "must_have": [
            "semantic_query_acceptance",
            "search_evidence_contract",
            "search_confidence_calibration_contract",
            "multimodal_intent_routing_contract",
        ],
        "supporting": ["embedding_runtime_contract", "user_facing_tail_latency", "production_readiness_gate"],
        "accepted_verdicts": {
            "semantic_query_acceptance": ["ok_ai_nas_semantic_query_acceptance"],
            "search_evidence_contract": ["ok_ai_nas_search_evidence_contract"],
            "search_confidence_calibration_contract": ["ok_ai_nas_search_confidence_calibration_contract"],
            "multimodal_intent_routing_contract": ["ok_ai_nas_multimodal_intent_routing_contract"],
        },
    },
    {
        "id": "document_rag_ocr",
        "area": "documents",
        "requirement": "Handle PDFs, OCR/scanned documents, classification, folder-level RAG, and explicit failure reporting without fabrication.",
        "must_have": ["document_pipeline_acceptance", "folder_rag_grounding_contract", "ocr_runtime_contract"],
        "supporting": ["production_readiness_gate"],
        "accepted_verdicts": {
            "document_pipeline_acceptance": ["ok_ai_nas_document_pipeline_acceptance"],
            "folder_rag_grounding_contract": ["ok_ai_nas_folder_rag_grounding_contract"],
            "ocr_runtime_contract": ["ok_ai_nas_ocr_runtime_contract", "limited_ai_nas_ocr_runtime_contract"],
        },
    },
    {
        "id": "photo_search_pipeline",
        "area": "photos",
        "requirement": "Cover EXIF/time/location/folder/hash, similarity/pHash, image embeddings, semantic photo search, and defer face recognition for privacy.",
        "must_have": ["photo_pipeline_acceptance", "photo_privacy_governance"],
        "supporting": ["photo_similarity", "image_embedding_extract", "photo_semantic_search", "production_readiness_gate"],
        "accepted_verdicts": {
            "photo_pipeline_acceptance": ["ok_ai_nas_photo_pipeline_acceptance"],
            "photo_privacy_governance": ["ok_ai_nas_photo_privacy_governance"],
        },
    },
    {
        "id": "openclaw_tool_governance",
        "area": "governance",
        "requirement": "Every OpenClaw tool needs schema, permission level, write/confirmation flags, report path policy, and auditable destructive-action workflow.",
        "must_have": [
            "allowlist_governance_audit",
            "destructive_action_governance",
            "action_manifest_integrity",
            "operator_approval_inbox",
            "audit_trail_contract",
        ],
        "supporting": ["evidence_catalog_contract", "evidence_freshness_contract", "production_readiness_gate"],
        "accepted_verdicts": {
            "allowlist_governance_audit": ["ok_ai_nas_allowlist_governance"],
            "destructive_action_governance": ["ok_ai_nas_destructive_action_governance"],
            "action_manifest_integrity": ["ok_ai_nas_action_manifest_integrity"],
            "operator_approval_inbox": ["ok_ai_nas_operator_approval_inbox"],
            "audit_trail_contract": ["ok_ai_nas_audit_trail_contract"],
        },
    },
    {
        "id": "local_copilot_appliance_shape",
        "area": "product_shape",
        "requirement": "Keep the product shape as a local AI Copilot appliance over arbitrary cheap NAS storage, not a NAS OS or plain file manager.",
        "must_have": ["portable_nas_adapter_contract", "appliance_experience_acceptance", "operator_portal_contract"],
        "supporting": ["production_dependency_bundle", "production_readiness_gate"],
        "accepted_verdicts": {
            "portable_nas_adapter_contract": ["ok_ai_nas_portable_nas_adapter_contract"],
            "appliance_experience_acceptance": ["ok_ai_nas_appliance_experience_acceptance"],
            "operator_portal_contract": ["ok_ai_nas_operator_portal_contract"],
        },
    },
    {
        "id": "renovation_payment_workflow",
        "area": "product_shape",
        "requirement": "For a 2024 renovation payment query, return files, match reasons, summaries, amounts/dates/payment nodes, paths, confidence, copy suggestions, report generation, approvals, and audit evidence.",
        "must_have": ["appliance_experience_acceptance", "operator_portal_contract", "user_facing_tail_latency"],
        "supporting": ["case_packet", "action_manifest_integrity", "audit_trail_contract", "production_readiness_gate"],
        "accepted_verdicts": {
            "appliance_experience_acceptance": ["ok_ai_nas_appliance_experience_acceptance"],
            "operator_portal_contract": ["ok_ai_nas_operator_portal_contract"],
            "user_facing_tail_latency": ["ok_ai_nas_user_facing_tail_latency"],
        },
    },
    {
        "id": "production_blockers_explicit",
        "area": "production_readiness",
        "requirement": "Do not claim production readiness until real NAS, production embedding/CLIP/OCR, ACL, health endpoints, systemd services, and recovery drill blockers are explicit and resolved.",
        "must_have": [
            "production_readiness_gate",
            "production_blocker_runbook_contract",
            "production_dependency_bundle",
            "evidence_freshness_contract",
            "evidence_catalog_contract",
            "index_systemd_daemon_install",
            "nas_backed_long_soak",
            "model_service_real_recovery_drill",
        ],
        "supporting": ["operational_slo_rollup_contract"],
        "accepted_verdicts": {
            "production_readiness_gate": ["ready_ai_nas_production_readiness_gate", "limited_ai_nas_production_readiness_gate"],
            "production_blocker_runbook_contract": ["ok_ai_nas_production_blocker_runbook_contract"],
            "production_dependency_bundle": ["ok_ai_nas_production_dependency_bundle", "limited_ai_nas_production_dependency_bundle"],
            "evidence_freshness_contract": ["ok_ai_nas_evidence_freshness_contract"],
            "evidence_catalog_contract": ["ok_ai_nas_evidence_catalog_contract"],
            "index_systemd_daemon_install": ["ok_ai_nas_index_systemd_daemon_install"],
            "nas_backed_long_soak": ["ok_ai_nas_nas_backed_long_soak"],
            "model_service_real_recovery_drill": ["ok_ai_nas_model_service_real_recovery_drill"],
        },
    },
]


REPORT_FILENAMES = {
    "action_manifest_integrity": "action_manifest_integrity.json",
    "allowlist_governance_audit": "allowlist_governance_audit.json",
    "appliance_experience_acceptance": "appliance_experience_acceptance.json",
    "audit_trail_contract": "audit_trail_contract_report.json",
    "bpu_headroom_slo": "bpu_headroom_slo.json",
    "case_packet": "case_packet.json",
    "concurrency_stability": "concurrency_stability.json",
    "continuous_task_soak": "continuous_task_soak.json",
    "destructive_action_governance": "destructive_action_governance.json",
    "document_pipeline_acceptance": "document_pipeline_acceptance.json",
    "embedding_runtime_contract": "embedding_runtime_contract.json",
    "evidence_catalog_contract": "evidence_catalog_contract.json",
    "evidence_freshness_contract": "evidence_freshness_contract.json",
    "folder_rag_grounding_contract": "folder_rag_grounding_contract.json",
    "image_embedding_extract": "image_embedding_extract.json",
    "incremental_scan_efficiency_contract": "incremental_scan_efficiency_contract.json",
    "index_daemon_readiness": "index_daemon_readiness.json",
    "index_daemon_resident": "index_daemon_resident.json",
    "index_systemd_daemon_install": "index_systemd_daemon_install.json",
    "index_observability_contract": "index_observability_contract.json",
    "index_rename_detection": "index_rename_detection.json",
    "index_search_isolation_slo": "index_search_isolation_slo.json",
    "model_service_recovery_drill": "model_service_recovery_drill.json",
    "model_service_recovery_manifest": "model_service_recovery_manifest.json",
    "model_service_real_recovery_drill": "model_service_real_recovery_drill.json",
    "multimodal_intent_routing_contract": "multimodal_intent_routing_contract.json",
    "nas_backed_long_soak": "nas_backed_long_soak.json",
    "ocr_runtime_contract": "ocr_runtime_contract.json",
    "operational_slo_rollup_contract": "operational_slo_rollup_contract.json",
    "operator_approval_inbox": "operator_approval_inbox.json",
    "operator_portal_contract": "operator_portal_contract.json",
    "photo_pipeline_acceptance": "photo_pipeline_acceptance.json",
    "photo_privacy_governance": "photo_privacy_governance.json",
    "photo_semantic_search": "photo_semantic_search.json",
    "photo_similarity": "photo_similarity.json",
    "portable_nas_adapter_contract": "portable_nas_adapter_contract.json",
    "production_blocker_runbook_contract": "production_blocker_runbook_contract.json",
    "production_dependency_bundle": "production_dependency_bundle.json",
    "production_readiness_gate": "production_readiness_gate.json",
    "queue_backpressure_slo": "queue_backpressure_slo.json",
    "search_confidence_calibration_contract": "search_confidence_calibration_contract.json",
    "search_evidence_contract": "search_evidence_contract.json",
    "semantic_query_acceptance": "semantic_query_acceptance.json",
    "soak_checkpoint_resume": "soak_checkpoint_resume.json",
    "sqlite_index_integrity_contract": "sqlite_index_integrity_contract.json",
    "user_facing_tail_latency": "user_facing_tail_latency.json",
}


def parse_report_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path) or {}
    generated_at = parse_report_time(payload.get("generated_at"))
    generated_ts = generated_at.timestamp() if generated_at else 0.0
    try:
        mtime_ts = path.stat().st_mtime
    except OSError:
        mtime_ts = 0.0
    return generated_ts, mtime_ts, str(path)


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [report_root]
    tmp_root = Path("tmp")
    if tmp_root.exists():
        roots.append(tmp_root)
    return roots


def latest_report(evidence_roots: list[Path], filename: str) -> dict:
    candidates: list[Path] = []
    for root in evidence_roots:
        if not root.exists():
            continue
        try:
            candidates.extend(path for path in root.rglob(filename) if path.is_file())
        except OSError:
            continue
    if not candidates:
        return {
            "found": False,
            "filename": filename,
            "path": None,
            "verdict": None,
            "generated_at": None,
            "summary": {},
            "blockers": [],
            "warnings": [],
        }
    selected = max(candidates, key=report_sort_key)
    payload = read_json(selected)
    summary = payload.get("summary") if isinstance(payload, dict) and isinstance(payload.get("summary"), dict) else {}
    blockers = payload.get("blockers") if isinstance(payload, dict) and isinstance(payload.get("blockers"), list) else []
    warnings = payload.get("warnings") if isinstance(payload, dict) and isinstance(payload.get("warnings"), list) else []
    return {
        "found": payload is not None,
        "filename": filename,
        "path": str(selected),
        "verdict": payload.get("verdict") if payload else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
    }


def compact_report(report: dict) -> dict:
    return {
        "found": report.get("found"),
        "filename": report.get("filename"),
        "path": report.get("path"),
        "verdict": report.get("verdict"),
        "generated_at": report.get("generated_at"),
        "summary": report.get("summary") or {},
    }


def evaluate_row(row: dict, reports: dict[str, dict]) -> dict:
    missing = []
    invalid = []
    limited = []
    accepted = row.get("accepted_verdicts") or {}
    evidence = {}
    for key in row["must_have"]:
        report = reports[key]
        evidence[key] = compact_report(report)
        if not report.get("found"):
            missing.append(key)
            continue
        accepted_verdicts = accepted.get(key)
        if accepted_verdicts and report.get("verdict") not in accepted_verdicts:
            invalid.append({"key": key, "verdict": report.get("verdict"), "accepted_verdicts": accepted_verdicts})
        if str(report.get("verdict") or "").startswith("limited_"):
            limited.append(key)
    for key in row.get("supporting", []):
        evidence[key] = compact_report(reports[key])
    status = "satisfied"
    if missing or invalid:
        status = "missing_or_failed_evidence"
        invalid_keys = {item.get("key") for item in invalid if isinstance(item, dict)}
        self_check_keys = {"evidence_freshness_contract", "objective_traceability_contract"}
        if row.get("id") == "production_blockers_explicit" and not missing and invalid_keys <= self_check_keys:
            status = "limited_evidence"
    elif limited:
        status = "limited_evidence"
    return {
        "id": row["id"],
        "area": row["area"],
        "requirement": row["requirement"],
        "status": status,
        "must_have_reports": row["must_have"],
        "supporting_reports": row.get("supporting", []),
        "missing_reports": missing,
        "invalid_reports": invalid,
        "limited_reports": limited,
        "evidence": evidence,
    }


def collect_blockers(reports: dict[str, dict]) -> list[str]:
    blockers: list[str] = []
    gate = reports.get("production_readiness_gate") or {}
    gate_summary = gate.get("summary") or {}
    for blocker in gate.get("blockers") or []:
        blockers.append(str(blocker))
    for blocker in gate_summary.get("blockers") or []:
        blockers.append(str(blocker))
    if blockers:
        return sorted(dict.fromkeys(blockers))
    runbook = reports.get("production_blocker_runbook_contract") or {}
    runbook_summary = runbook.get("summary") or {}
    for blocker in runbook_summary.get("active_blockers") or runbook.get("blockers") or []:
        blockers.append(str(blocker))
    dependency = reports.get("production_dependency_bundle") or {}
    dependency_summary = dependency.get("summary") or {}
    for blocker in dependency_summary.get("blockers") or dependency.get("blockers") or []:
        blockers.append(str(blocker))
    return sorted(dict.fromkeys(blockers))


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS objective traceability contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "objective_traceability_contract")
    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    report_keys = sorted({key for row in OBJECTIVE_ROWS for key in row["must_have"] + row.get("supporting", [])})
    reports = {key: latest_report(evidence_roots, REPORT_FILENAMES[key]) for key in report_keys}
    rows = [evaluate_row(row, reports) for row in OBJECTIVE_ROWS]
    missing_rows = [row for row in rows if row["status"] == "missing_or_failed_evidence"]
    limited_rows = [row for row in rows if row["status"] == "limited_evidence"]
    blockers = collect_blockers(reports)
    failures = []
    if missing_rows:
        failures.append(f"traceability_rows_missing_or_failed:{len(missing_rows)}")
    if any(key not in REPORT_FILENAMES for key in report_keys):
        failures.append("traceability_report_filename_mapping_incomplete")
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_objective_traceability_contract" if not failures else "failed_ai_nas_objective_traceability_contract",
        "scope": "Requirement-by-requirement traceability from the user objective to current AI-NAS evidence reports and explicit production blockers.",
        "evidence_roots": [str(root) for root in evidence_roots],
        "summary": {
            "objective_row_count": len(rows),
            "satisfied_row_count": sum(1 for row in rows if row["status"] == "satisfied"),
            "limited_row_count": len(limited_rows),
            "missing_or_failed_row_count": len(missing_rows),
            "active_production_blocker_count": len(blockers),
            "active_production_blockers": blockers,
            "failure_count": len(failures),
            "failures": failures,
        },
        "traceability_matrix": rows,
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "download_performed": False,
            "network_call_performed": False,
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON objective traceability reports only",
        },
    }
    json_path = run_dir / "objective_traceability_contract.json"
    md_path = run_dir / "objective_traceability_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Objective Traceability Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- objective_row_count: `{payload['summary']['objective_row_count']}`",
        f"- satisfied_row_count: `{payload['summary']['satisfied_row_count']}`",
        f"- limited_row_count: `{payload['summary']['limited_row_count']}`",
        f"- missing_or_failed_row_count: `{payload['summary']['missing_or_failed_row_count']}`",
        f"- active_production_blocker_count: `{payload['summary']['active_production_blocker_count']}`",
        "- policy: traceability only; no downloads, network calls, service restarts, kills, deletes, moves, overwrites, or Personal source mutation",
        "",
        "## Matrix",
        "",
    ]
    for row in rows:
        lines.append(f"- `{row['id']}` `{row['status']}`: {row['requirement']}")
        if row["missing_reports"]:
            lines.append(f"  - missing: `{', '.join(row['missing_reports'])}`")
        if row["invalid_reports"]:
            invalid = ", ".join(f"{item['key']}={item['verdict']}" for item in row["invalid_reports"])
            lines.append(f"  - invalid: `{invalid}`")
    lines.extend(["", "## Active Production Blockers", ""])
    for blocker in blockers[:80]:
        lines.append(f"- `{blocker}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
