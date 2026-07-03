#!/usr/bin/env python3
"""S100 grounded vision gateway for AI-NAS.

This service exposes three private HTTP contracts used by the portal:

- POST /ocr: PP-OCRv3 HBM text extraction
- POST /region: YOLOv8 HBM detections plus CV upper-clothing color attributes
- POST /chat/completions: OpenAI-compatible grounded captions built from the
  same detector/OCR evidence

It intentionally does not claim VLM inference. Captions are grounded summaries
derived from object detections, OCR, and bounded color analysis.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_CACHE_ROOT = Path(os.environ.get("AI_NAS_S100_GROUNDED_VISION_CACHE", "/tmp/ai_nas_s100_grounded_vision_gateway"))
YOLO_MODEL = Path("/opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm")
PPOCR_SAMPLE = Path("/app/pydev_demo/08_OCR_sample/01_paddleOCR")
PPOCR_UTILS = Path("/app/pydev_demo/utils")
PPOCR_DET_MODEL = Path("/opt/hobot/model/s100/basic/cn_PP-OCRv3_det_infer-deploy_640x640_nv12.hbm")
PPOCR_REC_MODEL = Path("/opt/hobot/model/s100/basic/cn_PP-OCRv3_rec_infer-deploy_48x320_rgb.hbm")
PPOCR_LABEL_FILE = Path("/app/res/labels/ppocr_keys_v1.txt")

REGION_MODEL_ID = "s100p-yolov8n-hbm-cv-region-v1"
OCR_MODEL_ID = "s100p-ppocrv3-hbm"
CAPTION_MODEL_ID = "s100p-grounded-caption-yolo-ppocr-v1"


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _decode_data_url(value: str) -> tuple[bytes, str]:
    text = str(value or "")
    if "," not in text or not text.startswith("data:"):
        raise ValueError("image_url.url must be a data URL")
    meta, data = text.split(",", 1)
    mime = meta.split(";", 1)[0].replace("data:", "") or "application/octet-stream"
    return base64.b64decode(data), mime


def _write_paddle_stub(root: Path) -> None:
    paddle_root = root / "paddle"
    nn_root = paddle_root / "nn"
    nn_root.mkdir(parents=True, exist_ok=True)
    (paddle_root / "__init__.py").write_text(
        """class Tensor:
    pass

def to_tensor(x, dtype=None):
    return x

def zeros(*args, **kwargs):
    raise RuntimeError("paddle stub zeros unavailable for this sample path")

def concat(*args, **kwargs):
    raise RuntimeError("paddle stub concat unavailable for this sample path")

def exp(x):
    return x

def log(x):
    return x
""",
        encoding="utf-8",
    )
    (nn_root / "__init__.py").write_text("", encoding="utf-8")
    (nn_root / "functional.py").write_text(
        """def softmax(x, axis=None):
    return x
