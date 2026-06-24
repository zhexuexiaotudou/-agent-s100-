#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


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
            "verdict": "failed_parse_remote_queue_partial_batch_flush_probe",
            "error": f"{type(exc).__name__}:{exc}",
            "remote_result": result,
        }
    return payload if isinstance(payload, dict) else {"error": f"non_dict_remote_payload:{type(payload).__name__}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only evidence probe for Dream7B queue partial-batch flush.")
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

SERVICE = "dream7b-bpu-batch-queue.service"
SCRIPT = pathlib.Path("/mnt/nas/openclaw/runtimes/dream7b-bpu-segment-major-default/scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py")
SUMMARY = pathlib.Path("/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/cross_job_queue_service_summary.json")
PENDING = pathlib.Path("/mnt/nas/openclaw/queues/dream7b-bpu/pending")
PROCESSING = pathlib.Path("/mnt/nas/openclaw/queues/dream7b-bpu/processing")


def cmd(args):
    completed = subprocess.run(args, text=True, capture_output=True)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def cmd_stdout(args):
    return cmd(args)["stdout"].splitlines()[0].strip() if cmd(args)["stdout"].strip() else ""


def count_jsonl(path):
    return len(list(path.glob("*.jsonl"))) if path.is_dir() else None


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}:{exc}"}


