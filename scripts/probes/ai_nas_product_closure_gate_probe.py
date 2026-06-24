#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_product_closure_gate"
OK_VERDICT = "ok_ai_nas_product_closure_gate"
BLOCKED_VERDICT = "blocked_ai_nas_product_closure_gate"


EXPECTED_VERDICTS = {
    "qwen25_ai_nas_acceptance.json": "ok_qwen25_ai_nas_acceptance_packet",
    "official_vision_route_packet.json": "ok_ai_nas_official_vision_route_demo_ready",
    "competition_final_acceptance.json": "ok_ai_nas_competition_final_acceptance",
    "official_route_readiness_gate.json": "ready_ai_nas_official_route_readiness_gate",
    "ocr_runtime_contract.json": "ok_ai_nas_ocr_runtime_contract",
    "document_pipeline_acceptance.json": "ok_ai_nas_document_pipeline_acceptance",
    "photo_pipeline_acceptance.json": "ok_ai_nas_photo_pipeline_acceptance",
    "action_manifest_integrity.json": "ok_ai_nas_action_manifest_integrity",
    "destructive_action_governance.json": "ok_ai_nas_destructive_action_governance",
    "audit_trail_contract_report.json": "ok_ai_nas_audit_trail_contract",
    "appliance_experience_acceptance.json": "ok_ai_nas_appliance_experience_acceptance",
    "operator_portal_contract.json": "ok_ai_nas_operator_portal_contract",
    "production_readiness_gate.json": "ready_ai_nas_production_readiness_gate",
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
    generated_at = parse_time(str(payload.get("generated_at") or payload.get("generated_at_utc") or ""))
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
    expected = EXPECTED_VERDICTS.get(filename)
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


def report_ok(report: dict[str, Any], expected: str | None = None) -> bool:
    if not report.get("found"):
        return False
    if expected is None:
        expected = EXPECTED_VERDICTS.get(str(report.get("filename")))
    return bool(expected and report.get("verdict") == expected)


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "found": bool(report.get("found")),
        "filename": report.get("filename"),
        "path": report.get("path"),
        "verdict": report.get("verdict"),
        "generated_at": report.get("generated_at"),
    }


def item(
    requirement_id: str,
    area: str,
    status: str,
    evidence: list[dict[str, Any]],
    blockers: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "area": area,
        "status": status,
        "evidence": [compact_report(entry) for entry in evidence],
        "blockers": blockers or [],
        "notes": notes or [],
    }


def qwen_requirement(qwen: dict[str, Any], competition: dict[str, Any]) -> dict[str, Any]:
    payload = qwen.get("payload") or {}
    health = payload.get("health") if isinstance(payload.get("health"), dict) else {}
    models = payload.get("models") if isinstance(payload.get("models"), dict) else {}
    chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
    ok = report_ok(qwen) and health.get("status") == 200 and models.get("status") == 200 and chat.get("status") == 200
    blockers = []
    if not ok:
        blockers.append("official_qwen_text_gateway_acceptance_not_current_ok")
    return item(
        "official_qwen_text_entry",
        "Official Qwen2.5 text model and OpenAI-compatible AI-NAS entry",
        "satisfied" if ok else "missing_or_failed_evidence",
        [qwen, competition],
        blockers,
        [
            f"base_url={payload.get('base_url')}",
            f"chat_elapsed_ms={(chat or {}).get('elapsed_ms')}",
        ],
    )


def vision_requirement(vision: dict[str, Any]) -> dict[str, Any]:
    payload = vision.get("payload") or {}
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    image_log = ((evidence.get("s100p_yolo_image") or {}).get("log") or {})
    video_log = ((evidence.get("s100p_video_frame") or {}).get("log") or {})
    image_boxes = int(image_log.get("box_count") or 0)
    video_boxes = int(video_log.get("box_count") or 0)
    ok = report_ok(vision) and image_boxes > 0 and video_boxes > 0
    blockers = []
    if not ok:
        blockers.append("official_vision_image_or_video_detection_not_verified")
    return item(
        "official_vision_image_video",
        "Official S100 vision route for image and video-frame recognition",
        "satisfied" if ok else "missing_or_failed_evidence",
        [vision],
        blockers,
        [f"image_box_count={image_boxes}", f"video_frame_box_count={video_boxes}"],
    )