""",
        encoding="utf-8",
    )


def _clamp_bbox(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> list[float]:
    xa = max(0.0, min(float(width), float(x1)))
    ya = max(0.0, min(float(height), float(y1)))
    xb = max(0.0, min(float(width), float(x2)))
    yb = max(0.0, min(float(height), float(y2)))
    if xb < xa:
        xa, xb = xb, xa
    if yb < ya:
        ya, yb = yb, ya
    return [round(xa, 3), round(ya, 3), round(xb, 3), round(yb, 3)]


def _bbox_to_xywh(box: list[float]) -> list[float]:
    if len(box) < 4:
        return []
    x1, y1, x2, y2 = box[:4]
    return [round(x1, 3), round(y1, 3), round(max(0.0, x2 - x1), 3), round(max(0.0, y2 - y1), 3)]


def _parse_yolo_log(text: str, image_width: int, image_height: int) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    pattern = re.compile(
        r"det rect:\s*([0-9.+-]+)\s+([0-9.+-]+)\s+([0-9.+-]+)\s+([0-9.+-]+),\s*"
        r"det type:\s*([^,]+),\s*score:([0-9.+-]+)"
    )
    for match in pattern.finditer(text):
        x1, y1, x2, y2 = (float(match.group(i)) for i in range(1, 5))
        label = match.group(5).strip().lower()
        score = float(match.group(6))
        xyxy = _clamp_bbox(x1, y1, x2, y2, image_width, image_height)
        detections.append(
            {
                "label": label,
                "bbox_xyxy": xyxy,
                "bbox": _bbox_to_xywh(xyxy),
                "confidence": score,
                "source": "official_s100p_yolov8_hbm_log",
            }
        )
    return detections


def _classify_rgb(r: float, g: float, b: float) -> str:
    import colorsys

    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0
    hue, sat, val = colorsys.rgb_to_hsv(rn, gn, bn)
    if val >= 0.78 and sat <= 0.22:
        return "white"
    if val <= 0.18:
        return "black"
    if sat <= 0.20:
        return "gray"
    deg = hue * 360.0
    if deg < 18 or deg >= 345:
        return "red"
    if deg < 45:
        return "orange"
    if deg < 72:
        return "yellow"
    if deg < 165:
        return "green"
    if deg < 255:
        return "blue"
    if deg < 292:
        return "purple"
    if deg < 345:
        return "pink"
    return "unknown"


def _dominant_color_for_crop(image_path: Path, box_xyxy: list[float]) -> dict[str, Any]:
    from PIL import Image

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    x1, y1, x2, y2 = _clamp_bbox(*box_xyxy[:4], width, height)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return {"color": "unknown", "confidence": 0.0, "counts": {}, "sampled_pixels": 0}
    crop = image.crop((int(x1), int(y1), int(x2), int(y2))).resize((32, 32))
    counts: dict[str, int] = {}
    sampled = 0
    for r, g, b in crop.getdata():
        color = _classify_rgb(float(r), float(g), float(b))
        if color == "unknown":
            continue
        counts[color] = counts.get(color, 0) + 1
        sampled += 1
    if not counts or sampled <= 0:
        return {"color": "unknown", "confidence": 0.0, "counts": counts, "sampled_pixels": sampled}
    color, count = max(counts.items(), key=lambda item: item[1])
    confidence = max(0.05, min(0.95, count / max(1, sampled)))
    return {"color": color, "confidence": round(confidence, 4), "counts": counts, "sampled_pixels": sampled}


def _upper_clothing_box(person_xyxy: list[float], width: int, height: int) -> list[float]:
    x1, y1, x2, y2 = person_xyxy[:4]
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    return _clamp_bbox(
        x1 + 0.16 * w,
        y1 + 0.20 * h,
        x2 - 0.16 * w,
        y1 + 0.52 * h,
        width,
        height,
    )


def _caption_from_analysis(regions: list[dict[str, Any]], ocr_text: str) -> dict[str, Any]:
    object_counts: dict[str, int] = {}
    people: list[dict[str, Any]] = []
    upper_colors: list[str] = []
    for region in regions:
        label = str(region.get("label") or "")
        kind = str(region.get("region_kind") or "")
        if kind == "object" or kind == "person":
            object_counts[label] = object_counts.get(label, 0) + 1
        if kind == "upper_clothing":
            attrs = region.get("attributes") or []
            color = ""
            for attr in attrs:
                if attr.get("namespace") == "upper_clothing" and attr.get("name") == "color":
                    color = str(attr.get("value") or "")
                    break
            if color:
                upper_colors.append(color)
                people.append(
                    {
                        "type": "generic_person",
                        "clothing": {"upper_color": color, "upper_garment": "top"},
                        "evidence_terms": ["person", f"{color} top", f"{color} upper clothing"],
                    }
                )
    objects = [
        {"label": label, "count": count}
        for label, count in sorted(object_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    fragments: list[str] = []
    if objects:
        fragments.append(
            "Detected " + ", ".join(f"{item['count']} {item['label']}" for item in objects[:6]) + "."
        )
    if upper_colors:
        fragments.append("Upper clothing colors include " + ", ".join(sorted(set(upper_colors))) + ".")
    if ocr_text.strip():
        fragments.append("Visible text is present.")
    if not fragments:
        fragments.append("No high-confidence object or text evidence was extracted.")
    return {
        "caption": " ".join(fragments),
        "objects": objects,
        "people": people,
        "attributes": {
            "object_counts": object_counts,
            "upper_clothing_colors": sorted(set(upper_colors)),
            "grounding": "official_s100p_yolov8_hbm_plus_ppocrv3_hbm_plus_cv_color",
        },
        "scene": "unknown",
        "visible_text": [line for line in ocr_text.splitlines() if line.strip()],
        "model_id": CAPTION_MODEL_ID,
    }


class GroundedVisionRuntime:
    def __init__(self, cache_root: Path, yolo_timeout: int, ocr_timeout: int) -> None:
        self.cache_root = Path(cache_root)
        self.image_root = self.cache_root / "images"
        self.request_root = self.cache_root / "requests"
        self.ppocr_root = self.cache_root / "ppocr_runtime"
        self.yolo_timeout = yolo_timeout
        self.ocr_timeout = ocr_timeout
        self.cache: dict[str, dict[str, Any]] = {}
        self.cache_lock = threading.Lock()
        self.yolo_lock = threading.Lock()
        self.ocr_lock = threading.Lock()
        self.ppocr_ready = False

    def setup(self) -> None:
        self.image_root.mkdir(parents=True, exist_ok=True)
        self.request_root.mkdir(parents=True, exist_ok=True)
        self.ppocr_root.mkdir(parents=True, exist_ok=True)

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "ready": bool(YOLO_MODEL.exists() and PPOCR_SAMPLE.exists() and PPOCR_UTILS.exists() and PPOCR_DET_MODEL.exists() and PPOCR_REC_MODEL.exists() and PPOCR_LABEL_FILE.exists()),
            "models": {
                "region": REGION_MODEL_ID,
                "ocr": OCR_MODEL_ID,
                "caption": CAPTION_MODEL_ID,
            },
            "paths": {
                "yolo_model": str(YOLO_MODEL),
                "ppocr_sample": str(PPOCR_SAMPLE),
                "ppocr_utils": str(PPOCR_UTILS),
                "ppocr_det_model": str(PPOCR_DET_MODEL),
                "ppocr_rec_model": str(PPOCR_REC_MODEL),
                "ppocr_label_file": str(PPOCR_LABEL_FILE),
                "cache_root": str(self.cache_root),
            },
        }

    def _image_path_for_bytes(self, image_bytes: bytes) -> tuple[str, Path]:
        digest = hashlib.sha256(image_bytes).hexdigest()
        image_path = self.image_root / f"{digest}.jpg"
        if not image_path.exists():
            from PIL import Image

            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            image.save(image_path, "JPEG", quality=94)
        return digest, image_path

    def _ensure_ppocr_runtime(self) -> Path:
        sample_copy = self.ppocr_root / "08_OCR_sample" / "01_paddleOCR"
        utils_copy = self.ppocr_root / "utils"
        marker = self.ppocr_root / ".ready"
        if marker.exists() and sample_copy.exists() and utils_copy.exists():
            self.ppocr_ready = True
            return sample_copy
        with self.ocr_lock:
            if marker.exists() and sample_copy.exists() and utils_copy.exists():
                self.ppocr_ready = True
                return sample_copy
            if sample_copy.exists():
                shutil.rmtree(sample_copy.parent)
            if utils_copy.exists():
                shutil.rmtree(utils_copy)
            sample_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(PPOCR_SAMPLE, sample_copy)
            shutil.copytree(PPOCR_UTILS, utils_copy)
            _write_paddle_stub(sample_copy)
            marker.write_text(str(time.time()), encoding="utf-8")
            self.ppocr_ready = True
        return sample_copy

    def _run_ocr(self, image_path: Path, digest: str) -> dict[str, Any]:
        with self.cache_lock:
            cached = self.cache.setdefault(digest, {})
            if "ocr" in cached:
                return cached["ocr"]
        sample_copy = self._ensure_ppocr_runtime()
        run_dir = self.request_root / f"ocr-{digest[:12]}-{uuid.uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=True)
        result_image = run_dir / "ppocr_result.jpg"
        command = [
            sys.executable,
            "paddle_ocr.py",
            "--det-model-path",
            str(PPOCR_DET_MODEL),
            "--rec-model-path",
            str(PPOCR_REC_MODEL),
            "--test-img",
            str(image_path),
            "--label-file",
            str(PPOCR_LABEL_FILE),
            "--img-save-path",
            str(result_image),
        ]
        with self.ocr_lock:
            proc = subprocess.run(
                command,
                cwd=sample_copy,
                capture_output=True,
                text=True,
                timeout=self.ocr_timeout,
                check=False,
            )
        predictions: list[str] = []
        for line in (proc.stdout or "").splitlines():
            stripped = line.strip()
            if stripped.startswith("Prediction:"):
                value = stripped.split("Prediction:", 1)[1].strip()
                if value:
                    predictions.append(value)
        payload = {
            "ok": proc.returncode == 0,
            "text": "\n".join(predictions),
            "regions": [],
            "confidence": 0.72 if predictions else 0.0,
            "language": "unknown",
            "model_id": OCR_MODEL_ID,
            "metadata": {
                "backend": "official_s100p_ppocrv3_hbm",
                "returncode": proc.returncode,
                "prediction_count": len(predictions),
                "result_image": str(result_image) if result_image.exists() else "",
                "stdout_preview": (proc.stdout or "")[-2000:],
                "stderr_preview": (proc.stderr or "")[-2000:],
            },
        }
        with self.cache_lock:
            self.cache.setdefault(digest, {})["ocr"] = payload
        return payload

    def _run_regions(self, image_path: Path, digest: str) -> dict[str, Any]:
        with self.cache_lock:
            cached = self.cache.setdefault(digest, {})
            if "region" in cached:
                return cached["region"]
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        image_width, image_height = image.size
        run_dir = self.request_root / f"yolo-{digest[:12]}-{uuid.uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=True)
        bash_command = (
            "source /opt/tros/humble/setup.bash; "
            f"cd {shlex_quote(str(run_dir))}; "
            f"timeout {int(self.yolo_timeout)} ros2 launch dnn_node_example dnn_node_example_feedback.launch.py "
            "dnn_example_config_file:=config/yolov8workconfig.json "
            f"dnn_example_image:={shlex_quote(str(image_path))}"
        )
        with self.yolo_lock:
            proc = subprocess.run(
                ["bash", "-lc", bash_command],
                capture_output=True,
                text=True,
                timeout=self.yolo_timeout + 8,
                check=False,
            )
        combined_log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        detections = _parse_yolo_log(combined_log, image_width, image_height)
        regions: list[dict[str, Any]] = []
        for det in detections:
            label = str(det["label"])
            confidence = float(det["confidence"])
            kind = "person" if label == "person" else "object"
            regions.append(
                {
                    "region_kind": kind,
                    "label": label,
                    "bbox": det["bbox"],
                    "confidence": confidence,
                    "attributes": [],
                    "metadata": {
                        "source": det["source"],
                        "bbox_xyxy": det["bbox_xyxy"],
                    },
                }
            )
            if label == "person":
                upper_xyxy = _upper_clothing_box(det["bbox_xyxy"], image_width, image_height)
                color = _dominant_color_for_crop(image_path, upper_xyxy)
                if color["color"] != "unknown":
                    regions.append(
                        {
                            "region_kind": "upper_clothing",
                            "label": "upper_clothing",
                            "bbox": _bbox_to_xywh(upper_xyxy),
                            "confidence": round(max(0.01, confidence * float(color["confidence"])), 4),
                            "attributes": [
                                {
                                    "namespace": "upper_clothing",
                                    "name": "color",
                                    "value": color["color"],
                                    "confidence": color["confidence"],
                                }
                            ],
                            "metadata": {
                                "source": "person_bbox_upper_crop_cv_color",
                                "person_confidence": confidence,
                                "person_bbox_xyxy": det["bbox_xyxy"],
                                "bbox_xyxy": upper_xyxy,
                                "color_counts": color["counts"],
                                "sampled_pixels": color["sampled_pixels"],
                            },
                        }
                    )
        payload = {
            "ok": proc.returncode == 0 or bool(regions),
            "model_id": REGION_MODEL_ID,
            "regions": regions,
            "metadata": {
                "backend": "official_s100p_yolov8_hbm_plus_cv_color",
                "returncode": proc.returncode,
                "detection_count": len(detections),
                "region_count": len(regions),
                "image_width": image_width,
                "image_height": image_height,
                "render_image": str(run_dir / "render_feedback_0_0.jpeg") if (run_dir / "render_feedback_0_0.jpeg").exists() else "",
                "stdout_preview": combined_log[-3000:],
            },
        }
        with self.cache_lock:
            self.cache.setdefault(digest, {})["region"] = payload
        return payload

    def analyze(self, image_bytes: bytes, *, include_ocr: bool, include_regions: bool) -> dict[str, Any]:
        digest, image_path = self._image_path_for_bytes(image_bytes)
        result: dict[str, Any] = {"digest": digest, "image_path": str(image_path)}
        if include_regions:
            result["region"] = self._run_regions(image_path, digest)
        if include_ocr:
            result["ocr"] = self._run_ocr(image_path, digest)
        return result


def shlex_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _image_from_standard_payload(payload: dict[str, Any]) -> bytes:
    image_url = payload.get("image_url") or {}
    if isinstance(image_url, dict):
        return _decode_data_url(str(image_url.get("url") or ""))[0]
    raise ValueError("missing image_url")


def _image_from_chat_payload(payload: dict[str, Any]) -> bytes:
    for message in payload.get("messages") or []:
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "image_url":
                    image_url = item.get("image_url") or {}
                    if isinstance(image_url, dict):
                        return _decode_data_url(str(image_url.get("url") or ""))[0]
        elif isinstance(content, dict) and content.get("type") == "image_url":
            image_url = content.get("image_url") or {}
            if isinstance(image_url, dict):
                return _decode_data_url(str(image_url.get("url") or ""))[0]
    raise ValueError("chat payload missing image_url content")


def make_handler(runtime: GroundedVisionRuntime):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AINASS100GroundedVisionGateway/1.0"

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path.rstrip("/") or "/"
            if route == "/health":
                _json_response(self, runtime.health())
                return
            _json_response(self, {"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path.rstrip("/") or "/"
            try:
                length = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                if route == "/ocr":
                    image_bytes = _image_from_standard_payload(payload)
                    analysis = runtime.analyze(image_bytes, include_ocr=True, include_regions=False)
                    ocr = dict(analysis["ocr"])
                    ocr.setdefault("metadata", {})["digest"] = analysis["digest"]
                    _json_response(self, ocr)
                    return
                if route == "/region":
                    image_bytes = _image_from_standard_payload(payload)
                    analysis = runtime.analyze(image_bytes, include_ocr=False, include_regions=True)
                    region = dict(analysis["region"])
                    region.setdefault("metadata", {})["digest"] = analysis["digest"]
                    _json_response(self, region)
                    return
                if route == "/chat/completions":
                    image_bytes = _image_from_chat_payload(payload)
                    analysis = runtime.analyze(image_bytes, include_ocr=True, include_regions=True)
                    regions = analysis["region"].get("regions") or []
                    ocr_text = str(analysis["ocr"].get("text") or "")
                    caption_payload = _caption_from_analysis(regions, ocr_text)
                    caption_payload["metadata"] = {
                        "digest": analysis["digest"],
                        "region_model_id": REGION_MODEL_ID,
                        "ocr_model_id": OCR_MODEL_ID,
                        "caption_generation": "grounded_detector_ocr_template",
                    }
                    response = {
                        "id": "chatcmpl-ai-nas-" + analysis["digest"][:16],
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": str(payload.get("model") or CAPTION_MODEL_ID),
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "stop",
                                "message": {
                                    "role": "assistant",
                                    "content": json.dumps(caption_payload, ensure_ascii=False),
                                },
                            }
                        ],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    }
                    _json_response(self, response)
                    return
                _json_response(self, {"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)
            except subprocess.TimeoutExpired as exc:
                _json_response(self, {"ok": False, "error": f"timeout:{exc}"}, HTTPStatus.GATEWAY_TIMEOUT)
            except Exception as exc:
                _json_response(
                    self,
                    {"ok": False, "error": f"{type(exc).__name__}:{exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S100 grounded OCR/detection/region/caption HTTP gateway.")
    parser.add_argument("--bind", default=os.environ.get("AI_NAS_S100_GROUNDED_VISION_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AI_NAS_S100_GROUNDED_VISION_PORT", "18183")))
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--yolo-timeout", type=int, default=int(os.environ.get("AI_NAS_S100_YOLO_TIMEOUT", "10")))
    parser.add_argument("--ocr-timeout", type=int, default=int(os.environ.get("AI_NAS_S100_OCR_TIMEOUT", "90")))
    args = parser.parse_args()

    runtime = GroundedVisionRuntime(args.cache_root, yolo_timeout=args.yolo_timeout, ocr_timeout=args.ocr_timeout)
    runtime.setup()
    health = runtime.health()
    print(json.dumps({"ok": True, "event": "starting", "health": health}, ensure_ascii=False), flush=True)
    if not health.get("ready"):
        print(json.dumps({"ok": False, "event": "not_ready", "health": health}, ensure_ascii=False), flush=True)
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(runtime))
    print(json.dumps({"ok": True, "event": "listening", "bind": args.bind, "port": args.port}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
