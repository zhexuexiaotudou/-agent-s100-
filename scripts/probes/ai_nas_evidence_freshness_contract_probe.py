#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_evidence_freshness_contract"

REQUIRED_REPORTS = [
    {
        "key": "index_daemon_resident",
        "filename": "index_daemon_resident.json",
        "tool_id": "ai_nas_index_daemon_resident",
        "accepted_verdicts": ["ok_ai_nas_index_daemon_resident"],
    },
    {
        "key": "index_systemd_daemon_install",
        "filename": "index_systemd_daemon_install.json",
        "tool_id": "ai_nas_index_systemd_daemon_install",
        "accepted_verdicts": ["ok_ai_nas_index_systemd_daemon_install"],
    },
    {
        "key": "index_rename_detection",
        "filename": "index_rename_detection.json",
        "tool_id": "ai_nas_index_rename_detection",
        "accepted_verdicts": ["ok_ai_nas_index_rename_detection"],
    },
    {
        "key": "index_observability_contract",
        "filename": "index_observability_contract.json",
        "tool_id": "ai_nas_index_observability_contract",
        "accepted_verdicts": ["ok_ai_nas_index_observability_contract"],
    },
    {
        "key": "sqlite_index_integrity_contract",
        "filename": "sqlite_index_integrity_contract.json",
        "tool_id": "ai_nas_sqlite_index_integrity_contract",
        "accepted_verdicts": ["ok_ai_nas_sqlite_index_integrity_contract"],
    },
    {
        "key": "incremental_scan_efficiency_contract",
        "filename": "incremental_scan_efficiency_contract.json",
        "tool_id": "ai_nas_incremental_scan_efficiency_contract",
        "accepted_verdicts": ["ok_ai_nas_incremental_scan_efficiency_contract"],
    },
    {
        "key": "continuous_task_soak",
        "filename": "continuous_task_soak.json",
        "tool_id": "ai_nas_continuous_task_soak",
        "accepted_verdicts": ["ok_ai_nas_continuous_task_soak"],
    },
    {
        "key": "nas_backed_long_soak",
        "filename": "nas_backed_long_soak.json",
        "tool_id": "ai_nas_nas_backed_long_soak",
        "accepted_verdicts": ["ok_ai_nas_nas_backed_long_soak"],
    },
    {
        "key": "soak_checkpoint_resume",
        "filename": "soak_checkpoint_resume.json",
        "tool_id": "ai_nas_soak_checkpoint_resume",
        "accepted_verdicts": ["ok_ai_nas_soak_checkpoint_resume"],
    },
    {
        "key": "queue_backpressure_slo",
        "filename": "queue_backpressure_slo.json",
        "tool_id": "ai_nas_queue_backpressure_slo",
        "accepted_verdicts": ["ok_ai_nas_queue_backpressure_slo"],
    },
    {
        "key": "index_search_isolation_slo",
        "filename": "index_search_isolation_slo.json",
        "tool_id": "ai_nas_index_search_isolation_slo",
        "accepted_verdicts": ["ok_ai_nas_index_search_isolation_slo"],
    },
    {
        "key": "user_facing_tail_latency",
        "filename": "user_facing_tail_latency.json",
        "tool_id": "ai_nas_user_facing_tail_latency",
        "accepted_verdicts": ["ok_ai_nas_user_facing_tail_latency"],
    },
    {
        "key": "bpu_headroom_slo",
        "filename": "bpu_headroom_slo.json",
        "tool_id": "ai_nas_bpu_headroom_slo",
        "accepted_verdicts": ["ok_ai_nas_bpu_headroom_slo"],
    },
    {
        "key": "operational_slo_rollup_contract",
        "filename": "operational_slo_rollup_contract.json",
        "tool_id": "ai_nas_operational_slo_rollup_contract",
        "accepted_verdicts": ["ok_ai_nas_operational_slo_rollup_contract"],
    },
    {
        "key": "semantic_query_acceptance",
        "filename": "semantic_query_acceptance.json",
        "tool_id": "ai_nas_semantic_query_acceptance",
        "accepted_verdicts": ["ok_ai_nas_semantic_query_acceptance"],
    },
    {
        "key": "appliance_experience_acceptance",
        "filename": "appliance_experience_acceptance.json",
        "tool_id": "ai_nas_appliance_experience_acceptance",
        "accepted_verdicts": ["ok_ai_nas_appliance_experience_acceptance"],
    },
    {
        "key": "operator_portal_contract",
        "filename": "operator_portal_contract.json",
        "tool_id": "ai_nas_operator_portal_contract",
        "accepted_verdicts": ["ok_ai_nas_operator_portal_contract"],
    },
    {
        "key": "search_evidence_contract",
        "filename": "search_evidence_contract.json",
        "tool_id": "ai_nas_search_evidence_contract",
        "accepted_verdicts": ["ok_ai_nas_search_evidence_contract"],
    },
    {
        "key": "search_confidence_calibration_contract",
        "filename": "search_confidence_calibration_contract.json",
        "tool_id": "ai_nas_search_confidence_calibration_contract",
        "accepted_verdicts": ["ok_ai_nas_search_confidence_calibration_contract"],
    },
    {
        "key": "multimodal_intent_routing_contract",
        "filename": "multimodal_intent_routing_contract.json",
        "tool_id": "ai_nas_multimodal_intent_routing_contract",
        "accepted_verdicts": ["ok_ai_nas_multimodal_intent_routing_contract"],
    },
    {
        "key": "embedding_runtime_contract",
        "filename": "embedding_runtime_contract.json",
        "tool_id": "ai_nas_embedding_runtime_contract",
        "accepted_verdicts": ["ok_ai_nas_embedding_runtime_contract", "limited_ai_nas_embedding_runtime_contract"],
    },
    {
        "key": "embedding_backend_readiness",
        "filename": "embedding_backend_readiness.json",
        "tool_id": "ai_nas_embedding_backend_readiness",
        "accepted_verdicts": ["ok_ai_nas_embedding_backend_readiness", "limited_ai_nas_embedding_backend_readiness"],
    },
    {
        "key": "document_pipeline_acceptance",
        "filename": "document_pipeline_acceptance.json",
        "tool_id": "ai_nas_document_pipeline_acceptance",
        "accepted_verdicts": ["ok_ai_nas_document_pipeline_acceptance"],
    },
    {
        "key": "folder_rag_grounding_contract",
        "filename": "folder_rag_grounding_contract.json",
        "tool_id": "ai_nas_folder_rag_grounding_contract",
        "accepted_verdicts": ["ok_ai_nas_folder_rag_grounding_contract"],
    },
    {
        "key": "ocr_runtime_contract",
        "filename": "ocr_runtime_contract.json",
        "tool_id": "ai_nas_ocr_runtime_contract",
        "accepted_verdicts": ["ok_ai_nas_ocr_runtime_contract", "limited_ai_nas_ocr_runtime_contract"],
    },
    {
        "key": "photo_pipeline_acceptance",
        "filename": "photo_pipeline_acceptance.json",
        "tool_id": "ai_nas_photo_pipeline_acceptance",
        "accepted_verdicts": ["ok_ai_nas_photo_pipeline_acceptance"],
    },
    {
        "key": "photo_privacy_governance",
        "filename": "photo_privacy_governance.json",
        "tool_id": "ai_nas_photo_privacy_governance",
        "accepted_verdicts": ["ok_ai_nas_photo_privacy_governance"],
    },
    {
        "key": "model_service_recovery_drill",
        "filename": "model_service_recovery_drill.json",
        "tool_id": "ai_nas_model_service_recovery_drill",
        "accepted_verdicts": ["ok_model_service_recovery_drill"],
    },
    {
        "key": "model_service_recovery_manifest",
        "filename": "model_service_recovery_manifest.json",
        "tool_id": "ai_nas_model_service_recovery_manifest",
        "accepted_verdicts": ["ok_ai_nas_model_service_recovery_manifest"],
    },
    {
        "key": "model_service_real_recovery_drill",
        "filename": "model_service_real_recovery_drill.json",
        "tool_id": "ai_nas_model_service_real_recovery_drill",
        "accepted_verdicts": ["ok_ai_nas_model_service_real_recovery_drill"],
    },
    {
        "key": "production_dependency_bundle",
        "filename": "production_dependency_bundle.json",
        "tool_id": "ai_nas_production_dependency_bundle",
        "accepted_verdicts": ["ok_ai_nas_production_dependency_bundle", "limited_ai_nas_production_dependency_bundle"],
    },
    {
        "key": "production_blocker_runbook_contract",
        "filename": "production_blocker_runbook_contract.json",
        "tool_id": "ai_nas_production_blocker_runbook_contract",
        "accepted_verdicts": ["ok_ai_nas_production_blocker_runbook_contract"],
    },
    {
        "key": "evidence_catalog_contract",
        "filename": "evidence_catalog_contract.json",
        "tool_id": "ai_nas_evidence_catalog_contract",
        "accepted_verdicts": ["ok_ai_nas_evidence_catalog_contract"],
    },
    {
        "key": "objective_traceability_contract",
        "filename": "objective_traceability_contract.json",
        "tool_id": "ai_nas_objective_traceability_contract",
        "accepted_verdicts": ["ok_ai_nas_objective_traceability_contract"],
    },
    {
        "key": "portable_nas_adapter_contract",
        "filename": "portable_nas_adapter_contract.json",
        "tool_id": "ai_nas_portable_nas_adapter_contract",
        "accepted_verdicts": ["ok_ai_nas_portable_nas_adapter_contract"],
    },
    {
        "key": "destructive_action_governance",
        "filename": "destructive_action_governance.json",
        "tool_id": "ai_nas_destructive_action_governance",
        "accepted_verdicts": ["ok_ai_nas_destructive_action_governance"],
    },
    {
        "key": "action_manifest_integrity",
        "filename": "action_manifest_integrity.json",
        "tool_id": "ai_nas_action_manifest_integrity",
        "accepted_verdicts": ["ok_ai_nas_action_manifest_integrity"],
    },
    {
        "key": "operator_approval_inbox",
        "filename": "operator_approval_inbox.json",
        "tool_id": "ai_nas_operator_approval_inbox",
        "accepted_verdicts": ["ok_ai_nas_operator_approval_inbox"],
    },
    {
        "key": "audit_trail_contract",
        "filename": "audit_trail_contract_report.json",
        "tool_id": "ai_nas_audit_trail_contract",
        "accepted_verdicts": ["ok_ai_nas_audit_trail_contract"],
    },
]


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [report_root]
    tmp = Path("tmp")
    if tmp.exists():
        roots.append(tmp)
    return roots


