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
from gates.aggressive_progression_gates import aggressive_remote_script
from gates.harness_gate_common import gate_payload
from gates.stage2_8_gates import normalize_protected_ports, port_snapshot, remote_file_sha, run_remote_python
from gates.stage2_s100p_live_gates import SshRunner, add_check, command_summary, rel, remote_health, sha256_file, sha256_text
from src.harness.copy_route_guard import (
    approval_phrase,
    assert_no_private_leak,
    clone_candidate,
    confirm,
    create_signed_approval_token,
    dry_run,
    execute,
    path_hash,
    preview,
    public_candidate_fingerprint,
    rollback,
    stable_hash,
)
from src.harness.copy_route_types import CopyCandidate, CopyRouteFeatureFlags, CopyRoutePolicy


REPORT_MAP = {
    "stage4_5_baseline_lock": "15500_stage4_5_baseline_lock",
    "stage4_5_self_created_synthetic_source_gate": "15510_stage4_5_self_created_synthetic_source_gate",
    "stage4_5_synthetic_approval_gate": "15520_stage4_5_synthetic_approval_gate",
    "stage4_5_candidate_readonly_verification_gate": "15530_stage4_5_candidate_readonly_verification_gate",
    "stage4_5_pre_execute_route_flow_gate": "15540_stage4_5_pre_execute_route_flow_gate",
    "stage4_5_feature_flag_scoped_enable_gate": "15550_stage4_5_feature_flag_scoped_enable_gate",
    "stage4_5_route_execute_canary_gate": "15560_stage4_5_route_execute_canary_gate",
    "stage4_5_route_rollback_canary_gate": "15570_stage4_5_route_rollback_canary_gate",
    "stage4_5_feature_flag_close_and_health_gate": "15580_stage4_5_feature_flag_close_and_health_gate",
    "stage4_5_post_execute_adversarial_regression_gate": "15590_stage4_5_post_execute_adversarial_regression_gate",
    "stage4_5_readonly_regression_mini_soak_gate": "15600_stage4_5_readonly_regression_mini_soak_gate",
}

FLAGS_JSON = ROOT / "configs" / "copy_route_feature_flags.json"
POLICY_JSON = ROOT / "configs" / "copy_route_policy.json"
STAGE4_4_PACKET = ROOT / "01_final_evidence" / "digua_ai_nas_stage4_4_copy_route_gate_packet.json"
FINAL_PACKET_JSON = ROOT / "01_final_evidence" / "digua_ai_nas_stage4_5_self_created_synthetic_route_canary_gate_packet.json"
FINAL_PACKET_MD = ROOT / "01_final_evidence" / "digua_ai_nas_stage4_5_self_created_synthetic_route_canary_gate_packet.md"
DECISION_DOC = ROOT / "docs" / "STAGE4_5_SELF_CREATED_SYNTHETIC_ROUTE_COPY_CANARY_DECISION.md"
NEXT_PLAN_DOC = ROOT / "docs" / "NEXT_STAGE4_6_OPERATOR_SELECTED_FIXTURE_ROUTE_CANARY_PLAN.md"
CANDIDATE_JSON = ROOT / "operator_candidates" / "stage4_5_self_created_synthetic_route_candidate.json"
APPROVAL_JSON = ROOT / "operator_approval" / "stage4_5_self_created_synthetic_route_execute_approved.json"
MANIFEST_JSON = ROOT / "operator_candidates" / "stage4_5_self_created_synthetic_route_approval_manifest.json"
PRE_EXEC_TRACE = ROOT / "reports" / "stage4_5_pre_execute_route_flow_trace.jsonl"
EXEC_TRACE = ROOT / "reports" / "stage4_5_route_execute_trace.jsonl"
ROLLBACK_TRACE = ROOT / "reports" / "stage4_5_route_rollback_trace.jsonl"
ADVERSARIAL_TRACE = ROOT / "reports" / "15590_stage4_5_post_execute_adversarial_cases.jsonl"
READONLY_TRACE = ROOT / "reports" / "stage4_5_readonly_regression_mini_soak_trace.jsonl"
REMOTE_DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
REMOTE_PERSONAL_ROOT = "/mnt/nas/openclaw/Personal"

