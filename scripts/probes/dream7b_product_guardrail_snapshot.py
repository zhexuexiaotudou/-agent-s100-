#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


QUEUE_BASELINE_AVG_BPU = 93.166
QUEUE_BASELINE_AVG_NONZERO_BPU = 95.097


def run_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_cmd(args: argparse.Namespace, remote_command: str, timeout: int = 30) -> dict[str, Any]:
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
            remote_command,
        ],
        timeout=timeout,
    )


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def find_local_file(name: str) -> Path | None:
    for path in Path(".").rglob(name):
        if path.is_file():
            return path
    return None


def latest_b4_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path) or {}
    latest = payload.get("runtime_summary") or {}
    telemetry = payload.get("telemetry_reports") or []
    return {
        "analysis_path": str(path),
        "telemetry_count": len(telemetry),
        "latest_telemetry_file": latest.get("latest_telemetry_file"),
        "avg_bpu_gap_vs_queue": latest.get("avg_bpu_gap_vs_queue"),
        "avg_nonzero_bpu_gap_vs_queue": latest.get("avg_nonzero_bpu_gap_vs_queue"),
        "final_logits_avg_run_ms": latest.get("final_logits_avg_run_ms"),
        "hidden_avg_run_ms": latest.get("hidden_avg_run_ms"),
        "final_vs_hidden_avg_run_ratio": latest.get("final_vs_hidden_avg_run_ratio"),
        "group_load_fraction_of_wall": latest.get("group_load_fraction_of_wall"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only Dream7B production guardrail evidence snapshot.")
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--b4-analysis-json", type=Path, default=Path("tmp/true_batch_hbm_stage/b4_segment_analysis.json"))
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = args.report_root / f"dream7b_product_guardrail_snapshot_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)

    remote_script = r"""
set -eu
SERVICE=dream7b-bpu-batch-queue.service
echo service_active=$(systemctl is-active "$SERVICE" 2>/dev/null || true)
echo service_enabled=$(systemctl is-enabled "$SERVICE" 2>/dev/null || true)
echo service_fragment=$(systemctl show "$SERVICE" -p FragmentPath --value 2>/dev/null || true)
echo service_main_pid=$(systemctl show "$SERVICE" -p MainPID --value 2>/dev/null || true)
echo service_active_since="$(systemctl show "$SERVICE" -p ActiveEnterTimestamp --value 2>/dev/null || true)"
echo service_description="$(systemctl show "$SERVICE" -p Description --value 2>/dev/null || true)"
echo service_exec_start="$(systemctl show "$SERVICE" -p ExecStart --value 2>/dev/null || true)"
ROLLBACK_SCRIPT=$(find /mnt/nas/openclaw -type f -name dream7b-default-rollback 2>/dev/null | sort | tail -1)
STATUS_SCRIPT=$(find /mnt/nas/openclaw -type f -name dream7b-default-status 2>/dev/null | sort | tail -1)
echo rollback_script_path="$ROLLBACK_SCRIPT"
echo status_script_path="$STATUS_SCRIPT"
echo rollback_script_present=$(test -n "$ROLLBACK_SCRIPT" && echo true || echo false)
echo status_script_present=$(test -n "$STATUS_SCRIPT" && echo true || echo false)
echo queue_dir_present=$(test -d /mnt/nas/openclaw/queues/dream7b-bpu && echo true || echo false)
echo latest_phase_timing_json="$(find /mnt/nas/openclaw/reports/models -maxdepth 2 -type f -name phase_timing_probe.json | sort | tail -1)"
echo latest_service_report_json="$(find /mnt/nas/openclaw/reports/models -maxdepth 2 -type f -name segment_major_queue.json | sort | tail -1)"
echo latest_true_batch_b4_json="$(find /mnt/nas/openclaw/reports/models -maxdepth 2 -type f -path '*_b4/true_batch_group_major_telemetry.json' | sort | tail -1)"
"""
    remote = ssh_cmd(args, remote_script, timeout=30)
    remote_values = parse_key_values(remote["stdout"])

    remote_json_script = r"""
B4_JSON=$(find /mnt/nas/openclaw/reports/models -maxdepth 2 -type f -path '*_b4/true_batch_group_major_telemetry.json' | sort | tail -1)
B4_JSON="$B4_JSON" python3 - <<'PY'
import glob
import json
import os
from pathlib import Path

def read_report(path):
    if not path:
        return {"path": None, "found": False}
    try:
        payload = json.load(open(path))
    except Exception as exc:
        return {"path": path, "found": False, "error": f"{type(exc).__name__}:{exc}"}
    if not isinstance(payload, dict):
        return {"path": path, "found": False, "error": f"non_dict_json:{type(payload).__name__}"}
    return {
        "path": path,
        "found": True,
        "verdict": payload.get("verdict"),
        "avg_bpu_loading": payload.get("avg_bpu_loading"),
        "avg_nonzero_bpu_loading": payload.get("avg_nonzero_bpu_loading"),
        "max_bpu_loading": payload.get("max_bpu_loading"),
        "failed_job_count": payload.get("failed_job_count"),
        "processed_request_count": payload.get("processed_request_count"),
        "amortized_wall_ms_per_request": payload.get("amortized_wall_ms_per_request"),
        "final_shape": payload.get("final_shape"),
    }

def find_latest_file(name):
    matches = sorted(glob.glob(f"/mnt/nas/openclaw/**/{name}", recursive=True))
    return matches[-1] if matches else ""

def file_contract(path):
    if not path:
        return {"path": "", "found": False}
    item = Path(path)
    if not item.exists():
        return {"path": path, "found": False}
    import hashlib
    data = item.read_bytes()
    stat = item.stat()
    return {
        "path": path,
        "found": True,
        "mode_octal": oct(stat.st_mode & 0o777),
        "size_bytes": stat.st_size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "executable": bool(stat.st_mode & 0o111),
    }

def run_command(args, timeout=20, env=None):
    import subprocess
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout, env=merged_env)
    return {
        "args": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }

def parse_json_stdout(command_result):
    try:
        return json.loads(command_result.get("stdout") or "{}")
    except Exception as exc:
        return {"parse_error": f"{type(exc).__name__}:{exc}", "stdout": command_result.get("stdout")}

status_script = find_latest_file("dream7b-default-status")
rollback_script = find_latest_file("dream7b-default-rollback")
status_run = (
    run_command([status_script, "json"], timeout=20)
    if status_script
    else {"returncode": 127, "stdout": "", "stderr": "status script not found"}
)
rollback_dry_run = (
    run_command(
        [
            "sudo",
            "-n",
            "env",
            "DREAM7B_DEFAULT_ROLLBACK_DRY_RUN=1",
            rollback_script,
        ],
        timeout=20,
    )
    if rollback_script
    else {"returncode": 127, "stdout": "", "stderr": "rollback script not found"}
)

queue_candidates = []
for pattern in [
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_phase_timing_*/phase_timing_probe.json",
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_*/*.json",
    "/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_*/*.json",
]:
    for path in glob.glob(pattern):
        report = read_report(path)
        if report.get("found") and report.get("failed_job_count") in (0, None) and report.get("avg_bpu_loading") is not None:
            queue_candidates.append(report)

latest_phase_paths = sorted(glob.glob("/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_phase_timing_*/phase_timing_probe.json"))
best_queue = max(queue_candidates, key=lambda item: float(item.get("avg_bpu_loading") or 0.0), default={"found": False, "path": None})
out = {
    "best_queue_baseline": best_queue,
    "latest_phase_timing": read_report(latest_phase_paths[-1] if latest_phase_paths else ""),
    "latest_true_batch_b4": read_report(os.environ.get("B4_JSON", "")),
    "queue_candidate_count": len(queue_candidates),
    "default_status_contract": {
        "script": file_contract(status_script),
        "run": status_run,
        "payload": parse_json_stdout(status_run),
    },
    "default_rollback_contract": {
        "script": file_contract(rollback_script),
        "dry_run": rollback_dry_run,
        "dry_run_ready": rollback_dry_run.get("returncode") == 0
        and "dry_run=1; no changes applied" in (rollback_dry_run.get("stdout") or ""),
    },
}
print(json.dumps(out, ensure_ascii=False))
PY
"""
    remote_json = ssh_cmd(args, remote_json_script, timeout=30)
    remote_report_summary = read_json(run_dir / "nonexistent.json") or {}
    try:
        remote_report_summary = json.loads(remote_json["stdout"])
    except json.JSONDecodeError:
        remote_report_summary = {"error": "failed_to_parse_remote_json_summary", "stdout": remote_json["stdout"]}

    local_rollback = find_local_file("dream7b-default-rollback")
    local_status = find_local_file("dream7b-default-status")
    b4 = latest_b4_summary(args.b4_analysis_json)
    active = remote_values.get("service_active") == "active"
    enabled = remote_values.get("service_enabled") == "enabled"
    rollback_ready = remote_values.get("rollback_script_present") == "true" and local_rollback is not None
    b4_gap = b4.get("avg_bpu_gap_vs_queue")
    true_batch_below_queue = isinstance(b4_gap, (int, float)) and b4_gap < 0
    phase = remote_report_summary.get("best_queue_baseline") or {}
    status_contract = remote_report_summary.get("default_status_contract") or {}
    rollback_contract = remote_report_summary.get("default_rollback_contract") or {}
    status_payload = status_contract.get("payload") or {}
    status_contract_ready = (
        (status_contract.get("script") or {}).get("found") is True
        and (status_contract.get("script") or {}).get("executable") is True
        and (status_contract.get("run") or {}).get("returncode") == 0
        and status_payload.get("active") == "active"
        and status_payload.get("enabled") == "enabled"
    )
    rollback_dry_run_ready = (
        (rollback_contract.get("script") or {}).get("found") is True
        and (rollback_contract.get("script") or {}).get("executable") is True
        and rollback_contract.get("dry_run_ready") is True
    )
    baseline_ok = (
        phase.get("found")
        and phase.get("avg_bpu_loading") is not None
        and float(phase.get("avg_bpu_loading")) >= 90.0
        and (phase.get("failed_job_count") in (0, None))
    )
    verdict = (
        "ok_dream7b_product_guardrail_snapshot"
        if active
        and enabled
        and rollback_ready
        and status_contract_ready
        and rollback_dry_run_ready
        and true_batch_below_queue
        and baseline_ok
        else "warning_dream7b_product_guardrail_snapshot"
    )

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "remote_host": args.remote_host,
        "service": {
            "name": "dream7b-bpu-batch-queue.service",
            "active": active,
            "enabled": enabled,
            "raw": remote_values,
        },
        "rollback": {
            "remote_script_present": remote_values.get("rollback_script_present") == "true",
            "remote_script_path": remote_values.get("rollback_script_path"),
            "remote_status_path": remote_values.get("status_script_path"),
            "local_script_path": str(local_rollback) if local_rollback else None,
            "local_status_path": str(local_status) if local_status else None,
            "ready": rollback_ready,
        },
        "default_status_contract": {
            "ready": status_contract_ready,
            "script": status_contract.get("script") or {},
            "payload": status_payload,
            "run_returncode": (status_contract.get("run") or {}).get("returncode"),
            "run_stderr": (status_contract.get("run") or {}).get("stderr"),
        },
        "default_rollback_contract": {
            "dry_run_ready": rollback_dry_run_ready,
            "script": rollback_contract.get("script") or {},
            "dry_run_returncode": (rollback_contract.get("dry_run") or {}).get("returncode"),
            "dry_run_stdout": (rollback_contract.get("dry_run") or {}).get("stdout"),
            "dry_run_stderr": (rollback_contract.get("dry_run") or {}).get("stderr"),
        },
        "queue_baseline": {
            "reference_avg_bpu_loading": QUEUE_BASELINE_AVG_BPU,
            "reference_avg_nonzero_bpu_loading": QUEUE_BASELINE_AVG_NONZERO_BPU,
            "best_remote_queue_baseline": phase,
            "latest_remote_phase_timing": remote_report_summary.get("latest_phase_timing") or {},
            "latest_remote_baseline_ok": bool(baseline_ok),
        },
        "true_batch_b4": b4,
        "remote_report_summary": remote_report_summary,
        "commands": {
            "remote_status": remote,
            "remote_report_summary": remote_json,
        },
        "guardrail": {
            "default_service_unchanged": active and enabled,
            "true_batch_not_promoted": true_batch_below_queue,
            "default_status_contract_ready": status_contract_ready,
            "default_rollback_dry_run_ready": rollback_dry_run_ready,
            "queue_batch_should_remain_default": active and enabled and true_batch_below_queue,
        },
    }
    json_path = run_dir / "dream7b_product_guardrail_snapshot.json"
    md_path = run_dir / "dream7b_product_guardrail_snapshot.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Dream7B Product Guardrail Snapshot",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- service_active: `{active}`",
        f"- service_enabled: `{enabled}`",
        f"- rollback_ready: `{rollback_ready}`",
        f"- status_contract_ready: `{status_contract_ready}`",
        f"- rollback_dry_run_ready: `{rollback_dry_run_ready}`",
        f"- latest_queue_baseline_avg_bpu: `{phase.get('avg_bpu_loading')}`",
        f"- latest_queue_baseline_failed_jobs: `{phase.get('failed_job_count')}`",
        f"- b4_latest_avg_bpu_gap_vs_queue_points: `{b4.get('avg_bpu_gap_vs_queue')}`",
        f"- b4_latest_avg_nonzero_gap_vs_queue_points: `{b4.get('avg_nonzero_bpu_gap_vs_queue')}`",
        "",
        "## Service",
        "",
        f"- description: `{remote_values.get('service_description')}`",
        f"- active_since: `{remote_values.get('service_active_since')}`",
        f"- fragment: `{remote_values.get('service_fragment')}`",
        f"- exec_start: `{remote_values.get('service_exec_start')}`",
        "",
        "## Guardrail Decision",
        "",
        f"- default_service_unchanged: `{payload['guardrail']['default_service_unchanged']}`",
        f"- true_batch_not_promoted: `{payload['guardrail']['true_batch_not_promoted']}`",
        f"- default_status_contract_ready: `{payload['guardrail']['default_status_contract_ready']}`",
        f"- default_rollback_dry_run_ready: `{payload['guardrail']['default_rollback_dry_run_ready']}`",
        f"- queue_batch_should_remain_default: `{payload['guardrail']['queue_batch_should_remain_default']}`",
        "",
        "## Recovery Contract",
        "",
        f"- status_script_sha256: `{payload['default_status_contract']['script'].get('sha256')}`",
        f"- status_script_mode: `{payload['default_status_contract']['script'].get('mode_octal')}`",
        f"- status_payload_active_enabled: `{status_payload.get('active')}` / `{status_payload.get('enabled')}`",
        f"- status_payload_segment_major_default: `{status_payload.get('segment_major_default')}`",
        f"- rollback_script_sha256: `{payload['default_rollback_contract']['script'].get('sha256')}`",
        f"- rollback_script_mode: `{payload['default_rollback_contract']['script'].get('mode_octal')}`",
        f"- rollback_dry_run_returncode: `{payload['default_rollback_contract']['dry_run_returncode']}`",
        f"- rollback_dry_run_stdout: `{payload['default_rollback_contract']['dry_run_stdout']}`",
        "",
        "## Evidence Paths",
        "",
        f"- queue_baseline_report: `{phase.get('path')}`",
        f"- b4_analysis: `{b4.get('analysis_path')}`",
        f"- rollback_script: `{payload['rollback']['local_script_path']}`",
        f"- json: `{json_path}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(md_path)
    print(json_path)
    return 0 if verdict.startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
