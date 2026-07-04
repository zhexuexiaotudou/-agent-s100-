#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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
from gates.stage2_8_gates import normalize_protected_ports, port_snapshot, remote_file_sha
from gates.stage2_s100p_live_gates import SshRunner, add_check, command_summary, rel, remote_health, sha256_file, sha256_text
from src.harness.copy_route_guard import (
    approval_phrase,
    assert_no_private_leak,
    clone_candidate,
    confirm,
    dry_run,
    execute,
    preview,
    rollback,
    stable_hash,
    validation_reasons,
)
from src.harness.copy_route_types import CopyCandidate, CopyRouteFeatureFlags, CopyRoutePolicy


REPORT_MAP = {
    "stage4_4_baseline_lock": "15400_stage4_4_baseline_lock",
    "copy_route_contract_gate": "15410_copy_route_contract_gate",
    "copy_route_policy_guard_gate": "15420_copy_route_policy_guard_gate",
    "copy_preview_dryrun_confirm_route_gate": "15430_copy_preview_dryrun_confirm_route_gate",
    "copy_route_adversarial_gate": "15450_copy_route_adversarial_gate",
    "route_level_execute_canary_gate": "15460_route_level_execute_canary_gate",
    "post_route_regression_gate": "15470_post_route_regression_gate",
}

PREVIOUS_COPY_PACKET = ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_copy_candidate_test_gate_packet.json"
FINAL_PACKET_JSON = ROOT / "01_final_evidence" / "digua_ai_nas_stage4_4_copy_route_gate_packet.json"
FINAL_PACKET_MD = ROOT / "01_final_evidence" / "digua_ai_nas_stage4_4_copy_route_gate_packet.md"
POLICY_JSON = ROOT / "configs" / "copy_route_policy.json"
FLAGS_JSON = ROOT / "configs" / "copy_route_feature_flags.json"
CONTRACT_DOC = ROOT / "docs" / "STAGE4_4_COPY_ROUTE_CONTRACT.md"
UI_SPEC_DOC = ROOT / "docs" / "STAGE4_4_OPENCLAW_COPY_UI_CONFIRMATION_SPEC.md"
COPYWRITING_DOC = ROOT / "docs" / "STAGE4_4_COPY_CONFIRMATION_COPYWRITING.md"
WIREFRAME_DOC = ROOT / "evidence" / "stage4_4_ui_wireframe_text.md"
DECISION_DOC = ROOT / "docs" / "STAGE4_4_COPY_ROUTE_DECISION.md"
NEXT_PLAN_DOC = ROOT / "docs" / "NEXT_STAGE4_5_LIMITED_COPY_BETA_PLAN.md"
PREVIEW_TRACE = ROOT / "reports" / "stage4_4_copy_route_preview_dryrun_trace.jsonl"
ADVERSARIAL_TRACE = ROOT / "reports" / "stage4_4_copy_route_adversarial_cases.jsonl"
EXECUTE_TRACE = ROOT / "reports" / "stage4_4_route_execute_canary_trace.jsonl"
REMOTE_DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"

