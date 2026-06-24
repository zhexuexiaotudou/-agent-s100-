#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"


REMOTE_PROBE = r'''
from __future__ import annotations

import json
import glob
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPORTS = __REPORTS__


def run(command, timeout=20):
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def service_state(name, *, root_user=False):
    if root_user:
        command = "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active " + name
    else:
        command = "systemctl is-active " + name
    result = run(command)
    return {
        "name": name,
        "root_user": root_user,
        "active": result["returncode"] == 0 and result["stdout"] == "active",
        "result": result,
    }


def http_json(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {
                "url": url,
                "ok": response.status == 200,
                "status": response.status,
                "json": json.loads(raw),
                "error": "",
            }
    except Exception as exc:
        return {
            "url": url,
            "ok": False,
            "status": 0,
            "json": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def resolve_report_path(spec):
    if isinstance(spec, str) and spec.startswith("LATEST:"):
        pattern = spec[len("LATEST:") :]
        candidates = [Path(item) for item in glob.glob(pattern) if Path(item).is_file()]
        if not candidates:
            return Path(pattern), {
                "path_spec": spec,
                "resolved_latest": False,
                "latest_match_count": 0,
                "latest_error": "no_latest_match",
            }
        latest = sorted(candidates, key=lambda item: (item.stat().st_mtime, str(item)))[-1]
        return latest, {
            "path_spec": spec,
            "resolved_latest": True,
            "latest_match_count": len(candidates),
            "latest_error": "",
        }
    return Path(spec), {
        "path_spec": spec,
        "resolved_latest": False,
        "latest_match_count": None,
        "latest_error": "",
    }


def report_status(report_id, path_spec):
    p, resolution = resolve_report_path(path_spec)
    item = {
        "id": report_id,
        "path": str(p),
        "exists": p.exists(),
        "verdict": None,
        "error": "",
        **resolution,
    }
    if p.exists():
        try:
            with p.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            item["verdict"] = payload.get("verdict")
            if report_id == "capacity_unblock":
                item["commit_headroom_gb"] = (payload.get("current_commit") or {}).get("commit_headroom_gb")
                item["recommended_commit_limit_gb"] = (
                    payload.get("projected_after_closing_large_private_processes") or {}
                ).get("recommended_commit_limit_gb")
            if report_id == "compile_admission":
                item["admitted_count"] = sum(1 for row in payload.get("classifications") or [] if row.get("command_admitted"))
            if report_id == "rollback_report":
                summary = payload.get("summary") or {}
                item["rollback_ready"] = summary.get("rollback_ready")
                item["production_path_unchanged"] = summary.get("production_path_unchanged")
                item["candidate_artifact_present"] = summary.get("candidate_artifact_present")
                item["candidate_manifest_verified"] = summary.get("candidate_manifest_verified")
            if report_id == "route_a_quality_boundary":
                evaluation = payload.get("evaluation") or {}
                fast_path = evaluation.get("fast_path") or {}
                generic = evaluation.get("generic_generation_boundary") or {}
                item["ready_for_demo"] = evaluation.get("ready_for_demo")
                item["fast_path_ready"] = fast_path.get("ready")
                item["fast_path_max_first_content_ms"] = fast_path.get("max_first_content_ms")
                cases = generic.get("cases") or []
                item["generic_case_count"] = len(cases)
                item["generic_elapsed_ms"] = cases[0].get("elapsed_ms") if cases else None
                item["generic_promotion_claim"] = generic.get("promotion_claim")
            if report_id == "capacity_operator_handoff":
                target = payload.get("target") or {}
                audit = payload.get("audit") or {}
                item["target_commit_limit_gb"] = target.get("target_commit_limit_gb")
                item["additional_pagefile_mb"] = target.get("additional_pagefile_mb")
                item["selected_additional_pagefile_name"] = target.get("selected_additional_pagefile_name")
                item["disk_space_ok"] = target.get("disk_space_ok")
                item["system_setting_changed"] = audit.get("system_setting_changed")
            if report_id == "capacity_post_reboot_verifier":
                checks = payload.get("checks") or {}
                observed = payload.get("observed") or {}
                commit = observed.get("commit") or {}
                item["ready"] = payload.get("ready")
                item["expected_pagefile"] = (payload.get("target") or {}).get("expected_pagefile")
                item["pagefile_active_after_reboot"] = checks.get("pagefile_active_after_reboot")
                item["commit_headroom_ready"] = checks.get("commit_headroom_ready")
                item["commit_headroom_gb"] = commit.get("commit_headroom_gb")
                item["no_compile_process"] = checks.get("no_compile_process")
            if report_id == "post_compile_validation_matrix":
                item["compile_allowed_now"] = payload.get("compile_allowed_now")
                item["ready_for_promotion_check"] = payload.get("ready_for_promotion_check")
                item["candidate_id"] = payload.get("candidate_id")
                item["blockers"] = payload.get("blockers")
                item["validation_ready"] = {
                    key: report.get("ready")
                    for key, report in (payload.get("validation_reports") or {}).items()
                }
            if report_id == "safe_compile_handoff":
                item["operator_may_run_compile"] = payload.get("operator_may_run_compile")
                item["candidate_id"] = payload.get("candidate_id")
                item["blockers"] = payload.get("blockers")
                item["advisory_blockers"] = payload.get("advisory_blockers")
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
    return item


compile_processes = run(
    "ps -eo pid,comm,args | grep -E '(oellm|hbdk|compile_dream|Compile-Dream|cmake|ninja|make|gcc|g\\+\\+)' | grep -v grep || true"
)

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "host": run("hostname")["stdout"],
    "services": {
        "dream7b_bpu_batch_queue": service_state("dream7b-bpu-batch-queue.service"),
        "dream7b_local_openai_gateway": service_state("dream7b-local-openai-gateway.service", root_user=True),
        "openclaw_gateway": service_state("openclaw-gateway.service", root_user=True),
    },
    "health": {
        "gateway_18888": http_json("http://127.0.0.1:18888/health"),
        "openclaw_18789": http_json("http://127.0.0.1:18789/health"),
    },
    "compile_processes": {
        "active": bool(compile_processes["stdout"]),
        "ps": compile_processes,
    },
    "reports": {report_id: report_status(report_id, path) for report_id, path in REPORTS.items()},
    "audit": {
        "compile_started": False,
        "runtime_started": False,
        "service_restarted": False,
        "production_write_performed": False,
    },
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
'''


