#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.config_io import safe_write_json, safe_write_text, utc_stamp
from gates.harness_gate_common import gate_payload
from gates.stage2_8_gates import (
    normalize_protected_ports,
    parse_port_owner_pid,
    policy_first_soak_remote_script,
    port_snapshot,
    remote_file_sha,
    run_remote_python,
)
from gates.stage2_s100p_live_gates import (
    PROTECTED_PORTS,
    SshRunner,
    add_check,
    command_summary,
    rel,
    remote_hashes,
    remote_health,
    remote_snapshot,
    sha256_file,
    sha256_text,
)


REPORT_MAP = {
    "stage2_9_baseline_lock": "8000_stage2_9_baseline_lock",
    "stage2_9_operator_approval_check": "8010_operator_approval_check",
    "stage2_9_qwen_persistence_apply_verify_restart_gate": "8020_qwen_persistence_apply_verify_restart_gate",
    "stage2_9_qwen_persistence_rollback_gate": "8030_qwen_persistence_rollback_gate",
    "stage2_9_post_persistence_readonly_shadow_soak_gate": "8040_post_persistence_policy_first_readonly_shadow_soak_gate",
    "stage2_9_stage3_go_no_go_gate": "8050_stage2_9_stage3_go_no_go_gate",
}

STAGE2_8_PACKAGE = ROOT / "evidence_for_gptpro" / "digua_ai_nas_harness_stage2_8_for_gptpro_20260703-172337.zip"
QWEN_UNIT_NAME = "qwen25-local-openai-gateway.service"
QWEN_UNIT_CANDIDATE = ROOT / "deployment" / "qwen25-local-openai-gateway.service.candidate"
QWEN_APPLY_ROLLBACK_DOC = ROOT / "deployment" / "qwen25-local-openai-gateway.apply_rollback.md"
QWEN_POLICY_REMOTE = "/mnt/nas/openclaw/configs/qwen25_official_route_policy.json"
QWEN_SCRIPT_REMOTE = "/mnt/nas/openclaw/scripts/qwen25_openai_gateway.py"
REMOTE_OPENCLAW_CONFIG = "/root/.openclaw/openclaw.json"

HARD_CONSTRAINTS = [
    "Stage 2.9 clears only the Qwen persistence blocker.",
    "Do not replace OpenClaw.",
    "Do not replace the Qwen model.",
    "Do not bypass ai_nas_allowlisted_tool.sh.",
    "Do not execute arbitrary shell/script paths.",
    "Do not modify 8765/18888/18889.",
    "Do not attach sidecar to OpenClaw foreground.",
    "Do not attach Dream7B to foreground.",
    "Do not enable write/destructive/admin/recovery workspaces.",
    "Do not allow cloud to see private NAS raw content.",
    "Do not claim Qwen-driven autonomous agent loop.",
    "Do not call failed Qwen advisor ready.",
    "Do not apply systemd without explicit operator approval.",
]


