#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ai_nas_acl_mapping_readiness_probe import (
    DEFAULT_MAPPING_CONFIGS,
    evaluate_readiness as evaluate_acl_readiness,
    mapping_configs,
    sample_entries,
    tool_paths,
)
from ai_nas_allowlist_governance_audit_probe import audit_tool, default_deploy_root, default_source_root, load_json, text_or_empty
from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_report_dir,
    image_embedding_runtime_status,
    iso_now,
    ocr_engine_status,
    safe_write_json,
    safe_write_text,
    sqlite_index_status,
)
from ai_nas_embedding_backend_readiness_probe import (
    IMAGE_MODEL_ENV,
    TEXT_MODEL_ENV,
    configured_image_model_dir,
    configured_text_model_dir,
    model_dir_status,
    module_status,
    try_clip_smoke,
    try_sentence_transformer_smoke,
)
from ai_nas_model_service_resilience_probe import (
    DEFAULT_HEALTH_URLS,
    DEFAULT_SERVICES,
    candidate_unit_paths,
    check_health_url,
    parse_unit_file,
    run_command,
)


TOOL_ID = "ai_nas_production_readiness_gate"
MIN_AI_NAS_TOOL_COUNT = 66
MIN_PRODUCTION_NAS_SOAK_SECONDS = 21600.0
MIN_PRODUCTION_NAS_SOAK_FILE_COUNT = 100


def default_gate_deploy_root() -> Path:
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "scripts" / "tool_allowlist.json").exists():
        return candidate
    return default_deploy_root()


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_report_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path) or {}
    generated_at = parse_report_time(payload.get("generated_at"))
    generated_ts = generated_at.timestamp() if generated_at else 0.0
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (generated_ts, mtime, str(path))


def latest_report(evidence_roots: list[Path], filename: str) -> dict:
    candidates: list[Path] = []
    for root in evidence_roots:
        if not root.exists():
            continue
        candidates.extend(root.rglob(filename))
    if not candidates:
        return {"found": False, "filename": filename}
    latest = max(candidates, key=report_sort_key)
    payload = read_json(latest) or {}
    return {
        "found": True,
        "path": str(latest),
        "verdict": payload.get("verdict"),
        "generated_at": payload.get("generated_at"),
        "selection_policy": "generated_at_then_mtime",
        "payload": payload,
    }


def ok_verdict(report: dict, expected: str) -> bool:
    return bool(report.get("found") and report.get("verdict") == expected)


def report_blocker(report: dict, label: str, expected: str) -> list[str]:
    if not report.get("found"):
        return [f"{label}_report_missing"]
    if report.get("verdict") != expected:
        return [f"{label}_verdict_not_{expected}"]
    return []


def category(name: str, status: str, evidence: dict, blockers: list[str] | None = None, warnings: list[str] | None = None) -> dict:
    return {
        "name": name,
        "status": status,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "evidence": evidence,
    }


def evaluate_index(personal_root: Path, sqlite_index_path: Path, evidence: dict) -> dict:
    status = sqlite_index_status(sqlite_index_path) if sqlite_index_path.exists() else {"exists": False}
    inventory = evidence["personal_inventory"]
    inventory_payload = inventory.get("payload") or {}
    inventory_status = inventory_payload.get("index_status") or {}
    remote_status_ok = inventory_status.get("status") in ("completed", "ready")
    remote_personal_ok = bool(
        inventory.get("found")
        and remote_status_ok
        and inventory_status.get("personal_root")
        and int(inventory_status.get("file_count") or 0) > 0
    )
    effective_status = status if status.get("status") in ("completed", "ready") else inventory_status
    blockers = []
    warnings = []
    if not personal_root.exists() and not remote_personal_ok:
        blockers.append("personal_root_missing")
    if not sqlite_index_path.exists() and not remote_status_ok:
        blockers.append("sqlite_index_missing")
    if effective_status.get("status") not in ("completed", "ready"):
        blockers.append("sqlite_index_not_completed")
    if (effective_status.get("failed_count") or 0) > 0:
        blockers.append("sqlite_index_has_failed_files")
    queue_progress = effective_status.get("queue_progress") or {}
    if queue_progress and queue_progress.get("complete") is not True:
        blockers.append("sqlite_index_queue_incomplete")
    resident = evidence["index_daemon_resident"]
    readiness = evidence["index_daemon_readiness"]
    rename_detection = evidence["index_rename_detection"]
    observability = evidence["index_observability_contract"]
    integrity = evidence["sqlite_index_integrity_contract"]
    incremental = evidence["incremental_scan_efficiency_contract"]
    systemd_install = evidence["index_systemd_daemon_install"]
    blockers.extend(report_blocker(resident, "index_daemon_resident", "ok_ai_nas_index_daemon_resident"))
    blockers.extend(report_blocker(rename_detection, "index_rename_detection", "ok_ai_nas_index_rename_detection"))
    blockers.extend(report_blocker(observability, "index_observability_contract", "ok_ai_nas_index_observability_contract"))
    blockers.extend(report_blocker(integrity, "sqlite_index_integrity_contract", "ok_ai_nas_sqlite_index_integrity_contract"))
    blockers.extend(
        report_blocker(
            incremental,
            "incremental_scan_efficiency_contract",
            "ok_ai_nas_incremental_scan_efficiency_contract",
        )
    )
    if readiness.get("found") and readiness.get("verdict") not in (
        "ok_ai_nas_index_daemon_readiness",
        "limited_ai_nas_index_daemon_readiness",
    ):
        blockers.append("index_daemon_readiness_report_failed")
    if not ok_verdict(systemd_install, "ok_ai_nas_index_systemd_daemon_install"):
        warnings.append("production_systemd_index_daemon_install_not_verified")
    return category(
        "index_productization",
        "ready" if not blockers else "limited",
        {
            "sqlite_index_status": status,
            "remote_personal_inventory_report": {k: v for k, v in inventory.items() if k != "payload"},
            "remote_personal_inventory_status": inventory_status,
            "effective_sqlite_index_status": effective_status,
            "index_daemon_resident_report": {k: v for k, v in resident.items() if k != "payload"},
            "index_daemon_readiness_report": {k: v for k, v in readiness.items() if k != "payload"},
            "index_rename_detection_report": {k: v for k, v in rename_detection.items() if k != "payload"},
            "index_observability_contract_report": {k: v for k, v in observability.items() if k != "payload"},
            "index_observability_contract_summary": (observability.get("payload") or {}).get("summary") or {},
            "sqlite_index_integrity_contract_report": {k: v for k, v in integrity.items() if k != "payload"},
            "sqlite_index_integrity_contract_summary": (integrity.get("payload") or {}).get("summary") or {},
            "incremental_scan_efficiency_contract_report": {k: v for k, v in incremental.items() if k != "payload"},
            "incremental_scan_efficiency_contract_summary": (incremental.get("payload") or {}).get("summary") or {},
            "index_systemd_daemon_install_report": {k: v for k, v in systemd_install.items() if k != "payload"},
            "index_systemd_daemon_install_summary": (systemd_install.get("payload") or {}).get("summary") or {},
        },
        blockers,
        warnings,
    )


