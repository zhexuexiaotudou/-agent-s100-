from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_ROLLBACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_rollback_report_latest.json"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_CANDIDATE_ID = "seg27_28_lmheadq16_last_token_sentinel"


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def get_path(payload: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    cursor: Any = payload
    for key in keys:
        if not isinstance(cursor, dict):
            return default
        cursor = cursor.get(key)
    return default if cursor is None else cursor


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def generated_at() -> str:
    return datetime.now().astimezone().isoformat()


def run_cmd(command: list[str], timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "args": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_command(args: Any, command: str, timeout: int = 90) -> dict[str, Any]:
    return run_cmd(
        [
            "ssh.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            command,
        ],
        timeout,
    )


def sync_to_nas(args: Any, report_dir: Path, json_name: str, md_name: str) -> dict[str, Any]:
    remote_dir = f"{args.remote_report_root.rstrip('/')}/{report_dir.name}"
    mkdir = ssh_command(args, f"mkdir -p {remote_dir}", timeout=30)
    if mkdir["returncode"] != 0:
        return {"ok": False, "remote_dir": remote_dir, "mkdir": mkdir}
    scp = run_cmd(
        [
            "scp.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            str(report_dir / json_name),
            str(report_dir / md_name),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def rollback_context(path: Path) -> dict[str, Any]:
    rollback = read_json(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "loaded": rollback is not None,
        "verdict": rollback.get("verdict") if rollback else None,
        "summary": rollback.get("summary") if rollback else {},
        "candidate_artifact_present": get_path(rollback, "summary", "candidate_artifact_present") is True,
        "candidate_manifest_verified": get_path(rollback, "summary", "candidate_manifest_verified") is True,
        "production_path_unchanged": get_path(rollback, "summary", "production_path_unchanged") is True,
    }


def write_latest(out_root: Path, stem: str, json_path: Path, md_path: Path) -> None:
    (out_root / f"{stem}_latest.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out_root / f"{stem}_latest.md").write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
