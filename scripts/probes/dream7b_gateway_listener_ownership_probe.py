#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_gateway_listener_ownership"


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


def parse_key_values(text: str) -> dict[str, str]:
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


def parse_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json", "raw": value}
    return payload if isinstance(payload, dict) else {"raw": payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the Dream7B OpenAI gateway port listener is owned by the enabled systemd user service."
    )
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--port", type=int, default=18888)
    parser.add_argument("--service-name", default="dream7b-local-openai-gateway.service")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_gateway_listener_ownership_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    remote_script = f"""
set -u
SERVICE={args.service_name}
PORT={args.port}
USER_SYSTEMCTL="sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user"
echo gateway_active="$($USER_SYSTEMCTL is-active "$SERVICE" 2>/dev/null || true)"
echo gateway_enabled="$($USER_SYSTEMCTL is-enabled "$SERVICE" 2>/dev/null || true)"
echo gateway_main_pid="$($USER_SYSTEMCTL show "$SERVICE" -p MainPID --value 2>/dev/null || true)"
echo gateway_exec_main_status="$($USER_SYSTEMCTL show "$SERVICE" -p ExecMainStatus --value 2>/dev/null || true)"
echo gateway_result="$($USER_SYSTEMCTL show "$SERVICE" -p Result --value 2>/dev/null || true)"
echo gateway_n_restarts="$($USER_SYSTEMCTL show "$SERVICE" -p NRestarts --value 2>/dev/null || true)"
echo gateway_fragment="$($USER_SYSTEMCTL show "$SERVICE" -p FragmentPath --value 2>/dev/null || true)"
listener_pid="$(sudo -n lsof -t -iTCP:$PORT -sTCP:LISTEN -P -n 2>/dev/null | head -1 || true)"
echo listener_pid="$listener_pid"
if test -n "$listener_pid"; then
  listener_cmd="$(sudo -n ps -p "$listener_pid" -o cmd= 2>/dev/null || true)"
  listener_ppid="$(sudo -n ps -p "$listener_pid" -o ppid= 2>/dev/null | tr -d ' ' || true)"
  listener_etime="$(sudo -n ps -p "$listener_pid" -o etime= 2>/dev/null | tr -d ' ' || true)"
  echo listener_ppid="$listener_ppid"
  echo listener_etime="$listener_etime"
  echo listener_cmd="$listener_cmd"
fi
health_json="$(curl -sS --max-time 3 http://127.0.0.1:$PORT/health 2>/dev/null || true)"
echo health_json="$health_json"
"""
    remote = ssh_cmd(args, remote_script, timeout=30)
    values = parse_key_values(remote["stdout"])

    gateway_main_pid = as_int(values.get("gateway_main_pid"))
    listener_pid = as_int(values.get("listener_pid"))
    health = parse_json(values.get("health_json"))
    active = values.get("gateway_active") == "active"
    enabled = values.get("gateway_enabled") == "enabled"
    listener_present = listener_pid is not None and listener_pid > 0
    listener_matches_main_pid = (
        gateway_main_pid is not None
        and gateway_main_pid > 0
        and listener_pid is not None
        and listener_pid == gateway_main_pid
    )
    health_ok = health.get("ok") is True and health.get("model") == "Dream7B-S100P-local"
    orphan_listener_detected = listener_present and not listener_matches_main_pid
    failures: list[str] = []
    if not active:
        failures.append(f"gateway_not_active:{values.get('gateway_active')}")
    if not enabled:
        failures.append(f"gateway_not_enabled:{values.get('gateway_enabled')}")
    if not listener_present:
        failures.append("listener_missing")
    if listener_present and not listener_matches_main_pid:
        failures.append(
            f"listener_pid_not_systemd_main_pid:listener={listener_pid}:main={gateway_main_pid}"
        )
    if not health_ok:
        failures.append("health_not_ok")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": "ok_dream7b_gateway_listener_ownership" if not failures else "failed_dream7b_gateway_listener_ownership",
        "remote_host": args.remote_host,
        "service_name": args.service_name,
        "port": args.port,
        "summary": {
            "gateway_active": active,
            "gateway_enabled": enabled,
            "gateway_main_pid": gateway_main_pid,
            "listener_pid": listener_pid,
            "listener_matches_systemd_main_pid": listener_matches_main_pid,
            "orphan_listener_detected": orphan_listener_detected,
            "health_ok": health_ok,
            "failure_count": len(failures),
        },
        "service": {
            "active_raw": values.get("gateway_active"),
            "enabled_raw": values.get("gateway_enabled"),
            "main_pid": gateway_main_pid,
            "exec_main_status": values.get("gateway_exec_main_status"),
            "result": values.get("gateway_result"),
            "n_restarts": values.get("gateway_n_restarts"),
            "fragment": values.get("gateway_fragment"),
        },
        "listener": {
            "pid": listener_pid,
            "ppid": as_int(values.get("listener_ppid")),
            "elapsed": values.get("listener_etime"),
            "cmd": values.get("listener_cmd"),
        },
        "health": health,
        "failures": failures,
        "remote_command": remote,
        "audit": {
            "read_only": True,
            "service_restarted": False,
            "process_killed": False,
            "writes": "local JSON/Markdown ownership report only",
        },
    }

    out_json = out_dir / "dream7b_gateway_listener_ownership.json"
    out_md = out_dir / "dream7b_gateway_listener_ownership.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Dream7B Gateway Listener Ownership",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- gateway_active: `{active}`",
        f"- gateway_enabled: `{enabled}`",
        f"- gateway_main_pid: `{gateway_main_pid}`",
        f"- listener_pid: `{listener_pid}`",
        f"- listener_matches_systemd_main_pid: `{listener_matches_main_pid}`",
        f"- orphan_listener_detected: `{orphan_listener_detected}`",
        f"- health_ok: `{health_ok}`",
        f"- failures: `{failures}`",
        "",
        "## Listener",
        "",
        f"- command: `{payload['listener']['cmd']}`",
        f"- elapsed: `{payload['listener']['elapsed']}`",
        "",
        "## Health",
        "",
        f"- model: `{health.get('model')}`",
        f"- backend: `{health.get('backend')}`",
        f"- quick_response_enabled: `{health.get('quick_response_enabled')}`",
        f"- inline_tokenizer_loaded: `{health.get('inline_tokenizer_loaded')}`",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_md)
    print(out_json)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