FINAL_VERDICTS = {
    "copy_preview_dryrun_route_ready_execute_disabled",
    "copy_route_execute_canary_blocked_safely",
    "copy_route_execute_canary_passed_target_rolled_back",
    "copy_route_policy_failure_hold",
    "copy_route_privacy_failure_hold",
    "copy_route_regression_failure_hold",
    "inconclusive_missing_evidence",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    safe_write_text(path, "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""))


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


def load_policy_and_flags() -> tuple[CopyRoutePolicy, CopyRouteFeatureFlags]:
    policy = CopyRoutePolicy.from_dict(read_json(POLICY_JSON))
    flags = CopyRouteFeatureFlags.from_dict(read_json(FLAGS_JSON))
    return policy, flags


def candidate_from_previous_packet() -> CopyCandidate:
    if PREVIOUS_COPY_PACKET.exists():
        packet = read_json(PREVIOUS_COPY_PACKET)
        summary = packet.get("copy_test_summary") or {}
        if summary.get("source_relative_path") and summary.get("target_relative_path"):
            return CopyCandidate(
                action_type="copy",
                source_relative_path=str(summary["source_relative_path"]),
                target_relative_path=str(summary["target_relative_path"]),
                source_sha256=str(summary.get("source_sha256") or "a" * 64),
                expected_size_bytes=int(summary.get("source_size_bytes") or 229),
                source_owner_scope="codex_synthetic",
                target_exists_now=False,
                target_parent_exists=True,
                candidate_id=str(summary.get("run_id") or "stage4_4_previous_copy_candidate"),
            )
    return CopyCandidate(
        action_type="copy",
        source_relative_path="Collections/CodexPreflight/source/stage4_4_source.txt",
        target_relative_path="Collections/CodexPreflight/target/stage4_4_target.txt",
        source_sha256="a" * 64,
        expected_size_bytes=229,
        source_owner_scope="codex_synthetic",
        candidate_id="stage4_4_fallback_candidate",
    )


def route_row(route: str, decision: Any) -> dict[str, Any]:
    response_ok, response_leaks = assert_no_private_leak(decision.response)
    audit_ok, audit_leaks = assert_no_private_leak(decision.audit_event)
    return {
        "route": route,
        "allowed": decision.allowed,
        "status": decision.status,
        "reason_codes": list(decision.reason_codes),
        "response": decision.response,
        "audit_event": decision.audit_event,
        "private_leak_count": 0 if response_ok and audit_ok else len(set(response_leaks + audit_leaks)),
        "private_leak_markers": sorted(set(response_leaks + audit_leaks)),
        "writes_performed": bool(decision.response.get("writes_performed")),
    }


def baseline_lock(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    previous = read_json(PREVIOUS_COPY_PACKET) if PREVIOUS_COPY_PACKET.exists() else {}
    previous_summary = previous.get("copy_test_summary") or {}
    remote_identity = ssh.run(
        r"""
set -u
echo '__WHOAMI__'; whoami
echo '__HOSTNAME__'; hostname
echo '__ADDR__'; ip -brief addr || true
echo '__NAS__'; findmnt /mnt/nas/openclaw || true
echo '__UNITS__'; systemctl is-active openclaw-gateway.service || true; systemctl is-active qwen25-local-openai-gateway.service || true
echo '__PORTS__'; ss -lntp 2>/dev/null | grep -E '(:8765|:18080|:18888|:18889)' || true
""",
        timeout=30,
    )
    ports = port_snapshot(ssh)
    openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    dispatcher_hash = remote_file_sha(ssh, REMOTE_DISPATCHER)
    add_check(checks, failures, "previous real NAS copy candidate packet exists", PREVIOUS_COPY_PACKET.exists(), rel(PREVIOUS_COPY_PACKET))
    add_check(
        checks,
        failures,
        "previous copy candidate passed and target rolled back",
        previous.get("final_verdict") == "real_nas_copy_candidate_test_passed_target_rolled_back_source_retained"
        and previous_summary.get("copy_verified") is True
        and previous_summary.get("rollback_verified") is True
        and previous_summary.get("target_missing_after_rollback") is True,
        previous.get("final_verdict"),
    )
    add_check(checks, failures, "S100P identity sampled over SSH", remote_identity["returncode"] == 0 and "__WHOAMI__" in remote_identity["stdout"], command_summary(remote_identity))
    add_check(checks, failures, "NAS mount sampled", "/mnt/nas/openclaw" in remote_identity["stdout"], command_summary(remote_identity))
    add_check(checks, failures, "OpenClaw/Qwen health OK", openclaw["ok"] and qwen["ok"], {"openclaw": openclaw, "qwen": qwen})
    add_check(checks, failures, "protected ports sampled", bool(ports["stdout"]), ports["stdout"])
    add_check(checks, failures, "allowlisted dispatcher hash recorded", bool(dispatcher_hash), dispatcher_hash)
    detail = {
        "previous_final_verdict": previous.get("final_verdict"),
        "previous_copy_summary": {
            "source_retained": previous_summary.get("source_retained"),
            "target_missing_after_rollback": previous_summary.get("target_missing_after_rollback"),
            "copy_verified": previous_summary.get("copy_verified"),
            "rollback_verified": previous_summary.get("rollback_verified"),
            "source_relative_path": previous_summary.get("source_relative_path"),
            "target_relative_path": previous_summary.get("target_relative_path"),
        },
        "remote_identity": command_summary(remote_identity),
        "remote_identity_stdout_tail": remote_identity["stdout"][-3000:],
        "ports": ports,
        "openclaw": openclaw,
        "qwen": qwen,
        "dispatcher_hash": dispatcher_hash,
        "boundary": [
            "Stage4.4 does not repeat real NAS execute.",
            "Stage4.4 exposes preview/dry-run/confirm contract only.",
            "Execute and rollback routes remain disabled by feature flag.",
        ],
    }
    return gate_payload("stage4_4_baseline_lock", checks, failures, detail)


def contract_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    policy, flags = load_policy_and_flags()
    docs = [CONTRACT_DOC, UI_SPEC_DOC, COPYWRITING_DOC, WIREFRAME_DOC]
    missing = [rel(path) for path in [POLICY_JSON, FLAGS_JSON, *docs] if not path.exists()]
    contract_text = CONTRACT_DOC.read_text(encoding="utf-8", errors="replace") if CONTRACT_DOC.exists() else ""
    add_check(checks, failures, "contract/config/UI docs exist", not missing, missing)
    add_check(checks, failures, "required route names documented", all(route in contract_text for route in ["/api/nas/copy/preview", "/api/nas/copy/dry-run", "/api/nas/copy/confirm", "/api/nas/copy/execute", "/api/nas/copy/rollback"]), None)
    add_check(checks, failures, "execute and rollback disabled by default", flags.execute_enabled is False and flags.rollback_enabled is False and flags.execute_canary_enabled is False, flags.to_dict())
    add_check(checks, failures, "policy is copy-only bounded candidate", policy.allowed_action_type == "copy" and policy.allowed_source_prefixes and policy.allowed_target_prefixes and policy.max_size_bytes <= 1048576, policy.to_dict())
    add_check(checks, failures, "Qwen no execution authority documented", "Qwen" in contract_text and "cannot" in contract_text and "execute" in contract_text, None)
    add_check(checks, failures, "destructive actions forbidden in policy", {"delete", "move", "rename", "chmod", "chown", "overwrite", "recursive"}.issubset(set(policy.forbidden_action_types)), policy.to_dict())
    detail = {"policy": policy.to_dict(), "feature_flags": flags.to_dict(), "docs": [rel(path) for path in docs]}
    return gate_payload("copy_route_contract_gate", checks, failures, detail)


def policy_guard_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_copy_route_guard.py"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    good = candidate_from_previous_packet()
    invalids = [
        clone_candidate(good, action_type="delete"),
        clone_candidate(good, source_relative_path="/mnt/nas/openclaw/Personal/a.txt"),
        clone_candidate(good, target_relative_path="C:/Users/x/file.txt"),
        clone_candidate(good, source_relative_path="Collections/CodexPreflight/source/../secret.txt"),
        clone_candidate(good, source_sha256="bad"),
        clone_candidate(good, expected_size_bytes=1048577),
        clone_candidate(good, target_exists_now=True),
        clone_candidate(good, source_is_symlink=True),
        clone_candidate(good, recursive=True),
        clone_candidate(good, overwrite=True),
        clone_candidate(good, requested_by_qwen=True),
        clone_candidate(good, cloud_derived=True),
    ]
    invalid_results = [{"index": idx, "reasons": validation_reasons(item)} for idx, item in enumerate(invalids)]
    default_execute = execute(good)
    add_check(checks, failures, "unit tests pass", completed.returncode == 0, {"stdout_tail": completed.stdout[-2000:], "stderr_tail": completed.stderr[-4000:]})
    add_check(checks, failures, "valid candidate has no policy reasons", validation_reasons(good) == [], validation_reasons(good))
    add_check(checks, failures, "sample invalid candidates rejected 100 percent", all(item["reasons"] for item in invalid_results), invalid_results)
    add_check(checks, failures, "execute blocked by default feature flags", not default_execute.allowed and "execute_feature_disabled" in default_execute.reason_codes, default_execute.to_dict())
    detail = {
        "unit_test_command": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_copy_route_guard.py"],
        "unit_test": {
            "returncode": completed.returncode,
            "stdout_hash": sha256_text(completed.stdout),
            "stderr_hash": sha256_text(completed.stderr),
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-4000:],
        },
        "invalid_sample_count": len(invalids),
        "invalid_results": invalid_results,
        "default_execute": default_execute.to_dict(),
    }
    return gate_payload("copy_route_policy_guard_gate", checks, failures, detail)


def preview_dryrun_confirm_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    policy, flags = load_policy_and_flags()
    cand = candidate_from_previous_packet()
    preview_decision = preview(cand, flags=flags, policy=policy)
    dry_run_decision = dry_run(cand, flags=flags, policy=policy)
    confirm_decision = confirm(cand, approval_phrase(cand), flags=flags, policy=policy, now=1000)
    rows = [
        route_row("preview", preview_decision),
        route_row("dry-run", dry_run_decision),
        route_row("confirm", confirm_decision),
    ]
    write_jsonl(PREVIEW_TRACE, rows)
    add_check(checks, failures, "preview/dry-run/confirm all allowed", all(row["allowed"] for row in rows), rows)
    add_check(checks, failures, "no route writes performed", all(not row["writes_performed"] for row in rows), rows)
    add_check(checks, failures, "confirm issued signed token", bool(confirm_decision.response.get("signed_approval_token")), confirm_decision.response)
    add_check(checks, failures, "route responses and audit are redacted", all(row["private_leak_count"] == 0 for row in rows), rows)
    add_check(checks, failures, "execute and rollback not invoked in route gate", True, {"execute_invoked": False, "rollback_invoked": False})
    detail = {
        "trace": rel(PREVIEW_TRACE),
        "trace_rows": len(rows),
        "candidate_fingerprint": rows[0]["response"]["candidate_fingerprint"],
        "token_hash": confirm_decision.response.get("signed_approval_token_hash"),
    }
    return gate_payload("copy_preview_dryrun_confirm_route_gate", checks, failures, detail)


def adversarial_candidates(base: CopyCandidate) -> list[tuple[str, CopyCandidate]]:
    mutations = [
        ("delete_action", {"action_type": "delete"}),
        ("move_action", {"action_type": "move"}),
        ("rename_action", {"action_type": "rename"}),
        ("chmod_action", {"action_type": "chmod"}),
        ("chown_action", {"action_type": "chown"}),
        ("absolute_source", {"source_relative_path": "/mnt/nas/openclaw/Personal/secret.txt"}),
        ("absolute_target", {"target_relative_path": "/mnt/nas/openclaw/Personal/target.txt"}),
        ("windows_source", {"source_relative_path": "C:/Users/zhexu/secret.txt"}),
        ("unc_source", {"source_relative_path": "\\\\nas\\share\\secret.txt"}),
        ("traversal_source", {"source_relative_path": "Collections/CodexPreflight/source/../secret.txt"}),
        ("traversal_target", {"target_relative_path": "Collections/CodexPreflight/target/../secret.txt"}),
        ("encoded_traversal", {"target_relative_path": "Collections/CodexPreflight/target/%2e%2e/secret.txt"}),
        ("bad_source_prefix", {"source_relative_path": "Documents/secret.txt"}),
        ("bad_target_prefix", {"target_relative_path": "Collections/Other/secret.txt"}),
        ("invalid_hash", {"source_sha256": "bad"}),
        ("zero_size", {"expected_size_bytes": 0}),
        ("too_large", {"expected_size_bytes": 1048577}),
        ("target_exists", {"target_exists_now": True}),
        ("target_parent_missing", {"target_parent_exists": False}),
        ("source_symlink", {"source_is_symlink": True}),
        ("target_parent_symlink", {"target_parent_is_symlink": True}),
        ("recursive", {"recursive": True}),
        ("overwrite", {"overwrite": True}),
        ("qwen_requested", {"requested_by_qwen": True}),
        ("cloud_derived", {"cloud_derived": True}),
        ("bad_owner", {"source_owner_scope": "unknown"}),
        ("same_path", {"target_relative_path": base.source_relative_path}),
        ("empty_source", {"source_relative_path": ""}),
        ("double_slash", {"source_relative_path": "Collections/CodexPreflight/source//secret.txt"}),
        ("control_char", {"target_relative_path": "Collections/CodexPreflight/target/secret\u0000.txt"}),
    ]
    cases: list[tuple[str, CopyCandidate]] = []
    for index in range(120):
        label, overrides = mutations[index % len(mutations)]
        unique = f"{index:03d}"
        adjusted = dict(overrides)
        if "source_relative_path" not in adjusted:
            adjusted["source_relative_path"] = f"Collections/CodexPreflight/source/source_{unique}.txt"
        if "target_relative_path" not in adjusted:
            adjusted["target_relative_path"] = f"Collections/CodexPreflight/target/target_{unique}.txt"
        cases.append((f"{label}_{unique}", clone_candidate(base, **adjusted)))
    return cases


def adversarial_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    policy, flags = load_policy_and_flags()
    base = candidate_from_previous_packet()
    rows: list[dict[str, Any]] = []
    for case_id, cand in adversarial_candidates(base):
        decision = preview(cand, flags=flags, policy=policy)
        row = route_row("preview", decision)
        row["case_id"] = case_id
        row["case_hash"] = stable_hash({"case_id": case_id, "candidate": cand.to_dict()})
        row.pop("response", None)
        row.pop("audit_event", None)
        rows.append(row)
    write_jsonl(ADVERSARIAL_TRACE, rows)
    qwen_count = sum(1 for row in rows if "qwen_has_no_execution_authority" in row["reason_codes"])
    cloud_count = sum(1 for row in rows if "cloud_derived_write_rejected" in row["reason_codes"])
    add_check(checks, failures, "adversarial case count >= 100", len(rows) >= 100, len(rows))
    add_check(checks, failures, "all adversarial cases rejected", all(not row["allowed"] for row in rows), [row for row in rows if row["allowed"]][:5])
    add_check(checks, failures, "private leak count zero", sum(row["private_leak_count"] for row in rows) == 0, [row for row in rows if row["private_leak_count"]][:5])
    add_check(checks, failures, "destructive execution count zero", all(not row["writes_performed"] for row in rows), None)
    add_check(checks, failures, "Qwen authority adversarial cases rejected", qwen_count >= 1, qwen_count)
    add_check(checks, failures, "cloud-derived write adversarial cases rejected", cloud_count >= 1, cloud_count)
    detail = {
        "trace": rel(ADVERSARIAL_TRACE),
        "case_count": len(rows),
        "allowed_count": sum(1 for row in rows if row["allowed"]),
        "private_leak_count": sum(row["private_leak_count"] for row in rows),
        "qwen_authority_rejection_count": qwen_count,
        "cloud_derived_rejection_count": cloud_count,
    }
    return gate_payload("copy_route_adversarial_gate", checks, failures, detail)


def execute_canary_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    policy, flags = load_policy_and_flags()
    cand = candidate_from_previous_packet()
    env_enabled = os.environ.get("AI_NAS_STAGE4_4_ROUTE_EXECUTE_CANARY") == "1"
    approval_path = ROOT / "operator_approval" / "stage4_4_route_execute_canary_approved.json"
    approval_file_present = approval_path.exists()
    operator_approved = False
    if approval_file_present:
        try:
            approval = read_json(approval_path)
            operator_approved = approval.get("approved") is True and approval.get("scope") == "stage4_4_route_execute_canary"
        except Exception:
            operator_approved = False
    token = None
    if flags.execute_enabled and env_enabled and operator_approved:
        token = confirm(cand, approval_phrase(cand), flags=flags, policy=policy, now=1000).response.get("signed_approval_token")
    decision = execute(
        cand,
        flags=flags,
        policy=policy,
        approval_token=token,
        operator_approved=operator_approved,
        env_enabled=env_enabled,
        approval_file_present=approval_file_present,
        now=1001,
    )
    rollback_decision = rollback(cand, flags=flags, policy=policy, operator_approved=operator_approved)
    rows = [route_row("execute", decision), route_row("rollback", rollback_decision)]
    for row in rows:
        row["env_enabled"] = env_enabled
        row["approval_file_present"] = approval_file_present
        row["operator_approved"] = operator_approved
        row["execute_feature_enabled"] = flags.execute_enabled
        row["rollback_feature_enabled"] = flags.rollback_enabled
    write_jsonl(EXECUTE_TRACE, rows)
    blocked_safely = not decision.allowed and "execute_feature_disabled" in decision.reason_codes and not decision.response.get("execution_performed_by_guard")
    add_check(checks, failures, "execute canary blocked safely by default", blocked_safely, decision.to_dict())
    add_check(checks, failures, "rollback blocked safely by default", not rollback_decision.allowed and "rollback_feature_disabled" in rollback_decision.reason_codes, rollback_decision.to_dict())
    add_check(checks, failures, "no execute or rollback writes performed", all(not row["writes_performed"] for row in rows), rows)
    add_check(checks, failures, "execute canary trace redacted", all(row["private_leak_count"] == 0 for row in rows), rows)
    payload = gate_payload(
        "route_level_execute_canary_gate",
        checks,
        failures,
        {
            "trace": rel(EXECUTE_TRACE),
            "env_enabled": env_enabled,
            "approval_file": rel(approval_path),
            "approval_file_present": approval_file_present,
            "operator_approved": operator_approved,
            "feature_flags": flags.to_dict(),
            "execute_status": decision.status,
            "execute_reason_codes": list(decision.reason_codes),
        },
    )
    if blocked_safely and not failures:
        payload["verdict"] = "route_execute_canary_blocked_by_missing_approval_or_flag"
    return payload


def post_route_regression_gate(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    policy, flags = load_policy_and_flags()
    before_ports = port_snapshot(ssh)
    before_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    before_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    dispatcher_before = remote_file_sha(ssh, REMOTE_DISPATCHER)
    base = candidate_from_previous_packet()
    rows = []
    for index in range(100):
        cand = clone_candidate(
            base,
            source_relative_path=f"Collections/CodexPreflight/source/regression_{index:03d}.txt",
            target_relative_path=f"Collections/CodexPreflight/target/regression_{index:03d}.txt",
            source_sha256=f"{index % 16:x}" * 64,
            expected_size_bytes=128 + index,
        )
        decision = preview(cand, flags=flags, policy=policy) if index % 2 == 0 else dry_run(cand, flags=flags, policy=policy)
        rows.append(route_row(decision.route, decision))
    after_ports = port_snapshot(ssh)
    after_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    after_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    dispatcher_after = remote_file_sha(ssh, REMOTE_DISPATCHER)
    normalized_before = normalize_protected_ports(before_ports["stdout"])
    normalized_after = normalize_protected_ports(after_ports["stdout"])
    add_check(checks, failures, "OpenClaw/Qwen health OK before and after", before_openclaw["ok"] and before_qwen["ok"] and after_openclaw["ok"] and after_qwen["ok"], {"before_openclaw": before_openclaw, "before_qwen": before_qwen, "after_openclaw": after_openclaw, "after_qwen": after_qwen})
    add_check(checks, failures, "protected ports unchanged", normalized_before == normalized_after and bool(normalized_before), {"before": normalized_before, "after": normalized_after})
    add_check(checks, failures, "dispatcher hash unchanged", bool(dispatcher_before) and dispatcher_before == dispatcher_after, {"before": dispatcher_before, "after": dispatcher_after})
    add_check(checks, failures, "route mini-soak 100/100 allowed", len(rows) == 100 and all(row["allowed"] for row in rows), {"run_count": len(rows), "denied": [row for row in rows if not row["allowed"]][:3]})
    add_check(checks, failures, "route mini-soak has zero writes and leaks", all(not row["writes_performed"] and row["private_leak_count"] == 0 for row in rows), {"leak_count": sum(row["private_leak_count"] for row in rows)})
    detail = {
        "run_count": len(rows),
        "allowed_count": sum(1 for row in rows if row["allowed"]),
        "private_leak_count": sum(row["private_leak_count"] for row in rows),
        "writes_performed_count": sum(1 for row in rows if row["writes_performed"]),
        "before_ports": before_ports,
        "after_ports": after_ports,
        "dispatcher_before": dispatcher_before,
        "dispatcher_after": dispatcher_after,
        "before_openclaw": before_openclaw,
        "after_openclaw": after_openclaw,
        "before_qwen": before_qwen,
        "after_qwen": after_qwen,
    }
    return gate_payload("post_route_regression_gate", checks, failures, detail)


def final_verdict(gates: list[dict[str, Any]]) -> str:
    by_id = {gate["gate_id"]: gate for gate in gates}
    if by_id.get("copy_route_policy_guard_gate", {}).get("failure_count") or by_id.get("copy_route_contract_gate", {}).get("failure_count"):
        return "copy_route_policy_failure_hold"
    route_gate = by_id.get("copy_preview_dryrun_confirm_route_gate", {})
    adversarial = by_id.get("copy_route_adversarial_gate", {})
    if route_gate.get("failure_count") or adversarial.get("failure_count"):
        route_leaks = (((route_gate.get("detail") or {}).get("private_leak_count")) or 0) + (((adversarial.get("detail") or {}).get("private_leak_count")) or 0)
        return "copy_route_privacy_failure_hold" if route_leaks else "copy_route_policy_failure_hold"
    if by_id.get("post_route_regression_gate", {}).get("failure_count"):
        return "copy_route_regression_failure_hold"
    execute_gate = by_id.get("route_level_execute_canary_gate", {})
    if execute_gate.get("verdict") == "route_execute_canary_blocked_by_missing_approval_or_flag" and not execute_gate.get("failure_count"):
        return "copy_route_execute_canary_blocked_safely"
    if all(gate.get("failure_count") == 0 for gate in gates):
        return "copy_preview_dryrun_route_ready_execute_disabled"
    return "inconclusive_missing_evidence"


def write_final_docs(packet: dict[str, Any]) -> None:
    package = packet.get("final_package") or {}
    safe_write_text(
        DECISION_DOC,
        f"""# Stage 4.4 Copy Route Decision

- final_verdict: `{packet['final_verdict']}`
- preview_dryrun_confirm_ready: `{packet['preview_dryrun_confirm_ready']}`
- route_execute_canary_blocked_safely: `{packet['route_execute_canary_blocked_safely']}`
- real_nas_copy_executed_in_stage4_4: `false`
- execute_feature_enabled: `false`
- rollback_feature_enabled: `false`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Stage 4.4 moves from CLI/probe copy evidence to a route-level API contract. The preview, dry-run, and confirm route guard is ready for review. Execute and rollback remain locked by feature flag, missing execute env, and missing dedicated operator approval file.

Boundary: this does not authorize arbitrary user-file copy, delete, move, rename, overwrite, chmod, chown, recursive operation, Qwen autonomous execution, or cloud-derived private writes.
""",
    )
    safe_write_text(
        NEXT_PLAN_DOC,
        """# Next Stage 4.5 Limited Copy Beta Plan

Goal: expose one limited beta copy path only after GPT Pro/human review of Stage 4.4.

Entry requirements:

1. Keep `execute_enabled=false` until a new operator approval packet is committed.
2. Add a real UI candidate selector that cannot browse the whole NAS.
3. Keep source and target allowlists narrow; do not widen to full `Personal/`.
4. Execute only through `ai_nas_action_execute_copy`.
5. Require fresh signed token, nonce, expiry, operator identity, source hash, target absence, and rollback manifest.
6. Run one real route-level copy canary on a Codex synthetic source only.
7. Roll back the copied target and retain source evidence.
8. Re-run OpenClaw/Qwen health, protected-port, dispatcher-hash, privacy, and adversarial gates.

Exit condition:

- one synthetic route-level execute canary passes and target is rolled back, or
- execute remains safely blocked with clear reason codes.

Still forbidden:

- arbitrary NAS copy
- user-file copy without explicit file selection
- overwrite
- delete
- move/rename
- chmod/chown
- recursive copy
- Qwen direct execution authority
- cloud private payload egress
""",
    )
    safe_write_text(
        FINAL_PACKET_MD,
        f"""# Digua AI-NAS Stage 4.4 Copy Route Gate Packet

- final_verdict: `{packet['final_verdict']}`
- all_gates_pass: `{packet['all_gates_pass']}`
- preview_dryrun_confirm_ready: `{packet['preview_dryrun_confirm_ready']}`
- route_execute_canary_blocked_safely: `{packet['route_execute_canary_blocked_safely']}`
- real_nas_copy_executed_in_stage4_4: `false`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Execute and rollback routes remain disabled by default. Stage 4.4 is a contract and guard readiness gate, not a production write enablement.
""",
    )


def build_packet(gates: list[dict[str, Any]], package_info: dict[str, Any] | None = None, self_check: dict[str, Any] | None = None) -> dict[str, Any]:
    by_id = {gate["gate_id"]: gate for gate in gates}
    verdict = final_verdict(gates)
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "final_verdict_allowed": verdict in FINAL_VERDICTS,
        "all_gates_pass": all(gate.get("failure_count") == 0 for gate in gates),
        "preview_dryrun_confirm_ready": by_id.get("copy_preview_dryrun_confirm_route_gate", {}).get("failure_count") == 0,
        "route_execute_canary_blocked_safely": verdict == "copy_route_execute_canary_blocked_safely",
        "real_nas_copy_executed_in_stage4_4": False,
        "route_execute_executed": False,
        "route_rollback_executed": False,
        "feature_flags": read_json(FLAGS_JSON) if FLAGS_JSON.exists() else {},
        "policy": read_json(POLICY_JSON) if POLICY_JSON.exists() else {},
        "evidence_table": [
            {
                "report": REPORT_MAP[gate["gate_id"]],
                "gate_id": gate["gate_id"],
                "verdict": gate["verdict"],
                "passed_count": gate["passed_count"],
                "check_count": gate["check_count"],
                "failure_count": gate["failure_count"],
            }
            for gate in gates
        ],
        "environment": {"repo_root": str(ROOT), "platform": platform.platform(), "python": platform.python_version()},
        "claim_boundary": [
            "Preview/dry-run/confirm route guard is ready for review.",
            "Execute and rollback routes remain disabled by default.",
            "Stage4.4 did not execute a real NAS copy.",
            "Qwen has no direct execution authority.",
            "Cloud-derived private writes are blocked.",
            "Private raw content is not emitted in route traces.",
        ],
    }
    if package_info:
        packet["final_package"] = package_info
    if self_check:
        packet["package_self_check"] = self_check
    return packet


def copy_into_package(package_root: Path, path: Path) -> None:
    if not path.exists():
        return
    target = package_root / rel(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def package_rows(package_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(package_root.rglob("*"), key=lambda item: item.relative_to(package_root).as_posix()):
        if path.is_file():
            rows.append({"path": path.relative_to(package_root).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return rows


def write_self_check(package_root: Path) -> None:
    safe_write_text(
        package_root / "SELF_CHECK.py",
        r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
checks = []
failures = []

def check(label, ok, detail=None):
    checks.append({"label": label, "ok": bool(ok), "detail": detail})
    if not ok:
        failures.append(label)

required = [
    "01_final_evidence/digua_ai_nas_stage4_4_copy_route_gate_packet.json",
    "01_final_evidence/digua_ai_nas_stage4_4_copy_route_gate_packet.md",
    "docs/STAGE4_4_COPY_ROUTE_CONTRACT.md",
    "docs/STAGE4_4_OPENCLAW_COPY_UI_CONFIRMATION_SPEC.md",
    "docs/STAGE4_4_COPY_CONFIRMATION_COPYWRITING.md",
    "docs/STAGE4_4_COPY_ROUTE_DECISION.md",
    "docs/NEXT_STAGE4_5_LIMITED_COPY_BETA_PLAN.md",
    "configs/copy_route_policy.json",
    "configs/copy_route_feature_flags.json",
    "src/harness/copy_route_guard.py",
    "src/harness/copy_route_types.py",
    "tests/test_copy_route_guard.py",
    "gates/stage4_4_copy_route_gates.py",
    "reports/15400_stage4_4_baseline_lock.json",
    "reports/15410_copy_route_contract_gate.json",
    "reports/15420_copy_route_policy_guard_gate.json",
    "reports/15430_copy_preview_dryrun_confirm_route_gate.json",
    "reports/15450_copy_route_adversarial_gate.json",
    "reports/15460_route_level_execute_canary_gate.json",
    "reports/15470_post_route_regression_gate.json",
    "reports/stage4_4_copy_route_preview_dryrun_trace.jsonl",
    "reports/stage4_4_copy_route_adversarial_cases.jsonl",
    "reports/stage4_4_route_execute_canary_trace.jsonl",
    "evidence/stage4_4_ui_wireframe_text.md",
]
for rel in required:
    check(f"exists: {rel}", (root / rel).exists(), rel)

packet_path = root / "01_final_evidence/digua_ai_nas_stage4_4_copy_route_gate_packet.json"
if packet_path.exists():
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    check("final verdict valid", packet.get("final_verdict") in {
        "copy_preview_dryrun_route_ready_execute_disabled",
        "copy_route_execute_canary_blocked_safely",
        "copy_route_execute_canary_passed_target_rolled_back",
        "copy_route_policy_failure_hold",
        "copy_route_privacy_failure_hold",
        "copy_route_regression_failure_hold",
        "inconclusive_missing_evidence",
    }, packet.get("final_verdict"))
    check("stage4_4 did not execute real copy", packet.get("real_nas_copy_executed_in_stage4_4") is False, packet.get("real_nas_copy_executed_in_stage4_4"))
    flags = packet.get("feature_flags") or {}
    check("execute and rollback flags false", flags.get("execute_enabled") is False and flags.get("rollback_enabled") is False, flags)
    check("preview dryrun confirm ready", packet.get("preview_dryrun_confirm_ready") is True, packet.get("preview_dryrun_confirm_ready"))

for rel in [
    "reports/stage4_4_copy_route_preview_dryrun_trace.jsonl",
    "reports/stage4_4_copy_route_adversarial_cases.jsonl",
    "reports/stage4_4_route_execute_canary_trace.jsonl",
]:
    path = root / rel
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
        check(f"trace has no raw NAS path markers: {rel}", all(marker not in text for marker in ["/mnt/nas", "Personal/", "source_relative_path", "target_relative_path"]), rel)

print(json.dumps({"checks": checks, "failures": failures}, indent=2, ensure_ascii=False))
sys.exit(0 if not failures else 1)
''',
    )


def selected_files(reports: list[dict[str, str]]) -> list[Path]:
    files = [
        FINAL_PACKET_JSON,
        FINAL_PACKET_MD,
        CONTRACT_DOC,
        UI_SPEC_DOC,
        COPYWRITING_DOC,
        WIREFRAME_DOC,
        DECISION_DOC,
        NEXT_PLAN_DOC,
        POLICY_JSON,
        FLAGS_JSON,
        PREVIEW_TRACE,
        ADVERSARIAL_TRACE,
        EXECUTE_TRACE,
        ROOT / "src" / "__init__.py",
        ROOT / "src" / "harness" / "__init__.py",
        ROOT / "src" / "harness" / "copy_route_guard.py",
        ROOT / "src" / "harness" / "copy_route_types.py",
        ROOT / "tests" / "__init__.py",
        ROOT / "tests" / "test_copy_route_guard.py",
        ROOT / "gates" / "stage4_4_copy_route_gates.py",
        PREVIOUS_COPY_PACKET,
        ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_copy_candidate_test_gate_packet.md",
    ]
    for report in reports:
        files.extend([Path(report["json"]), Path(report["md"])])
    return sorted({path for path in files if path.exists()}, key=lambda path: rel(path))


def build_package(reports: list[dict[str, str]], timestamp: str) -> dict[str, Any]:
    package_root = ROOT / "tmp" / f"digua_ai_nas_stage4_4_copy_route_for_gptpro_{timestamp}"
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)
    for path in selected_files(reports):
        copy_into_package(package_root, path)
    internal_packet = package_root / rel(FINAL_PACKET_JSON)
    if internal_packet.exists():
        packet = json.loads(internal_packet.read_text(encoding="utf-8"))
        packet.pop("final_package", None)
        packet.pop("package_self_check", None)
        packet["package_internal_note"] = "This packet is embedded inside the zip, so the zip SHA256 is recorded in the external .sha256.txt file and the root workspace packet."
        safe_write_json(internal_packet, packet)
    internal_packet_md = package_root / rel(FINAL_PACKET_MD)
    if internal_packet_md.exists():
        text = internal_packet_md.read_text(encoding="utf-8", errors="replace")
        lines = []
        for line in text.splitlines():
            if line.startswith("- package:") or line.startswith("- sha256:"):
                continue
            lines.append(line)
        lines.extend(
            [
                "",
                "Package SHA note: this Markdown file is embedded inside the zip; use the adjacent external `.sha256.txt` file for the final zip hash.",
            ]
        )
        safe_write_text(internal_packet_md, "\n".join(lines) + "\n")
    write_self_check(package_root)
    rows = package_rows(package_root)
    safe_write_json(package_root / "MANIFEST.json", {"package": "digua_ai_nas_stage4_4_copy_route", "generated_at": utc_stamp(), "file_count": len(rows), "files": rows})
    safe_write_text(package_root / "SHA256SUMS.txt", "\n".join(f"{row['sha256']}  {row['path']}" for row in package_rows(package_root)) + "\n")
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_stage4_4_copy_route_for_gptpro_{timestamp}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_root.rglob("*"), key=lambda item: item.relative_to(package_root).as_posix()):
            if path.is_file():
                zf.write(path, path.relative_to(package_root).as_posix())
    digest = sha256_file(zip_path)
    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256.txt")
    safe_write_text(sha_path, f"{digest}  {zip_path.name}\n")
    return {"package_root": str(package_root), "zip_path": str(zip_path), "sha256": digest, "sha256_file": str(sha_path), "file_count": len(package_rows(package_root))}


def run_self_check(package_info: dict[str, Any]) -> dict[str, Any]:
    package_root = Path(package_info["package_root"])
    completed = subprocess.run([sys.executable, str(package_root / "SELF_CHECK.py")], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120)
    try:
        parsed = json.loads(completed.stdout)
    except Exception:
        parsed = None
    return {
        "returncode": completed.returncode,
        "stdout_hash": sha256_text(completed.stdout),
        "stderr_hash": sha256_text(completed.stderr),
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
        "json": parsed,
    }


def write_packet(packet: dict[str, Any]) -> None:
    safe_write_json(FINAL_PACKET_JSON, packet)
    write_final_docs(packet)


def run_all(args: argparse.Namespace) -> list[dict[str, Any]]:
    args.report_root.mkdir(parents=True, exist_ok=True)
    ssh = SshRunner(args.host, args.key)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    gates: list[dict[str, Any]] = []
    reports: list[dict[str, str]] = []
    gate_fns = [
        lambda: baseline_lock(args.report_root, ssh),
        lambda: contract_gate(args.report_root),
        lambda: policy_guard_gate(args.report_root),
        lambda: preview_dryrun_confirm_gate(args.report_root),
        lambda: adversarial_gate(args.report_root),
        lambda: execute_canary_gate(args.report_root),
        lambda: post_route_regression_gate(args.report_root, ssh),
    ]
    for gate_fn in gate_fns:
        payload = gate_fn()
        payload["report_paths"] = write_numbered_report(payload, args.report_root)
        gates.append(payload)
        reports.append(payload["report_paths"])
    packet = build_packet(gates)
    write_packet(packet)
    package_info = build_package(reports, timestamp)
    packet = build_packet(gates, package_info)
    write_packet(packet)
    package_info = build_package(reports, timestamp)
    self_check = run_self_check(package_info)
    packet = build_packet(gates, package_info, self_check)
    write_packet(packet)
    package_info = build_package(reports, timestamp)
    self_check = run_self_check(package_info)
    packet = build_packet(gates, package_info, self_check)
    write_packet(packet)
    failed = [gate for gate in gates if gate.get("failure_count")]
    print(json.dumps({"final_verdict": packet["final_verdict"], "failed_gates": [gate["gate_id"] for gate in failed], "package": package_info}, ensure_ascii=False, indent=2))
    return gates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Digua AI-NAS Stage4.4 copy route gates.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gates = run_all(args)
    verdict = final_verdict(gates)
    return 0 if verdict in FINAL_VERDICTS and all(gate.get("failure_count") == 0 for gate in gates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