def evaluate_queue(evidence: dict) -> dict:
    soak = evidence["continuous_task_soak"]
    checkpoint_resume = evidence["soak_checkpoint_resume"]
    backpressure = evidence["queue_backpressure_slo"]
    isolation = evidence["index_search_isolation_slo"]
    tail_latency = evidence["user_facing_tail_latency"]
    bpu_headroom = evidence["bpu_headroom_slo"]
    operational_rollup = evidence["operational_slo_rollup_contract"]
    nas_soak = evidence["nas_backed_long_soak"]
    blockers = report_blocker(soak, "continuous_task_soak", "ok_ai_nas_continuous_task_soak")
    blockers.extend(report_blocker(checkpoint_resume, "soak_checkpoint_resume", "ok_ai_nas_soak_checkpoint_resume"))
    blockers.extend(report_blocker(backpressure, "queue_backpressure_slo", "ok_ai_nas_queue_backpressure_slo"))
    blockers.extend(report_blocker(isolation, "index_search_isolation_slo", "ok_ai_nas_index_search_isolation_slo"))
    blockers.extend(report_blocker(tail_latency, "user_facing_tail_latency", "ok_ai_nas_user_facing_tail_latency"))
    blockers.extend(report_blocker(bpu_headroom, "bpu_headroom_slo", "ok_ai_nas_bpu_headroom_slo"))
    blockers.extend(
        report_blocker(
            operational_rollup,
            "operational_slo_rollup_contract",
            "ok_ai_nas_operational_slo_rollup_contract",
        )
    )
    warnings = []
    nas_soak_payload = nas_soak.get("payload") or {}
    nas_soak_summary = nas_soak_payload.get("summary") or {}
    nas_soak_config = nas_soak_payload.get("config") or {}
    nas_elapsed = float(nas_soak_summary.get("elapsed_seconds") or 0.0)
    nas_min_duration = float(nas_soak_config.get("min_duration_seconds") or 0.0)
    nas_file_count = int(nas_soak_summary.get("final_file_count") or 0)
    nas_soak_production_verified = (
        ok_verdict(nas_soak, "ok_ai_nas_nas_backed_long_soak")
        and bool(nas_soak_summary.get("nas_backed"))
        and nas_elapsed >= MIN_PRODUCTION_NAS_SOAK_SECONDS
        and nas_min_duration >= MIN_PRODUCTION_NAS_SOAK_SECONDS
        and nas_file_count >= MIN_PRODUCTION_NAS_SOAK_FILE_COUNT
    )
    if not nas_soak_production_verified:
        warnings.append("production_nas_backed_long_soak_not_verified")
    payload = soak.get("payload") or {}
    summary = payload.get("summary") or {}
    checkpoint_payload = checkpoint_resume.get("payload") or {}
    backpressure_payload = backpressure.get("payload") or {}
    isolation_payload = isolation.get("payload") or {}
    tail_latency_payload = tail_latency.get("payload") or {}
    bpu_headroom_payload = bpu_headroom.get("payload") or {}
    operational_rollup_payload = operational_rollup.get("payload") or {}
    return category(
        "p95_p99_queue_throughput",
        "ready" if not blockers else "limited",
        {
            "continuous_task_soak_report": {k: v for k, v in soak.items() if k != "payload"},
            "summary": summary,
            "soak_checkpoint_resume_report": {k: v for k, v in checkpoint_resume.items() if k != "payload"},
            "soak_checkpoint_resume_summary": checkpoint_payload.get("summary") or {},
            "queue_backpressure_slo_report": {k: v for k, v in backpressure.items() if k != "payload"},
            "queue_backpressure_slo_summary": backpressure_payload.get("summary") or {},
            "index_search_isolation_slo_report": {k: v for k, v in isolation.items() if k != "payload"},
            "index_search_isolation_slo_summary": isolation_payload.get("summary") or {},
            "user_facing_tail_latency_report": {k: v for k, v in tail_latency.items() if k != "payload"},
            "user_facing_tail_latency_summary": tail_latency_payload.get("summary") or {},
            "bpu_headroom_slo_report": {k: v for k, v in bpu_headroom.items() if k != "payload"},
            "bpu_headroom_slo_summary": bpu_headroom_payload.get("summary") or {},
            "operational_slo_rollup_contract_report": {k: v for k, v in operational_rollup.items() if k != "payload"},
            "operational_slo_rollup_contract_summary": operational_rollup_payload.get("summary") or {},
            "operational_slo_rollup_scorecard": operational_rollup_payload.get("scorecard") or {},
            "nas_backed_long_soak_report": {k: v for k, v in nas_soak.items() if k != "payload"},
            "nas_backed_long_soak_summary": nas_soak_summary,
            "nas_backed_long_soak_production_requirements": {
                "verified": nas_soak_production_verified,
                "min_elapsed_seconds": MIN_PRODUCTION_NAS_SOAK_SECONDS,
                "min_configured_duration_seconds": MIN_PRODUCTION_NAS_SOAK_SECONDS,
                "min_file_count": MIN_PRODUCTION_NAS_SOAK_FILE_COUNT,
                "observed_elapsed_seconds": nas_elapsed,
                "observed_configured_min_duration_seconds": nas_min_duration,
                "observed_file_count": nas_file_count,
            },
        },
        blockers,
        warnings,
    )


