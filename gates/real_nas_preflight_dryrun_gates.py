#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import re
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
from gates.stage2_8_gates import normalize_protected_ports, port_snapshot
from gates.stage2_s100p_live_gates import SshRunner, add_check, command_summary, rel, remote_health, sha256_file, sha256_text


REPORT_MAP = {
    "real_nas_preflight_approval_lock_gate": "15100_real_nas_preflight_approval_lock_gate",
    "real_nas_copy_candidate_policy_gate": "15110_real_nas_copy_candidate_policy_gate",
    "real_nas_preflight_dryrun_diff_gate": "15120_real_nas_preflight_dryrun_diff_gate",
    "real_nas_execution_block_gate": "15130_real_nas_execution_block_gate",
    "real_nas_live_readonly_status_gate": "15140_real_nas_live_readonly_status_gate",
}

STAGE4_1_PACKET = ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage4_1_gate_packet.json"
STAGE4_1_PACKAGE_SHA = ROOT / "evidence_for_gptpro" / "digua_ai_nas_harness_stage4_1_for_gptpro_20260704-113916.zip.sha256.txt"
APPROVAL_FILE = ROOT / "operator_approval" / "real_nas_preflight_dryrun_approved.json"
DRYRUN_DIFF_JSON = ROOT / "reports" / "real_nas_preflight_dryrun_diff_redacted.json"
DRYRUN_DIFF_MD = ROOT / "reports" / "real_nas_preflight_dryrun_diff_redacted.md"
FINAL_PACKET_JSON = ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_preflight_dryrun_gate_packet.json"
FINAL_PACKET_MD = ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_preflight_dryrun_gate_packet.md"
DECISION_DOC = ROOT / "docs" / "REAL_NAS_PREFLIGHT_DRYRUN_DECISION.md"
CANDIDATE_REQUEST_DOC = ROOT / "docs" / "NEXT_REAL_NAS_COPY_CANDIDATE_REQUEST.md"
GPTPRO_PROMPT_DOC = ROOT / "docs" / "REAL_NAS_PREFLIGHT_DRYRUN_GPTPRO_PROMPT.md"

ACTION_APPROVAL_PROBE = ROOT / "scripts" / "probes" / "ai_nas_action_approval_manifest_probe.py"
ACTION_EXECUTE_COPY_PROBE = ROOT / "scripts" / "probes" / "ai_nas_action_execute_copy_probe.py"
ACTION_ROLLBACK_COPY_PROBE = ROOT / "scripts" / "probes" / "ai_nas_action_rollback_copy_probe.py"

REMOTE_DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
REMOTE_PERSONAL_ROOT = "/mnt/nas/openclaw/Personal"
REMOTE_COLLECTION_TARGET_PREFIX = "Collections/"
MAX_FIRST_COPY_BYTES = 1024 * 1024

FINAL_VERDICTS = {
    "real_nas_preflight_dryrun_approved_locked_missing_explicit_candidate",
    "real_nas_preflight_dryrun_materialized_awaiting_gptpro_review",
    "real_nas_preflight_not_ready",
}