def find_latest(evidence_roots: list[Path], filename: str) -> Path | None:
    candidates: list[tuple[float, float, str, Path]] = []
    for root in evidence_roots:
        if root.exists():
            for path in root.rglob(filename):
                payload = read_json(path) or {}
                generated_at = parse_time(payload.get("generated_at"))
                generated_ts = generated_at.timestamp() if generated_at else 0.0
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                candidates.append((generated_ts, mtime, str(path), path))
    if not candidates:
        return None
    return max(candidates)[3]


def audit_flags(payload: dict) -> tuple[list[str], list[str]]:
    audit = payload.get("audit") or {}
    blockers = []
    warnings = []
    bad_true_flags = [
        "personal_source_modified",
        "download_performed",
        "service_restart_performed",
        "kill_performed",
        "delete_performed",
        "move_performed",
        "overwrite_performed",
        "face_recognition_performed",
        "permission_change_performed",
    ]
    for flag in bad_true_flags:
        if audit.get(flag) is True:
            blockers.append(f"audit_forbidden_flag_true:{flag}")
    if not audit:
        warnings.append("audit_object_missing")
    return blockers, warnings


def evaluate_report(spec: dict, evidence_roots: list[Path], max_age_days: int, now: datetime) -> dict:
    path = find_latest(evidence_roots, spec["filename"])
    if not path:
        return {
            "key": spec["key"],
            "filename": spec["filename"],
            "found": False,
            "fresh": False,
            "valid": False,
            "blockers": ["report_missing"],
            "warnings": [],
        }
    payload = read_json(path) or {}
    generated_at = parse_time(payload.get("generated_at"))
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=now.tzinfo)
    evidence_time = generated_at or mtime
    age = now - evidence_time
    blockers = []
    warnings = []
    if not payload:
        blockers.append("json_payload_unreadable")
    if generated_at is None:
        warnings.append("generated_at_missing_or_invalid_using_file_mtime")
    if payload.get("tool_id") and payload.get("tool_id") != spec["tool_id"]:
        blockers.append(f"tool_id_mismatch:{payload.get('tool_id')}")
    elif not payload.get("tool_id"):
        warnings.append("tool_id_missing")
    if payload.get("verdict") not in spec["accepted_verdicts"]:
        blockers.append(f"verdict_not_accepted:{payload.get('verdict')}")
    if age > timedelta(days=max_age_days):
        blockers.append(f"evidence_older_than_{max_age_days}_days")
    audit_blockers, audit_warnings = audit_flags(payload)
    blockers.extend(audit_blockers)
    warnings.extend(audit_warnings)
    return {
        "key": spec["key"],
        "filename": spec["filename"],
        "found": True,
        "path": str(path),
        "generated_at": payload.get("generated_at"),
        "file_mtime": mtime.isoformat(),
        "age_seconds": round(age.total_seconds(), 3),
        "fresh": age <= timedelta(days=max_age_days),
        "valid": not blockers,
        "tool_id": payload.get("tool_id"),
        "verdict": payload.get("verdict"),
        "accepted_verdicts": spec["accepted_verdicts"],
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS production evidence freshness and provenance contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    parser.add_argument("--max-age-days", type=int, default=30)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).astimezone()
    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    reports = [
        evaluate_report(spec, evidence_roots, args.max_age_days, now)
        for spec in REQUIRED_REPORTS
    ]
    blockers = [
        f"{report['key']}:{blocker}"
        for report in reports
        for blocker in report["blockers"]
    ]
    warnings = [
        f"{report['key']}:{warning}"
        for report in reports
        for warning in report["warnings"]
    ]
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_evidence_freshness_contract" if not blockers else "limited_ai_nas_evidence_freshness_contract",
        "scope": "read-only freshness and provenance contract for AI-NAS production-readiness evidence",
        "max_age_days": args.max_age_days,
        "evidence_roots": [str(root) for root in evidence_roots],
        "reports": reports,
        "summary": {
            "required_report_count": len(REQUIRED_REPORTS),
            "found_count": sum(1 for report in reports if report["found"]),
            "fresh_count": sum(1 for report in reports if report["fresh"]),
            "valid_count": sum(1 for report in reports if report["valid"]),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "blockers": blockers,
            "warnings": warnings,
        },
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
            "writes": "Markdown/JSON evidence freshness contract report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "evidence_freshness_contract")
    json_path = run_dir / "evidence_freshness_contract.json"
    md_path = run_dir / "evidence_freshness_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Evidence Freshness Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- max_age_days: `{args.max_age_days}`",
        f"- required_report_count: `{payload['summary']['required_report_count']}`",
        f"- found_count: `{payload['summary']['found_count']}`",
        f"- valid_count: `{payload['summary']['valid_count']}`",
        f"- blocker_count: `{payload['summary']['blocker_count']}`",
        f"- warning_count: `{payload['summary']['warning_count']}`",
        "- policy: read-only evidence scan; no services, downloads, source edits, deletes, moves, or overwrites",
        "",
        "## Reports",
        "",
    ]
    for report in reports:
        lines.append(
            f"- {report['key']}: found `{report['found']}` fresh `{report['fresh']}` "
            f"valid `{report['valid']}` verdict `{report.get('verdict')}` blockers `{report['blockers']}`"
        )
    lines.extend(["", "## Warnings", ""])
    if not warnings:
        lines.append("- No evidence freshness warning detected.")
    for warning in warnings:
        lines.append(f"- {warning}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
