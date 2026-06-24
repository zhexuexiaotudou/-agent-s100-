#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_soak_completion_gate_watcher"


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def process_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def pid_from_file(path: Path | None) -> int | None:
    if not path:
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return int(raw)
    except Exception:
        return None


def process_snapshot(pid: int | None) -> dict:
    if not pid:
        return {"found": False, "pid": pid}
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etimes=", "-o", "etime=", "-o", "cmd="],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return {"found": False, "pid": pid, "error": f"{type(exc).__name__}: {exc}"}
    if completed.returncode != 0 or not completed.stdout.strip():
        return {"found": False, "pid": pid, "stderr": completed.stderr.strip()[:1000]}
    raw = completed.stdout.strip()
    parts = raw.split(None, 2)
    try:
        elapsed_seconds = int(parts[0])
    except Exception:
        elapsed_seconds = None
    etime = parts[1] if len(parts) > 1 else None
    command = parts[2] if len(parts) > 2 else raw
    target_seconds = None
    match = re.search(r"--duration-seconds\s+(\d+)", command)
    if match:
        target_seconds = int(match.group(1))
    remaining_seconds = None
    progress_percent = None
    estimated_completion_epoch = None
    estimated_completion_at = None
    if elapsed_seconds is not None and target_seconds:
        remaining_seconds = max(0, target_seconds - elapsed_seconds)
        progress_percent = round(min(100.0, elapsed_seconds * 100.0 / target_seconds), 3)
        estimated_completion_epoch = int(time.time() + remaining_seconds)
        estimated_completion_at = datetime.fromtimestamp(estimated_completion_epoch).astimezone().isoformat()
    return {
        "found": True,
        "pid": pid,
        "elapsed_seconds": elapsed_seconds,
        "etime": etime,
        "target_seconds": target_seconds,
        "remaining_seconds": remaining_seconds,
        "estimated_completion_epoch": estimated_completion_epoch,
        "estimated_completion_at": estimated_completion_at,
        "progress_percent": progress_percent,
        "command": command,
    }


