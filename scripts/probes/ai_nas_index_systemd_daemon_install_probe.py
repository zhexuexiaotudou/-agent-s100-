#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_index_daemon_readiness_probe import DEFAULT_DAEMON_DB_NAME
from ai_nas_model_service_resilience_probe import parse_unit_file, run_command


TOOL_ID = "ai_nas_index_systemd_daemon_install"
DEFAULT_SERVICE = "ai-nas-index-daemon.service"


def systemctl_check(service: str, scope: str) -> dict:
    prefix = ["systemctl", "--user"] if scope == "user" else ["systemctl"]
    return {
        "scope": scope,
        "service": service,
        "is_active": run_command([*prefix, "is-active", service]),
        "is_enabled": run_command([*prefix, "is-enabled", service]),
        "status": run_command([*prefix, "status", service, "--no-pager"], timeout=8),
        "show": run_command(
            [
                *prefix,
                "show",
                service,
                "--property=ActiveState,SubState,UnitFileState,NRestarts,ExecMainPID,ActiveEnterTimestamp",
            ],
            timeout=8,
        ),
    }


def best_scope(checks: list[dict]) -> dict | None:
    for check in checks:
        if check["is_active"].get("ok") and check["is_enabled"].get("ok"):
            return check
    for check in checks:
        if check["is_active"].get("ok"):
            return check
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a production-installed AI-NAS index daemon systemd service.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--scope", choices=["user", "system", "both"], default="both")
    parser.add_argument("--unit-file", action="append", type=Path, default=[])
    parser.add_argument("--min-observed-cycles", type=int, default=3)
    parser.add_argument("--daemon-db-path", type=Path, default=None)
    args = parser.parse_args()

    scopes = ["user", "system"] if args.scope == "both" else [args.scope]
    checks = [systemctl_check(args.service, scope) for scope in scopes]
    selected = best_scope(checks)
    repo_root = Path(__file__).resolve().parents[2]
    unit_candidates = [
        repo_root / "configs" / "systemd" / "ai-nas-index-daemon.service",
        Path("/root/.config/systemd/user/ai-nas-index-daemon.service"),
        Path("/etc/systemd/system/ai-nas-index-daemon.service"),
    ]
    unit_candidates.extend(args.unit_file)
    unit_files = [parse_unit_file(path) for path in unit_candidates]
    daemon_db_path = args.daemon_db_path or (args.report_root / DEFAULT_DAEMON_DB_NAME)
    daemon_state = {"checked": False, "path": str(daemon_db_path)}
    observed_cycles = 0
    if daemon_db_path.exists():
        import sqlite3

        daemon_state["checked"] = True
        try:
            con = sqlite3.connect(daemon_db_path)
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT status, cycle_count, started_at, finished_at FROM daemon_runs ORDER BY id DESC LIMIT 5").fetchall()
            daemon_state["latest_runs"] = [dict(row) for row in rows]
            observed_cycles = max([int(row["cycle_count"] or 0) for row in rows] or [0])
            con.close()
        except Exception as exc:  # pragma: no cover - production runtime dependent
            daemon_state["error"] = f"{type(exc).__name__}:{exc}"
    else:
        daemon_state["missing"] = True

    blockers = []
    if not selected:
        blockers.append("systemd_index_daemon_service_not_active")
    elif not selected["is_enabled"].get("ok"):
        blockers.append("systemd_index_daemon_service_not_enabled")
    if not any(unit.get("has_restart_policy") for unit in unit_files):
        blockers.append("index_daemon_unit_restart_policy_not_verified")
    if observed_cycles < args.min_observed_cycles:
        blockers.append("index_daemon_observed_cycles_below_threshold")
    if not any(check["is_active"].get("available") for check in checks):
        blockers.append("systemctl_not_available")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_index_systemd_daemon_install" if not blockers else "limited_ai_nas_index_systemd_daemon_install",
        "service": args.service,
        "checks": checks,
        "selected_scope": selected["scope"] if selected else None,
        "unit_files": unit_files,
        "daemon_state": daemon_state,
        "summary": {
            "service_active": bool(selected and selected["is_active"].get("ok")),
            "service_enabled": bool(selected and selected["is_enabled"].get("ok")),
            "restart_policy_count": sum(1 for unit in unit_files if unit.get("has_restart_policy")),
            "observed_cycles": observed_cycles,
            "min_observed_cycles": args.min_observed_cycles,
            "blockers": blockers,
        },
        "audit": {
            "source_files_modified": False,
            "service_installed_by_this_probe": False,
            "service_started_by_this_probe": False,
            "systemd_mutation_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON installation verification report only",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "index_systemd_daemon_install")
    json_path = run_dir / "index_systemd_daemon_install.json"
    md_path = run_dir / "index_systemd_daemon_install.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Index Systemd Daemon Install",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- service: `{args.service}`",
        f"- selected_scope: `{payload['selected_scope']}`",
        f"- service_active: `{payload['summary']['service_active']}`",
        f"- service_enabled: `{payload['summary']['service_enabled']}`",
        f"- restart_policy_count: `{payload['summary']['restart_policy_count']}`",
        f"- observed_cycles: `{observed_cycles}`",
        f"- blockers: `{blockers}`",
        "- policy: read-only systemd/status verification; no install, no start, no restart",
        "",
        "## Audit",
        "",
    ]
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