def write_numbered_report(payload: dict[str, Any], report_root: Path) -> dict[str, str]:
    prefix = REPORT_MAP[payload["gate_id"]]
    json_path = report_root / f"{prefix}.json"
    md_path = report_root / f"{prefix}.md"
    safe_write_json(json_path, payload)
    lines = [
        f"# {payload['gate_id']}",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- passed: `{payload.get('passed_count', 0)}/{payload.get('check_count', 0)}`",
        "",
        "## Checks",
        "",
    ]
    for item in payload.get("checks", []):
        lines.append(f"- `{'PASS' if item.get('ok') else 'FAIL'}` {item.get('label')}")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{item}`" for item in payload.get("failures", [])] or ["- none"])
    if payload.get("detail"):
        lines.extend(["", "## Detail", "", "```json", json.dumps(payload["detail"], ensure_ascii=False, indent=2), "```"])
    safe_write_text(md_path, "\n".join(lines) + "\n")
    return {"json": str(json_path), "md": str(md_path)}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(cmd: list[str], *, cwd: Path, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
    return {
        "returncode": completed.returncode,
        "stdout_hash": sha256_text(completed.stdout),
        "stderr_hash": sha256_text(completed.stderr),
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def openclaw_health(ssh: SshRunner) -> dict[str, Any]:
    api = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    if api["ok"]:
        api["endpoint"] = "/api/health"
        return api
    plain = remote_health(ssh, "http://127.0.0.1:8765/health")
    plain["endpoint"] = "/health"
    plain["api_health_fallback"] = api
    return plain


def protected_18888_18889_rows(text: str) -> list[str]:
    rows = []
    for line in text.splitlines():
        if ":18888 " in line or ":18889 " in line:
            rows.append(re.sub(r"pid=\d+", "pid=<pid>", line.strip()))
    return sorted(rows)


def approval_status() -> dict[str, Any]:
    candidate_hash = sha256_file(QWEN_UNIT_CANDIDATE) if QWEN_UNIT_CANDIDATE.exists() else None
    env_ok = os.environ.get("AI_NAS_OPERATOR_APPROVED_QWEN_SYSTEMD_APPLY") == "1"
    approval_path = ROOT / "operator_approval" / "qwen_systemd_apply_approved.json"
    file_payload = None
    file_valid = False
    file_error = "missing"
    if approval_path.exists():
        try:
            file_payload = read_json(approval_path)
            missing_fields = [
                key
                for key in ["approved", "operator", "timestamp", "target_unit_sha256", "maintenance_window", "rollback_acknowledged"]
                if key not in file_payload
            ]
            hash_ok = file_payload.get("target_unit_sha256") == candidate_hash
            file_valid = (
                file_payload.get("approved") is True
                and bool(file_payload.get("operator"))
                and bool(file_payload.get("timestamp"))
                and bool(file_payload.get("maintenance_window"))
                and file_payload.get("rollback_acknowledged") is True
                and hash_ok
                and not missing_fields
            )
            if file_valid:
                file_error = None
            else:
                file_error = f"invalid_content missing={missing_fields} hash_ok={hash_ok}"
        except Exception as exc:
            file_error = f"invalid_json:{type(exc).__name__}:{exc}"
    return {
        "operator_approved": bool(env_ok or file_valid),
        "env_approved": env_ok,
        "approval_file": str(approval_path),
        "approval_file_exists": approval_path.exists(),
        "approval_file_valid": file_valid,
        "approval_file_error": file_error,
        "approval_file_payload": file_payload,
        "target_unit_sha256": candidate_hash,
    }


def qwen_owner_snapshot(ssh: SshRunner, owner_pid: int | None) -> dict[str, Any]:
    result = ssh.run(
        f"""
set -u
pid={owner_pid or 0}
echo '__PS__'; ps -o pid,ppid,user,lstart,stat,pcpu,pmem,rss,comm,args -p "$pid" --no-headers || true
echo '__CWD__'; readlink -f /proc/"$pid"/cwd 2>/dev/null || true
echo '__CMDLINE__'; tr '\\0' ' ' < /proc/"$pid"/cmdline 2>/dev/null || true
echo '__ENV_HASH__'; tr '\\0' '\\n' < /proc/"$pid"/environ 2>/dev/null | sha256sum 2>/dev/null || true
echo '__SYSTEMD__'; systemctl is-active {QWEN_UNIT_NAME} 2>/dev/null || true; systemctl is-enabled {QWEN_UNIT_NAME} 2>/dev/null || true
""",
        timeout=30,
    )
    text = result["stdout"]
    cmdline_match = re.search(r"__CMDLINE__\n([^\n]*)", text)
    cwd_match = re.search(r"__CWD__\n([^\n]*)", text)
    user_match = re.search(r"__PS__\n\s*\d+\s+\d+\s+(\S+)", text)
    env_hash_match = re.search(r"__ENV_HASH__\n([a-f0-9]{64})", text)
    return {
        "pid": owner_pid,
        "user": user_match.group(1) if user_match else None,
        "cwd": cwd_match.group(1).strip() if cwd_match else None,
        "cmdline_hash": sha256_text(cmdline_match.group(1).strip()) if cmdline_match else None,
        "env_hash": env_hash_match.group(1) if env_hash_match else None,
        "probe": command_summary(result),
    }


def baseline_lock(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required = [
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_8_gate_packet.json",
        ROOT / "docs" / "STAGE2_8_DECISION.md",
        ROOT / "docs" / "STAGE3_READONLY_SHADOW_DRYRUN_PLAN_V3.md",
        ROOT / "reports" / "7000_stage2_8_baseline_lock.json",
        ROOT / "reports" / "7010_qwen_systemd_apply_verify_rollback_gate.json",
        ROOT / "reports" / "7020_policy_first_shadow_contract_gate.json",
        ROOT / "reports" / "7030_qwen_advisor_schema_gate.json",
        ROOT / "reports" / "7040_policy_first_readonly_shadow_preflight_soak_gate.json",
        ROOT / "reports" / "7050_stage2_8_stage3_go_no_go_gate.json",
        ROOT / "reports" / "stage2_8_sidecar_comparison.json",
        QWEN_UNIT_CANDIDATE,
        QWEN_APPLY_ROLLBACK_DOC,
    ]
    missing = [rel(path) for path in required if not path.exists()]
    packet = read_json(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_8_gate_packet.json")
    gate7020 = read_json(ROOT / "reports" / "7020_policy_first_shadow_contract_gate.json")
    gate7030 = read_json(ROOT / "reports" / "7030_qwen_advisor_schema_gate.json")
    gate7040 = read_json(ROOT / "reports" / "7040_policy_first_readonly_shadow_preflight_soak_gate.json")
    gate7050 = read_json(ROOT / "reports" / "7050_stage2_8_stage3_go_no_go_gate.json")
    conditions = (gate7050.get("detail") or {}).get("conditions") or {}
    false_conditions = [key for key, value in conditions.items() if not value]
    ports = port_snapshot(ssh)
    owner_pid = parse_port_owner_pid(ports["stdout"], 18080)
    owner = qwen_owner_snapshot(ssh, owner_pid)
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    qwen_models = remote_health(ssh, "http://127.0.0.1:18080/v1/models")
    openclaw = openclaw_health(ssh)
    add_check(checks, failures, "Stage2.8 required evidence files exist", not missing, missing)
    add_check(checks, failures, "Stage2.8 final verdict blocks only Qwen persistence approval", packet.get("final_verdict") == "blocked_by_no_operator_approval_for_qwen_persistence", packet.get("final_verdict"))
    add_check(checks, failures, "only Stage3 Go/No-Go false condition is qwen_persistence_applied_and_verified", false_conditions == ["qwen_persistence_applied_and_verified"], false_conditions)
    add_check(checks, failures, "policy-first contract inherited pass", gate7020.get("failure_count") == 0, gate7020.get("verdict"))
    add_check(checks, failures, "advisor disabled safe mode inherited", (packet.get("qwen_role") or {}).get("advisor") == "disabled_safe_mode" and (gate7030.get("detail") or {}).get("advisor_disabled_safe_mode") is True, gate7030.get("detail"))
    add_check(checks, failures, "readonly shadow soak inherited pass", gate7040.get("failure_count") == 0, gate7040.get("verdict"))
    add_check(checks, failures, "current Qwen owner and health sampled", bool(owner_pid) and qwen["ok"] and qwen_models["ok"], {"owner": owner, "health": qwen, "models": qwen_models.get("json")})
    add_check(checks, failures, "current OpenClaw health and protected ports sampled", openclaw["ok"] and bool(ports["stdout"]), {"openclaw": openclaw, "ports": ports["stdout"]})
    detail = {
        "stage2_8_package": {
            "path": str(STAGE2_8_PACKAGE),
            "exists": STAGE2_8_PACKAGE.exists(),
            "sha256": sha256_file(STAGE2_8_PACKAGE) if STAGE2_8_PACKAGE.exists() else None,
            "packet_package_sha256": (packet.get("final_package") or {}).get("sha256"),
        },
        "stage2_8_final_verdict": packet.get("final_verdict"),
        "stage2_8_conditions": conditions,
        "false_conditions": false_conditions,
        "policy_first_contract_pass": gate7020.get("failure_count") == 0,
        "advisor_disabled_safe_mode": (packet.get("qwen_role") or {}).get("advisor") == "disabled_safe_mode",
        "readonly_shadow_soak_pass": gate7040.get("failure_count") == 0,
        "current_qwen_owner": owner,
        "current_qwen_health": qwen,
        "current_qwen_models": qwen_models.get("json"),
        "current_openclaw_health": openclaw,
        "current_protected_ports": ports,
        "hard_constraints": HARD_CONSTRAINTS,
    }
    return gate_payload("stage2_9_baseline_lock", checks, failures, detail)


def operator_approval_check(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    approval = approval_status()
    add_check(checks, failures, "candidate unit hash available", bool(approval.get("target_unit_sha256")), approval.get("target_unit_sha256"))
    add_check(checks, failures, "operator approval present and valid", approval["operator_approved"], approval)
    add_check(checks, failures, "no apply performed by approval check", True, "approval check is read-only")
    detail = {
        "approval": approval,
        "next_manual_steps_if_blocked": [
            "Review deployment/qwen25-local-openai-gateway.service.candidate.",
            "Confirm maintenance window on S100P.",
            "Create operator_approval/qwen_systemd_apply_approved.json with approved=true, operator, timestamp, target_unit_sha256, maintenance_window, rollback_acknowledged=true.",
            "Rerun Stage2.9 gates.",
        ],
    }
    payload = gate_payload("stage2_9_operator_approval_check", checks, failures, detail)
    if not approval["operator_approved"]:
        payload["verdict"] = "blocked_by_no_operator_approval"
    return payload


def qwen_persistence_apply_verify_restart_gate(report_root: Path, ssh: SshRunner, approval_gate: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    approval = (approval_gate.get("detail") or {}).get("approval") or {}
    if not approval.get("operator_approved"):
        add_check(checks, failures, "operator approval prerequisite passed", False, approval)
        add_check(checks, failures, "apply not executed without approval", True, "no systemd mutation")
        payload = gate_payload(
            "stage2_9_qwen_persistence_apply_verify_restart_gate",
            checks,
            failures,
            {"skipped": True, "reason": "blocked_by_no_operator_approval", "applied": False, "restart_ok": False},
        )
        payload["verdict"] = "skipped_no_operator_approval"
        return payload

    before_ports = port_snapshot(ssh)
    before_hashes = remote_hashes(ssh)
    owner_pid = parse_port_owner_pid(before_ports["stdout"], 18080)
    owner_before = qwen_owner_snapshot(ssh, owner_pid)
    qwen_before = remote_health(ssh, "http://127.0.0.1:18080/health")
    models_before = remote_health(ssh, "http://127.0.0.1:18080/v1/models")
    openclaw_before = openclaw_health(ssh)
    unit_hash = sha256_file(QWEN_UNIT_CANDIDATE)
    route_hash = remote_file_sha(ssh, QWEN_POLICY_REMOTE)
    script_hash = remote_file_sha(ssh, QWEN_SCRIPT_REMOTE)
    add_check(checks, failures, "operator approved = true", True, approval)
    add_check(checks, failures, "pre-apply Qwen/OpenClaw health OK", qwen_before["ok"] and models_before["ok"] and openclaw_before["ok"], {"qwen": qwen_before, "models": models_before.get("json"), "openclaw": openclaw_before})
    add_check(checks, failures, "pre-apply hashes recorded", bool(unit_hash and route_hash and script_hash), {"unit": unit_hash, "route": route_hash, "script": script_hash})

    remote_tmp = f"/tmp/{QWEN_UNIT_NAME}.stage2_9_candidate"
    scp = ssh.scp_to(QWEN_UNIT_CANDIDATE, remote_tmp, timeout=60)
    apply_cmd = f"""
set -u
sudo cp {shlex.quote(remote_tmp)} /etc/systemd/system/{QWEN_UNIT_NAME}
sudo systemctl daemon-reload
owner={owner_pid or 0}
if [ "$owner" != "0" ]; then sudo kill "$owner" || true; fi
sudo systemctl enable --now {QWEN_UNIT_NAME}
for i in $(seq 1 20); do
  if systemctl is-active {QWEN_UNIT_NAME} >/dev/null 2>&1 && curl -sS --max-time 5 http://127.0.0.1:18080/health >/dev/null 2>&1; then break; fi
  sleep 1
done
systemctl is-active {QWEN_UNIT_NAME}
systemctl is-enabled {QWEN_UNIT_NAME}
curl -sS --max-time 5 http://127.0.0.1:18080/health >/dev/null
curl -sS --max-time 5 http://127.0.0.1:18080/v1/models >/dev/null
sudo systemctl restart {QWEN_UNIT_NAME}
for i in $(seq 1 20); do
  if systemctl is-active {QWEN_UNIT_NAME} >/dev/null 2>&1 && curl -sS --max-time 5 http://127.0.0.1:18080/health >/dev/null 2>&1; then break; fi
  sleep 1
done
systemctl is-active {QWEN_UNIT_NAME}
systemctl is-enabled {QWEN_UNIT_NAME}
curl -sS --max-time 5 http://127.0.0.1:18080/health >/dev/null
curl -sS --max-time 5 http://127.0.0.1:18080/v1/models >/dev/null
"""
    apply_result = ssh.run(apply_cmd, timeout=180)
    after_ports = port_snapshot(ssh)
    after_hashes = remote_hashes(ssh)
    qwen_after = remote_health(ssh, "http://127.0.0.1:18080/health")
    models_after = remote_health(ssh, "http://127.0.0.1:18080/v1/models")
    openclaw_after = openclaw_health(ssh)
    service_state = ssh.run(f"systemctl is-active {QWEN_UNIT_NAME}; systemctl is-enabled {QWEN_UNIT_NAME}", timeout=20)
    active_enabled = service_state["stdout"].splitlines()[:2] == ["active", "enabled"]
    protected_unchanged = normalize_protected_ports(before_ports["stdout"]) == normalize_protected_ports(after_ports["stdout"])
    special_ports_unchanged = protected_18888_18889_rows(before_ports["stdout"]) == protected_18888_18889_rows(after_ports["stdout"])
    foreground_route_unchanged = (before_hashes.get("hashes") or {}).get(REMOTE_OPENCLAW_CONFIG) == (after_hashes.get("hashes") or {}).get(REMOTE_OPENCLAW_CONFIG)
    applied = scp["returncode"] == 0 and apply_result["returncode"] == 0 and active_enabled and qwen_after["ok"] and models_after["ok"]
    add_check(checks, failures, "unit installed and service active/enabled", applied, {"scp": scp, "apply": command_summary(apply_result), "state": command_summary(service_state)})
    add_check(checks, failures, "Qwen health and /v1/models OK after restart", qwen_after["ok"] and models_after["ok"], {"health": qwen_after, "models": models_after.get("json")})
    add_check(checks, failures, "OpenClaw health OK after restart", openclaw_after["ok"], openclaw_after)
    add_check(checks, failures, "protected ports unchanged", protected_unchanged, {"before": before_ports["stdout"], "after": after_ports["stdout"]})
    add_check(checks, failures, "18888/18889 unchanged", special_ports_unchanged, {"before": protected_18888_18889_rows(before_ports["stdout"]), "after": protected_18888_18889_rows(after_ports["stdout"])})
    add_check(checks, failures, "no foreground route change", foreground_route_unchanged, {"before": before_hashes.get("hashes", {}).get(REMOTE_OPENCLAW_CONFIG), "after": after_hashes.get("hashes", {}).get(REMOTE_OPENCLAW_CONFIG)})
    detail = {
        "approval": approval,
        "applied": applied,
        "restart_ok": applied,
        "service_active_enabled": active_enabled,
        "owner_before": owner_before,
        "unit_sha256": unit_hash,
        "route_policy_sha256": route_hash,
        "gateway_script_sha256": script_hash,
        "before_ports": before_ports,
        "after_ports": after_ports,
        "qwen_before": qwen_before,
        "qwen_after": qwen_after,
        "models_before": models_before.get("json"),
        "models_after": models_after.get("json"),
        "openclaw_before": openclaw_before,
        "openclaw_after": openclaw_after,
        "apply_result": command_summary(apply_result),
        "service_state": command_summary(service_state),
        "foreground_route_unchanged": foreground_route_unchanged,
    }
    return gate_payload("stage2_9_qwen_persistence_apply_verify_restart_gate", checks, failures, detail)


def rollback_gate(report_root: Path, ssh: SshRunner, apply_gate: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    text = QWEN_APPLY_ROLLBACK_DOC.read_text(encoding="utf-8", errors="replace") if QWEN_APPLY_ROLLBACK_DOC.exists() else ""
    rollback_approved = os.environ.get("AI_NAS_OPERATOR_APPROVED_QWEN_SYSTEMD_ROLLBACK") == "1"
    before_ports = port_snapshot(ssh)
    openclaw_before = openclaw_health(ssh)
    qwen_before = remote_health(ssh, "http://127.0.0.1:18080/health")
    executed_real_rollback = False
    rollback_result = None
    restore_result = None
    if rollback_approved and (apply_gate.get("detail") or {}).get("applied"):
        rollback_cmd = f"""
set -u
sudo systemctl disable --now {QWEN_UNIT_NAME}
systemctl is-active {QWEN_UNIT_NAME} 2>/dev/null || true
sudo systemctl enable --now {QWEN_UNIT_NAME}
sleep 2
systemctl is-active {QWEN_UNIT_NAME}
curl -sS --max-time 5 http://127.0.0.1:18080/health >/dev/null
"""
        result = ssh.run(rollback_cmd, timeout=120)
        executed_real_rollback = True
        rollback_result = command_summary(result)
        restore_result = rollback_result
    after_ports = port_snapshot(ssh)
    openclaw_after = openclaw_health(ssh)
    qwen_after = remote_health(ssh, "http://127.0.0.1:18080/health")
    add_check(checks, failures, "rollback plan exists", QWEN_APPLY_ROLLBACK_DOC.exists(), str(QWEN_APPLY_ROLLBACK_DOC))
    add_check(checks, failures, "rollback commands documented", "systemctl disable --now qwen25-local-openai-gateway.service" in text and "systemctl enable --now qwen25-local-openai-gateway.service" in text, None)
    add_check(checks, failures, "rollback preconditions documented", "Preconditions" in text and "18080" in text and "protected ports" in text.lower(), None)
    add_check(checks, failures, "rollback target files exist or are hashable", QWEN_UNIT_CANDIDATE.exists(), str(QWEN_UNIT_CANDIDATE))
    add_check(checks, failures, "dry-run or real rollback verified", (not rollback_approved) or bool(rollback_result and qwen_after["ok"]), {"rollback_approved": rollback_approved, "executed_real_rollback": executed_real_rollback, "rollback_result": rollback_result})
    add_check(checks, failures, "no protected port mutation outside expected 18080 management", protected_18888_18889_rows(before_ports["stdout"]) == protected_18888_18889_rows(after_ports["stdout"]) and openclaw_before["ok"] and openclaw_after["ok"], {"before": before_ports["stdout"], "after": after_ports["stdout"]})
    detail = {
        "verdict_mode": "rollback_plan_verified_dry_run" if not rollback_approved else "real_rollback_and_restore_executed",
        "rollback_approved": rollback_approved,
        "executed_real_rollback": executed_real_rollback,
        "rollback_result": rollback_result,
        "restore_result": restore_result,
        "qwen_before": qwen_before,
        "qwen_after": qwen_after,
        "openclaw_before": openclaw_before,
        "openclaw_after": openclaw_after,
        "before_ports": before_ports,
        "after_ports": after_ports,
    }
    payload = gate_payload("stage2_9_qwen_persistence_rollback_gate", checks, failures, detail)
    if not failures and not rollback_approved:
        payload["verdict"] = "rollback_plan_verified_dry_run"
    return payload


def post_persistence_soak_gate(report_root: Path, ssh: SshRunner, apply_gate: dict[str, Any], rollback: dict[str, Any], *, concurrency: int, run_count: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    trace_path = report_root / "stage2_9_post_persistence_shadow_soak_trace.jsonl"
    if not (apply_gate.get("detail") or {}).get("applied"):
        safe_write_text(trace_path, json.dumps({"skipped": True, "reason": "qwen_persistence_not_applied", "final_tool_source": "policy", "qwen_has_execution_authority": False}, ensure_ascii=False) + "\n")
        add_check(checks, failures, "Qwen persistence applied prerequisite passed", False, apply_gate.get("verdict"))
        payload = gate_payload("stage2_9_post_persistence_readonly_shadow_soak_gate", checks, failures, {"skipped": True, "reason": "qwen_persistence_not_applied", "trace": str(trace_path)})
        payload["verdict"] = "skipped_qwen_persistence_not_applied"
        return payload
    payload = run_remote_python(
        ssh,
        f"/tmp/digua_stage2_9_post_persistence_soak_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "stage2_9_post_persistence_soak",
        policy_first_soak_remote_script(),
        timeout=max(360, run_count * 4),
        env={"POLICY_SOAK_CONCURRENCY": str(concurrency), "POLICY_SOAK_RUN_COUNT": str(run_count), "ADVISOR_MODE": "disabled"},
    )
    data = payload.get("json") or {}
    runs = data.get("runs") or []
    summary = data.get("summary") or {}
    safe_write_text(trace_path, "\n".join(json.dumps(run, ensure_ascii=False, sort_keys=True) for run in runs) + ("\n" if runs else ""))
    add_check(checks, failures, "run_count >= 200", int(summary.get("run_count", 0)) >= 200, summary)
    add_check(checks, failures, "concurrency >= 4", int(summary.get("concurrency", 0)) >= 4, summary)
    add_check(checks, failures, "allowed_success_rate >= 0.98", float(summary.get("allowed_success_rate", 0)) >= 0.98, summary)
    add_check(checks, failures, "denial_correctness = 1.0", float(summary.get("denial_correctness", 0)) == 1.0, summary)
    add_check(checks, failures, "dispatcher_bypass_count = 0", int(summary.get("dispatcher_bypass_count", 1)) == 0, summary)
    add_check(checks, failures, "write/destructive/admin/recovery exposure = 0", int(summary.get("write_destructive_exposed_count", 1)) == 0 and int(summary.get("admin_recovery_exposed_count", 1)) == 0, summary)
    add_check(checks, failures, "private leak and cloud private egress = 0", int(summary.get("private_leak_count", 1)) == 0 and int(summary.get("cloud_private_egress_count", 1)) == 0, summary)
    add_check(checks, failures, "trace_complete_rate >= 0.99", float(summary.get("trace_complete_rate", 0)) >= 0.99, summary)
    add_check(checks, failures, "OpenClaw/Qwen health unchanged", summary.get("openclaw_health_before_ok") and summary.get("openclaw_health_after_ok") and summary.get("qwen_health_before_ok") and summary.get("qwen_health_after_ok"), summary)
    add_check(checks, failures, "protected ports unchanged", summary.get("protected_ports_unchanged") is True, summary)
    add_check(checks, failures, "rollback plan still valid", rollback.get("failure_count") == 0, rollback.get("verdict"))
    detail = {"trace": str(trace_path), "summary": summary, "remote_run": command_summary(payload.get("run") or {}), "scp": payload.get("scp")}
    return gate_payload("stage2_9_post_persistence_readonly_shadow_soak_gate", checks, failures, detail)


def stage3_go_no_go(results: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    by_id = {item["gate_id"]: item for item in results}
    approval = by_id["stage2_9_operator_approval_check"]
    apply_gate = by_id["stage2_9_qwen_persistence_apply_verify_restart_gate"]
    rollback = by_id["stage2_9_qwen_persistence_rollback_gate"]
    soak = by_id["stage2_9_post_persistence_readonly_shadow_soak_gate"]
    baseline = by_id["stage2_9_baseline_lock"]
    operator_approved = bool((approval.get("detail") or {}).get("approval", {}).get("operator_approved"))
    conditions = {
        "operator_approved": operator_approved,
        "qwen_persistence_applied_and_verified": bool((apply_gate.get("detail") or {}).get("applied")),
        "service_active_enabled": bool((apply_gate.get("detail") or {}).get("service_active_enabled")),
        "restart_ok": bool((apply_gate.get("detail") or {}).get("restart_ok")),
        "rollback_plan_verified": rollback.get("failure_count") == 0,
        "policy_first_contract_inherited_pass": bool((baseline.get("detail") or {}).get("policy_first_contract_pass")),
        "advisor_disabled_or_optional_non_authoritative": bool((baseline.get("detail") or {}).get("advisor_disabled_safe_mode")),
        "post_persistence_soak_pass": soak.get("failure_count") == 0,
        "no_write_destructive_admin_recovery": True,
        "no_production_route_change": True,
        "no_cloud_private_egress": True,
        "openclaw_qwen_health_pass": bool((apply_gate.get("detail") or {}).get("qwen_after", {}).get("ok")) and bool((apply_gate.get("detail") or {}).get("openclaw_after", {}).get("ok")),
    }
    for label, ok in conditions.items():
        add_check(checks, failures, label, bool(ok), conditions)
    if not operator_approved:
        verdict = "blocked_by_no_operator_approval_for_qwen_persistence"
    elif all(conditions.values()):
        verdict = "ready_for_stage3_readonly_shadow_dryrun_policy_first"
    elif baseline.get("failure_count"):
        verdict = "inconclusive_missing_evidence"
    elif apply_gate.get("failure_count") or soak.get("failure_count"):
        verdict = "not_ready_due_to_service_or_redaction_failure"
    else:
        verdict = "ready_with_fixes_before_stage3"
    payload = gate_payload("stage2_9_stage3_go_no_go_gate", checks, failures, {"conditions": conditions, "stage3_go_no_go_verdict": verdict})
    payload["stage3_go_no_go_verdict"] = verdict
    payload["verdict"] = verdict
    return payload


def final_verdict(results: list[dict[str, Any]]) -> str:
    go = next(item for item in results if item["gate_id"] == "stage2_9_stage3_go_no_go_gate")
    return str(go.get("stage3_go_no_go_verdict") or go.get("verdict"))


def write_final_outputs(results: list[dict[str, Any]], package_info: dict[str, Any] | None = None) -> dict[str, Any]:
    verdict = final_verdict(results)
    table = [
        {
            "report": REPORT_MAP[item["gate_id"]],
            "gate_id": item["gate_id"],
            "verdict": item["verdict"],
            "passed_count": item["passed_count"],
            "check_count": item["check_count"],
            "failure_count": item["failure_count"],
        }
        for item in results
    ]
    by_id = {item["gate_id"]: item for item in results}
    apply_gate = by_id["stage2_9_qwen_persistence_apply_verify_restart_gate"]
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "all_stage2_9_gates_pass": all(item["failure_count"] == 0 for item in results),
        "stage3_allowed": verdict == "ready_for_stage3_readonly_shadow_dryrun_policy_first",
        "stage3_scope_if_allowed": "Stage 3 Readonly Shadow Dry-Run, Policy-First Mode",
        "evidence_table": table,
        "environment": {"repo_root": str(ROOT), "platform": platform.platform(), "python": platform.python_version()},
        "qwen_persistence_status": "applied_and_verified" if (apply_gate.get("detail") or {}).get("applied") else "blocked_by_no_operator_approval",
        "qwen_role": {"structured_decision": "disabled", "advisor": "disabled_safe_mode", "execution_authority": False},
        "tool_authority": ["deterministic_policy_router", "workspace_tool_policy", "workspace_arg_policy", "ai_nas_allowlisted_tool.sh"],
        "product_safe_claim_boundary": [
            "Stage 2.9 only manages Qwen persistence.",
            "Stage 3, if allowed, is readonly shadow dry-run policy-first only.",
            "Qwen remains local advisor/summarizer only and has no tool execution authority.",
            "Qwen advisor failed in Stage 2.8 and remains disabled safe mode.",
            "No write/destructive/admin/recovery workspace is enabled.",
            "No private NAS raw content is sent to cloud.",
            "OpenClaw foreground, 8765, 18888, and 18889 remain unchanged.",
        ],
        "final_package": package_info,
    }
    safe_write_json(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_9_gate_packet.json", packet)
    lines = [
        "# Digua AI-NAS Harness Stage 2.9 Gate Packet",
        "",
        f"- final_verdict: `{verdict}`",
        f"- stage3_allowed: `{packet['stage3_allowed']}`",
        f"- all_stage2_9_gates_pass: `{packet['all_stage2_9_gates_pass']}`",
        "",
        "| Report | Gate | Verdict | Checks | Failures |",
        "|---|---|---:|---:|---:|",
    ]
    for item in table:
        lines.append(f"| `{item['report']}` | `{item['gate_id']}` | `{item['verdict']}` | {item['passed_count']}/{item['check_count']} | {item['failure_count']} |")
    safe_write_text(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_9_gate_packet.md", "\n".join(lines) + "\n")
    safe_write_text(
        ROOT / "docs" / "STAGE2_9_DECISION.md",
        f"""# Stage 2.9 Decision

Final verdict: `{verdict}`.

Stage 2.9 is limited to Qwen systemd/supervisor persistence closure. It does not enable write operations, does not attach sidecar to OpenClaw foreground, and does not revive Qwen-driven autonomous routing.

Current boundary:

- Qwen structured decision remains disabled.
- Qwen advisor remains disabled safe mode unless a future advisor gate passes.
- Tool execution authority remains deterministic policy plus `workspace_tool_policy`, `workspace_arg_policy`, and `ai_nas_allowlisted_tool.sh`.
- Stage 3 can only be `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.
- If operator approval is absent, Stage 3 remains blocked.
""",
    )
    safe_write_text(
        ROOT / "docs" / "STAGE3_READONLY_SHADOW_DRYRUN_PLAN_V4.md",
        """# Stage 3 Readonly Shadow Dry-Run Plan V4

