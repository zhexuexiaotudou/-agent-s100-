#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_true_batch_runtime_instrumentation_deployment_contract"
DEFAULT_OUT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_SSH_KEY = Path("C:/Users/zhexu/.ssh/s100p_linkcheck_ed25519")
REMOTE_PROBE = "/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py"


def parse_kv(stdout: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def run_remote(args: argparse.Namespace) -> dict[str, Any]:
    remote_script = " ".join(
        [
            f"PROBE={REMOTE_PROBE};",
            "echo probe_exists=$(test -f \"$PROBE\" && echo true || echo false);",
            "echo probe_path=$PROBE;",
            "echo input_prepare_count=$(grep -c input_prepare_ms \"$PROBE\" 2>/dev/null || true);",
            "echo output_postprocess_count=$(grep -c output_postprocess_ms \"$PROBE\" 2>/dev/null || true);",
            "echo total_input_prepare_count=$(grep -c total_input_prepare_ms \"$PROBE\" 2>/dev/null || true);",
            "echo total_output_postprocess_count=$(grep -c total_output_postprocess_ms \"$PROBE\" 2>/dev/null || true);",
            "echo avg_input_prepare_count=$(grep -c avg_input_prepare_ms \"$PROBE\" 2>/dev/null || true);",
            "echo avg_output_postprocess_count=$(grep -c avg_output_postprocess_ms \"$PROBE\" 2>/dev/null || true);",
            "echo probe_sha256=$(sha256sum \"$PROBE\" 2>/dev/null | cut -d \" \" -f 1);",
            "echo latest_backup=$(ls -1t ${PROBE}.bak_*_pre_input_postprocess_instrumentation 2>/dev/null | head -1);",
            "echo active_true_batch_python=$(ps -eo cmd= | grep python | grep dream7b_true_batch | grep -v grep | wc -l);",
            "echo active_compile_true_batch=$(ps -eo cmd= | grep compile_dream_true_batch | grep -v grep | wc -l);",
        ]
    )
    completed = subprocess.run(
        [
            "ssh.exe",
            "-i",
            str(args.ssh_key),
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={args.connect_timeout_sec}",
            args.remote_host,
            remote_script,
        ],
        text=True,
        capture_output=True,
        timeout=args.timeout_sec,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "values": parse_kv(completed.stdout),
    }


def as_int(values: dict[str, str], key: str) -> int:
    try:
        return int(values.get(key) or 0)
    except ValueError:
        return 0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    remote = run_remote(args)
    values = remote["values"]
    checks = {
        "remote_probe_exists": values.get("probe_exists") == "true",
        "input_prepare_instrumentation_present": as_int(values, "input_prepare_count") > 0
        and as_int(values, "total_input_prepare_count") > 0
        and as_int(values, "avg_input_prepare_count") > 0,
        "output_postprocess_instrumentation_present": as_int(values, "output_postprocess_count") > 0
        and as_int(values, "total_output_postprocess_count") > 0
        and as_int(values, "avg_output_postprocess_count") > 0,
        "backup_present": bool(values.get("latest_backup")),
        "no_true_batch_runtime_started": as_int(values, "active_true_batch_python") == 0,
        "no_compile_started": as_int(values, "active_compile_true_batch") == 0,
        "ssh_ok": remote["returncode"] == 0,
    }
    failures = [key for key, value in checks.items() if not value]
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": (
            "ok_dream7b_true_batch_runtime_instrumentation_deployment_contract"
            if not failures
            else "failed_dream7b_true_batch_runtime_instrumentation_deployment_contract"
        ),
        "remote_host": args.remote_host,
        "remote_probe": REMOTE_PROBE,
        "checks": checks,
        "failures": failures,
        "remote_values": values,
        "remote_stdout": remote["stdout"],
        "remote_stderr": remote["stderr"],
        "behavior": {
            "runtime_experiment_started": False,
            "compile_started": False,
            "remote_file_overwritten_with_backup": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate remote deployment of Dream7B true-batch instrumentation.")
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--ssh-key", type=Path, default=DEFAULT_SSH_KEY)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--connect-timeout-sec", type=int, default=15)
    parser.add_argument("--timeout-sec", type=int, default=30)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_root.mkdir(parents=True, exist_ok=True)
    json_path = args.out_root / "dream7b_true_batch_runtime_instrumentation_deployment_contract_20260621.json"
    md_path = args.out_root / "dream7b_true_batch_runtime_instrumentation_deployment_contract_20260621.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B True-Batch Runtime Instrumentation Deployment Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- remote_host: `{payload['remote_host']}`",
        f"- remote_probe: `{payload['remote_probe']}`",
        f"- probe_sha256: `{payload['remote_values'].get('probe_sha256')}`",
        f"- latest_backup: `{payload['remote_values'].get('latest_backup')}`",
        f"- active_true_batch_python: `{payload['remote_values'].get('active_true_batch_python')}`",
        f"- active_compile_true_batch: `{payload['remote_values'].get('active_compile_true_batch')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["checks"].items())
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {item}" for item in payload["failures"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_path, flush=True)
    print(md_path, flush=True)
    return 0 if not payload["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
