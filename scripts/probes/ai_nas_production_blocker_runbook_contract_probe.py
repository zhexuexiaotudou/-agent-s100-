#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_production_blocker_runbook_contract"


RUNBOOK_ITEMS = [
    {
        "id": "nas_personal_root_mount",
        "owner_category": "index_productization",
        "covers_blockers": [
            "index_productization:personal_root_missing",
            "index_productization:sqlite_index_missing",
            "index_productization:sqlite_index_not_completed",
            "real_nas_acl_user_mapping:personal_root_missing",
            "nas_acl_user_mapping:personal_root_missing",
        ],
        "operator_steps": [
            "Mount the real NAS Personal share at the configured AI-NAS Personal root.",
            "Confirm the OpenClaw runtime user can read Movies, Documents, Photos, and Inbox under that root.",
            "Re-run the index and ACL readiness probes against the mounted root.",
        ],
        "verification_commands": [
            "ai_nas_personal_inventory",
            "ai_nas_index_status",
            "ai_nas_acl_mapping_readiness",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "personal_root exists in production_readiness_gate",
            "SQLite index status is completed",
            "ACL sample entries are present",
        ],
    },
    {
        "id": "production_systemd_index_daemon_install",
        "owner_category": "index_productization",
        "covers_blockers": [
            "index_productization:production_systemd_index_daemon_install_not_verified",
            "index_systemd_daemon_install:systemd_index_daemon_service_not_active",
            "index_systemd_daemon_install:systemd_index_daemon_service_not_enabled",
            "index_systemd_daemon_install:index_daemon_unit_restart_policy_not_verified",
            "index_systemd_daemon_install:index_daemon_observed_cycles_below_threshold",
        ],
        "operator_steps": [
            "Install configs/systemd/ai-nas-index-daemon.service as a system or user service on the appliance.",
            "Enable and start the service during a maintenance window after confirming AI_NAS_PERSONAL_ROOT and AI_NAS_REPORT_ROOT.",
            "Let the service run long enough to record multiple daemon cycles in ai_nas_index_daemon_state.sqlite3.",
            "Verify active/enabled state, Restart policy, and observed cycle count with the install probe.",
        ],
        "verification_commands": [
            "ai_nas_index_systemd_daemon_install",
            "ai_nas_index_status",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "index_systemd_daemon_install verdict is ok",
            "systemd service is active and enabled",
            "daemon state shows the required observed cycles",
            "production readiness gate no longer reports production_systemd_index_daemon_install_not_verified",
        ],
    },
    {
        "id": "production_text_embedding_runtime",
        "owner_category": "search_embedding_and_fuzzy_query",
        "covers_blockers": [
            "search_embedding_and_fuzzy_query:production_text_embedding_smoke_not_ready",
            "search_embedding_and_fuzzy_query:local_hash_embedding_v1_remains_fallback_until_production_model_rows_exist",
            "text_embedding_runtime:sentence_transformers_not_importable",
            "text_embedding_runtime:torch_not_importable",
            "text_embedding_runtime:local_text_embedding_model_dir_not_ready",
            "text_embedding_runtime:production_text_embedding_smoke_not_ready",
        ],
        "operator_steps": [
            "Install sentence-transformers and torch into the OpenClaw Python runtime.",
            "Pre-provision a local sentence-transformer model directory; do not download models during tool execution.",
            "Set the configured text embedding model environment variable for the OpenClaw runtime.",
        ],
        "verification_commands": [
            "ai_nas_embedding_backend_readiness",
            "ai_nas_embedding_runtime_contract",
            "ai_nas_search_confidence_calibration_contract",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "production sentence-transformer smoke is ok",
            "SQLite vector rows remain queryable",
            "semantic query acceptance still returns grounded evidence",
        ],
    },
    {
        "id": "production_image_clip_runtime",
        "owner_category": "photo_exif_phash_clip_path",
        "covers_blockers": [
            "search_embedding_and_fuzzy_query:production_image_clip_smoke_not_ready",
            "photo_exif_phash_clip_path:production_clip_runtime_not_ready",
            "photo_exif_phash_clip_path:photo_semantics_remain_exif_phash_pil_fallback_until_production_clip_ready",
            "image_clip_runtime:torch_not_importable",
            "image_clip_runtime:clip_or_transformers_runtime_not_importable",
            "image_clip_runtime:local_image_clip_model_dir_not_ready",
            "image_clip_runtime:production_image_clip_smoke_not_ready",
        ],
        "operator_steps": [
            "Install a CLIP-capable local runtime such as transformers, clip, or open_clip plus torch.",
            "Pre-provision a local image model directory and configure the runtime path.",
            "Keep face recognition disabled until a separate privacy review approves it.",
        ],
        "verification_commands": [
            "ai_nas_embedding_backend_readiness",
            "ai_nas_embedding_runtime_contract",
            "ai_nas_photo_pipeline_acceptance",
            "ai_nas_photo_privacy_governance",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "production image CLIP smoke is ok",
            "photo semantic search remains grounded",
            "privacy governance still reports no face recognition",
        ],
    },
    {
        "id": "production_ocr_runtime",
        "owner_category": "document_pdf_ocr_folder_rag",
        "covers_blockers": [
            "document_pdf_ocr_folder_rag:production_ocr_runtime_not_ready",
            "document_pdf_ocr_folder_rag:scanned_content_must_remain_explicitly_blocked_when_ocr_runtime_missing",
            "ocr_runtime:tesseract_cli_not_found",
            "ocr_runtime:pytesseract_not_importable",
            "ocr_runtime:production_ocr_runtime_not_ready",
        ],
        "operator_steps": [
            "Install Tesseract OCR and make the CLI discoverable on PATH.",
            "Install pytesseract into the OpenClaw Python runtime.",
            "Keep scanned files explicitly blocked or failed until OCR smoke passes; never invent extracted text.",
        ],
        "verification_commands": [
            "ai_nas_ocr_runtime_contract",
            "ai_nas_ocr_extract",
            "ai_nas_document_pipeline_acceptance",
            "ai_nas_folder_rag_grounding_contract",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "OCR runtime contract is ok",
            "scanned PDF/image OCR rows are completed or explicitly failed",
            "folder RAG still has no-answer behavior for unsupported facts",
        ],
    },
    {
        "id": "nas_acl_identity_mapping",
        "owner_category": "real_nas_acl_user_mapping",
        "covers_blockers": [
            "real_nas_acl_user_mapping:no_acl_sample_entries",
            "nas_acl_user_mapping:no_acl_sample_entries",
            "nas_acl_user_mapping:principal_mapping_config_missing",
            "real_nas_acl_user_mapping:windows_local_dev_cannot_verify_linux_nas_posix_acl",
        ],
        "operator_steps": [
            "Install or expose ACL and identity tooling such as getfacl, id, getent, and SMB mapping utilities.",
            "Provide a principal-to-NAS-user/group mapping config for admin, family, accountant, guest, and child roles.",
            "Re-run permission-aware search and ACL mapping readiness against the real NAS mount.",
        ],
        "verification_commands": [
            "ai_nas_acl_mapping_readiness",
            "ai_nas_permission_aware_search",
            "ai_nas_production_dependency_bundle",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "ACL sample entries are readable",
            "principal mapping config is present",
            "permission-aware search denies/redacts forbidden evidence",
        ],
    },
    {
        "id": "production_nas_backed_long_soak",
        "owner_category": "p95_p99_queue_throughput",
        "covers_blockers": [
            "p95_p99_queue_throughput:production_nas_backed_long_soak_not_verified",
            "nas_backed_long_soak:personal_root_missing",
            "nas_backed_long_soak:personal_root_not_nas_backed",
            "nas_backed_long_soak:duration_below_production_minimum",
            "nas_backed_long_soak:file_count_below_production_minimum",
            "nas_backed_long_soak:index_failed_files_present",
            "nas_backed_long_soak:task_p95_slo_missed",
            "nas_backed_long_soak:task_p99_slo_missed",
            "p95_p99_queue_throughput:operational_slo_rollup_contract_verdict_not_ok_ai_nas_operational_slo_rollup_contract",
        ],
        "operator_steps": [
            "Run ai_nas_nas_backed_long_soak against the real mounted NAS Personal root, not a fixture directory.",
            "Use the production minimum duration and file-count thresholds, and keep source data read-only.",
            "Attach the generated NAS-backed soak report before claiming production P95/P99 readiness.",
        ],
        "verification_commands": [
            "ai_nas_nas_backed_long_soak",
            "ai_nas_operational_slo_rollup_contract",
            "ai_nas_evidence_freshness_contract",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "nas_backed_long_soak verdict is ok",
            "Personal root is NAS-backed",
            "elapsed duration and file count meet production thresholds",
            "production readiness gate no longer reports production_nas_backed_long_soak_not_verified",
        ],
    },
    {
        "id": "model_openclaw_health_and_systemd",
        "owner_category": "model_service_crash_recovery",
        "covers_blockers": [
            "model_service_crash_recovery:no_model_or_openclaw_health_endpoint_ok",
            "model_service_crash_recovery:no_systemd_user_service_active",
            "model_service_crash_recovery:no_systemd_service_active",
            "model_service_crash_recovery:restart_policy_not_verified",
            "model_openclaw_service_recovery:no_model_or_openclaw_health_endpoint_ok",
            "model_openclaw_service_recovery:no_systemd_user_service_active",
            "model_openclaw_service_recovery:no_systemd_service_active",
            "model_openclaw_service_recovery:restart_policy_not_verified",
            "model_service_crash_recovery:operator_approved_real_service_kill_restart_drill_not_verified",
        ],
        "operator_steps": [
            "Expose local health endpoints for the model gateway and OpenClaw gateway.",
            "Run the model queue and OpenClaw gateway under systemd user or system services with Restart policy.",
            "Perform an operator-approved kill/restart drill and attach the recovery manifest plus post-check report.",
        ],
        "verification_commands": [
            "ai_nas_model_service_resilience",
            "ai_nas_model_service_recovery_manifest",
            "ai_nas_model_service_recovery_drill",
            "ai_nas_model_service_real_recovery_drill",
            "ai_nas_production_dependency_bundle",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "model/OpenClaw health endpoints return ok",
            "systemd user or system service is active/enabled",
            "Restart policy is parsed from a real unit file",
            "operator-approved real service recovery drill is recorded",
        ],
    },
    {
        "id": "evidence_freshness_and_traceability",
        "owner_category": "evidence_freshness_and_provenance",
        "covers_blockers": [
            "production_dependency_evidence_bundle:production_blocker_runbook_contract_verdict_not_ok_ai_nas_production_blocker_runbook_contract",
            "evidence_freshness_and_provenance:evidence_freshness_contract_report_missing",
            "evidence_freshness_and_provenance:evidence_freshness_contract_verdict_not_ok_ai_nas_evidence_freshness_contract",
            "evidence_freshness_and_provenance:objective_traceability_contract_verdict_not_ok_ai_nas_objective_traceability_contract",
            "evidence_freshness_and_provenance:evidence_catalog_contract_report_missing",
            "evidence_freshness_and_provenance:objective_traceability_contract_report_missing",
        ],
        "operator_steps": [
            "Regenerate the production dependency bundle, blocker runbook, evidence catalog, freshness, objective traceability, and production gate reports in that order.",
            "Confirm every required report is fresh, attributable to the expected tool ID, and free of forbidden destructive audit flags.",
            "Treat remaining limited production blockers as deployment work, not as proof of production readiness.",
        ],
        "verification_commands": [
            "ai_nas_production_dependency_bundle",
            "ai_nas_production_blocker_runbook_contract",
            "ai_nas_evidence_catalog_contract",
            "ai_nas_evidence_freshness_contract",
            "ai_nas_objective_traceability_contract",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "evidence catalog covers every canonical allowlisted tool",
            "freshness contract has no missing or invalid required reports",
            "objective traceability rows are satisfied or explicitly limited only by external production blockers",
        ],
    },
    {
        "id": "acceptance_evidence_regeneration",
        "owner_category": "evidence_freshness_and_provenance",
        "covers_blockers": [
            "index_productization:index_daemon_resident_report_missing",
            "index_productization:index_rename_detection_report_missing",
            "index_productization:index_observability_contract_report_missing",
            "index_productization:sqlite_index_integrity_contract_report_missing",
            "index_productization:incremental_scan_efficiency_contract_report_missing",
            "p95_p99_queue_throughput:continuous_task_soak_report_missing",
            "p95_p99_queue_throughput:soak_checkpoint_resume_report_missing",
            "p95_p99_queue_throughput:queue_backpressure_slo_report_missing",
            "p95_p99_queue_throughput:index_search_isolation_slo_report_missing",
            "p95_p99_queue_throughput:user_facing_tail_latency_report_missing",
            "p95_p99_queue_throughput:bpu_headroom_slo_report_missing",
            "p95_p99_queue_throughput:operational_slo_rollup_contract_report_missing",
            "search_embedding_and_fuzzy_query:semantic_query_acceptance_report_missing",
            "search_embedding_and_fuzzy_query:appliance_experience_acceptance_report_missing",
            "search_embedding_and_fuzzy_query:operator_portal_contract_report_missing",
            "search_embedding_and_fuzzy_query:search_evidence_contract_report_missing",
            "search_embedding_and_fuzzy_query:search_confidence_calibration_contract_report_missing",
            "search_embedding_and_fuzzy_query:multimodal_intent_routing_contract_report_missing",
            "document_pdf_ocr_folder_rag:document_pipeline_acceptance_report_missing",
            "document_pdf_ocr_folder_rag:folder_rag_grounding_contract_report_missing",
            "photo_exif_phash_clip_path:photo_pipeline_acceptance_report_missing",
            "model_service_crash_recovery:model_service_recovery_drill_report_missing",
            "production_dependency_evidence_bundle:production_dependency_bundle_report_missing",
            "production_dependency_evidence_bundle:production_blocker_runbook_contract_report_missing",
            "portable_nas_adapter_contract:portable_nas_adapter_contract_report_missing",
            "openclaw_tool_governance:destructive_action_governance_report_missing",
            "openclaw_tool_governance:action_manifest_integrity_report_missing",
            "openclaw_tool_governance:operator_approval_inbox_report_missing",
            "openclaw_tool_governance:audit_trail_contract_report_missing",
        ],
        "operator_steps": [
            "Regenerate the missing acceptance reports with the canonical ai_nas_* tools before interpreting the latest production gate.",
            "Run fixture-bounded reports separately from production-only reports; do not use fixture evidence to clear NAS/systemd/runtime production warnings.",
            "Re-run evidence catalog, freshness, objective traceability, production blocker runbook, and production readiness gate after the evidence set is regenerated.",
        ],
        "verification_commands": [
            "ai_nas_index_daemon_resident",
            "ai_nas_index_rename_detection",
            "ai_nas_index_observability_contract",
            "ai_nas_sqlite_index_integrity_contract",
            "ai_nas_incremental_scan_efficiency_contract",
            "ai_nas_continuous_task_soak",
            "ai_nas_soak_checkpoint_resume",
            "ai_nas_queue_backpressure_slo",
            "ai_nas_index_search_isolation_slo",
            "ai_nas_user_facing_tail_latency",
            "ai_nas_bpu_headroom_slo",
            "ai_nas_operational_slo_rollup_contract",
            "ai_nas_semantic_query_acceptance",
            "ai_nas_search_evidence_contract",
            "ai_nas_search_confidence_calibration_contract",
            "ai_nas_multimodal_intent_routing_contract",
            "ai_nas_document_pipeline_acceptance",
            "ai_nas_folder_rag_grounding_contract",
            "ai_nas_photo_pipeline_acceptance",
            "ai_nas_model_service_recovery_drill",
            "ai_nas_production_dependency_bundle",
            "ai_nas_portable_nas_adapter_contract",
            "ai_nas_destructive_action_governance",
            "ai_nas_action_manifest_integrity",
            "ai_nas_operator_approval_inbox",
            "ai_nas_audit_trail_contract",
            "ai_nas_evidence_catalog_contract",
            "ai_nas_evidence_freshness_contract",
            "ai_nas_objective_traceability_contract",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "latest production readiness gate no longer contains report_missing blockers for regenerated reports",
            "evidence freshness contract accepts the regenerated reports",
            "objective traceability rows move from missing_or_failed to satisfied or explicitly limited by true production blockers",
        ],
    },
    {
        "id": "photo_face_privacy_review",
        "owner_category": "photo_exif_phash_clip_path",
        "covers_blockers": [
            "photo_exif_phash_clip_path:face_recognition_remains_out_of_scope_until_privacy_review",
        ],
        "operator_steps": [
            "Keep face recognition, face embeddings, person identity matching, and child identity inference disabled in production.",
            "If face/person recognition is proposed later, complete a separate privacy, consent, retention, and compliance review before changing the scope.",
            "Re-run photo privacy governance after any future privacy-approved face model integration.",
        ],
        "verification_commands": [
            "ai_nas_photo_privacy_governance",
            "ai_nas_photo_pipeline_acceptance",
            "ai_nas_production_readiness_gate",
        ],
        "acceptance_evidence": [
            "photo privacy governance reports face_recognition_performed false",
            "production readiness gate preserves the privacy warning until a separate approved face-recognition scope exists",
            "no face embedding or identity matching audit flags are present",
        ],
    },
]


