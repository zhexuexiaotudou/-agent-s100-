#!/usr/bin/env python3
from __future__ import annotations

import argparse
import configparser
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, safe_write_json, safe_write_text


DEFAULT_SERVICES = [
    "dream7b-bpu-batch-queue.service",
    "dream7b-local-openai-gateway.service",
    "openclaw-gateway.service",
]
DEFAULT_HEALTH_URLS = [
    "http://127.0.0.1:18888/health",
    "http://127.0.0.1:18789/health",
]


def run_command(args: list[str], timeout: int = 5) -> dict:
    exe = shutil.which(args[0])
    if not exe:
        return {"available": False, "ok": False, "error": f"missing_command:{args[0]}"}
    try:
        proc = subprocess.run([exe, *args[1:]], text=True, capture_output=True, timeout=timeout)
    except Exception as exc:
        return {"available": True, "ok": False, "error": f"{type(exc).__name__}:{exc}"}
    return {
        "available": True,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip()[:2000],
        "stderr": proc.stderr.strip()[:2000],
    }


def check_health_url(url: str, timeout: float = 2.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            return {"url": url, "ok": 200 <= response.status < 300, "status": response.status, "body": body[:1000]}
    except urllib.error.HTTPError as exc:
        body = exc.read(1000).decode("utf-8", errors="replace")
        return {"url": url, "ok": False, "status": exc.code, "error": body}
    except Exception as exc:
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}:{exc}"}


def systemctl_service_check(service: str) -> dict:
    user_prefix = ["env", "XDG_RUNTIME_DIR=/run/user/0", "systemctl", "--user"]
    user_active = run_command([*user_prefix, "is-active", service])
    user_enabled = run_command([*user_prefix, "is-enabled", service])
    system_active = run_command(["systemctl", "is-active", service])
    system_enabled = run_command(["systemctl", "is-enabled", service])
    return {
        "service": service,
        "user": {"is_active": user_active, "is_enabled": user_enabled},
        "system": {"is_active": system_active, "is_enabled": system_enabled},
        "is_active": user_active if user_active.get("ok") else system_active,
        "is_enabled": user_enabled if user_enabled.get("ok") else system_enabled,
        "active_scope": "user" if user_active.get("ok") else ("system" if system_active.get("ok") else None),
        "enabled_scope": "user" if user_enabled.get("ok") else ("system" if system_enabled.get("ok") else None),
    }


