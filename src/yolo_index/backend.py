from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .labels import label_zh


YOLO_RECT_RE = re.compile(
    r"det\s+rect:\s*([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+),\s*"
    r"det\s+type:\s*([^,]+),\s*score:\s*([-0-9.]+)",
    re.IGNORECASE,
)
YOLO_TARGET_TYPE_RE = re.compile(r"target\s+type:\s*([^,]+),\s*rois\.size:\s*\d+", re.IGNORECASE)
YOLO_ROI_RE = re.compile(
    r"roi\.type:\s*([^,]*),\s*"
    r"x_offset:\s*([-0-9.]+)\s+y_offset:\s*([-0-9.]+)\s+"
    r"width:\s*([-0-9.]+)\s+height:\s*([-0-9.]+)",
    re.IGNORECASE,
)
ROI_LOG_FALLBACK_CONFIDENCE = 0.5


@dataclass(frozen=True)
class YoloDetection:
    label: str
    confidence: float
    bbox_x1: float | None
    bbox_y1: float | None
    bbox_x2: float | None
    bbox_y2: float | None
    image_width: int | None
    image_height: int | None
    evidence_ref: str


class YoloBackendError(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_yolo_log(text: str, *, evidence_ref: str = "yolo_ev_unassigned", image_size: tuple[int, int] | None = None) -> list[YoloDetection]:
    width, height = image_size or (None, None)
    detections: list[YoloDetection] = []
    for match in YOLO_RECT_RE.finditer(text or ""):
        x1, y1, x2, y2 = [float(match.group(i)) for i in range(1, 5)]
        label = match.group(5).strip()
        confidence = float(match.group(6))
        if width and height and width > 0 and height > 0:
            nx1 = _clamp(min(x1, x2) / width)
            ny1 = _clamp(min(y1, y2) / height)
            nx2 = _clamp(max(x1, x2) / width)
            ny2 = _clamp(max(y1, y2) / height)
        else:
            nx1, ny1, nx2, ny2 = x1, y1, x2, y2
        detections.append(
            YoloDetection(
                label=label,
                confidence=confidence,
                bbox_x1=nx1,
                bbox_y1=ny1,
                bbox_x2=nx2,
                bbox_y2=ny2,
                image_width=width,
                image_height=height,
                evidence_ref=evidence_ref,
            )
        )
    if detections:
        return detections
    current_label = ""
    for line in (text or "").splitlines():
        target_match = YOLO_TARGET_TYPE_RE.search(line)
        if target_match:
            current_label = target_match.group(1).strip().lower()
        roi_match = YOLO_ROI_RE.search(line)
        if not roi_match:
            continue
        label = (roi_match.group(1).strip() or current_label).lower()
        if not label:
            continue
        x1 = float(roi_match.group(2))
        y1 = float(roi_match.group(3))
        x2 = x1 + float(roi_match.group(4))
        y2 = y1 + float(roi_match.group(5))
        if width and height and width > 0 and height > 0:
            nx1 = _clamp(min(x1, x2) / width)
            ny1 = _clamp(min(y1, y2) / height)
            nx2 = _clamp(max(x1, x2) / width)
            ny2 = _clamp(max(y1, y2) / height)
        else:
            nx1, ny1, nx2, ny2 = x1, y1, x2, y2
        detections.append(
            YoloDetection(
                label=label,
                confidence=ROI_LOG_FALLBACK_CONFIDENCE,
                bbox_x1=nx1,
                bbox_y1=ny1,
                bbox_x2=nx2,
                bbox_y2=ny2,
                image_width=width,
                image_height=height,
                evidence_ref=evidence_ref,
            )
        )
    return detections


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as img:
            return int(img.width), int(img.height)
    except Exception:
        return None


class BaseYoloBackend:
    model_id = "digua-yolo-backend"
    model_name = "digua-yolo"
    model_family = "yolo"
    backend_name = "base"
    runtime_target = "local"

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "backend": self.backend_name,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_family": self.model_family,
            "runtime_target": self.runtime_target,
            "local_only": True,
            "weights_committed_to_repo": False,
        }

    def detect(self, image_path: str | Path, *, artifact_dir: str | Path, evidence_ref: str, timeout_sec: int = 30) -> list[YoloDetection]:
        raise NotImplementedError


class SyntheticYoloBackend(BaseYoloBackend):
    model_id = "digua-synthetic-yolo-fixture-v1"
    model_name = "digua-synthetic-yolo-fixture"
    backend_name = "synthetic_fixture"
    runtime_target = "unit_test_only"

    def detect(self, image_path: str | Path, *, artifact_dir: str | Path, evidence_ref: str, timeout_sec: int = 30) -> list[YoloDetection]:
        path = Path(image_path)
        labels = _labels_from_stem(path.stem)
        if not labels:
            labels = ["person"] if path.suffix.lower() in {".jpg", ".jpeg", ".png"} else []
        size = image_size(path) or (100, 100)
        rows: list[YoloDetection] = []
        for idx, label in enumerate(labels):
            offset = idx * 0.06
            rows.append(
                YoloDetection(
                    label=label,
                    confidence=0.91 - idx * 0.03,
                    bbox_x1=0.08 + offset,
                    bbox_y1=0.10 + offset,
                    bbox_x2=0.58 + offset,
                    bbox_y2=0.72 + offset,
                    image_width=size[0],
                    image_height=size[1],
                    evidence_ref=evidence_ref,
                )
            )
        Path(artifact_dir).mkdir(parents=True, exist_ok=True)
        (Path(artifact_dir) / f"{evidence_ref}.log").write_text(
            "\n".join(f"synthetic label={row.label} label_zh={label_zh(row.label)} score={row.confidence}" for row in rows),
            encoding="utf-8",
        )
        return rows


