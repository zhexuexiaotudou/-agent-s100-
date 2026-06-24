#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_official_route_readiness_gate"
READY_VERDICT = "ready_ai_nas_official_route_readiness_gate"
BLOCKED_VERDICT = "blocked_ai_nas_official_route_readiness_gate"


EXPECTED = {
    "qwen25_ai_nas_acceptance.json": "ok_qwen25_ai_nas_acceptance_packet",
    "official_vision_route_packet.json": "ok_ai_nas_official_vision_route_demo_ready",
    "official_ppocr_wrapper.json": "ok_ai_nas_official_ppocr_wrapper",
    "ocr_runtime_contract.json": "ok_ai_nas_ocr_runtime_contract",
    "document_pipeline_acceptance.json": "ok_ai_nas_document_pipeline_acceptance",
    "photo_pipeline_acceptance.json": "ok_ai_nas_photo_pipeline_acceptance",
    "operator_portal_contract.json": "ok_ai_nas_operator_portal_contract",
    "action_manifest_integrity.json": "ok_ai_nas_action_manifest_integrity",
    "destructive_action_governance.json": "ok_ai_nas_destructive_action_governance",
    "audit_trail_contract_report.json": "ok_ai_nas_audit_trail_contract",
    "appliance_experience_acceptance.json": "ok_ai_nas_appliance_experience_acceptance",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def parse_time(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path) or {}
    generated_at = parse_time(str(payload.get("generated_at") or ""))
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return generated_at, mtime, str(path)


def latest_report(roots: list[Path], filename: str) -> dict[str, Any]:
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            candidates.extend(path for path in root.rglob(filename) if path.is_file())
        except OSError:
            continue
    if not candidates:
        return {"found": False, "filename": filename, "path": "", "verdict": None, "payload": None}
    expected = EXPECTED.get(filename)
    accepted_candidates = []
    if expected:
        for path in candidates:
            payload = read_json(path) or {}
            if payload.get("verdict") == expected:
                accepted_candidates.append(path)
    selected = max(accepted_candidates or candidates, key=report_sort_key)
    payload = read_json(selected)
    return {
        "found": payload is not None,
        "filename": filename,
        "path": str(selected),
        "verdict": payload.get("verdict") if payload else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "payload": payload,
    }


def ok(report: dict[str, Any], expected: str | None = None) -> bool:
    if expected is None:
        expected = EXPECTED.get(str(report.get("filename")))
    return bool(report.get("found") and expected and report.get("verdict") == expected)


def compact(report: dict[str, Any]) -> dict[str, Any]:
    return {key: report.get(key) for key in ["found", "filename", "path", "verdict", "generated_at"]}


def official_ppocr_state(vision: dict[str, Any], wrapper: dict[str, Any]) -> dict[str, Any]:
    payload = vision.get("payload") or {}
    candidates = payload.get("model_candidates") if isinstance(payload.get("model_candidates"), list) else []
    ocr = next((item for item in candidates if item.get("capability") == "ocr_screenshot_recognition"), {})
    deployment_status = str(ocr.get("deployment_status") or "")
    hbm_verified = "hbm_model_info_verified" in deployment_status
    wrapper_payload = wrapper.get("payload") or {}
    remote = wrapper_payload.get("remote_result") if isinstance(wrapper_payload.get("remote_result"), dict) else {}
    wrapper_ready = ok(wrapper) and bool(remote.get("ok")) and bool(remote.get("predictions"))
    return {
        "model": ocr.get("model"),
        "det_hbm": ocr.get("board_model_file"),
        "rec_hbm": ocr.get("alternate_model_file"),
        "deployment_status": deployment_status,
        "hbm_model_info_verified": hbm_verified,
        "wrapper_ready": wrapper_ready,
        "wrapper_report": compact(wrapper),
        "wrapper_prediction_count": len(remote.get("predictions") or []),
        "wrapper_result_image_exists": ((remote.get("result_image") or {}).get("exists")),
        "first_release_role": ocr.get("first_release_role"),
        "source": ocr.get("source"),
    }


def build_payload(roots: list[Path]) -> dict[str, Any]:
    reports = {name: latest_report(roots, name) for name in EXPECTED}
    blockers: list[str] = []
    warnings: list[str] = []

    for filename, expected in EXPECTED.items():
        if not ok(reports[filename], expected):
            blockers.append(f"{filename}:expected_{expected}_missing_or_not_current")

    qwen_payload = reports["qwen25_ai_nas_acceptance.json"].get("payload") or {}
    qwen_health = qwen_payload.get("health") if isinstance(qwen_payload.get("health"), dict) else {}
    qwen_chat = qwen_payload.get("chat") if isinstance(qwen_payload.get("chat"), dict) else {}
    if qwen_health.get("status") != 200 or qwen_chat.get("status") != 200:
        blockers.append("qwen25_gateway_health_or_chat_not_200")

    vision_payload = reports["official_vision_route_packet.json"].get("payload") or {}
    vision_evidence = vision_payload.get("evidence") if isinstance(vision_payload.get("evidence"), dict) else {}
    image_boxes = int((((vision_evidence.get("s100p_yolo_image") or {}).get("log") or {}).get("box_count")) or 0)
    video_boxes = int((((vision_evidence.get("s100p_video_frame") or {}).get("log") or {}).get("box_count")) or 0)
    if image_boxes <= 0 or video_boxes <= 0:
        blockers.append("official_s100_yolo_image_or_video_boxes_missing")

    ocr_payload = reports["ocr_runtime_contract.json"].get("payload") or {}
    ocr_smoke = (ocr_payload.get("smoke") or {}).get("scanned_image_ocr") or {}
    if not (ocr_payload.get("production_ocr_ready") and ocr_smoke.get("status") == "ocr_completed"):
        blockers.append("ocr_runtime_smoke_not_completed")

    ppocr = official_ppocr_state(
        reports["official_vision_route_packet.json"],
        reports["official_ppocr_wrapper.json"],
    )
    if not ppocr["hbm_model_info_verified"]:
        blockers.append("official_ppocr_hbm_model_info_not_verified")
    if not ppocr["wrapper_ready"]:
        blockers.append("official_ppocr_wrapper_pending")

    doc_payload = reports["document_pipeline_acceptance.json"].get("payload") or {}
    doc_ocr_results = doc_payload.get("ocr_results") if isinstance(doc_payload.get("ocr_results"), list) else []
    if not any(item.get("status") == "ocr_completed" and item.get("text_preview") for item in doc_ocr_results):
        warnings.append("document_pipeline_fixture_has_no_completed_ocr_result_on_windows; s100p_ocr_runtime_contract_supplies_current_ocr_smoke")

    verdict = READY_VERDICT if not blockers else BLOCKED_VERDICT
    return {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "ok": verdict == READY_VERDICT,
        "scope": "current official AI-NAS model route readiness for Qwen2.5 text, S100 vision, OCR runtime, safe actions, and unified portal",
        "active_route": {
            "text": "Qwen2.5 official local gateway",
            "vision": "Official S100 YOLO image/video-frame route",
            "ocr_runtime": "S100P local OCR runtime smoke",
            "official_ocr_target": "Official S100 PP-OCRv3 det/rec HBM wrapper",
        },
        "summary": {
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "qwen_health_status": qwen_health.get("status"),
            "qwen_chat_status": qwen_chat.get("status"),
            "vision_image_box_count": image_boxes,
            "vision_video_box_count": video_boxes,
            "ocr_smoke_status": ocr_smoke.get("status"),
            "official_ppocr_hbm_model_info_verified": ppocr["hbm_model_info_verified"],
            "official_ppocr_wrapper_ready": ppocr["wrapper_ready"],
        },
        "official_ppocr": ppocr,
        "reports": {name: compact(report) for name, report in reports.items()},
        "blockers": blockers,
        "warnings": warnings,
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_restart_performed": False,
            "writes": "JSON/Markdown official route readiness report only",
        },
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# AI-NAS Official Route Readiness Gate",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- blocker_count: `{payload['summary']['blocker_count']}`",
        f"- warning_count: `{payload['summary']['warning_count']}`",
        f"- qwen_health_status: `{payload['summary']['qwen_health_status']}`",
        f"- qwen_chat_status: `{payload['summary']['qwen_chat_status']}`",
        f"- vision_image_box_count: `{payload['summary']['vision_image_box_count']}`",
        f"- vision_video_box_count: `{payload['summary']['vision_video_box_count']}`",
        f"- ocr_smoke_status: `{payload['summary']['ocr_smoke_status']}`",
        f"- official_ppocr_wrapper_ready: `{payload['summary']['official_ppocr_wrapper_ready']}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload["blockers"]) if payload["blockers"] else lines.append("- None.")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- `{item}`" for item in payload["warnings"]) if payload["warnings"] else lines.append("- None.")
    lines.extend(["", "## Evidence", ""])
    for name, report in payload["reports"].items():
        lines.append(f"- `{name}` `{report.get('verdict')}`: `{report.get('path')}`")
    return "\n".join(lines) + "\n"


def default_roots(report_root: Path) -> list[Path]:
    return [
        report_root,
        Path("tmp"),
        Path("tmp/ai_nas_product_closure"),
        Path("tmp/ai_nas_product_closure/remote_s100p"),
        Path("tmp/product_guardrail_snapshots"),
        Path("tmp/ai_nas_official_vision_20260623"),
        Path("tmp/ai_nas_competition_delivery"),
        Path("tmp/remote_production_evidence"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Current official Qwen2.5 + S100 vision/OCR AI-NAS readiness gate.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_closure"))
    parser.add_argument("--evidence-root", type=Path, action="append", default=[])
    args = parser.parse_args()
    roots = args.evidence_root or default_roots(args.report_root)
    payload = build_payload(roots)
    run_dir = ensure_report_dir(args.report_root, "official_route_readiness_gate")
    json_path = run_dir / "official_route_readiness_gate.json"
    md_path = run_dir / "official_route_readiness_gate.md"
    safe_write_json(json_path, payload)
    safe_write_text(md_path, markdown(payload))
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