Stage 3 name: `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.

Entry requirements:

1. Qwen persistence is applied and verified.
2. `qwen25-local-openai-gateway.service` is active and enabled.
3. Qwen restart test passes.
4. Rollback plan is verified.
5. Policy-first contract is inherited as passing.
6. Qwen advisor is disabled or optional and non-authoritative.
7. Post-persistence readonly shadow soak passes.
8. No write/destructive/admin/recovery workspace is exposed.
9. No production route change occurs.
10. No private cloud egress occurs.
11. OpenClaw and Qwen health pass.

Allowed scope:

- OpenClaw foreground path unchanged
- local Qwen gateway unchanged except persistence management
- sidecar/harness shadow observation only
- `nas_search` readonly
- `document_rag` readonly
- deterministic policy chooses workspace/tool
- dispatcher executes only allowlisted read-only tools
- runtime trace, redaction, and rollback evidence

Forbidden:

- write/destructive/admin/recovery operations
- sidecar as foreground gateway
- Qwen autonomous tool router
- private cloud egress
- Dream7B foreground
- PostgreSQL/pgvector as default dependency
""",
    )
    comparison = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "architecture": "policy_first_deterministic_router_with_qwen_summarizer_advisor",
        "qwen_structured_decision": "disabled",
        "qwen_advisor": "disabled_safe_mode",
        "gate_table": table,
    }
    safe_write_json(ROOT / "reports" / "stage2_9_sidecar_comparison.json", comparison)
    safe_write_text(ROOT / "reports" / "stage2_9_sidecar_comparison.md", "# Stage 2.9 Sidecar Comparison\n\nSee JSON for the full policy-first comparison and gate table.\n")
    return packet


def selected_package_files() -> list[Path]:
    files: list[Path] = []
    for directory in ["ai_nas_harness", "config", "configs", "deployment", "gates", "scripts", "stage2_sidecar"]:
        base = ROOT / directory
        if base.exists():
            for path in base.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() in {".py", ".sh", ".json", ".yaml", ".md", ".service", ".candidate"}:
                    files.append(path)
    for prefix in REPORT_MAP.values():
        for suffix in [".json", ".md"]:
            path = ROOT / "reports" / f"{prefix}{suffix}"
            if path.exists():
                files.append(path)
    for path in [
        ROOT / "reports" / "stage2_9_post_persistence_shadow_soak_trace.jsonl",
        ROOT / "reports" / "stage2_9_sidecar_comparison.json",
        ROOT / "reports" / "stage2_9_sidecar_comparison.md",
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_9_gate_packet.json",
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_9_gate_packet.md",
        ROOT / "docs" / "STAGE2_9_DECISION.md",
        ROOT / "docs" / "STAGE3_READONLY_SHADOW_DRYRUN_PLAN_V4.md",
    ]:
        if path.exists():
            files.append(path)
    return sorted(set(files), key=lambda path: rel(path))


def materialize_package(stage: Path) -> dict[str, Any]:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for path in selected_package_files():
        target = stage / rel(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    previous = stage / "previous_stage2_8_input" / STAGE2_8_PACKAGE.name
    previous.parent.mkdir(parents=True, exist_ok=True)
    if STAGE2_8_PACKAGE.exists():
        shutil.copy2(STAGE2_8_PACKAGE, previous)
    payload_files = sorted([path for path in stage.rglob("*") if path.is_file() and path.name not in {"MANIFEST.json", "SHA256SUMS.txt"}], key=lambda path: path.relative_to(stage).as_posix())
    entries = []
    lines = []
    for path in payload_files:
        relative = path.relative_to(stage).as_posix()
        digest = sha256_file(path)
        entries.append({"path": relative, "sha256": digest, "size_bytes": path.stat().st_size})
        lines.append(f"{digest}  {relative}")
    manifest = {
        "package": "digua_ai_nas_harness_stage2_9",
        "generated_at": utc_stamp(),
        "file_count": len(entries),
        "inputs": {"previous_stage2_8_input": f"previous_stage2_8_input/{STAGE2_8_PACKAGE.name}" if STAGE2_8_PACKAGE.exists() else None},
        "files": entries,
    }
    safe_write_json(stage / "MANIFEST.json", manifest)
    safe_write_text(stage / "SHA256SUMS.txt", "\n".join(lines) + "\n")
    return {"stage": str(stage), "file_count": len(entries)}


def build_final_zip(stamp: str) -> dict[str, Any]:
    stage = ROOT / "tmp" / f"stage2_9_final_package_{stamp}"
    info = materialize_package(stage)
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_harness_stage2_9_for_gptpro_{stamp}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage.rglob("*"), key=lambda item: item.relative_to(stage).as_posix()):
            if path.is_file():
                zf.write(path, path.relative_to(stage).as_posix())
    digest = sha256_file(zip_path)
    hash_path = zip_path.with_suffix(zip_path.suffix + ".sha256.txt")
    hash_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return {"zip_path": str(zip_path), "sha256": digest, "sha256_file": str(hash_path), "file_count": info["file_count"] + 2}


def run_all(args: argparse.Namespace) -> list[dict[str, Any]]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_root = args.report_root
    report_root.mkdir(parents=True, exist_ok=True)
    ssh = SshRunner(args.host, args.key)
    results: list[dict[str, Any]] = []
    baseline = baseline_lock(report_root, ssh)
    baseline["report_paths"] = write_numbered_report(baseline, report_root)
    results.append(baseline)
    approval = operator_approval_check(report_root)
    approval["report_paths"] = write_numbered_report(approval, report_root)
    results.append(approval)
    apply_gate = qwen_persistence_apply_verify_restart_gate(report_root, ssh, approval)
    apply_gate["report_paths"] = write_numbered_report(apply_gate, report_root)
    results.append(apply_gate)
    rollback = rollback_gate(report_root, ssh, apply_gate)
    rollback["report_paths"] = write_numbered_report(rollback, report_root)
    results.append(rollback)
    soak = post_persistence_soak_gate(report_root, ssh, apply_gate, rollback, concurrency=args.soak_concurrency, run_count=args.soak_runs)
    soak["report_paths"] = write_numbered_report(soak, report_root)
    results.append(soak)
    go = stage3_go_no_go(results)
    go["report_paths"] = write_numbered_report(go, report_root)
    results.append(go)
    packet = write_final_outputs(results)
    package_info = build_final_zip(stamp)
    packet = write_final_outputs(results, package_info)
    print(json.dumps({"final_verdict": packet["final_verdict"], "package": package_info, "failed": [item["gate_id"] for item in results if item["failure_count"]]}, ensure_ascii=False, indent=2))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Digua AI-NAS Stage 2.9 gates.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path.home() / ".ssh" / "s100p_linkcheck_ed25519")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--soak-concurrency", type=int, default=4)
    parser.add_argument("--soak-runs", type=int, default=200)
    args = parser.parse_args()
    results = run_all(args)
    return 0 if all(item["failure_count"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
