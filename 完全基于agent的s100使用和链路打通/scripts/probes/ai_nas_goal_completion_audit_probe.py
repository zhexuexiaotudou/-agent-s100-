#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_goal_completion_audit"


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


def report_ref(root: Path, filename: str) -> dict:
    path = latest_json(root, filename)
    payload = read_json(path)
    if not path or not payload:
        return {"found": False, "filename": filename, "path": str(path) if path else None}
    return {
        "found": True,
        "filename": filename,
        "path": str(path),
        "mtime_epoch": path.stat().st_mtime,
        "verdict": payload.get("verdict"),
        "generated_at": payload.get("generated_at"),
        "summary": payload.get("summary") or {},
        "warnings": payload.get("warnings") or [],
        "blockers": payload.get("blockers") or [],
        "payload": payload,
    }


def service_status_ref(path: Path | None) -> dict:
    payload = read_json(path) if path else None
    if not payload:
        return {"found": False, "path": str(path) if path else None}
    summary = payload.get("summary") or payload
    return {
        "found": True,
        "path": str(path),
        "ok_count": summary.get("ok_count"),
        "failed_count": summary.get("failed_count"),
        "source": payload.get("source") or summary.get("source"),
        "payload": payload,
    }


def watcher_ref(root: Path) -> dict:
    path = root / "long_soak_jobs" / "soak_completion_gate_watcher_latest.json"
    payload = read_json(path)
    if not payload:
        return {"found": False, "path": str(path)}
    summary = payload.get("summary") or {}
    gate_result = payload.get("gate_result") or {}
    runbook_result = payload.get("runbook_result") or {}
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "pid_running": payload.get("pid_running"),
        "latest_soak_meets_precheck": payload.get("latest_soak_meets_precheck", summary.get("latest_soak_meets_precheck")),
        "gate_report": payload.get("gate_report") or summary.get("latest_gate_report"),
        "runbook_report": payload.get("runbook_report") or summary.get("latest_runbook_report"),
        "gate_returncode": gate_result.get("returncode", summary.get("gate_returncode")),
        "runbook_returncode": runbook_result.get("returncode", summary.get("runbook_returncode")),
        "soak_process": payload.get("soak_process") or {},
        "generated_at": payload.get("generated_at"),
        "payload": payload,
    }