def document_requirement(document: dict[str, Any], ocr_runtime: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = document.get("payload") or {}
    ocr_results = payload.get("ocr_results") if isinstance(payload.get("ocr_results"), list) else []
    ocr_completed = [entry for entry in ocr_results if entry.get("status") == "ocr_completed" and entry.get("text_preview")]
    ocr_blocked = [entry for entry in ocr_results if entry.get("status") == "blocked_missing_ocr_engine"]
    doc_ok = report_ok(document)
    doc_item = item(
        "document_summary_qa",
        "Document extraction, grounded summary, and folder question answering",
        "satisfied" if doc_ok else "missing_or_failed_evidence",
        [document],
        [] if doc_ok else ["document_pipeline_acceptance_not_ok"],
        [
            f"document_record_count={payload.get('document_record_count')}",
            f"folder_rag_status={(payload.get('folder_rag') or {}).get('answer_status')}",
        ],
    )
    ocr_runtime_payload = ocr_runtime.get("payload") or {}
    ocr_smoke = (ocr_runtime_payload.get("smoke") or {}).get("scanned_image_ocr") or {}
    ocr_runtime_completed = (
        report_ok(ocr_runtime)
        and ocr_runtime_payload.get("production_ocr_ready") is True
        and ocr_smoke.get("status") == "ocr_completed"
        and bool(str(ocr_smoke.get("text_preview") or "").strip())
    )
    if ocr_completed or ocr_runtime_completed:
        status = "satisfied"
        blockers: list[str] = []
    elif doc_ok and ocr_blocked:
        status = "limited_evidence"
        blockers = ["ocr_candidate_detected_but_no_runtime_completed_text_extraction"]
    else:
        status = "missing_or_failed_evidence"
        blockers = ["ocr_extraction_completion_not_verified"]
    ocr_item = item(
        "ocr_text_extraction",
        "OCR text extraction for scanned PDFs/images without invented content",
        status,
        [document, ocr_runtime],
        blockers,
        [
            f"ocr_completed_count={len(ocr_completed)}",
            f"ocr_blocked_count={len(ocr_blocked)}",
            f"ocr_ready={((payload.get('runtime') or {}).get('ocr') or {}).get('ocr_ready')}",
            f"s100p_ocr_runtime_completed={ocr_runtime_completed}",
            f"s100p_ocr_engine={ocr_smoke.get('engine')}",
        ],
    )
    return doc_item, ocr_item


def photo_requirement(photo: dict[str, Any], vision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = photo.get("payload") or {}
    similarity = payload.get("similarity") if isinstance(payload.get("similarity"), dict) else {}
    search = payload.get("search") if isinstance(payload.get("search"), dict) else {}
    runtime = ((payload.get("runtime") or {}).get("image_embedding") or {})
    photo_ok = report_ok(photo)
    photo_item = item(
        "photo_semantic_pipeline",
        "Photo metadata, pHash/local visual embeddings, and grounded semantic photo search",
        "satisfied" if photo_ok else "missing_or_failed_evidence",
        [photo, vision],
        [] if photo_ok else ["photo_pipeline_acceptance_not_ok"],
        [
            f"photo_count={(payload.get('metadata') or {}).get('photo_count')}",
            f"production_clip_ready={runtime.get('production_clip_ready')}",
            "face_recognition_claimed=false",
        ],
    )
    dup_ok = bool(similarity.get("passed")) and report_ok(photo)
    duplicate_item = item(
        "duplicate_similar_analysis",
        "Duplicate/similar file analysis without automatic deletion",
        "satisfied" if dup_ok else "missing_or_failed_evidence",
        [photo],
        [] if dup_ok else ["photo_similarity_or_duplicate_evidence_missing"],
        [
            f"similar_group_count={similarity.get('group_count')}",
            f"photo_search_passed={search.get('passed')}",
        ],
    )
    return photo_item, duplicate_item


def safe_ops_requirement(
    manifest_integrity: dict[str, Any],
    destructive_governance: dict[str, Any],
    audit_trail: dict[str, Any],
    appliance: dict[str, Any],
) -> dict[str, Any]:
    required = [manifest_integrity, destructive_governance, appliance]
    ok = all(report_ok(report) for report in required)
    audit_ok = report_ok(audit_trail) if audit_trail.get("found") else False
    blockers = []
    if not ok:
        blockers.append("approval_manifest_or_destructive_governance_or_appliance_acceptance_missing")
    if not audit_ok:
        blockers.append("hash_chained_audit_trail_contract_missing_or_not_ok")
    status = "satisfied" if ok and audit_ok else "limited_evidence" if ok else "missing_or_failed_evidence"
    return item(
        "safe_organize_audit_execution",
        "Safe organizing suggestions, confirmation-gated copy execution, rollback, and audit trail",
        status,
        [manifest_integrity, destructive_governance, audit_trail, appliance],
        blockers,
        ["delete_move_overwrite_default=false", "copy_execution_requires_exact_approval_phrase=true"],
    )


def unified_entry_requirement(qwen: dict[str, Any], portal: dict[str, Any]) -> dict[str, Any]:
    qwen_ok = report_ok(qwen)
    portal_ok = report_ok(portal)
    portal_text = json.dumps(portal.get("payload") or {}, ensure_ascii=False).lower()
    portal_current_route = ("qwen25" in portal_text or "qwen2.5" in portal_text) and (
        "official_vision" in portal_text or "s100 vision" in portal_text or "yolo" in portal_text
    )
    if qwen_ok and portal_ok and portal_current_route:
        status = "satisfied"
        blockers: list[str] = []
    elif qwen_ok:
        status = "limited_evidence"
        blockers = ["operator_portal_contract_missing_or_not_refreshed_for_current_official_qwen_vision_route"]
    else:
        status = "missing_or_failed_evidence"
        blockers = ["qwen_entry_missing", "operator_portal_contract_missing"]
    return item(
        "unified_openclaw_web_entry",
        "Unified OpenClaw/web entry that surfaces grounded reports and operator actions",
        status,
        [qwen, portal],
        blockers,
        ["Qwen gateway covers text entry; portal contract covers web/operator report entry."],
    )


def traceability_requirement(competition: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    competition_ok = report_ok(competition)
    readiness_payload = readiness.get("payload") or {}
    readiness_ok = report_ok(readiness)
    if competition_ok and readiness_ok:
        status = "satisfied"
        blockers: list[str] = []
    elif competition_ok:
        status = "limited_evidence"
        blockers = list(readiness_payload.get("blockers") or []) or [
            "official_route_readiness_gate_not_ready"
        ]
    else:
        status = "missing_or_failed_evidence"
        blockers = ["competition_final_acceptance_missing_or_not_ok"]
    return item(
        "traceability_and_release_gate",
        "End-to-end traceability from objective to current official-route readiness",
        status,
        [competition, readiness],
        blockers,
        ["Competition acceptance is not equivalent to full product closure."],
    )


def build_payload(roots: list[Path]) -> dict[str, Any]:
    reports = {filename: latest_report(roots, filename) for filename in EXPECTED_VERDICTS}
    qwen = reports["qwen25_ai_nas_acceptance.json"]
    vision = reports["official_vision_route_packet.json"]
    competition = reports["competition_final_acceptance.json"]
    route_readiness = reports["official_route_readiness_gate.json"]
    ocr_runtime = reports["ocr_runtime_contract.json"]
    document = reports["document_pipeline_acceptance.json"]
    photo = reports["photo_pipeline_acceptance.json"]
    manifest_integrity = reports["action_manifest_integrity.json"]
    destructive = reports["destructive_action_governance.json"]
    audit_trail = reports["audit_trail_contract_report.json"]
    appliance = reports["appliance_experience_acceptance.json"]
    portal = reports["operator_portal_contract.json"]

    document_item, ocr_item = document_requirement(document, ocr_runtime)
    photo_item, duplicate_item = photo_requirement(photo, vision)
    matrix = [
        qwen_requirement(qwen, competition),
        vision_requirement(vision),
        document_item,
        ocr_item,
        photo_item,
        duplicate_item,
        safe_ops_requirement(manifest_integrity, destructive, audit_trail, appliance),
        unified_entry_requirement(qwen, portal),
        traceability_requirement(competition, route_readiness),
    ]
    blockers = [
        f"{row['id']}:{blocker}"
        for row in matrix
        for blocker in row.get("blockers", [])
        if row.get("status") != "satisfied"
    ]
    satisfied = [row for row in matrix if row["status"] == "satisfied"]
    limited = [row for row in matrix if row["status"] == "limited_evidence"]
    missing = [row for row in matrix if row["status"] == "missing_or_failed_evidence"]
    verdict = OK_VERDICT if len(satisfied) == len(matrix) else BLOCKED_VERDICT
    return {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "ok": verdict == OK_VERDICT,
        "scope": "strict product-closure gate for the official Qwen2.5 + official S100 vision/OCR AI-NAS Copilot objective",
        "evidence_roots": [str(root) for root in roots],
        "summary": {
            "requirement_count": len(matrix),
            "satisfied_count": len(satisfied),
            "limited_count": len(limited),
            "missing_or_failed_count": len(missing),
            "blocker_count": len(blockers),
        },
        "requirement_matrix": matrix,
        "blockers": blockers,
        "reports": {name: compact_report(report) for name, report in reports.items()},
        "claim_boundary": {
            "competition_demo_ready": report_ok(competition),
            "full_product_closure_ready": verdict == OK_VERDICT,
            "residual_not_claimed": [
                "production CLIP/person/photo semantics",
                "full NAS OS replacement",
                "automatic delete/move/overwrite cleanup",
                "permission-complete multi-user NAS parity",
            ],
        },
        "next_required_work": [
            blocker for blocker in blockers
        ],
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_restart_performed": False,
            "writes": "JSON/Markdown product closure gate report only",
        },
    }


def write_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# AI-NAS Product Closure Gate",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- satisfied: `{payload['summary']['satisfied_count']}/{payload['summary']['requirement_count']}`",
        f"- limited: `{payload['summary']['limited_count']}`",
        f"- missing_or_failed: `{payload['summary']['missing_or_failed_count']}`",
        f"- blocker_count: `{payload['summary']['blocker_count']}`",
        "",
        "## Requirement Matrix",
        "",
        "| id | status | area | blockers |",
        "|---|---:|---|---|",
    ]
    for row in payload["requirement_matrix"]:
        blockers = "<br>".join(row.get("blockers") or [])
        lines.append(f"| `{row['id']}` | `{row['status']}` | {row['area']} | {blockers} |")
    lines.extend(["", "## Evidence", ""])
    for row in payload["requirement_matrix"]:
        lines.append(f"### {row['id']}")
        for report in row.get("evidence", []):
            if report.get("found"):
                lines.append(f"- `{report.get('filename')}` `{report.get('verdict')}`: `{report.get('path')}`")
            else:
                lines.append(f"- missing `{report.get('filename')}`")
        for note in row.get("notes", []):
            lines.append(f"- note: {note}")
        lines.append("")
    lines.extend(["## Next Required Work", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in payload["blockers"])
    else:
        lines.append("- No blockers.")
    lines.extend(["", "## Claim Boundary", ""])
    for key, value in payload["claim_boundary"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [
        report_root,
        Path("tmp"),
        Path("tmp/product_guardrail_snapshots"),
        Path("tmp/ai_nas_official_vision_20260623"),
        Path("tmp/ai_nas_competition_delivery"),
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict AI-NAS product closure gate for the official Qwen2.5 and S100 vision route.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_closure"))
    parser.add_argument("--evidence-root", type=Path, action="append", default=[])
    args = parser.parse_args()

    roots = args.evidence_root or default_evidence_roots(args.report_root)
    payload = build_payload(roots)
    run_dir = ensure_report_dir(args.report_root, "product_closure_gate")
    json_path = run_dir / "product_closure_gate.json"
    md_path = run_dir / "product_closure_gate.md"
    safe_write_json(json_path, payload)
    safe_write_text(md_path, write_markdown(payload))
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
