#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_goal_completion_finalizer"


def read_json(path: Path | None) -> dict | None:
    if not path:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def latest_json(root: Path, filename: str) -> Path | None:
    candidates = [path for path in root.rglob(filename) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def watcher_ready(payload: dict | None) -> bool:
    if not payload:
        return False
    summary = payload.get("summary") or {}
    latest_soak_meets_precheck = payload.get("latest_soak_meets_precheck")
    if latest_soak_meets_precheck is None:
        latest_soak_meets_precheck = summary.get("latest_soak_meets_precheck")
    gate_report = payload.get("gate_report") or summary.get("latest_gate_report")
    runbook_report = payload.get("runbook_report") or summary.get("latest_runbook_report")
    gate_returncode = summary.get("gate_returncode")
    runbook_returncode = summary.get("runbook_returncode")
    return (
        payload.get("verdict") == "ok_ai_nas_soak_completion_gate_watcher"
        and latest_soak_meets_precheck is True
        and bool(gate_report)
        and bool(runbook_report)
        and gate_returncode == 0
        and (runbook_returncode is None or runbook_returncode == 0)
    )


def run_goal_audit(script_path: Path, report_root: Path, service_status_json: Path | None, timeout: int) -> dict:
    cmd = [sys.executable, str(script_path), "--report-root", str(report_root)]
    if service_status_json:
        cmd.extend(["--service-status-json", str(service_status_json)])
    started = time.perf_counter()
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "command": cmd,
            "returncode": completed.returncode,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "stdout": completed.stdout.strip()[-4000:],
            "stderr": completed.stderr.strip()[-4000:],
        }
    except Exception as exc:
        return {
            "command": cmd,
            "returncode": None,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_write_json(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for the soak watcher final gate/runbook, then run the strict goal completion audit.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--watcher-status-json", type=Path, default=None)
    parser.add_argument("--service-status-json", type=Path, default=None)
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--max-wait-seconds", type=float, default=10800.0)
    parser.add_argument("--audit-timeout-seconds", type=int, default=600)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "goal_completion_finalizer")
    status_path = args.report_root / "long_soak_jobs" / "goal_completion_finalizer_latest.json"
    watcher_path = args.watcher_status_json or args.report_root / "long_soak_jobs" / "soak_completion_gate_watcher_latest.json"
    service_status_json = args.service_status_json or latest_json(args.report_root, "services.json")
    audit_script = Path(__file__).resolve().parent / "ai_nas_goal_completion_audit_probe.py"
    started = time.monotonic()
    events: list[dict] = []
    verdict = "waiting_ai_nas_goal_completion_finalizer"
    audit_result: dict | None = None

    while True:
        watcher_payload = read_json(watcher_path)
        elapsed = time.monotonic() - started
        ready = watcher_ready(watcher_payload)
        event = {
            "at": iso_now(),
            "elapsed_wait_seconds": round(elapsed, 3),
            "watcher_path": str(watcher_path),
            "watcher_verdict": watcher_payload.get("verdict") if watcher_payload else None,
            "watcher_status": watcher_payload.get("status") if watcher_payload else None,
            "watcher_ready": ready,
        }
        events.append(event)
        latest_audit = latest_json(args.report_root, "goal_completion_audit.json")
        latest_audit_payload = read_json(latest_audit)
        write_status(
            status_path,
            {
                "generated_at": iso_now(),
                "tool_id": TOOL_ID,
                "verdict": verdict,
                "status": "waiting_for_watcher" if not ready else "ready_to_audit",
                "report_root": str(args.report_root),
                "watcher_status_json": str(watcher_path),
                "service_status_json": str(service_status_json) if service_status_json else None,
                "finalizer_pid": os.getpid(),
                "elapsed_wait_seconds": round(elapsed, 3),
                "watcher_ready": ready,
                "watcher_verdict": event["watcher_verdict"],
                "watcher_status": event["watcher_status"],
                "summary": {
                    "event_count": len(events),
                    "finalizer_pid": os.getpid(),
                    "wait_elapsed_seconds": round(elapsed, 3),
                    "watcher_ready": ready,
                    "audit_returncode": None,
                    "latest_goal_audit_report": str(latest_audit) if latest_audit else None,
                    "latest_goal_audit_verdict": latest_audit_payload.get("verdict") if latest_audit_payload else None,
                    "latest_goal_audit_summary": latest_audit_payload.get("summary") if latest_audit_payload else None,
                },
                "audit_result": None,
                "events": events[-20:],
            },
        )
        if ready:
            audit_result = run_goal_audit(audit_script, args.report_root, service_status_json, args.audit_timeout_seconds)
            verdict = "ok_ai_nas_goal_completion_finalizer" if audit_result.get("returncode") == 0 else "limited_ai_nas_goal_completion_finalizer"
            break
        if args.once:
            break
        if elapsed >= args.max_wait_seconds:
            verdict = "timeout_ai_nas_goal_completion_finalizer"
            break
        time.sleep(max(1.0, args.poll_seconds))

    final_watcher_payload = read_json(watcher_path)
    final_watcher_ready = watcher_ready(final_watcher_payload)
    latest_audit = latest_json(args.report_root, "goal_completion_audit.json")
    latest_audit_payload = read_json(latest_audit)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "status": (
            "complete"
            if verdict == "ok_ai_nas_goal_completion_finalizer"
            else "waiting_for_watcher"
            if verdict == "waiting_ai_nas_goal_completion_finalizer"
            else "incomplete"
        ),
        "report_root": str(args.report_root),
        "watcher_status_json": str(watcher_path),
        "service_status_json": str(service_status_json) if service_status_json else None,
        "finalizer_pid": os.getpid(),
        "watcher_ready": final_watcher_ready,
        "watcher_verdict": final_watcher_payload.get("verdict") if final_watcher_payload else None,
        "watcher_status": final_watcher_payload.get("status") if final_watcher_payload else None,
        "summary": {
            "event_count": len(events),
            "finalizer_pid": os.getpid(),
            "wait_elapsed_seconds": round(time.monotonic() - started, 3),
            "watcher_ready": final_watcher_ready,
            "audit_returncode": audit_result.get("returncode") if audit_result else None,
            "latest_goal_audit_report": str(latest_audit) if latest_audit else None,
            "latest_goal_audit_verdict": latest_audit_payload.get("verdict") if latest_audit_payload else None,
            "latest_goal_audit_summary": latest_audit_payload.get("summary") if latest_audit_payload else None,
        },
        "audit_result": audit_result,
        "events": events[-20:],
        "audit": {
            "real_personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "writes": "goal finalizer JSON/Markdown status plus strict goal completion audit report",
        },
    }
    json_path = run_dir / "goal_completion_finalizer.json"
    md_path = run_dir / "goal_completion_finalizer.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Goal Completion Finalizer",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- watcher_ready: `{payload['summary']['watcher_ready']}`",
        f"- audit_returncode: `{payload['summary']['audit_returncode']}`",
        f"- latest_goal_audit_report: `{payload['summary']['latest_goal_audit_report']}`",
        f"- latest_goal_audit_verdict: `{payload['summary']['latest_goal_audit_verdict']}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    write_status(status_path, payload)
    print(md_path)
    print(json_path)
    return 0 if verdict == "ok_ai_nas_goal_completion_finalizer" or verdict.startswith("waiting_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
