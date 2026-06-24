#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_queue_health_snapshot"


def run_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_cmd(args: argparse.Namespace, command: str, timeout: int = 30) -> dict[str, Any]:
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
        timeout=timeout,
    )


def parse_remote_json(result: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError as exc:
        return {
            "verdict": "failed_parse_dream7b_queue_health_snapshot",
            "error": f"{type(exc).__name__}:{exc}",
            "remote_result": result,
        }
    return payload if isinstance(payload, dict) else {"error": f"non_dict_remote_payload:{type(payload).__name__}"}


def local_latest_json(root: Path, pattern: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}
    return path, payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only current-health snapshot for the Dream7B queue-batch default service."
    )
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    args = parser.parse_args()

    remote_script = r"""
python3 - <<'PY'
import glob
import json
import pathlib
import subprocess

QUEUE_SERVICE = "dream7b-bpu-batch-queue.service"
GATEWAY_SERVICE = "dream7b-local-openai-gateway.service"
OPENCLAW_SERVICE = "openclaw-gateway.service"
PORT = "18888"
SUMMARY = pathlib.Path("/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/cross_job_queue_service_summary.json")
PENDING = pathlib.Path("/mnt/nas/openclaw/queues/dream7b-bpu/pending")
PROCESSING = pathlib.Path("/mnt/nas/openclaw/queues/dream7b-bpu/processing")


def cmd(args):
    proc = subprocess.run(args, text=True, capture_output=True)
    return {
        "args": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def first_stdout(args):
    out = cmd(args)["stdout"].splitlines()
    return out[0].strip() if out else ""


def user_systemctl(*parts):
    return [
        "sudo",
        "-n",
        "env",
        "XDG_RUNTIME_DIR=/run/user/0",
        "systemctl",
        "--user",
        *parts,
    ]


def count_jsonl(path):
    return len(list(path.glob("*.jsonl"))) if path.is_dir() else None


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}:{exc}"}


queue_active = first_stdout(["systemctl", "is-active", QUEUE_SERVICE])
queue_enabled = first_stdout(["systemctl", "is-enabled", QUEUE_SERVICE])
queue_main_pid = first_stdout(["systemctl", "show", QUEUE_SERVICE, "-p", "MainPID", "--value"])
queue_n_restarts = first_stdout(["systemctl", "show", QUEUE_SERVICE, "-p", "NRestarts", "--value"])
gateway_active = first_stdout(user_systemctl("is-active", GATEWAY_SERVICE))
gateway_enabled = first_stdout(user_systemctl("is-enabled", GATEWAY_SERVICE))
gateway_main_pid = first_stdout(user_systemctl("show", GATEWAY_SERVICE, "-p", "MainPID", "--value"))
openclaw_active = first_stdout(user_systemctl("is-active", OPENCLAW_SERVICE))
listener_pid = first_stdout(["sudo", "-n", "lsof", "-t", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-P", "-n"])
health_raw = first_stdout(["curl", "-sS", "--max-time", "3", f"http://127.0.0.1:{PORT}/health"])
try:
    health = json.loads(health_raw) if health_raw else {}
except Exception as exc:
    health = {"_error": f"{type(exc).__name__}:{exc}", "raw": health_raw}

summary = read_json(SUMMARY)
runs = summary.get("runs") or [] if isinstance(summary, dict) else []
partial_runs = [
    row
    for row in runs
    if row.get("run_reason") == "partial_batch_flush_timeout"
    and int(row.get("pending_count_at_start") or 0) > 1
    and int(row.get("returncode") or 0) == 0
    and row.get("runner_verdict") == "ok_dream7b_bpu_segment_major_load_once_queue_runner"
]
latest_partial = partial_runs[-1] if partial_runs else {}

text_reports = sorted(
    glob.glob("/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_*/text_queue_run.json"),
    key=lambda item: pathlib.Path(item).stat().st_mtime,
)
latest_text_path = text_reports[-1] if text_reports else ""
latest_text = read_json(pathlib.Path(latest_text_path)) if latest_text_path else {}

ps = cmd(["ps", "-eo", "pid=,args="])["stdout"].splitlines()
true_batch_processes = [
    line.strip()
    for line in ps
    if ("dream7b_true_batch" in line or "compile_dream_true_batch" in line)
    and "grep" not in line
]
pending_count = count_jsonl(PENDING)
processing_count = count_jsonl(PROCESSING)
checks = {
    "queue_batch_service_active": queue_active == "active",
    "queue_batch_service_enabled": queue_enabled == "enabled",
    "gateway_service_active": gateway_active == "active",
    "gateway_service_enabled": gateway_enabled == "enabled",
    "openclaw_gateway_active": openclaw_active == "active",
    "gateway_health_ok": health.get("ok") is True and health.get("model") == "Dream7B-S100P-local",
    "gateway_listener_matches_main_pid": bool(listener_pid) and listener_pid == gateway_main_pid,
    "queue_idle_at_probe": pending_count == 0 and processing_count == 0,
    "latest_text_queue_run_ok": latest_text.get("verdict") == "ok_dream7b_bpu_text_queue_run"
    and latest_text.get("job_status") == "done",
    "partial_batch_flush_evidence_ready": bool(partial_runs),
    "no_true_batch_or_compile_process": len(true_batch_processes) == 0,
}
payload = {
    "service": {
        "queue_active": queue_active,
        "queue_enabled": queue_enabled,
        "queue_main_pid": queue_main_pid,
        "queue_n_restarts": queue_n_restarts,
        "gateway_active": gateway_active,
        "gateway_enabled": gateway_enabled,
        "gateway_main_pid": gateway_main_pid,
        "openclaw_gateway_active": openclaw_active,
        "listener_pid": listener_pid,
    },
    "gateway_health": health,
    "queue": {
        "pending_count": pending_count,
        "processing_count": processing_count,
    },
    "latest_partial_batch_flush": {
        "summary_path": str(SUMMARY),
        "partial_run_count": len(partial_runs),
        "run_dir": latest_partial.get("run_dir"),
        "pending_count_at_start": latest_partial.get("pending_count_at_start"),
        "effective_max_job_count": latest_partial.get("effective_max_job_count"),
        "processed_request_count": latest_partial.get("processed_request_count"),
        "ms_per_request": latest_partial.get("amortized_wall_ms_per_processed_request"),
    },
    "latest_text_queue_run": {
        "path": latest_text_path,
        "verdict": latest_text.get("verdict"),
        "job_status": latest_text.get("job_status"),
        "processed_count": latest_text.get("processed_count"),
        "result_count": latest_text.get("result_count"),
        "ms_per_request": latest_text.get("amortized_wall_ms_per_processed_request"),
    },
    "true_batch_processes": true_batch_processes,
    "checks": checks,
}
payload["verdict"] = "ok_dream7b_queue_health_snapshot" if all(checks.values()) else "warning_dream7b_queue_health_snapshot"
print(json.dumps(payload, ensure_ascii=False))
PY
"""
    remote = ssh_cmd(args, remote_script, timeout=30)
    remote_payload = parse_remote_json(remote)
    fast_path_path, fast_path = local_latest_json(
        args.out_root, "dream7b_fast_path_regression_*/dream7b_fast_path_regression.json"
    )
    fast_cases = {str(case.get("id")): case for case in fast_path.get("cases") or []}
    quick_ready = fast_cases.get("quick_ready") or {}
    localized_status = fast_cases.get("chinese_short") or {}
    fast_path_summary = {
        "path": str(fast_path_path) if fast_path_path else None,
        "verdict": fast_path.get("verdict"),
        "quick_ready_first_content_ms": quick_ready.get("first_content_ms"),
        "quick_ready_execution_path": (quick_ready.get("dream7b_candidate") or {}).get("execution_path"),
        "localized_status_first_content_ms": localized_status.get("first_content_ms"),
        "localized_status_execution_path": (localized_status.get("dream7b_candidate") or {}).get("execution_path"),
    }

    remote_checks = remote_payload.get("checks") or {}
    local_checks = {
        "fast_path_regression_ok": fast_path.get("verdict") == "ok_dream7b_fast_path_regression",
        "quick_ready_fast_path_ok": fast_path_summary["quick_ready_execution_path"] == "gateway_fast_ready",
        "localized_status_fast_path_ok": fast_path_summary["localized_status_execution_path"]
        == "gateway_fast_local_status",
    }
    all_checks = {**remote_checks, **local_checks}
    verdict = (
        "ok_dream7b_queue_health_snapshot"
        if all(all_checks.values())
        else "warning_dream7b_queue_health_snapshot"
    )
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "remote_host": args.remote_host,
        "remote": remote_payload,
        "fast_path_regression": fast_path_summary,
        "checks": all_checks,
        "decision": {
            "queue_batch_service_remains_default": verdict.startswith("ok_"),
            "do_not_start_true_batch_runtime_now": True,
            "do_not_start_compile_now": True,
            "read_only_probe": True,
        },
        "remote_command": remote,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_queue_health_snapshot_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_queue_health_snapshot.json"
    out_md = out_dir / "dream7b_queue_health_snapshot.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    service = remote_payload.get("service") or {}
    queue = remote_payload.get("queue") or {}
    latest_text = remote_payload.get("latest_text_queue_run") or {}
    latest_partial = remote_payload.get("latest_partial_batch_flush") or {}
    lines = [
        "# Dream7B Queue Health Snapshot",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- queue_active: `{service.get('queue_active')}`",
        f"- queue_enabled: `{service.get('queue_enabled')}`",
        f"- gateway_active: `{service.get('gateway_active')}`",
        f"- gateway_enabled: `{service.get('gateway_enabled')}`",
        f"- openclaw_gateway_active: `{service.get('openclaw_gateway_active')}`",
        f"- pending_count: `{queue.get('pending_count')}`",
        f"- processing_count: `{queue.get('processing_count')}`",
        f"- true_batch_process_count: `{len(remote_payload.get('true_batch_processes') or [])}`",
        "",
        "## Latest Text Queue Run",
        "",
        f"- path: `{latest_text.get('path')}`",
        f"- verdict: `{latest_text.get('verdict')}`",
        f"- job_status: `{latest_text.get('job_status')}`",
        f"- ms_per_request: `{latest_text.get('ms_per_request')}`",
        "",
        "## Partial Batch Flush Evidence",
        "",
        f"- run_dir: `{latest_partial.get('run_dir')}`",
        f"- pending_count_at_start: `{latest_partial.get('pending_count_at_start')}`",
        f"- processed_request_count: `{latest_partial.get('processed_request_count')}`",
        f"- ms_per_request: `{latest_partial.get('ms_per_request')}`",
        "",
        "## Fast Path",
        "",
        f"- regression_path: `{fast_path_summary.get('path')}`",
        f"- quick_ready_first_content_ms: `{fast_path_summary.get('quick_ready_first_content_ms')}`",
        f"- localized_status_first_content_ms: `{fast_path_summary.get('localized_status_first_content_ms')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in all_checks.items())
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if verdict.startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