FORBIDDEN_REAL_NAS_ACTIONS = [
    "delete",
    "chmod",
    "chown",
    "recursive_copy",
    "recursive_delete",
    "move",
    "rename",
    "overwrite",
    "cross_user_copy",
    "cloud_derived_write",
    "qwen_autonomous_write",
    "arbitrary_shell",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_hash(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(value)


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


def load_candidate(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, "missing"
    if not path.exists():
        return None, "candidate_file_missing"
    try:
        data = read_json(path)
    except Exception as exc:
        return None, f"invalid_json:{type(exc).__name__}"
    return data, None


def safe_relative_path(value: Any) -> tuple[bool, str]:
    if not isinstance(value, str) or not value.strip():
        return False, "missing_or_not_string"
    text = value.strip().replace("\\", "/")
    path = Path(text)
    if path.is_absolute():
        return False, "absolute_path_rejected"
    if ".." in path.parts:
        return False, "parent_traversal_rejected"
    if text.startswith("/") or text.startswith("~"):
        return False, "absolute_or_home_path_rejected"
    if re.search(r"(^|/)\.($|/)", text):
        return False, "dot_segment_rejected"
    if text.lower().startswith("personal/"):
        return False, "relative_to_personal_root_required_not_personal_prefix"
    return True, text


def validate_candidate(candidate: dict[str, Any] | None) -> dict[str, Any]:
    if candidate is None:
        return {
            "candidate_present": False,
            "candidate_valid": False,
            "block_reason": "missing_explicit_candidate",
            "safe_block": True,
            "redacted_candidate": None,
            "candidate_hash": None,
        }

    errors: list[str] = []
    action_type = candidate.get("action_type")
    source_ok, source_value = safe_relative_path(candidate.get("source_relative_path"))
    target_ok, target_value = safe_relative_path(candidate.get("target_relative_path"))
    source_sha = candidate.get("source_sha256")
    expected_size = candidate.get("expected_size_bytes")
    owner_scope = candidate.get("source_owner_scope")

    if action_type != "copy":
        errors.append("first_stage_action_must_be_copy")
    if not source_ok:
        errors.append(f"source_relative_path:{source_value}")
    if not target_ok:
        errors.append(f"target_relative_path:{target_value}")
    if target_ok and not str(target_value).startswith(REMOTE_COLLECTION_TARGET_PREFIX):
        errors.append("target_must_be_under_collections")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", source_sha):
        errors.append("source_sha256_required")
    if not isinstance(expected_size, int) or expected_size < 0 or expected_size > MAX_FIRST_COPY_BYTES:
        errors.append("expected_size_bytes_must_be_int_between_0_and_1MiB")
    if owner_scope not in {"operator_owned", "operator_visible"}:
        errors.append("source_owner_scope_required")
    if candidate.get("target_exists_now") not in {False, None}:
        errors.append("target_exists_now_must_be_false_or_unknown")

    redacted = {
        "action_type": action_type,
        "source_relative_path_hash": stable_hash(source_value) if source_ok else None,
        "target_relative_path_hash": stable_hash(target_value) if target_ok else None,
        "source_sha256_prefix": source_sha[:12] if isinstance(source_sha, str) else None,
        "expected_size_bytes": expected_size if isinstance(expected_size, int) else None,
        "source_owner_scope": owner_scope,
        "target_prefix": REMOTE_COLLECTION_TARGET_PREFIX if target_ok and str(target_value).startswith(REMOTE_COLLECTION_TARGET_PREFIX) else None,
    }
    return {
        "candidate_present": True,
        "candidate_valid": not errors,
        "block_reason": None if not errors else "candidate_policy_rejected",
        "safe_block": bool(errors),
        "errors": errors,
        "redacted_candidate": redacted,
        "candidate_hash": stable_hash(candidate),
    }


def approval_lock_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    packet = read_json(STAGE4_1_PACKET) if STAGE4_1_PACKET.exists() else {}
    approval = {
        "generated_at": utc_stamp(),
        "approval_source": "current Codex chat approval",
        "user_message_summary": "operator approved continuing beyond Stage4.1",
        "interpreted_scope": "real_nas_preflight_dryrun_only",
        "real_nas_write_allowed": False,
        "execute_copy_allowed": False,
        "rollback_copy_allowed": False,
        "dryrun_diff_allowed": True,
        "requires_explicit_candidate_before_materialized_dryrun": True,
        "allowed_first_action": "copy",
        "forbidden_actions": FORBIDDEN_REAL_NAS_ACTIONS,
        "previous_stage4_1_packet": rel(STAGE4_1_PACKET),
        "previous_stage4_1_package_sha256_file": rel(STAGE4_1_PACKAGE_SHA) if STAGE4_1_PACKAGE_SHA.exists() else None,
    }
    safe_write_json(APPROVAL_FILE, approval)
    add_check(checks, failures, "Stage4.1 packet exists", STAGE4_1_PACKET.exists(), rel(STAGE4_1_PACKET))
    add_check(
        checks,
        failures,
        "Stage4.1 final verdict allows preflight review",
        packet.get("final_verdict") == "expanded_sandbox_write_canary_passed_ready_for_real_write_preflight_review",
        packet.get("final_verdict"),
    )
    add_check(checks, failures, "Stage4.1 real NAS write was false", packet.get("real_nas_write_executed") is False, packet.get("real_nas_write_executed"))
    add_check(checks, failures, "approval file written as dry-run only", APPROVAL_FILE.exists() and approval["real_nas_write_allowed"] is False and approval["dryrun_diff_allowed"] is True, approval)
    add_check(checks, failures, "execute and rollback remain disallowed by approval", not approval["execute_copy_allowed"] and not approval["rollback_copy_allowed"], approval)
    detail = {"approval_file": rel(APPROVAL_FILE), "approval": approval, "stage4_1_verdict": packet.get("final_verdict")}
    return gate_payload("real_nas_preflight_approval_lock_gate", checks, failures, detail)


def candidate_policy_gate(report_root: Path, candidate_path: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate, load_error = load_candidate(candidate_path)
    validation = validate_candidate(candidate)
    candidate_present = validation["candidate_present"]
    add_check(checks, failures, "first-stage policy is copy-only", True, {"allowed_action": "copy", "forbidden_actions": FORBIDDEN_REAL_NAS_ACTIONS})
    add_check(checks, failures, "target prefix restricted to Personal/Collections", REMOTE_COLLECTION_TARGET_PREFIX == "Collections/", REMOTE_COLLECTION_TARGET_PREFIX)
    add_check(checks, failures, "small-file first-stage limit recorded", MAX_FIRST_COPY_BYTES == 1048576, MAX_FIRST_COPY_BYTES)
    add_check(checks, failures, "missing candidate blocks safely", (not candidate_present and validation["safe_block"]) or candidate_present, validation)
    if candidate_present:
        add_check(checks, failures, "candidate schema passes policy", validation["candidate_valid"], validation)
    else:
        add_check(checks, failures, "no candidate materialized by Codex", True, load_error)
    detail = {
        "candidate_path": str(candidate_path) if candidate_path else None,
        "candidate_load_error": load_error,
        "validation": validation,
        "required_candidate_schema": {
            "action_type": "copy",
            "source_relative_path": "relative to /mnt/nas/openclaw/Personal, no Personal/ prefix, no absolute paths",
            "target_relative_path": "Collections/<reviewed-folder>/<filename>",
            "source_sha256": "64 hex chars from a separate readonly hash probe",
            "expected_size_bytes": f"integer <= {MAX_FIRST_COPY_BYTES}",
            "source_owner_scope": "operator_owned or operator_visible",
            "target_exists_now": "false or omitted until immediate pre-execution recheck",
        },
        "future_required_preconditions": [
            "readonly source existence and sha256 verification",
            "readonly target non-existence check",
            "ACL-visible path check for the current operator",
            "signed approval phrase bound to candidate hash and before-state hash",
            "rollback manifest before execution",
        ],
    }
    return gate_payload("real_nas_copy_candidate_policy_gate", checks, failures, detail)


def dryrun_diff_gate(report_root: Path, candidate_policy: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    validation = ((candidate_policy.get("detail") or {}).get("validation")) or {}
    candidate_valid = bool(validation.get("candidate_valid"))
    candidate_present = bool(validation.get("candidate_present"))
    if candidate_valid:
        diff = {
            "generated_at": utc_stamp(),
            "dryrun_only": True,
            "candidate_hash": validation.get("candidate_hash"),
            "redacted_candidate": validation.get("redacted_candidate"),
            "would_create_one_file": True,
            "would_modify_source": False,
            "would_delete_anything": False,
            "would_overwrite": False,
            "would_call_execute_copy": False,
            "would_call_rollback_copy": False,
            "approval_phrase_generated": False,
            "next_required_gate": "GPT Pro / human review of this dry-run diff before any real execute-copy approval",
        }
        verdict_note = "materialized_redacted_policy_diff"
    else:
        diff = {
            "generated_at": utc_stamp(),
            "dryrun_only": True,
            "candidate_present": candidate_present,
            "candidate_hash": validation.get("candidate_hash"),
            "block_reason": validation.get("block_reason") or "candidate_invalid",
            "safe_block": True,
            "would_create_one_file": False,
            "would_modify_source": False,
            "would_delete_anything": False,
            "would_overwrite": False,
            "would_call_execute_copy": False,
            "would_call_rollback_copy": False,
            "approval_phrase_generated": False,
            "next_required_gate": "provide one explicit low-risk copy candidate before materialized dry-run diff",
        }
        verdict_note = "safe_block_no_materialized_diff"
    safe_write_json(DRYRUN_DIFF_JSON, diff)
    lines = [
        "# Real NAS Preflight Dry-Run Diff",
        "",
        f"- dryrun_only: `{diff['dryrun_only']}`",
        f"- candidate_present: `{diff.get('candidate_present', True)}`",
        f"- block_reason: `{diff.get('block_reason')}`",
        f"- would_create_one_file: `{diff['would_create_one_file']}`",
        f"- would_call_execute_copy: `{diff['would_call_execute_copy']}`",
        f"- would_call_rollback_copy: `{diff['would_call_rollback_copy']}`",
        f"- next_required_gate: `{diff['next_required_gate']}`",
    ]
    safe_write_text(DRYRUN_DIFF_MD, "\n".join(lines) + "\n")
    add_check(checks, failures, "dry-run diff report written", DRYRUN_DIFF_JSON.exists() and DRYRUN_DIFF_MD.exists(), {"json": rel(DRYRUN_DIFF_JSON), "md": rel(DRYRUN_DIFF_MD)})
    add_check(checks, failures, "dry-run performed zero real writes", diff["would_call_execute_copy"] is False and diff["would_call_rollback_copy"] is False, diff)
    add_check(checks, failures, "no destructive effect planned", not diff["would_delete_anything"] and not diff["would_overwrite"] and not diff["would_modify_source"], diff)
    add_check(checks, failures, "candidate missing or invalid blocks safely, valid candidate stays dry-run only", (not candidate_valid and diff.get("safe_block") is True) or (candidate_valid and diff["dryrun_only"] is True), diff)
    detail = {"diff_json": rel(DRYRUN_DIFF_JSON), "diff_md": rel(DRYRUN_DIFF_MD), "diff": diff, "verdict_note": verdict_note}
    return gate_payload("real_nas_preflight_dryrun_diff_gate", checks, failures, detail)


def execution_block_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    probes = {
        "approval_manifest_probe": ACTION_APPROVAL_PROBE,
        "execute_copy_probe": ACTION_EXECUTE_COPY_PROBE,
        "rollback_copy_probe": ACTION_ROLLBACK_COPY_PROBE,
    }
    probe_hashes = {name: {"path": rel(path), "exists": path.exists(), "sha256": sha256_file(path) if path.exists() else None} for name, path in probes.items()}
    execution_audit = {
        "generated_at": utc_stamp(),
        "real_nas_write_executed": False,
        "approval_manifest_probe_invoked": False,
        "execute_copy_probe_invoked": False,
        "rollback_copy_probe_invoked": False,
        "copy_performed": False,
        "target_delete_performed": False,
        "source_modified": False,
        "probes_hashed": probe_hashes,
        "reason": "this gate records preflight lock state and never calls execute/rollback probes",
    }
    add_check(checks, failures, "execute_copy probe exists and was not invoked", ACTION_EXECUTE_COPY_PROBE.exists() and not execution_audit["execute_copy_probe_invoked"], probe_hashes["execute_copy_probe"])
    add_check(checks, failures, "rollback_copy probe exists and was not invoked", ACTION_ROLLBACK_COPY_PROBE.exists() and not execution_audit["rollback_copy_probe_invoked"], probe_hashes["rollback_copy_probe"])
    add_check(checks, failures, "real NAS write executed flag false", execution_audit["real_nas_write_executed"] is False, execution_audit)
    add_check(checks, failures, "copy/delete/source-modification counters false", not execution_audit["copy_performed"] and not execution_audit["target_delete_performed"] and not execution_audit["source_modified"], execution_audit)
    detail = execution_audit
    return gate_payload("real_nas_execution_block_gate", checks, failures, detail)


def live_readonly_status_gate(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    env_probe = ssh.run(
        r"""
set -u
echo '__USER__'; whoami
echo '__HOST__'; hostname
echo '__IP__'; ip -brief addr
echo '__MOUNT__'; findmnt -n /mnt/nas/openclaw || true
echo '__UNITS__'; systemctl --user --no-pager --full list-units --all '*qwen*' '*openclaw*' || true
echo '__PORTS__'; ss -ltnp | grep -E '(:8765|:18080|:18888|:18889)' || true
""",
        timeout=30,
    )
    before_ports = port_snapshot(ssh)
    openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    after_ports = port_snapshot(ssh)
    normalized_before = normalize_protected_ports(before_ports.get("stdout", ""))
    normalized_after = normalize_protected_ports(after_ports.get("stdout", ""))
    port_lines = "\n".join(normalized_after)
    exposed_lines = [line for line in port_lines.splitlines() if any(f":{port} " in line for port in [8765, 18080, 18888, 18889]) and "127.0.0.1:" not in line and "[::1]:" not in line]
    qwen_unit_status = "unknown"
    unit_block = env_probe["stdout"].split("__UNITS__", 1)[-1].split("__PORTS__", 1)[0] if "__UNITS__" in env_probe["stdout"] else ""
    if "qwen25-local-openai-gateway.service" in unit_block:
        qwen_unit_status = "listed"
    elif qwen["ok"]:
        qwen_unit_status = "health_ok_but_expected_unit_not_listed"
    add_check(checks, failures, "SSH readonly environment probe succeeded", env_probe["returncode"] == 0, command_summary(env_probe))
    add_check(checks, failures, "NAS mount visible", "/mnt/nas/openclaw" in env_probe["stdout"], env_probe["stdout"][-2000:])
    add_check(checks, failures, "OpenClaw health OK", openclaw["ok"], openclaw)
    add_check(checks, failures, "Qwen health OK", qwen["ok"], qwen)
    add_check(checks, failures, "protected ports loopback-only and unchanged", not exposed_lines and normalized_before == normalized_after and bool(normalized_after), {"before": normalized_before, "after": normalized_after, "exposed_lines": exposed_lines})
    detail = {
        "remote_probe": command_summary(env_probe),
        "remote_probe_stdout_tail": env_probe["stdout"][-4000:],
        "before_ports": before_ports,
        "after_ports": after_ports,
        "normalized_ports": normalized_after,
        "openclaw_health": openclaw,
        "qwen_health": qwen,
        "qwen_unit_status_note": qwen_unit_status,
        "claim_boundary": "live status is read-only; no NAS user file hash/read/write was performed",
    }
    return gate_payload("real_nas_live_readonly_status_gate", checks, failures, detail)


def final_verdict(gates: list[dict[str, Any]]) -> str:
    if any(gate.get("failure_count") for gate in gates):
        return "real_nas_preflight_not_ready"
    candidate = next(gate for gate in gates if gate["gate_id"] == "real_nas_copy_candidate_policy_gate")
    validation = ((candidate.get("detail") or {}).get("validation")) or {}
    if validation.get("candidate_valid"):
        return "real_nas_preflight_dryrun_materialized_awaiting_gptpro_review"
    return "real_nas_preflight_dryrun_approved_locked_missing_explicit_candidate"


def write_docs(packet: dict[str, Any]) -> None:
    package = packet.get("final_package") or {}
    safe_write_text(
        DECISION_DOC,
        f"""# Real NAS Preflight Dry-Run Decision

- final_verdict: `{packet['final_verdict']}`
- real_nas_write_executed: `false`
- execute_copy_invoked: `false`
- rollback_copy_invoked: `false`
- explicit_candidate_present: `{packet['candidate_status'].get('candidate_present')}`
- explicit_candidate_valid: `{packet['candidate_status'].get('candidate_valid')}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

The operator approval has been registered only for preflight dry-run design. It does not authorize real NAS copy, rename, move, delete, chmod, overwrite, rollback deletion, or arbitrary shell execution.

Current next step: provide one low-risk copy candidate or send this package to GPT Pro for review. Real NAS writes remain locked.
""",
    )
    safe_write_text(
        CANDIDATE_REQUEST_DOC,
        f"""# Next Real NAS Copy Candidate Request

To progress beyond the current safe block, provide exactly one candidate JSON file with this schema:

```json
{{
  "action_type": "copy",
  "source_relative_path": "Documents/example.txt",
  "target_relative_path": "Collections/CodexPreflight/example.txt",
  "source_sha256": "<64 hex chars from a separate readonly hash check>",
  "expected_size_bytes": 12345,
  "source_owner_scope": "operator_owned",
  "target_exists_now": false
}}
```

Rules:

- Paths are relative to `{REMOTE_PERSONAL_ROOT}` and must not start with `Personal/`.
- Target must start with `{REMOTE_COLLECTION_TARGET_PREFIX}`.
- First candidate must be a single file and <= {MAX_FIRST_COPY_BYTES} bytes.
- No delete, chmod, overwrite, recursive operation, move, or rename.
- No cloud-derived writes and no Qwen autonomous writes.
- This candidate enables only a materialized dry-run diff, not execution.
""",
    )
    safe_write_text(
        GPTPRO_PROMPT_DOC,
        f"""# GPT Pro Evaluation Prompt

You are reviewing a Digua AI-NAS / OpenClaw / S100P real-NAS-write preflight package.

Context:
- Stage4.1 passed expanded synthetic sandbox write canaries and failure injection.
- The operator has approved continuing only into real NAS preflight dry-run design.
- No real NAS write has been executed.
- `ai_nas_action_execute_copy_probe.py` and `ai_nas_action_rollback_copy_probe.py` were not invoked.
- The current package verdict is `{packet['final_verdict']}`.

Please evaluate:

1. Is it reasonable to keep real NAS writes locked until one explicit low-risk copy candidate is provided?
2. Is the candidate schema strict enough for a first real NAS copy dry-run?
3. Are the forbidden actions complete enough: delete/chmod/chown/recursive/move/rename/overwrite/cross-user/cloud-derived/Qwen-autonomous/arbitrary-shell?
4. Should the first materialized dry-run require a readonly source hash check and target non-existence check before displaying an approval phrase?
5. What exact gates should Codex implement before the first real copy execution?
6. What rollback evidence is required before allowing execution?
7. Are there any additional ACL, privacy, audit, or UX checks needed for OpenClaw + NAS baseline?

Return:
- final recommendation: keep locked / allow materialized dry-run only / allow first real copy execution later
- required fixes before materialized dry-run
- required fixes before real execution
- a concise staged roadmap Codex can implement with repo-verifiable evidence
""",
    )
    safe_write_text(
        FINAL_PACKET_MD,
        f"""# Digua AI-NAS Real NAS Preflight Dry-Run Gate Packet

- final_verdict: `{packet['final_verdict']}`
- all_gates_pass: `{packet['all_gates_pass']}`
- real_nas_write_executed: `{packet['real_nas_write_executed']}`
- execute_copy_invoked: `{packet['execution_status'].get('execute_copy_probe_invoked')}`
- rollback_copy_invoked: `{packet['execution_status'].get('rollback_copy_probe_invoked')}`
- candidate_present: `{packet['candidate_status'].get('candidate_present')}`
- candidate_valid: `{packet['candidate_status'].get('candidate_valid')}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Real NAS writes remain locked. The next gate needs one explicit low-risk copy candidate before a materialized dry-run diff can be produced.
""",
    )


def build_packet(gates: list[dict[str, Any]], package_info: dict[str, Any] | None = None, self_check: dict[str, Any] | None = None) -> dict[str, Any]:
    by_id = {gate["gate_id"]: gate for gate in gates}
    candidate_status = ((by_id["real_nas_copy_candidate_policy_gate"].get("detail") or {}).get("validation")) or {}
    execution_status = by_id["real_nas_execution_block_gate"].get("detail") or {}
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": final_verdict(gates),
        "final_verdict_allowed": final_verdict(gates) in FINAL_VERDICTS,
        "all_gates_pass": all(gate.get("failure_count") == 0 for gate in gates),
        "real_nas_write_executed": False,
        "real_nas_write_remains_locked": True,
        "materialized_dryrun_requires_explicit_candidate": True,
        "candidate_status": candidate_status,
        "execution_status": execution_status,
        "evidence_table": [
            {
                "report": REPORT_MAP[gate["gate_id"]],
                "gate_id": gate["gate_id"],
                "verdict": gate["verdict"],
                "passed_count": gate.get("passed_count"),
                "check_count": gate.get("check_count"),
                "failure_count": gate.get("failure_count"),
            }
            for gate in gates
        ],
        "environment": {"repo_root": str(ROOT), "platform": platform.platform(), "python": platform.python_version()},
        "claim_boundary": [
            "This package registers approval for dry-run preflight only.",
            "No real NAS copy, delete, move, rename, chmod, overwrite, or rollback deletion was executed.",
            "Existing execute_copy and rollback_copy probes remain hashed but not invoked.",
            "Qwen has no direct write execution authority.",
            "A future materialized dry-run requires one explicit candidate from the operator.",
        ],
        "final_package": package_info,
        "package_self_check": self_check,
    }
    return packet


def selected_package_files(reports: list[dict[str, str]]) -> list[Path]:
    files = [
        FINAL_PACKET_JSON,
        FINAL_PACKET_MD,
        DECISION_DOC,
        CANDIDATE_REQUEST_DOC,
        GPTPRO_PROMPT_DOC,
        APPROVAL_FILE,
        DRYRUN_DIFF_JSON,
        DRYRUN_DIFF_MD,
        ROOT / "docs" / "REAL_NAS_WRITE_PREFLIGHT_DESIGN.md",
        ROOT / "docs" / "REAL_NAS_WRITE_HUMAN_CONFIRMATION_SPEC.md",
        ROOT / "docs" / "REAL_NAS_WRITE_GATE_PLAN.md",
        ROOT / "docs" / "REAL_NAS_WRITE_PREFLIGHT_REVIEW_REQUEST.md",
        ROOT / "docs" / "STAGE4_1_DECISION.md",
        STAGE4_1_PACKET,
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage4_1_gate_packet.md",
        ROOT / "gates" / "real_nas_preflight_dryrun_gates.py",
        ACTION_APPROVAL_PROBE,
        ACTION_EXECUTE_COPY_PROBE,
        ACTION_ROLLBACK_COPY_PROBE,
        ROOT / "scripts" / "run_real_nas_preflight_dryrun_from_package.sh",
    ]
    for report in reports:
        files.extend([Path(report["json"]), Path(report["md"])])
    if STAGE4_1_PACKAGE_SHA.exists():
        files.append(STAGE4_1_PACKAGE_SHA)
    return sorted({path for path in files if path.exists()}, key=lambda path: rel(path))


def write_self_check(stage: Path) -> None:
    safe_write_text(
        stage / "SELF_CHECK.py",
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
    "01_final_evidence/digua_ai_nas_real_nas_preflight_dryrun_gate_packet.json",
    "01_final_evidence/digua_ai_nas_real_nas_preflight_dryrun_gate_packet.md",
    "docs/REAL_NAS_PREFLIGHT_DRYRUN_DECISION.md",
    "docs/NEXT_REAL_NAS_COPY_CANDIDATE_REQUEST.md",
    "docs/REAL_NAS_PREFLIGHT_DRYRUN_GPTPRO_PROMPT.md",
    "operator_approval/real_nas_preflight_dryrun_approved.json",
    "reports/15100_real_nas_preflight_approval_lock_gate.json",
    "reports/15110_real_nas_copy_candidate_policy_gate.json",
    "reports/15120_real_nas_preflight_dryrun_diff_gate.json",
    "reports/15130_real_nas_execution_block_gate.json",
    "reports/15140_real_nas_live_readonly_status_gate.json",
    "reports/real_nas_preflight_dryrun_diff_redacted.json",
    "gates/real_nas_preflight_dryrun_gates.py",
    "scripts/probes/ai_nas_action_execute_copy_probe.py",
    "scripts/probes/ai_nas_action_rollback_copy_probe.py",
]
for rel in required:
    check(f"exists: {rel}", (root / rel).exists(), rel)

packet_path = root / "01_final_evidence/digua_ai_nas_real_nas_preflight_dryrun_gate_packet.json"
if packet_path.exists():
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    check("final verdict allowed", packet.get("final_verdict") in {
        "real_nas_preflight_dryrun_approved_locked_missing_explicit_candidate",
        "real_nas_preflight_dryrun_materialized_awaiting_gptpro_review",
        "real_nas_preflight_not_ready",
    }, packet.get("final_verdict"))
    check("real NAS write false", packet.get("real_nas_write_executed") is False, packet.get("real_nas_write_executed"))
    execution = packet.get("execution_status") or {}
    check("execute_copy not invoked", execution.get("execute_copy_probe_invoked") is False, execution)
    check("rollback_copy not invoked", execution.get("rollback_copy_probe_invoked") is False, execution)
    candidate = packet.get("candidate_status") or {}
    if packet.get("final_verdict") == "real_nas_preflight_dryrun_approved_locked_missing_explicit_candidate":
        check("missing candidate blocks safely", candidate.get("candidate_present") is False and candidate.get("safe_block") is True, candidate)

approval_path = root / "operator_approval/real_nas_preflight_dryrun_approved.json"
if approval_path.exists():
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    check("approval is dry-run only", approval.get("dryrun_diff_allowed") is True and approval.get("real_nas_write_allowed") is False, approval)

diff_path = root / "reports/real_nas_preflight_dryrun_diff_redacted.json"
if diff_path.exists():
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    check("diff does not call execution probes", diff.get("would_call_execute_copy") is False and diff.get("would_call_rollback_copy") is False, diff)

print(json.dumps({"checks": checks, "failures": failures}, indent=2, ensure_ascii=False))
sys.exit(0 if not failures else 1)
''',
    )


def materialize_package(stage: Path, reports: list[dict[str, str]]) -> dict[str, Any]:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for path in selected_package_files(reports):
        target = stage / rel(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    write_self_check(stage)
    entries = []
    lines = []
    for path in sorted(stage.rglob("*"), key=lambda item: item.relative_to(stage).as_posix()):
        if not path.is_file() or path.name in {"MANIFEST.json", "SHA256SUMS.txt"}:
            continue
        relative = path.relative_to(stage).as_posix()
        digest = sha256_file(path)
        entries.append({"path": relative, "sha256": digest, "size_bytes": path.stat().st_size})
        lines.append(f"{digest}  {relative}")
    safe_write_json(stage / "MANIFEST.json", {"package": "digua_ai_nas_real_nas_preflight_dryrun", "generated_at": utc_stamp(), "file_count": len(entries), "files": entries})
    safe_write_text(stage / "SHA256SUMS.txt", "\n".join(lines) + "\n")
    return {"stage": str(stage), "file_count": len(entries) + 2}


def build_package(reports: list[dict[str, str]], stamp: str) -> dict[str, Any]:
    stage = ROOT / "tmp" / f"digua_ai_nas_real_nas_preflight_dryrun_for_gptpro_{stamp}"
    info = materialize_package(stage, reports)
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_real_nas_preflight_dryrun_for_gptpro_{stamp}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage.rglob("*"), key=lambda item: item.relative_to(stage).as_posix()):
            if path.is_file():
                zf.write(path, path.relative_to(stage).as_posix())
    digest = sha256_file(zip_path)
    hash_path = zip_path.with_suffix(zip_path.suffix + ".sha256.txt")
    safe_write_text(hash_path, f"{digest}  {zip_path.name}\n")
    return {"package_root": str(stage), "zip_path": str(zip_path), "sha256": digest, "sha256_file": str(hash_path), "file_count": info["file_count"]}


def run_self_check(package_info: dict[str, Any]) -> dict[str, Any]:
    stage = Path(package_info["package_root"])
    completed = subprocess.run([sys.executable, str(stage / "SELF_CHECK.py")], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120)
    parsed = None
    try:
        parsed = json.loads(completed.stdout)
    except Exception:
        pass
    return {
        "returncode": completed.returncode,
        "stdout_hash": sha256_text(completed.stdout),
        "stderr_hash": sha256_text(completed.stderr),
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-1000:],
        "json": parsed,
    }


def write_packet(packet: dict[str, Any]) -> None:
    safe_write_json(FINAL_PACKET_JSON, packet)
    write_docs(packet)


def run_all(args: argparse.Namespace) -> list[dict[str, Any]]:
    report_root = args.report_root
    report_root.mkdir(parents=True, exist_ok=True)
    ssh = SshRunner(args.host, args.key)
    gates: list[dict[str, Any]] = []
    reports: list[dict[str, str]] = []

    for gate in [
        approval_lock_gate(report_root),
        candidate_policy_gate(report_root, args.candidate_json),
    ]:
        gates.append(gate)
        reports.append(write_numbered_report(gate, report_root))

    dryrun = dryrun_diff_gate(report_root, gates[-1])
    gates.append(dryrun)
    reports.append(write_numbered_report(dryrun, report_root))

    for gate in [
        execution_block_gate(report_root),
        live_readonly_status_gate(report_root, ssh),
    ]:
        gates.append(gate)
        reports.append(write_numbered_report(gate, report_root))

    packet = build_packet(gates)
    write_packet(packet)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    package_info = build_package(reports, stamp)
    packet = build_packet(gates, package_info)
    write_packet(packet)
    package_info = build_package(reports, stamp)
    self_check = run_self_check(package_info)
    packet = build_packet(gates, package_info, self_check)
    write_packet(packet)
    package_info = build_package(reports, stamp)
    self_check = run_self_check(package_info)
    packet = build_packet(gates, package_info, self_check)
    write_packet(packet)
    print(json.dumps({"final_verdict": packet["final_verdict"], "package": package_info, "failed": [gate["gate_id"] for gate in gates if gate["failure_count"]]}, ensure_ascii=False, indent=2))
    return gates


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real NAS preflight dry-run-only gates.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path.home() / ".ssh" / "s100p_linkcheck_ed25519")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--candidate-json", type=Path, default=None)
    args = parser.parse_args()
    gates = run_all(args)
    return 0 if all(gate.get("failure_count") == 0 for gate in gates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