service_active = cmd_stdout(["systemctl", "is-active", SERVICE])
service_enabled = cmd_stdout(["systemctl", "is-enabled", SERVICE])
gateway_active = cmd_stdout([
    "sudo",
    "-n",
    "env",
    "XDG_RUNTIME_DIR=/run/user/0",
    "systemctl",
    "--user",
    "is-active",
    "dream7b-local-openai-gateway.service",
])
openclaw_gateway_active = cmd_stdout([
    "sudo",
    "-n",
    "env",
    "XDG_RUNTIME_DIR=/run/user/0",
    "systemctl",
    "--user",
    "is-active",
    "openclaw-gateway.service",
])
script_text = SCRIPT.read_text(encoding="utf-8") if SCRIPT.exists() else ""
summary = read_json(SUMMARY)
runs = summary.get("runs") or [] if isinstance(summary, dict) else []
partial_runs = [
    row
    for row in runs
    if row.get("run_reason") == "partial_batch_flush_timeout"
    and int(row.get("pending_count_at_start") or 0) > 1
    and int(row.get("effective_max_job_count") or 0) == int(row.get("pending_count_at_start") or 0)
    and int(row.get("processed_request_count") or 0) == int(row.get("pending_count_at_start") or 0)
    and int(row.get("returncode") or 0) == 0
    and row.get("runner_verdict") == "ok_dream7b_bpu_segment_major_load_once_queue_runner"
]
latest_partial = partial_runs[-1] if partial_runs else {}
text_reports = sorted(
    glob.glob("/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_*/text_queue_run.json"),
    key=lambda item: pathlib.Path(item).stat().st_mtime,
)
latest_text_report_path = text_reports[-1] if text_reports else ""
latest_text_report = read_json(pathlib.Path(latest_text_report_path)) if latest_text_report_path else {}
pending_count = count_jsonl(PENDING)
processing_count = count_jsonl(PROCESSING)
checks = {
    "service_active": service_active == "active",
    "service_enabled": service_enabled == "enabled",
    "gateway_active": gateway_active == "active",
    "openclaw_gateway_active": openclaw_gateway_active == "active",
    "deployed_code_has_partial_flush": "partial_batch_flush_timeout" in script_text,
    "partial_batch_flush_evidence_ready": bool(partial_runs),
    "latest_text_queue_run_ok": latest_text_report.get("verdict") == "ok_dream7b_bpu_text_queue_run",
    "latest_text_queue_job_done": latest_text_report.get("job_status") == "done",
    "queue_empty_at_probe": pending_count == 0 and processing_count == 0,
}
payload = {
    "service": {
        "active": service_active,
        "enabled": service_enabled,
        "gateway_active": gateway_active,
        "openclaw_gateway_active": openclaw_gateway_active,
    },
    "deployed_script": {
        "path": str(SCRIPT),
        "exists": SCRIPT.exists(),
        "has_partial_batch_flush": "partial_batch_flush_timeout" in script_text,
    },
    "queue": {
        "pending_count": pending_count,
        "processing_count": processing_count,
    },
    "service_summary": {
        "path": str(SUMMARY),
        "exists": SUMMARY.exists(),
        "verdict": summary.get("verdict") if isinstance(summary, dict) else None,
        "processed_run_count": summary.get("processed_run_count") if isinstance(summary, dict) else None,
        "failed_run_count": summary.get("failed_run_count") if isinstance(summary, dict) else None,
        "latest_partial_batch_run": latest_partial,
    },
    "latest_text_queue_run": {
        "path": latest_text_report_path,
        "verdict": latest_text_report.get("verdict"),
        "job_status": latest_text_report.get("job_status"),
        "processed_count": latest_text_report.get("processed_count"),
        "result_count": latest_text_report.get("result_count"),
        "amortized_wall_ms_per_processed_request": latest_text_report.get("amortized_wall_ms_per_processed_request"),
    },
    "checks": checks,
}
payload["verdict"] = (
    "ok_dream7b_queue_partial_batch_flush_probe"
    if all(checks.values())
    else "warning_dream7b_queue_partial_batch_flush_probe"
)
print(json.dumps(payload, ensure_ascii=False))
PY
"""
    remote = ssh_cmd(args, remote_script, timeout=30)
    remote_payload = parse_remote_json(remote)
    verdict = remote_payload.get("verdict") or "failed_dream7b_queue_partial_batch_flush_probe"
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "remote_host": args.remote_host,
        "remote": remote_payload,
        "remote_command": remote,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_queue_partial_batch_flush_probe_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_queue_partial_batch_flush_probe.json"
    out_md = out_dir / "dream7b_queue_partial_batch_flush_probe.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    remote_service = remote_payload.get("service") or {}
    remote_queue = remote_payload.get("queue") or {}
    service_summary = remote_payload.get("service_summary") or {}
    latest_partial = service_summary.get("latest_partial_batch_run") or {}
    latest_text = remote_payload.get("latest_text_queue_run") or {}
    checks = remote_payload.get("checks") or {}
    lines = [
        "# Dream7B Queue Partial-Batch Flush Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- service_active: {remote_service.get('active')}",
        f"- service_enabled: {remote_service.get('enabled')}",
        f"- gateway_active: {remote_service.get('gateway_active')}",
        f"- openclaw_gateway_active: {remote_service.get('openclaw_gateway_active')}",
        f"- pending_count: {remote_queue.get('pending_count')}",
        f"- processing_count: {remote_queue.get('processing_count')}",
        "",
        "## Partial Flush Evidence",
        "",
        f"- run_dir: {latest_partial.get('run_dir')}",
        f"- run_reason: {latest_partial.get('run_reason')}",
        f"- pending_count_at_start: {latest_partial.get('pending_count_at_start')}",
        f"- effective_max_job_count: {latest_partial.get('effective_max_job_count')}",
        f"- processed_request_count: {latest_partial.get('processed_request_count')}",
        f"- ms_per_request: {latest_partial.get('amortized_wall_ms_per_processed_request')}",
        "",
        "## Latest Text Queue Run",
        "",
        f"- path: {latest_text.get('path')}",
        f"- verdict: {latest_text.get('verdict')}",
        f"- job_status: {latest_text.get('job_status')}",
        f"- processed_count: {latest_text.get('processed_count')}",
        f"- result_count: {latest_text.get('result_count')}",
        f"- ms_per_request: {latest_text.get('amortized_wall_ms_per_processed_request')}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in checks.items())
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if str(verdict).startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
