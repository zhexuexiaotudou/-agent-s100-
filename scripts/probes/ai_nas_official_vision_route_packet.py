#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_official_vision_route_packet"


OFFICIAL_MODEL_CANDIDATES = [
    {
        "capability": "image_object_detection",
        "selected": True,
        "model": "YOLOv8 / YOLO11 via dnn_node_example",
        "board_model_file": "/opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm",
        "alternate_model_file": "/opt/hobot/model/s100/basic/yolo11m_detect_nashe_640x640_nv12.hbm",
        "runtime_entry": "ros2 launch dnn_node_example dnn_node_example_feedback.launch.py",
        "reason": "Official S100 HBM already installed; TROS dnn_node_example has ready config and COCO postprocess.",
        "deployment_status": "verified_inference_on_s100p",
        "first_release_role": "primary image and video-frame detector",
        "source": "https://github.com/D-Robotics/rdk_model_zoo_s",
    },
    {
        "capability": "image_classification",
        "selected": True,
        "model": "MobileNetV2 / ResNet family",
        "board_model_file": "/opt/hobot/model/s100/basic/mobilenetv2_224x224_nv12.hbm",
        "runtime_entry": "dnn_node_example classification parser",
        "reason": "Official S100 classification HBM and ImageNet labels are installed; low-risk fallback for screenshots/photos.",
        "deployment_status": "model_info_verified_on_s100p",
        "first_release_role": "secondary classification tagger",
        "source": "https://github.com/D-Robotics/rdk_model_zoo_s/tree/main/samples/Vision/ResNet",
    },
    {
        "capability": "ocr_screenshot_recognition",
        "selected": True,
        "model": "PP-OCRv3 det + rec",
        "board_model_file": "/opt/hobot/model/s100/basic/cn_PP-OCRv3_det_infer-deploy_640x640_nv12.hbm",
        "alternate_model_file": "/opt/hobot/model/s100/basic/cn_PP-OCRv3_rec_infer-deploy_48x320_rgb.hbm",
        "runtime_entry": "PaddleOCR sample packaging or thin Python/C++ wrapper around det/rec HBM",
        "reason": "Official S100 OCR HBM files load with hrt_model_exec; best fit for screenshot and document-image text.",
        "deployment_status": "hbm_model_info_verified_wrapper_pending",
        "first_release_role": "OCR contract target; local AI-NAS OCR probe remains fallback until wrapper lands",
        "source": "https://github.com/D-Robotics/rdk_model_zoo_s/tree/main/samples/Vision/PaddleOCR",
    },
    {
        "capability": "image_semantic_retrieval",
        "selected": True,
        "model": "CLIP ViT-B/32 on NAS plus local_visual_embedding_v1 fallback",
        "board_model_file": "/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32/pytorch_model.bin",
        "runtime_entry": "AI-NAS image embedding extract/search probes",
        "reason": "NAS already has CLIP model files; existing AI-NAS probes produce grounded JSON/Markdown evidence.",
        "deployment_status": "nas_model_files_present_local_fallback_verified",
        "first_release_role": "semantic retrieval/indexing; keep fallback limitations explicit",
        "source": "local NAS model cache plus scripts/probes/ai_nas_image_embedding_extract_probe.py",
    },
    {
        "capability": "video_understanding",
        "selected": False,
        "model": "3D/video model family",
        "board_model_file": None,
        "runtime_entry": None,
        "reason": "Higher integration risk; first release only extracts frames and reuses image detector/OCR/classifier.",
        "deployment_status": "deferred",
        "first_release_role": "not in first NodeHub submission",
        "source": "https://github.com/D-Robotics/rdk_model_zoo_s",
    },
]


RUN_COMMANDS = {
    "photo_pipeline": (
        "py scripts\\probes\\ai_nas_photo_pipeline_acceptance_probe.py "
        "--report-root F:\\Project\\Digua\\tmp\\ai_nas_official_vision_20260623"
    ),
    "document_ocr_pipeline": (
        "py scripts\\probes\\ai_nas_document_pipeline_acceptance_probe.py "
        "--report-root F:\\Project\\Digua\\tmp\\ai_nas_official_vision_20260623"
    ),
    "image_embedding": (
        "py scripts\\probes\\ai_nas_image_embedding_extract_probe.py "
        "--personal-root <Personal> --sqlite-index-path <index.sqlite3>"
    ),
    "photo_semantic_search": (
        "py scripts\\probes\\ai_nas_photo_semantic_search_probe.py "
        "\"white car invoice screenshot beach\" --personal-root <Personal> "
        "--sqlite-index-path <index.sqlite3> --no-refresh-index"
    ),
    "s100p_yolo_image": (
        "ssh sunrise@192.168.127.10 \"source /opt/tros/humble/setup.bash; "
        "mkdir -p /tmp/ai_nas_yolo_demo && cd /tmp/ai_nas_yolo_demo; "
        "timeout 20 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py "
        "dnn_example_config_file:=config/yolov8workconfig.json "
        "dnn_example_image:=config/test.jpg\""
    ),
    "s100p_video_frame": (
        "ssh sunrise@192.168.127.10 \"ffmpeg -i input.mp4 -vf fps=1 frames/frame_%03d.jpg; "
        "source /opt/tros/humble/setup.bash; cd /tmp/ai_nas_video_frame_demo/run; "
        "timeout 20 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py "
        "dnn_example_config_file:=config/yolov8workconfig.json "
        "dnn_example_image:=/tmp/ai_nas_video_frame_demo/frames/frame_001.jpg\""
    ),
}


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"missing": False, "path": str(path), "json_error": str(exc)}