CURRENT_GATE_BLOCKERS = [
    "index_productization:personal_root_missing",
    "search_embedding_and_fuzzy_query:production_text_embedding_smoke_not_ready",
    "search_embedding_and_fuzzy_query:production_image_clip_smoke_not_ready",
    "document_pdf_ocr_folder_rag:production_ocr_runtime_not_ready",
    "photo_exif_phash_clip_path:production_clip_runtime_not_ready",
    "real_nas_acl_user_mapping:personal_root_missing",
    "real_nas_acl_user_mapping:no_acl_sample_entries",
    "model_service_crash_recovery:no_model_or_openclaw_health_endpoint_ok",
    "model_service_crash_recovery:no_systemd_service_active",
]


CURRENT_GATE_WARNINGS = [
    "index_productization:production_systemd_index_daemon_install_not_verified",
    "p95_p99_queue_throughput:production_nas_backed_long_soak_not_verified",
    "search_embedding_and_fuzzy_query:local_hash_embedding_v1_remains_fallback_until_production_model_rows_exist",
    "document_pdf_ocr_folder_rag:scanned_content_must_remain_explicitly_blocked_when_ocr_runtime_missing",
    "photo_exif_phash_clip_path:photo_semantics_remain_exif_phash_pil_fallback_until_production_clip_ready",
    "model_service_crash_recovery:operator_approved_real_service_kill_restart_drill_not_verified",
]


