from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload


NAME = "stage9_final_recording_readiness_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate final recording readiness for the three product demos.")
    add_common_args(parser)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--qwen-url", default="http://127.0.0.1:18080/health")
    parser.add_argument("--auth-token", default=os.environ.get("DIGUA_DEMO_AUTH_TOKEN", ""))
    parser.add_argument("--demo-image", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    configure_production_env()
    gate_dir = Path(__file__).resolve().parent
    results: dict[str, dict[str, Any]] = {}
    report_files: list[Path] = []

    commands = {
        "demo1_link_readiness": [
            sys.executable,
            str(gate_dir / "stage8_demo1_link_readiness_gate.py"),
            "--report-root",
            str(args.report_root),
            "--base-url",
            args.base_url,
            "--qwen-url",
            args.qwen_url,
            "--timeout",
            str(args.timeout),
        ],
        "auto_organizer_ai_driven": [
            sys.executable,
            str(gate_dir / "stage9_auto_organizer_ai_driven_gate.py"),
            "--report-root",
            str(args.report_root),
            "--timeout",
            str(args.timeout),
        ],
        "demo2_real_user_flow": [
            sys.executable,
            str(gate_dir / "stage9_demo2_real_user_flow_gate.py"),
            "--report-root",
            str(args.report_root),
            "--base-url",
            args.base_url,
            "--auth-token",
            str(args.auth_token or ""),
            "--timeout",
            str(args.timeout),
        ],
        "demo3_real_trace_flow": [
            sys.executable,
            str(gate_dir / "stage9_demo3_real_trace_flow_gate.py"),
            "--report-root",
            str(args.report_root),
            "--base-url",
            args.base_url,
            "--timeout",
            str(args.timeout),
        ],
        "product_smoke": [
            sys.executable,
            str(Path("scripts") / "product_smoke_test.py"),
            "--report-root",
            str(args.report_root),
            "--base-url",
            args.base_url,
            "--timeout",
            str(args.timeout),
        ],
    }
    if args.personal_root:
        commands["auto_organizer_ai_driven"].extend(["--source-rel", "Uploads/stage9_ai_driven/IMG_0001.jpg"])
    for name in ("demo1_link_readiness", "auto_organizer_ai_driven", "demo2_real_user_flow"):
        if args.personal_root:
            commands[name].extend(["--personal-root", str(args.personal_root)])
    if args.demo_image:
        commands["auto_organizer_ai_driven"].extend(["--demo-image", str(args.demo_image)])
        commands["demo2_real_user_flow"].extend(["--demo-image", str(args.demo_image)])

    for name, cmd in commands.items():
        if name == "product_smoke":
            results["recording_index_prepare"] = prepare_recording_indices(args.report_root, args.personal_root)
        command_env = dict(os.environ)
        command_env["DIGUA_ADMIN_TOKEN"] = str(args.auth_token or "")
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=args.timeout + 180, env=command_env)
        result = latest_gate_result(args.report_root, name)
        if result:
            payload = json.loads(result.read_text(encoding="utf-8"))
            payload["subprocess_returncode"] = completed.returncode
            results[name] = payload
            report_files.extend([p for p in [result, result.with_suffix(".md")] if p.exists()])
        else:
            results[name] = {
                "ok": False,
                "verdict": "missing_report",
                "subprocess_returncode": completed.returncode,
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            }
    results = redact_paths(results)

    checks = [
        check("Demo 1 ready", results.get("demo1_link_readiness", {}).get("ok") is True, results.get("demo1_link_readiness", {}).get("verdict")),
        check("Demo 2 real flow ready", results.get("demo2_real_user_flow", {}).get("ok") is True, results.get("demo2_real_user_flow", {}).get("verdict")),
        check("Demo 3 real trace ready", results.get("demo3_real_trace_flow", {}).get("ok") is True, results.get("demo3_real_trace_flow", {}).get("verdict")),
        check("Auto Organizer AI-driven ready", results.get("auto_organizer_ai_driven", {}).get("ok") is True, results.get("auto_organizer_ai_driven", {}).get("verdict")),
        check("Product smoke ok", results.get("product_smoke", {}).get("ok") is True, results.get("product_smoke", {}).get("verdict")),
        check("Recording indices restored", results.get("recording_index_prepare", {}).get("ok") is True, results.get("recording_index_prepare")),
    ]
    safety = collect_safety(results)
    checks.extend(
        [
            check("No raw path", safety["raw_path_returned"] is False, safety),
            check("No delete", safety["delete_enabled"] is False, safety),
            check("No overwrite", safety["overwrite_enabled"] is False, safety),
            check("No uncontrolled move/rename", safety["uncontrolled_move_or_rename"] is False, safety),
            check("No hidden CoT", safety["hidden_chain_of_thought_saved"] is False, safety),
            check("No private cloud egress", safety["private_cloud_egress"] is False, safety),
        ]
    )
    payload = gate_payload(
        "ok_stage9_final_recording_readiness_gate",
        "blocked_stage9_final_recording_readiness_gate",
        checks,
        {
            "base_url": args.base_url,
            "qwen_url": args.qwen_url,
            "auth_token_supplied": bool(args.auth_token),
            "demo_image_supplied": bool(args.demo_image),
            "sub_gates": results,
            "safety": safety,
            "gptpro_bundle": None,
            "gptpro_bundle_sha256": None,
        },
    )
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    report_files.extend([json_path, md_path])
    bundle = bundle_reports(report_files)
    if bundle and bundle.exists():
        payload["evidence"]["gptpro_bundle"] = str(bundle)
        payload["evidence"]["gptpro_bundle_sha256"] = sha256_file(bundle)
        json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    if bundle:
        print(bundle)
    return 0 if payload["ok"] else 1


