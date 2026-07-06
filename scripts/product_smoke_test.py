#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_ID = "product_smoke_test"
OK_VERDICT = "ok_product_smoke_test"
FAILED_VERDICT = "failed_product_smoke_test"
RAW_PATH_RE = re.compile(r"([A-Za-z]:\\|/mnt/nas/|/root/|/home/sunrise/)")
REQUIRED_MODULES = {
    "gateway",
    "qwen",
    "harness",
    "router",
    "multimodal",
    "yolo",
    "person_attribute",
    "ai_space",
    "smart_classification",
    "smart_naming",
    "subtitle",
    "job_queue",
    "ocr",
    "documents",
    "media",
    "photos",
    "auto_organizer",
    "assistant_trace",
    "copy_plan",
    "backup",
    "snapshot",
    "journal",
    "ops",
    "audit",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def compact_timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def http_get_json(base_url: str, path: str, timeout: int) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    started = time.perf_counter()
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1024 * 1024).decode("utf-8", errors="replace")
            payload = json.loads(raw)
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "path": path,
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(8192).decode("utf-8", errors="replace")
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:1000]}
        return {
            "ok": False,
            "status": exc.code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "path": path,
            "payload": payload,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "path": path,
            "payload": {},
            "error": f"{type(exc).__name__}:{exc}",
        }


def has_raw_path(payload: Any) -> bool:
    return bool(RAW_PATH_RE.search(json.dumps(payload, ensure_ascii=False)))


