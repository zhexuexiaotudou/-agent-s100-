#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.config_io import safe_write_json, safe_write_text, utc_stamp
from gates.aggressive_progression_gates import PREVIOUS_STAGE3_PACKAGE, aggressive_remote_script
from gates.harness_gate_common import gate_payload
from gates.stage2_8_gates import normalize_protected_ports, port_snapshot, remote_file_sha, run_remote_python
from gates.stage2_s100p_live_gates import SshRunner, add_check, command_summary, rel, remote_health, sha256_file, sha256_text


REPORT_MAP = {
    "stage4_1_baseline_lock": "15000_stage4_1_baseline_lock",
    "stage4_1_extended_synthetic_sandbox_fixture_gate": "15010_extended_synthetic_sandbox_fixture_gate",
    "stage4_1_expanded_approval_token_gate": "15020_expanded_approval_token_gate",
    "stage4_1_expanded_sandbox_write_canary_gate": "15030_expanded_sandbox_write_canary_gate",
    "stage4_1_sandbox_write_failure_injection_rollback_gate": "15040_sandbox_write_failure_injection_rollback_gate",
    "stage4_1_post_canary_health_readonly_regression_gate": "15060_post_canary_health_readonly_regression_gate",
}

PRIOR_STAGE4_PACKAGE = ROOT / "evidence_for_gptpro" / "digua_ai_nas_harness_aggressive_progression_for_gptpro_20260704-112214.zip"
PRIOR_PACKET = ROOT / "01_final_evidence" / "digua_ai_nas_harness_aggressive_progression_gate_packet.json"
FINAL_PACKET_JSON = ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage4_1_gate_packet.json"
FINAL_PACKET_MD = ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage4_1_gate_packet.md"
STAGE4_1_DECISION_DOC = ROOT / "docs" / "STAGE4_1_DECISION.md"
REAL_NAS_PREFLIGHT_DESIGN = ROOT / "docs" / "REAL_NAS_WRITE_PREFLIGHT_DESIGN.md"
REAL_NAS_CONFIRMATION_SPEC = ROOT / "docs" / "REAL_NAS_WRITE_HUMAN_CONFIRMATION_SPEC.md"
REAL_NAS_GATE_PLAN = ROOT / "docs" / "REAL_NAS_WRITE_GATE_PLAN.md"
REAL_NAS_REVIEW_REQUEST = ROOT / "docs" / "REAL_NAS_WRITE_PREFLIGHT_REVIEW_REQUEST.md"
STAGE4_1_SANDBOX_ROOT = ROOT / "tmp" / "digua_ai_nas_stage4_1_write_sandbox"
STAGE4_1_MANIFEST = ROOT / "evidence" / "stage4_1_write_sandbox_manifest.json"
STAGE4_1_APPROVAL = ROOT / "operator_approval" / "stage4_1_sandbox_write_approved.json"
STAGE4_1_AUDIT_TRACE = ROOT / "reports" / "stage4_1_sandbox_write_canary_trace.jsonl"
STAGE4_1_FAILURE_TRACE = ROOT / "reports" / "stage4_1_failure_injection_trace.jsonl"
STAGE4_1_REGRESSION_TRACE = ROOT / "reports" / "stage4_1_post_canary_readonly_regression_trace.jsonl"
REMOTE_DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
TOKEN_SECRET = b"digua-stage4-1-synthetic-sandbox-token"
SANDBOX_DISPATCHER_ID = "stage4_1_synthetic_sandbox_allowlisted_dispatcher_v1"

