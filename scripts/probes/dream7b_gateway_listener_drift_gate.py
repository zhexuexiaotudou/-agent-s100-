#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TOOL_ID = "dream7b_gateway_listener_drift_gate"


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def report_sort_key(path: Path) -> tuple[float, float, str]:
    payload = read_json(path)
    generated_at = parse_time(payload.get("generated_at"))
    generated_ts = generated_at.timestamp() if generated_at else 0.0
    try:
        mtime_ts = path.stat().st_mtime
    except OSError:
        mtime_ts = 0.0
    return generated_ts, mtime_ts, str(path)


def latest_json(root: Path, pattern: str) -> Path | None:
    candidates = [path for path in root.glob(pattern) if path.is_file()]
    return max(candidates, key=report_sort_key) if candidates else None


def live_gateway_state(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
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
listener_pid="$(sudo -n lsof -t -iTCP:$PORT -sTCP:LISTEN -P -n 2>/dev/null | head -1 || true)"
echo listener_pid="$listener_pid"
if test -n "$listener_pid"; then
  echo listener_ppid="$(sudo -n ps -p "$listener_pid" -o ppid= 2>/dev/null | tr -d ' ' || true)"
  echo listener_etime="$(sudo -n ps -p "$listener_pid" -o etime= 2>/dev/null | tr -d ' ' || true)"
  echo listener_cmd="$(sudo -n ps -p "$listener_pid" -o cmd= 2>/dev/null || true)"
fi
health_json="$(curl -sS --max-time 3 http://127.0.0.1:$PORT/health 2>/dev/null || true)"
echo health_json="$health_json"
"""
    remote = ssh_cmd(args, remote_script, timeout=args.timeout)
    values = parse_key_values(remote["stdout"])
    main_pid = as_int(values.get("gateway_main_pid"))
    listener_pid = as_int(values.get("listener_pid"))
    health = parse_json(values.get("health_json"))
    listener_present = listener_pid is not None and listener_pid > 0
    listener_matches_main_pid = (
        main_pid is not None and main_pid > 0 and listener_present and listener_pid == main_pid
    )
    summary = {
        "gateway_active": values.get("gateway_active") == "active",
        "gateway_enabled": values.get("gateway_enabled") == "enabled",
        "gateway_main_pid": main_pid,
        "listener_pid": listener_pid,
        "listener_matches_systemd_main_pid": listener_matches_main_pid,
        "orphan_listener_detected": listener_present and not listener_matches_main_pid,
        "health_ok": health.get("ok") is True and health.get("model") == "Dream7B-S100P-local",
    }
    detail = {
        "service": {
            "active_raw": values.get("gateway_active"),
            "enabled_raw": values.get("gateway_enabled"),
            "main_pid": main_pid,
            "exec_main_status": values.get("gateway_exec_main_status"),
            "result": values.get("gateway_result"),
            "n_restarts": values.get("gateway_n_restarts"),
        },
        "listener": {
            "pid": listener_pid,
            "ppid": as_int(values.get("listener_ppid")),
            "elapsed": values.get("listener_etime"),
            "cmd": values.get("listener_cmd"),
        },
        "health": health,
        "remote_command": remote,
    }
    return summary, detail


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gate Dream7B gateway listener ownership against live S100P state to catch orphan-listener drift."
    )
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    parser.add_argument("--snapshot-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--port", type=int, default=18888)
    parser.add_argument("--service-name", default="dream7b-local-openai-gateway.service")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_gateway_listener_drift_gate_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    snapshot_path = latest_json(
        args.snapshot_root, "dream7b_gateway_listener_ownership_*/dream7b_gateway_listener_ownership.json"
    )
    snapshot = read_json(snapshot_path) if snapshot_path else {}
    snapshot_summary = snapshot.get("summary") or {}
    snapshot_generated_at = parse_time(snapshot.get("generated_at"))
    now = datetime.now(timezone.utc)
    snapshot_age_seconds = (
        round((now - snapshot_generated_at).total_seconds(), 3) if snapshot_generated_at else None
    )
    live_summary, live_detail = live_gateway_state(args)

    failures: list[str] = []
    warnings: list[str] = []
    if not snapshot_path:
        failures.append("ownership_snapshot_missing")
    elif snapshot.get("verdict") != "ok_dream7b_gateway_listener_ownership":
        failures.append(f"ownership_snapshot_not_ok:{snapshot.get('verdict')}")
    if live_summary["gateway_active"] is not True:
        failures.append("live_gateway_not_active")
    if live_summary["gateway_enabled"] is not True:
        failures.append("live_gateway_not_enabled")
    if live_summary["listener_matches_systemd_main_pid"] is not True:
        failures.append("live_listener_not_owned_by_systemd_main_pid")
    if live_summary["orphan_listener_detected"] is not False:
        failures.append("live_orphan_listener_detected")
    if live_summary["health_ok"] is not True:
        failures.append("live_gateway_health_not_ok")

    if snapshot_path and snapshot_summary.get("gateway_main_pid") != live_summary["gateway_main_pid"]:
        warnings.append(
            f"gateway_main_pid_changed:snapshot={snapshot_summary.get('gateway_main_pid')}:live={live_summary['gateway_main_pid']}"
        )
    if snapshot_path and snapshot_summary.get("listener_pid") != live_summary["listener_pid"]:
        warnings.append(
            f"listener_pid_changed:snapshot={snapshot_summary.get('listener_pid')}:live={live_summary['listener_pid']}"
        )

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": "ok_dream7b_gateway_listener_drift_gate"
        if not failures
        else "failed_dream7b_gateway_listener_drift_gate",
        "remote_host": args.remote_host,
        "service_name": args.service_name,
        "port": args.port,
        "snapshot": {
            "path": str(snapshot_path) if snapshot_path else None,
            "verdict": snapshot.get("verdict"),
            "generated_at": snapshot.get("generated_at"),
            "age_seconds": snapshot_age_seconds,
            "summary": snapshot_summary,
        },
        "live": {
            "summary": live_summary,
            **live_detail,
        },
        "summary": {
            "snapshot_found": snapshot_path is not None,
            "snapshot_ok": snapshot.get("verdict") == "ok_dream7b_gateway_listener_ownership",
            "live_gateway_active": live_summary["gateway_active"],
            "live_gateway_enabled": live_summary["gateway_enabled"],
            "live_listener_matches_systemd_main_pid": live_summary[
                "listener_matches_systemd_main_pid"
            ],
            "live_orphan_listener_detected": live_summary["orphan_listener_detected"],
            "live_health_ok": live_summary["health_ok"],
            "snapshot_age_seconds": snapshot_age_seconds,
            "failure_count": len(failures),
            "warning_count": len(warnings),
        },
        "failures": failures,
        "warnings": warnings,
        "audit": {
            "read_only": True,
            "service_restarted": False,
            "process_killed": False,
            "writes": "local JSON/Markdown drift gate report only",
        },
    }

    out_json = out_dir / "dream7b_gateway_listener_drift_gate.json"
    out_md = out_dir / "dream7b_gateway_listener_drift_gate.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B Gateway Listener Drift Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- snapshot_path: `{payload['snapshot']['path']}`",
        f"- snapshot_ok: `{payload['summary']['snapshot_ok']}`",
        f"- live_gateway_active: `{payload['summary']['live_gateway_active']}`",
        f"- live_gateway_enabled: `{payload['summary']['live_gateway_enabled']}`",
        f"- live_listener_matches_systemd_main_pid: `{payload['summary']['live_listener_matches_systemd_main_pid']}`",
        f"- live_orphan_listener_detected: `{payload['summary']['live_orphan_listener_detected']}`",
        f"- live_health_ok: `{payload['summary']['live_health_ok']}`",
        f"- failures: `{failures}`",
        f"- warnings: `{warnings}`",
        "",
        "## Live Listener",
        "",
        f"- gateway_main_pid: `{live_summary['gateway_main_pid']}`",
        f"- listener_pid: `{live_summary['listener_pid']}`",
        f"- listener_cmd: `{live_detail['listener']['cmd']}`",
        f"- listener_elapsed: `{live_detail['listener']['elapsed']}`",
        "",
        "## Audit",
        "",
        "- read_only: `True`",
        "- service_restarted: `False`",
        "- process_killed: `False`",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_md)
    print(out_json)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
