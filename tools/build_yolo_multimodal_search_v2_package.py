#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO_ROOT / "reports" / "yolo_production"
PACKAGE_DIR = REPO_ROOT / "evidence_for_gptpro"

REPORTS = [
    ("27000_s100p_environment_lock", "S100P environment lock"),
    ("27010_yolo_backend_discovery_gate", "YOLO backend discovery"),
    ("27020_yolo_sqlite_schema_gate", "YOLO SQLite schema"),
    ("27030_image_yolo_index_gate", "Image YOLO index"),
    ("27040_video_keyframe_yolo_index_gate", "Video keyframe YOLO index"),
    ("27050_object_label_search_gate", "Object label search"),
    ("27060_hybrid_retrieval_gate", "Hybrid retrieval"),
    ("27070_openclaw_api_gate", "OpenClaw API"),
    ("27080_ui_visual_detection_gate", "UI visual detection"),
    ("27090_security_privacy_gate", "Security and privacy"),
    ("27100_s100p_test_matrix_gate", "S100P test matrix"),
]

FORBIDDEN_SUFFIXES = {
    ".hbm",
    ".bin",
    ".onnx",
    ".safetensors",
    ".pt",
    ".pth",
    ".gguf",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
}
FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache", "node_modules"}
FORBIDDEN_NAME_PARTS = {"redaction_map", ".env", "secret", "apikey", "api_key"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote-summary", type=Path, default=None)
    parser.add_argument("--out-root", type=Path, default=REPORT_DIR)
    parser.add_argument("--package-root", type=Path, default=PACKAGE_DIR)
    parser.add_argument("--timestamp", default=time.strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()

    summary = read_json(args.remote_summary) if args.remote_summary else {}
    out_root = args.out_root
    out_root.mkdir(parents=True, exist_ok=True)
    package_root = args.package_root
    package_root.mkdir(parents=True, exist_ok=True)

    generated_reports = []
    for report_id, title in REPORTS:
        payload = build_report(report_id, title, summary)
        json_path = out_root / f"{report_id}.json"
        md_path = out_root / f"{report_id}.md"
        write_json(json_path, payload)
        write_markdown(md_path, payload)
        generated_reports.extend([json_path, md_path])

    package_path = package_root / f"digua_ai_nas_s100p_yolo_multimodal_search_v2_for_gptpro_{args.timestamp}.zip"
    manifest = build_package(package_path, generated_reports)
    final_payload = {
        "ok": manifest["forbidden_file_count"] == 0 and summary.get("final_verdict") not in {None, "hold_due_to_s100p_unreachable"},
        "generated_at": now(),
        "report_id": "27110_final_delivery_package_manifest",
        "title": "Final delivery package manifest",
        "final_verdict": summary.get("final_verdict") or infer_verdict(summary),
        "package": manifest,
        "remote_summary": compact_summary(summary),
    }
    final_json = out_root / "27110_final_delivery_package_manifest.json"
    final_md = out_root / "27110_final_delivery_package_manifest.md"
    write_json(final_json, final_payload)
    write_markdown(final_md, final_payload)
    with zipfile.ZipFile(package_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(final_json, final_json.relative_to(REPO_ROOT).as_posix())
        zf.write(final_md, final_md.relative_to(REPO_ROOT).as_posix())
    sha = sha256_file(package_path)
    (package_path.with_suffix(package_path.suffix + ".sha256")).write_text(f"{sha}  {package_path.name}\n", encoding="utf-8")
    manifest["sha256"] = sha
    write_json(package_path.with_suffix(".manifest.json"), manifest)
    write_json(final_json, {**final_payload, "package": manifest})
    return 0 if final_payload["ok"] and manifest["forbidden_file_count"] == 0 else 1


def build_report(report_id: str, title: str, summary: dict[str, Any]) -> dict[str, Any]:
    key = report_id.split("_", 1)[1]
    section = summary.get("reports", {}).get(report_id) or summary.get(key) or {}
    checks = section.get("checks") if isinstance(section, dict) else None
    ok = bool(section.get("ok")) if isinstance(section, dict) and "ok" in section else infer_report_ok(report_id, summary)
    return {
        "ok": ok,
        "generated_at": now(),
        "report_id": report_id,
        "title": title,
        "verdict": section.get("verdict") if isinstance(section, dict) else None,
        "checks": checks if isinstance(checks, dict) else default_checks(report_id, summary),
        "evidence": section.get("evidence") if isinstance(section, dict) else None,
        "notes": section.get("notes") if isinstance(section, dict) else [],
    }


def infer_report_ok(report_id: str, summary: dict[str, Any]) -> bool:
    if report_id == "27000_s100p_environment_lock":
        return bool(summary.get("s100p_reachable") and summary.get("openclaw_8765_live"))
    if report_id == "27010_yolo_backend_discovery_gate":
        return bool(summary.get("yolo_backend_available") and summary.get("sample_detections", 0) > 0)
    if report_id == "27020_yolo_sqlite_schema_gate":
        return bool(summary.get("schema_ok"))
    if report_id == "27030_image_yolo_index_gate":
        return bool(summary.get("image_index_ok"))
    if report_id == "27040_video_keyframe_yolo_index_gate":
        return bool(summary.get("video_index_ok"))
    if report_id == "27050_object_label_search_gate":
        return bool(summary.get("object_search_ok"))
    if report_id == "27060_hybrid_retrieval_gate":
        return bool(summary.get("hybrid_ok"))
    if report_id == "27070_openclaw_api_gate":
        return bool(summary.get("api_ok"))
    if report_id == "27080_ui_visual_detection_gate":
        return bool(summary.get("ui_ok"))
    if report_id == "27090_security_privacy_gate":
        return bool(summary.get("security_ok"))
    if report_id == "27100_s100p_test_matrix_gate":
        return bool(summary.get("test_matrix_ok"))
    return False


def default_checks(report_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "final_verdict": summary.get("final_verdict"),
        "s100p_host": summary.get("s100p_host"),
        "openclaw_8765_live": summary.get("openclaw_8765_live"),
        "qwen_18080_live": summary.get("qwen_18080_live"),
        "indexed_count": summary.get("indexed_count"),
        "detection_count": summary.get("detection_count"),
        "keyframe_count": summary.get("keyframe_count"),
        "strict_eval_pass_rate": summary.get("strict_eval_pass_rate"),
        "private_leak_count": summary.get("private_leak_count"),
        "raw_path_rows": summary.get("raw_path_rows"),
    }


def build_package(package_path: Path, generated_reports: list[Path]) -> dict[str, Any]:
    include_paths = [
        REPO_ROOT / "src" / "yolo_index",
        REPO_ROOT / "src" / "openclaw" / "routes" / "yolo_index_routes.py",
        REPO_ROOT / "src" / "openclaw" / "routes" / "multimodal_search_routes.py",
        REPO_ROOT / "src" / "multimodal_search" / "search_api.py",
        REPO_ROOT / "scripts" / "probes" / "ai_nas_operator_portal_server.py",
        REPO_ROOT / "scripts" / "production" / "check_yolo_index_status.sh",
        REPO_ROOT / "scripts" / "production" / "rebuild_yolo_index.sh",
        REPO_ROOT / "scripts" / "production" / "enable_yolo_index_service.sh",
        REPO_ROOT / "scripts" / "production" / "rollback_yolo_index_service.sh",
        REPO_ROOT / "web" / "templates" / "multimodal_search.html",
        REPO_ROOT / "web" / "static" / "digua_multimodal_search.js",
        REPO_ROOT / "web" / "static" / "digua_multimodal_search.css",
        REPO_ROOT / "tests" / "test_yolo_index_core.py",
        REPO_ROOT / "tests" / "test_multimodal_search_v1.py",
        REPO_ROOT / "benchmarks" / "yolo_object_search_eval_cases.jsonl",
        REPO_ROOT / "evidence" / "yolo_production" / "s100p_yolo_v2_gate_summary.json",
        REPO_ROOT / "evidence" / "yolo_production" / "playwright_ui_gate.json",
        REPO_ROOT / "docs" / "YOLO_INDEX_PRODUCTION_RUNBOOK.md",
        REPO_ROOT / "docs" / "YOLO_INDEX_ROLLBACK_RUNBOOK.md",
        REPO_ROOT / "docs" / "YOLO_MULTIMODAL_SEARCH_SAFE_CLAIMS.md",
        REPO_ROOT / "SELF_CHECK.py",
    ] + generated_reports
    files: list[Path] = []
    for path in include_paths:
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file())
        elif path.is_file():
            files.append(path)
    forbidden: list[str] = []
    written: list[str] = []
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(set(files)):
            rel = path.relative_to(REPO_ROOT).as_posix()
            reason = forbidden_reason(path)
            if reason:
                forbidden.append(f"{rel}:{reason}")
                continue
            zf.write(path, rel)
            written.append(rel)
    return {
        "package_path": str(package_path),
        "file_count": len(written),
        "files": written,
        "forbidden_file_count": len(forbidden),
        "forbidden_files": forbidden,
        "self_check": {
            "no_weights": not any(Path(item).suffix.lower() in FORBIDDEN_SUFFIXES for item in written),
            "no_runtime_db": not any(Path(item).suffix.lower() in {".db", ".sqlite", ".sqlite3"} for item in written),
            "no_real_media": not any(Path(item).suffix.lower() in {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".mkv"} for item in written),
        },
    }


def forbidden_reason(path: Path) -> str | None:
    rel_parts = set(path.relative_to(REPO_ROOT).parts)
    if rel_parts & FORBIDDEN_PARTS:
        return "forbidden_path_part"
    suffix = path.suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        return "forbidden_suffix"
    lower_name = path.name.lower()
    if any(part in lower_name for part in FORBIDDEN_NAME_PARTS):
        return "forbidden_name"
    return None


def infer_verdict(summary: dict[str, Any]) -> str:
    if not summary.get("s100p_reachable"):
        return "hold_due_to_s100p_unreachable"
    if summary.get("image_index_ok") and summary.get("video_index_ok") and summary.get("ui_ok"):
        return "s100p_yolo_multimodal_search_v2_image_video_limited_ready"
    if summary.get("image_index_ok") and summary.get("object_search_ok"):
        return "s100p_yolo_multimodal_search_v2_image_ready_video_pending"
    if not summary.get("yolo_backend_available"):
        return "hold_due_to_no_s100p_yolo_backend"
    return "s100p_yolo_multimodal_search_v2_incomplete"


def compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "s100p_host",
        "final_verdict",
        "s100p_reachable",
        "openclaw_8765_live",
        "qwen_18080_live",
        "yolo_backend_available",
        "indexed_count",
        "detection_count",
        "keyframe_count",
        "strict_eval_pass_rate",
        "private_leak_count",
        "raw_path_rows",
        "ui_url",
    ]
    return {key: summary.get(key) for key in keys}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# {payload.get('title') or payload.get('report_id')}",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- report_id: `{payload.get('report_id')}`",
        f"- generated_at: `{payload.get('generated_at')}`",
    ]
    if payload.get("verdict") or payload.get("final_verdict"):
        lines.append(f"- verdict: `{payload.get('verdict') or payload.get('final_verdict')}`")
    checks = payload.get("checks") or {}
    if checks:
        lines.extend(["", "## Checks"])
        for key, value in checks.items():
            lines.append(f"- `{key}`: `{value}`")
    package = payload.get("package")
    if isinstance(package, dict):
        lines.extend(["", "## Package", f"- path: `{package.get('package_path')}`", f"- file_count: `{package.get('file_count')}`", f"- forbidden_file_count: `{package.get('forbidden_file_count')}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    raise SystemExit(main())