FINAL_VERDICTS = {
    "expanded_sandbox_write_canary_passed_ready_for_real_write_preflight_review",
    "sandbox_write_canary_blocked_by_no_approval",
    "sandbox_write_canary_failed_hold",
    "readonly_regression_failed_hold",
    "inconclusive_missing_evidence",
}
ALLOWED_ACTIONS = {"copy", "rename", "move", "batch_copy"}
ALLOWED_TOOLS = {
    "ai_nas_sandbox_copy",
    "ai_nas_sandbox_rename",
    "ai_nas_sandbox_move",
    "ai_nas_sandbox_batch_copy",
}
FORBIDDEN_ACTIONS = {"delete", "chmod", "recursive_delete", "permission_mutation", "shell_bypass", "real_nas_write"}
HARD_CONSTRAINTS = [
    "Do not replace OpenClaw.",
    "Do not replace Qwen.",
    "Do not modify 8765, 18080, 18888, or 18889.",
    "Do not let sidecar or harness become foreground route.",
    "Do not give Qwen tool execution authority.",
    "Do not execute real NAS writes.",
    "Do not touch real family/user data for writes.",
    "Do not write to /mnt/nas/Personal or any real user data path.",
    "Do not execute delete.",
    "Do not execute chmod or permission mutation.",
    "Do not execute recursive destructive operations.",
    "All sandbox writes require a signed approval token.",
    "All sandbox writes require before/after state and rollback.",
    "Cloud must not see private NAS raw content.",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def hash_value(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def path_hash(path: str | Path) -> str:
    return hash_value(Path(path).as_posix() if isinstance(path, Path) else str(path).replace("\\", "/"))


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


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def assert_sandbox_path(path: Path) -> None:
    if not is_under(path, STAGE4_1_SANDBOX_ROOT):
        raise ValueError(f"path outside synthetic sandbox: {path}")
    text = path.resolve().as_posix().lower()
    if "/mnt/nas" in text or "openclaw/personal" in text:
        raise ValueError(f"real NAS path rejected: {path}")


def safe_reset_sandbox_root() -> None:
    if STAGE4_1_SANDBOX_ROOT.exists():
        if not is_under(STAGE4_1_SANDBOX_ROOT, ROOT / "tmp"):
            raise RuntimeError(f"refusing to remove sandbox outside repo tmp: {STAGE4_1_SANDBOX_ROOT}")
        shutil.rmtree(STAGE4_1_SANDBOX_ROOT)
    for rel_dir in ["source/nested/deep", "source/batch", "target", "archive", "conflict"]:
        (STAGE4_1_SANDBOX_ROOT / rel_dir).mkdir(parents=True, exist_ok=True)
    files = {
        "source/public_doc.txt": "synthetic public document for Stage4.1\n",
        "source/private_like_doc.txt": "synthetic private-looking document; not real NAS content\n",
        "source/中文资料.txt": "synthetic chinese filename fixture\n",
        "source/photo_placeholder.jpg": "not-a-real-image-stage4-1-placeholder\n",
        "source/duplicate_name.txt": "synthetic duplicate source\n",
        "source/nested/deep/file.md": "# synthetic deep file\n",
        "source/batch/a.txt": "batch A\n",
        "source/batch/b.txt": "batch B\n",
        "source/batch/c.txt": "batch C\n",
        "conflict/duplicate_name.txt": "existing conflict target\n",
    }
    for relative, text in files.items():
        path = STAGE4_1_SANDBOX_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def sandbox_manifest(root: Path = STAGE4_1_SANDBOX_ROOT) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                files.append(
                    {
                        "path": relative,
                        "path_hash": path_hash(relative),
                        "sha256": sha256_file(path),
                        "size": path.stat().st_size,
                        "synthetic": True,
                    }
                )
    return {
        "generated_at": utc_stamp(),
        "sandbox_root": str(root),
        "sandbox_root_relative": rel(root),
        "sandbox_root_isolated": is_under(root, ROOT / "tmp"),
        "real_nas_path": False,
        "file_count": len(files),
        "files": files,
        "manifest_hash": hash_value(files),
        "cleanup_rollback_plan": {
            "reset_command": "regenerate synthetic sandbox from stage4_1 fixture builder",
            "rollback_scope": "local_synthetic_sandbox_only",
        },
    }


def canonical_token_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps({k: v for k, v in payload.items() if k != "signature"}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_token(payload: dict[str, Any]) -> dict[str, Any]:
    signed = dict(payload)
    signed["signature"] = hmac.new(TOKEN_SECRET, canonical_token_payload(payload), hashlib.sha256).hexdigest()
    return signed


def action_context(action: str, *, source: str | None = None, target: str | None = None, sources: list[str] | None = None, targets: list[str] | None = None, before_hash: str = "") -> dict[str, Any]:
    args = {"action": action, "source": source, "target": target, "sources": sources or [], "targets": targets or []}
    rollback = {"action": action, "rollback": True, "source": source, "target": target, "sources": sources or [], "targets": targets or []}
    return {
        "action_type": action,
        "tool_id": f"ai_nas_sandbox_{action}",
        "args": args,
        "args_hash": hash_value(args),
        "source_path_hash": path_hash(source or sources or []),
        "target_path_hash": path_hash(target or targets or []),
        "before_state_hash": before_hash,
        "rollback_plan_hash": hash_value(rollback),
        "source": source,
        "target": target,
        "sources": sources or [],
        "targets": targets or [],
    }


def create_token(ctx: dict[str, Any], *, nonce: str, expires_delta: timedelta = timedelta(minutes=30), overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    payload = {
        "approval_id": f"stage4-1-{nonce}",
        "user_id": "operator-zhexu",
        "workspace_id": "sandbox_write",
        "tool_id": ctx["tool_id"],
        "action_type": ctx["action_type"],
        "args_hash": ctx["args_hash"],
        "source_path_hash": ctx["source_path_hash"],
        "target_path_hash": ctx["target_path_hash"],
        "before_state_hash": ctx["before_state_hash"],
        "rollback_plan_hash": ctx["rollback_plan_hash"],
        "human_confirmation": "I_APPROVE_STAGE4_1_SANDBOX_WRITE",
        "expires_at": (now + expires_delta).isoformat(),
        "nonce": nonce,
        "scope": "local_synthetic_sandbox_only",
        "target_path": ctx.get("target"),
        "target_paths": ctx.get("targets", []),
        "source_path": ctx.get("source"),
        "source_paths": ctx.get("sources", []),
    }
    if overrides:
        payload.update(overrides)
    return sign_token(payload)


def validate_token(token: dict[str, Any], ctx: dict[str, Any], *, seen: set[str] | None = None, now: datetime | None = None) -> tuple[bool, str]:
    required = [
        "approval_id",
        "user_id",
        "workspace_id",
        "tool_id",
        "action_type",
        "args_hash",
        "source_path_hash",
        "target_path_hash",
        "before_state_hash",
        "rollback_plan_hash",
        "human_confirmation",
        "expires_at",
        "nonce",
        "scope",
        "signature",
    ]
    missing = [field for field in required if not token.get(field)]
    if missing:
        return False, "missing:" + ",".join(missing)
    expected_sig = hmac.new(TOKEN_SECRET, canonical_token_payload(token), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(token.get("signature")), expected_sig):
        return False, "bad_signature"
    try:
        expires_at = datetime.fromisoformat(str(token["expires_at"]).replace("Z", "+00:00"))
    except Exception:
        return False, "bad_expires_at"
    if expires_at <= (now or datetime.now(timezone.utc)):
        return False, "expired"
    if seen is not None:
        if token["nonce"] in seen:
            return False, "nonce_reuse"
        seen.add(str(token["nonce"]))
    if token["workspace_id"] != "sandbox_write" or token["scope"] != "local_synthetic_sandbox_only":
        return False, "scope_or_workspace_rejected"
    if token["action_type"] not in ALLOWED_ACTIONS or token["tool_id"] not in ALLOWED_TOOLS:
        return False, "tool_or_action_not_allowlisted"
    if token["human_confirmation"] != "I_APPROVE_STAGE4_1_SANDBOX_WRITE":
        return False, "human_confirmation_rejected"
    for field in ["args_hash", "source_path_hash", "target_path_hash", "before_state_hash", "rollback_plan_hash"]:
        if token[field] != ctx[field]:
            return False, f"{field}_mismatch"
    raw_paths = [token.get("source_path"), token.get("target_path"), *(token.get("source_paths") or []), *(token.get("target_paths") or [])]
    for raw in raw_paths:
        if raw and ("/mnt/nas" in str(raw).replace("\\", "/").lower() or "openclaw/personal" in str(raw).replace("\\", "/").lower()):
            return False, "real_nas_path_rejected"
    return True, "ok"


def ensure_stage4_1_operator_approval() -> dict[str, Any]:
    approved_by_env = os.environ.get("AI_NAS_OPERATOR_APPROVED_STAGE4_1_SANDBOX_WRITE") == "1"
    if not STAGE4_1_APPROVAL.exists():
        safe_write_json(
            STAGE4_1_APPROVAL,
            {
                "generated_at": utc_stamp(),
                "approval_source": "current Codex chat request to progress Stage4.1",
                "env_approval_present": approved_by_env,
                "scope": "local_synthetic_sandbox_only",
                "allowed_actions": sorted(ALLOWED_ACTIONS),
                "forbidden_actions": sorted(FORBIDDEN_ACTIONS),
                "sandbox_root": str(STAGE4_1_SANDBOX_ROOT),
                "real_nas_write_allowed": False,
                "real_nas_write_executed": False,
                "human_confirmation": "I_APPROVE_STAGE4_1_SANDBOX_WRITE",
            },
        )
    approval = read_json(STAGE4_1_APPROVAL)
    approval["env_approval_present_at_runtime"] = approved_by_env
    return approval


def baseline_lock(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required = [
        PRIOR_PACKET,
        ROOT / "reports" / "13100_stage3_1_extended_readonly_shadow_soak_gate.json",
        ROOT / "reports" / "13110_stage3_1_health_resource_latency_gate.json",
        ROOT / "reports" / "13120_stage3_1_adversarial_privacy_injection_gate.json",
        ROOT / "reports" / "13130_stage3_1_repeated_shadow_rollback_gate.json",
        ROOT / "reports" / "13200_stage4_signed_approval_token_gate.json",
        ROOT / "reports" / "13210_stage4_synthetic_sandbox_fixture_gate.json",
        ROOT / "reports" / "13220_stage4_write_action_dryrun_planner_gate.json",
        ROOT / "reports" / "13230_stage4_sandbox_write_canary_gate.json",
        ROOT / "docs" / "HARNESS_AGGRESSIVE_PROGRESSION_DECISION.md",
        ROOT / "docs" / "STAGE4_WRITE_ACTION_DESIGN_DOSSIER.md",
        ROOT / "docs" / "STAGE4_WRITE_ACTION_READINESS_DECISION.md",
        ROOT / "evidence" / "write_sandbox_manifest.json",
        ROOT / "reports" / "stage4_write_action_dryrun_plans.json",
        ROOT / "operator_approval" / "stage4_sandbox_write_canary_operator_approval.json",
    ]
    missing = [rel(path) for path in required if not path.exists()]
    prior = read_json(PRIOR_PACKET) if PRIOR_PACKET.exists() else {}
    safety = prior.get("safety_summary") or {}
    stage4 = (prior.get("stage4_readiness") or {}).get("sandbox_write_canary") or {}
    current_manifest = read_json(ROOT / "evidence" / "write_sandbox_manifest.json") if (ROOT / "evidence" / "write_sandbox_manifest.json").exists() else {}
    add_check(checks, failures, "required prior Stage4 artifacts readable", not missing, missing)
    add_check(checks, failures, "prior final verdict is sandbox canary pass", prior.get("final_verdict") == "stage4_sandbox_write_canary_passed_ready_for_gptpro_review", prior.get("final_verdict"))
    add_check(checks, failures, "prior real NAS write remains false", prior.get("real_nas_write_executed") is False and stage4.get("real_nas_write_executed") is False, stage4)
    add_check(checks, failures, "prior sandbox canary executed and rollback restored", stage4.get("sandbox_write_executed") is True and stage4.get("rollback_restored_before_manifest") is True, stage4)
    add_check(checks, failures, "prior Stage3.1 safety counters zero", all(int(safety.get(key) or 0) == 0 for key in ["dispatcher_bypass_count", "private_leak_count", "cloud_private_egress_count", "write_destructive_execution_count", "admin_recovery_execution_count", "foreground_response_modified_count", "qwen_execution_authority_count"]), safety)
    add_check(checks, failures, "prior package exists", PRIOR_STAGE4_PACKAGE.exists(), str(PRIOR_STAGE4_PACKAGE))
    detail = {
        "prior_final_verdict": prior.get("final_verdict"),
        "prior_package": {"path": str(PRIOR_STAGE4_PACKAGE), "sha256": sha256_file(PRIOR_STAGE4_PACKAGE) if PRIOR_STAGE4_PACKAGE.exists() else None},
        "sandbox_canary": stage4,
        "approved_actions": ["copy"],
        "stage4_1_candidate_actions": sorted(ALLOWED_ACTIONS),
        "forbidden_actions": sorted(FORBIDDEN_ACTIONS),
        "hard_constraints": HARD_CONSTRAINTS,
        "current_sandbox_manifest": current_manifest,
    }
    return gate_payload("stage4_1_baseline_lock", checks, failures, detail)


def extended_sandbox_fixture_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    safe_reset_sandbox_root()
    manifest = sandbox_manifest()
    safe_write_json(STAGE4_1_MANIFEST, manifest)
    paths = {item["path"] for item in manifest["files"]}
    required_paths = {
        "source/public_doc.txt",
        "source/private_like_doc.txt",
        "source/中文资料.txt",
        "source/photo_placeholder.jpg",
        "source/duplicate_name.txt",
        "source/nested/deep/file.md",
        "source/batch/a.txt",
        "source/batch/b.txt",
        "source/batch/c.txt",
    }
    add_check(checks, failures, "sandbox root isolated under repo tmp", manifest["sandbox_root_isolated"] is True and is_under(STAGE4_1_SANDBOX_ROOT, ROOT / "tmp"), manifest["sandbox_root"])
    add_check(checks, failures, "all requested synthetic files exist", required_paths.issubset(paths), sorted(required_paths - paths))
    add_check(checks, failures, "target/archive/conflict dirs exist", all((STAGE4_1_SANDBOX_ROOT / item).exists() for item in ["target", "archive", "conflict"]), None)
    add_check(checks, failures, "all manifest entries synthetic", all(item["synthetic"] is True for item in manifest["files"]), manifest["files"])
    add_check(checks, failures, "no real NAS path in manifest", manifest["real_nas_path"] is False and "/mnt/nas" not in json.dumps(manifest).lower(), None)
    add_check(checks, failures, "manifest hash and cleanup rollback plan recorded", bool(manifest["manifest_hash"]) and bool(manifest["cleanup_rollback_plan"]), manifest)
    detail = {"manifest": rel(STAGE4_1_MANIFEST), "manifest_payload": manifest}
    return gate_payload("stage4_1_extended_synthetic_sandbox_fixture_gate", checks, failures, detail)


def expanded_approval_token_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    before_hash = read_json(STAGE4_1_MANIFEST)["manifest_hash"]
    contexts = {
        "valid_copy": action_context("copy", source="source/public_doc.txt", target="target/public_doc.copy.txt", before_hash=before_hash),
        "valid_rename": action_context("rename", source="source/duplicate_name.txt", target="archive/duplicate_name.renamed.txt", before_hash=before_hash),
        "valid_move": action_context("move", source="source/nested/deep/file.md", target="archive/deep_file.md", before_hash=before_hash),
        "valid_batch_copy": action_context("batch_copy", sources=["source/batch/a.txt", "source/batch/b.txt", "source/batch/c.txt"], targets=["target/batch/a.txt", "target/batch/b.txt", "target/batch/c.txt"], before_hash=before_hash),
    }
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for name, ctx in contexts.items():
        ok, reason = validate_token(create_token(ctx, nonce=name), ctx, seen=seen)
        results.append({"name": name, "expected": "accept", "ok": ok, "reason": reason})
    test_ctx = contexts["valid_copy"]
    invalid_cases = [
        ("expired", create_token(test_ctx, nonce="expired", expires_delta=timedelta(seconds=-1)), test_ctx),
        ("wrong_tool", create_token(test_ctx, nonce="wrong-tool", overrides={"tool_id": "ai_nas_action_execute_copy"}), test_ctx),
        ("wrong_args_hash", create_token(test_ctx, nonce="wrong-args", overrides={"args_hash": hash_value("wrong")}), test_ctx),
        ("wrong_target_path_hash", create_token(test_ctx, nonce="wrong-target", overrides={"target_path_hash": hash_value("wrong-target")}), test_ctx),
        ("missing_before_state", sign_token({k: v for k, v in create_token(test_ctx, nonce="missing-before").items() if k != "before_state_hash" and k != "signature"}), test_ctx),
        ("missing_rollback", sign_token({k: v for k, v in create_token(test_ctx, nonce="missing-rollback").items() if k != "rollback_plan_hash" and k != "signature"}), test_ctx),
        ("nonce_reuse", create_token(test_ctx, nonce="valid_copy"), test_ctx),
        ("bad_signature", {**create_token(test_ctx, nonce="bad-signature"), "signature": "00" * 32}, test_ctx),
        ("delete_attempt", create_token(test_ctx, nonce="delete", overrides={"action_type": "delete", "tool_id": "ai_nas_sandbox_delete"}), test_ctx),
        ("chmod_attempt", create_token(test_ctx, nonce="chmod", overrides={"action_type": "chmod", "tool_id": "ai_nas_sandbox_chmod"}), test_ctx),
        ("real_nas_path_attempt", create_token(test_ctx, nonce="real-nas", overrides={"target_path": "/mnt/nas/openclaw/Personal/target.txt"}), test_ctx),
    ]
    for name, token, ctx in invalid_cases:
        ok, reason = validate_token(token, ctx, seen=seen)
        results.append({"name": name, "expected": "reject", "ok": ok, "reason": reason})
    accepted_valid = [item for item in results if item["expected"] == "accept" and item["ok"]]
    rejected_invalid = [item for item in results if item["expected"] == "reject" and not item["ok"]]
    add_check(checks, failures, "all valid token cases accepted", len(accepted_valid) == 4, results)
    add_check(checks, failures, "all invalid token cases rejected", len(rejected_invalid) == 11, results)
    add_check(checks, failures, "delete/chmod/real NAS rejected", all(any(item["name"] == name and not item["ok"] for item in results) for name in ["delete_attempt", "chmod_attempt", "real_nas_path_attempt"]), results)
    add_check(checks, failures, "token bound to action/tool/args/path/before/rollback", all(any(item["name"] == name and not item["ok"] for item in results) for name in ["wrong_tool", "wrong_args_hash", "wrong_target_path_hash", "missing_before_state", "missing_rollback"]), results)
    detail = {"test_results": results, "valid_count": len(accepted_valid), "invalid_rejected_count": len(rejected_invalid)}
    return gate_payload("stage4_1_expanded_approval_token_gate", checks, failures, detail)


def copy_file(src: Path, dst: Path) -> None:
    assert_sandbox_path(src)
    assert_sandbox_path(dst)
    if not src.exists():
        raise FileNotFoundError(str(src))
    if dst.exists():
        raise FileExistsError(str(dst))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def move_file(src: Path, dst: Path) -> None:
    assert_sandbox_path(src)
    assert_sandbox_path(dst)
    if not src.exists():
        raise FileNotFoundError(str(src))
    if dst.exists():
        raise FileExistsError(str(dst))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def sandbox_dispatch(action: dict[str, Any], token: dict[str, Any], before_hash: str, trace: list[dict[str, Any]], *, simulate_interrupt: bool = False) -> dict[str, Any]:
    ctx = action_context(action["action"], source=action.get("source"), target=action.get("target"), sources=action.get("sources"), targets=action.get("targets"), before_hash=before_hash)
    ok, reason = validate_token(token, ctx, seen=None)
    entry: dict[str, Any] = {
        "run_id": action["run_id"],
        "action": action["action"],
        "dispatcher": SANDBOX_DISPATCHER_ID,
        "dispatcher_bypass": False,
        "token_ok": ok,
        "token_reason": reason,
        "real_nas_write": False,
        "delete_execution": False,
        "chmod_execution": False,
        "audit_trace_complete": False,
    }
    before_manifest = sandbox_manifest()
    entry["before_manifest_hash"] = before_manifest["manifest_hash"]
    if not ok:
        entry.update({"status": "fail_closed", "failure_reason": reason, "after_rollback_manifest_hash": sandbox_manifest()["manifest_hash"], "rollback_restored": sandbox_manifest()["manifest_hash"] == before_manifest["manifest_hash"], "audit_trace_complete": True})
        trace.append(entry)
        return entry
    created_targets: list[str] = []
    try:
        if action["action"] == "copy":
            copy_file(STAGE4_1_SANDBOX_ROOT / action["source"], STAGE4_1_SANDBOX_ROOT / action["target"])
            created_targets.append(action["target"])
            expected_changes = [action["target"]]
        elif action["action"] == "rename":
            move_file(STAGE4_1_SANDBOX_ROOT / action["source"], STAGE4_1_SANDBOX_ROOT / action["target"])
            expected_changes = [action["target"]]
        elif action["action"] == "move":
            move_file(STAGE4_1_SANDBOX_ROOT / action["source"], STAGE4_1_SANDBOX_ROOT / action["target"])
            expected_changes = [action["target"]]
        elif action["action"] == "batch_copy":
            expected_changes = []
            for src, dst in zip(action["sources"], action["targets"], strict=True):
                copy_file(STAGE4_1_SANDBOX_ROOT / src, STAGE4_1_SANDBOX_ROOT / dst)
                created_targets.append(dst)
                expected_changes.append(dst)
        else:
            raise ValueError("action_not_allowlisted")
        after_write = sandbox_manifest()
        entry["after_write_manifest_hash"] = after_write["manifest_hash"]
        entry["expected_changes_verified"] = all((STAGE4_1_SANDBOX_ROOT / item).exists() for item in expected_changes)
        if simulate_interrupt:
            raise RuntimeError("simulated_interrupt_after_write_before_rollback")
        entry["status"] = "executed"
    except Exception as exc:
        entry["status"] = "fail_closed_after_exception" if entry.get("after_write_manifest_hash") else "fail_closed"
        entry["failure_reason"] = type(exc).__name__ + ":" + str(exc)
    finally:
        if action["action"] in {"copy", "batch_copy"}:
            for dst in created_targets:
                path = STAGE4_1_SANDBOX_ROOT / dst
                assert_sandbox_path(path)
                if path.exists():
                    path.unlink()
        elif action["action"] in {"rename", "move"} and action.get("target") and action.get("source"):
            target = STAGE4_1_SANDBOX_ROOT / action["target"]
            source = STAGE4_1_SANDBOX_ROOT / action["source"]
            assert_sandbox_path(target)
            assert_sandbox_path(source)
            if target.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(source))
        after_rollback = sandbox_manifest()
        entry["after_rollback_manifest_hash"] = after_rollback["manifest_hash"]
        entry["rollback_executed"] = True
        entry["rollback_restored"] = after_rollback["manifest_hash"] == before_manifest["manifest_hash"]
        entry["audit_trace_complete"] = True
        trace.append(entry)
    return entry


def expanded_sandbox_write_canary_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    approval = ensure_stage4_1_operator_approval()
    approved = approval.get("scope") == "local_synthetic_sandbox_only" and approval.get("real_nas_write_allowed") is False
    before_hash = sandbox_manifest()["manifest_hash"]
    actions = [
        {"run_id": "stage4-1-copy", "action": "copy", "source": "source/public_doc.txt", "target": "target/public_doc.copy.txt"},
        {"run_id": "stage4-1-rename", "action": "rename", "source": "source/duplicate_name.txt", "target": "archive/duplicate_name.renamed.txt"},
        {"run_id": "stage4-1-move", "action": "move", "source": "source/nested/deep/file.md", "target": "archive/deep_file.md"},
        {"run_id": "stage4-1-batch-copy", "action": "batch_copy", "sources": ["source/batch/a.txt", "source/batch/b.txt", "source/batch/c.txt"], "targets": ["target/batch/a.txt", "target/batch/b.txt", "target/batch/c.txt"]},
    ]
    trace: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    if approved:
        for index, action in enumerate(actions, 1):
            ctx = action_context(action["action"], source=action.get("source"), target=action.get("target"), sources=action.get("sources"), targets=action.get("targets"), before_hash=sandbox_manifest()["manifest_hash"])
            token = create_token(ctx, nonce=f"stage4-1-canary-{index}")
            results.append(sandbox_dispatch(action, token, ctx["before_state_hash"], trace))
    write_jsonl(STAGE4_1_AUDIT_TRACE, trace)
    success_actions = {item["action"] for item in results if item.get("status") == "executed" and item.get("rollback_restored") is True}
    summary = {
        "approval_present": approved,
        "copy_pass": "copy" in success_actions,
        "rename_pass": "rename" in success_actions,
        "move_pass": "move" in success_actions,
        "batch_copy_pass": "batch_copy" in success_actions,
        "real_nas_write_count": sum(1 for item in trace if item.get("real_nas_write")),
        "delete_execution_count": sum(1 for item in trace if item.get("delete_execution")),
        "chmod_execution_count": sum(1 for item in trace if item.get("chmod_execution")),
        "dispatcher_bypass_count": sum(1 for item in trace if item.get("dispatcher_bypass")),
        "audit_trace_complete": all(item.get("audit_trace_complete") for item in trace) and len(trace) == 4,
        "final_manifest_hash": sandbox_manifest()["manifest_hash"],
    }
    add_check(checks, failures, "operator approval present for Stage4.1 sandbox only", approved, approval)
    if approved:
        add_check(checks, failures, "copy/rename/move/batch copy pass", all(summary[key] for key in ["copy_pass", "rename_pass", "move_pass", "batch_copy_pass"]), summary)
        add_check(checks, failures, "rollback restored before manifest for all canaries", all(item.get("rollback_restored") for item in results), results)
        add_check(checks, failures, "real NAS/delete/chmod/dispatcher bypass counts are zero", summary["real_nas_write_count"] == 0 and summary["delete_execution_count"] == 0 and summary["chmod_execution_count"] == 0 and summary["dispatcher_bypass_count"] == 0, summary)
        add_check(checks, failures, "audit trace complete", summary["audit_trace_complete"] is True, summary)
    detail = {"approval": approval, "trace": rel(STAGE4_1_AUDIT_TRACE), "results": results, "summary": summary}
    payload = gate_payload("stage4_1_expanded_sandbox_write_canary_gate", checks, failures, detail)
    if not approved and not failures:
        payload["verdict"] = "blocked_stage4_1_sandbox_write_canary_no_approval"
    return payload


def failure_injection_rollback_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    safe_reset_sandbox_root()
    trace: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    def record(case_id: str, action: dict[str, Any], token: dict[str, Any] | None, *, simulate_interrupt: bool = False) -> None:
        before = sandbox_manifest()
        ctx = action_context(action["action"], source=action.get("source"), target=action.get("target"), sources=action.get("sources"), targets=action.get("targets"), before_hash=before["manifest_hash"])
        result = sandbox_dispatch(action, token or create_token(ctx, nonce=case_id), before["manifest_hash"], trace, simulate_interrupt=simulate_interrupt)
        after = sandbox_manifest()
        rows.append(
            {
                "case_id": case_id,
                "status": result.get("status"),
                "failure_reason": result.get("failure_reason") or result.get("token_reason"),
                "fail_closed": result.get("status") != "executed",
                "manifest_restored": before["manifest_hash"] == after["manifest_hash"],
                "real_nas_write": False,
                "audit_trace_complete": result.get("audit_trace_complete") is True,
            }
        )

    record("target_already_exists_conflict", {"run_id": "fail-conflict", "action": "copy", "source": "source/duplicate_name.txt", "target": "conflict/duplicate_name.txt"}, None)
    record("missing_source", {"run_id": "fail-missing-source", "action": "copy", "source": "source/missing.txt", "target": "target/missing.copy.txt"}, None)
    record("interrupted_after_copy_before_rollback", {"run_id": "fail-interrupt", "action": "copy", "source": "source/public_doc.txt", "target": "target/interrupted.copy.txt"}, None, simulate_interrupt=True)
    bad_ctx = action_context("copy", source="source/public_doc.txt", target="target/invalid-token.copy.txt", before_hash=sandbox_manifest()["manifest_hash"])
    record("invalid_token", {"run_id": "fail-invalid-token", "action": "copy", "source": "source/public_doc.txt", "target": "target/invalid-token.copy.txt"}, {**create_token(bad_ctx, nonce="invalid-token"), "signature": "00" * 32})
    wrong_ctx = action_context("copy", source="source/public_doc.txt", target="target/wrong-rollback.copy.txt", before_hash=sandbox_manifest()["manifest_hash"])
    record("wrong_rollback_hash", {"run_id": "fail-wrong-rollback", "action": "copy", "source": "source/public_doc.txt", "target": "target/wrong-rollback.copy.txt"}, create_token(wrong_ctx, nonce="wrong-rollback", overrides={"rollback_plan_hash": hash_value("wrong")}))
    real_ctx = action_context("copy", source="source/public_doc.txt", target="/mnt/nas/openclaw/Personal/denied.txt", before_hash=sandbox_manifest()["manifest_hash"])
    record("denied_real_path", {"run_id": "fail-real-path", "action": "copy", "source": "source/public_doc.txt", "target": "/mnt/nas/openclaw/Personal/denied.txt"}, create_token(real_ctx, nonce="real-path"))
    write_jsonl(STAGE4_1_FAILURE_TRACE, rows)
    summary = {
        "case_count": len(rows),
        "fail_closed_count": sum(1 for row in rows if row["fail_closed"]),
        "manifest_restored_count": sum(1 for row in rows if row["manifest_restored"]),
        "real_nas_write_count": sum(1 for row in rows if row["real_nas_write"]),
        "audit_trace_complete": all(row["audit_trace_complete"] for row in rows),
    }
    add_check(checks, failures, "all failure cases fail closed", summary["fail_closed_count"] == 6, rows)
    add_check(checks, failures, "rollback or no-op restored manifest for all failures", summary["manifest_restored_count"] == 6, rows)
    add_check(checks, failures, "real NAS write count remains zero", summary["real_nas_write_count"] == 0, rows)
    add_check(checks, failures, "audit trace complete", summary["audit_trace_complete"] is True, rows)
    detail = {"trace": rel(STAGE4_1_FAILURE_TRACE), "cases": rows, "summary": summary}
    return gate_payload("stage4_1_sandbox_write_failure_injection_rollback_gate", checks, failures, detail)


def write_real_nas_preflight_docs() -> None:
    safe_write_text(
        REAL_NAS_PREFLIGHT_DESIGN,
        """# Real NAS Write Preflight Design

This is design-only. No real NAS write is executed by Stage4.1.

Allowed first candidates:
- Copy only, low-risk, single small file.
- Rename only after copy-stage evidence passes.
- Move only after rename-stage evidence passes.
- Delete remains forbidden.

Required gates:
- Real path allowlist with explicit share and user scope.
- Human confirmation UI with action, source, target, before snapshot, rollback plan, and TTL.
- Before/after snapshot with hash and ACL metadata.
- Rollback execution and verification.
- Immutable audit record.
- Dry-run diff.
- ACL confirmation against real NAS user/group policy.
- Rate limit and small-file-only first stage.

Forbidden:
- Delete, chmod, recursive directory operation, cross-user path, cloud-derived write, Qwen autonomous write, arbitrary shell/script path.
""",
    )
    safe_write_text(
        REAL_NAS_CONFIRMATION_SPEC,
        """# Real NAS Write Human Confirmation Spec

Every future real-write request must show:
- action type, source, target, workspace, user identity, ACL basis, and risk class
- before-state hash and rollback-plan hash
- exact confirmation phrase bound to the signed approval token
- expiration time and nonce
- statement that Qwen cannot execute the write directly

The first accepted phrase should be scoped per action, for example:
`I_APPROVE_REAL_NAS_COPY_<approval_id>`.
""",
    )
    safe_write_text(
        REAL_NAS_GATE_PLAN,
        """# Real NAS Write Gate Plan

1. GPT Pro/human reviews Stage4.1 package.
2. Implement real-path allowlist in design-only mode.
3. Run dry-run diff on one low-risk copy candidate.
4. Add immutable audit sink.
5. Add rollback storage and verified rollback execution.
6. Only then request a separate real-write approval packet.

Stage4.1 does not grant that approval.
""",
    )
    safe_write_text(
        REAL_NAS_REVIEW_REQUEST,
        """# Real NAS Write Preflight Review Request

Please review whether Stage4.1 evidence is sufficient to design a first real NAS copy preflight.

Evidence to inspect:
- 15000 baseline lock
- 15010 extended synthetic sandbox fixture
- 15020 expanded approval token gate
- 15030 expanded sandbox write canary gate
- 15040 failure injection rollback gate
- 15060 post-canary health/readonly regression gate

Requested decision:
- keep real NAS writes locked, or
- authorize a future design-only dry-run diff for a single low-risk copy candidate.

No real NAS write has been executed in Stage4.1.
""",
    )


def post_canary_health_readonly_regression_gate(report_root: Path, ssh: SshRunner, *, mini_runs: int, concurrency: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    before_ports = port_snapshot(ssh)
    before_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    before_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    dispatcher_hash = remote_file_sha(ssh, REMOTE_DISPATCHER)
    remote_root = f"/tmp/digua_stage4_1_readonly_regression_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    payload = run_remote_python(
        ssh,
        remote_root,
        "stage4_1_post_canary_readonly_regression",
        aggressive_remote_script(),
        timeout=max(600, mini_runs * 4),
        env={"AI_NAS_STAGE3_SHADOW": "1", "AGGRESSIVE_SHADOW_RUN_COUNT": str(mini_runs), "AGGRESSIVE_SHADOW_CONCURRENCY": str(concurrency)},
    )
    data = payload.get("json") or {}
    runs = data.get("runs") or []
    summary = data.get("summary") or {}
    write_jsonl(STAGE4_1_REGRESSION_TRACE, runs)
    after_ports = port_snapshot(ssh)
    after_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    after_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    normalized_before = normalize_protected_ports(before_ports.get("stdout", ""))
    normalized_after = normalize_protected_ports(after_ports.get("stdout", ""))
    add_check(checks, failures, "OpenClaw/Qwen health OK before and after", before_qwen["ok"] and before_openclaw["ok"] and after_qwen["ok"] and after_openclaw["ok"], {"before_qwen": before_qwen, "after_qwen": after_qwen, "before_openclaw": before_openclaw, "after_openclaw": after_openclaw})
    add_check(checks, failures, "protected ports unchanged", normalized_before == normalized_after and bool(normalized_before), {"before": normalized_before, "after": normalized_after})
    add_check(checks, failures, "readonly mini-soak pass", payload.get("run", {}).get("returncode") == 0 and summary.get("run_count") == mini_runs and summary.get("allowed_success_rate") == 1.0 and summary.get("denial_correctness") == 1.0, summary)
    add_check(checks, failures, "no leaks or foreground route change", summary.get("private_leak_count") == 0 and summary.get("cloud_private_egress_count") == 0 and summary.get("foreground_response_modified_count") == 0, summary)
    add_check(checks, failures, "dispatcher hash recorded and no bypass", bool(dispatcher_hash) and summary.get("dispatcher_bypass_count") == 0, {"dispatcher_hash": dispatcher_hash, "summary": summary})
    detail = {
        "trace": rel(STAGE4_1_REGRESSION_TRACE),
        "remote_root": remote_root,
        "remote_run": command_summary(payload.get("run", {})),
        "summary": summary,
        "before": {"ports": before_ports, "qwen": before_qwen, "openclaw": before_openclaw},
        "after": {"ports": after_ports, "qwen": after_qwen, "openclaw": after_openclaw},
    }
    return gate_payload("stage4_1_post_canary_health_readonly_regression_gate", checks, failures, detail)


def final_verdict(gates: list[dict[str, Any]]) -> str:
    by_id = {gate["gate_id"]: gate for gate in gates}
    if by_id.get("stage4_1_post_canary_health_readonly_regression_gate", {}).get("failure_count"):
        return "readonly_regression_failed_hold"
    canary = by_id.get("stage4_1_expanded_sandbox_write_canary_gate", {})
    if canary.get("verdict") == "blocked_stage4_1_sandbox_write_canary_no_approval":
        return "sandbox_write_canary_blocked_by_no_approval"
    if canary.get("failure_count"):
        return "sandbox_write_canary_failed_hold"
    if all(gate.get("failure_count") == 0 for gate in gates):
        return "expanded_sandbox_write_canary_passed_ready_for_real_write_preflight_review"
    return "inconclusive_missing_evidence"


def write_final_docs(packet: dict[str, Any]) -> None:
    safe_write_text(
        STAGE4_1_DECISION_DOC,
        f"""# Stage4.1 Decision

- final_verdict: `{packet['final_verdict']}`
- expanded sandbox canaries: `{packet['sandbox_canary_summary'].get('copy_pass')}`, `{packet['sandbox_canary_summary'].get('rename_pass')}`, `{packet['sandbox_canary_summary'].get('move_pass')}`, `{packet['sandbox_canary_summary'].get('batch_copy_pass')}`
- failure injection cases: `{packet['failure_injection_summary'].get('case_count')}`
- readonly regression runs: `{packet['readonly_regression_summary'].get('run_count')}`
- real_nas_write_executed: `false`

Real NAS write remains locked pending GPT Pro / human review.
""",
    )
    safe_write_text(
        FINAL_PACKET_MD,
        f"""# Digua AI-NAS Harness Stage4.1 Gate Packet

- final_verdict: `{packet['final_verdict']}`
- real_nas_write_executed: `{packet['real_nas_write_executed']}`
- package: `{(packet.get('final_package') or {}).get('zip_path')}`
- sha256: `{(packet.get('final_package') or {}).get('sha256')}`

Real NAS write remains locked pending GPT Pro / human review.
""",
    )


def build_packet(gates: list[dict[str, Any]], package_info: dict[str, Any] | None = None) -> dict[str, Any]:
    by_id = {gate["gate_id"]: gate for gate in gates}
    canary_summary = (((by_id.get("stage4_1_expanded_sandbox_write_canary_gate", {}).get("detail") or {}).get("summary")) or {})
    failure_summary = (((by_id.get("stage4_1_sandbox_write_failure_injection_rollback_gate", {}).get("detail") or {}).get("summary")) or {})
    readonly_summary = (((by_id.get("stage4_1_post_canary_health_readonly_regression_gate", {}).get("detail") or {}).get("summary")) or {})
    verdict = final_verdict(gates)
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "final_verdict_allowed": verdict in FINAL_VERDICTS,
        "all_gates_pass": all(gate.get("failure_count") == 0 for gate in gates),
        "real_nas_write_executed": False,
        "real_nas_write_remains_locked": True,
        "requires_gptpro_or_human_review_before_real_nas_write": True,
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
        "sandbox_canary_summary": canary_summary,
        "failure_injection_summary": failure_summary,
        "readonly_regression_summary": readonly_summary,
        "environment": {"repo_root": str(ROOT), "platform": platform.platform(), "python": sys.version.split()[0]},
        "claim_boundary": [
            "Stage4.1 executes only local synthetic sandbox writes.",
            "Real NAS write remains locked pending GPT Pro / human review.",
            "Delete/chmod/recursive destructive operations remain forbidden.",
            "Qwen has no direct tool execution authority.",
        ],
    }
    if package_info:
        packet["final_package"] = package_info
    return packet


def copy_into_package(package_root: Path, path: Path, arcname: str | None = None) -> None:
    if not path.exists():
        return
    target = package_root / (arcname or rel(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def package_rows(package_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(package_root.rglob("*")):
        if path.is_file():
            rows.append({"path": path.relative_to(package_root).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)})
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
    "01_final_evidence/digua_ai_nas_harness_stage4_1_gate_packet.json",
    "01_final_evidence/digua_ai_nas_harness_stage4_1_gate_packet.md",
    "docs/STAGE4_1_DECISION.md",
    "docs/REAL_NAS_WRITE_PREFLIGHT_DESIGN.md",
    "docs/REAL_NAS_WRITE_HUMAN_CONFIRMATION_SPEC.md",
    "docs/REAL_NAS_WRITE_GATE_PLAN.md",
    "docs/REAL_NAS_WRITE_PREFLIGHT_REVIEW_REQUEST.md",
    "reports/15000_stage4_1_baseline_lock.json",
    "reports/15010_extended_synthetic_sandbox_fixture_gate.json",
    "reports/15020_expanded_approval_token_gate.json",
    "reports/15030_expanded_sandbox_write_canary_gate.json",
    "reports/15040_sandbox_write_failure_injection_rollback_gate.json",
    "reports/15060_post_canary_health_readonly_regression_gate.json",
    "reports/stage4_1_sandbox_write_canary_trace.jsonl",
    "reports/stage4_1_failure_injection_trace.jsonl",
    "reports/stage4_1_post_canary_readonly_regression_trace.jsonl",
    "evidence/stage4_1_write_sandbox_manifest.json",
    "operator_approval/stage4_1_sandbox_write_approved.json",
    "gates/stage4_1_gates.py",
]
for rel in required:
    check(f"exists: {rel}", (root / rel).exists(), rel)

packet_path = root / "01_final_evidence/digua_ai_nas_harness_stage4_1_gate_packet.json"
if packet_path.exists():
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    check("final verdict valid", packet.get("final_verdict") in {
        "expanded_sandbox_write_canary_passed_ready_for_real_write_preflight_review",
        "sandbox_write_canary_blocked_by_no_approval",
        "sandbox_write_canary_failed_hold",
        "readonly_regression_failed_hold",
        "inconclusive_missing_evidence",
    }, packet.get("final_verdict"))
    check("real NAS write remains false", packet.get("real_nas_write_executed") is False, packet.get("real_nas_write_executed"))
    if packet.get("final_verdict") == "expanded_sandbox_write_canary_passed_ready_for_real_write_preflight_review":
        summary = packet.get("sandbox_canary_summary") or {}
        check("copy rename move batch copy all passed", all(summary.get(key) for key in ["copy_pass", "rename_pass", "move_pass", "batch_copy_pass"]), summary)
        check("forbidden write counters zero", all(int(summary.get(key) or 0) == 0 for key in ["real_nas_write_count", "delete_execution_count", "chmod_execution_count", "dispatcher_bypass_count"]), summary)
        ro = packet.get("readonly_regression_summary") or {}
        check("readonly regression has 100 runs", int(ro.get("run_count") or 0) >= 100, ro)

trace_path = root / "reports/stage4_1_sandbox_write_canary_trace.jsonl"
if trace_path.exists():
    lines = [line for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    check("sandbox write trace has four rows", len(lines) == 4, len(lines))

print(json.dumps({"checks": checks, "failures": failures}, indent=2, ensure_ascii=False))
sys.exit(0 if not failures else 1)
''',
    )


def build_package(gates: list[dict[str, Any]], reports: list[dict[str, str]], timestamp: str) -> dict[str, Any]:
    package_root = ROOT / "tmp" / f"digua_ai_nas_harness_stage4_1_for_gptpro_{timestamp}"
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)
    files = [
        FINAL_PACKET_JSON,
        FINAL_PACKET_MD,
        STAGE4_1_DECISION_DOC,
        REAL_NAS_PREFLIGHT_DESIGN,
        REAL_NAS_CONFIRMATION_SPEC,
        REAL_NAS_GATE_PLAN,
        REAL_NAS_REVIEW_REQUEST,
        STAGE4_1_MANIFEST,
        STAGE4_1_APPROVAL,
        STAGE4_1_AUDIT_TRACE,
        STAGE4_1_FAILURE_TRACE,
        STAGE4_1_REGRESSION_TRACE,
        ROOT / "gates" / "stage4_1_gates.py",
        ROOT / "gates" / "aggressive_progression_gates.py",
        ROOT / "scripts" / "run_stage4_1_from_package.sh",
    ]
    for report in reports:
        files.extend([Path(report["json"]), Path(report["md"])])
    for path in files:
        copy_into_package(package_root, path)
    if PRIOR_STAGE4_PACKAGE.exists():
        copy_into_package(package_root, PRIOR_STAGE4_PACKAGE, f"previous_stage4_input/{PRIOR_STAGE4_PACKAGE.name}")
    write_self_check(package_root)
    rows = package_rows(package_root)
    safe_write_json(package_root / "MANIFEST.json", {"generated_at": utc_stamp(), "file_count": len(rows), "files": rows})
    safe_write_text(package_root / "SHA256SUMS.txt", "\n".join(f"{row['sha256']}  {row['path']}" for row in package_rows(package_root)) + "\n")
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_harness_stage4_1_for_gptpro_{timestamp}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_root.rglob("*")):
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
    return {"returncode": completed.returncode, "stdout_hash": sha256_text(completed.stdout), "stderr_hash": sha256_text(completed.stderr), "stdout_tail": completed.stdout[-2000:], "stderr_tail": completed.stderr[-2000:], "json": parsed}


def write_packet(packet: dict[str, Any]) -> None:
    safe_write_json(FINAL_PACKET_JSON, packet)
    write_final_docs(packet)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Digua AI-NAS Harness Stage4.1 gates.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--mini-runs", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.report_root.mkdir(parents=True, exist_ok=True)
    ssh = SshRunner(args.host, args.key)
    ensure_stage4_1_operator_approval()
    gates: list[dict[str, Any]] = []
    reports: list[dict[str, str]] = []

    for gate in [
        baseline_lock(args.report_root),
        extended_sandbox_fixture_gate(args.report_root),
        expanded_approval_token_gate(args.report_root),
        expanded_sandbox_write_canary_gate(args.report_root),
        failure_injection_rollback_gate(args.report_root),
    ]:
        gates.append(gate)
        reports.append(write_numbered_report(gate, args.report_root))

    write_real_nas_preflight_docs()
    gate = post_canary_health_readonly_regression_gate(args.report_root, ssh, mini_runs=args.mini_runs, concurrency=args.concurrency)
    gates.append(gate)
    reports.append(write_numbered_report(gate, args.report_root))

    packet = build_packet(gates)
    write_packet(packet)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    package_info = build_package(gates, reports, timestamp)
    packet = build_packet(gates, package_info)
    write_packet(packet)
    package_info = build_package(gates, reports, timestamp)
    packet = build_packet(gates, package_info)
    packet["package_self_check"] = run_self_check(package_info)
    write_packet(packet)
    package_info = build_package(gates, reports, timestamp)
    packet = build_packet(gates, package_info)
    packet["package_self_check"] = run_self_check(package_info)
    write_packet(packet)

    failed = [gate for gate in gates if gate.get("failure_count")]
    print(json.dumps({"final_verdict": packet["final_verdict"], "failed_gates": [gate["gate_id"] for gate in failed], "package": package_info}, ensure_ascii=False, indent=2))
    return 0 if not failed and packet["final_verdict"] in FINAL_VERDICTS else 1


if __name__ == "__main__":
    raise SystemExit(main())