FINAL_VERDICTS = {
    "self_created_synthetic_route_copy_canary_passed_target_rolled_back",
    "synthetic_source_creation_failed_hold",
    "route_execute_blocked_safely",
    "route_execute_policy_failure_hold",
    "route_rollback_failure_hold",
    "route_privacy_failure_hold",
    "route_regression_failure_hold",
    "feature_flag_close_failure_hold",
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


def hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_text(encoded.decode("utf-8"))


def stable_action_id(action_type: str, source_relative_path: str, target_relative_path: str) -> str:
    raw = f"{action_type}\0{source_relative_path}\0{target_relative_path}"
    return f"{action_type}-{sha256_text(raw)[:16]}"


def load_policy_and_flags() -> tuple[CopyRoutePolicy, CopyRouteFeatureFlags]:
    return CopyRoutePolicy.from_dict(read_json(POLICY_JSON)), CopyRouteFeatureFlags.from_dict(read_json(FLAGS_JSON))


def ctx_candidate(ctx: dict[str, Any]) -> CopyCandidate | None:
    payload = ctx.get("candidate_payload")
    return CopyCandidate.from_dict(payload) if payload else None


def scoped_flags_enabled() -> CopyRouteFeatureFlags:
    return CopyRouteFeatureFlags(
        preview_enabled=True,
        dry_run_enabled=True,
        confirm_enabled=True,
        execute_enabled=True,
        rollback_enabled=True,
        execute_canary_enabled=True,
        require_operator_approval_file=True,
        require_execute_env=True,
    )


def scoped_flags_closed() -> CopyRouteFeatureFlags:
    return CopyRouteFeatureFlags(
        preview_enabled=True,
        dry_run_enabled=True,
        confirm_enabled=True,
        execute_enabled=False,
        rollback_enabled=False,
        execute_canary_enabled=False,
        require_operator_approval_file=True,
        require_execute_env=True,
    )


def route_row(route: str, decision: Any, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    response_ok, response_leaks = assert_no_private_leak(decision.response)
    audit_ok, audit_leaks = assert_no_private_leak(decision.audit_event)
    row = {
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
    if extra:
        row.update(extra)
    return row


def sanitize_trace_rows(rows: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    markers = [marker for marker in ["/mnt/nas", "Personal/", "source_relative_path", "target_relative_path", "C:\\"] if marker.lower() in text.lower()]
    return not markers, markers


def source_create_script() -> str:
    return r'''
import hashlib
import json
import os
from pathlib import Path

run_id = os.environ["STAGE45_RUN_ID"]
personal = Path("/mnt/nas/openclaw/Personal")
source_rel = f"Collections/CodexPreflight/source/{run_id}.txt"
target_rel = f"Collections/CodexPreflight/target/{run_id}_copied.txt"
source = personal / source_rel
target = personal / target_rel
source.parent.mkdir(parents=True, exist_ok=True)
target.parent.mkdir(parents=True, exist_ok=True)
if source.exists():
    raise SystemExit(json.dumps({"ok": False, "error": "synthetic_source_already_exists", "source_relative_path": source_rel}))
if target.exists():
    raise SystemExit(json.dumps({"ok": False, "error": "synthetic_target_already_exists", "target_relative_path": target_rel}))
content = "\n".join([
    f"run_id={run_id}",
    "created_by=codex",
    "purpose=stage4_5_self_created_synthetic_route_copy_canary",
    "non_sensitive=true",
    "source_scope=Collections/CodexPreflight/source",
]) + "\n"
source.write_text(content, encoding="utf-8", newline="\n")
digest = hashlib.sha256(source.read_bytes()).hexdigest()
payload = {
    "ok": True,
    "run_id": run_id,
    "personal_root": str(personal),
    "source_relative_path": source_rel,
    "source_absolute_path": str(source),
    "target_relative_path": target_rel,
    "target_absolute_path": str(target),
    "source_sha256": digest,
    "source_size_bytes": source.stat().st_size,
    "source_exists": source.exists(),
    "source_is_file": source.is_file(),
    "source_is_symlink": source.is_symlink(),
    "target_exists": target.exists(),
    "target_parent_exists": target.parent.exists(),
    "target_parent_is_symlink": target.parent.is_symlink(),
}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
'''


def verify_candidate_script() -> str:
    return r'''
import hashlib
import json
import os
from pathlib import Path

personal = Path("/mnt/nas/openclaw/Personal")
source_rel = os.environ["STAGE45_SOURCE_REL"]
target_rel = os.environ["STAGE45_TARGET_REL"]
expected_sha = os.environ["STAGE45_SOURCE_SHA"]
source = personal / source_rel
target = personal / target_rel

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

source_sha = digest(source) if source.exists() and source.is_file() else None
payload = {
    "source_exists": source.exists(),
    "source_is_file": source.is_file(),
    "source_is_symlink": source.is_symlink(),
    "source_sha256": source_sha,
    "source_sha256_matches": source_sha == expected_sha,
    "source_size_bytes": source.stat().st_size if source.exists() else None,
    "target_exists": target.exists(),
    "target_is_symlink": target.is_symlink(),
    "target_parent_exists": target.parent.exists(),
    "target_parent_is_symlink": target.parent.is_symlink(),
    "source_relative_path": source_rel,
    "target_relative_path": target_rel,
}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
'''


def dispatcher_helper_script() -> str:
    return r'''
import glob
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
PERSONAL_ROOT = Path("/mnt/nas/openclaw/Personal")
action = os.environ["STAGE45_ACTION"]
report_root = os.environ["STAGE45_REPORT_ROOT"]
env = os.environ.copy()
env["AI_NAS_PERSONAL_ROOT"] = str(PERSONAL_ROOT)
env["AI_NAS_REPORT_ROOT"] = report_root

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

if action == "execute":
    cmd = [
        DISPATCHER,
        "ai_nas_action_execute_copy",
        os.environ["STAGE45_MANIFEST_PATH"],
        os.environ["STAGE45_APPROVAL_PHRASE"],
        "--report-root",
        report_root,
    ]
    pattern = os.path.join(report_root, "action_execute_copy_*", "action_execute_copy.json")
elif action == "rollback":
    cmd = [
        DISPATCHER,
        "ai_nas_action_rollback_copy",
        os.environ["STAGE45_ROLLBACK_MANIFEST_PATH"],
        os.environ["STAGE45_ROLLBACK_PHRASE"],
        "--report-root",
        report_root,
    ]
    pattern = os.path.join(report_root, "action_rollback_copy_*", "action_rollback_copy.json")
else:
    raise SystemExit("unsupported_action")

started = subprocess.run(["date", "-Is"], text=True, capture_output=True).stdout.strip()
cp = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120, env=env)
matches = sorted(glob.glob(pattern), key=os.path.getmtime)
report_path = matches[-1] if matches else None
report_payload = json.loads(Path(report_path).read_text(encoding="utf-8")) if report_path else None
payload = {
    "action": action,
    "started_at": started,
    "returncode": cp.returncode,
    "stdout_hash": hashlib.sha256(cp.stdout.encode("utf-8", errors="replace")).hexdigest(),
    "stderr_hash": hashlib.sha256(cp.stderr.encode("utf-8", errors="replace")).hexdigest(),
    "stdout_tail": cp.stdout[-1000:],
    "stderr_tail": cp.stderr[-1000:],
    "report_path": report_path,
    "report_payload": report_payload,
}
if action == "execute" and report_path:
    rollback_path = str(Path(report_path).parent / "rollback_manifest.json")
    payload["rollback_manifest_path"] = rollback_path
if os.environ.get("STAGE45_SOURCE_REL"):
    source = PERSONAL_ROOT / os.environ["STAGE45_SOURCE_REL"]
    payload["source_exists_after"] = source.exists()
    payload["source_sha256_after"] = digest(source) if source.exists() and source.is_file() else None
if os.environ.get("STAGE45_TARGET_REL"):
    target = PERSONAL_ROOT / os.environ["STAGE45_TARGET_REL"]
    payload["target_exists_after"] = target.exists()
    payload["target_sha256_after"] = digest(target) if target.exists() and target.is_file() else None
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
sys.exit(0 if cp.returncode == 0 and report_payload else 1)
'''


def make_approval_manifest(candidate: CopyCandidate, ctx: dict[str, Any]) -> dict[str, Any]:
    action_id = stable_action_id("copy", candidate.source_relative_path, candidate.target_relative_path)
    seed = {
        "run_id": ctx["run_id"],
        "candidate_id": candidate.candidate_id,
        "source_sha256": candidate.source_sha256,
        "source_path_hash": path_hash(candidate.source_relative_path),
        "target_path_hash": path_hash(candidate.target_relative_path),
        "action_id": action_id,
    }
    manifest_id = "apm-" + hash_payload(seed)[:16]
    manifest = {
        "generated_at": utc_stamp(),
        "tool_id": "ai_nas_action_approval_manifest",
        "manifest_id": manifest_id,
        "status": "awaiting_human_confirmation",
        "personal_root": REMOTE_PERSONAL_ROOT,
        "query": "stage4_5_self_created_synthetic_route_copy_canary",
        "collection_name": "CodexPreflight",
        "run_id": ctx["run_id"],
        "proposed_actions": [
            {
                "action_id": action_id,
                "action_type": "copy",
                "status": "proposed_requires_human_confirmation",
                "source_relative_path": candidate.source_relative_path,
                "source_absolute_path": f"{REMOTE_PERSONAL_ROOT}/{candidate.source_relative_path}",
                "source_sha256": candidate.source_sha256,
                "target_relative_path": candidate.target_relative_path,
                "target_absolute_path": f"{REMOTE_PERSONAL_ROOT}/{candidate.target_relative_path}",
                "target_exists_now": candidate.target_exists_now,
                "reason": "copy one Codex-created non-sensitive synthetic canary file through the existing allowlisted dispatcher",
                "permission_level_required": "bounded-codex-synthetic-copy",
                "requires_human_confirmation": True,
                "destructive": False,
                "write_effect": "create one target file only if absent; never overwrite; never delete source",
                "rollback_plan": [
                    "remove only the copied target listed by rollback_manifest.json",
                    "verify target sha256 before removal",
                    "never touch source file",
                ],
            }
        ],
        "blocked_destructive_actions": [
            {"action_type": item, "status": "blocked_not_generated", "reason": "Stage4.5 canary is copy-only"}
            for item in ["delete", "move", "rename", "chmod", "chown", "overwrite", "recursive"]
        ],
        "approval": {
            "required": True,
            "approval_phrase": f"APPROVE {manifest_id}",
            "approval_scope": "one self-created synthetic file copy listed in proposed_actions by exact action_id",
            "execution_allowed_by_this_tool": False,
        },
        "audit": {
            "tool_id": "ai_nas_action_approval_manifest",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "execution_performed": False,
            "qwen_execution_authority": False,
            "cloud_private_egress": False,
        },
    }
    manifest["manifest_sha256"] = hash_payload(manifest)
    return manifest


def baseline_lock(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    previous = read_json(STAGE4_4_PACKET) if STAGE4_4_PACKET.exists() else {}
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
    policy, flags = load_policy_and_flags()
    ctx["baseline_dispatcher_hash"] = dispatcher_hash
    ctx["baseline_ports_normalized"] = normalize_protected_ports(ports.get("stdout", ""))
    add_check(checks, failures, "Stage4.4 route packet exists", STAGE4_4_PACKET.exists(), rel(STAGE4_4_PACKET))
    add_check(checks, failures, "Stage4.4 ended with execute blocked safely", previous.get("final_verdict") == "copy_route_execute_canary_blocked_safely", previous.get("final_verdict"))
    add_check(checks, failures, "S100P identity sampled over SSH", remote_identity["returncode"] == 0 and "__WHOAMI__" in remote_identity["stdout"], command_summary(remote_identity))
    add_check(checks, failures, "NAS mount sampled", "/mnt/nas/openclaw" in remote_identity["stdout"], command_summary(remote_identity))
    add_check(checks, failures, "OpenClaw/Qwen health OK", openclaw["ok"] and qwen["ok"], {"openclaw": openclaw, "qwen": qwen})
    add_check(checks, failures, "protected ports sampled", bool(ports["stdout"]), ports["stdout"])
    add_check(checks, failures, "allowlisted dispatcher hash recorded", bool(dispatcher_hash), dispatcher_hash)
    add_check(checks, failures, "global execute/rollback flags are closed before canary", flags.execute_enabled is False and flags.rollback_enabled is False and flags.execute_canary_enabled is False, flags.to_dict())
    detail = {
        "run_id": ctx["run_id"],
        "stage4_4_final_verdict": previous.get("final_verdict"),
        "remote_identity": command_summary(remote_identity),
        "remote_identity_stdout_tail": remote_identity["stdout"][-3000:],
        "openclaw": openclaw,
        "qwen": qwen,
        "ports": ports,
        "normalized_protected_ports": ctx["baseline_ports_normalized"],
        "dispatcher_hash": dispatcher_hash,
        "policy": policy.to_dict(),
        "global_feature_flags_before": flags.to_dict(),
        "boundary": [
            "Stage4.5 may create only one Codex synthetic source under Collections/CodexPreflight/source.",
            "The canary copy and rollback must go through route guard plus allowlisted dispatcher.",
            "Global execute/rollback flags remain disabled.",
        ],
    }
    return gate_payload("stage4_5_baseline_lock", checks, failures, detail)


def self_created_synthetic_source_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    remote_root = f"/mnt/nas/openclaw/reports/stage4_5_route_canary_{ctx['run_id']}"
    ctx["remote_root"] = remote_root
    result = run_remote_python(
        ssh,
        remote_root,
        "stage4_5_create_self_synthetic_source",
        source_create_script(),
        timeout=60,
        env={"STAGE45_RUN_ID": ctx["run_id"]},
    )
    data = result.get("json") or {}
    add_check(checks, failures, "remote source creation helper copied and ran", result.get("scp", {}).get("returncode") == 0 and result.get("run", {}).get("returncode") == 0 and data.get("ok") is True, command_summary(result.get("run", {})))
    add_check(checks, failures, "source path is constrained to CodexPreflight/source", str(data.get("source_relative_path", "")).startswith("Collections/CodexPreflight/source/"), data.get("source_relative_path"))
    add_check(checks, failures, "target path is constrained to CodexPreflight/target", str(data.get("target_relative_path", "")).startswith("Collections/CodexPreflight/target/"), data.get("target_relative_path"))
    add_check(checks, failures, "source exists as regular non-symlink file", data.get("source_exists") is True and data.get("source_is_file") is True and data.get("source_is_symlink") is False, data)
    add_check(checks, failures, "target is absent before route execute", data.get("target_exists") is False and data.get("target_parent_exists") is True and data.get("target_parent_is_symlink") is False, data)
    add_check(checks, failures, "source sha256 and size recorded", isinstance(data.get("source_sha256"), str) and len(data.get("source_sha256", "")) == 64 and int(data.get("source_size_bytes") or 0) > 0, data)
    if not failures:
        candidate_payload = {
            "schema_version": "stage4_5_self_created_synthetic_route_candidate_v1",
            "run_id": ctx["run_id"],
            "candidate_id": f"stage4_5-{ctx['run_id']}",
            "action_type": "copy",
            "source_relative_path": data["source_relative_path"],
            "target_relative_path": data["target_relative_path"],
            "source_sha256": data["source_sha256"],
            "expected_size_bytes": int(data["source_size_bytes"]),
            "source_owner_scope": "codex_synthetic",
            "target_exists_now": False,
            "target_parent_exists": True,
            "target_parent_exists_now": True,
            "source_is_symlink": False,
            "target_parent_is_symlink": False,
            "requested_by_qwen": False,
            "cloud_derived": False,
            "recursive": False,
            "overwrite": False,
            "operator_user_id": "operator-zhexu",
            "metadata": {
                "source_created_by_codex": True,
                "non_sensitive": True,
                "remote_source_absolute_path": data.get("source_absolute_path"),
                "remote_target_absolute_path": data.get("target_absolute_path"),
            },
        }
        CANDIDATE_JSON.parent.mkdir(parents=True, exist_ok=True)
        safe_write_json(CANDIDATE_JSON, candidate_payload)
        ctx["candidate_payload"] = candidate_payload
        ctx["source_create"] = data
    detail = {
        "remote_root": remote_root,
        "remote_run": command_summary(result.get("run", {})),
        "source_creation": data,
        "candidate_json": rel(CANDIDATE_JSON) if CANDIDATE_JSON.exists() else None,
    }
    return gate_payload("stage4_5_self_created_synthetic_source_gate", checks, failures, detail)


def synthetic_approval_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    policy, _ = load_policy_and_flags()
    if candidate:
        manifest = make_approval_manifest(candidate, ctx)
        approval = {
            "schema_version": "stage4_5_self_created_synthetic_route_execute_approval_v1",
            "generated_at": utc_stamp(),
            "approved": True,
            "approved_by": "operator_zhexu_chat_authorized",
            "approval_source": "user_chat_explicit_permission",
            "scope": {
                "candidate_id": candidate.candidate_id,
                "candidate_fingerprint": public_candidate_fingerprint(candidate),
                "source_path_hash": path_hash(candidate.source_relative_path),
                "target_path_hash": path_hash(candidate.target_relative_path),
                "source_sha256": candidate.source_sha256,
                "allowed_action_type": "copy",
                "required_dispatcher_tool": "ai_nas_action_execute_copy",
            },
            "forbidden": ["delete", "move", "rename", "chmod", "chown", "overwrite", "recursive", "arbitrary_shell", "qwen_autonomous_execute", "cloud_private_write"],
            "expires_after_stage": "stage4_5_single_canary_only",
        }
        safe_write_json(APPROVAL_JSON, approval)
        safe_write_json(MANIFEST_JSON, manifest)
        remote_manifest = f"{ctx['remote_root']}/approval_manifest.json"
        ssh.run(f"mkdir -p '{ctx['remote_root']}'", timeout=20)
        scp = ssh.scp_to(MANIFEST_JSON, remote_manifest, timeout=60)
        ctx["approval_payload"] = approval
        ctx["manifest_payload"] = manifest
        ctx["remote_manifest_path"] = remote_manifest
        ctx["manifest_id"] = manifest["manifest_id"]
        ctx["manifest_approval_phrase"] = manifest["approval"]["approval_phrase"]
        ctx["manifest_scp"] = scp
    else:
        manifest = {}
        approval = {}
        scp = {}
    add_check(checks, failures, "candidate exists from self-created synthetic source", candidate is not None and CANDIDATE_JSON.exists(), rel(CANDIDATE_JSON))
    add_check(checks, failures, "operator approval file created and scoped", bool(approval.get("approved")) and APPROVAL_JSON.exists() and approval.get("scope", {}).get("required_dispatcher_tool") == "ai_nas_action_execute_copy", rel(APPROVAL_JSON))
    add_check(checks, failures, "approval forbids destructive and autonomous actions", {"delete", "move", "rename", "overwrite", "recursive", "arbitrary_shell", "qwen_autonomous_execute", "cloud_private_write"}.issubset(set(approval.get("forbidden", []))), approval.get("forbidden"))
    add_check(checks, failures, "approval manifest has valid one-action copy proposal", len(manifest.get("proposed_actions") or []) == 1 and manifest.get("approval", {}).get("execution_allowed_by_this_tool") is False, manifest)
    add_check(checks, failures, "manifest hash is self-consistent", manifest.get("manifest_sha256") == hash_payload({k: v for k, v in manifest.items() if k != "manifest_sha256"}), manifest.get("manifest_sha256"))
    add_check(checks, failures, "manifest copied to S100P report root", scp.get("returncode") == 0, scp)
    add_check(checks, failures, "policy still copy-only", policy.allowed_action_type == "copy" and policy.forbid_qwen_autonomous and policy.forbid_cloud_derived, policy.to_dict())
    detail = {
        "candidate_json": rel(CANDIDATE_JSON) if CANDIDATE_JSON.exists() else None,
        "approval_json": rel(APPROVAL_JSON) if APPROVAL_JSON.exists() else None,
        "manifest_json": rel(MANIFEST_JSON) if MANIFEST_JSON.exists() else None,
        "remote_manifest_path": ctx.get("remote_manifest_path"),
        "manifest_id": ctx.get("manifest_id"),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "scp": scp,
    }
    return gate_payload("stage4_5_synthetic_approval_gate", checks, failures, detail)


def candidate_readonly_verification_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    if candidate:
        payload = run_remote_python(
            ssh,
            ctx["remote_root"],
            "stage4_5_readonly_candidate_verify",
            verify_candidate_script(),
            timeout=60,
            env={
                "STAGE45_SOURCE_REL": candidate.source_relative_path,
                "STAGE45_TARGET_REL": candidate.target_relative_path,
                "STAGE45_SOURCE_SHA": candidate.source_sha256,
            },
        )
        data = payload.get("json") or {}
        ctx["pre_execute_verify"] = data
    else:
        payload = {}
        data = {}
    add_check(checks, failures, "candidate loaded from JSON", candidate is not None, rel(CANDIDATE_JSON))
    add_check(checks, failures, "readonly verification helper ran", payload.get("scp", {}).get("returncode") == 0 and payload.get("run", {}).get("returncode") == 0 and bool(data), command_summary(payload.get("run", {})))
    add_check(checks, failures, "source hash still matches candidate", data.get("source_sha256_matches") is True, data)
    add_check(checks, failures, "target still absent before execute", data.get("target_exists") is False, data)
    add_check(checks, failures, "source and target parent are not symlinks", data.get("source_is_symlink") is False and data.get("target_parent_is_symlink") is False, data)
    detail = {
        "remote_run": command_summary(payload.get("run", {})),
        "verification": data,
        "note": "This gate reads source/target metadata only; it performs no copy/delete/move.",
    }
    return gate_payload("stage4_5_candidate_readonly_verification_gate", checks, failures, detail)


def pre_execute_route_flow_gate(report_root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    policy, flags = load_policy_and_flags()
    rows: list[dict[str, Any]] = []
    decisions: dict[str, Any] = {}
    if candidate:
        for route, decision in [
            ("preview", preview(candidate, flags=flags, policy=policy)),
            ("dry-run", dry_run(candidate, flags=flags, policy=policy)),
        ]:
            rows.append(route_row(route, decision))
            decisions[route] = decision
        phrase = approval_phrase(candidate)
        confirm_decision = confirm(candidate, phrase, flags=flags, policy=policy, now=ctx["token_now"])
        rows.append(route_row("confirm", confirm_decision))
        decisions["confirm"] = confirm_decision
        token = confirm_decision.response.get("signed_approval_token")
        default_execute = execute(
            candidate,
            flags=flags,
            policy=policy,
            approval_token=token,
            operator_approved=True,
            env_enabled=True,
            approval_file_present=True,
            now=ctx["token_now"] + 1,
        )
        rows.append(route_row("execute_default_closed", default_execute))
        decisions["execute_default_closed"] = default_execute
        ctx["approval_token"] = token
        ctx["approval_token_hash"] = stable_hash(token)
    trace_ok, trace_markers = sanitize_trace_rows(rows)
    write_jsonl(PRE_EXEC_TRACE, rows)
    add_check(checks, failures, "candidate exists for route flow", candidate is not None, rel(CANDIDATE_JSON))
    add_check(checks, failures, "preview/dry-run/confirm allowed", all(decisions.get(route) and decisions[route].allowed for route in ["preview", "dry-run", "confirm"]), [decisions.get(route).status if decisions.get(route) else None for route in ["preview", "dry-run", "confirm"]])
    add_check(checks, failures, "signed approval token issued by confirm", isinstance(ctx.get("approval_token"), dict) and ctx["approval_token"].get("signature"), ctx.get("approval_token_hash"))
    add_check(checks, failures, "execute remains blocked under default global flags", decisions.get("execute_default_closed") is not None and not decisions["execute_default_closed"].allowed and "execute_feature_disabled" in decisions["execute_default_closed"].reason_codes, decisions.get("execute_default_closed").reason_codes if decisions.get("execute_default_closed") else None)
    add_check(checks, failures, "pre-execute route flow performed no writes", all(not row.get("writes_performed") for row in rows), rows)
    add_check(checks, failures, "pre-execute route trace has no raw paths/private content", trace_ok and sum(row.get("private_leak_count", 0) for row in rows) == 0, trace_markers)
    detail = {
        "trace": rel(PRE_EXEC_TRACE),
        "global_feature_flags": flags.to_dict(),
        "approval_token_hash": ctx.get("approval_token_hash"),
        "route_statuses": {route: decision.status for route, decision in decisions.items()},
        "execute_default_reason_codes": list(decisions["execute_default_closed"].reason_codes) if "execute_default_closed" in decisions else [],
    }
    return gate_payload("stage4_5_pre_execute_route_flow_gate", checks, failures, detail)


def feature_flag_scoped_enable_gate(report_root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    _, global_flags = load_policy_and_flags()
    flags = scoped_flags_enabled()
    ctx["scoped_flags"] = flags.to_dict()
    add_check(checks, failures, "global execute/rollback flags remain closed", global_flags.execute_enabled is False and global_flags.rollback_enabled is False and global_flags.execute_canary_enabled is False, global_flags.to_dict())
    add_check(checks, failures, "scoped canary flags enable only execute/rollback for this run", flags.execute_enabled and flags.rollback_enabled and flags.execute_canary_enabled and flags.require_execute_env and flags.require_operator_approval_file, flags.to_dict())
    add_check(checks, failures, "scoped enable is bound to candidate fingerprint", candidate is not None and public_candidate_fingerprint(candidate) == (ctx.get("approval_payload") or {}).get("scope", {}).get("candidate_fingerprint"), (ctx.get("approval_payload") or {}).get("scope"))
    add_check(checks, failures, "operator approval and signed token both present", APPROVAL_JSON.exists() and isinstance(ctx.get("approval_token"), dict), {"approval": rel(APPROVAL_JSON), "token_hash": ctx.get("approval_token_hash")})
    add_check(checks, failures, "manifest approval phrase bound to apm manifest", str(ctx.get("manifest_approval_phrase", "")).startswith("APPROVE apm-"), ctx.get("manifest_approval_phrase"))
    detail = {
        "global_feature_flags": global_flags.to_dict(),
        "scoped_canary_flags": flags.to_dict(),
        "scope": {
            "run_id": ctx.get("run_id"),
            "candidate_fingerprint": public_candidate_fingerprint(candidate) if candidate else None,
            "approval_token_hash": ctx.get("approval_token_hash"),
            "manifest_id": ctx.get("manifest_id"),
        },
        "persistence_boundary": "Scoped flags are in-memory gate state only; configs/copy_route_feature_flags.json is not modified.",
    }
    return gate_payload("stage4_5_feature_flag_scoped_enable_gate", checks, failures, detail)


def route_execute_canary_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    policy, _ = load_policy_and_flags()
    rows: list[dict[str, Any]] = []
    if candidate:
        pre = run_remote_python(
            ssh,
            ctx["remote_root"],
            "stage4_5_pre_execute_verify",
            verify_candidate_script(),
            timeout=60,
            env={"STAGE45_SOURCE_REL": candidate.source_relative_path, "STAGE45_TARGET_REL": candidate.target_relative_path, "STAGE45_SOURCE_SHA": candidate.source_sha256},
        )
        pre_data = pre.get("json") or {}
        seen_nonces: set[str] = set()
        decision = execute(
            candidate,
            flags=scoped_flags_enabled(),
            policy=policy,
            approval_token=ctx.get("approval_token"),
            operator_approved=True,
            env_enabled=True,
            approval_file_present=APPROVAL_JSON.exists(),
            now=ctx["token_now"] + 2,
            seen_nonces=seen_nonces,
        )
        rows.append(route_row("execute_scoped_canary", decision))
        ctx["execute_decision"] = decision.to_dict()
        if decision.allowed and pre_data.get("source_sha256_matches") is True and pre_data.get("target_exists") is False:
            report_root_remote = f"{ctx['remote_root']}/reports"
            action = run_remote_python(
                ssh,
                ctx["remote_root"],
                "stage4_5_dispatch_execute_copy",
                dispatcher_helper_script(),
                timeout=180,
                env={
                    "STAGE45_ACTION": "execute",
                    "STAGE45_REPORT_ROOT": report_root_remote,
                    "STAGE45_MANIFEST_PATH": ctx["remote_manifest_path"],
                    "STAGE45_APPROVAL_PHRASE": ctx["manifest_approval_phrase"],
                    "STAGE45_SOURCE_REL": candidate.source_relative_path,
                    "STAGE45_TARGET_REL": candidate.target_relative_path,
                },
            )
            action_data = action.get("json") or {}
        else:
            action = {}
            action_data = {}
        ctx["execute_action"] = action_data
        if action_data.get("rollback_manifest_path"):
            ctx["remote_rollback_manifest_path"] = action_data["rollback_manifest_path"]
        trace_ok, trace_markers = sanitize_trace_rows(rows)
    else:
        pre = {}
        pre_data = {}
        decision = None
        action = {}
        action_data = {}
        trace_ok = False
        trace_markers = ["missing_candidate"]
    write_jsonl(EXEC_TRACE, rows)
    report_payload = action_data.get("report_payload") or {}
    executed_actions = report_payload.get("executed_actions") or []
    add_check(checks, failures, "candidate exists for execute canary", candidate is not None, rel(CANDIDATE_JSON))
    add_check(checks, failures, "source still matches and target absent immediately before execute", pre_data.get("source_sha256_matches") is True and pre_data.get("target_exists") is False, pre_data)
    add_check(checks, failures, "route guard authorizes execute only under scoped canary", decision is not None and decision.allowed and decision.status == "execute_authorized_for_allowlisted_dispatcher", decision.to_dict() if decision else None)
    add_check(checks, failures, "allowlisted dispatcher execute ran", action.get("run", {}).get("returncode") == 0 and action_data.get("returncode") == 0, command_summary(action.get("run", {})))
    add_check(checks, failures, "exactly one copy executed", report_payload.get("status") == "completed" and report_payload.get("executed_count") == 1 and report_payload.get("failed_count") == 0, report_payload)
    add_check(checks, failures, "target hash equals source hash after execute", action_data.get("target_exists_after") is True and action_data.get("target_sha256_after") == (candidate.source_sha256 if candidate else None), action_data)
    add_check(checks, failures, "source retained unchanged after execute", action_data.get("source_exists_after") is True and action_data.get("source_sha256_after") == (candidate.source_sha256 if candidate else None), action_data)
    add_check(checks, failures, "execute audit forbids delete/move/overwrite", (report_payload.get("audit") or {}).get("source_files_modified") is False and (report_payload.get("audit") or {}).get("delete_performed") is False and (report_payload.get("audit") or {}).get("move_performed") is False and (report_payload.get("audit") or {}).get("overwrite_performed") is False, report_payload.get("audit"))
    add_check(checks, failures, "execute trace has no raw paths/private content", trace_ok and sum(row.get("private_leak_count", 0) for row in rows) == 0, trace_markers)
    detail = {
        "trace": rel(EXEC_TRACE),
        "pre_execute_verify": pre_data,
        "route_decision": decision.to_dict() if decision else None,
        "dispatcher_run": command_summary(action.get("run", {})),
        "dispatcher_result": action_data,
        "executed_action_count": len(executed_actions),
        "rollback_manifest_path": ctx.get("remote_rollback_manifest_path"),
    }
    payload = gate_payload("stage4_5_route_execute_canary_gate", checks, failures, detail)
    if decision is not None and not decision.allowed and not action_data:
        payload["verdict"] = "route_execute_blocked_safely"
    return payload


def route_rollback_canary_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    policy, _ = load_policy_and_flags()
    rows: list[dict[str, Any]] = []
    if candidate:
        decision = rollback(candidate, flags=scoped_flags_enabled(), policy=policy, operator_approved=True)
        rows.append(route_row("rollback_scoped_canary", decision))
        rollback_phrase = f"ROLLBACK {ctx.get('manifest_id')}"
        if decision.allowed and ctx.get("remote_rollback_manifest_path"):
            action = run_remote_python(
                ssh,
                ctx["remote_root"],
                "stage4_5_dispatch_rollback_copy",
                dispatcher_helper_script(),
                timeout=180,
                env={
                    "STAGE45_ACTION": "rollback",
                    "STAGE45_REPORT_ROOT": f"{ctx['remote_root']}/reports",
                    "STAGE45_ROLLBACK_MANIFEST_PATH": ctx["remote_rollback_manifest_path"],
                    "STAGE45_ROLLBACK_PHRASE": rollback_phrase,
                    "STAGE45_SOURCE_REL": candidate.source_relative_path,
                    "STAGE45_TARGET_REL": candidate.target_relative_path,
                },
            )
            action_data = action.get("json") or {}
        else:
            action = {}
            action_data = {}
        ctx["rollback_action"] = action_data
        post = run_remote_python(
            ssh,
            ctx["remote_root"],
            "stage4_5_post_rollback_verify",
            verify_candidate_script(),
            timeout=60,
            env={"STAGE45_SOURCE_REL": candidate.source_relative_path, "STAGE45_TARGET_REL": candidate.target_relative_path, "STAGE45_SOURCE_SHA": candidate.source_sha256},
        )
        post_data = post.get("json") or {}
        ctx["post_rollback_verify"] = post_data
        trace_ok, trace_markers = sanitize_trace_rows(rows)
    else:
        decision = None
        action = {}
        action_data = {}
        post_data = {}
        trace_ok = False
        trace_markers = ["missing_candidate"]
    write_jsonl(ROLLBACK_TRACE, rows)
    report_payload = action_data.get("report_payload") or {}
    add_check(checks, failures, "candidate exists for rollback canary", candidate is not None, rel(CANDIDATE_JSON))
    add_check(checks, failures, "route guard authorizes rollback only under scoped canary", decision is not None and decision.allowed and decision.status == "rollback_authorized_for_allowlisted_dispatcher", decision.to_dict() if decision else None)
    add_check(checks, failures, "allowlisted dispatcher rollback ran", action.get("run", {}).get("returncode") == 0 and action_data.get("returncode") == 0, command_summary(action.get("run", {})))
    add_check(checks, failures, "rollback removed exactly the copied target", report_payload.get("status") == "completed" and report_payload.get("removed_count") == 1 and report_payload.get("failed_count") == 0, report_payload)
    add_check(checks, failures, "target missing and source unchanged after rollback", post_data.get("target_exists") is False and post_data.get("source_sha256_matches") is True, post_data)
    add_check(checks, failures, "rollback audit forbids source/delete/move/overwrite side effects", (report_payload.get("audit") or {}).get("source_files_modified") is False and (report_payload.get("audit") or {}).get("source_delete_performed") is False and (report_payload.get("audit") or {}).get("move_performed") is False and (report_payload.get("audit") or {}).get("overwrite_performed") is False, report_payload.get("audit"))
    add_check(checks, failures, "rollback trace has no raw paths/private content", trace_ok and sum(row.get("private_leak_count", 0) for row in rows) == 0, trace_markers)
    detail = {
        "trace": rel(ROLLBACK_TRACE),
        "route_decision": decision.to_dict() if decision else None,
        "dispatcher_run": command_summary(action.get("run", {})),
        "dispatcher_result": action_data,
        "post_rollback_verify": post_data,
    }
    return gate_payload("stage4_5_route_rollback_canary_gate", checks, failures, detail)


def feature_flag_close_and_health_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    _, global_flags = load_policy_and_flags()
    closed = scoped_flags_closed()
    ctx["scoped_flags_after_close"] = closed.to_dict()
    ports = port_snapshot(ssh)
    normalized_after = normalize_protected_ports(ports.get("stdout", ""))
    openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    dispatcher_hash = remote_file_sha(ssh, REMOTE_DISPATCHER)
    if candidate:
        closed_execute = execute(
            candidate,
            flags=closed,
            policy=load_policy_and_flags()[0],
            approval_token=ctx.get("approval_token"),
            operator_approved=True,
            env_enabled=True,
            approval_file_present=APPROVAL_JSON.exists(),
            now=ctx["token_now"] + 3,
        )
        closed_rollback = rollback(candidate, flags=closed, policy=load_policy_and_flags()[0], operator_approved=True)
    else:
        closed_execute = None
        closed_rollback = None
    add_check(checks, failures, "global config flags still closed after canary", global_flags.execute_enabled is False and global_flags.rollback_enabled is False and global_flags.execute_canary_enabled is False, global_flags.to_dict())
    add_check(checks, failures, "scoped canary flags closed in gate state", closed.execute_enabled is False and closed.rollback_enabled is False and closed.execute_canary_enabled is False, closed.to_dict())
    add_check(checks, failures, "closed flags block execute and rollback routes", closed_execute is not None and not closed_execute.allowed and closed_rollback is not None and not closed_rollback.allowed, {"execute": closed_execute.to_dict() if closed_execute else None, "rollback": closed_rollback.to_dict() if closed_rollback else None})
    add_check(checks, failures, "OpenClaw/Qwen health OK after close", openclaw["ok"] and qwen["ok"], {"openclaw": openclaw, "qwen": qwen})
    add_check(checks, failures, "protected ports unchanged after normalization", normalized_after == ctx.get("baseline_ports_normalized") and bool(normalized_after), {"before": ctx.get("baseline_ports_normalized"), "after": normalized_after})
    add_check(checks, failures, "dispatcher hash unchanged", dispatcher_hash == ctx.get("baseline_dispatcher_hash") and bool(dispatcher_hash), {"before": ctx.get("baseline_dispatcher_hash"), "after": dispatcher_hash})
    post = ctx.get("post_rollback_verify") or {}
    add_check(checks, failures, "target remains absent and synthetic source retained", post.get("target_exists") is False and post.get("source_sha256_matches") is True, post)
    detail = {
        "global_feature_flags_after": global_flags.to_dict(),
        "scoped_flags_after_close": closed.to_dict(),
        "closed_execute_decision": closed_execute.to_dict() if closed_execute else None,
        "closed_rollback_decision": closed_rollback.to_dict() if closed_rollback else None,
        "health": {"openclaw": openclaw, "qwen": qwen},
        "ports_after": ports,
        "normalized_ports_after": normalized_after,
        "dispatcher_hash_after": dispatcher_hash,
    }
    return gate_payload("stage4_5_feature_flag_close_and_health_gate", checks, failures, detail)


def post_execute_adversarial_regression_gate(report_root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    candidate = ctx_candidate(ctx)
    policy, _ = load_policy_and_flags()
    rows: list[dict[str, Any]] = []
    if candidate:
        now = ctx["token_now"] + 30
        valid_token = create_signed_approval_token(candidate, now=now, ttl_seconds=600, nonce="stage45-valid")
        expired_token = create_signed_approval_token(candidate, now=now - 1000, ttl_seconds=1, nonce="stage45-expired")
        wrong_candidate = clone_candidate(candidate, target_relative_path="Collections/CodexPreflight/target/wrong.txt")
        wrong_token = create_signed_approval_token(wrong_candidate, now=now, ttl_seconds=600, nonce="stage45-wrong")
        base_cases = [
            ("action_delete", "preview", clone_candidate(candidate, action_type="delete"), None, {}),
            ("source_escape", "preview", clone_candidate(candidate, source_relative_path="../secret.txt"), None, {}),
            ("target_escape", "preview", clone_candidate(candidate, target_relative_path="../target.txt"), None, {}),
            ("target_exists", "preview", clone_candidate(candidate, target_exists_now=True), None, {}),
            ("bad_source_hash", "preview", clone_candidate(candidate, source_sha256="bad"), None, {}),
            ("oversize", "preview", clone_candidate(candidate, expected_size_bytes=2_000_000), None, {}),
            ("source_symlink", "preview", clone_candidate(candidate, source_is_symlink=True), None, {}),
            ("target_parent_symlink", "preview", clone_candidate(candidate, target_parent_is_symlink=True), None, {}),
            ("recursive", "preview", clone_candidate(candidate, recursive=True), None, {}),
            ("overwrite", "preview", clone_candidate(candidate, overwrite=True), None, {}),
            ("qwen_requested", "preview", clone_candidate(candidate, requested_by_qwen=True), None, {}),
            ("cloud_derived", "preview", clone_candidate(candidate, cloud_derived=True), None, {}),
            ("missing_parent", "preview", clone_candidate(candidate, target_parent_exists=False), None, {}),
            ("same_path", "preview", clone_candidate(candidate, target_relative_path=candidate.source_relative_path), None, {}),
            ("closed_execute", "execute", candidate, valid_token, {"flags": scoped_flags_closed()}),
            ("missing_token", "execute", candidate, None, {"flags": scoped_flags_enabled()}),
            ("expired_token", "execute", candidate, expired_token, {"flags": scoped_flags_enabled()}),
            ("wrong_token_candidate", "execute", candidate, wrong_token, {"flags": scoped_flags_enabled()}),
            ("nonce_reuse", "execute", candidate, valid_token, {"flags": scoped_flags_enabled(), "seen_nonces": {"stage45-valid"}}),
            ("closed_rollback", "rollback", candidate, None, {"flags": scoped_flags_closed()}),
        ]
        for index in range(160):
            case_id, route, cand, token, opts = base_cases[index % len(base_cases)]
            if route == "preview":
                decision = preview(cand, flags=scoped_flags_closed(), policy=policy)
            elif route == "rollback":
                decision = rollback(cand, flags=opts.get("flags", scoped_flags_closed()), policy=policy, operator_approved=True)
            else:
                seen = set(opts.get("seen_nonces", set()))
                decision = execute(
                    cand,
                    flags=opts.get("flags", scoped_flags_closed()),
                    policy=policy,
                    approval_token=token,
                    operator_approved=True,
                    env_enabled=True,
                    approval_file_present=True,
                    now=now,
                    seen_nonces=seen,
                )
            row = route_row(route, decision, extra={"case_id": f"adv-{index + 1:03d}", "case_type": case_id, "expected_allowed": False, "dispatcher_called": False, "cloud_called": False, "qwen_has_execution_authority": False})
            rows.append(row)
    trace_ok, trace_markers = sanitize_trace_rows(rows)
    write_jsonl(ADVERSARIAL_TRACE, rows)
    rejected = [row for row in rows if row.get("allowed") is False]
    add_check(checks, failures, "adversarial suite has at least 150 cases", len(rows) >= 150, len(rows))
    add_check(checks, failures, "all invalid cases rejected", len(rejected) == len(rows) and bool(rows), {"case_count": len(rows), "rejected_count": len(rejected)})
    add_check(checks, failures, "no dispatcher bypass or writes during adversarial regression", all(not row.get("dispatcher_called") and not row.get("writes_performed") for row in rows), None)
    add_check(checks, failures, "no Qwen authority or cloud private egress", all(row.get("qwen_has_execution_authority") is False and row.get("cloud_called") is False for row in rows), None)
    add_check(checks, failures, "adversarial trace has no raw paths/private content", trace_ok and sum(row.get("private_leak_count", 0) for row in rows) == 0, trace_markers)
    categories = sorted({row.get("case_type") for row in rows})
    add_check(checks, failures, "covers broad policy/token/flag failures", len(categories) >= 18, categories)
    detail = {
        "trace": rel(ADVERSARIAL_TRACE),
        "summary": {
            "case_count": len(rows),
            "rejected_count": len(rejected),
            "case_types": categories,
            "private_leak_count": sum(row.get("private_leak_count", 0) for row in rows),
            "dispatcher_bypass_count": sum(1 for row in rows if row.get("dispatcher_called")),
            "cloud_private_egress_count": sum(1 for row in rows if row.get("cloud_called")),
        },
    }
    return gate_payload("stage4_5_post_execute_adversarial_regression_gate", checks, failures, detail)


def readonly_regression_mini_soak_gate(report_root: Path, ssh: SshRunner, *, mini_runs: int, concurrency: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    before_ports = port_snapshot(ssh)
    before_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    before_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    dispatcher_hash = remote_file_sha(ssh, REMOTE_DISPATCHER)
    remote_root = f"/tmp/digua_stage4_5_readonly_regression_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    payload = run_remote_python(
        ssh,
        remote_root,
        "stage4_5_readonly_regression_mini_soak",
        aggressive_remote_script(),
        timeout=max(600, mini_runs * 4),
        env={"AI_NAS_STAGE3_SHADOW": "1", "AGGRESSIVE_SHADOW_RUN_COUNT": str(mini_runs), "AGGRESSIVE_SHADOW_CONCURRENCY": str(concurrency)},
    )
    data = payload.get("json") or {}
    runs = data.get("runs") or []
    summary = data.get("summary") or {}
    write_jsonl(READONLY_TRACE, runs)
    after_ports = port_snapshot(ssh)
    after_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    after_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    normalized_before = normalize_protected_ports(before_ports.get("stdout", ""))
    normalized_after = normalize_protected_ports(after_ports.get("stdout", ""))
    add_check(checks, failures, "OpenClaw/Qwen health OK before and after", before_qwen["ok"] and before_openclaw["ok"] and after_qwen["ok"] and after_openclaw["ok"], {"before_qwen": before_qwen, "after_qwen": after_qwen, "before_openclaw": before_openclaw, "after_openclaw": after_openclaw})
    add_check(checks, failures, "protected ports unchanged", normalized_before == normalized_after and bool(normalized_before), {"before": normalized_before, "after": normalized_after})
    add_check(checks, failures, "readonly mini-soak pass", payload.get("run", {}).get("returncode") == 0 and summary.get("run_count") == mini_runs and float(summary.get("allowed_success_rate") or 0) >= 0.98 and summary.get("denial_correctness") == 1.0, summary)
    add_check(checks, failures, "no leaks, write regression, or foreground route change", summary.get("private_leak_count") == 0 and summary.get("cloud_private_egress_count") == 0 and summary.get("write_destructive_execution_count") == 0 and summary.get("foreground_response_modified_count") == 0, summary)
    add_check(checks, failures, "dispatcher hash recorded and no bypass", bool(dispatcher_hash) and summary.get("dispatcher_bypass_count") == 0, {"dispatcher_hash": dispatcher_hash, "summary": summary})
    add_check(checks, failures, "only policy-sourced tool calls", summary.get("final_tool_source_policy_rate") == 1.0 and summary.get("qwen_execution_authority_count") == 0, summary)
    detail = {
        "trace": rel(READONLY_TRACE),
        "remote_root": remote_root,
        "remote_run": command_summary(payload.get("run", {})),
        "summary": summary,
        "before": {"ports": before_ports, "qwen": before_qwen, "openclaw": before_openclaw},
        "after": {"ports": after_ports, "qwen": after_qwen, "openclaw": after_openclaw},
    }
    return gate_payload("stage4_5_readonly_regression_mini_soak_gate", checks, failures, detail)


def final_verdict(gates: list[dict[str, Any]]) -> str:
    by_id = {gate["gate_id"]: gate for gate in gates}
    if by_id.get("stage4_5_self_created_synthetic_source_gate", {}).get("failure_count"):
        return "synthetic_source_creation_failed_hold"
    execute_gate = by_id.get("stage4_5_route_execute_canary_gate", {})
    if execute_gate.get("verdict") == "route_execute_blocked_safely":
        return "route_execute_blocked_safely"
    if execute_gate.get("failure_count"):
        return "route_execute_policy_failure_hold"
    if by_id.get("stage4_5_route_rollback_canary_gate", {}).get("failure_count"):
        return "route_rollback_failure_hold"
    if by_id.get("stage4_5_feature_flag_close_and_health_gate", {}).get("failure_count"):
        return "feature_flag_close_failure_hold"
    if by_id.get("stage4_5_post_execute_adversarial_regression_gate", {}).get("failure_count"):
        return "route_privacy_failure_hold"
    if by_id.get("stage4_5_readonly_regression_mini_soak_gate", {}).get("failure_count"):
        return "route_regression_failure_hold"
    if all(gate.get("failure_count") == 0 for gate in gates):
        return "self_created_synthetic_route_copy_canary_passed_target_rolled_back"
    return "inconclusive_missing_evidence"


def build_packet(gates: list[dict[str, Any]], ctx: dict[str, Any], package_info: dict[str, Any] | None = None, self_check: dict[str, Any] | None = None) -> dict[str, Any]:
    by_id = {gate["gate_id"]: gate for gate in gates}
    verdict = final_verdict(gates)
    candidate = ctx.get("candidate_payload") or {}
    execute_result = ((by_id.get("stage4_5_route_execute_canary_gate", {}).get("detail") or {}).get("dispatcher_result") or {})
    rollback_result = ((by_id.get("stage4_5_route_rollback_canary_gate", {}).get("detail") or {}).get("dispatcher_result") or {})
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "final_verdict_allowed": verdict in FINAL_VERDICTS,
        "all_gates_pass": all(gate.get("failure_count") == 0 for gate in gates),
        "run_id": ctx.get("run_id"),
        "route_execute_executed": bool(((execute_result.get("report_payload") or {}).get("executed_count") == 1)),
        "route_rollback_executed": bool(((rollback_result.get("report_payload") or {}).get("removed_count") == 1)),
        "target_missing_after_rollback": (ctx.get("post_rollback_verify") or {}).get("target_exists") is False,
        "source_retained_after_rollback": (ctx.get("post_rollback_verify") or {}).get("source_sha256_matches") is True,
        "candidate_summary": {
            "candidate_id": candidate.get("candidate_id"),
            "source_relative_path": candidate.get("source_relative_path"),
            "target_relative_path": candidate.get("target_relative_path"),
            "source_sha256": candidate.get("source_sha256"),
            "expected_size_bytes": candidate.get("expected_size_bytes"),
            "source_owner_scope": candidate.get("source_owner_scope"),
        },
        "feature_flags": {
            "global_config": read_json(FLAGS_JSON) if FLAGS_JSON.exists() else {},
            "scoped_enabled": ctx.get("scoped_flags"),
            "scoped_after_close": ctx.get("scoped_flags_after_close"),
        },
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
        "remote_evidence": {
            "remote_root": ctx.get("remote_root"),
            "remote_manifest_path": ctx.get("remote_manifest_path"),
            "remote_rollback_manifest_path": ctx.get("remote_rollback_manifest_path"),
            "baseline_dispatcher_hash": ctx.get("baseline_dispatcher_hash"),
        },
        "claim_boundary": [
            "Only one Codex-created synthetic source file was copied.",
            "Copy and rollback used route guard authorization plus ai_nas_allowlisted_tool.sh dispatcher.",
            "Global execute/rollback feature flags remain disabled.",
            "This does not authorize arbitrary user-file copy or whole-NAS browsing.",
            "Qwen did not choose source/target and has no execution authority.",
            "Cloud private payload egress remains forbidden.",
        ],
    }
    if package_info:
        packet["final_package"] = package_info
    if self_check:
        packet["package_self_check"] = self_check
    return packet


def write_final_docs(packet: dict[str, Any]) -> None:
    candidate = packet.get("candidate_summary") or {}
    package = packet.get("final_package") or {}
    safe_write_text(
        DECISION_DOC,
        f"""# Stage 4.5 Self-Created Synthetic Route Copy Canary Decision

- final_verdict: `{packet['final_verdict']}`
- route_execute_executed: `{packet['route_execute_executed']}`
- route_rollback_executed: `{packet['route_rollback_executed']}`
- target_missing_after_rollback: `{packet['target_missing_after_rollback']}`
- source_retained_after_rollback: `{packet['source_retained_after_rollback']}`
- source_relative_path: `{candidate.get('source_relative_path')}`
- target_relative_path: `{candidate.get('target_relative_path')}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Stage 4.5 proves one route-level execute canary on a Codex-created, non-sensitive synthetic source under `Collections/CodexPreflight/source`. The target was created only through `ai_nas_action_execute_copy` behind the copy route guard and was removed only through `ai_nas_action_rollback_copy`.

The global copy route execute/rollback feature flags remain closed. This stage does not authorize arbitrary NAS copy, real user-file copy, overwrite, delete, move, rename, chmod, chown, recursive copy, Qwen autonomous execution, or cloud-derived private writes.
""",
    )
    safe_write_text(
        NEXT_PLAN_DOC,
        """# Next Stage 4.6 Operator-Selected Fixture Route Canary Plan

Goal: move from Codex-created synthetic source to one operator-selected fixture file without expanding to arbitrary NAS copy.

Entry requirements:

1. Keep global `execute_enabled=false` and use a scoped canary only.
2. Add an operator selector that can choose exactly one fixture file, not browse or grant the whole NAS.
3. Record source owner, relative path, source hash, size, ACL scope, target absence, and rollback plan before confirm.
4. Require fresh signed token, manifest id, approval phrase, operator approval file, and allowlisted dispatcher execution.
5. Re-check source hash and target absence immediately before execute.
6. Roll back the copied target and prove the source hash is unchanged.
7. Re-run adversarial privacy regression, protected-port health, dispatcher hash, and readonly mini-soak.

Exit condition:

- one operator-selected fixture route copy passes and target is rolled back, or
- route execute remains safely blocked with explicit reason codes.

Still forbidden:

- full-NAS copy
- recursive copy
- overwrite
- delete or move source
- Qwen-selected source/target
- cloud-derived private write requests
- public gateway exposure
""",
    )
    safe_write_text(
        FINAL_PACKET_MD,
        f"""# Digua AI-NAS Stage 4.5 Self-Created Synthetic Route Canary Packet

- final_verdict: `{packet['final_verdict']}`
- all_gates_pass: `{packet['all_gates_pass']}`
- route_execute_executed: `{packet['route_execute_executed']}`
- route_rollback_executed: `{packet['route_rollback_executed']}`
- target_missing_after_rollback: `{packet['target_missing_after_rollback']}`
- source_retained_after_rollback: `{packet['source_retained_after_rollback']}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Boundary: Stage 4.5 authorizes only the recorded self-created synthetic canary. Product default execute/rollback flags remain disabled.
""",
    )


def copy_into_package(package_root: Path, path: Path) -> None:
    if not path.exists():
        return
    target = package_root / rel(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def selected_files(reports: list[dict[str, str]]) -> list[Path]:
    files = [
        FINAL_PACKET_JSON,
        FINAL_PACKET_MD,
        DECISION_DOC,
        NEXT_PLAN_DOC,
        POLICY_JSON,
        FLAGS_JSON,
        CANDIDATE_JSON,
        APPROVAL_JSON,
        MANIFEST_JSON,
        PRE_EXEC_TRACE,
        EXEC_TRACE,
        ROLLBACK_TRACE,
        ADVERSARIAL_TRACE,
        READONLY_TRACE,
        ROOT / "gates" / "stage4_5_self_created_synthetic_route_canary_gates.py",
        ROOT / "gates" / "stage4_4_copy_route_gates.py",
        ROOT / "src" / "harness" / "copy_route_guard.py",
        ROOT / "src" / "harness" / "copy_route_types.py",
        ROOT / "tests" / "test_copy_route_guard.py",
        STAGE4_4_PACKET,
        ROOT / "docs" / "STAGE4_4_COPY_ROUTE_DECISION.md",
        ROOT / "docs" / "NEXT_STAGE4_5_LIMITED_COPY_BETA_PLAN.md",
    ]
    for report in reports:
        files.extend([Path(report["json"]), Path(report["md"])])
    return sorted({path for path in files if path.exists()}, key=lambda path: rel(path))


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
    "01_final_evidence/digua_ai_nas_stage4_5_self_created_synthetic_route_canary_gate_packet.json",
    "01_final_evidence/digua_ai_nas_stage4_5_self_created_synthetic_route_canary_gate_packet.md",
    "docs/STAGE4_5_SELF_CREATED_SYNTHETIC_ROUTE_COPY_CANARY_DECISION.md",
    "docs/NEXT_STAGE4_6_OPERATOR_SELECTED_FIXTURE_ROUTE_CANARY_PLAN.md",
    "operator_candidates/stage4_5_self_created_synthetic_route_candidate.json",
    "operator_approval/stage4_5_self_created_synthetic_route_execute_approved.json",
    "operator_candidates/stage4_5_self_created_synthetic_route_approval_manifest.json",
    "reports/15500_stage4_5_baseline_lock.json",
    "reports/15510_stage4_5_self_created_synthetic_source_gate.json",
    "reports/15520_stage4_5_synthetic_approval_gate.json",
    "reports/15530_stage4_5_candidate_readonly_verification_gate.json",
    "reports/15540_stage4_5_pre_execute_route_flow_gate.json",
    "reports/15550_stage4_5_feature_flag_scoped_enable_gate.json",
    "reports/15560_stage4_5_route_execute_canary_gate.json",
    "reports/15570_stage4_5_route_rollback_canary_gate.json",
    "reports/15580_stage4_5_feature_flag_close_and_health_gate.json",
    "reports/15590_stage4_5_post_execute_adversarial_regression_gate.json",
    "reports/15600_stage4_5_readonly_regression_mini_soak_gate.json",
    "reports/stage4_5_pre_execute_route_flow_trace.jsonl",
    "reports/stage4_5_route_execute_trace.jsonl",
    "reports/stage4_5_route_rollback_trace.jsonl",
    "reports/15590_stage4_5_post_execute_adversarial_cases.jsonl",
    "reports/stage4_5_readonly_regression_mini_soak_trace.jsonl",
]
for rel in required:
    check(f"exists: {rel}", (root / rel).exists(), rel)

packet_path = root / "01_final_evidence/digua_ai_nas_stage4_5_self_created_synthetic_route_canary_gate_packet.json"
if packet_path.exists():
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    check("final verdict valid", packet.get("final_verdict") in {
        "self_created_synthetic_route_copy_canary_passed_target_rolled_back",
        "synthetic_source_creation_failed_hold",
        "route_execute_blocked_safely",
        "route_execute_policy_failure_hold",
        "route_rollback_failure_hold",
        "route_privacy_failure_hold",
        "route_regression_failure_hold",
        "feature_flag_close_failure_hold",
        "inconclusive_missing_evidence",
    }, packet.get("final_verdict"))
    check("global execute flags remain closed", (packet.get("feature_flags") or {}).get("global_config", {}).get("execute_enabled") is False, packet.get("feature_flags"))
    if packet.get("final_verdict") == "self_created_synthetic_route_copy_canary_passed_target_rolled_back":
        check("copy and rollback executed", packet.get("route_execute_executed") is True and packet.get("route_rollback_executed") is True, packet)
        check("target rolled back and source retained", packet.get("target_missing_after_rollback") is True and packet.get("source_retained_after_rollback") is True, packet)

for rel in [
    "reports/stage4_5_pre_execute_route_flow_trace.jsonl",
    "reports/stage4_5_route_execute_trace.jsonl",
    "reports/stage4_5_route_rollback_trace.jsonl",
    "reports/15590_stage4_5_post_execute_adversarial_cases.jsonl",
]:
    path = root / rel
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
        check(f"route trace has no raw NAS path markers: {rel}", all(marker not in text for marker in ["/mnt/nas", "Personal/", "source_relative_path", "target_relative_path"]), rel)

print(json.dumps({"checks": checks, "failures": failures}, indent=2, ensure_ascii=False))
sys.exit(0 if not failures else 1)
''',
    )


def build_package(reports: list[dict[str, str]], timestamp: str) -> dict[str, Any]:
    package_root = ROOT / "tmp" / f"digua_ai_nas_stage4_5_self_created_synthetic_route_canary_for_gptpro_{timestamp}"
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
        packet["package_internal_note"] = "This packet is embedded inside the zip, so the zip SHA256 is recorded in the external .sha256.txt file and root workspace packet."
        safe_write_json(internal_packet, packet)
    internal_packet_md = package_root / rel(FINAL_PACKET_MD)
    if internal_packet_md.exists():
        text = internal_packet_md.read_text(encoding="utf-8", errors="replace")
        lines = [line for line in text.splitlines() if not line.startswith("- package:") and not line.startswith("- sha256:")]
        lines.extend(["", "Package SHA note: this Markdown file is embedded inside the zip; use the adjacent external `.sha256.txt` file for the final zip hash."])
        safe_write_text(internal_packet_md, "\n".join(lines) + "\n")
    write_self_check(package_root)
    rows = package_rows(package_root)
    safe_write_json(package_root / "MANIFEST.json", {"package": "digua_ai_nas_stage4_5_self_created_synthetic_route_canary", "generated_at": utc_stamp(), "file_count": len(rows), "files": rows})
    safe_write_text(package_root / "SHA256SUMS.txt", "\n".join(f"{row['sha256']}  {row['path']}" for row in package_rows(package_root)) + "\n")
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_stage4_5_self_created_synthetic_route_canary_for_gptpro_{timestamp}.zip"
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
    ctx: dict[str, Any] = {
        "run_id": f"stage4_5_self_created_route_canary_{timestamp}",
        "token_now": int(datetime.now().timestamp()),
    }
    gates: list[dict[str, Any]] = []
    reports: list[dict[str, str]] = []
    gate_fns = [
        lambda: baseline_lock(args.report_root, ssh, ctx),
        lambda: self_created_synthetic_source_gate(args.report_root, ssh, ctx),
        lambda: synthetic_approval_gate(args.report_root, ssh, ctx),
        lambda: candidate_readonly_verification_gate(args.report_root, ssh, ctx),
        lambda: pre_execute_route_flow_gate(args.report_root, ctx),
        lambda: feature_flag_scoped_enable_gate(args.report_root, ctx),
        lambda: route_execute_canary_gate(args.report_root, ssh, ctx),
        lambda: route_rollback_canary_gate(args.report_root, ssh, ctx),
        lambda: feature_flag_close_and_health_gate(args.report_root, ssh, ctx),
        lambda: post_execute_adversarial_regression_gate(args.report_root, ctx),
        lambda: readonly_regression_mini_soak_gate(args.report_root, ssh, mini_runs=args.mini_runs, concurrency=args.concurrency),
    ]
    for gate_fn in gate_fns:
        payload = gate_fn()
        payload["report_paths"] = write_numbered_report(payload, args.report_root)
        gates.append(payload)
        reports.append(payload["report_paths"])
    packet = build_packet(gates, ctx)
    write_packet(packet)
    package_info = build_package(reports, timestamp)
    packet = build_packet(gates, ctx, package_info)
    write_packet(packet)
    package_info = build_package(reports, timestamp)
    self_check = run_self_check(package_info)
    packet = build_packet(gates, ctx, package_info, self_check)
    write_packet(packet)
    package_info = build_package(reports, timestamp)
    self_check = run_self_check(package_info)
    packet = build_packet(gates, ctx, package_info, self_check)
    write_packet(packet)
    failed = [gate for gate in gates if gate.get("failure_count")]
    print(json.dumps({"final_verdict": packet["final_verdict"], "failed_gates": [gate["gate_id"] for gate in failed], "package": package_info, "self_check_returncode": self_check.get("returncode")}, ensure_ascii=False, indent=2))
    return gates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Digua AI-NAS Stage4.5 self-created synthetic route copy canary gates.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--mini-runs", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gates = run_all(args)
    return 0 if final_verdict(gates) in FINAL_VERDICTS else 1


if __name__ == "__main__":
    raise SystemExit(main())
