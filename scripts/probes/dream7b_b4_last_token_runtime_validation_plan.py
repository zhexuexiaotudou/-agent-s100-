#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_GATE = DEFAULT_ROOT / "dream7b_b4_last_token_experiment_gate_20260620.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_last_token_runtime_validation_plan_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_last_token_runtime_validation_plan_20260620.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
            str(args.ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            remote_command,
        ],
        timeout=timeout,
    )


def parse_kv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def as_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(str(value).strip())
    except Exception:
        return None


def remote_state(args: argparse.Namespace, gate: dict[str, Any]) -> dict[str, Any]:
    manifest = gate.get("remote_manifest") or {}
    hbm_path = manifest.get("hbm_path") or (
        f"{args.final_hbm_root}/seg27_28/"
        f"dream7b_segment_27_28_seq{args.seq_len}_b{args.batch_size}_q{args.w_bits}_last_token_logits.hbm"
    )
    segment_dir = manifest.get("segment_dir") or f"{args.final_hbm_root}/seg27_28"
    remote_script = "\n".join(
        [
            "set -u",
            f"SEG_DIR='{segment_dir}'",
            f"HBM='{hbm_path}'",
            "echo queue_pending_count=$(sudo -n find /mnt/nas/openclaw/queues/dream7b-bpu/pending -type f 2>/dev/null | wc -l)",
            "echo queue_processing_count=$(sudo -n find /mnt/nas/openclaw/queues/dream7b-bpu/processing -type f 2>/dev/null | wc -l)",
            "echo queue_active=$(systemctl is-active dream7b-bpu-batch-queue.service 2>/dev/null || true)",
            "echo queue_enabled=$(systemctl is-enabled dream7b-bpu-batch-queue.service 2>/dev/null || true)",
            "echo gateway_active=$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service 2>/dev/null || true)",
            "echo openclaw_gateway_active=$(sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service 2>/dev/null || true)",
            "echo lock_busy=$(flock -n /run/lock/dream7b_bpu_batch_queue_runner.lock -c 'echo false' 2>/dev/null || echo true)",
            "echo final_hbm_root_exists=$(test -d \"$SEG_DIR\" && echo true || echo false)",
            "echo last_token_hbm_exists=$(test -f \"$HBM\" && echo true || echo false)",
            "echo manifest_exists=$(test -f \"$SEG_DIR/manifest.sha256\" && echo true || echo false)",
            "if cd \"$SEG_DIR\" 2>/dev/null && test -f manifest.sha256 && sha256sum -c manifest.sha256 >/dev/null 2>&1; then echo manifest_verified=true; else echo manifest_verified=false; fi",
            "echo hbm_path=\"$HBM\"",
            f"echo runtime_probe_exists=$(test -f {args.remote_probe} && echo true || echo false)",
            f"echo runtime_python_exists=$(test -x {args.remote_python} && echo true || echo false)",
        ]
    )
    result = ssh_cmd(args, remote_script, timeout=args.remote_timeout_sec)
    values = parse_kv(result["stdout"])
    return {
        "command": remote_script,
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "queue_pending_count": as_int(values.get("queue_pending_count")),
        "queue_processing_count": as_int(values.get("queue_processing_count")),
        "queue_active": values.get("queue_active"),
        "queue_enabled": values.get("queue_enabled"),
        "gateway_active": values.get("gateway_active"),
        "openclaw_gateway_active": values.get("openclaw_gateway_active"),
        "lock_busy": values.get("lock_busy") == "true",
        "final_hbm_root_exists": values.get("final_hbm_root_exists") == "true",
        "last_token_hbm_exists": values.get("last_token_hbm_exists") == "true",
        "manifest_exists": values.get("manifest_exists") == "true",
        "manifest_verified": values.get("manifest_verified") == "true",
        "hbm_path": values.get("hbm_path") or hbm_path,
        "runtime_probe_exists": values.get("runtime_probe_exists") == "true",
        "runtime_python_exists": values.get("runtime_python_exists") == "true",
    }


def build_runtime_command(args: argparse.Namespace) -> list[str]:
    return [
        "flock",
        "/run/lock/dream7b_bpu_batch_queue_runner.lock",
        args.remote_python,
        args.remote_probe,
        "--hbm-root",
        args.hbm_root,
        "--final-hbm-root",
        args.final_hbm_root,
        "--groups",
        args.groups,
        "--microbatch-count",
        str(args.microbatch_count),
        "--batch-size",
        str(args.batch_size),
        "--seq-len",
        str(args.seq_len),
        "--inner-order",
        "segment-major",
        "--final-logits-mode",
        "last-token",
    ]


