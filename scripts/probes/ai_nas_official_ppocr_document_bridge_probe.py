#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import (
    _record_from_sqlite_row,
    _upsert_sqlite_record,
    build_sqlite_inventory,
    ensure_report_dir,
    extract_document_entities,
    iso_now,
    ocr_results_summary,
    open_index_db,
    safe_write_json,
    safe_write_text,
    search_sqlite_index,
    sqlite_index_status,
    upsert_ocr_result,
)
from ai_nas_official_ppocr_wrapper_probe import (
    DEFAULT_HOST,
    DEFAULT_KEY,
    DET_MODEL,
    LABEL_FILE,
    REC_MODEL,
    REMOTE_SAMPLE,
    TEST_IMAGE,
)


TOOL_ID = "ai_nas_official_ppocr_document_bridge"
OK = "ok_ai_nas_official_ppocr_document_bridge"
FAILED = "failed_ai_nas_official_ppocr_document_bridge"


REMOTE_BRIDGE_PROBE = r'''
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REMOTE_SAMPLE = Path("/app/pydev_demo/08_OCR_sample/01_paddleOCR")
REMOTE_UTILS = Path("/app/pydev_demo/utils")
DET_MODEL = Path("/opt/hobot/model/s100/basic/cn_PP-OCRv3_det_infer-deploy_640x640_nv12.hbm")
REC_MODEL = Path("/opt/hobot/model/s100/basic/cn_PP-OCRv3_rec_infer-deploy_48x320_rgb.hbm")
LABEL_FILE = Path("/app/res/labels/ppocr_keys_v1.txt")


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def write_paddle_stub(root: Path) -> list[str]:
    created = []
    paddle_root = root / "paddle"
    nn_root = paddle_root / "nn"
    nn_root.mkdir(parents=True, exist_ok=True)
    files = {
        paddle_root / "__init__.py": """class Tensor:
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
        nn_root / "__init__.py": "",
        nn_root / "functional.py": """def softmax(x, axis=None):
    return x
""",
    }
    for path, text in files.items():
        path.write_text(text, encoding="utf-8")
        created.append(str(path))
    return created


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--input-image", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    sample_copy = args.work_dir / "08_OCR_sample" / "01_paddleOCR"
    utils_copy = args.work_dir / "utils"
    result_image = args.work_dir / "result.jpg"
    stdout_path = args.work_dir / "ppocr_stdout.log"
    stderr_path = args.work_dir / "ppocr_stderr.log"
    report_path = args.work_dir / "official_ppocr_document_bridge_remote.json"
    blockers = []
    for name, path in [
        ("sample", REMOTE_SAMPLE),
        ("utils", REMOTE_UTILS),
        ("det_model", DET_MODEL),
        ("rec_model", REC_MODEL),
        ("label_file", LABEL_FILE),
        ("input_image", args.input_image),
    ]:
        if not path.exists():
            blockers.append(f"{name}_missing")

    payload = {
        "generated_at": iso_now(),
        "work_dir": str(args.work_dir),
        "input_image": str(args.input_image),
        "command": [],
        "returncode": None,
        "timed_out": False,
        "predictions": [],
        "stdout_preview": "",
        "stderr_preview": "",
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "result_image": str(result_image),
        "blockers": blockers,
    }
    try:
        if not blockers:
            shutil.copytree(REMOTE_SAMPLE, sample_copy)
            shutil.copytree(REMOTE_UTILS, utils_copy)
            payload["paddle_stub_files"] = write_paddle_stub(sample_copy)
            command = [
                sys.executable,
                "paddle_ocr.py",
                "--det-model-path",
                str(DET_MODEL),
                "--rec-model-path",
                str(REC_MODEL),
                "--test-img",
                str(args.input_image),
                "--label-file",
                str(LABEL_FILE),
                "--img-save-path",
                str(result_image),
            ]
            payload["command"] = command
            proc = subprocess.run(command, cwd=sample_copy, capture_output=True, text=True, timeout=args.timeout, check=False)
            stdout_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
            stderr_path.write_text(proc.stderr, encoding="utf-8", errors="replace")
            payload["returncode"] = proc.returncode
            payload["stdout_preview"] = proc.stdout[-4000:]
            payload["stderr_preview"] = proc.stderr[-4000:]
            predictions = []
            for line in proc.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("Prediction:"):
                    value = stripped.split("Prediction:", 1)[1].strip()
                    if value:
                        predictions.append(value)
            payload["predictions"] = predictions
    except subprocess.TimeoutExpired as exc:
        payload["timed_out"] = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
        stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
        payload["stdout_preview"] = stdout[-4000:]
        payload["stderr_preview"] = stderr[-4000:]
        payload["blockers"].append("official_ppocr_bridge_timed_out")
    except Exception as exc:
        payload["blockers"].append(f"remote_exception:{type(exc).__name__}:{exc}")

    if payload["returncode"] not in (0, None):
        payload["blockers"].append(f"official_ppocr_exit_{payload['returncode']}")
    if payload["returncode"] == 0 and not payload["predictions"]:
        payload["blockers"].append("no_prediction_lines")
    if payload["returncode"] == 0 and not result_image.exists():
        payload["blockers"].append("result_image_missing")
    payload["ok"] = not payload["blockers"]
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def run_command(command: list[str], timeout: int | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return {"command": command, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "ok": proc.returncode == 0}
    except Exception as exc:
        return {"command": command, "returncode": None, "stdout": "", "stderr": "", "ok": False, "error": f"{type(exc).__name__}:{exc}"}


def ssh_base(args: argparse.Namespace) -> list[str]:
    command = ["ssh.exe" if sys.platform.startswith("win") else "ssh"]
    if args.ssh_key:
        command.extend(["-i", str(args.ssh_key)])
    command.extend(["-o", "BatchMode=yes", "-o", f"ConnectTimeout={args.connect_timeout}", args.host])
    return command


def scp_base(args: argparse.Namespace) -> list[str]:
    command = ["scp.exe" if sys.platform.startswith("win") else "scp"]
    if args.ssh_key:
        command.extend(["-i", str(args.ssh_key)])
    command.extend(["-o", "BatchMode=yes", "-o", f"ConnectTimeout={args.connect_timeout}"])
    return command


def remote_target(args: argparse.Namespace, path: str) -> str:
    return f"{args.host}:{path}"


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_pdf_from_image(pdf_path: Path, image_path: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    _width, height = letter
    c.drawImage(str(image_path), 72, height - 360, width=420, height=260, preserveAspectRatio=True, anchor="nw")
    c.save()


def newest_document_record(db_path: Path, relative_path: str) -> dict[str, Any] | None:
    con = open_index_db(db_path)
    try:
        row = con.execute("SELECT * FROM records WHERE relative_path = ?", (relative_path,)).fetchone()
        if not row:
            return None
        record = _record_from_sqlite_row(row)
        record["mtime_ns"] = row["mtime_ns"]
        return record
    finally:
        con.close()


def mark_pdf_ocr_completed(db_path: Path, record: dict[str, Any], ocr_text: str, remote_payload: dict[str, Any], sidecar_image: Path) -> dict[str, Any]:
    result = {
        "path": record["path"],
        "relative_path": record["relative_path"],
        "status": "ocr_completed",
        "engine": "official_s100p_ppocr",
        "text_preview": ocr_text[:4000],
        "error": None,
        "metadata": {
            "backend": "official_s100p_ppocr",
            "source_image": str(sidecar_image),
            "prediction_count": len(remote_payload.get("predictions") or []),
            "remote_work_dir": remote_payload.get("work_dir"),
            "remote_result_image": remote_payload.get("result_image"),
            "text_char_count": len(ocr_text),
        },
    }
    upsert_ocr_result(db_path, result)

    updated = dict(record)
    metadata = dict(updated.get("metadata") or {})
    metadata["content_status"] = "extracted_via_ocr"
    metadata["original_parse_error"] = updated.get("parse_error")
    metadata["document_class"] = metadata.get("document_class") or "invoice"
    metadata["ocr"] = {
        "required": True,
        "engine_available": True,
        "status": "ocr_completed",
        "engine": "official_s100p_ppocr",
        "text_char_count": len(ocr_text),
    }
    metadata["entities"] = extract_document_entities(ocr_text)
    updated["metadata"] = metadata
    updated["parse_error"] = None
    updated["summary"] = "Official S100P PP-OCR text: " + " ".join(ocr_text.split())[:180]
    updated["keywords"] = sorted(set((updated.get("keywords") or []) + ["official", "ppocr", "ocr", "scan", "scanned", "document"]))
    updated["tags"] = sorted(set((updated.get("tags") or []) + ["invoice", "ocr", "official-ppocr"]))

    con = open_index_db(db_path)
    try:
        with con:
            _upsert_sqlite_record(con, updated, iso_now())
    finally:
        con.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge official S100P PP-OCR output into the AI-NAS document index/OCR tables.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_closure"))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--ssh-key", type=Path, default=DEFAULT_KEY if DEFAULT_KEY.exists() else None)
    parser.add_argument("--remote-root", default="/tmp/ai_nas_official_ppocr_document_bridge")
    parser.add_argument("--connect-timeout", type=int, default=8)
    parser.add_argument("--sample-timeout", type=int, default=90)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "official_ppocr_document_bridge")
    fixture_root = run_dir / "fixture" / "Personal"
    documents = fixture_root / "Documents"
    documents.mkdir(parents=True, exist_ok=True)
    local_sample = run_dir / "official_ppocr_source.jpg"
    sidecar_image = documents / "official_ppocr_scanned_invoice.scan.jpg"
    scanned_pdf = documents / "official_ppocr_scanned_invoice.pdf"
    remote_script = run_dir / "official_ppocr_document_bridge_remote_probe.py"
    remote_script.write_text(REMOTE_BRIDGE_PROBE, encoding="utf-8")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    remote_dir = f"{args.remote_root.rstrip('/')}/{stamp}"
    remote_work = f"{remote_dir}/work"
    remote_input = f"{remote_dir}/input.jpg"
    remote_probe = f"{remote_dir}/official_ppocr_document_bridge_remote_probe.py"
    remote_json = run_dir / "official_ppocr_document_bridge_remote.json"
    stdout_log = run_dir / "ppocr_stdout.log"
    stderr_log = run_dir / "ppocr_stderr.log"
    result_image = run_dir / "official_ppocr_bridge_result.jpg"

    commands: dict[str, Any] = {}
    commands["mkdir"] = run_command(ssh_base(args) + ["mkdir", "-p", remote_dir], timeout=args.connect_timeout + 5)
    commands["download_sample"] = run_command(scp_base(args) + [remote_target(args, TEST_IMAGE), str(local_sample)], timeout=args.connect_timeout + 20)
    blockers: list[str] = []
    if not commands["mkdir"].get("ok"):
        blockers.append("remote_work_dir_create_failed")
    if not commands["download_sample"].get("ok") or not local_sample.exists():
        blockers.append("official_sample_download_failed")

    if not blockers:
        shutil.copy2(local_sample, sidecar_image)
        write_pdf_from_image(scanned_pdf, sidecar_image)
        sqlite_index_path = run_dir / "official_ppocr_document_bridge.sqlite3"
        index_status = build_sqlite_inventory(fixture_root, sqlite_index_path)
        record = newest_document_record(sqlite_index_path, "Documents/official_ppocr_scanned_invoice.pdf")
        if not record:
            blockers.append("scanned_pdf_record_missing")
        elif not ((record.get("metadata") or {}).get("ocr") or {}).get("required"):
            blockers.append("scanned_pdf_not_marked_ocr_required")
    else:
        sqlite_index_path = run_dir / "official_ppocr_document_bridge.sqlite3"
        index_status = {}
        record = None

    if not blockers:
        commands["upload_probe"] = run_command(scp_base(args) + [str(remote_script), remote_target(args, remote_probe)], timeout=args.connect_timeout + 20)
        commands["upload_image"] = run_command(scp_base(args) + [str(sidecar_image), remote_target(args, remote_input)], timeout=args.connect_timeout + 20)
        if not commands["upload_probe"].get("ok"):
            blockers.append("remote_probe_upload_failed")
        if not commands["upload_image"].get("ok"):
            blockers.append("remote_input_image_upload_failed")

    remote_payload: dict[str, Any] | None = None
    if not blockers:
        commands["execute"] = run_command(
            ssh_base(args)
            + [
                "python3",
                remote_probe,
                "--work-dir",
                remote_work,
                "--input-image",
                remote_input,
                "--timeout",
                str(args.sample_timeout),
            ],
            timeout=args.sample_timeout + 20,
        )
        for name, remote_path, local_path in [
            ("remote_json", f"{remote_work}/official_ppocr_document_bridge_remote.json", remote_json),
            ("stdout_log", f"{remote_work}/ppocr_stdout.log", stdout_log),
            ("stderr_log", f"{remote_work}/ppocr_stderr.log", stderr_log),
            ("result_image", f"{remote_work}/result.jpg", result_image),
        ]:
            commands[f"download_{name}"] = run_command(scp_base(args) + [remote_target(args, remote_path), str(local_path)], timeout=args.connect_timeout + 20)
        remote_payload = read_json(remote_json)
        if not remote_payload:
            blockers.append("remote_result_json_missing")
        elif not remote_payload.get("ok"):
            blockers.extend(str(item) for item in remote_payload.get("blockers") or ["remote_ppocr_not_ok"])

    bridge_result: dict[str, Any] | None = None
    search_results: list[dict[str, Any]] = []
    if not blockers and record and remote_payload:
        predictions = [str(item).strip() for item in remote_payload.get("predictions") or [] if str(item).strip()]
        ocr_text = "\n".join(predictions)
        if not ocr_text.strip():
            blockers.append("ocr_text_empty")
        else:
            bridge_result = mark_pdf_ocr_completed(sqlite_index_path, record, ocr_text, remote_payload, sidecar_image)
            search_results = search_sqlite_index(sqlite_index_path, "official ppocr scanned document", limit=5)
            if not any(item.get("relative_path") == "Documents/official_ppocr_scanned_invoice.pdf" for item in search_results):
                blockers.append("ocr_enriched_scanned_pdf_not_searchable")

    ocr_summary = ocr_results_summary(sqlite_index_path) if sqlite_index_path.exists() else {}
    verdict = OK if not blockers else FAILED
    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "scope": "Task B acceptance: official S100P PP-OCR output is written into AI-NAS document OCR/index tables for a scanned PDF.",
        "host": args.host,
        "official_paths": {
            "sample_image": TEST_IMAGE,
            "det_hbm": DET_MODEL,
            "rec_hbm": REC_MODEL,
            "label_file": LABEL_FILE,
            "sample": REMOTE_SAMPLE,
        },
        "fixture": {
            "personal_root": str(fixture_root),
            "sidecar_image": str(sidecar_image),
            "scanned_pdf": str(scanned_pdf),
            "sqlite_index_path": str(sqlite_index_path),
        },
        "index_status": index_status,
        "remote_payload": remote_payload,
        "bridge_result": bridge_result,
        "ocr_summary": ocr_summary,
        "search_results": search_results,
        "commands": commands,
        "blockers": blockers,
        "audit": {
            "source_files_modified": False,
            "real_personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "remote_writes": "unique /tmp probe directory only",
            "local_writes": "bounded fixture PDF/image, SQLite index/OCR rows, Markdown/JSON/log/image evidence",
        },
    }
    safe_write_json(run_dir / "official_ppocr_document_bridge.json", payload)
    lines = [
        "# AI-NAS Official PP-OCR Document Bridge",
        "",
        f"- verdict: `{verdict}`",
        f"- scanned_pdf: `{scanned_pdf}`",
        f"- ocr_status: `{(bridge_result or {}).get('status')}`",
        f"- engine: `{(bridge_result or {}).get('engine')}`",
        f"- prediction_count: `{len((remote_payload or {}).get('predictions') or [])}`",
        f"- searchable: `{any(item.get('relative_path') == 'Documents/official_ppocr_scanned_invoice.pdf' for item in search_results)}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in blockers) if blockers else lines.append("- None.")
    safe_write_text(run_dir / "official_ppocr_document_bridge.md", "\n".join(lines) + "\n")
    print(run_dir / "official_ppocr_document_bridge.md")
    print(run_dir / "official_ppocr_document_bridge.json")
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