def parse_report_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path)
    generated_at = parse_report_time(payload.get("generated_at") if payload else None)
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
    candidates = []
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
            "path": None,
            "verdict": None,
            "generated_at": None,
            "selection_policy": "generated_at_then_mtime",
            "payload": None,
        }
    selected = max(candidates, key=report_sort_key)
    payload = read_json(selected)
    return {
        "found": payload is not None,
        "path": str(selected),
        "verdict": payload.get("verdict") if payload else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "selection_policy": "generated_at_then_mtime",
        "payload": payload,
    }


def gate_findings_from_report(gate_report: dict) -> tuple[list[str], str]:
    payload = gate_report.get("payload") or {}
    blockers = payload.get("blockers")
    warnings = payload.get("warnings")
    findings = []
    if isinstance(blockers, list):
        findings.extend(str(blocker) for blocker in blockers)
    if isinstance(warnings, list):
        findings.extend(str(warning) for warning in warnings)
    if findings:
        return list(dict.fromkeys(findings)), "latest_production_readiness_gate"
    return CURRENT_GATE_BLOCKERS + CURRENT_GATE_WARNINGS, "fallback_current_gate_findings"


def validate_runbook(items: list[dict], required_blockers: list[str]) -> tuple[list[str], dict]:
    failures = []
    coverage = {}
    for item in items:
        item_id = item.get("id", "unknown")
        if not item.get("owner_category"):
            failures.append(f"{item_id}:missing_owner_category")
        if not item.get("covers_blockers"):
            failures.append(f"{item_id}:missing_covers_blockers")
        if len(item.get("operator_steps") or []) < 2:
            failures.append(f"{item_id}:operator_steps_lt_2")
        if not item.get("verification_commands"):
            failures.append(f"{item_id}:missing_verification_commands")
        if not item.get("acceptance_evidence"):
            failures.append(f"{item_id}:missing_acceptance_evidence")
        for command in item.get("verification_commands") or []:
            if not str(command).startswith("ai_nas_"):
                failures.append(f"{item_id}:verification_command_not_ai_nas:{command}")
        for blocker in item.get("covers_blockers") or []:
            coverage.setdefault(blocker, []).append(item_id)
    for blocker in required_blockers:
        if blocker not in coverage:
            failures.append(f"required_blocker_uncovered:{blocker}")
    return failures, coverage


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS production blocker runbook contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "production_blocker_runbook_contract")
    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    gate_report = latest_report(evidence_roots, "production_readiness_gate.json")
    required_findings, blocker_source = gate_findings_from_report(gate_report)
    failures, coverage = validate_runbook(RUNBOOK_ITEMS, required_findings)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_production_blocker_runbook_contract" if not failures else "failed_ai_nas_production_blocker_runbook_contract",
        "scope": "operator-facing runbook contract mapping production readiness blockers/warnings to owner, remediation, verification, and acceptance evidence",
        "blocker_source": blocker_source,
        "required_blockers": required_findings,
        "current_gate_blockers_baseline": CURRENT_GATE_BLOCKERS,
        "current_gate_warnings_baseline": CURRENT_GATE_WARNINGS,
        "production_readiness_gate_report": {key: value for key, value in gate_report.items() if key != "payload"},
        "runbook_items": RUNBOOK_ITEMS,
        "coverage": coverage,
        "summary": {
            "runbook_item_count": len(RUNBOOK_ITEMS),
            "required_blocker_count": len(required_findings),
            "covered_required_blocker_count": sum(1 for blocker in required_findings if blocker in coverage),
            "verification_command_count": sum(len(item["verification_commands"]) for item in RUNBOOK_ITEMS),
            "all_required_blockers_covered": all(blocker in coverage for blocker in required_findings),
            "failures": failures,
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
            "writes": "Markdown/JSON production blocker runbook reports only",
        },
    }
    json_path = run_dir / "production_blocker_runbook_contract.json"
    md_path = run_dir / "production_blocker_runbook_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Production Blocker Runbook Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- blocker_source: `{payload['blocker_source']}`",
        f"- production_readiness_gate_report: `{payload['production_readiness_gate_report']}`",
        f"- runbook_item_count: `{payload['summary']['runbook_item_count']}`",
        f"- required_blocker_count: `{payload['summary']['required_blocker_count']}`",
        f"- covered_required_blocker_count: `{payload['summary']['covered_required_blocker_count']}`",
        f"- verification_command_count: `{payload['summary']['verification_command_count']}`",
        f"- all_required_blockers_covered: `{payload['summary']['all_required_blockers_covered']}`",
        f"- failures: `{failures}`",
        "",
        "## Runbook Items",
        "",
    ]
    for item in RUNBOOK_ITEMS:
        lines.append(f"### {item['id']}")
        lines.append("")
        lines.append(f"- owner_category: `{item['owner_category']}`")
        lines.append(f"- covers_blockers: `{item['covers_blockers']}`")
        lines.append("- operator_steps:")
        for step in item["operator_steps"]:
            lines.append(f"  - {step}")
        lines.append("- verification_commands:")
        for command in item["verification_commands"]:
            lines.append(f"  - `{command}`")
        lines.append("- acceptance_evidence:")
        for evidence in item["acceptance_evidence"]:
            lines.append(f"  - {evidence}")
        lines.append("")
    lines.extend(["## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