def parse_unit_file(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    parser = configparser.ConfigParser(strict=False)
    parser.optionxform = str
    text = path.read_text(encoding="utf-8", errors="replace")
    parser.read_string(text)
    service = parser["Service"] if parser.has_section("Service") else {}
    return {
        "path": str(path),
        "exists": True,
        "Restart": service.get("Restart"),
        "RestartSec": service.get("RestartSec"),
        "ExecStart": service.get("ExecStart"),
        "has_restart_policy": bool(service.get("Restart")),
    }


def candidate_unit_paths(repo_root: Path, extra_paths: list[Path]) -> list[Path]:
    paths = [
        repo_root / "dream7b-local-openai-gateway.service",
        repo_root / "configs" / "systemd" / "dream7b-bpu-batch-queue.service",
        repo_root / "configs" / "systemd" / "dream7b-local-openai-gateway.service",
        repo_root / "configs" / "systemd" / "openclaw-gateway.service",
        Path("/root/.config/systemd/user/dream7b-local-openai-gateway.service"),
        Path("/etc/systemd/system/dream7b-bpu-batch-queue.service"),
        Path("/etc/systemd/system/dream7b-local-openai-gateway.service"),
        Path("/etc/systemd/system/openclaw-gateway.service"),
        Path("/root/.config/systemd/user/openclaw-gateway.service"),
    ]
    paths.extend(extra_paths)
    seen = set()
    result = []
    for path in paths:
        text = str(path)
        if text in seen:
            continue
        seen.add(text)
        result.append(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only model-service resilience and crash-recovery preflight.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--health-url", action="append", default=[])
    parser.add_argument("--service", action="append", default=[])
    parser.add_argument("--unit-file", action="append", type=Path, default=[])
    args = parser.parse_args()

    resolved_script = Path(__file__).resolve()
    repo_root = resolved_script.parents[2] if len(resolved_script.parents) > 2 else resolved_script.parent
    services = args.service or DEFAULT_SERVICES
    health_urls = args.health_url or DEFAULT_HEALTH_URLS
    systemctl_checks = [systemctl_service_check(service) for service in services]
    default_status = run_command(["dream7b-default-status"])
    health = [check_health_url(url) for url in health_urls]
    unit_files = [parse_unit_file(path) for path in candidate_unit_paths(repo_root, args.unit_file)]

    restart_policy_count = sum(1 for item in unit_files if item.get("has_restart_policy"))
    healthy_count = sum(1 for item in health if item.get("ok"))
    active_count = sum(1 for item in systemctl_checks if item["is_active"].get("ok"))
    gaps = []
    if not any(item.get("available") for check in systemctl_checks for item in [check["user"]["is_active"], check["system"]["is_active"]]):
        gaps.append("systemctl not available in this environment; run on S100P for live service state.")
    if restart_policy_count == 0:
        gaps.append("No readable unit file with Restart policy was found from candidate paths.")
    if healthy_count == 0:
        gaps.append("No configured health endpoint responded successfully.")
    if not default_status.get("ok"):
        gaps.append("dream7b-default-status did not run successfully; default-service summary unavailable.")

    payload = {
        "generated_at": iso_now(),
        "verdict": "ok_model_service_resilience_probe" if not gaps else "limited_model_service_resilience_probe",
        "services": services,
        "health": health,
        "systemctl_checks": systemctl_checks,
        "default_status": default_status,
        "unit_files": unit_files,
        "summary": {
            "health_ok_count": healthy_count,
            "systemctl_active_count": active_count,
            "restart_policy_count": restart_policy_count,
            "destructive_recovery_drill_performed": False,
            "restart_performed": False,
            "kill_performed": False,
        },
        "gaps": gaps,
        "recommended_manual_drill": [
            "Confirm low-traffic window and operator approval.",
            "Capture baseline health, queue depth, and P95/P99 latency.",
            "Stop only the gateway service first, verify systemd Restart recovery and health endpoint restoration.",
            "Repeat for the model queue service only after gateway recovery is proven.",
            "Record before/after reports and rollback path in the incident manifest.",
        ],
    }

    run_dir = ensure_report_dir(args.report_root, "model_service_resilience")
    json_path = run_dir / "model_service_resilience.json"
    md_path = run_dir / "model_service_resilience.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Model Service Resilience",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "- policy: read-only preflight; no restart, no kill, no service mutation",
        f"- health_ok_count: `{healthy_count}`",
        f"- systemctl_active_count: `{active_count}`",
        f"- restart_policy_count: `{restart_policy_count}`",
        "",
        "## Health Endpoints",
        "",
    ]
    for item in health:
        lines.append(f"- `{item['url']}` ok `{item.get('ok')}` status `{item.get('status', '')}` error `{item.get('error', '')}`")
    lines.extend(["", "## Systemd Services", ""])
    for check in systemctl_checks:
        lines.append(
            f"- `{check['service']}` active_ok `{check['is_active'].get('ok')}` "
            f"enabled_ok `{check['is_enabled'].get('ok')}` active_scope `{check.get('active_scope')}`"
        )
    lines.extend(["", "## Unit Restart Policies", ""])
    for unit in unit_files:
        if not unit.get("exists"):
            lines.append(f"- `{unit['path']}` missing")
            continue
        lines.append(
            f"- `{unit['path']}` Restart `{unit.get('Restart')}` "
            f"RestartSec `{unit.get('RestartSec')}`"
        )
    lines.extend(["", "## Gaps", ""])
    if not gaps:
        lines.append("- No preflight gap detected.")
    for gap in gaps:
        lines.append(f"- {gap}")
    lines.extend(["", "## Manual Drill", ""])
    for step in payload["recommended_manual_drill"]:
        lines.append(f"- {step}")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