def evaluate_search(evidence: dict, text_model_dir: Path | None, image_model_dir: Path | None) -> dict:
    modules = module_status(["sentence_transformers", "transformers", "torch", "PIL", "clip", "open_clip"])
    text_model = model_dir_status(text_model_dir, ["config.json", "modules.json", "sentence_bert_config.json"])
    image_model = model_dir_status(image_model_dir, ["config.json", "preprocessor_config.json", "open_clip_config.json"])
    text_smoke = try_sentence_transformer_smoke(text_model_dir)
    image_smoke = try_clip_smoke(image_model_dir)
    backend = evidence["embedding_backend_readiness"]
    backend_payload = backend.get("payload") or {}
    backend_readiness = backend_payload.get("production_readiness") or {}
    backend_text_ready = bool(backend_readiness.get("text_embedding_ready"))
    backend_image_ready = bool(backend_readiness.get("image_clip_ready"))
    semantic = evidence["semantic_query_acceptance"]
    appliance = evidence["appliance_experience_acceptance"]
    portal = evidence["operator_portal_contract"]
    evidence_contract = evidence["search_evidence_contract"]
    confidence_contract = evidence["search_confidence_calibration_contract"]
    routing_contract = evidence["multimodal_intent_routing_contract"]
    runtime_contract = evidence["embedding_runtime_contract"]
    blockers = []
    blockers.extend(report_blocker(semantic, "semantic_query_acceptance", "ok_ai_nas_semantic_query_acceptance"))
    blockers.extend(report_blocker(appliance, "appliance_experience_acceptance", "ok_ai_nas_appliance_experience_acceptance"))
    blockers.extend(report_blocker(portal, "operator_portal_contract", "ok_ai_nas_operator_portal_contract"))
    blockers.extend(report_blocker(evidence_contract, "search_evidence_contract", "ok_ai_nas_search_evidence_contract"))
    blockers.extend(
        report_blocker(
            confidence_contract,
            "search_confidence_calibration_contract",
            "ok_ai_nas_search_confidence_calibration_contract",
        )
    )
    blockers.extend(
        report_blocker(
            routing_contract,
            "multimodal_intent_routing_contract",
            "ok_ai_nas_multimodal_intent_routing_contract",
        )
    )
    if not runtime_contract.get("found"):
        blockers.append("embedding_runtime_contract_report_missing")
    text_ready = bool(text_smoke.get("ok") or backend_text_ready)
    image_ready = bool(image_smoke.get("ok") or backend_image_ready)
    if not text_ready:
        blockers.append("production_text_embedding_smoke_not_ready")
    if not image_ready:
        blockers.append("production_image_clip_smoke_not_ready")
    warnings = []
    if not (text_ready and image_ready):
        warnings.append("local_hash_embedding_v1_remains_fallback_until_production_model_rows_exist")
    return category(
        "search_embedding_and_fuzzy_query",
        "ready" if not blockers else "limited",
        {
            "module_status": modules,
            "text_model_dir": text_model,
            "image_model_dir": image_model,
            "text_smoke": text_smoke,
            "image_smoke": image_smoke,
            "effective_text_embedding_ready": text_ready,
            "effective_image_clip_ready": image_ready,
            "embedding_backend_readiness_report": {k: v for k, v in backend.items() if k != "payload"},
            "embedding_backend_readiness_summary": backend_readiness,
            "semantic_acceptance_report": {k: v for k, v in semantic.items() if k != "payload"},
            "appliance_experience_report": {k: v for k, v in appliance.items() if k != "payload"},
            "operator_portal_contract_report": {k: v for k, v in portal.items() if k != "payload"},
            "operator_portal_contract_summary": (portal.get("payload") or {}).get("summary") or {},
            "search_evidence_contract_report": {k: v for k, v in evidence_contract.items() if k != "payload"},
            "search_evidence_contract_summary": (evidence_contract.get("payload") or {}).get("summary") or {},
            "search_confidence_calibration_contract_report": {k: v for k, v in confidence_contract.items() if k != "payload"},
            "search_confidence_calibration_contract_summary": (confidence_contract.get("payload") or {}).get("summary") or {},
            "multimodal_intent_routing_contract_report": {k: v for k, v in routing_contract.items() if k != "payload"},
            "multimodal_intent_routing_contract_summary": (routing_contract.get("payload") or {}).get("summary") or {},
            "embedding_runtime_contract_report": {k: v for k, v in runtime_contract.items() if k != "payload"},
            "embedding_runtime_contract_summary": (runtime_contract.get("payload") or {}).get("summary") or {},
        },
        blockers,
        warnings,
    )


