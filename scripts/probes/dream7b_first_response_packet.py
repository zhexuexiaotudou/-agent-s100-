#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


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


def parse_kv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def get_path(data: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def latest_perf_json(root: Path) -> Path:
    paths = sorted(root.glob("dream7b_first_response_smoke_*/dream7b_perf_identity.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        raise FileNotFoundError(f"no first-response perf JSON under {root}")
    return paths[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--perf-json", type=Path)
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    parser.add_argument("--warn-first-content-ms", type=float, default=5000.0)
    args = parser.parse_args()

    perf_path = args.perf_json or latest_perf_json(args.snapshot_root)
    perf = read_json(perf_path)
    summary = perf.get("summary") or {}
    preflight = perf.get("preflight") or {}
    interaction_gaps = summary.get("interaction_gaps") or {}
    remote = ssh_cmd(
        args,
        "\n".join(
            [
                "set -eu",
                "SERVICE=dream7b-bpu-batch-queue.service",
                'echo service_active=$(systemctl is-active "$SERVICE" 2>/dev/null || true)',
                'echo service_enabled=$(systemctl is-enabled "$SERVICE" 2>/dev/null || true)',
            ]
        ),
    )
    remote_values = parse_kv(remote["stdout"])

    failed_case_count = int(summary.get("failed_case_count") or 0)
    model_id_confirmed = bool(preflight.get("model_id_confirmed"))
    service_active_enabled = remote_values.get("service_active") == "active" and remote_values.get("service_enabled") == "enabled"
    stream_supported_count = int(summary.get("stream_supported_case_count") or 0)
    progress_event_total_count = int(summary.get("progress_event_total_count") or 0)
    ttft_p50 = get_path(summary, ["ttft_ms", "p50_ms"])
    first_progress_p50 = get_path(summary, ["first_progress_ms", "p50_ms"])
    first_content_p50 = get_path(summary, ["first_content_ms", "p50_ms"])
    first_content_p95 = get_path(summary, ["first_content_ms", "p95_ms"])
    content_warning = bool(
        first_content_p50 is not None and float(first_content_p50) > args.warn_first_content_ms
    )
    hard_ok = (
        perf.get("verdict") == "ok_dream7b_perf_identity"
        and failed_case_count == 0
        and model_id_confirmed
        and service_active_enabled
        and stream_supported_count > 0
    )
    verdict = (
        "warning_dream7b_first_response_packet_content_latency"
        if hard_ok and content_warning
        else "ok_dream7b_first_response_packet"
        if hard_ok
        else "failed_dream7b_first_response_packet"
    )

    cases = [
        {
            "id": case.get("id"),
            "ok": case.get("ok"),
            "ttft_ms": case.get("ttft_ms"),
            "first_progress_ms": case.get("first_progress_ms"),
            "first_content_ms": case.get("first_content_ms"),
            "progress_event_count": case.get("progress_event_count"),
            "stream_supported": case.get("stream_supported"),
            "content_preview": str(case.get("content") or "")[:160],
        }
        for case in perf.get("cases") or []
    ]
    decision = {
        "first_response_events_ready": hard_ok,
        "sse_progress_ready": progress_event_total_count > 0,
        "first_content_latency_needs_work": content_warning,
        "queue_batch_service_remains_default": service_active_enabled,
        "recommended_next": "keep SSE progress path; optimize first content latency separately from B4 true-batch research",
    }
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_perf_json": str(perf_path),
        "service": {
            "active": remote_values.get("service_active") == "active",
            "enabled": remote_values.get("service_enabled") == "enabled",
            "active_enabled": service_active_enabled,
        },
        "preflight": {
            "health_status": preflight.get("health_status"),
            "models_status": preflight.get("models_status"),
            "model_id_confirmed": model_id_confirmed,
            "health_latency_ms": preflight.get("health_latency_ms"),
            "models_latency_ms": preflight.get("models_latency_ms"),
        },
        "summary": {
            "case_count": summary.get("case_count"),
            "failed_case_count": failed_case_count,
            "ttft_p50_ms": ttft_p50,
            "ttft_p95_ms": get_path(summary, ["ttft_ms", "p95_ms"]),
            "first_progress_p50_ms": first_progress_p50,
            "first_progress_p95_ms": get_path(summary, ["first_progress_ms", "p95_ms"]),
            "first_content_p50_ms": first_content_p50,
            "first_content_p95_ms": first_content_p95,
            "stream_supported_case_count": stream_supported_count,
            "progress_event_total_count": progress_event_total_count,
            "warnings": perf.get("warnings") or [],
            "interaction_gaps": interaction_gaps,
        },
        "cases": cases,
        "decision": decision,
        "remote_command": remote,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.snapshot_root / f"dream7b_first_response_packet_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_first_response_packet.json"
    out_md = out_dir / "dream7b_first_response_packet.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B First Response Packet",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- source_perf_json: {payload['source_perf_json']}",
        f"- service_active_enabled: {service_active_enabled}",
        f"- model_id_confirmed: {model_id_confirmed}",
        f"- failed_case_count: {failed_case_count}",
        f"- ttft_p50_ms: {ttft_p50}",
        f"- first_progress_p50_ms: {first_progress_p50}",
        f"- first_content_p50_ms: {first_content_p50}",
        f"- first_content_p95_ms: {first_content_p95}",
        f"- stream_supported_case_count: {stream_supported_count}",
        f"- progress_event_total_count: {progress_event_total_count}",
        "",
        "## Decision",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in decision.items())
    lines.extend(["", "## Cases", "", "| id | ok | ttft_ms | first_progress_ms | first_content_ms | progress_events |", "| --- | --- | ---: | ---: | ---: | ---: |"])
    for case in cases:
        lines.append(
            f"| {case['id']} | {case['ok']} | {case['ttft_ms']} | {case['first_progress_ms']} | "
            f"{case['first_content_ms']} | {case['progress_event_count']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if verdict.startswith(("ok_", "warning_")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
