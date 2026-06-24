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


def case_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case.get("id")): case for case in payload.get("cases") or []}


def meta(case: dict[str, Any]) -> dict[str, Any]:
    return (case.get("dream7b_candidate") or (case.get("response") or {}).get("dream7b_candidate") or {})


def parse_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def delta(before: Any, after: Any) -> float | None:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return round(float(after) - float(before), 3)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-json", type=Path, required=True)
    parser.add_argument("--after-json", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    args = parser.parse_args()

    before = read_json(args.before_json)
    after = read_json(args.after_json)
    before_cases = case_by_id(before)
    after_cases = case_by_id(after)
    rows = []
    for case_id in sorted(set(before_cases) & set(after_cases)):
        bcase = before_cases[case_id]
        acase = after_cases[case_id]
        bmeta = meta(bcase)
        ameta = meta(acase)
        rows.append(
            {
                "id": case_id,
                "before_first_content_ms": bcase.get("first_content_ms"),
                "after_first_content_ms": acase.get("first_content_ms"),
                "delta_after_minus_before_ms": delta(bcase.get("first_content_ms"), acase.get("first_content_ms")),
                "before_execution_path": bmeta.get("execution_path"),
                "after_execution_path": ameta.get("execution_path"),
                "before_backend_invoked": bmeta.get("backend_invoked"),
                "after_backend_invoked": ameta.get("backend_invoked"),
                "after_content_preview": str(acase.get("content") or "")[:160],
            }
        )

    remote = ssh_cmd(
        args,
        "systemctl is-active dream7b-bpu-batch-queue.service; "
        "systemctl is-enabled dream7b-bpu-batch-queue.service; "
        "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service; "
        "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-enabled dream7b-local-openai-gateway.service",
        timeout=30,
    )
    status_lines = parse_lines(remote["stdout"])
    chinese = next((row for row in rows if row["id"] == "chinese_short"), {})
    identity = next((row for row in rows if row["id"] == "identity_short"), {})
    verdict = (
        "ok_dream7b_first_response_fast_status_packet"
        if chinese.get("after_execution_path") == "gateway_fast_local_status"
        and isinstance(chinese.get("after_first_content_ms"), (int, float))
        and float(chinese["after_first_content_ms"]) < 100.0
        and identity.get("after_execution_path") == "gateway_fast_identity"
        and status_lines[:4] == ["active", "enabled", "active", "enabled"]
        else "warning_dream7b_first_response_fast_status_packet"
    )
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "before_json": str(args.before_json),
        "after_json": str(args.after_json),
        "remote_status_lines": status_lines,
        "backup_path": "/root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py.bak_20260619_fast_status",
        "patched_path": "/root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py",
        "rows": rows,
        "decision": {
            "localized_status_fast_path_ready": chinese.get("after_execution_path") == "gateway_fast_local_status",
            "localized_status_first_content_ms": chinese.get("after_first_content_ms"),
            "localized_status_delta_ms": chinese.get("delta_after_minus_before_ms"),
            "identity_fast_path_still_ready": identity.get("after_execution_path") == "gateway_fast_identity",
            "queue_batch_service_remains_default": status_lines[:2] == ["active", "enabled"],
            "gateway_service_active_enabled": status_lines[2:4] == ["active", "enabled"],
        },
        "remote_command": remote,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_first_response_fast_status_packet_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_first_response_fast_status_packet.json"
    out_md = out_dir / "dream7b_first_response_fast_status_packet.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Dream7B First Response Fast Status Packet",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- backup_path: {payload['backup_path']}",
        f"- patched_path: {payload['patched_path']}",
        "",
        "## Decision",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in payload["decision"].items())
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| id | before_ms | after_ms | delta_ms | before_path | after_path | after_backend |",
            "| --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['before_first_content_ms']} | {row['after_first_content_ms']} | "
            f"{row['delta_after_minus_before_ms']} | {row['before_execution_path']} | "
            f"{row['after_execution_path']} | {row['after_backend_invoked']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if verdict.startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