def evaluate_documents(evidence: dict) -> dict:
    runtime = ocr_engine_status()
    document = evidence["document_pipeline_acceptance"]
    folder_grounding = evidence["folder_rag_grounding_contract"]
    ocr_contract = evidence["ocr_runtime_contract"]
    official_ppocr = evidence.get("official_ppocr_wrapper") or {}
    official_bridge = evidence.get("official_ppocr_document_bridge") or {}
    ocr_payload = ocr_contract.get("payload") or {}
    official_ppocr_payload = official_ppocr.get("payload") or {}
    official_bridge_payload = official_bridge.get("payload") or {}
    official_ppocr_ready = bool(
        official_ppocr.get("found")
        and official_ppocr_payload.get("verdict") == "ok_ai_nas_official_ppocr_wrapper"
        and official_ppocr_payload.get("ok") is True
    )
    official_bridge_ready = bool(
        official_bridge.get("found")
        and official_bridge_payload.get("verdict") == "ok_ai_nas_official_ppocr_document_bridge"
        and ((official_bridge_payload.get("bridge_result") or {}).get("status") == "ocr_completed")
    )
    local_document_ocr_ready = bool(runtime.get("ocr_ready") or ocr_payload.get("production_ocr_ready"))
    ocr_runtime_available = bool(local_document_ocr_ready or official_ppocr_ready or official_bridge_ready)
    ocr_smoke = ocr_payload.get("smoke") or {}
    pdf_text_layer_ready = bool((ocr_smoke.get("pdf_text_layer") or {}).get("ok"))
    scan_detection_ready = bool((ocr_smoke.get("scanned_image_detection") or {}).get("ok"))
    blockers = report_blocker(document, "document_pipeline_acceptance", "ok_ai_nas_document_pipeline_acceptance")
    blockers.extend(
        report_blocker(
            folder_grounding,
            "folder_rag_grounding_contract",
            "ok_ai_nas_folder_rag_grounding_contract",
        )
    )
    if not ocr_contract.get("found"):
        blockers.append("ocr_runtime_contract_report_missing")
    if not ocr_runtime_available:
        blockers.append("production_ocr_runtime_not_ready")
    elif not (local_document_ocr_ready or official_bridge_ready):
        blockers.append("official_ppocr_ready_but_document_pipeline_ocr_bridge_not_integrated")
    warnings = []
    if not ocr_runtime_available:
        warnings.append("scanned_content_must_remain_explicitly_blocked_when_ocr_runtime_missing")
    elif not (local_document_ocr_ready or official_bridge_ready):
        warnings.append("scanned_pdf_ocr_requires_official_ppocr_bridge_into_document_pipeline")
    return category(
        "document_pdf_ocr_folder_rag",
        "ready" if not blockers else "limited",
        {
            "ocr_runtime": runtime,
            "effective_ocr_runtime_available": ocr_runtime_available,
            "local_document_ocr_ready": local_document_ocr_ready,
            "official_ppocr_wrapper_ready": official_ppocr_ready,
            "official_ppocr_document_bridge_ready": official_bridge_ready,
            "pdf_text_layer_ready": pdf_text_layer_ready,
            "scan_detection_ready": scan_detection_ready,
            "document_pipeline_report": {k: v for k, v in document.items() if k != "payload"},
            "folder_rag_grounding_contract_report": {k: v for k, v in folder_grounding.items() if k != "payload"},
            "folder_rag_grounding_contract_summary": (folder_grounding.get("payload") or {}).get("summary") or {},
            "ocr_runtime_contract_report": {k: v for k, v in ocr_contract.items() if k != "payload"},
            "ocr_runtime_contract_summary": (ocr_contract.get("payload") or {}).get("summary") or {},
            "official_ppocr_wrapper_report": {k: v for k, v in official_ppocr.items() if k != "payload"},
            "official_ppocr_document_bridge_report": {k: v for k, v in official_bridge.items() if k != "payload"},
        },
        blockers,
        warnings,
    )


def evaluate_photos(evidence: dict) -> dict:
    runtime = image_embedding_runtime_status()
    photo = evidence["photo_pipeline_acceptance"]
    privacy = evidence["photo_privacy_governance"]
    backend = evidence["embedding_backend_readiness"]
    backend_payload = backend.get("payload") or {}
    backend_readiness = backend_payload.get("production_readiness") or {}
    runtime_contract = evidence["embedding_runtime_contract"]
    runtime_payload = runtime_contract.get("payload") or {}
    runtime_summary = runtime_payload.get("summary") or {}
    clip_ready = bool(
        runtime.get("production_clip_ready")
        or backend_readiness.get("image_clip_ready")
        or runtime_summary.get("production_image_ready")
    )
    blockers = report_blocker(photo, "photo_pipeline_acceptance", "ok_ai_nas_photo_pipeline_acceptance")
    blockers.extend(report_blocker(privacy, "photo_privacy_governance", "ok_ai_nas_photo_privacy_governance"))
    if not clip_ready:
        blockers.append("production_clip_runtime_not_ready")
    warnings = ["face_recognition_remains_out_of_scope_until_privacy_review"]
    if not clip_ready:
        warnings.append("photo_semantics_remain_exif_phash_pil_fallback_until_production_clip_ready")
    return category(
        "photo_exif_phash_clip_path",
        "ready" if not blockers else "limited",
        {
            "image_runtime": runtime,
            "effective_clip_ready": clip_ready,
            "embedding_backend_readiness_report": {k: v for k, v in backend.items() if k != "payload"},
            "embedding_backend_readiness_summary": backend_readiness,
            "embedding_runtime_contract_report": {k: v for k, v in runtime_contract.items() if k != "payload"},
            "embedding_runtime_contract_summary": runtime_summary,
            "photo_pipeline_report": {k: v for k, v in photo.items() if k != "payload"},
            "photo_privacy_governance_report": {k: v for k, v in privacy.items() if k != "payload"},
            "photo_privacy_governance_summary": (privacy.get("payload") or {}).get("summary") or {},
        },
        blockers,
        warnings,
    )