def add_failure(failures: list[str], condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def build_payload(base_url: str, timeout: int) -> dict[str, Any]:
    checks = {
        "health": http_get_json(base_url, "/api/health", timeout),
        "product_status": http_get_json(base_url, "/api/product/status", timeout),
        "product_evidence": http_get_json(base_url, "/api/product/evidence/latest", timeout),
        "harness": http_get_json(base_url, "/api/harness/status", timeout),
        "yolo_status": http_get_json(base_url, "/api/yolo-index/status", timeout),
        "multimodal_status": http_get_json(base_url, "/api/multimodal-search/status", timeout),
        "person_attribute_status": http_get_json(base_url, "/api/person-attribute/status", timeout),
        "ai_space_status": http_get_json(base_url, "/api/ai-space/status", timeout),
        "smart_classification_status": http_get_json(base_url, "/api/smart-classification/status", timeout),
        "smart_naming_status": http_get_json(base_url, "/api/smart-naming/status", timeout),
        "auto_organizer_status": http_get_json(base_url, "/api/auto-organize/status", timeout),
        "assistant_trace_status": http_get_json(base_url, "/api/assistant/trace/status", timeout),
        "subtitle_status": http_get_json(base_url, "/api/subtitle/status", timeout),
        "jobs_status": http_get_json(base_url, "/api/jobs/status", timeout),
    }

    failures: list[str] = []
    warnings: list[str] = []

    for name, check in checks.items():
        add_failure(failures, bool(check.get("ok")), f"{name}_http_failed:{check.get('status')}:{check.get('error')}")

    health = checks["health"].get("payload") or {}
    product = checks["product_status"].get("payload") or {}
    evidence = checks["product_evidence"].get("payload") or {}
    harness = checks["harness"].get("payload") or {}
    yolo = checks["yolo_status"].get("payload") or {}
    multimodal = checks["multimodal_status"].get("payload") or {}
    person_attribute = checks["person_attribute_status"].get("payload") or {}
    ai_space = checks["ai_space_status"].get("payload") or {}
    smart = checks["smart_classification_status"].get("payload") or {}
    smart_naming = checks["smart_naming_status"].get("payload") or {}
    auto_organizer = checks["auto_organizer_status"].get("payload") or {}
    assistant_trace = checks["assistant_trace_status"].get("payload") or {}
    subtitle = checks["subtitle_status"].get("payload") or {}
    jobs = checks["jobs_status"].get("payload") or {}

    modules = product.get("modules") if isinstance(product.get("modules"), dict) else {}
    missing_modules = sorted(REQUIRED_MODULES - set(modules))
    failed_modules = sorted(name for name, item in modules.items() if isinstance(item, dict) and item.get("status") == "failed")
    degraded_modules = sorted(name for name, item in modules.items() if isinstance(item, dict) and item.get("status") == "degraded")
    if degraded_modules:
        warnings.append("degraded_modules:" + ",".join(degraded_modules))

    add_failure(failures, bool(health.get("ok")), "health_not_ok")
    add_failure(failures, bool(product.get("ok")), "product_status_not_ok")
    add_failure(failures, (product.get("overall") or {}).get("production_ready") is True, "production_readiness_not_ready")
    add_failure(failures, not missing_modules, "product_status_missing_modules:" + ",".join(missing_modules))
    add_failure(failures, not failed_modules, "product_status_failed_modules:" + ",".join(failed_modules))
    add_failure(failures, bool(evidence.get("ok")) and int(evidence.get("report_count") or 0) > 0, "product_evidence_empty")
    add_failure(failures, not has_raw_path(product), "product_status_raw_path_leak")
    add_failure(failures, not has_raw_path(evidence), "product_evidence_raw_path_leak")

    privacy = product.get("privacy_boundary") if isinstance(product.get("privacy_boundary"), dict) else {}
    add_failure(failures, privacy.get("cloud_private_raw_egress") is False, "cloud_private_raw_egress_not_false")
    add_failure(failures, privacy.get("qwen_execution_authority") is False, "qwen_execution_authority_not_false")
    add_failure(failures, privacy.get("cloud_vision_enabled") is False, "cloud_vision_enabled_not_false")
    add_failure(failures, privacy.get("cloud_asr_enabled") is False, "cloud_asr_enabled_not_false")
    add_failure(failures, privacy.get("face_identification_enabled") is False, "face_identification_enabled_not_false")
    add_failure(failures, privacy.get("biometric_recognition_enabled") is False, "biometric_recognition_enabled_not_false")
    add_failure(failures, privacy.get("sensitive_attribute_inference_enabled") is False, "sensitive_attribute_inference_enabled_not_false")
    add_failure(failures, privacy.get("raw_path_returned") is False, "product_status_raw_path_flag_not_false")
    controlled_boundary = privacy.get("controlled_move_rename_boundary") if isinstance(privacy.get("controlled_move_rename_boundary"), dict) else {}
    add_failure(failures, controlled_boundary.get("controlled_move_enabled") is True, "controlled_move_boundary_not_true")
    add_failure(failures, controlled_boundary.get("controlled_rename_enabled") is True, "controlled_rename_boundary_not_true")
    add_failure(failures, controlled_boundary.get("uncontrolled_move_enabled") is False, "uncontrolled_move_boundary_not_false")
    add_failure(failures, controlled_boundary.get("uncontrolled_rename_enabled") is False, "uncontrolled_rename_boundary_not_false")
    add_failure(failures, controlled_boundary.get("delete_enabled") is False, "controlled_boundary_delete_not_false")
    add_failure(failures, controlled_boundary.get("overwrite_enabled") is False, "controlled_boundary_overwrite_not_false")

    add_failure(failures, bool(harness.get("ok")), "harness_status_not_ok")
    add_failure(failures, harness.get("qwen_execution_authority") is False, "harness_qwen_execution_authority_not_false")
    add_failure(failures, harness.get("cloud_private_raw_egress") is False, "harness_cloud_private_raw_egress_not_false")
    add_failure(failures, harness.get("controlled_move_enabled") is True, "harness_controlled_move_not_true")
    add_failure(failures, harness.get("controlled_rename_enabled") is True, "harness_controlled_rename_not_true")
    add_failure(failures, harness.get("uncontrolled_move_enabled") is False, "harness_uncontrolled_move_not_false")
    add_failure(failures, harness.get("uncontrolled_rename_enabled") is False, "harness_uncontrolled_rename_not_false")
    add_failure(failures, harness.get("delete_enabled") is False, "harness_delete_not_false")
    add_failure(failures, harness.get("overwrite_enabled") is False, "harness_overwrite_not_false")
    add_failure(failures, harness.get("auto_organizer_required_for_move_rename") is True, "harness_auto_organizer_required_not_true")
    forbidden = set(harness.get("forbidden_actions") or [])
    for action in ("delete", "overwrite", "recursive", "arbitrary_shell"):
        add_failure(failures, action in forbidden, f"harness_forbidden_action_missing:{action}")

    yolo_backend = yolo.get("backend") if isinstance(yolo.get("backend"), dict) else {}
    add_failure(failures, bool(yolo.get("ok")), "yolo_status_not_ok")
    add_failure(failures, yolo_backend.get("runtime_target") == "s100p_bpu_hbm", "yolo_runtime_not_s100p_bpu_hbm")
    add_failure(failures, int(yolo.get("indexed_count") or 0) > 0, "yolo_indexed_count_empty")
    if int(yolo.get("detection_count") or 0) <= 0:
        warnings.append("yolo_detection_count_empty_real_s100p_backend_completed_without_boxes")
    add_failure(failures, yolo.get("cloud_used") is False, "yolo_cloud_used_not_false")
    add_failure(failures, int(yolo.get("raw_path_rows") or 0) == 0, "yolo_raw_path_rows_nonzero")
    add_failure(failures, int(yolo.get("private_leak_count") or 0) == 0, "yolo_private_leak_nonzero")

    add_failure(failures, bool(multimodal.get("ok")), "multimodal_status_not_ok")
    add_failure(failures, multimodal.get("cloud_used") is False, "multimodal_cloud_used_not_false")
    add_failure(failures, int(multimodal.get("private_leak_count") or 0) == 0, "multimodal_private_leak_nonzero")
    add_failure(failures, multimodal.get("degraded") is False, "multimodal_degraded")
    add_failure(failures, int(multimodal.get("production_semantic_embedding_count") or 0) >= 5, "multimodal_production_embeddings_below_min")

    add_failure(failures, bool(person_attribute.get("ok")), "person_attribute_status_not_ok")
    if person_attribute.get("degraded") is not False:
        warnings.append("person_attribute_degraded_without_yolo_person_boxes")
    if int(person_attribute.get("person_detection_count") or 0) <= 0:
        warnings.append("person_attribute_detection_count_empty")
    add_failure(failures, person_attribute.get("face_identification_enabled") is False, "person_attribute_face_identification_not_false")
    add_failure(failures, person_attribute.get("biometric_recognition_enabled") is False, "person_attribute_biometric_not_false")
    add_failure(failures, person_attribute.get("sensitive_attribute_inference_enabled") is False, "person_attribute_sensitive_inference_not_false")
    add_failure(failures, person_attribute.get("cloud_used") is False, "person_attribute_cloud_used_not_false")
    add_failure(failures, person_attribute.get("raw_path_returned") is False, "person_attribute_raw_path_not_false")

    add_failure(failures, bool(ai_space.get("ok")), "ai_space_status_not_ok")
    add_failure(failures, ai_space.get("degraded") is False, "ai_space_degraded")
    add_failure(failures, int(ai_space.get("asset_count") or 0) >= 10, "ai_space_asset_count_below_min")
    add_failure(failures, ai_space.get("cloud_used") is False, "ai_space_cloud_used_not_false")
    add_failure(failures, ai_space.get("raw_path_returned") is False, "ai_space_raw_path_not_false")

    add_failure(failures, bool(smart.get("ok")), "smart_classification_status_not_ok")
    add_failure(failures, smart.get("degraded") is False, "smart_classification_degraded")
    add_failure(failures, int(smart.get("category_count") or 0) >= 5, "smart_classification_category_count_below_min")
    add_failure(failures, int(smart.get("hit_category_count") or 0) >= 3, "smart_classification_hit_category_count_below_min")
    add_failure(failures, smart.get("physical_file_moved") is False, "smart_classification_physical_move_not_false")
    add_failure(failures, bool(smart_naming.get("ok")), "smart_naming_status_not_ok")
    add_failure(failures, int(smart_naming.get("name_count") or 0) > 0, "smart_naming_count_empty")
    add_failure(failures, smart_naming.get("physical_file_renamed") is False, "smart_naming_physical_rename_not_false")
    add_failure(failures, smart_naming.get("cloud_used") is False, "smart_naming_cloud_used_not_false")

    add_failure(failures, bool(auto_organizer.get("ok")), "auto_organizer_status_not_ok")
    add_failure(failures, auto_organizer.get("controlled_move_enabled") is True, "auto_organizer_controlled_move_not_true")
    add_failure(failures, auto_organizer.get("controlled_rename_enabled") is True, "auto_organizer_controlled_rename_not_true")
    add_failure(failures, auto_organizer.get("uncontrolled_move_enabled") is False, "auto_organizer_uncontrolled_move_not_false")
    add_failure(failures, auto_organizer.get("uncontrolled_rename_enabled") is False, "auto_organizer_uncontrolled_rename_not_false")
    add_failure(failures, auto_organizer.get("delete_enabled") is False, "auto_organizer_delete_not_false")
    add_failure(failures, auto_organizer.get("overwrite_enabled") is False, "auto_organizer_overwrite_not_false")
    add_failure(failures, auto_organizer.get("rollback_required") is True, "auto_organizer_rollback_required_not_true")
    add_failure(failures, auto_organizer.get("qwen_execution_authority") is False, "auto_organizer_qwen_execution_authority_not_false")
    add_failure(failures, auto_organizer.get("cloud_private_raw_egress") is False, "auto_organizer_cloud_private_raw_egress_not_false")
    add_failure(failures, auto_organizer.get("raw_path_returned") is False, "auto_organizer_raw_path_not_false")

    add_failure(failures, bool(assistant_trace.get("ok")), "assistant_trace_status_not_ok")
    add_failure(failures, assistant_trace.get("hidden_chain_of_thought_saved") is False, "assistant_trace_hidden_cot_not_false")
    add_failure(failures, assistant_trace.get("raw_path_returned") is False, "assistant_trace_raw_path_not_false")
    add_failure(failures, assistant_trace.get("cloud_private_raw_egress") is False, "assistant_trace_cloud_private_raw_egress_not_false")
    add_failure(failures, assistant_trace.get("qwen_execution_authority") is False, "assistant_trace_qwen_execution_authority_not_false")
    required_trace_steps = {"received", "qwen_router", "privacy_tokenizer", "task_classifier", "route_decision", "token_budget", "tool_execution", "safety_gate", "evidence_summary", "final_answer"}
    add_failure(failures, required_trace_steps.issubset(set(assistant_trace.get("required_steps") or [])), "assistant_trace_required_steps_missing")

    add_failure(failures, bool(subtitle.get("ok")), "subtitle_status_not_ok")
    add_failure(failures, subtitle.get("degraded") is False, "subtitle_degraded")
    add_failure(failures, int(subtitle.get("segment_count") or 0) > 0, "subtitle_segment_count_empty")
    add_failure(failures, subtitle.get("cloud_used") is False, "subtitle_cloud_used_not_false")
    add_failure(failures, subtitle.get("raw_path_returned") is False, "subtitle_raw_path_not_false")
    add_failure(failures, subtitle.get("fixture_only_for_ci") is False, "subtitle_fixture_used")

    add_failure(failures, bool(jobs.get("ok")), "jobs_status_not_ok")

    verdict = OK_VERDICT if not failures else FAILED_VERDICT
    return {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "ok": verdict == OK_VERDICT,
        "base_url": base_url,
        "summary": {
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "required_module_count": len(REQUIRED_MODULES),
            "observed_module_count": len(modules),
            "degraded_modules": degraded_modules,
            "yolo_runtime_target": yolo_backend.get("runtime_target"),
            "yolo_detection_count": yolo.get("detection_count"),
            "multimodal_embedding_count": multimodal.get("embedding_count"),
            "ai_space_asset_count": ai_space.get("asset_count"),
            "smart_category_count": smart.get("category_count"),
            "smart_name_count": smart_naming.get("name_count"),
            "auto_organizer_plan_count": auto_organizer.get("plan_count"),
            "assistant_trace_count_visible": assistant_trace.get("trace_count_visible"),
            "subtitle_segment_count": subtitle.get("segment_count"),
            "production_ready": (product.get("overall") or {}).get("production_ready"),
            "readiness_verdict": (product.get("overall") or {}).get("readiness_verdict"),
        },
        "failures": failures,
        "warnings": warnings,
        "checks": checks,
        "audit": {
            "method": "HTTP GET smoke only",
            "source_files_modified": False,
            "personal_source_modified": False,
            "service_restart_performed": False,
            "delete_performed": False,
            "uncontrolled_move_performed": False,
            "overwrite_performed": False,
            "writes": "product smoke JSON/Markdown report only",
        },
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Product Smoke Test",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- base_url: `{payload['base_url']}`",
        f"- failure_count: `{payload['summary']['failure_count']}`",
        f"- warning_count: `{payload['summary']['warning_count']}`",
        f"- production_ready: `{payload['summary']['production_ready']}`",
        f"- readiness_verdict: `{payload['summary']['readiness_verdict']}`",
        f"- yolo_runtime_target: `{payload['summary']['yolo_runtime_target']}`",
        f"- yolo_detection_count: `{payload['summary']['yolo_detection_count']}`",
        "",
        "## Failures",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload["failures"]) if payload["failures"] else lines.append("- None.")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- `{item}`" for item in payload["warnings"]) if payload["warnings"] else lines.append("- None.")
    lines.extend(["", "## Endpoints", ""])
    for name, check in payload["checks"].items():
        lines.append(f"- `{name}` {check.get('status')} {check.get('elapsed_ms')}ms `{check.get('path')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run product-level live HTTP smoke tests against the AI-NAS portal.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--report-root", type=Path, default=Path("reports/product_delivery"))
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    payload = build_payload(args.base_url, args.timeout)
    run_dir = args.report_root / f"product_smoke_test_{compact_timestamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    json_path = run_dir / "product_smoke_test.json"
    md_path = run_dir / "product_smoke_test.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown(payload), encoding="utf-8")
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