REPORT_PATHS = {
    "fast_path_regression": "/mnt/nas/openclaw/reports/models/dream7b_fast_path_regression_20260622-174547/dream7b_fast_path_regression.json",
    "first_response_slo": "/mnt/nas/openclaw/reports/models/dream7b_first_response_slo_tier_guard_20260622-174823/dream7b_first_response_slo_tier_guard.json",
    "openclaw_entry_demo": "/mnt/nas/openclaw/reports/models/openclaw_entry_demo_20260622-174732/openclaw_entry_demo.json",
    "route_a_demo_readiness": "/mnt/nas/openclaw/reports/models/ai_nas_route_a_demo_readiness_packet_20260622-182319/ai_nas_route_a_demo_readiness_packet.json",
    "route_a_quality_boundary": "/mnt/nas/openclaw/reports/models/dream7b_route_a_quality_boundary_packet_20260622-183931/dream7b_route_a_quality_boundary_packet.json",
    "candidate_gate": "/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_candidate_gate_20260622-180021/dream7b_bpu_quality_candidate_gate.json",
    "candidate_pack": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_candidate_pack_*/dream7b_bpu_quality_candidate_pack.json",
    "rank1_preflight": "/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_preflight_runner_20260622-180415/dream7b_bpu_quality_preflight_runner.json",
    "remaining_preflight": "/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_preflight_runner_20260622-180725/dream7b_bpu_quality_preflight_runner.json",
    "capacity_unblock": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_unblock_plan_*/dream7b_bpu_quality_capacity_unblock_plan.json",
    "compile_admission": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_compile_admission_guard_*/dream7b_bpu_quality_compile_admission_guard.json",
    "capacity_operator_handoff": "/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_operator_handoff_20260622-185400/dream7b_bpu_quality_capacity_operator_handoff.json",
    "capacity_post_reboot_verifier": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_post_reboot_verifier_*/dream7b_bpu_quality_capacity_post_reboot_verifier.json",
    "safe_compile_handoff": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_safe_compile_handoff_*/dream7b_bpu_quality_safe_compile_handoff.json",
    "post_compile_validation_matrix": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_compile_validation_matrix_*/dream7b_bpu_quality_post_compile_validation_matrix.json",
    "rollback_report": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_rollback_report_*/dream7b_bpu_quality_rollback_report.json",
    "promotion_gate": "LATEST:/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_promotion_gate_*/dream7b_bpu_quality_promotion_gate.json",
}