def evaluate_acl(personal_root: Path, mapping_config: list[Path], evidence: dict) -> dict:
    tools = tool_paths()
    samples, failures = sample_entries(personal_root)
    configs = mapping_configs(mapping_config or DEFAULT_MAPPING_CONFIGS)
    readiness = evaluate_acl_readiness(personal_root, samples, failures, tools, configs)
    acl_report = evidence["acl_mapping_readiness"]
    remote_payload = acl_report.get("payload") or {}
    remote_readiness = remote_payload.get("readiness") or {}
    remote_samples = remote_payload.get("sample_entries") or []
    remote_is_useful = bool(
        acl_report.get("found")
        and remote_readiness.get("root_exists")
        and int(remote_readiness.get("sample_count") or len(remote_samples) or 0) > 0
    )
    if remote_is_useful:
        readiness = remote_readiness
        tools = remote_payload.get("tools") or tools
        configs = remote_payload.get("mapping_configs") or configs
        samples = remote_samples
        failures = remote_payload.get("stat_failures") or []
    blockers = list(readiness.get("blockers") or [])
    warnings = list(readiness.get("warnings") or [])
    return category(
        "real_nas_acl_user_mapping",
        "ready" if readiness.get("production_nas_acl_ready") else "limited",
        {
            "tools": tools,
            "mapping_configs": configs,
            "readiness": readiness,
            "sample_count": len(samples),
            "stat_failure_count": len(failures),
            "remote_acl_mapping_readiness_report": {k: v for k, v in acl_report.items() if k != "payload"},
            "remote_acl_mapping_readiness_used": remote_is_useful,
        },
        blockers,
        warnings,
    )


def evaluate_model_service(evidence: dict, report_root: Path, services: list[str], health_urls: list[str], unit_files: list[Path]) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    systemctl_checks = []
    for service in services:
        user_active = run_command(["systemctl", "--user", "is-active", service])
        user_enabled = run_command(["systemctl", "--user", "is-enabled", service])
        system_active = run_command(["systemctl", "is-active", service])
        system_enabled = run_command(["systemctl", "is-enabled", service])
        systemctl_checks.append(
            {
                "service": service,
                "user": {"is_active": user_active, "is_enabled": user_enabled},
                "system": {"is_active": system_active, "is_enabled": system_enabled},
                "is_active": user_active if user_active.get("ok") else system_active,
                "is_enabled": user_enabled if user_enabled.get("ok") else system_enabled,
                "active_scope": "user" if user_active.get("ok") else ("system" if system_active.get("ok") else None),
                "enabled_scope": "user" if user_enabled.get("ok") else ("system" if system_enabled.get("ok") else None),
            }
        )
    health = [check_health_url(url) for url in health_urls]
    units = [parse_unit_file(path) for path in candidate_unit_paths(repo_root, unit_files)]
    resilience = evidence["model_service_resilience"]
    resilience_payload = resilience.get("payload") or {}
    resilience_summary = resilience_payload.get("summary") or {}
    recovery = evidence["model_service_recovery_drill"]
    real_recovery = evidence["model_service_real_recovery_drill"]
    recovery_manifest = evidence["model_service_recovery_manifest"]
    blockers = []
    health_ok = any(item.get("ok") for item in health) or int(resilience_summary.get("health_ok_count") or 0) > 0
    systemd_active = (
        any(check["is_active"].get("ok") for check in systemctl_checks)
        or int(resilience_summary.get("systemctl_active_count") or 0) > 0
    )
    restart_policy = (
        any(unit.get("has_restart_policy") for unit in units)
        or int(resilience_summary.get("restart_policy_count") or 0) > 0
    )
    if not health_ok:
        blockers.append("no_model_or_openclaw_health_endpoint_ok")
    if not systemd_active:
        blockers.append("no_systemd_service_active")
    if not restart_policy:
        blockers.append("restart_policy_not_verified")
    blockers.extend(report_blocker(recovery, "model_service_recovery_drill", "ok_model_service_recovery_drill"))
    manifest_warnings = report_blocker(
        recovery_manifest,
        "model_service_recovery_manifest",
        "ok_ai_nas_model_service_recovery_manifest",
    )
    warnings = []
    if not ok_verdict(real_recovery, "ok_ai_nas_model_service_real_recovery_drill"):
        warnings.append("operator_approved_real_service_kill_restart_drill_not_verified")
    warnings.extend(manifest_warnings)
    return category(
        "model_service_crash_recovery",
        "ready" if not blockers else "limited",
        {
            "health": health,
            "model_service_resilience_report": {k: v for k, v in resilience.items() if k != "payload"},
            "model_service_resilience_summary": resilience_summary,
            "systemctl_checks": systemctl_checks,
            "unit_files": units,
            "model_service_recovery_drill_report": {k: v for k, v in recovery.items() if k != "payload"},
            "model_service_real_recovery_drill_report": {k: v for k, v in real_recovery.items() if k != "payload"},
            "model_service_real_recovery_drill_summary": (real_recovery.get("payload") or {}).get("summary") or {},
            "model_service_recovery_manifest_report": {k: v for k, v in recovery_manifest.items() if k != "payload"},
            "report_root": str(report_root),
        },
        blockers,
        warnings,
    )