def ok(condition: bool, evidence: dict | None = None, blockers: list[str] | None = None) -> dict:
    return {
        "ok": bool(condition),
        "evidence": evidence or {},
        "blockers": blockers or ([] if condition else ["condition_not_met"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit current evidence against the three active Digua/OpenClaw/AI-NAS goal workstreams.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--service-status-json", type=Path, default=None)
    parser.add_argument("--min-soak-seconds", type=float, default=21600.0)
    parser.add_argument("--min-soak-files", type=int, default=100)
    parser.add_argument("--max-dream7b-first-content-ms", type=float, default=5000.0)
    parser.add_argument("--max-dream7b-first-progress-ms", type=float, default=500.0)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "goal_completion_audit")
    gate = report_ref(args.report_root, "production_readiness_gate.json")
    runbook = report_ref(args.report_root, "production_blocker_runbook_contract.json")
    soak = report_ref(args.report_root, "nas_backed_long_soak.json")
    watcher = watcher_ref(args.report_root)
    portal = report_ref(args.report_root, "operator_portal_contract.json")
    slo = report_ref(args.report_root, "operational_slo_rollup_contract.json")
    traceability = report_ref(args.report_root, "objective_traceability_contract.json")
    dream = report_ref(args.report_root, "dream7b_perf_identity.json")
    service_status = service_status_ref(args.service_status_json)

    gate_summary = gate.get("summary") or {}
    soak_summary = soak.get("summary") or {}
    dream_summary = dream.get("summary") or {}
    first_progress = dream_summary.get("first_progress_ms") or {}
    first_content = dream_summary.get("first_content_ms") or {}

    gate_ready = (
        gate.get("verdict") == "ready_ai_nas_production_readiness_gate"
        and gate_summary.get("production_ready") is True
        and int(gate_summary.get("blocker_count") or 0) == 0
    )
    soak_ready = (
        soak.get("verdict") == "ok_ai_nas_nas_backed_long_soak"
        and soak_summary.get("nas_backed") is True
        and float(soak_summary.get("elapsed_seconds") or 0.0) >= args.min_soak_seconds
        and int(soak_summary.get("final_file_count") or 0) >= args.min_soak_files
        and int(soak_summary.get("final_failed_count") or 0) == 0
    )
    watcher_ready = (
        watcher.get("latest_soak_meets_precheck") is True
        and bool(watcher.get("gate_report"))
        and bool(watcher.get("runbook_report"))
        and watcher.get("gate_returncode") == 0
        and watcher.get("runbook_returncode") == 0
    )
    portal_ready = (
        portal.get("verdict") == "ok_ai_nas_operator_portal_contract"
        and (portal.get("summary") or {}).get("production_readiness_found") is True
        and (portal.get("summary") or {}).get("operational_slo_found") is True
        and (portal.get("summary") or {}).get("objective_traceability_found") is True
        and (portal.get("summary") or {}).get("dream7b_interaction_found") is True
    )
    service_ready = service_status.get("found") and int(service_status.get("failed_count") or 0) == 0
    dream_ready = (
        dream.get("verdict") == "ok_dream7b_perf_identity"
        and int(dream_summary.get("failed_case_count") or 0) == 0
        and int(dream_summary.get("stream_supported_case_count") or 0) >= 1
        and int(dream_summary.get("progress_event_case_count") or 0) >= 1
        and float(first_progress.get("p50_ms") or 1e9) <= args.max_dream7b_first_progress_ms
        and float(first_content.get("p50_ms") or 1e9) <= args.max_dream7b_first_content_ms
    )
    slo_ready = slo.get("verdict") == "ok_ai_nas_operational_slo_rollup_contract"
    traceability_ready = (
        traceability.get("verdict") == "ok_ai_nas_objective_traceability_contract"
        and int((traceability.get("summary") or {}).get("missing_or_failed_row_count") or 0) == 0
    )

    checks = {
        "nas_personal_soak_and_gate": ok(
            gate_ready and soak_ready and watcher_ready and runbook.get("verdict") == "ok_ai_nas_production_blocker_runbook_contract",
            {
                "gate": {key: gate.get(key) for key in ["path", "verdict", "summary", "warnings", "blockers"]},
                "soak": {key: soak.get(key) for key in ["path", "verdict", "summary"]},
                "watcher": {key: watcher.get(key) for key in ["path", "status", "pid_running", "latest_soak_meets_precheck", "gate_report", "runbook_report", "gate_returncode", "runbook_returncode", "soak_process"]},
                "runbook": {key: runbook.get(key) for key in ["path", "verdict", "summary"]},
            },
            [
                item
                for item, passed in [
                    ("production_gate_not_ready", gate_ready),
                    ("six_hour_nas_soak_not_verified", soak_ready),
                    ("watcher_final_gate_runbook_not_verified", watcher_ready),
                    ("runbook_not_ok", runbook.get("verdict") == "ok_ai_nas_production_blocker_runbook_contract"),
                ]
                if not passed
            ],
        ),
        "operator_portal_demo_ready": ok(
            portal_ready and slo_ready and traceability_ready and (service_ready or not args.service_status_json),
            {
                "portal": {key: portal.get(key) for key in ["path", "verdict", "summary"]},
                "slo": {key: slo.get(key) for key in ["path", "verdict", "summary"]},
                "traceability": {key: traceability.get(key) for key in ["path", "verdict", "summary"]},
                "service_status": {key: service_status.get(key) for key in ["path", "ok_count", "failed_count", "source"]},
            },
            [
                item
                for item, passed in [
                    ("operator_portal_contract_not_ok", portal_ready),
                    ("operational_slo_rollup_not_ok", slo_ready),
                    ("objective_traceability_not_ok", traceability_ready),
                    ("service_status_not_ok", service_ready or not args.service_status_json),
                ]
                if not passed
            ],
        ),
        "dream7b_interaction_ready": ok(
            dream_ready,
            {
                "dream7b": {
                    "path": dream.get("path"),
                    "verdict": dream.get("verdict"),
                    "summary": dream_summary,
                    "warnings": dream.get("warnings"),
                }
            },
            [
                item
                for item, passed in [
                    ("dream7b_report_not_ok", dream.get("verdict") == "ok_dream7b_perf_identity"),
                    ("dream7b_cases_failed", int(dream_summary.get("failed_case_count") or 0) == 0),
                    ("sse_streaming_not_verified", int(dream_summary.get("stream_supported_case_count") or 0) >= 1),
                    ("progress_events_not_verified", int(dream_summary.get("progress_event_case_count") or 0) >= 1),
                    ("first_progress_above_threshold", float(first_progress.get("p50_ms") or 1e9) <= args.max_dream7b_first_progress_ms),
                    ("first_content_above_threshold", float(first_content.get("p50_ms") or 1e9) <= args.max_dream7b_first_content_ms),
                ]
                if not passed
            ],
        ),
    }
    blocker_list = [f"{name}:{blocker}" for name, check in checks.items() for blocker in check["blockers"]]
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_goal_completion_audit" if not blocker_list else "limited_ai_nas_goal_completion_audit",
        "scope": "completion audit for the three active goal workstreams: NAS soak/gate, Operator Portal, and Dream7B interaction",
        "config": {
            "report_root": str(args.report_root),
            "service_status_json": str(args.service_status_json) if args.service_status_json else None,
            "min_soak_seconds": args.min_soak_seconds,
            "min_soak_files": args.min_soak_files,
            "max_dream7b_first_content_ms": args.max_dream7b_first_content_ms,
            "max_dream7b_first_progress_ms": args.max_dream7b_first_progress_ms,
        },
        "summary": {
            "check_count": len(checks),
            "passed_check_count": sum(1 for check in checks.values() if check["ok"]),
            "blocker_count": len(blocker_list),
            "blockers": blocker_list,
            "all_goal_requirements_verified": not blocker_list,
        },
        "checks": checks,
        "audit": {
            "real_personal_source_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "service_started": False,
            "network_call_performed": False,
            "writes": "bounded JSON/Markdown audit report only",
        },
        "note": "This audit is intentionally stricter than the production gate for the current thread goal; it requires the fresh 6-hour NAS-backed soak plus watcher-triggered gate/runbook evidence before reporting ok.",
    }
    json_path = run_dir / "goal_completion_audit.json"
    md_path = run_dir / "goal_completion_audit.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Goal Completion Audit",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- passed_check_count: `{payload['summary']['passed_check_count']}/{payload['summary']['check_count']}`",
        f"- blocker_count: `{payload['summary']['blocker_count']}`",
        "",
        "## Checks",
        "",
    ]
    for name, check in checks.items():
        lines.append(f"- `{name}` ok `{check['ok']}` blockers `{check['blockers']}`")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {item}" for item in blocker_list) if blocker_list else lines.append("- none")
    lines.extend(["", "## Note", "", f"- {payload['note']}"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0 if not blocker_list else 1


if __name__ == "__main__":
    raise SystemExit(main())
