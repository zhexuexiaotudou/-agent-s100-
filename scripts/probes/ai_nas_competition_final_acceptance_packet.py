#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_competition_final_acceptance_packet"


DEFAULT_QWEN_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_VISION_ROOT = Path("tmp/ai_nas_official_vision_20260623")
DEFAULT_REPORT_ROOT = Path("tmp/ai_nas_competition_delivery")


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"missing": True, "path": ""}
    if not path.exists():
        return {"missing": True, "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "missing": False,
            "path": str(path),
            "json_error": f"{type(exc).__name__}: {exc}",
        }
    if isinstance(payload, dict):
        payload.setdefault("_path", str(path))
        return payload
    return {"missing": False, "path": str(path), "json_error": "top_level_not_object"}


def latest_file(root: Path, pattern: str) -> Path | None:
    matches = [path for path in root.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def file_state(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {"path": "", "exists": False, "size_bytes": 0}
    path = Path(path_value)
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
    }


def compact_report_paths(qwen: dict[str, Any]) -> list[dict[str, Any]]:
    reports = qwen.get("reports")
    if not isinstance(reports, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in reports:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "path": item.get("path", ""),
                "exists": bool(item.get("exists")),
                "verdict": item.get("verdict"),
                "answer_status": item.get("answer_status"),
                "summary": item.get("summary"),
            }
        )
    return compact


def extract_qwen_summary(qwen: dict[str, Any]) -> dict[str, Any]:
    health = qwen.get("health") if isinstance(qwen.get("health"), dict) else {}
    models = qwen.get("models") if isinstance(qwen.get("models"), dict) else {}
    chat = qwen.get("chat") if isinstance(qwen.get("chat"), dict) else {}
    runtime_1024 = qwen.get("official_qwen_1024_runtime_probe")
    if not isinstance(runtime_1024, dict):
        runtime_1024 = {}
    health_json = health.get("json") if isinstance(health.get("json"), dict) else {}
    return {
        "source_path": qwen.get("_path") or qwen.get("path", ""),
        "verdict": qwen.get("verdict"),
        "base_url": qwen.get("base_url"),
        "model_id": health_json.get("model"),
        "service_port": health_json.get("port"),
        "active_profile": health_json.get("active_profile"),
        "priority_profile": health_json.get("priority_profile"),
        "priority_status": health_json.get("priority_status"),
        "health_status": health.get("status"),
        "models_status": models.get("status"),
        "chat_status": chat.get("status"),
        "chat_elapsed_ms": chat.get("elapsed_ms"),
        "errors": qwen.get("errors") if isinstance(qwen.get("errors"), list) else [],
        "report_paths": compact_report_paths(qwen),
        "qwen_1024_boundary": {
            "path": runtime_1024.get("path"),
            "runtime_completed": runtime_1024.get("runtime_completed"),
            "runtime_returncode": runtime_1024.get("runtime_returncode"),
            "hbm_load_success_observed": runtime_1024.get("hbm_load_success_observed"),
            "init_model_success_observed": runtime_1024.get("init_model_success_observed"),
            "memory_alloc_failure_observed": runtime_1024.get("memory_alloc_failure_observed"),
            "qwen_hbm_path": runtime_1024.get("qwen_hbm_path"),
            "warnings": runtime_1024.get("warnings"),
        },
    }


def extract_vision_summary(vision: dict[str, Any]) -> dict[str, Any]:
    evidence = vision.get("evidence") if isinstance(vision.get("evidence"), dict) else {}
    yolo_image = evidence.get("s100p_yolo_image") if isinstance(evidence.get("s100p_yolo_image"), dict) else {}
    yolo_video = evidence.get("s100p_video_frame") if isinstance(evidence.get("s100p_video_frame"), dict) else {}
    image_log = yolo_image.get("log") if isinstance(yolo_image.get("log"), dict) else {}
    video_log = yolo_video.get("log") if isinstance(yolo_video.get("log"), dict) else {}
    image_render = yolo_image.get("render") if isinstance(yolo_image.get("render"), dict) else {}
    video_render = yolo_video.get("render") if isinstance(yolo_video.get("render"), dict) else {}
    frames = yolo_video.get("frames") if isinstance(yolo_video.get("frames"), list) else []
    return {
        "source_path": vision.get("_path") or vision.get("path", ""),
        "verdict": vision.get("verdict"),
        "failures": vision.get("failures") if isinstance(vision.get("failures"), list) else [],
        "remaining_risks": vision.get("remaining_risks")
        if isinstance(vision.get("remaining_risks"), list)
        else [],
        "image_detection": {
            "model_file_name": image_log.get("model_file_name"),
            "box_count": image_log.get("box_count"),
            "detections": image_log.get("detections"),
            "render": image_render,
        },
        "video_frame_detection": {
            "model_file_name": video_log.get("model_file_name"),
            "box_count": video_log.get("box_count"),
            "detections": video_log.get("detections"),
            "frame_count": len(frames),
            "render": video_render,
        },
        "photo_pipeline_verdict": (evidence.get("photo_pipeline") or {}).get("verdict")
        if isinstance(evidence.get("photo_pipeline"), dict)
        else None,
        "document_pipeline_verdict": (evidence.get("document_ocr_pipeline") or {}).get("verdict")
        if isinstance(evidence.get("document_ocr_pipeline"), dict)
        else None,
        "image_embedding_verdict": (evidence.get("image_embedding") or {}).get("verdict")
        if isinstance(evidence.get("image_embedding"), dict)
        else None,
        "photo_semantic_search_match_count": (evidence.get("photo_semantic_search") or {}).get(
            "match_count"
        )
        if isinstance(evidence.get("photo_semantic_search"), dict)
        else None,
    }