def evaluate_governance(deploy_root: Path, evidence: dict) -> dict:
    source_root = default_source_root(deploy_root)
    allowlist_path = deploy_root / "scripts" / "tool_allowlist.json"
    runner_path = deploy_root / "scripts" / "run_allowlisted_tool.sh"
    plugin_path = deploy_root / "openclaw-plugins" / "s100p-allowlisted-tools" / "index.js"
    blockers = []
    warnings = []
    if not allowlist_path.exists():
        return category("openclaw_tool_governance", "blocked", {"deploy_root": str(deploy_root)}, ["allowlist_json_missing"], [])
    allowlist = load_json(allowlist_path)
    runner_text = text_or_empty(runner_path)
    plugin_text = text_or_empty(plugin_path)
    tools = allowlist.get("tools") or []
    ai_nas_tools = [tool for tool in tools if str(tool.get("id", "")).startswith("ai_nas_")]
    ids = [tool.get("id") for tool in ai_nas_tools]
    duplicates = sorted({tool_id for tool_id in ids if ids.count(tool_id) > 1})
    audits = [audit_tool(tool, runner_text, plugin_text, source_root, deploy_root) for tool in ai_nas_tools]
    issues = [{"id": dup, "issue": "duplicate ai_nas tool id"} for dup in duplicates]
    issues.extend({"id": item["id"], "issue": issue} for item in audits for issue in item["issues"])
    warnings.extend(f"{item['id']}:{warning}" for item in audits for warning in item["warnings"])
    if len(ai_nas_tools) < MIN_AI_NAS_TOOL_COUNT:
        blockers.append(f"ai_nas_tool_count_lt_{MIN_AI_NAS_TOOL_COUNT}")
    blockers.extend(f"{item['id']}:{item['issue']}" for item in issues)
    destructive_governance = evidence["destructive_action_governance"]
    manifest_integrity = evidence["action_manifest_integrity"]
    operator_inbox = evidence["operator_approval_inbox"]
    audit_trail = evidence["audit_trail_contract"]
    blockers.extend(
        report_blocker(
            destructive_governance,
            "destructive_action_governance",
            "ok_ai_nas_destructive_action_governance",
        )
    )
    blockers.extend(
        report_blocker(
            manifest_integrity,
            "action_manifest_integrity",
            "ok_ai_nas_action_manifest_integrity",
        )
    )
    blockers.extend(
        report_blocker(
            operator_inbox,
            "operator_approval_inbox",
            "ok_ai_nas_operator_approval_inbox",
        )
    )
    blockers.extend(
        report_blocker(
            audit_trail,
            "audit_trail_contract",
            "ok_ai_nas_audit_trail_contract",
        )
    )
    return category(
        "openclaw_tool_governance",
        "ready" if not blockers else "limited",
        {
            "deploy_root": str(deploy_root),
            "source_root": str(source_root),
            "tool_count": len(ai_nas_tools),
            "hard_issue_count": len(issues),
            "warning_count": len(warnings),
            "source_deploy_parity": {
                "source_exists_count": sum(1 for item in audits if item["script_parity"].get("source_exists")),
                "deploy_exists_count": sum(1 for item in audits if item["script_parity"].get("deploy_exists")),
                "same_sha256_count": sum(1 for item in audits if item["script_parity"].get("same_sha256")),
                "different_sha256_count": sum(
                    1
                    for item in audits
                    if item["script_parity"].get("source_exists")
                    and item["script_parity"].get("deploy_exists")
                    and not item["script_parity"].get("same_sha256")
                ),
            },
            "contains_gate_tool": TOOL_ID in ids,
            "destructive_action_governance_report": {
                k: v for k, v in destructive_governance.items() if k != "payload"
            },
            "destructive_action_governance_summary": (destructive_governance.get("payload") or {}).get("summary") or {},
            "action_manifest_integrity_report": {
                k: v for k, v in manifest_integrity.items() if k != "payload"
            },
            "action_manifest_integrity_summary": (manifest_integrity.get("payload") or {}).get("summary") or {},
            "operator_approval_inbox_report": {
                k: v for k, v in operator_inbox.items() if k != "payload"
            },
            "operator_approval_inbox_summary": (operator_inbox.get("payload") or {}).get("summary") or {},
            "audit_trail_contract_report": {
                k: v for k, v in audit_trail.items() if k != "payload"
            },
            "audit_trail_contract_summary": (audit_trail.get("payload") or {}).get("summary") or {},
        },
        blockers,
        warnings,
    )


def evaluate_dependency_bundle(evidence: dict) -> dict:
    bundle = evidence["production_dependency_bundle"]
    runbook = evidence["production_blocker_runbook_contract"]
    blockers = []
    if not bundle.get("found"):
        blockers.append("production_dependency_bundle_report_missing")
    elif bundle.get("verdict") not in (
        "ok_ai_nas_production_dependency_bundle",
        "limited_ai_nas_production_dependency_bundle",
    ):
        blockers.append("production_dependency_bundle_verdict_invalid")
    blockers.extend(
        report_blocker(
            runbook,
            "production_blocker_runbook_contract",
            "ok_ai_nas_production_blocker_runbook_contract",
        )
    )
    payload = bundle.get("payload") or {}
    runbook_payload = runbook.get("payload") or {}
    return category(
        "production_dependency_evidence_bundle",
        "ready" if not blockers else "limited",
        {
            "production_dependency_bundle_report": {k: v for k, v in bundle.items() if k != "payload"},
            "production_dependency_bundle_summary": payload.get("summary") or {},
            "production_blocker_runbook_contract_report": {k: v for k, v in runbook.items() if k != "payload"},
            "production_blocker_runbook_contract_summary": runbook_payload.get("summary") or {},
            "operator_next_steps": payload.get("operator_next_steps") or [],
            "note": "This category verifies consolidated evidence exists; underlying dependency blockers remain in their owning categories.",
        },
        blockers,
        [],
    )


