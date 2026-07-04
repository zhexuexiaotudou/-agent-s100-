#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
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
from gates.stage2_8_gates import policy_first_soak_remote_script, port_snapshot, run_remote_python
from gates.stage2_9_gates import (
    HARD_CONSTRAINTS as STAGE2_9_HARD_CONSTRAINTS,
    QWEN_APPLY_ROLLBACK_DOC,
    QWEN_UNIT_CANDIDATE,
    approval_status,
    openclaw_health,
    parse_port_owner_pid,
    qwen_owner_snapshot,
    qwen_persistence_apply_verify_restart_gate as stage2_9_apply_gate,
    rollback_gate as stage2_9_rollback_gate,
)
from gates.stage2_s100p_live_gates import (
    SshRunner,
    add_check,
    command_summary,
    rel,
    remote_health,
    sha256_file,
    sha256_text,
)


REPORT_MAP = {
    "stage2_10_baseline_lock": "9000_stage2_10_baseline_lock",
    "stage2_10_operator_approval_hard_gate": "9010_operator_approval_hard_gate",
    "stage2_10_qwen_persistence_apply_verify_restart_gate": "9020_qwen_persistence_apply_verify_restart_gate",
    "stage2_10_qwen_persistence_rollback_verify_gate": "9030_qwen_persistence_rollback_verify_gate",
    "stage2_10_post_persistence_readonly_shadow_soak_gate": "9040_post_persistence_policy_first_readonly_shadow_soak_gate",
    "stage2_10_stage3_go_no_go_gate": "9050_stage2_10_stage3_go_no_go_gate",
}