def latest_json(root: Path, pattern: str) -> Path | None:
    matches = sorted(root.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def parse_yolo_log(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "status": "missing"}
    text = path.read_text(encoding="utf-8", errors="replace")
    detections = []
    for line in text.splitlines():
        match = re.search(r"det type: ([^,]+), score:([0-9.]+)", line)
        if match:
            detections.append({"type": match.group(1).strip(), "score": float(match.group(2))})
    box_match = re.search(r"out box size: (\d+)", text)
    model_match = re.search(r"model_file_name: ([^\n]+)", text)
    render_drawn = "Draw result to file" in text
    return {
        "path": str(path),
        "status": "completed" if detections else "no_detections_or_unparsed",
        "model_file_name": model_match.group(1).strip() if model_match else None,
        "box_count": int(box_match.group(1)) if box_match else len(detections),
        "detections": detections,
        "render_drawn": render_drawn,
    }


def file_state(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


def collect_evidence(report_root: Path) -> dict:
    photo_json = latest_json(report_root, "photo_pipeline_acceptance_*/photo_pipeline_acceptance.json")
    document_json = latest_json(report_root, "document_pipeline_acceptance_*/document_pipeline_acceptance.json")
    embedding_json = latest_json(report_root, "image_embedding_extract_*/image_embedding_extract.json")
    search_json = latest_json(report_root, "photo_semantic_search_*/photo_semantic_search.json")
    image_log = report_root / "s100p_yolo_image_demo" / "ai_nas_yolov8_demo_writable.log"
    image_render = report_root / "s100p_yolo_image_demo" / "render_feedback_0_0.jpeg"
    video_log = report_root / "s100p_video_frame_demo" / "yolov8_frame.log"
    video_render = report_root / "s100p_video_frame_demo" / "run" / "render_feedback_0_0.jpeg"
    video_file = report_root / "s100p_video_frame_demo" / "sample.mp4"
    video_frames = sorted((report_root / "s100p_video_frame_demo" / "frames").glob("frame_*.jpg"))
    return {
        "photo_pipeline": load_json(photo_json) if photo_json else {"missing": True},
        "document_ocr_pipeline": load_json(document_json) if document_json else {"missing": True},
        "image_embedding": load_json(embedding_json) if embedding_json else {"missing": True},
        "photo_semantic_search": load_json(search_json) if search_json else {"missing": True},
        "s100p_yolo_image": {
            "log": parse_yolo_log(image_log),
            "render": file_state(image_render),
        },
        "s100p_video_frame": {
            "video": file_state(video_file),
            "frames": [file_state(path) for path in video_frames],
            "log": parse_yolo_log(video_log),
            "render": file_state(video_render),
        },
    }


def verdict_from_evidence(evidence: dict) -> tuple[str, list[str], list[str]]:
    failures = []
    risks = []
    if evidence["photo_pipeline"].get("verdict") != "ok_ai_nas_photo_pipeline_acceptance":
        failures.append("photo_pipeline_not_ok")
    if evidence["document_ocr_pipeline"].get("verdict") != "ok_ai_nas_document_pipeline_acceptance":
        failures.append("document_ocr_pipeline_not_ok")
    if evidence["image_embedding"].get("verdict") != "ok_ai_nas_image_embedding_extract":
        failures.append("image_embedding_not_ok")
    if evidence["photo_semantic_search"].get("match_count", 0) <= 0:
        failures.append("photo_semantic_search_no_match")
    if evidence["s100p_yolo_image"]["log"].get("box_count", 0) <= 0:
        failures.append("s100p_yolo_image_no_boxes")
    if not evidence["s100p_yolo_image"]["render"].get("exists"):
        failures.append("s100p_yolo_image_render_missing")
    if evidence["s100p_video_frame"]["log"].get("box_count", 0) <= 0:
        failures.append("s100p_video_frame_no_boxes")
    if not evidence["s100p_video_frame"]["render"].get("exists"):
        failures.append("s100p_video_frame_render_missing")
    if len(evidence["s100p_video_frame"].get("frames") or []) <= 0:
        failures.append("video_frames_missing")
    if not evidence["s100p_video_frame"]["video"].get("exists"):
        failures.append("video_file_missing")

    document_runtime = (evidence["document_ocr_pipeline"].get("runtime") or {}).get("ocr") or {}
    if document_runtime.get("ocr_ready") is False:
        risks.append("windows_fixture_ocr_engine_missing; official PP-OCRv3 HBM is available on S100P but wrapper remains pending")
    embedding_runtime = evidence["image_embedding"].get("runtime") or {}
    if embedding_runtime.get("production_clip_ready") is False:
        risks.append("local Windows CLIP runtime not installed; NAS CLIP files exist, local_visual_embedding_v1 used for plumbing evidence")
    risks.append("sunrise user could not write /mnt/nas/openclaw/reports/ai_nas_mvp during this run; local tmp evidence retained")
    verdict = "ok_ai_nas_official_vision_route_demo_ready" if not failures else "blocked_ai_nas_official_vision_route"
    return verdict, failures, risks


def write_markdown(path: Path, payload: dict) -> None:
    evidence = payload["evidence"]
    lines = [
        "# AI-NAS Official Vision Route Packet",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- report_root: `{payload['report_root']}`",
        "- boundary: no Dream7B optimization, no text service port/service changes, video uses frame extraction first",
        "",
        "## Selected Route",
        "",
    ]
    for item in payload["model_candidates"]:
        mark = "selected" if item["selected"] else "deferred"
        lines.append(f"- {item['capability']}: `{mark}` | {item['model']} | status `{item['deployment_status']}`")
        lines.append(f"  - role: {item['first_release_role']}")
        lines.append(f"  - reason: {item['reason']}")
        if item.get("board_model_file"):
            lines.append(f"  - model_file: `{item['board_model_file']}`")
    lines.extend(["", "## Evidence", ""])
    lines.append(f"- photo_pipeline_verdict: `{evidence['photo_pipeline'].get('verdict')}`")
    lines.append(f"- document_pipeline_verdict: `{evidence['document_ocr_pipeline'].get('verdict')}`")
    lines.append(f"- image_embedding_verdict: `{evidence['image_embedding'].get('verdict')}`")
    lines.append(f"- semantic_search_match_count: `{evidence['photo_semantic_search'].get('match_count')}`")
    lines.append(
        f"- s100p_yolo_image_boxes: `{evidence['s100p_yolo_image']['log'].get('box_count')}` "
        f"render `{evidence['s100p_yolo_image']['render'].get('path')}`"
    )
    lines.append(
        f"- s100p_video_frame_boxes: `{evidence['s100p_video_frame']['log'].get('box_count')}` "
        f"frames `{len(evidence['s100p_video_frame'].get('frames') or [])}` "
        f"render `{evidence['s100p_video_frame']['render'].get('path')}`"
    )
    lines.extend(["", "## Demo Commands", ""])
    for key, command in payload["run_commands"].items():
        lines.append(f"- {key}:")
        lines.append(f"  ```powershell\n  {command}\n  ```")
    lines.extend(["", "## Acceptance", ""])
    lines.append(f"- failures: `{payload['failures']}`")
    lines.append(f"- remaining_risks: `{payload['remaining_risks']}`")
    lines.append("- OpenClaw/AI-NAS integration contract: call these probes or wrap them behind a non-text `ai-nas-vision-*` service name; return JSON paths plus Markdown evidence links.")
    safe_write_text(path, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build official S100P vision route evidence packet for AI-NAS.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_official_vision_20260623"))
    args = parser.parse_args()

    report_root = args.report_root.resolve()
    run_dir = ensure_report_dir(report_root, "official_vision_route_packet")
    evidence = collect_evidence(report_root)
    verdict, failures, risks = verdict_from_evidence(evidence)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "report_root": str(report_root),
        "model_candidates": OFFICIAL_MODEL_CANDIDATES,
        "run_commands": RUN_COMMANDS,
        "evidence": evidence,
        "failures": failures,
        "remaining_risks": risks,
        "nodehub_submission_boundary": {
            "text_route_modified": False,
            "dream7b_optimization_continued": False,
            "service_name_recommendation": "ai-nas-vision-gateway / ai-nas-video-frame-worker",
            "video_first_release": "extract frames, then run image detector/OCR/classifier; no video LLM in first release",
        },
        "audit": {
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_source_files": False,
            "writes": "Markdown/JSON official vision route packet only",
        },
    }
    json_path = run_dir / "official_vision_route_packet.json"
    md_path = run_dir / "official_vision_route_packet.md"
    safe_write_json(json_path, payload)
    write_markdown(md_path, payload)
    print(md_path)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