def evaluate_evidence_freshness(evidence: dict) -> dict:
    freshness = evidence["evidence_freshness_contract"]
    catalog = evidence["evidence_catalog_contract"]
    traceability = evidence["objective_traceability_contract"]
    blockers = report_blocker(
        freshness,
        "evidence_freshness_contract",
        "ok_ai_nas_evidence_freshness_contract",
    )
    blockers.extend(
        report_blocker(
            catalog,
            "evidence_catalog_contract",
            "ok_ai_nas_evidence_catalog_contract",
        )
    )
    blockers.extend(
        report_blocker(
            traceability,
            "objective_traceability_contract",
            "ok_ai_nas_objective_traceability_contract",
        )
    )
    payload = freshness.get("payload") or {}
    catalog_payload = catalog.get("payload") or {}
    traceability_payload = traceability.get("payload") or {}
    return category(
        "evidence_freshness_and_provenance",
        "ready" if not blockers else "limited",
        {
            "evidence_freshness_contract_report": {k: v for k, v in freshness.items() if k != "payload"},
            "evidence_freshness_contract_summary": payload.get("summary") or {},
            "evidence_catalog_contract_report": {k: v for k, v in catalog.items() if k != "payload"},
            "evidence_catalog_contract_summary": catalog_payload.get("summary") or {},
            "objective_traceability_contract_report": {k: v for k, v in traceability.items() if k != "payload"},
            "objective_traceability_contract_summary": traceability_payload.get("summary") or {},
        },
        blockers,
        [],
    )