def run_cmd(command: list[str], timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "args": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_command(args: argparse.Namespace, command: str, timeout: int = 90) -> dict[str, Any]:
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
            command,
        ],
        timeout,
    )


def run_remote_probe(args: argparse.Namespace) -> dict[str, Any]:
    source = REMOTE_PROBE.replace("__REPORTS__", json.dumps(REPORT_PATHS, ensure_ascii=False))
    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}').decode('utf-8'))\""
    result = ssh_command(args, command, timeout=args.remote_timeout)
    if result["returncode"] != 0:
        return {"ok": False, "error": "remote_probe_failed", "ssh": result}
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"remote_json_decode_failed:{exc}", "ssh": result}
    payload["ok"] = True
    return payload


def evaluate(remote: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    route_a_errors: list[str] = []
    route_b_errors: list[str] = []
    if not remote.get("ok"):
        errors.append(remote.get("error", "remote_probe_failed"))
    for service_id, service in (remote.get("services") or {}).items():
        if service.get("active") is not True:
            errors.append(f"service_not_active:{service_id}")
            route_a_errors.append(f"service_not_active:{service_id}")
    for health_id, health in (remote.get("health") or {}).items():
        if health.get("ok") is not True:
            errors.append(f"health_not_ok:{health_id}")
            route_a_errors.append(f"health_not_ok:{health_id}")
    for report_id, report in (remote.get("reports") or {}).items():
        if report.get("exists") is not True:
            errors.append(f"report_missing:{report_id}")
        if report.get("error"):
            errors.append(f"report_error:{report_id}:{report.get('error')}")

    reports = remote.get("reports") or {}
    if reports.get("fast_path_regression", {}).get("verdict") != "ok_dream7b_fast_path_regression":
        route_a_errors.append("fast_path_regression_not_ok")
    if reports.get("first_response_slo", {}).get("verdict") != "ok_dream7b_first_response_slo_tier_guard":
        route_a_errors.append("first_response_slo_not_ok")
    if reports.get("openclaw_entry_demo", {}).get("verdict") != "ok_openclaw_entry_demo_probe":
        route_a_errors.append("openclaw_entry_demo_not_ok")
    if reports.get("route_a_demo_readiness", {}).get("verdict") != "ok_ai_nas_route_a_demo_readiness_packet":
        route_a_errors.append("route_a_demo_readiness_not_ok")
    if reports.get("route_a_quality_boundary", {}).get("verdict") != "ok_dream7b_route_a_quality_boundary_packet":
        route_a_errors.append("route_a_quality_boundary_not_ok")
    if reports.get("candidate_gate", {}).get("verdict") != "ok_dream7b_bpu_quality_candidate_gate":
        route_b_errors.append("candidate_gate_not_ok")
    if reports.get("candidate_pack", {}).get("verdict") != "ok_dream7b_bpu_quality_candidate_pack":
        route_b_errors.append("candidate_pack_not_ok")
    if reports.get("remaining_preflight", {}).get("verdict") != "ok_dream7b_bpu_quality_preflight_runner":
        route_b_errors.append("state_dict_preflight_not_ok")
    if reports.get("capacity_unblock", {}).get("verdict") != "ready_dream7b_bpu_quality_capacity_unblock_plan":
        route_b_errors.append("capacity_unblock_not_ready")
    if reports.get("capacity_post_reboot_verifier", {}).get("verdict") != "ready_dream7b_bpu_quality_capacity_post_reboot_verifier":
        route_b_errors.append("capacity_post_reboot_verifier_not_ready")
    if reports.get("safe_compile_handoff", {}).get("operator_may_run_compile") is not True:
        route_b_errors.append("safe_compile_handoff_not_ready")
    if reports.get("post_compile_validation_matrix", {}).get("verdict") != "ready_dream7b_bpu_quality_post_compile_validation_matrix":
        route_b_errors.append("post_compile_validation_matrix_not_ready")
    if (
        reports.get("compile_admission", {}).get("admitted_count") not in (0, None)
        and reports.get("safe_compile_handoff", {}).get("operator_may_run_compile") is not True
    ):
        route_b_errors.append("compile_admission_unexpectedly_admitted_command")
    if reports.get("rollback_report", {}).get("verdict") != "ready_dream7b_bpu_quality_rollback_report":
        route_b_errors.append("rollback_report_not_ready")
    if reports.get("promotion_gate", {}).get("verdict") != "ready_dream7b_bpu_quality_promotion_gate":
        route_b_errors.append("promotion_gate_not_ready")
    if (remote.get("compile_processes") or {}).get("active") is True:
        route_b_errors.append("compile_process_active")
        errors.append("compile_process_active")

    route_a_ready = not route_a_errors
    route_b_ready_for_compile = (
        "candidate_gate_not_ok" not in route_b_errors
        and "candidate_pack_not_ok" not in route_b_errors
        and "state_dict_preflight_not_ok" not in route_b_errors
        and "capacity_unblock_not_ready" not in route_b_errors
        and "capacity_post_reboot_verifier_not_ready" not in route_b_errors
        and "safe_compile_handoff_not_ready" not in route_b_errors
        and "compile_process_active" not in route_b_errors
    )
    route_b_ready_for_promotion = not route_b_errors
    goal_complete = route_a_ready and route_b_ready_for_promotion
    return {
        "verdict": "ready_route_a_blocked_route_b_goal_status" if route_a_ready and not goal_complete else "warning_dream7b_ai_nas_goal_status",
        "errors": errors,
        "route_a": {
            "ready": route_a_ready,
            "errors": route_a_errors,
            "status": "ready_for_demo" if route_a_ready else "needs_attention",
        },
        "route_b": {
            "ready_for_compile": route_b_ready_for_compile,
            "ready_for_promotion": route_b_ready_for_promotion,
            "errors": route_b_errors,
            "status": "candidate_preflight_done_capacity_blocked" if "capacity_unblock_not_ready" in route_b_errors else "needs_attention",
        },
        "goal_complete": goal_complete,
        "remaining_work": [
            "Raise Windows commit/pagefile and rerun capacity/preflight gates.",
            "Compile only rank-1 seg27_28_lmheadq16 last-token sentinel after admission guard passes.",
            "Run logits diagnostics and three-prompt Chinese generation quality checks.",
            "Promote nothing until rollback and same-workload evidence pass.",
        ] if not goal_complete else [],
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    remote = run_remote_probe(args)
    evaluation = evaluate(remote)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": evaluation["verdict"],
        "remote": remote,
        "evaluation": evaluation,
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    evaluation = payload["evaluation"]
    remote = payload["remote"]
    reports = remote.get("reports") or {}
    lines = [
        "# Dream7B AI-NAS Goal Status Packet",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- goal_complete: `{evaluation['goal_complete']}`",
        f"- route_a_status: `{evaluation['route_a']['status']}`",
        f"- route_b_status: `{evaluation['route_b']['status']}`",
        "- compile_started: `False`",
        "- service_restarted: `False`",
        "",
        "## Live Services",
        "",
    ]
    for service_id, service in (remote.get("services") or {}).items():
        lines.append(f"- {service_id}: active=`{service.get('active')}`")
    for health_id, health in (remote.get("health") or {}).items():
        lines.append(f"- {health_id}: ok=`{health.get('ok')}` status=`{health.get('status')}`")
    lines.extend(["", "## Evidence", ""])
    for report_id, report in reports.items():
        extra = ""
        if report_id == "capacity_unblock":
            extra = (
                f", headroom={report.get('commit_headroom_gb')}, "
                f"recommended_commit_limit={report.get('recommended_commit_limit_gb')}"
            )
        if report_id == "compile_admission":
            extra = f", admitted_count={report.get('admitted_count')}"
        if report_id == "rollback_report":
            extra = (
                f", rollback_ready={report.get('rollback_ready')}, "
                f"production_path_unchanged={report.get('production_path_unchanged')}, "
                f"candidate_artifact_present={report.get('candidate_artifact_present')}, "
                f"candidate_manifest_verified={report.get('candidate_manifest_verified')}"
            )
        if report_id == "route_a_quality_boundary":
            extra = (
                f", ready_for_demo={report.get('ready_for_demo')}, "
                f"fast_path_ready={report.get('fast_path_ready')}, "
                f"fast_path_max_first_content_ms={report.get('fast_path_max_first_content_ms')}, "
                f"generic_elapsed_ms={report.get('generic_elapsed_ms')}, "
                f"generic_promotion_claim={report.get('generic_promotion_claim')}"
            )
        if report_id == "capacity_operator_handoff":
            extra = (
                f", target_commit_limit_gb={report.get('target_commit_limit_gb')}, "
                f"additional_pagefile_mb={report.get('additional_pagefile_mb')}, "
                f"selected_additional_pagefile_name={report.get('selected_additional_pagefile_name')}, "
                f"disk_space_ok={report.get('disk_space_ok')}, "
                f"system_setting_changed={report.get('system_setting_changed')}"
            )
        if report_id == "capacity_post_reboot_verifier":
            extra = (
                f", ready={report.get('ready')}, "
                f"expected_pagefile={report.get('expected_pagefile')}, "
                f"pagefile_active_after_reboot={report.get('pagefile_active_after_reboot')}, "
                f"commit_headroom_ready={report.get('commit_headroom_ready')}, "
                f"commit_headroom_gb={report.get('commit_headroom_gb')}, "
                f"no_compile_process={report.get('no_compile_process')}"
            )
        if report_id == "post_compile_validation_matrix":
            extra = (
                f", candidate_id={report.get('candidate_id')}, "
                f"compile_allowed_now={report.get('compile_allowed_now')}, "
                f"ready_for_promotion_check={report.get('ready_for_promotion_check')}, "
                f"validation_ready={report.get('validation_ready')}"
            )
        if report_id == "safe_compile_handoff":
            extra = (
                f", candidate_id={report.get('candidate_id')}, "
                f"operator_may_run_compile={report.get('operator_may_run_compile')}, "
                f"blockers={report.get('blockers')}"
            )
        lines.append(
            f"- {report_id}: exists=`{report.get('exists')}`, verdict=`{report.get('verdict')}`{extra}"
        )
    lines.extend(["", "## Remaining Work", ""])
    if evaluation["remaining_work"]:
        lines.extend(f"- {item}" for item in evaluation["remaining_work"])
    else:
        lines.append("- none")
    lines.extend(["", "## Errors", ""])
    if evaluation["errors"]:
        lines.extend(f"- `{error}`" for error in evaluation["errors"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sync_to_nas(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    remote_dir = f"{args.remote_report_root.rstrip('/')}/{report_dir.name}"
    mkdir = ssh_command(args, f"mkdir -p {remote_dir}", timeout=30)
    if mkdir["returncode"] != 0:
        return {"ok": False, "remote_dir": remote_dir, "mkdir": mkdir}
    scp = run_cmd(
        [
            "scp.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            str(report_dir / "dream7b_ai_nas_goal_status_packet.json"),
            str(report_dir / "dream7b_ai_nas_goal_status_packet.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--remote-timeout", type=int, default=90)
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.out_root) / f"dream7b_ai_nas_goal_status_packet_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_ai_nas_goal_status_packet.json"
    md_path = report_dir / "dream7b_ai_nas_goal_status_packet.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    if not args.no_sync:
        sync = sync_to_nas(args, report_dir)
        payload["sync"] = sync
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(md_path, payload)
        if sync.get("ok") is False:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
    latest_json = Path(args.out_root) / "dream7b_ai_nas_goal_status_packet_latest.json"
    latest_md = Path(args.out_root) / "dream7b_ai_nas_goal_status_packet_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