def build_payload(qwen: dict[str, Any], vision: dict[str, Any], qwen_path: Path | None, vision_path: Path | None) -> dict[str, Any]:
    qwen_summary = extract_qwen_summary(qwen)
    vision_summary = extract_vision_summary(vision)
    failures: list[str] = []
    warnings: list[str] = []

    if qwen_summary["verdict"] != "ok_qwen25_ai_nas_acceptance_packet":
        failures.append("qwen_text_route_not_ok")
    if qwen_summary["health_status"] != 200:
        failures.append("qwen_gateway_health_not_200")
    if qwen_summary["models_status"] != 200:
        failures.append("qwen_models_not_200")
    if qwen_summary["chat_status"] != 200:
        failures.append("qwen_ai_nas_chat_not_200")
    if qwen_summary["errors"]:
        failures.append("qwen_acceptance_errors_present")

    if vision_summary["verdict"] != "ok_ai_nas_official_vision_route_demo_ready":
        failures.append("vision_route_not_ok")
    if vision_summary["failures"]:
        failures.append("vision_failures_present")
    if not vision_summary["image_detection"]["box_count"]:
        failures.append("vision_image_detection_missing_boxes")
    if not vision_summary["video_frame_detection"]["box_count"]:
        failures.append("vision_video_detection_missing_boxes")

    qwen_boundary = qwen_summary["qwen_1024_boundary"]
    if qwen_boundary.get("memory_alloc_failure_observed"):
        warnings.append(
            "official Qwen 1024 HBM exists and initializes, but current S100P run is blocked by BPU/common-buffer allocation; 512/128 profile is the demo baseline"
        )
    warnings.extend(vision_summary["remaining_risks"])

    verdict = "ok_ai_nas_competition_final_acceptance" if not failures else "blocked_ai_nas_competition_final_acceptance"
    return {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "goal": "competition-ready AI-NAS delivery integrating official Qwen2.5 text entry and official S100 vision route",
        "source_packets": {
            "qwen_text": str(qwen_path) if qwen_path else "",
            "official_vision": str(vision_path) if vision_path else "",
        },
        "competition_story": {
            "title": "AI-NAS Copilot on RDK S100",
            "one_liner": "Use RDK S100 as a local AI layer for a low-cost NAS: official Qwen2.5 handles the text entry, official S100 vision models handle image/video evidence, and OpenClaw/allowlisted tools produce auditable reports.",
            "platform": "RDK S100 / S100P plus NAS plus OpenClaw allowlisted tools",
            "not_claimed": [
                "Dream7B production model readiness",
                "1024-token Qwen HBM runtime completion on the current S100P memory layout",
                "production OCR wrapper completion",
                "full video-language model understanding",
                "automatic deletion, move, overwrite, or destructive NAS action",
            ],
        },
        "qwen_text_route": qwen_summary,
        "official_vision_route": vision_summary,
        "demo_flow": [
            "Start from a Chinese user request through Qwen2.5 gateway at http://127.0.0.1:18080/v1.",
            "Route NAS evidence requests to allowlisted AI-NAS probes.",
            "Return Markdown/JSON evidence paths for inventory, evidence report, case packet, and folder RAG.",
            "Run official S100 YOLO on a NAS image or extracted video frame.",
            "Attach detection render images and structured report paths to the final operator evidence packet.",
        ],
        "nodehub_submission": {
            "required_files": [
                "README.md",
                "docs/competition_delivery_2026-06-23.md",
                "docs/nodehub_submission_package_2026-06-23.md",
                "docs/qwen25_ai_nas_text_entry_2026-06-23.md",
                "docs/ai_nas_official_vision_route_2026-06-23.md",
                "scripts/qwen25_openai_gateway.py",
                "scripts/probes/qwen25_ai_nas_acceptance_packet.py",
                "scripts/probes/ai_nas_official_vision_route_packet.py",
                "scripts/probes/ai_nas_competition_final_acceptance_packet.py",
                "configs/systemd/qwen25-local-openai-gateway.service",
                "configs/qwen25_official_route_policy.json",
                "configs/qwen25_512_multichat_config.json",
            ],
            "demo_assets": [
                vision_summary["image_detection"]["render"].get("path"),
                vision_summary["video_frame_detection"]["render"].get("path"),
            ],
        },
        "run_commands": {
            "qwen_health": "curl -sS http://127.0.0.1:18080/health",
            "qwen_models": "curl -sS http://127.0.0.1:18080/v1/models",
            "qwen_acceptance": "py -3 scripts\\probes\\qwen25_ai_nas_acceptance_packet.py",
            "vision_acceptance": "py -3 scripts\\probes\\ai_nas_official_vision_route_packet.py --report-root tmp\\ai_nas_official_vision_20260623",
            "final_acceptance": "py -3 scripts\\probes\\ai_nas_competition_final_acceptance_packet.py",
        },
        "failures": failures,
        "warnings": warnings,
        "ok": not failures,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    qwen = payload["qwen_text_route"]
    vision = payload["official_vision_route"]
    lines = [
        "# AI-NAS Competition Final Acceptance",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- title: {payload['competition_story']['title']}",
        f"- one_liner: {payload['competition_story']['one_liner']}",
        "",
        "## Text Route",
        "",
        f"- model_id: `{qwen.get('model_id')}`",
        f"- base_url: `{qwen.get('base_url')}`",
        f"- service_port: `{qwen.get('service_port')}`",
        f"- active_profile: `{qwen.get('active_profile')}`",
        f"- verdict: `{qwen.get('verdict')}`",
        f"- chat_elapsed_ms: `{qwen.get('chat_elapsed_ms')}`",
        f"- source_packet: `{qwen.get('source_path')}`",
        "",
        "## Vision Route",
        "",
        f"- verdict: `{vision.get('verdict')}`",
        f"- image_model: `{vision['image_detection'].get('model_file_name')}`",
        f"- image_boxes: `{vision['image_detection'].get('box_count')}`",
        f"- image_render: `{vision['image_detection']['render'].get('path')}`",
        f"- video_boxes: `{vision['video_frame_detection'].get('box_count')}`",
        f"- video_frame_count: `{vision['video_frame_detection'].get('frame_count')}`",
        f"- video_render: `{vision['video_frame_detection']['render'].get('path')}`",
        f"- source_packet: `{vision.get('source_path')}`",
        "",
        "## Demo Flow",
        "",
    ]
    lines.extend(f"1. {item}" for item in payload["demo_flow"])
    lines.extend(["", "## Commands", ""])
    for name, command in payload["run_commands"].items():
        lines.append(f"- {name}: `{command}`")
    lines.extend(["", "## Evidence Packets", ""])
    for name, source in payload["source_packets"].items():
        lines.append(f"- {name}: `{source}`")
    lines.extend(["", "## Submission Files", ""])
    for item in payload["nodehub_submission"]["required_files"]:
        lines.append(f"- `{item}`")
    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in payload["warnings"])
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {item}" for item in payload["failures"])
    safe_write_text(path, "\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the final AI-NAS competition acceptance packet.")
    parser.add_argument("--qwen-root", type=Path, default=DEFAULT_QWEN_ROOT)
    parser.add_argument("--vision-root", type=Path, default=DEFAULT_VISION_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    qwen_path = latest_file(args.qwen_root, "qwen25_ai_nas_acceptance_*/qwen25_ai_nas_acceptance.json")
    vision_path = latest_file(args.vision_root, "official_vision_route_packet_*/official_vision_route_packet.json")
    qwen = load_json(qwen_path)
    vision = load_json(vision_path)
    payload = build_payload(qwen, vision, qwen_path, vision_path)
    run_dir = ensure_report_dir(args.report_root, "competition_final_acceptance")
    json_path = run_dir / "competition_final_acceptance.json"
    md_path = run_dir / "competition_final_acceptance.md"
    payload["acceptance_paths"] = {"json": str(json_path), "md": str(md_path)}
    safe_write_json(json_path, payload)
    write_markdown(md_path, payload)
    print(json_path)
    print(md_path)
    print(payload["verdict"])
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

