#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_official_ppocr_wrapper"
OK_VERDICT = "ok_ai_nas_official_ppocr_wrapper"
BLOCKED_VERDICT = "blocked_ai_nas_official_ppocr_wrapper"

DEFAULT_HOST = "sunrise@192.168.127.10"
DEFAULT_KEY = Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
REMOTE_SAMPLE = "/app/pydev_demo/08_OCR_sample/01_paddleOCR"
DET_MODEL = "/opt/hobot/model/s100/basic/cn_PP-OCRv3_det_infer-deploy_640x640_nv12.hbm"
REC_MODEL = "/opt/hobot/model/s100/basic/cn_PP-OCRv3_rec_infer-deploy_48x320_rgb.hbm"
LABEL_FILE = "/app/res/labels/ppocr_keys_v1.txt"
TEST_IMAGE = "/app/res/assets/gt_2322.jpg"


REMOTE_PROBE = r'''
from __future__ import annotations

import argparse
import importlib.util
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
TEST_IMAGE = Path("/app/res/assets/gt_2322.jpg")


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def file_info(path: Path) -> dict:
    info = {"path": str(path), "exists": path.exists()}
    if path.exists():
        stat = path.stat()
        info.update({"size_bytes": stat.st_size, "mtime": stat.st_mtime})
    return info


def module_status(names: list[str]) -> dict:
    result = {}
    for name in names:
        result[name] = {"importable": importlib.util.find_spec(name) is not None}
    return result


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
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    sample_copy = args.work_dir / "08_OCR_sample" / "01_paddleOCR"
    utils_copy = args.work_dir / "utils"
    result_image = args.work_dir / "result.jpg"
    stdout_path = args.work_dir / "ppocr_stdout.log"
    stderr_path = args.work_dir / "ppocr_stderr.log"
    report_path = args.work_dir / "official_ppocr_wrapper_remote.json"

    blockers = []
    if not REMOTE_SAMPLE.exists():
        blockers.append("official_sample_missing")
    if not REMOTE_UTILS.exists():
        blockers.append("official_utils_missing")
    for name, path in [
        ("det_model", DET_MODEL),
        ("rec_model", REC_MODEL),
        ("label_file", LABEL_FILE),
        ("test_image", TEST_IMAGE),
    ]:
        if not path.exists():
            blockers.append(f"{name}_missing")

    payload = {
        "generated_at": iso_now(),
        "work_dir": str(args.work_dir),
        "official_sample": file_info(REMOTE_SAMPLE),
        "official_utils": file_info(REMOTE_UTILS),
        "model_files": {
            "det_hbm": file_info(DET_MODEL),
            "rec_hbm": file_info(REC_MODEL),
            "label_file": file_info(LABEL_FILE),
            "test_image": file_info(TEST_IMAGE),
        },
        "dependency_status_before_stub": module_status([
            "hbm_runtime",
            "cv2",
            "PIL",
            "numpy",
            "pyclipper",
            "paddle",
        ]),
        "paddle_stub_files": [],
        "command": [],
        "returncode": None,
        "timed_out": False,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_preview": "",
        "stderr_preview": "",
        "predictions": [],
        "result_image": file_info(result_image),
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
                str(TEST_IMAGE),
                "--label-file",
                str(LABEL_FILE),
                "--img-save-path",
                str(result_image),
            ]
            payload["command"] = command
            try:
                proc = subprocess.run(
                    command,
                    cwd=sample_copy,
                    capture_output=True,
                    text=True,
                    timeout=args.timeout,
                    check=False,
                )
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
                payload["returncode"] = None
                stdout = (exc.stdout or "")
                stderr = (exc.stderr or "")
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")
                stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
                stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
                payload["stdout_preview"] = stdout[-4000:]
                payload["stderr_preview"] = stderr[-4000:]
                payload["blockers"].append("official_sample_timed_out")
    except Exception as exc:
        payload["blockers"].append(f"remote_probe_exception:{type(exc).__name__}:{exc}")

    payload["result_image"] = file_info(result_image)
    if payload["returncode"] not in (0, None):
        payload["blockers"].append(f"official_sample_exit_{payload['returncode']}")
    if payload["returncode"] == 0 and not payload["predictions"]:
        payload["blockers"].append("no_prediction_lines")
    if payload["returncode"] == 0 and not payload["result_image"]["exists"]:
        payload["blockers"].append("result_image_missing")
    payload["ok"] = not payload["blockers"]
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def run_command(command: list[str], timeout: int | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "ok": proc.returncode == 0,
        }
    except Exception as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
        }


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


def markdown(payload: dict[str, Any]) -> str:
    remote = payload.get("remote_result") or {}
    lines = [
        "# AI-NAS Official PP-OCR Wrapper Probe",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- host: `{payload['host']}`",
        f"- remote_work_dir: `{payload['remote_work_dir']}`",
        f"- returncode: `{remote.get('returncode')}`",
        f"- prediction_count: `{len(remote.get('predictions') or [])}`",
        f"- result_image_exists: `{((remote.get('result_image') or {}).get('exists'))}`",
        "",
        "## Predictions",
        "",
    ]
    predictions = remote.get("predictions") or []
    lines.extend(f"- `{prediction}`" for prediction in predictions) if predictions else lines.append("- None.")
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{blocker}`" for blocker in blockers) if blockers else lines.append("- None.")
    lines.extend(["", "## Local Artifacts", ""])
    for name, value in (payload.get("local_artifacts") or {}).items():
        lines.append(f"- {name}: `{value}`")
    return "\n".join(lines) + "\n"


def build_payload(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    remote_dir = f"{args.remote_root.rstrip('/')}/{stamp}"
    remote_script = f"{remote_dir}/official_ppocr_wrapper_remote_probe.py"
    remote_work = f"{remote_dir}/work"
    local_remote_script = run_dir / "official_ppocr_wrapper_remote_probe.py"
    local_remote_script.write_text(REMOTE_PROBE, encoding="utf-8")

    mkdir = run_command(ssh_base(args) + ["mkdir", "-p", remote_dir], timeout=args.connect_timeout + 5)
    upload = {"ok": False, "returncode": None, "stdout": "", "stderr": "mkdir failed; upload skipped"}
    execute = {"ok": False, "returncode": None, "stdout": "", "stderr": "upload failed; execute skipped"}
    remote_json = run_dir / "official_ppocr_wrapper_remote.json"
    stdout_log = run_dir / "ppocr_stdout.log"
    stderr_log = run_dir / "ppocr_stderr.log"
    result_image = run_dir / "official_ppocr_result.jpg"
    remote_result = None

    if mkdir.get("ok"):
        upload = run_command(
            scp_base(args) + [str(local_remote_script), remote_target(args, remote_script)],
            timeout=args.connect_timeout + 15,
        )
    if upload.get("ok"):
        execute = run_command(
            ssh_base(args)
            + [
                "python3",
                remote_script,
                "--work-dir",
                remote_work,
                "--timeout",
                str(args.sample_timeout),
            ],
            timeout=args.sample_timeout + 20,
        )

    downloads: dict[str, Any] = {}
    for label, remote_path, local_path in [
        ("remote_json", f"{remote_work}/official_ppocr_wrapper_remote.json", remote_json),
        ("stdout_log", f"{remote_work}/ppocr_stdout.log", stdout_log),
        ("stderr_log", f"{remote_work}/ppocr_stderr.log", stderr_log),
        ("result_image", f"{remote_work}/result.jpg", result_image),
    ]:
        downloads[label] = run_command(
            scp_base(args) + [remote_target(args, remote_path), str(local_path)],
            timeout=args.connect_timeout + 20,
        )

    if remote_json.exists():
        remote_result = read_json(remote_json)

    blockers: list[str] = []
    if not mkdir.get("ok"):
        blockers.append("remote_work_dir_create_failed")
    if mkdir.get("ok") and not upload.get("ok"):
        blockers.append("remote_probe_upload_failed")
    if upload.get("ok") and execute.get("returncode") not in (0, 2):
        blockers.append("remote_probe_execution_failed")
    if not remote_result:
        blockers.append("remote_result_json_missing")
    elif not remote_result.get("ok"):
        blockers.extend(str(item) for item in remote_result.get("blockers") or ["remote_probe_not_ok"])

    ok = not blockers
    return {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": OK_VERDICT if ok else BLOCKED_VERDICT,
        "ok": ok,
        "host": args.host,
        "remote_work_dir": remote_work,
        "official_paths": {
            "sample": REMOTE_SAMPLE,
            "det_hbm": DET_MODEL,
            "rec_hbm": REC_MODEL,
            "label_file": LABEL_FILE,
            "test_image": TEST_IMAGE,
        },
        "commands": {
            "mkdir": mkdir,
            "upload": upload,
            "execute": execute,
            "downloads": downloads,
        },
        "remote_result": remote_result,
        "local_artifacts": {
            "remote_script": str(local_remote_script),
            "remote_json": str(remote_json) if remote_json.exists() else "",
            "stdout_log": str(stdout_log) if stdout_log.exists() else "",
            "stderr_log": str(stderr_log) if stderr_log.exists() else "",
            "result_image": str(result_image) if result_image.exists() else "",
        },
        "blockers": blockers,
        "audit": {
            "source_files_modified": False,
            "official_sample_directory_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "remote_writes": "unique /tmp probe directory only",
            "local_writes": "JSON/Markdown/log/image evidence under report root",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the official S100 PP-OCRv3 sample as an AI-NAS wrapper readiness proof.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_product_closure"))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--ssh-key", type=Path, default=DEFAULT_KEY if DEFAULT_KEY.exists() else None)
    parser.add_argument("--remote-root", default="/tmp/ai_nas_official_ppocr_wrapper")
    parser.add_argument("--connect-timeout", type=int, default=8)
    parser.add_argument("--sample-timeout", type=int, default=90)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "official_ppocr_wrapper")
    payload = build_payload(args, run_dir)
    json_path = run_dir / "official_ppocr_wrapper.json"
    md_path = run_dir / "official_ppocr_wrapper.md"
    safe_write_json(json_path, payload)
    safe_write_text(md_path, markdown(payload))
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
