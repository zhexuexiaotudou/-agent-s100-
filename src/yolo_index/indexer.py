from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .backend import BaseYoloBackend, YoloBackendError, YoloDetection, backend_from_env
from .labels import label_zh
from .schema import connect, migrate


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}


@dataclass(frozen=True)
class AssetCandidate:
    path: Path
    modality: str


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def file_sha256(path: Path, *, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    remaining = max_bytes
    with path.open("rb") as fh:
        while True:
            size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
            if size <= 0:
                break
            chunk = fh.read(size)
            if not chunk:
                break
            h.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return h.hexdigest()


def path_hash(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8", errors="replace")).hexdigest()


def asset_id_for(path: Path) -> str:
    stat = path.stat()
    identity = f"{path_hash(path)}:{stat.st_size}:{int(stat.st_mtime)}"
    return "yasset_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def safe_title(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    return stem[:80] or "media asset"


def collect_assets(roots: Iterable[str | Path], *, max_files: int) -> list[AssetCandidate]:
    assets: list[AssetCandidate] = []
    for root_value in roots:
        root = Path(root_value)
        if not root.exists():
            continue
        paths = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in sorted(paths):
            suffix = path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                assets.append(AssetCandidate(path=path, modality="image"))
            elif suffix in VIDEO_EXTENSIONS:
                assets.append(AssetCandidate(path=path, modality="video"))
            if len(assets) >= max_files:
                return assets
    return assets


class VideoKeyframeExtractor:
    def __init__(self, *, timestamps: tuple[float, ...] = (0.0,), timeout_sec: int = 45) -> None:
        self.timestamps = timestamps
        self.timeout_sec = timeout_sec

    def extract(self, video_path: Path, *, output_dir: Path, asset_id: str) -> list[dict[str, Any]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        frames: list[dict[str, Any]] = []
        for ts in self.timestamps:
            keyframe_id = "ykf_" + hashlib.sha256(f"{asset_id}:{ts}".encode("utf-8")).hexdigest()[:20]
            frame_path = output_dir / f"{keyframe_id}.jpg"
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(ts),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(frame_path),
            ]
            completed = subprocess.run(cmd, text=True, capture_output=True, timeout=self.timeout_sec, check=False)
            if completed.returncode != 0 or not frame_path.exists():
                frames.append(
                    {
                        "ok": False,
                        "keyframe_id": keyframe_id,
                        "timestamp_sec": ts,
                        "error": redact_paths((completed.stderr or completed.stdout or "ffmpeg_keyframe_failed")[-500:]),
                    }
                )
                continue
            frames.append(
                {
                    "ok": True,
                    "keyframe_id": keyframe_id,
                    "timestamp_sec": ts,
                    "frame_path": frame_path,
                    "frame_hash": file_sha256(frame_path),
                }
            )
        return frames


def redact_paths(value: str) -> str:
    return re.sub(r"([A-Za-z]:\\[^\s\"']+|/mnt/nas/[^\s\"']+|/home/[^\s\"']+|/root/[^\s\"']+|/opt/[^\s\"']+)", "[redacted-path]", value)


class YoloIndexer:
    def __init__(
        self,
        db_path: str | Path,
        *,
        report_root: str | Path,
        backend: BaseYoloBackend | None = None,
        max_files: int = 100,
    ) -> None:
        self.db_path = Path(db_path)
        self.report_root = Path(report_root)
        self.backend = backend or backend_from_env()
        self.max_files = max_files
        self.keyframes = VideoKeyframeExtractor()

    def rebuild(self, roots: Iterable[str | Path], *, max_files: int | None = None, include_video: bool = True) -> dict[str, Any]:
        migrate(self.db_path)
        run_id = "yolo_run_" + uuid.uuid4().hex[:16]
        evidence_dir = self.report_root / "yolo_index" / "evidence" / run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        assets = collect_assets(roots, max_files=int(max_files or self.max_files))
        if not include_video:
            assets = [asset for asset in assets if asset.modality != "video"]
        started = time.perf_counter()
        counts = {"image": 0, "video": 0, "detections": 0, "keyframes": 0, "errors": 0}
        errors: list[dict[str, str]] = []
        conn = connect(self.db_path)
        try:
            conn.execute("DELETE FROM mm_search_results")
            conn.execute("DELETE FROM mm_yolo_detections")
            conn.execute("DELETE FROM mm_video_keyframes")
            conn.execute("DELETE FROM mm_yolo_assets")
            self._upsert_model(conn)
            conn.commit()
            for candidate in assets:
                try:
                    asset_id = asset_id_for(candidate.path)
                    self._upsert_asset(conn, candidate.path, asset_id, candidate.modality)
                    if candidate.modality == "image":
                        detections = self._detect_image(candidate.path, asset_id=asset_id, modality="image", evidence_dir=evidence_dir)
                        self._insert_detections(conn, detections, asset_id=asset_id, modality="image")
                        counts["image"] += 1
                        counts["detections"] += len(detections)
                    elif candidate.modality == "video":
                        video_result = self._detect_video(candidate.path, asset_id=asset_id, evidence_dir=evidence_dir, conn=conn)
                        counts["video"] += 1
                        counts["keyframes"] += video_result["keyframes"]
                        counts["detections"] += video_result["detections"]
                    conn.commit()
                except Exception as exc:
                    counts["errors"] += 1
                    errors.append({"asset_hash": path_hash(candidate.path)[:16], "error": redact_paths(f"{type(exc).__name__}:{exc}")})
                    conn.commit()
        finally:
            conn.close()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        trace_path = evidence_dir / "rebuild_summary.json"
        result = {
            "ok": counts["errors"] == 0 and bool(assets),
            "run_id": run_id,
            "schema": "digua_yolo_index_v2",
            "backend": self.backend.status(),
            "asset_count": len(assets),
            "counts": counts,
            "elapsed_ms": elapsed_ms,
            "errors": errors[:20],
            "privacy": {"raw_path_returned": False, "cloud_used": False, "local_only": True},
            "evidence_dir": f"yolo_index/evidence/{run_id}",
            "evidence_ref": f"yolo_index/evidence/{run_id}/rebuild_summary.json",
        }
        trace_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return result

    def _detect_image(self, path: Path, *, asset_id: str, modality: str, evidence_dir: Path, keyframe_id: str | None = None) -> list[YoloDetection]:
        evidence_ref = "yolo_ev_" + hashlib.sha256(f"{asset_id}:{keyframe_id or path.name}".encode("utf-8")).hexdigest()[:20]
        return self.backend.detect(path, artifact_dir=evidence_dir, evidence_ref=evidence_ref)

    def _detect_video(self, path: Path, *, asset_id: str, evidence_dir: Path, conn) -> dict[str, int]:
        frames = self.keyframes.extract(path, output_dir=evidence_dir / "keyframes", asset_id=asset_id)
        detection_count = 0
        keyframe_count = 0
        for frame in frames:
            keyframe_id = frame["keyframe_id"]
            timestamp_sec = float(frame.get("timestamp_sec") or 0.0)
            conn.execute(
                "INSERT OR REPLACE INTO mm_video_keyframes(keyframe_id,asset_id,timestamp_sec,thumbnail_id,frame_hash,yolo_index_status,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    keyframe_id,
                    asset_id,
                    timestamp_sec,
                    None,
                    frame.get("frame_hash"),
                    "indexed" if frame.get("ok") else "failed",
                    now_iso(),
                ),
            )
            if not frame.get("ok"):
                continue
            keyframe_count += 1
            detections = self._detect_image(Path(frame["frame_path"]), asset_id=asset_id, modality="video", evidence_dir=evidence_dir, keyframe_id=keyframe_id)
            self._insert_detections(conn, detections, asset_id=asset_id, modality="video", keyframe_id=keyframe_id, timestamp_sec=timestamp_sec)
            detection_count += len(detections)
        return {"keyframes": keyframe_count, "detections": detection_count}

    def _upsert_model(self, conn) -> None:
        status = self.backend.status()
        conn.execute(
            """
            INSERT OR REPLACE INTO mm_yolo_models(
              model_id,model_name,model_family,backend,runtime_target,input_size,label_set,model_path_hash,
              weights_committed_to_repo,local_only,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                status["model_id"],
                status.get("model_name") or status["model_id"],
                status.get("model_family") or "yolo",
                status.get("backend") or "unknown",
                status.get("runtime_target") or "local",
                "640x640",
                "coco",
                status.get("model_path_hash"),
                0,
                1,
                now_iso(),
            ),
        )

    def _upsert_asset(self, conn, path: Path, asset_id: str, modality: str) -> None:
        stat = path.stat()
        conn.execute(
            """
            INSERT OR REPLACE INTO mm_yolo_assets(
              asset_id,modality,title_redacted,file_type,path_hash,size_bytes,mtime,privacy_level,index_status,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                asset_id,
                modality,
                safe_title(path),
                mimetypes.guess_type(path.name)[0] or path.suffix.lower().lstrip("."),
                path_hash(path),
                stat.st_size,
                int(stat.st_mtime),
                "private_local_only",
                "indexed",
                now_iso(),
                now_iso(),
            ),
        )

    def _insert_detections(
        self,
        conn,
        detections: list[YoloDetection],
        *,
        asset_id: str,
        modality: str,
        keyframe_id: str | None = None,
        timestamp_sec: float | None = None,
    ) -> None:
        for detection in detections:
            detection_id = "ydet_" + uuid.uuid4().hex[:24]
            conn.execute(
                """
                INSERT INTO mm_yolo_detections(
                  detection_id,asset_id,keyframe_id,modality,label,label_zh,confidence,
                  bbox_x1,bbox_y1,bbox_x2,bbox_y2,bbox_units,image_width,image_height,timestamp_sec,
                  model_id,model_backend,evidence_ref,trace_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    detection_id,
                    asset_id,
                    keyframe_id,
                    modality,
                    detection.label,
                    label_zh(detection.label),
                    detection.confidence,
                    detection.bbox_x1,
                    detection.bbox_y1,
                    detection.bbox_x2,
                    detection.bbox_y2,
                    "normalized_0_1",
                    detection.image_width,
                    detection.image_height,
                    timestamp_sec,
                    self.backend.model_id,
                    self.backend.backend_name,
                    detection.evidence_ref,
                    "trace_" + uuid.uuid4().hex[:16],
                    now_iso(),
                ),
            )