def evaluate_portable_nas_adapter(evidence: dict) -> dict:
    adapter = evidence["portable_nas_adapter_contract"]
    blockers = report_blocker(
        adapter,
        "portable_nas_adapter_contract",
        "ok_ai_nas_portable_nas_adapter_contract",
    )
    payload = adapter.get("payload") or {}
    return category(
        "portable_nas_adapter_contract",
        "ready" if not blockers else "limited",
        {
            "portable_nas_adapter_contract_report": {k: v for k, v in adapter.items() if k != "payload"},
            "portable_nas_adapter_contract_summary": payload.get("summary") or {},
        },
        blockers,
        [],
    )


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [report_root]
    local_tmp = Path("tmp")
    if local_tmp.exists():
        roots.append(local_tmp)
    return roots


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS production readiness gate for the local Copilot Appliance architecture.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--deploy-root", type=Path, default=default_gate_deploy_root())
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    parser.add_argument("--mapping-config", action="append", type=Path, default=[])
    parser.add_argument("--text-model-dir", type=Path, default=None)
    parser.add_argument("--image-model-dir", type=Path, default=None)
    parser.add_argument("--health-url", action="append", default=[])
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--unit-file", action="append", type=Path, default=[])
    parser.add_argument("--refresh-index", action="store_true")
    args = parser.parse_args()

    if args.refresh_index or (args.personal_root.exists() and not args.sqlite_index_path.exists()):
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    evidence = {
        "personal_inventory": latest_report(evidence_roots, "personal_inventory.json"),
        "index_daemon_readiness": latest_report(evidence_roots, "index_daemon_readiness.json"),
        "index_daemon_resident": latest_report(evidence_roots, "index_daemon_resident.json"),
        "index_systemd_daemon_install": latest_report(evidence_roots, "index_systemd_daemon_install.json"),
        "index_rename_detection": latest_report(evidence_roots, "index_rename_detection.json"),
        "index_observability_contract": latest_report(evidence_roots, "index_observability_contract.json"),
        "sqlite_index_integrity_contract": latest_report(evidence_roots, "sqlite_index_integrity_contract.json"),
        "incremental_scan_efficiency_contract": latest_report(evidence_roots, "incremental_scan_efficiency_contract.json"),
        "continuous_task_soak": latest_report(evidence_roots, "continuous_task_soak.json"),
        "soak_checkpoint_resume": latest_report(evidence_roots, "soak_checkpoint_resume.json"),
        "queue_backpressure_slo": latest_report(evidence_roots, "queue_backpressure_slo.json"),
        "index_search_isolation_slo": latest_report(evidence_roots, "index_search_isolation_slo.json"),
        "user_facing_tail_latency": latest_report(evidence_roots, "user_facing_tail_latency.json"),
        "bpu_headroom_slo": latest_report(evidence_roots, "bpu_headroom_slo.json"),
        "operational_slo_rollup_contract": latest_report(evidence_roots, "operational_slo_rollup_contract.json"),
        "nas_backed_long_soak": latest_report(evidence_roots, "nas_backed_long_soak.json"),
        "semantic_query_acceptance": latest_report(evidence_roots, "semantic_query_acceptance.json"),
        "appliance_experience_acceptance": latest_report(evidence_roots, "appliance_experience_acceptance.json"),
        "operator_portal_contract": latest_report(evidence_roots, "operator_portal_contract.json"),
        "search_evidence_contract": latest_report(evidence_roots, "search_evidence_contract.json"),
        "search_confidence_calibration_contract": latest_report(evidence_roots, "search_confidence_calibration_contract.json"),
        "multimodal_intent_routing_contract": latest_report(evidence_roots, "multimodal_intent_routing_contract.json"),
        "embedding_runtime_contract": latest_report(evidence_roots, "embedding_runtime_contract.json"),
        "embedding_backend_readiness": latest_report(evidence_roots, "embedding_backend_readiness.json"),
        "document_pipeline_acceptance": latest_report(evidence_roots, "document_pipeline_acceptance.json"),
        "folder_rag_grounding_contract": latest_report(evidence_roots, "folder_rag_grounding_contract.json"),
        "ocr_runtime_contract": latest_report(evidence_roots, "ocr_runtime_contract.json"),
        "official_ppocr_wrapper": latest_report(evidence_roots, "official_ppocr_wrapper.json"),
        "official_ppocr_document_bridge": latest_report(evidence_roots, "official_ppocr_document_bridge.json"),
        "photo_pipeline_acceptance": latest_report(evidence_roots, "photo_pipeline_acceptance.json"),
        "photo_privacy_governance": latest_report(evidence_roots, "photo_privacy_governance.json"),
        "model_service_resilience": latest_report(evidence_roots, "model_service_resilience.json"),
        "model_service_recovery_drill": latest_report(evidence_roots, "model_service_recovery_drill.json"),
        "model_service_real_recovery_drill": latest_report(evidence_roots, "model_service_real_recovery_drill.json"),
        "model_service_recovery_manifest": latest_report(evidence_roots, "model_service_recovery_manifest.json"),
        "production_dependency_bundle": latest_report(evidence_roots, "production_dependency_bundle.json"),
        "acl_mapping_readiness": latest_report(evidence_roots, "acl_mapping_readiness.json"),
        "production_blocker_runbook_contract": latest_report(evidence_roots, "production_blocker_runbook_contract.json"),
        "evidence_catalog_contract": latest_report(evidence_roots, "evidence_catalog_contract.json"),
        "objective_traceability_contract": latest_report(evidence_roots, "objective_traceability_contract.json"),
        "evidence_freshness_contract": latest_report(evidence_roots, "evidence_freshness_contract.json"),
        "portable_nas_adapter_contract": latest_report(evidence_roots, "portable_nas_adapter_contract.json"),
        "destructive_action_governance": latest_report(evidence_roots, "destructive_action_governance.json"),
        "action_manifest_integrity": latest_report(evidence_roots, "action_manifest_integrity.json"),
        "operator_approval_inbox": latest_report(evidence_roots, "operator_approval_inbox.json"),
        "audit_trail_contract": latest_report(evidence_roots, "audit_trail_contract_report.json"),
    }
    text_model_dir = configured_text_model_dir(args.text_model_dir)
    image_model_dir = configured_image_model_dir(args.image_model_dir)
    categories = [
        evaluate_index(args.personal_root, args.sqlite_index_path, evidence),
        evaluate_queue(evidence),
        evaluate_search(evidence, text_model_dir, image_model_dir),
        evaluate_documents(evidence),
        evaluate_photos(evidence),
        evaluate_acl(args.personal_root, args.mapping_config, evidence),
        evaluate_model_service(
            evidence,
            args.report_root,
            args.service or DEFAULT_SERVICES,
            args.health_url or DEFAULT_HEALTH_URLS,
            args.unit_file,
        ),
        evaluate_dependency_bundle(evidence),
        evaluate_evidence_freshness(evidence),
        evaluate_portable_nas_adapter(evidence),
        evaluate_governance(args.deploy_root, evidence),
    ]
    blockers = [
        f"{item['name']}:{blocker}"
        for item in categories
        for blocker in item["blockers"]
    ]
    warnings = [
        f"{item['name']}:{warning}"
        for item in categories
        for warning in item["warnings"]
    ]
    production_ready = all(item["status"] == "ready" for item in categories) and not blockers
    ready_category_count = sum(1 for item in categories if item["status"] == "ready")
    limited_category_count = sum(1 for item in categories if item["status"] != "ready")
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ready_ai_nas_production_readiness_gate" if production_ready else "limited_ai_nas_production_readiness_gate",
        "production_ready": production_ready,
        "scope": "readiness gate for cheap-NAS plus local AI Copilot Appliance production claims",
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "deploy_root": str(args.deploy_root),
        "evidence_roots": [str(root) for root in evidence_roots],
        "categories": categories,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "summary": {
            "production_ready": production_ready,
            "category_count": len(categories),
            "ready_category_count": ready_category_count,
            "limited_category_count": limited_category_count,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "blockers": blockers,
        "warnings": warnings,
        "required_before_claiming_production_ready": [
            "NAS Personal root is mounted and indexed with queryable SQLite/FTS state.",
            "SQLite/FTS index integrity, required tables, vector rows, and orphan cleanup are verified.",
            "The AI-NAS layer can point at arbitrary mounted NAS roots without NAS-OS-specific assumptions.",
            "Resident index daemon and long-running NAS-backed soak are verified outside bounded fixtures.",
            "BPU scheduling preserves headroom instead of targeting 100% average utilization.",
            "Official Qwen text semantic route and the supported image route pass local-only smoke tests; do not claim CLIP semantics unless a CLIP model smoke passes.",
            "OCR runtime is available and scanned PDFs/images are either extracted or explicitly failed.",
            "Permission-aware search decisions are backed by real NAS ACL/user mapping.",
            "Model/OpenClaw services have health endpoints, restart policies, and an operator-approved recovery drill.",
            "Production evidence reports are fresh, attributable to expected tool IDs, and free of forbidden audit flags.",
            "OpenClaw exposes only governed allowlisted tools with schemas, permissions, write flags, confirmation flags, and report paths.",
            "User-facing web/chat entry surfaces show grounded results, one-click reports, approval queue, and audit state.",
        ],
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
            "writes": "Markdown/JSON production readiness gate report only; optional SQLite index refresh when requested",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "production_readiness_gate")
    json_path = run_dir / "production_readiness_gate.json"
    md_path = run_dir / "production_readiness_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Production Readiness Gate",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- production_ready: `{production_ready}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- blocker_count: `{len(blockers)}`",
        f"- warning_count: `{len(warnings)}`",
        "- policy: report-only gate; no downloads, service restarts, kills, deletes, moves, or overwrites",
        "",
        "## Categories",
        "",
    ]
    for item in categories:
        lines.append(f"- {item['name']}: `{item['status']}` blockers `{len(item['blockers'])}` warnings `{len(item['warnings'])}`")
    lines.extend(["", "## Blockers", ""])
    if not blockers:
        lines.append("- No production readiness blocker detected.")
    for blocker in blockers:
        lines.append(f"- {blocker}")
    lines.extend(["", "## Warnings", ""])
    if not warnings:
        lines.append("- No production readiness warning detected.")
    for warning in warnings:
        lines.append(f"- {warning}")
    lines.extend(["", "## Required Before Production Ready", ""])
    for item in payload["required_before_claiming_production_ready"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
