#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_model_service_recovery_drill"


class HealthHandler(BaseHTTPRequestHandler):
    server_version = "AiNasMockModelHealth/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        payload = {
            "ok": True,
            "model": "mock-local-model-service",
            "pid": self.server.server_pid,  # type: ignore[attr-defined]
            "started_at": self.server.started_at,  # type: ignore[attr-defined]
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def run_health_child(port: int) -> int:
    server = ThreadingHTTPServer(("127.0.0.1", port), HealthHandler)
    server.server_pid = os.getpid()  # type: ignore[attr-defined]
    server.started_at = iso_now()  # type: ignore[attr-defined]
    server.serve_forever(poll_interval=0.1)
    return 0


def choose_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 4)


def check_health(url: str, timeout: float = 0.3) -> dict:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(2048).decode("utf-8", errors="replace")
            latency_ms = (time.perf_counter() - started) * 1000
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "latency_ms": round(latency_ms, 3),
                "body": body[:1000],
            }
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {"ok": False, "status": exc.code, "latency_ms": round(latency_ms, 3), "error": str(exc)}
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {"ok": False, "latency_ms": round(latency_ms, 3), "error": f"{type(exc).__name__}:{exc}"}


def wait_health(url: str, timeout_s: float = 4.0) -> dict:
    deadline = time.perf_counter() + timeout_s
    attempts = []
    while time.perf_counter() < deadline:
        result = check_health(url)
        attempts.append(result)
        if result.get("ok"):
            return {
                "ok": True,
                "attempt_count": len(attempts),
                "last_result": result,
                "attempts": attempts[-5:],
            }
        time.sleep(0.05)
    return {
        "ok": False,
        "attempt_count": len(attempts),
        "last_result": attempts[-1] if attempts else None,
        "attempts": attempts[-5:],
    }


def start_child(port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--health-child", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def terminate_child(proc: subprocess.Popen | None) -> None:
    if not proc or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=1.5)


def run_drill(iterations: int) -> dict:
    port = choose_port()
    url = f"http://127.0.0.1:{port}/health"
    child: subprocess.Popen | None = None
    restart_events = []
    recovery_latencies = []
    baseline_latencies = []
    try:
        child = start_child(port)
        baseline = wait_health(url)
        if not baseline.get("ok"):
            return {
                "ok": False,
                "health_url": url,
                "error": "initial_mock_health_failed",
                "baseline": baseline,
                "restart_events": restart_events,
            }
        baseline_latencies.append(float((baseline.get("last_result") or {}).get("latency_ms") or 0.0))
        for index in range(iterations):
            old_pid = child.pid
            kill_started = time.perf_counter()
            child.kill()
            child.wait(timeout=2.0)
            after_kill = check_health(url, timeout=0.15)
            child = start_child(port)
            recovery = wait_health(url, timeout_s=4.0)
            recovery_ms = (time.perf_counter() - kill_started) * 1000
            if recovery.get("ok"):
                recovery_latencies.append(recovery_ms)
                baseline_latencies.append(float((recovery.get("last_result") or {}).get("latency_ms") or 0.0))
            restart_events.append(
                {
                    "iteration": index + 1,
                    "old_child_pid": old_pid,
                    "new_child_pid": child.pid,
                    "owned_child_kill_performed": True,
                    "after_kill_health_ok": after_kill.get("ok"),
                    "recovered": bool(recovery.get("ok")),
                    "recovery_ms": round(recovery_ms, 3),
                    "health_attempts": recovery.get("attempt_count"),
                    "last_health": recovery.get("last_result"),
                }
            )
        return {
            "ok": bool(restart_events) and all(item["recovered"] for item in restart_events),
            "health_url": url,
            "baseline": baseline,
            "restart_events": restart_events,
            "recovery_latency_ms": {
                "count": len(recovery_latencies),
                "min": round(min(recovery_latencies), 3) if recovery_latencies else None,
                "max": round(max(recovery_latencies), 3) if recovery_latencies else None,
                "p50": percentile(recovery_latencies, 0.50),
                "p95": percentile(recovery_latencies, 0.95),
                "p99": percentile(recovery_latencies, 0.99),
            },
            "health_latency_ms": {
                "count": len(baseline_latencies),
                "p50": percentile(baseline_latencies, 0.50),
                "p95": percentile(baseline_latencies, 0.95),
                "p99": percentile(baseline_latencies, 0.99),
            },
        }
    finally:
        terminate_child(child)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded AI-NAS model-service crash recovery drill.")
    parser.add_argument("--health-child", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()

    if args.health_child:
        return run_health_child(args.health_child)
    if args.iterations < 1 or args.iterations > 5:
        raise ValueError("iterations must be between 1 and 5")

    drill = run_drill(args.iterations)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_model_service_recovery_drill" if drill.get("ok") else "failed_model_service_recovery_drill",
        "scope": "bounded local supervisor drill using only a child mock health service created by this probe",
        "drill": drill,
        "summary": {
            "iterations": args.iterations,
            "recovered_count": sum(1 for item in drill.get("restart_events", []) if item.get("recovered")),
            "recovery_p95_ms": (drill.get("recovery_latency_ms") or {}).get("p95"),
            "recovery_p99_ms": (drill.get("recovery_latency_ms") or {}).get("p99"),
            "real_services_killed": False,
            "systemd_restart_performed": False,
            "owned_child_kill_performed": any(
                item.get("owned_child_kill_performed") for item in drill.get("restart_events", [])
            ),
        },
        "audit": {
            "source_files_modified": False,
            "real_model_service_modified": False,
            "real_service_kill_performed": False,
            "owned_child_kill_performed": any(
                item.get("owned_child_kill_performed") for item in drill.get("restart_events", [])
            ),
            "systemd_restart_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON recovery drill reports only",
        },
        "production_gap": "This proves supervised crash/restart mechanics locally; the real S100P Dream/OpenClaw services still need an operator-approved service-level kill/restart drill.",
    }

    run_dir = ensure_report_dir(args.report_root, "model_service_recovery_drill")
    json_path = run_dir / "model_service_recovery_drill.json"
    md_path = run_dir / "model_service_recovery_drill.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Model Service Recovery Drill",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- scope: {payload['scope']}",
        f"- recovered_count: `{payload['summary']['recovered_count']}` / `{payload['summary']['iterations']}`",
        f"- recovery_p95_ms: `{payload['summary']['recovery_p95_ms']}`",
        f"- recovery_p99_ms: `{payload['summary']['recovery_p99_ms']}`",
        "- policy: kill/restart is confined to an owned child mock health service; no real Dream/OpenClaw/systemd service is killed or restarted",
        "",
        "## Restart Events",
        "",
    ]
    for event in drill.get("restart_events", []):
        lines.append(
            f"- iteration `{event['iteration']}` old_pid `{event['old_child_pid']}` "
            f"new_pid `{event['new_child_pid']}` recovered `{event['recovered']}` "
            f"recovery_ms `{event['recovery_ms']}`"
        )
    if not drill.get("restart_events"):
        lines.append(f"- No restart events; error `{drill.get('error')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Production Gap", "", f"- {payload['production_gap']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if drill.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