class S100PYoloBackend(BaseYoloBackend):
    model_id = "s100p-yolov8n-hbm-cv-object-v2"
    model_name = "yolov8n_640x640_nv12"
    backend_name = "s100p_tros_dnn_node_example"
    runtime_target = "s100p_bpu_hbm"

    def __init__(
        self,
        *,
        workdir: str | Path = "/home/sunrise/yolo_s100p_run",
        config_file: str = "config/yolov8workconfig.json",
        model_path: str | Path = "/opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm",
    ) -> None:
        self.workdir = Path(workdir)
        self.config_file = config_file
        self.model_path = Path(model_path)

    def status(self) -> dict[str, Any]:
        base = super().status()
        ros_setup = Path("/opt/ros/humble/setup.bash")
        tros_setup = Path("/opt/tros/humble/setup.bash")
        available = (
            platform.machine().lower() in {"aarch64", "arm64"}
            and self.workdir.exists()
            and (self.workdir / self.config_file).exists()
            and self.model_path.exists()
            and ros_setup.exists()
            and tros_setup.exists()
        )
        base.update(
            {
                "available": available,
                "machine": platform.machine(),
                "workdir_exists": self.workdir.exists(),
                "config_exists": (self.workdir / self.config_file).exists(),
                "model_path_hash": sha256_text(str(self.model_path)),
                "ros_setup_exists": ros_setup.exists(),
                "tros_setup_exists": tros_setup.exists(),
            }
        )
        return base

    def detect(self, image_path: str | Path, *, artifact_dir: str | Path, evidence_ref: str, timeout_sec: int = 30) -> list[YoloDetection]:
        status = self.status()
        if not status.get("available"):
            raise YoloBackendError(f"s100p_yolo_backend_unavailable:{status}")
        image = Path(image_path)
        if not image.exists():
            raise YoloBackendError("image_not_found")
        artifact = Path(artifact_dir)
        artifact.mkdir(parents=True, exist_ok=True)
        log_path = artifact / f"{evidence_ref}.log"
        render_src = self.workdir / "render_feedback_0_0.jpeg"
        script = f"""
set -e
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash
cd "{self.workdir}"
rm -f render_feedback_0_0.jpeg
set +e
timeout {int(timeout_sec)} ros2 launch dnn_node_example dnn_node_example_feedback.launch.py dnn_example_config_file:="{self.config_file}" dnn_example_image:="$DIGUA_YOLO_IMAGE"
status=$?
set -e
echo "__DIGUA_YOLO_LAUNCH_STATUS=$status"
exit "$status"
"""
        env = os.environ.copy()
        env["DIGUA_YOLO_IMAGE"] = str(image)
        started = time.perf_counter()
        completed = subprocess.run(["bash", "-lc", script], text=True, capture_output=True, timeout=timeout_sec + 10, env=env, check=False)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        combined = completed.stdout + "\n" + completed.stderr
        log_path.write_text(
            json_safe_log(
                {
                    "returncode": completed.returncode,
                    "elapsed_ms": elapsed_ms,
                    "model_id": self.model_id,
                    "backend": self.backend_name,
                    "stdout_stderr": combined,
                }
            ),
            encoding="utf-8",
        )
        timeout_after_render = "__DIGUA_YOLO_LAUNCH_STATUS=124" in combined and render_src.exists()
        if completed.returncode not in {0, 124} and not timeout_after_render:
            raise YoloBackendError(f"yolo_launch_failed:{completed.returncode}:{redact_paths(combined[-600:])}")
        if not render_src.exists():
            raise YoloBackendError(f"yolo_render_missing:{completed.returncode}:{redact_paths(combined[-600:])}")
        if render_src.exists():
            try:
                shutil.copy2(render_src, artifact / f"{evidence_ref}_render.jpeg")
            except OSError:
                pass
        detections = parse_yolo_log(combined, evidence_ref=evidence_ref, image_size=image_size(image))
        return detections


def json_safe_log(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def redact_paths(value: str) -> str:
    import re

    return re.sub(r"([A-Za-z]:\\[^\s\"']+|/mnt/nas/[^\s\"']+|/home/[^\s\"']+|/root/[^\s\"']+|/opt/[^\s\"']+)", "[redacted-path]", value)


def _labels_from_stem(stem: str) -> list[str]:
    text = stem.lower().replace("-", "_")
    known = [
        "person",
        "cat",
        "dog",
        "car",
        "bus",
        "laptop",
        "book",
        "keyboard",
        "mouse",
        "tv",
        "cup",
        "bottle",
        "chair",
        "backpack",
        "cell_phone",
        "kite",
        "stop_sign",
    ]
    labels: list[str] = []
    for label in known:
        token = label.replace(" ", "_")
        if token in text:
            labels.append(label.replace("_", " "))
    return labels


def backend_from_env() -> BaseYoloBackend:
    requested = os.environ.get("DIGUA_YOLO_BACKEND", "").strip().lower()
    if requested in {"synthetic", "fake", "fixture"}:
        return SyntheticYoloBackend()
    return S100PYoloBackend()