def latest_gate_result(report_root: Path, name: str) -> Path | None:
    direct = {
        "demo1_link_readiness": report_root / "stage8_demo1_link_readiness_gate.json",
        "auto_organizer_ai_driven": report_root / "stage9_auto_organizer_ai_driven_gate.json",
        "demo2_real_user_flow": report_root / "stage9_demo2_real_user_flow_gate.json",
        "demo3_real_trace_flow": report_root / "stage9_demo3_real_trace_flow_gate.json",
    }.get(name)
    if direct and direct.exists():
        return direct
    if name == "product_smoke":
        candidates = sorted(report_root.glob("product_smoke_test_*/product_smoke_test.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None
    return None


def configure_production_env() -> None:
    model_root = Path.cwd() / "models"
    clip_dir = model_root / "ai_nas_clip_vit_base_patch32"
    whisper_dir = model_root / "whisper_tiny"
    if clip_dir.exists():
        os.environ.setdefault("DIGUA_CLIP_BACKEND", "clip")
        os.environ.setdefault("DIGUA_CLIP_MODEL_DIR", str(clip_dir))
        os.environ.setdefault("DIGUA_CLIP_DEVICE", "cpu")
        os.environ.setdefault("DIGUA_CLIP_REQUIRE_PRODUCTION", "1")
    if whisper_dir.exists():
        os.environ.setdefault("DIGUA_ASR_BACKEND", "transformers_whisper")
        os.environ.setdefault("DIGUA_ASR_MODEL_DIR", str(whisper_dir))
        os.environ.setdefault("DIGUA_ASR_DEVICE", "cpu")
        os.environ.setdefault("DIGUA_ASR_REQUIRE_REAL", "1")


def prepare_recording_indices(report_root: Path, personal_root: Path | None) -> dict[str, Any]:
    if not personal_root:
        return {"ok": False, "error": "personal_root_required"}
    try:
        from src.openclaw.routes.ai_space_routes import ai_space_route_response
        from src.openclaw.routes.multimodal_search_routes import multimodal_route_response
        from src.openclaw.routes.person_attribute_routes import person_attribute_route_response
        from src.openclaw.routes.smart_classification_routes import smart_classification_route_response
        from src.openclaw.routes.yolo_index_routes import yolo_route_response

        personal = Path(personal_root)
        candidate_roots = [
            personal / "Photos" / "stage7_smart_album_demo",
            personal / "Uploads" / "stage7_auto_classify",
            personal.parent / "demo_data" / "photos",
        ]
        roots = [str(path) for path in candidate_roots if path.exists()]
        if not roots:
            return {"ok": False, "error": "no_demo_roots_found"}
        rebuild_payload = {"roots": roots, "max_files": 40, "include_video": False}
        results = {
            "multimodal": multimodal_route_response("/api/multimodal-index/rebuild", method="POST", payload=rebuild_payload, report_root=report_root, personal_root=personal)[1],
            "yolo": yolo_route_response("/api/yolo-index/rebuild", method="POST", payload={"roots": roots[:1], "max_files": 1, "include_video": False}, report_root=report_root, personal_root=personal)[1],
            "person_attribute": person_attribute_route_response("/api/person-attribute/rebuild", method="POST", payload={"roots": roots, "max_files": 40}, report_root=report_root, personal_root=personal)[1],
            "smart_classification": smart_classification_route_response("/api/smart-classification/rebuild", method="POST", payload={}, report_root=report_root, personal_root=personal)[1],
            "ai_space": ai_space_route_response("/api/ai-space/rebuild", method="POST", payload={}, report_root=report_root, personal_root=personal)[1],
        }
        return {
            "ok": bool(results["multimodal"].get("ok")) and bool(results["yolo"].get("ok")) and bool(results["smart_classification"].get("ok")) and bool(results["ai_space"].get("ok")),
            "roots_count": len(roots),
            "results": compact_prepare_results(results),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def compact_prepare_results(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for name, payload in results.items():
        compact[name] = {
            "ok": payload.get("ok"),
            "degraded": payload.get("degraded"),
            "degraded_reason": payload.get("degraded_reason"),
            "asset_count": payload.get("asset_count") or payload.get("indexed_assets") or payload.get("indexed_count"),
            "detection_count": payload.get("detection_count") or (payload.get("counts") or {}).get("detections"),
            "cloud_used": payload.get("cloud_used") if "cloud_used" in payload else (payload.get("privacy") or {}).get("cloud_used"),
            "raw_path_returned": payload.get("raw_path_returned") if "raw_path_returned" in payload else (payload.get("privacy") or {}).get("raw_path_returned"),
        }
    return compact


def redact_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_paths(item) for item in value]
    if isinstance(value, str):
        return value.replace("/mnt/nas/openclaw/Personal", "[redacted-personal-root]").replace("/mnt/nas/", "[redacted-path]/").replace("/home/", "[redacted-home]/").replace("/root/", "[redacted-root]/").replace("F:\\", "[redacted-drive]\\").replace("C:\\", "[redacted-drive]\\")
    return value


def collect_safety(results: dict[str, dict[str, Any]]) -> dict[str, bool]:
    encoded = json.dumps(results, ensure_ascii=False)
    return {
        "raw_path_returned": any(marker in encoded for marker in ["/mnt/nas/", "/root/", "/home/", "F:\\", "C:\\"]),
        "delete_enabled": '"delete_enabled": true' in encoded or '"delete_allowed": true' in encoded,
        "overwrite_enabled": '"overwrite_enabled": true' in encoded or '"overwrite_allowed": true' in encoded,
        "uncontrolled_move_or_rename": '"uncontrolled_move_enabled": true' in encoded or '"uncontrolled_rename_enabled": true' in encoded,
        "hidden_chain_of_thought_saved": '"hidden_chain_of_thought_saved": true' in encoded,
        "private_cloud_egress": '"raw_private_cloud_egress": true' in encoded or '"cloud_private_raw_egress": true' in encoded,
    }


def bundle_reports(report_files: list[Path]) -> Path | None:
    try:
        evidence_dir = Path("evidence_for_gptpro")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        bundle = evidence_dir / f"digua_final_recording_readiness_{time.strftime('%Y%m%d-%H%M%S')}.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in report_files:
                if path.exists():
                    zf.write(path, arcname=path.name)
        sidecar = bundle.with_suffix(bundle.suffix + ".sha256.txt")
        sidecar.write_text(f"{sha256_file(bundle)}  {bundle.name}\n", encoding="utf-8")
        return bundle
    except Exception:
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
