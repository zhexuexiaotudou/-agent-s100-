#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_model_service_resilience_probe import (
    DEFAULT_HEALTH_URLS,
    DEFAULT_SERVICES,
    candidate_unit_paths,
    check_health_url,
    parse_unit_file,
    run_command,
    systemctl_service_check,
)


TOOL_ID = "ai_nas_model_service_recovery_manifest"


def hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_recovery_actions(services: list[str], health_urls: list[str], systemctl_checks: list[dict]) -> list[dict]:
    checks_by_service = {item.get("service"): item for item in systemctl_checks}
    actions = []
    for index, service in enumerate(services, start=1):
        check = checks_by_service.get(service) or {}
        scope = check.get("active_scope") or check.get("enabled_scope") or "system"
        command = (
            ["env", "XDG_RUNTIME_DIR=/run/user/0", "systemctl", "--user", "restart", service]
            if scope == "user"
            else ["systemctl", "restart", service]
        )
        actions.append(
            {
                "action_id": f"svc-restart-{hashlib.sha256(service.encode('utf-8')).hexdigest()[:12]}",
                "phase": index,
                "service": service,
                "systemd_scope": scope,
                "action_type": "operator_approved_service_restart",
                "status": "proposed_requires_human_confirmation",
                "execution_allowed_by_this_tool": False,
                "requires_human_confirmation": True,
                "destructive_or_disruptive": True,
                "candidate_command": command,
                "preconditions": [
                    "operator approves this manifest id and exact action id",
                    "low-traffic window is confirmed",
                    "baseline health endpoints and queue depth are captured",
                    "unit file has a restart policy or an explicit rollback command is present",
                    "do not run concurrent recovery actions for multiple services",
                ],
                "post_checks": [
                    "health endpoints return HTTP 2xx within the recovery SLO",
                    "queue depth stops increasing for pending model/dialog jobs",
                    "P95/P99 smoke latency is captured after recovery",
                    "execution manifest records command, return code, timestamps, and health results",
                ],
                "rollback_plan": [
                    f"if restart fails, run `{' '.join(command[:-2] + ['status', service])}` and capture logs",
                    f"if service was previously active and cannot recover, run service stop only after operator approval",
                    "restore previous unit file only from a pre-captured backup manifest",
                    "append rollback_manifest.json and never delete logs or reports",
                ],
            }
        )
    actions.append(
        {
            "action_id": "post-recovery-health-sweep",
            "phase": len(services) + 1,
            "service": None,
            "action_type": "post_recovery_health_sweep",
            "status": "proposed_requires_human_confirmation",
            "execution_allowed_by_this_tool": False,
            "requires_human_confirmation": True,
            "destructive_or_disruptive": False,
            "candidate_health_urls": health_urls,
            "preconditions": [
                "all approved service actions have execution manifests",
                "no service action is still running",
            ],
            "post_checks": [
                "all configured health URLs are checked",
                "latency samples are recorded for P50/P95/P99",
                "final recovery report links preflight, execution, and rollback manifests",
            ],
            "rollback_plan": [
                "health sweep has no write-side rollback; failed checks become explicit blockers",
            ],
        }
    )
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only AI-NAS model-service recovery approval manifest.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--health-url", action="append", default=[])
    parser.add_argument("--unit-file", action="append", type=Path, default=[])
    parser.add_argument("--recovery-slo-seconds", type=float, default=30.0)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    services = args.service or DEFAULT_SERVICES
    health_urls = args.health_url or DEFAULT_HEALTH_URLS
    systemctl_checks = [systemctl_service_check(service) for service in services]
    health = [check_health_url(url) for url in health_urls]
    unit_files = [parse_unit_file(path) for path in candidate_unit_paths(repo_root, args.unit_file)]
    actions = build_recovery_actions(services, health_urls, systemctl_checks)
    manifest_seed = {
        "services": services,
        "health_urls": health_urls,
        "actions": [
            {
                "action_id": action["action_id"],
                "service": action.get("service"),
                "systemd_scope": action.get("systemd_scope"),
                "candidate_command": action.get("candidate_command"),
            }
            for action in actions
        ],
        "recovery_slo_seconds": args.recovery_slo_seconds,
    }
    manifest_id = "msr-" + hash_payload(manifest_seed)[:16]
    manifest = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "manifest_id": manifest_id,
        "status": "awaiting_human_confirmation",
        "scope": "read-only recovery approval manifest for real model/OpenClaw service recovery drills",
        "services": services,
        "health_urls": health_urls,
        "recovery_slo_seconds": args.recovery_slo_seconds,
        "preflight_snapshot": {
            "health": health,
            "systemctl_checks": systemctl_checks,
            "unit_files": unit_files,
            "health_ok_count": sum(1 for item in health if item.get("ok")),
            "restart_policy_count": sum(1 for item in unit_files if item.get("has_restart_policy")),
            "systemctl_active_count": sum(1 for item in systemctl_checks if item["is_active"].get("ok")),
        },
        "proposed_actions": actions,
        "blocked_actions": [
            {
                "action_type": "kill_process_by_pid",
                "status": "blocked_not_generated",
                "reason": "real PID kill is not approved by this manifest; use service-scoped restart with health checks and explicit operator confirmation",
            },
            {
                "action_type": "disable_service",
                "status": "blocked_not_generated",
                "reason": "disabling services is outside crash-recovery scope and requires a separate change-control manifest",
            },
            {
                "action_type": "delete_logs_or_reports",
                "status": "blocked_not_generated",
                "reason": "recovery audit logs and reports must be preserved",
            },
        ],
        "approval": {
            "required": True,
            "approval_phrase": f"APPROVE-RECOVERY {manifest_id}",
            "execution_allowed_by_this_tool": False,
            "approval_scope": "proposal only; a separate executor must re-check all preconditions immediately before any service action",
            "future_execution_requirements": [
                "accept only this manifest_id and exact action_id list",
                "capture preflight health, queue depth, and latency immediately before the first action",
                "execute at most one service restart at a time",
                "write execution_manifest.json and rollback_manifest.json",
                "stop on first failed post-check and require a new operator decision",
            ],
        },
        "audit": {
            "source_files_modified": False,
            "real_model_service_modified": False,
            "real_service_restart_performed": False,
            "real_service_kill_performed": False,
            "systemd_mutation_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON recovery approval manifest only",
        },
    }
    manifest["manifest_sha256"] = hash_payload(manifest)
    payload = {
        **manifest,
        "verdict": "ok_ai_nas_model_service_recovery_manifest",
    }

    run_dir = ensure_report_dir(args.report_root, "model_service_recovery_manifest")
    json_path = run_dir / "model_service_recovery_manifest.json"
    md_path = run_dir / "model_service_recovery_manifest.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Model Service Recovery Manifest",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- manifest_id: `{manifest_id}`",
        f"- manifest_sha256: `{payload['manifest_sha256']}`",
        f"- approval_phrase: `{payload['approval']['approval_phrase']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- recovery_slo_seconds: `{args.recovery_slo_seconds}`",
        "- policy: read-only manifest only; no service restart, no kill, no systemd mutation",
        "",
        "## Preflight Snapshot",
        "",
        f"- health_ok_count: `{payload['preflight_snapshot']['health_ok_count']}`",
        f"- systemctl_active_count: `{payload['preflight_snapshot']['systemctl_active_count']}`",
        f"- restart_policy_count: `{payload['preflight_snapshot']['restart_policy_count']}`",
        "",
        "## Proposed Actions",
        "",
    ]
    for action in actions:
        lines.append(
            f"- `{action['action_id']}` phase `{action['phase']}` type `{action['action_type']}` "
            f"service `{action.get('service')}` scope `{action.get('systemd_scope')}` "
            f"command `{' '.join(action.get('candidate_command') or [])}` confirmation `{action['requires_human_confirmation']}`"
        )
    lines.extend(["", "## Blocked Actions", ""])
    for action in payload["blocked_actions"]:
        lines.append(f"- `{action['action_type']}`: {action['reason']}")
    lines.extend(["", "## Approval Contract", ""])
    for key, value in payload["approval"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