def shell_quote(parts: list[str]) -> str:
    quoted = []
    for part in parts:
        if all(ch.isalnum() or ch in "/._:-" for ch in part):
            quoted.append(part)
        else:
            quoted.append("'" + part.replace("'", "'\"'\"'") + "'")
    return " ".join(quoted)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    gate = read_json(args.gate_json)
    state = remote_state(args, gate)
    command_parts = build_runtime_command(args)
    code_support_ready = (gate.get("summary") or {}).get("code_support_ready") is True
    manifest_ready = state["last_token_hbm_exists"] is True and state["manifest_verified"] is True
    queue_idle = state["queue_pending_count"] == 0 and state["queue_processing_count"] == 0
    services_ready = (
        state["queue_active"] == "active"
        and state["queue_enabled"] == "enabled"
        and state["gateway_active"] == "active"
        and state["openclaw_gateway_active"] == "active"
    )
    runtime_tools_ready = state["runtime_probe_exists"] is True and state["runtime_python_exists"] is True
    validation_ready = code_support_ready and manifest_ready and queue_idle and services_ready and runtime_tools_ready
    blockers: list[str] = []
    if not code_support_ready:
        blockers.append("last_token_code_support_not_ready")
    if not manifest_ready:
        blockers.append("last_token_manifest_not_ready")
    if not queue_idle:
        blockers.append("queue_not_idle")
    if not services_ready:
        blockers.append("service_state_not_ready")
    if state["lock_busy"]:
        blockers.append("bpu_lock_busy")
    if not runtime_tools_ready:
        blockers.append("runtime_probe_or_python_missing")

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ready_dream7b_b4_last_token_runtime_validation_plan"
        if validation_ready and not state["lock_busy"]
        else "blocked_dream7b_b4_last_token_runtime_validation_plan",
        "candidate": "seg27_28_last_token_logits",
        "source_paths": {
            "gate": str(args.gate_json),
        },
        "expected": {
            "final_shape": [args.batch_size, 1, args.vocab_size],
            "microbatch_count": args.microbatch_count,
            "processed_request_count": args.microbatch_count * args.batch_size,
            "groups": args.groups.split(","),
            "inner_order": "segment-major",
            "final_logits_mode": "last-token",
        },
        "remote_state": state,
        "readiness": {
            "code_support_ready": code_support_ready,
            "manifest_ready": manifest_ready,
            "queue_idle": queue_idle,
            "services_ready": services_ready,
            "runtime_tools_ready": runtime_tools_ready,
            "lock_busy": state["lock_busy"],
            "validation_ready": validation_ready and not state["lock_busy"],
            "blockers": blockers,
        },
        "runtime_command": {
            "argv": command_parts,
            "shell": shell_quote(command_parts),
            "execute_only_after": [
                "last_token_manifest_ready",
                "queue_idle",
                "services_ready",
                "bpu_lock_not_busy",
            ],
        },
        "promotion_gate": {
            "required_verdict": "ok_dream7b_true_batch_group_major_telemetry",
            "required_final_shape": [args.batch_size, 1, args.vocab_size],
            "required_failed_job_count": 0,
            "compare_against": "mb512_segment_major_5_group_full_final_baseline",
            "do_not_promote_to_default": True,
        },
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "service_restarted": False,
            "remote_write_performed": False,
            "local_writes": "JSON/Markdown validation plan only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    ready = payload["readiness"]
    state = payload["remote_state"]
    lines = [
        "# Dream7B B4 Last-Token Runtime Validation Plan",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate: `{payload['candidate']}`",
        f"- validation_ready: `{ready['validation_ready']}`",
        f"- blockers: `{ready['blockers']}`",
        f"- expected_final_shape: `{payload['expected']['final_shape']}`",
        f"- microbatch_count: `{payload['expected']['microbatch_count']}`",
        f"- processed_request_count: `{payload['expected']['processed_request_count']}`",
        "",
        "## Readiness",
        "",
        f"- code_support_ready: `{ready['code_support_ready']}`",
        f"- manifest_ready: `{ready['manifest_ready']}`",
        f"- queue_idle: `{ready['queue_idle']}`",
        f"- services_ready: `{ready['services_ready']}`",
        f"- runtime_tools_ready: `{ready['runtime_tools_ready']}`",
        f"- lock_busy: `{ready['lock_busy']}`",
        f"- queue_pending_count: `{state['queue_pending_count']}`",
        f"- queue_processing_count: `{state['queue_processing_count']}`",
        f"- last_token_hbm_exists: `{state['last_token_hbm_exists']}`",
        f"- manifest_verified: `{state['manifest_verified']}`",
        f"- hbm_path: `{state['hbm_path']}`",
        "",
        "## Runtime Command",
        "",
        "```bash",
        payload["runtime_command"]["shell"],
        "```",
        "",
        "## Promotion Gate",
        "",
    ]
    for key, value in payload["promotion_gate"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a report-only S100P validation plan for the B4 last-token final-logits candidate."
    )
    parser.add_argument("--gate-json", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--known-hosts", type=Path, default=Path(r"C:\Users\zhexu\.ssh\known_hosts"))
    parser.add_argument("--remote-timeout-sec", type=int, default=30)
    parser.add_argument("--remote-python", default="/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python")
    parser.add_argument(
        "--remote-probe",
        default="/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py",
    )
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4")
    parser.add_argument(
        "--final-hbm-root",
        default="/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final",
    )
    parser.add_argument("--groups", default="0:6,6:12,12:18,18:24,24:28")
    parser.add_argument("--microbatch-count", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_md)
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
