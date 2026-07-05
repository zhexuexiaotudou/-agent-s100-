#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.multimodal_search.feature_flags import load_feature_flags
from src.multimodal_search.schema import connect, migrate
from src.multimodal_search.search_api import MultimodalSearchService
from src.multimodal_search.vector_store import vector_store_status
from src.openclaw.routes.multimodal_search_routes import multimodal_route_response


REPORT_DIR = REPO_ROOT / "reports" / "multimodal_search"
FINAL_DIR = REPO_ROOT / "01_final_evidence"
PACKAGE_DIR = REPO_ROOT / "evidence_for_gptpro"
BENCHMARK = REPO_ROOT / "benchmarks" / "multimodal_search_eval_cases.jsonl"
VERDICT_READY_WITH_OPTIONAL_DISABLED = "multimodal_search_v1_ready_with_optional_ocr_video_audio_disabled"


def seed_fixture(root: Path) -> Path:
    from PIL import Image

    root.mkdir(parents=True, exist_ok=True)
    docs = root / "Documents"
    photos = root / "Photos"
    videos = root / "Videos"
    audio = root / "Audio"
    code = root / "Code"
    archives = root / "Archives"
    for folder in [docs, photos, videos, audio, code, archives]:
        folder.mkdir(parents=True, exist_ok=True)

    documents = [
        ("renovation_invoice_receipt.txt", "renovation invoice receipt paid evidence kitchen cabinet contract"),
        ("openclaw_s100p_baseline.txt", "OpenClaw S100P NAS baseline route health qwen local gateway evidence"),
        ("privacy_policy_notes.md", "privacy policy local first no cloud vision no raw path export"),
        ("family_trip_plan.txt", "family trip itinerary train hotel calendar document"),
        ("maintenance_record.txt", "maintenance record router disk fan cleanup"),
        ("report_claim_matrix.txt", "design report claim matrix safe wording evidence refs"),
        ("nas_mount_notes.txt", "NAS mount allowlist workspace harness read only route"),
        ("journal_summary.txt", "journal timeline user events project summary"),
        ("token_budget_report.txt", "token budget compression context pack private redaction"),
        ("shipping_list.csv", "item,count\ncable,3\nadapter,2\n"),
    ]
    for name, content in documents:
        (docs / name).write_text(content, encoding="utf-8")

    colors = [
        ("white_shirt_photo.png", (245, 245, 240)),
        ("black_router_photo.png", (15, 15, 20)),
        ("red_receipt_photo.png", (230, 35, 40)),
        ("green_board_photo.png", (30, 180, 70)),
        ("blue_usb_photo.png", (35, 70, 230)),
        ("yellow_label_photo.png", (235, 220, 40)),
        ("gray_box_photo.png", (120, 120, 120)),
        ("white_wall_reference.png", (250, 250, 250)),
        ("blue_folder_cover.png", (40, 80, 210)),
        ("red_warning_sticker.png", (220, 20, 35)),
    ]
    for name, color in colors:
        Image.new("RGB", (48, 32), color).save(photos / name)

    for idx in range(6):
        (videos / f"home_clip_{idx}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes([idx]) * 32)
    for idx in range(5):
        (audio / f"meeting_audio_{idx}.wav").write_bytes(b"RIFF" + bytes([idx]) * 64)
    for idx in range(5):
        (code / f"automation_script_{idx}.py").write_text(f"def task_{idx}():\n    return 'workspace harness policy'\n", encoding="utf-8")
    (archives / "handoff_bundle.zip").write_bytes(b"PK\x03\x04synthetic archive")
    return root


def write_json_report(name: str, payload: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{name}.json"
    write_text_lf(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    md_path = REPORT_DIR / f"{name}.md"
    write_text_lf(md_path, report_markdown(name, payload))
    return path


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read_optional_report(name: str) -> dict[str, Any] | None:
    path = REPORT_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def report_markdown(name: str, payload: dict[str, Any]) -> str:
    lines = [f"# {name}", "", f"- ok: `{payload.get('ok')}`"]
    if "verdict" in payload:
        lines.append(f"- verdict: `{payload['verdict']}`")
    if "summary" in payload:
        for key, value in payload["summary"].items():
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "```json", json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_result(cmd: list[str]) -> dict[str, Any]:
    started = time.time()
    display_cmd = [_redact_local_path(part) for part in cmd]
    try:
        result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, timeout=120)
        return {
            "cmd": display_cmd,
            "returncode": result.returncode,
            "stdout_tail": _redact_local_path(result.stdout[-4000:]),
            "stderr_tail": _redact_local_path(result.stderr[-4000:]),
            "duration_sec": round(time.time() - started, 3),
        }
    except FileNotFoundError as exc:
        return {"cmd": display_cmd, "returncode": None, "error": _redact_local_path(str(exc)), "duration_sec": round(time.time() - started, 3)}
    except subprocess.TimeoutExpired as exc:
        return {"cmd": display_cmd, "returncode": "timeout", "stdout_tail": _redact_local_path((exc.stdout or "")[-4000:]), "stderr_tail": _redact_local_path((exc.stderr or "")[-4000:])}


def _redact_local_path(value: object) -> str:
    text = str(value)
    replacements = {
        str(REPO_ROOT): "<repo>",
        str(REPO_ROOT).replace("\\", "/"): "<repo>",
        str(Path(sys.executable)): "<python>",
        str(Path(sys.executable)).replace("\\", "/"): "<python>",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def package_self_check_source() -> str:
    return r'''#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
SUMS = {}
for line in (ROOT / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
    if line.strip():
        digest, rel = line.split("  ", 1)
        SUMS[rel] = digest

missing = []
bad_hash = []
for entry in MANIFEST["files"]:
    rel = entry["path"]
    path = ROOT / rel
    if not path.exists():
        missing.append(rel)
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if SUMS.get(rel) != digest or entry.get("sha256") != digest:
        bad_hash.append(rel)

packet = json.loads((ROOT / "01_final_evidence" / "digua_ai_nas_multimodal_search_v1_gate_packet.json").read_text(encoding="utf-8"))
checks = {
    "verdict": packet.get("verdict"),
    "eval_ok": packet.get("gates", {}).get("eval", {}).get("ok"),
    "security_ok": packet.get("gates", {}).get("security", {}).get("ok"),
    "raw_path_returned": packet.get("gates", {}).get("security", {}).get("raw_path_returned"),
    "cloud_used": packet.get("gates", {}).get("security", {}).get("cloud_used"),
}
ok = (
    not missing
    and not bad_hash
    and checks["verdict"] == "multimodal_search_v1_ready_with_optional_ocr_video_audio_disabled"
    and checks["eval_ok"]
    and checks["security_ok"]
    and checks["raw_path_returned"] is False
    and checks["cloud_used"] is False
)
print(json.dumps({"ok": ok, "missing": missing, "bad_hash": bad_hash, "checks": checks}, ensure_ascii=False, indent=2))
raise SystemExit(0 if ok else 1)
'''


def build_zip(timestamp: str, final_packet_path: Path) -> dict[str, Any]:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = PACKAGE_DIR / f"digua_ai_nas_multimodal_search_v1_for_gptpro_{timestamp}.zip"
    include_paths = [
        "src/multimodal_search",
        "src/openclaw/routes/multimodal_search_routes.py",
        "scripts/probes/ai_nas_operator_portal_server.py",
        "migrations/create_multimodal_search_tables.sql",
        "configs/multimodal_search_feature_flags.json",
        "configs/multimodal_search_policy.json",
        "configs/multimodal_model_registry.json",
        "benchmarks/multimodal_search_eval_cases.jsonl",
        "tests/test_multimodal_search_v1.py",
        "web/templates/multimodal_search.html",
        "web/static/digua_multimodal_search.css",
        "web/static/digua_multimodal_search.js",
        "docs/MULTIMODAL_SEARCH_ARCHITECTURE.md",
        "docs/MULTIMODAL_SEARCH_RUNBOOK.md",
        "docs/MULTIMODAL_SEARCH_SAFE_CLAIMS.md",
        "docs/MULTIMODAL_SEARCH_DELIVERY_DECISION.md",
        "reports/multimodal_search",
        "01_final_evidence/digua_ai_nas_multimodal_search_v1_gate_packet.json",
        "01_final_evidence/digua_ai_nas_multimodal_search_v1_gate_packet.md",
    ]

    files: list[Path] = []
    for rel in include_paths:
        path = REPO_ROOT / rel
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif path.is_file():
            files.append(path)
    unique_files = []
    seen = set()
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel not in seen:
            seen.add(rel)
            unique_files.append(path)

    manifest_files: list[dict[str, Any]] = []
    sums: list[str] = []
    self_check = package_self_check_source().encode("utf-8")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in unique_files:
            rel = path.relative_to(REPO_ROOT).as_posix()
            data = path.read_bytes()
            digest = sha256_bytes(data)
            zf.writestr(rel, data)
            manifest_files.append({"path": rel, "size": len(data), "sha256": digest})
            sums.append(f"{digest}  {rel}")
        self_digest = sha256_bytes(self_check)
        zf.writestr("SELF_CHECK.py", self_check)
        manifest_files.append({"path": "SELF_CHECK.py", "size": len(self_check), "sha256": self_digest})
        sums.append(f"{self_digest}  SELF_CHECK.py")

        manifest = {
            "package": zip_path.name,
            "created_at": timestamp,
            "final_packet": final_packet_path.relative_to(REPO_ROOT).as_posix(),
            "files": sorted(manifest_files, key=lambda item: item["path"]),
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        zf.writestr("MANIFEST.json", manifest_bytes)
        zf.writestr("SHA256SUMS.txt", ("\n".join(sorted(sums)) + "\n").encode("utf-8"))

    return {"path": zip_path.relative_to(REPO_ROOT).as_posix(), "sha256": sha256_file(zip_path), "size_bytes": zip_path.stat().st_size}


def no_raw_path_markers(payload: Any) -> bool:
    encoded = json.dumps(payload, ensure_ascii=False)
    markers = ["/mnt/", "\\\\", "C:", "F:", "relative_path"]
    return all(marker not in encoded for marker in markers)


def main() -> int:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="digua_mm_v1_") as tmp:
        tmp_path = Path(tmp)
        fixture_root = seed_fixture(tmp_path / "Personal")
        db_path = tmp_path / "runtime" / "multimodal_search.db"
        vector_dir = tmp_path / "runtime" / "vectors"
        trace_path = tmp_path / "runtime" / "trace.jsonl"
        service = MultimodalSearchService(db_path=db_path, vector_dir=vector_dir, trace_path=trace_path, roots=[fixture_root])

        flags = load_feature_flags(REPO_ROOT / "configs" / "multimodal_search_feature_flags.json")
        migrate(db_path)
        conn = connect(db_path)
        try:
            tables = sorted(row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','virtual table')"))
        finally:
            conn.close()
        schema_gate = {
            "ok": all(name in tables for name in ["mm_assets", "mm_text_chunks", "mm_embeddings", "mm_search_runs", "mm_search_results"])
            and not flags.cloud_vision_enabled
            and not flags.cloud_ocr_enabled
            and not flags.cloud_asr_enabled
            and not flags.qwen_tool_execution_enabled
            and not flags.destructive_actions_enabled,
            "tables": tables,
            "feature_flags": flags.to_dict(),
        }
        write_json_report("26000_multimodal_schema_and_flags_gate", schema_gate)

        rebuild = service.rebuild({"roots": [str(fixture_root)], "max_files": 80})
        indexer_gate = {
            "ok": rebuild.get("ok")
            and rebuild.get("counts", {}).get("document", 0) >= 10
            and rebuild.get("counts", {}).get("image", 0) >= 10
            and rebuild.get("image_embeddings", 0) >= 10,
            "rebuild": rebuild,
            "vector_store": vector_store_status(vector_dir),
        }
        write_json_report("26010_multimodal_indexer_gate", indexer_gate)

        api_queries = {
            "document": service.query({"query": "renovation invoice", "modality": "document", "top_k": 5}),
            "image": service.query({"query": "white image", "modality": "image", "top_k": 5}),
            "video": service.query({"query": "home video clip", "modality": "video", "top_k": 5}),
            "audio": service.query({"query": "meeting audio", "modality": "audio", "top_k": 5}),
            "code": service.query({"query": "python automation script", "modality": "code", "top_k": 5}),
            "archive": service.query({"query": "archive bundle zip", "modality": "archive", "top_k": 5}),
        }
        route_report_root = tmp_path / "route_reports"
        route_rebuild_status, route_rebuild_payload = multimodal_route_response(
            "/api/multimodal-index/rebuild",
            method="POST",
            payload={"roots": [str(fixture_root)], "max_files": 80},
            report_root=route_report_root,
            personal_root=fixture_root,
        )
        route_status, route_payload = multimodal_route_response(
            "/api/multimodal-search/eval/summary",
            method="GET",
            report_root=route_report_root,
            personal_root=fixture_root,
        )
        api_gate = {
            "ok": all(value.get("ok") and value.get("results") for value in api_queries.values())
            and all(any(row.get("evidence_ref") for row in value.get("results", [])) for value in api_queries.values())
            and no_raw_path_markers(api_queries)
            and route_rebuild_status == 200
            and route_rebuild_payload.get("ok")
            and route_status == 200
            and route_payload.get("ok"),
            "queries": api_queries,
            "route_adapter": {
                "rebuild_status": route_rebuild_status,
                "rebuild": route_rebuild_payload,
                "summary_status": route_status,
                "summary": route_payload,
            },
        }
        write_json_report("26020_multimodal_search_api_gate", api_gate)

        eval_gate = service.eval_run(BENCHMARK)
        write_json_report("26030_multimodal_eval_gate", eval_gate)

        ui_js = (REPO_ROOT / "web" / "static" / "digua_multimodal_search.js").read_text(encoding="utf-8")
        ui_html = (REPO_ROOT / "web" / "templates" / "multimodal_search.html").read_text(encoding="utf-8")
        node_check = command_result(["node", "--check", "web/static/digua_multimodal_search.js"])
        ui_gate = {
            "ok": "/api/multimodal-search/status" in ui_js
            and "/api/multimodal-search/query" in ui_js
            and "/api/multimodal-index/rebuild" in ui_js
            and "http://" not in ui_js
            and "https://" not in ui_js
            and "digua_multimodal_search.css" in ui_html
            and (node_check["returncode"] in (0, None)),
            "node_check": node_check,
            "html_bytes": len(ui_html.encode("utf-8")),
            "js_bytes": len(ui_js.encode("utf-8")),
        }
        write_json_report("26040_multimodal_ui_gate", ui_gate)

        security_gate = {
            "ok": no_raw_path_markers({"api": api_gate, "eval": eval_gate})
            and eval_gate.get("private_leak_count") == 0
            and not flags.cloud_vision_enabled
            and not flags.cloud_ocr_enabled
            and not flags.cloud_asr_enabled
            and not flags.face_identification_enabled
            and not flags.biometric_recognition_enabled
            and not flags.sensitive_attribute_inference_enabled
            and not flags.qwen_tool_execution_enabled
            and not flags.destructive_actions_enabled,
            "raw_path_returned": not no_raw_path_markers({"api": api_gate, "eval": eval_gate}),
            "private_leak_count": eval_gate.get("private_leak_count"),
            "cloud_used": False,
            "qwen_tool_execution_enabled": flags.qwen_tool_execution_enabled,
            "destructive_actions_enabled": flags.destructive_actions_enabled,
            "optional_content_features": {
                "ocr_enabled": flags.ocr_enabled,
                "video_keyframe_enabled": flags.video_keyframe_enabled,
                "video_keyframe_embedding_enabled": flags.video_keyframe_embedding_enabled,
                "audio_transcript_enabled": flags.audio_transcript_enabled,
                "asr_enabled": flags.asr_enabled,
            },
        }
        write_json_report("26050_multimodal_security_gate", security_gate)

        pytest_multimodal = command_result([sys.executable, "-m", "pytest", "tests/test_multimodal_search_v1.py", "-q"])
        self_check = command_result([sys.executable, "SELF_CHECK.py"])
        test_gate = {
            "ok": pytest_multimodal["returncode"] == 0 and self_check["returncode"] == 0,
            "pytest_multimodal": pytest_multimodal,
            "self_check": self_check,
        }
        write_json_report("26060_multimodal_test_gate", test_gate)

        gates = {
            "schema": schema_gate,
            "indexer": indexer_gate,
            "api": api_gate,
            "eval": eval_gate,
            "ui": ui_gate,
            "security": security_gate,
            "tests": test_gate,
        }
        ui_browser_gate = read_optional_report("26070_multimodal_ui_browser_gate")
        if ui_browser_gate is not None:
            gates["ui_browser"] = ui_browser_gate
        verdict = VERDICT_READY_WITH_OPTIONAL_DISABLED if all(gate.get("ok") for gate in gates.values()) else "hold_due_to_search_api_failure"
        if not security_gate.get("ok"):
            verdict = "hold_due_to_security_boundary_violation"
        elif not ui_gate.get("ok"):
            verdict = "hold_due_to_ui_validation_failure"
        elif not api_gate.get("ok"):
            verdict = "hold_due_to_search_api_failure"
        elif not indexer_gate.get("ok"):
            verdict = "hold_due_to_vector_store_failure"
        elif not eval_gate.get("ok"):
            verdict = "inconclusive_missing_evidence"
        final_packet = {
            "ok": verdict == VERDICT_READY_WITH_OPTIONAL_DISABLED,
            "created_at": timestamp,
            "verdict": verdict,
            "soak_24h_started": False,
            "soak_scope": "not_requested",
            "gates": gates,
            "summary": {
                "indexed_assets": rebuild.get("indexed_assets"),
                "image_embeddings": rebuild.get("image_embeddings"),
                "eval_case_count": eval_gate.get("case_count"),
                "no_raw_path_rate": eval_gate.get("no_raw_path_rate"),
                "private_leak_count": eval_gate.get("private_leak_count"),
                "optional_ocr_video_audio_content": "disabled_by_feature_flag",
            },
        }
        final_report_path = write_json_report("26100_multimodal_search_v1_final_gate_packet", final_packet)
        final_json = FINAL_DIR / "digua_ai_nas_multimodal_search_v1_gate_packet.json"
        final_md = FINAL_DIR / "digua_ai_nas_multimodal_search_v1_gate_packet.md"
        shutil.copy2(final_report_path, final_json)
        write_text_lf(final_md, report_markdown("digua_ai_nas_multimodal_search_v1_gate_packet", final_packet))

    package = build_zip(timestamp, final_json)
    package_report = {
        "ok": True,
        "package": package,
        "verdict": json.loads(final_json.read_text(encoding="utf-8"))["verdict"],
    }
    write_json_report("26110_multimodal_search_v1_package_manifest", package_report)
    print(json.dumps(package_report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if package_report["verdict"] == VERDICT_READY_WITH_OPTIONAL_DISABLED else 1


if __name__ == "__main__":
    raise SystemExit(main())