def latest_json(report_root: Path, filename: str) -> Path | None:
    candidates = [path for path in report_root.rglob(filename) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def soak_summary(path: Path | None, min_mtime_epoch: float | None = None) -> dict:
    path_mtime_epoch = None
    fresh_after_min_mtime = min_mtime_epoch is None
    if path:
        try:
            path_mtime_epoch = path.stat().st_mtime
            fresh_after_min_mtime = min_mtime_epoch is None or path_mtime_epoch >= min_mtime_epoch
        except OSError:
            fresh_after_min_mtime = False if min_mtime_epoch is not None else True
    payload = read_json(path) if path else None
    if not payload:
        return {
            "found": False,
            "path": str(path) if path else None,
            "path_mtime_epoch": path_mtime_epoch,
            "min_mtime_epoch": min_mtime_epoch,
            "fresh_after_min_mtime": fresh_after_min_mtime,
            "verdict": None,
            "summary": {},
            "config": {},
            "precheck_without_freshness": False,
            "meets_precheck": False,
        }
    summary = payload.get("summary") or {}
    config = payload.get("config") or {}
    elapsed = float(summary.get("elapsed_seconds") or 0.0)
    file_count = int(summary.get("final_file_count") or 0)
    precheck_without_freshness = bool(
        payload.get("verdict") == "ok_ai_nas_nas_backed_long_soak"
        and summary.get("nas_backed") is True
        and elapsed >= 21600.0
        and file_count >= 100
    )
    return {
        "found": True,
        "path": str(path),
        "path_mtime_epoch": path_mtime_epoch,
        "min_mtime_epoch": min_mtime_epoch,
        "fresh_after_min_mtime": fresh_after_min_mtime,
        "verdict": payload.get("verdict"),
        "generated_at": payload.get("generated_at"),
        "summary": summary,
        "config": config,
        "precheck_without_freshness": precheck_without_freshness,
        "meets_precheck": bool(precheck_without_freshness and fresh_after_min_mtime),
    }


def run_probe(script_path: Path, report_root: Path, evidence_roots: list[Path], timeout: int) -> dict:
    cmd = [sys.executable, str(script_path), "--report-root", str(report_root)]
    for root in evidence_roots:
        cmd.extend(["--evidence-root", str(root)])
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for a NAS-backed soak PID to finish, then run production readiness gate.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--pid-file", type=Path, default=None)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--max-wait-seconds", type=float, default=25200.0)
    parser.add_argument("--post-exit-report-wait-seconds", type=float, default=600.0)
    parser.add_argument("--post-exit-poll-seconds", type=float, default=10.0)
    parser.add_argument("--gate-timeout-seconds", type=int, default=900)
    parser.add_argument("--runbook-timeout-seconds", type=int, default=600)
    parser.add_argument("--run-runbook", action="store_true", help="Refresh production blocker runbook after the gate.")
    parser.add_argument("--dry-run", action="store_true", help="Do not run production gate; only report what would happen.")
    parser.add_argument("--once", action="store_true", help="Check once and exit without waiting.")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "soak_completion_gate_watcher")
    status_path = args.report_root / "long_soak_jobs" / "soak_completion_gate_watcher_latest.json"
    evidence_roots = args.evidence_root or [args.report_root]
    pid = args.pid if args.pid is not None else pid_from_file(args.pid_file)
    started = time.monotonic()
    watcher_started_epoch = time.time()
    watcher_started_at = datetime.fromtimestamp(watcher_started_epoch).astimezone().isoformat()
    events: list[dict] = []
    script_dir = Path(__file__).resolve().parent
    gate_script = script_dir / "ai_nas_production_readiness_gate_probe.py"
    runbook_script = script_dir / "ai_nas_production_blocker_runbook_contract_probe.py"

    verdict = "waiting_ai_nas_soak_completion_gate_watcher"
    gate_result: dict | None = None
    runbook_result: dict | None = None
    post_exit_wait_elapsed = 0.0
    soak_precheck_before_gate = False
    latest_soak = soak_summary(latest_json(args.report_root, "nas_backed_long_soak.json"), watcher_started_epoch)
    while True:
        running = process_running(pid)
        soak_process = process_snapshot(pid)
        elapsed = time.monotonic() - started
        event = {
            "at": iso_now(),
            "pid": pid,
            "pid_running": running,
            "soak_process": soak_process,
            "elapsed_wait_seconds": round(elapsed, 3),
            "latest_soak": latest_soak,
        }
        events.append(event)
        write_status(
            status_path,
            {
                "generated_at": iso_now(),
                "tool_id": TOOL_ID,
                "verdict": verdict,
                "status": "waiting" if running else "ready_to_gate",
                "watcher_report_dir": str(run_dir),
                "watcher_started_epoch": watcher_started_epoch,
                "watcher_started_at": watcher_started_at,
                "min_soak_report_mtime_epoch": watcher_started_epoch,
                "evidence_roots": [str(root) for root in evidence_roots],
                "pid": pid,
                "pid_running": running,
                "soak_process": soak_process,
                "elapsed_wait_seconds": round(elapsed, 3),
                "latest_soak_report": latest_soak.get("path"),
                "latest_soak_meets_precheck": latest_soak.get("meets_precheck"),
                "summary": {
                    "event_count": len(events),
                    "final_pid_running": running,
                    "final_soak_process": soak_process,
                    "wait_elapsed_seconds": round(elapsed, 3),
                    "latest_soak_report": latest_soak.get("path"),
                    "latest_soak_meets_precheck": latest_soak.get("meets_precheck"),
                    "latest_soak_fresh_after_min_mtime": latest_soak.get("fresh_after_min_mtime"),
                    "latest_soak_precheck_without_freshness": latest_soak.get("precheck_without_freshness"),
                    "gate_returncode": None,
                    "runbook_returncode": None,
                    "latest_gate_report": None,
                    "latest_runbook_report": None,
                },
                "gate_report": None,
                "runbook_report": None,
                "latest_soak": latest_soak,
            },
        )
        if args.once:
            verdict = "waiting_ai_nas_soak_completion_gate_watcher" if running else "ready_ai_nas_soak_completion_gate_watcher"
            break
        if not running:
            if args.dry_run:
                verdict = "dry_run_ai_nas_soak_completion_gate_watcher"
            else:
                post_exit_started = time.monotonic()
                latest_soak = soak_summary(latest_json(args.report_root, "nas_backed_long_soak.json"), watcher_started_epoch)
                while not latest_soak.get("meets_precheck") and (time.monotonic() - post_exit_started) < args.post_exit_report_wait_seconds:
                    post_exit_wait_elapsed = time.monotonic() - post_exit_started
                    write_status(
                        status_path,
                        {
                            "generated_at": iso_now(),
                            "tool_id": TOOL_ID,
                            "verdict": verdict,
                            "status": "waiting_for_soak_report",
                            "watcher_report_dir": str(run_dir),
                            "watcher_started_epoch": watcher_started_epoch,
                            "watcher_started_at": watcher_started_at,
                            "min_soak_report_mtime_epoch": watcher_started_epoch,
                            "evidence_roots": [str(root) for root in evidence_roots],
                            "pid": pid,
                            "pid_running": False,
                            "soak_process": process_snapshot(pid),
                            "elapsed_wait_seconds": round(time.monotonic() - started, 3),
                            "post_exit_wait_elapsed_seconds": round(post_exit_wait_elapsed, 3),
                            "post_exit_report_wait_seconds": args.post_exit_report_wait_seconds,
                            "latest_soak_report": latest_soak.get("path"),
                            "latest_soak_meets_precheck": latest_soak.get("meets_precheck"),
                            "summary": {
                                "event_count": len(events),
                                "final_pid_running": False,
                                "final_soak_process": process_snapshot(pid),
                                "wait_elapsed_seconds": round(time.monotonic() - started, 3),
                                "post_exit_wait_elapsed_seconds": round(post_exit_wait_elapsed, 3),
                                "latest_soak_report": latest_soak.get("path"),
                                "latest_soak_meets_precheck": latest_soak.get("meets_precheck"),
                                "latest_soak_fresh_after_min_mtime": latest_soak.get("fresh_after_min_mtime"),
                                "latest_soak_precheck_without_freshness": latest_soak.get("precheck_without_freshness"),
                                "gate_returncode": None,
                                "runbook_returncode": None,
                                "latest_gate_report": None,
                                "latest_runbook_report": None,
                            },
                            "gate_report": None,
                            "runbook_report": None,
                            "latest_soak": latest_soak,
                        },
                    )
                    time.sleep(max(1.0, args.post_exit_poll_seconds))
                    latest_soak = soak_summary(latest_json(args.report_root, "nas_backed_long_soak.json"), watcher_started_epoch)
                post_exit_wait_elapsed = time.monotonic() - post_exit_started
                soak_precheck_before_gate = bool(latest_soak.get("meets_precheck"))
                gate_result = run_probe(gate_script, args.report_root, evidence_roots, args.gate_timeout_seconds)
                if args.run_runbook:
                    runbook_result = run_probe(runbook_script, args.report_root, evidence_roots, args.runbook_timeout_seconds)
                verdict = (
                    "ok_ai_nas_soak_completion_gate_watcher"
                    if soak_precheck_before_gate and gate_result.get("returncode") == 0 and (runbook_result is None or runbook_result.get("returncode") == 0)
                    else "failed_ai_nas_soak_completion_gate_watcher"
                )
            break
        if elapsed >= args.max_wait_seconds:
            verdict = "timeout_ai_nas_soak_completion_gate_watcher"
            break
        time.sleep(max(1.0, args.poll_seconds))
        latest_soak = soak_summary(latest_json(args.report_root, "nas_backed_long_soak.json"), watcher_started_epoch)

    latest_gate = latest_json(args.report_root, "production_readiness_gate.json")
    latest_runbook = latest_json(args.report_root, "production_blocker_runbook_contract.json")
    final_soak_process = process_snapshot(pid)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "pid": pid,
        "pid_file": str(args.pid_file) if args.pid_file else None,
        "report_root": str(args.report_root),
        "watcher_started_epoch": watcher_started_epoch,
        "watcher_started_at": watcher_started_at,
        "min_soak_report_mtime_epoch": watcher_started_epoch,
        "evidence_roots": [str(root) for root in evidence_roots],
        "dry_run": args.dry_run,
        "once": args.once,
        "summary": {
            "event_count": len(events),
            "final_pid_running": process_running(pid),
            "final_soak_process": final_soak_process,
            "wait_elapsed_seconds": round(time.monotonic() - started, 3),
            "post_exit_wait_elapsed_seconds": round(post_exit_wait_elapsed, 3),
            "soak_precheck_before_gate": soak_precheck_before_gate,
            "latest_soak_report": latest_soak.get("path"),
            "latest_soak_meets_precheck": latest_soak.get("meets_precheck"),
            "latest_soak_fresh_after_min_mtime": latest_soak.get("fresh_after_min_mtime"),
            "latest_soak_precheck_without_freshness": latest_soak.get("precheck_without_freshness"),
            "gate_returncode": gate_result.get("returncode") if gate_result else None,
            "runbook_returncode": runbook_result.get("returncode") if runbook_result else None,
            "latest_gate_report": str(latest_gate) if latest_gate else None,
            "latest_runbook_report": str(latest_runbook) if latest_runbook else None,
        },
        "latest_soak": latest_soak,
        "soak_precheck_before_gate": soak_precheck_before_gate,
        "gate_report": str(latest_gate) if latest_gate else None,
        "runbook_report": str(latest_runbook) if latest_runbook else None,
        "gate_result": gate_result,
        "runbook_result": runbook_result,
        "events": events[-20:],
        "audit": {
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_restart_performed": False,
            "writes": "watcher JSON/MD status plus production gate/runbook reports after soak completion",
        },
    }
    json_path = run_dir / "soak_completion_gate_watcher.json"
    md_path = run_dir / "soak_completion_gate_watcher.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Soak Completion Gate Watcher",
        "",
        f"- verdict: `{verdict}`",
        f"- pid: `{pid}`",
        f"- final_pid_running: `{payload['summary']['final_pid_running']}`",
        f"- latest_soak_report: `{payload['summary']['latest_soak_report']}`",
        f"- latest_soak_meets_precheck: `{payload['summary']['latest_soak_meets_precheck']}`",
        f"- latest_soak_fresh_after_min_mtime: `{payload['summary']['latest_soak_fresh_after_min_mtime']}`",
        f"- latest_gate_report: `{payload['summary']['latest_gate_report']}`",
        f"- latest_runbook_report: `{payload['summary']['latest_runbook_report']}`",
        f"- gate_returncode: `{payload['summary']['gate_returncode']}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    write_status(status_path, payload)
    print(md_path)
    print(json_path)
    return 0 if verdict.startswith(("ok_", "waiting_", "ready_", "dry_run_")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