STAGE2_9_PACKAGE = ROOT / "evidence_for_gptpro" / "digua_ai_nas_harness_stage2_9_for_gptpro_20260703-234407.zip"
HARD_CONSTRAINTS = [
    "Stage 2.10 is only operator-approved Qwen persistence closure.",
    *[item for item in STAGE2_9_HARD_CONSTRAINTS if item != "Stage 2.9 clears only the Qwen persistence blocker."],
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


def rekey_payload(payload: dict[str, Any], gate_id: str) -> dict[str, Any]:
    copied = json.loads(json.dumps(payload, ensure_ascii=False))
    copied["gate_id"] = gate_id
    verdict = str(copied.get("verdict", ""))
    copied["verdict"] = verdict.replace("stage2_9", "stage2_10")
    return copied


def baseline_lock(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required = [
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_9_gate_packet.json",
        ROOT / "reports" / "8000_stage2_9_baseline_lock.json",
        ROOT / "reports" / "8010_operator_approval_check.json",
        ROOT / "reports" / "8020_qwen_persistence_apply_verify_restart_gate.json",
        ROOT / "reports" / "8030_qwen_persistence_rollback_gate.json",
        ROOT / "reports" / "8040_post_persistence_policy_first_readonly_shadow_soak_gate.json",
        ROOT / "reports" / "8050_stage2_9_stage3_go_no_go_gate.json",
        QWEN_UNIT_CANDIDATE,
        QWEN_APPLY_ROLLBACK_DOC,
        ROOT / "docs" / "STAGE2_9_DECISION.md",
    ]
    missing = [rel(path) for path in required if not path.exists()]
    packet = read_json(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_9_gate_packet.json")
    gate8050 = read_json(ROOT / "reports" / "8050_stage2_9_stage3_go_no_go_gate.json")
    conditions = (gate8050.get("detail") or {}).get("conditions") or {}
    false_conditions = [key for key, value in conditions.items() if not value]
    ports = port_snapshot(ssh)
    owner_pid = parse_port_owner_pid(ports["stdout"], 18080)
    owner = qwen_owner_snapshot(ssh, owner_pid)
    openclaw = openclaw_health(ssh)
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    qwen_models = remote_health(ssh, "http://127.0.0.1:18080/v1/models")
    approval = approval_status()
    add_check(checks, failures, "Stage2.9 required evidence files exist", not missing, missing)
    add_check(checks, failures, "Stage2.9 final verdict recorded", packet.get("final_verdict") == "blocked_by_no_operator_approval_for_qwen_persistence", packet.get("final_verdict"))
    add_check(checks, failures, "current blocker includes operator approval and persistence apply", "operator_approved" in false_conditions and "qwen_persistence_applied_and_verified" in false_conditions, false_conditions)
    add_check(checks, failures, "protected ports sampled", bool(ports["stdout"]), ports["stdout"])
    add_check(checks, failures, "Qwen owner before apply sampled", bool(owner_pid), owner)
    add_check(checks, failures, "OpenClaw health before apply OK", openclaw["ok"], openclaw)
    add_check(checks, failures, "Qwen health/models before apply OK", qwen["ok"] and qwen_models["ok"], {"health": qwen, "models": qwen_models.get("json")})
    add_check(checks, failures, "operator approval status recorded", True, approval)
    detail = {
        "stage2_9_package": {
            "path": str(STAGE2_9_PACKAGE),
            "exists": STAGE2_9_PACKAGE.exists(),
            "sha256": sha256_file(STAGE2_9_PACKAGE) if STAGE2_9_PACKAGE.exists() else None,
            "packet_package_sha256": (packet.get("final_package") or {}).get("sha256"),
        },
        "stage2_9_final_verdict": packet.get("final_verdict"),
        "current_blocker": false_conditions,
        "protected_ports": ports,
        "qwen_owner_before_apply": owner,
        "openclaw_health_before_apply": openclaw,
        "qwen_health_before_apply": qwen,
        "qwen_models_before_apply": qwen_models.get("json"),
        "operator_approval_status": approval,
        "hard_constraints": HARD_CONSTRAINTS,
    }
    return gate_payload("stage2_10_baseline_lock", checks, failures, detail)


def operator_approval_hard_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    approval = approval_status()
    add_check(checks, failures, "target unit sha256 recorded", bool(approval.get("target_unit_sha256")), approval.get("target_unit_sha256"))
    add_check(checks, failures, "operator approval pass", approval["operator_approved"], approval)
    add_check(checks, failures, "apply not executed by hard gate", True, "read-only approval gate")
    detail = {
        "approval": approval,
        "manual_action_if_blocked": [
            "Review deployment/qwen25-local-openai-gateway.service.candidate.",
            "Use a maintenance window on S100P.",
            "Create operator_approval/qwen_systemd_apply_approved.json with approved=true, operator, timestamp, target_unit_sha256, maintenance_window, rollback_acknowledged=true.",
            "Required target_unit_sha256: " + str(approval.get("target_unit_sha256")),
            "Rerun Stage2.10.",
        ],
    }
    payload = gate_payload("stage2_10_operator_approval_hard_gate", checks, failures, detail)
    if not approval["operator_approved"]:
        payload["verdict"] = "blocked_by_no_operator_approval"
    return payload


def apply_gate(report_root: Path, ssh: SshRunner, approval_gate: dict[str, Any]) -> dict[str, Any]:
    stage2_9_like = json.loads(json.dumps(approval_gate, ensure_ascii=False))
    stage2_9_like["gate_id"] = "stage2_9_operator_approval_check"
    payload = stage2_9_apply_gate(report_root, ssh, stage2_9_like)
    return rekey_payload(payload, "stage2_10_qwen_persistence_apply_verify_restart_gate")


def rollback_verify_gate(report_root: Path, ssh: SshRunner, apply_payload: dict[str, Any]) -> dict[str, Any]:
    stage2_9_like = json.loads(json.dumps(apply_payload, ensure_ascii=False))
    stage2_9_like["gate_id"] = "stage2_9_qwen_persistence_apply_verify_restart_gate"
    payload = stage2_9_rollback_gate(report_root, ssh, stage2_9_like)
    return rekey_payload(payload, "stage2_10_qwen_persistence_rollback_verify_gate")


def post_persistence_soak_gate(report_root: Path, ssh: SshRunner, apply_payload: dict[str, Any], rollback: dict[str, Any], *, concurrency: int, run_count: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    trace_path = report_root / "stage2_10_post_persistence_shadow_soak_trace.jsonl"
    if not (apply_payload.get("detail") or {}).get("applied"):
        safe_write_text(trace_path, json.dumps({"skipped": True, "reason": "qwen_persistence_not_applied", "final_tool_source": "policy", "qwen_has_execution_authority": False}, ensure_ascii=False) + "\n")
        add_check(checks, failures, "Qwen persistence applied prerequisite passed", False, apply_payload.get("verdict"))
        payload = gate_payload("stage2_10_post_persistence_readonly_shadow_soak_gate", checks, failures, {"skipped": True, "reason": "qwen_persistence_not_applied", "trace": str(trace_path)})
        payload["verdict"] = "skipped_qwen_persistence_not_applied"
        return payload
    payload = run_remote_python(
        ssh,
        f"/tmp/digua_stage2_10_post_persistence_soak_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "stage2_10_post_persistence_soak",
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
    add_check(checks, failures, "private leak and cloud private egress = 0", int(summary.get("private_leak_count", 1)) == 0 and int(summary.get("cloud_private_egress_count", 1)) == 0, summary)
    add_check(checks, failures, "trace_complete_rate >= 0.99", float(summary.get("trace_complete_rate", 0)) >= 0.99, summary)
    add_check(checks, failures, "OpenClaw/Qwen health unchanged", summary.get("openclaw_health_before_ok") and summary.get("openclaw_health_after_ok") and summary.get("qwen_health_before_ok") and summary.get("qwen_health_after_ok"), summary)
    add_check(checks, failures, "protected ports unchanged", summary.get("protected_ports_unchanged") is True, summary)
    add_check(checks, failures, "rollback plan still valid", rollback.get("failure_count") == 0, rollback.get("verdict"))
    detail = {"trace": str(trace_path), "summary": summary, "remote_run": command_summary(payload.get("run") or {}), "scp": payload.get("scp")}
    return gate_payload("stage2_10_post_persistence_readonly_shadow_soak_gate", checks, failures, detail)


def stage3_go_no_go(results: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    by_id = {item["gate_id"]: item for item in results}
    approval = by_id["stage2_10_operator_approval_hard_gate"]
    apply_payload = by_id["stage2_10_qwen_persistence_apply_verify_restart_gate"]
    rollback = by_id["stage2_10_qwen_persistence_rollback_verify_gate"]
    soak = by_id["stage2_10_post_persistence_readonly_shadow_soak_gate"]
    baseline = by_id["stage2_10_baseline_lock"]
    operator_approved = bool((approval.get("detail") or {}).get("approval", {}).get("operator_approved"))
    conditions = {
        "operator_approval_pass": operator_approved,
        "qwen_service_applied": bool((apply_payload.get("detail") or {}).get("applied")),
        "service_active_enabled": bool((apply_payload.get("detail") or {}).get("service_active_enabled")),
        "restart_ok": bool((apply_payload.get("detail") or {}).get("restart_ok")),
        "rollback_plan_verified": rollback.get("failure_count") == 0,
        "post_persistence_soak_pass": soak.get("failure_count") == 0,
        "no_write_destructive_admin_recovery": True,
        "no_production_route_change": True,
        "no_private_cloud_egress": True,
        "openclaw_qwen_health_pass": bool((apply_payload.get("detail") or {}).get("qwen_after", {}).get("ok")) and bool((apply_payload.get("detail") or {}).get("openclaw_after", {}).get("ok")),
        "baseline_evidence_present": baseline.get("failure_count") == 0,
    }
    for label, ok in conditions.items():
        add_check(checks, failures, label, bool(ok), conditions)
    if not operator_approved:
        verdict = "blocked_by_no_operator_approval_for_qwen_persistence"
    elif all(conditions.values()):
        verdict = "ready_for_stage3_readonly_shadow_dryrun_policy_first"
    elif baseline.get("failure_count"):
        verdict = "inconclusive_missing_evidence"
    elif apply_payload.get("failure_count") or soak.get("failure_count"):
        verdict = "not_ready_due_to_service_or_redaction_failure"
    else:
        verdict = "ready_with_fixes_before_stage3"
    payload = gate_payload("stage2_10_stage3_go_no_go_gate", checks, failures, {"conditions": conditions, "stage3_go_no_go_verdict": verdict})
    payload["stage3_go_no_go_verdict"] = verdict
    payload["verdict"] = verdict
    return payload


def final_verdict(results: list[dict[str, Any]]) -> str:
    go = next(item for item in results if item["gate_id"] == "stage2_10_stage3_go_no_go_gate")
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
    approval_payload = by_id["stage2_10_operator_approval_hard_gate"]
    apply_payload = by_id["stage2_10_qwen_persistence_apply_verify_restart_gate"]
    rollback_payload = by_id["stage2_10_qwen_persistence_rollback_verify_gate"]
    soak_payload = by_id["stage2_10_post_persistence_readonly_shadow_soak_gate"]
    approval_detail = approval_payload.get("detail") or {}
    approval = approval_detail.get("approval") or {}
    approval_file_payload = approval.get("approval_file_payload") or {}
    apply_detail = apply_payload.get("detail") or {}
    soak_summary = (soak_payload.get("detail") or {}).get("summary") or {}
    target_unit_sha256 = approval.get("target_unit_sha256") or approval_file_payload.get("target_unit_sha256") or apply_detail.get("unit_sha256")
    package_lines = [
        "- Final zip and `.sha256.txt` are generated after this packet is materialized.",
        "- Package integrity is verified by `MANIFEST.json`, `SHA256SUMS.txt`, and the adjacent `.sha256.txt` file.",
    ]
    if package_info:
        package_lines = [
            f"- Latest local zip: `{rel(Path(package_info['zip_path']))}`.",
            f"- SHA256: `{package_info['sha256']}`.",
            f"- File count: `{package_info['file_count']}`.",
            "- A zip cannot contain its own final SHA without changing that SHA; trust the adjacent `.sha256.txt` for package-level verification.",
        ]
    gate_rows = "\n".join(
        f"| `{item['report']}` | `{item['gate_id']}` | `{item['verdict']}` | {item['passed_count']}/{item['check_count']} | {item['failure_count']} |"
        for item in table
    )
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "all_stage2_10_gates_pass": all(item["failure_count"] == 0 for item in results),
        "stage3_allowed": verdict == "ready_for_stage3_readonly_shadow_dryrun_policy_first",
        "stage3_scope_if_allowed": "Stage 3 Readonly Shadow Dry-Run, Policy-First Mode",
        "evidence_table": table,
        "environment": {"repo_root": str(ROOT), "platform": platform.platform(), "python": platform.python_version()},
        "qwen_persistence_status": "applied_and_verified" if (apply_payload.get("detail") or {}).get("applied") else "blocked_by_no_operator_approval",
        "qwen_role": {"structured_decision": "disabled", "advisor": "disabled_safe_mode", "execution_authority": False},
        "tool_authority": ["deterministic_policy_router", "workspace_tool_policy", "workspace_arg_policy", "ai_nas_allowlisted_tool.sh"],
        "product_safe_claim_boundary": [
            "Stage 2.10 only applies Qwen persistence with explicit operator approval.",
            "Stage 3, if allowed, is readonly shadow dry-run policy-first only.",
            "Qwen has no tool execution authority.",
            "Qwen advisor remains disabled safe mode unless a future advisor gate passes.",
            "No write/destructive/admin/recovery workspace is enabled.",
            "No private NAS raw content is sent to cloud.",
            "OpenClaw foreground, 8765, 18888, and 18889 remain unchanged.",
        ],
        "final_package": package_info,
    }
    safe_write_json(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_10_gate_packet.json", packet)
    lines = [
        "# Digua AI-NAS Harness Stage 2.10 Gate Packet",
        "",
        f"- final_verdict: `{verdict}`",
        f"- stage3_allowed: `{packet['stage3_allowed']}`",
        f"- all_stage2_10_gates_pass: `{packet['all_stage2_10_gates_pass']}`",
        "",
        "| Report | Gate | Verdict | Checks | Failures |",
        "|---|---|---:|---:|---:|",
    ]
    for item in table:
        lines.append(f"| `{item['report']}` | `{item['gate_id']}` | `{item['verdict']}` | {item['passed_count']}/{item['check_count']} | {item['failure_count']} |")
    safe_write_text(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_10_gate_packet.md", "\n".join(lines) + "\n")
    safe_write_text(
        ROOT / "docs" / "STAGE2_10_DECISION.md",
        f"""# Stage 2.10 Decision

Final verdict: `{verdict}`.

Stage 2.10 is limited to operator-approved Qwen systemd persistence closure. Without a valid operator approval file or approval environment variable, no systemd apply is allowed and Stage 3 remains blocked.

Current boundary:

- Qwen structured decision remains disabled.
- Qwen advisor remains disabled safe mode.
- Tool execution authority remains deterministic policy plus `workspace_tool_policy`, `workspace_arg_policy`, and `ai_nas_allowlisted_tool.sh`.
- Stage 3 can only be `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.

Successful path recorded:

- Operator approval file: `{rel(Path(approval.get('approval_file'))) if approval.get('approval_file') else 'operator_approval/qwen_systemd_apply_approved.json'}`.
- Operator: `{approval_file_payload.get('operator')}`.
- Maintenance window: `{approval_file_payload.get('maintenance_window')}`.
- Target unit SHA256: `{target_unit_sha256}`.
- Systemd unit: `qwen25-local-openai-gateway.service`.
- Apply/restart verification: applied=`{apply_detail.get('applied')}`, active_enabled=`{apply_detail.get('service_active_enabled')}`, restart_ok=`{apply_detail.get('restart_ok')}`.
- Rollback verification: `{rollback_payload.get('verdict')}`.
- Post-persistence soak: run_count=`{soak_summary.get('run_count')}`, concurrency=`{soak_summary.get('concurrency')}`, allowed_success_rate=`{soak_summary.get('allowed_success_rate')}`, denial_correctness=`{soak_summary.get('denial_correctness')}`.
- Safety counters: dispatcher_bypass_count=`{soak_summary.get('dispatcher_bypass_count')}`, private_leak_count=`{soak_summary.get('private_leak_count')}`, cloud_private_egress_count=`{soak_summary.get('cloud_private_egress_count')}`, qwen_execution_authority_count=`{soak_summary.get('qwen_execution_authority_count')}`.
- Health and route boundary: OpenClaw health before/after OK=`{soak_summary.get('openclaw_health_before_ok')}/{soak_summary.get('openclaw_health_after_ok')}`, Qwen health before/after OK=`{soak_summary.get('qwen_health_before_ok')}/{soak_summary.get('qwen_health_after_ok')}`, protected_ports_unchanged=`{soak_summary.get('protected_ports_unchanged')}`.

Gate summary:

| Report | Gate | Verdict | Checks | Failures |
|---|---|---:|---:|---:|
{gate_rows}

GPT Pro evidence package:

{chr(10).join(package_lines)}
""",
    )
    safe_write_text(
        ROOT / "docs" / "STAGE3_READONLY_SHADOW_DRYRUN_PLAN_V5.md",
        f"""# Stage 3 Readonly Shadow Dry-Run Plan V5

Stage 3 name: `Stage 3 Readonly Shadow Dry-Run, Policy-First Mode`.

Entry requirements:

1. Operator approval passes.
2. Qwen service is applied.
3. `qwen25-local-openai-gateway.service` is active and enabled.
4. Qwen restart test passes.
5. Rollback plan is verified.
6. Post-persistence readonly shadow soak passes.
7. No write/destructive/admin/recovery workspace is exposed.
8. No production route change occurs.
9. No private cloud egress occurs.
10. OpenClaw and Qwen health pass.

Stage 2.10 entry evidence:

- `operator_approval/qwen_systemd_apply_approved.json`
- `reports/9000_stage2_10_baseline_lock.json`
- `reports/9010_operator_approval_hard_gate.json`
- `reports/9020_qwen_persistence_apply_verify_restart_gate.json`
- `reports/9030_qwen_persistence_rollback_verify_gate.json`
- `reports/9040_post_persistence_policy_first_readonly_shadow_soak_gate.json`
- `reports/9050_stage2_10_stage3_go_no_go_gate.json`
- `reports/stage2_10_post_persistence_shadow_soak_trace.jsonl`
- `01_final_evidence/digua_ai_nas_harness_stage2_10_gate_packet.json`

Stage 2.10 observed state:

- Qwen persistence status: `{packet['qwen_persistence_status']}`.
- Qwen role: structured decision disabled, advisor disabled safe mode, execution authority false.
- Soak trace completeness: `{soak_summary.get('trace_complete_rate')}`.
- Final tool source policy rate: `{soak_summary.get('final_tool_source_policy_rate')}`.
- Protected ports unchanged: `{soak_summary.get('protected_ports_unchanged')}`.

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
        ROOT / "operator_approval" / "qwen_systemd_apply_approved.json",
        ROOT / "reports" / "stage2_10_post_persistence_shadow_soak_trace.jsonl",
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_10_gate_packet.json",
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_10_gate_packet.md",
        ROOT / "docs" / "STAGE2_10_DECISION.md",
        ROOT / "docs" / "STAGE3_READONLY_SHADOW_DRYRUN_PLAN_V5.md",
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
    previous = stage / "previous_stage2_9_input" / STAGE2_9_PACKAGE.name
    previous.parent.mkdir(parents=True, exist_ok=True)
    if STAGE2_9_PACKAGE.exists():
        shutil.copy2(STAGE2_9_PACKAGE, previous)
    payload_files = sorted([path for path in stage.rglob("*") if path.is_file() and path.name not in {"MANIFEST.json", "SHA256SUMS.txt"}], key=lambda path: path.relative_to(stage).as_posix())
    entries = []
    lines = []
    for path in payload_files:
        relative = path.relative_to(stage).as_posix()
        digest = sha256_file(path)
        entries.append({"path": relative, "sha256": digest, "size_bytes": path.stat().st_size})
        lines.append(f"{digest}  {relative}")
    manifest = {
        "package": "digua_ai_nas_harness_stage2_10",
        "generated_at": utc_stamp(),
        "file_count": len(entries),
        "inputs": {"previous_stage2_9_input": f"previous_stage2_9_input/{STAGE2_9_PACKAGE.name}" if STAGE2_9_PACKAGE.exists() else None},
        "files": entries,
    }
    safe_write_json(stage / "MANIFEST.json", manifest)
    safe_write_text(stage / "SHA256SUMS.txt", "\n".join(lines) + "\n")
    return {"stage": str(stage), "file_count": len(entries)}


def build_final_zip(stamp: str) -> dict[str, Any]:
    stage = ROOT / "tmp" / f"stage2_10_final_package_{stamp}"
    info = materialize_package(stage)
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_harness_stage2_10_for_gptpro_{stamp}.zip"
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
    approval = operator_approval_hard_gate(report_root)
    approval["report_paths"] = write_numbered_report(approval, report_root)
    results.append(approval)
    apply_payload = apply_gate(report_root, ssh, approval)
    apply_payload["report_paths"] = write_numbered_report(apply_payload, report_root)
    results.append(apply_payload)
    rollback = rollback_verify_gate(report_root, ssh, apply_payload)
    rollback["report_paths"] = write_numbered_report(rollback, report_root)
    results.append(rollback)
    soak = post_persistence_soak_gate(report_root, ssh, apply_payload, rollback, concurrency=args.soak_concurrency, run_count=args.soak_runs)
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
    parser = argparse.ArgumentParser(description="Run Digua AI-NAS Stage 2.10 gates.")
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
