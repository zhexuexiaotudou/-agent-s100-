#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_model_service_resilience_probe import DEFAULT_HEALTH_URLS, check_health_url, run_command


TOOL_ID = "ai_nas_model_service_real_recovery_drill"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def health_sweep(urls: list[str]) -> list[dict]:
    return [check_health_url(url) for url in urls]


def approved_restart_command(action: dict) -> list[str] | None:
    service = action.get("service")
    command = action.get("candidate_command")
    if not service or not isinstance(command, list):
        return None
    if command == ["systemctl", "restart", service]:
        return command
    if command == ["systemctl", "--user", "restart", service]:
        return command
    if command == ["env", "XDG_RUNTIME_DIR=/run/user/0", "systemctl", "--user", "restart", service]:
        return command
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute or verify an operator-approved real model/OpenClaw service recovery drill.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--manifest-json", type=Path, required=True)
    parser.add_argument("--approval-phrase", default="")
    parser.add_argument("--action-id", action="append", default=[])
    parser.add_argument("--health-url", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recovery-timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    manifest = read_json(args.manifest_json)
    expected_phrase = ((manifest.get("approval") or {}).get("approval_phrase") or "").strip()
    actions_by_id = {
        action.get("action_id"): action
        for action in manifest.get("proposed_actions", [])
        if action.get("action_type") == "operator_approved_service_restart"
    }
    selected_ids = args.action_id or list(actions_by_id.keys())
    selected_actions = [actions_by_id[action_id] for action_id in selected_ids if action_id in actions_by_id]
    health_urls = args.health_url or manifest.get("health_urls") or DEFAULT_HEALTH_URLS
    approval_ok = bool(expected_phrase and args.approval_phrase.strip() == expected_phrase)
    blockers = []
    if manifest.get("verdict") != "ok_ai_nas_model_service_recovery_manifest":
        blockers.append("manifest_verdict_not_ok")
    if not approval_ok:
        blockers.append("approval_phrase_missing_or_mismatch")
    if not selected_actions:
        blockers.append("no_valid_service_restart_action_selected")

    preflight_health = health_sweep(health_urls)
    events = []
    restart_performed = False
    if args.execute and not blockers:
        for action in selected_actions:
            service = action.get("service")
            command = approved_restart_command(action)
            if not command:
                blockers.append(f"unapproved_restart_command:{action.get('action_id')}")
                break
            started = time.perf_counter()
            result = run_command(command, timeout=int(max(5, args.recovery_timeout_seconds)))
            restart_performed = restart_performed or result.get("ok", False)
            deadline = time.perf_counter() + args.recovery_timeout_seconds
            attempts = []
            while time.perf_counter() < deadline:
                attempts = health_sweep(health_urls)
                if any(item.get("ok") for item in attempts):
                    break
                time.sleep(1.0)
            events.append(
                {
                    "action_id": action.get("action_id"),
                    "service": service,
                    "systemd_scope": action.get("systemd_scope"),
                    "command": command,
                    "command_result": result,
                    "recovery_elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "post_health": attempts,
                    "recovered": bool(result.get("ok") and any(item.get("ok") for item in attempts)),
                }
            )
            if not events[-1]["recovered"]:
                blockers.append(f"service_recovery_failed:{service}")
                break
    elif args.execute and blockers:
        events.append({"skipped": True, "reason": "preconditions_failed", "blockers": blockers})
    else:
        blockers.append("execute_flag_not_set")

    post_health = health_sweep(health_urls)
    ok = bool(args.execute and not blockers and events and all(event.get("recovered") for event in events))
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_model_service_real_recovery_drill" if ok else "limited_ai_nas_model_service_real_recovery_drill",
        "manifest_json": str(args.manifest_json),
        "manifest_id": manifest.get("manifest_id"),
        "approval_phrase_matched": approval_ok,
        "execute": args.execute,
        "selected_action_ids": selected_ids,
        "preflight_health": preflight_health,
        "events": events,
        "post_health": post_health,
        "summary": {
            "real_service_restart_performed": restart_performed,
            "real_service_kill_performed": False,
            "recovered_count": sum(1 for event in events if event.get("recovered")),
            "blockers": blockers,
        },
        "audit": {
            "source_files_modified": False,
            "real_model_service_modified": restart_performed,
            "real_service_restart_performed": restart_performed,
            "real_service_kill_performed": False,
            "systemd_mutation_performed": restart_performed,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON real recovery drill report only; service restart only when exact manifest approval phrase and --execute are supplied",
        },
    }
    run_dir = ensure_report_dir(args.report_root, "model_service_real_recovery_drill")
    json_path = run_dir / "model_service_real_recovery_drill.json"
    md_path = run_dir / "model_service_real_recovery_drill.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Real Model Service Recovery Drill",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- manifest_id: `{payload['manifest_id']}`",
        f"- approval_phrase_matched: `{approval_ok}`",
        f"- execute: `{args.execute}`",
        f"- real_service_restart_performed: `{restart_performed}`",
        f"- recovered_count: `{payload['summary']['recovered_count']}`",
        f"- blockers: `{blockers}`",
        "- policy: no PID kill; service-scoped restart only with exact manifest approval and --execute",
        "",
        "## Events",
        "",
    ]
    if not events:
        lines.append("- No restart events.")
    for event in events:
        lines.append(f"- action `{event.get('action_id')}` service `{event.get('service')}` recovered `{event.get('recovered')}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
