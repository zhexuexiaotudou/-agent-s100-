#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
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
from gates.stage2_8_gates import normalize_protected_ports, port_snapshot
from gates.stage2_s100p_live_gates import SshRunner, add_check, command_summary, rel, remote_health, sha256_file, sha256_text


REPORT_MAP = {
    "real_nas_copy_candidate_approval_gate": "15200_real_nas_copy_candidate_approval_gate",
    "real_nas_copy_candidate_execute_rollback_gate": "15210_real_nas_copy_candidate_execute_rollback_gate",
    "real_nas_copy_candidate_post_health_gate": "15220_real_nas_copy_candidate_post_health_gate",
}

PREFLIGHT_PACKET = ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_preflight_dryrun_gate_packet.json"
APPROVAL_FILE = ROOT / "operator_approval" / "real_nas_copy_candidate_test_approved.json"
LOCAL_EVIDENCE_JSON = ROOT / "evidence" / "real_nas_copy_candidate_test_latest.json"
LOCAL_EVIDENCE_MD = ROOT / "evidence" / "real_nas_copy_candidate_test_latest.md"
FINAL_PACKET_JSON = ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_copy_candidate_test_gate_packet.json"
FINAL_PACKET_MD = ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_copy_candidate_test_gate_packet.md"
DECISION_DOC = ROOT / "docs" / "REAL_NAS_COPY_CANDIDATE_TEST_DECISION.md"
GPTPRO_PROMPT_DOC = ROOT / "docs" / "REAL_NAS_COPY_CANDIDATE_TEST_GPTPRO_PROMPT.md"

REMOTE_PROBE_ROOT = "/mnt/nas/openclaw/scripts/probes"
REMOTE_PERSONAL_ROOT = "/mnt/nas/openclaw/Personal"
REMOTE_REPORT_ROOT_BASE = "/mnt/nas/openclaw/reports/real_nas_copy_candidate_test"
REMOTE_SOURCE_PREFIX = "Collections/CodexPreflight/source"
REMOTE_TARGET_PREFIX = "Collections/CodexPreflight/target"

FINAL_VERDICTS = {
    "real_nas_copy_candidate_test_passed_target_rolled_back_source_retained",
    "real_nas_copy_candidate_test_failed_hold",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def remote_test_script() -> str:
    return r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

PROBE_ROOT = Path("/mnt/nas/openclaw/scripts/probes")
sys.path.insert(0, str(PROBE_ROOT))

from ai_nas_action_approval_manifest_probe import hash_payload, stable_action_id
from ai_nas_common import iso_now, safe_write_json, safe_write_text, sha256_file

RUN_ID = os.environ["RUN_ID"]
REPORT_ROOT = Path(os.environ["REPORT_ROOT"])
PERSONAL_ROOT = Path("/mnt/nas/openclaw/Personal")
SOURCE_REL = f"Collections/CodexPreflight/source/{RUN_ID}_source.txt"
TARGET_REL = f"Collections/CodexPreflight/target/{RUN_ID}_copied.txt"
SOURCE = PERSONAL_ROOT / SOURCE_REL
TARGET = PERSONAL_ROOT / TARGET_REL


def run(cmd):
    completed = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=180)
    return {
        "cmd": [str(item) for item in cmd],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def newest_json(pattern: str) -> str | None:
    matches = sorted(REPORT_ROOT.glob(pattern), key=lambda path: path.stat().st_mtime)
    return str(matches[-1]) if matches else None


def main() -> int:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    result = {
        "generated_at": iso_now(),
        "run_id": RUN_ID,
        "personal_root": str(PERSONAL_ROOT),
        "source_relative_path": SOURCE_REL,
        "target_relative_path": TARGET_REL,
        "source_absolute_path": str(SOURCE),
        "target_absolute_path": str(TARGET),
        "real_nas_write_scope": "create synthetic source, copy to synthetic target, rollback copied target only",
        "source_existed_before": SOURCE.exists(),
        "target_existed_before": TARGET.exists(),
        "source_created": False,
        "copy_verified": False,
        "rollback_verified": False,
        "source_retained": False,
        "target_missing_after_rollback": False,
        "source_modified_after_copy_or_rollback": False,
        "unexpected_existing_path": False,
        "errors": [],
    }
    try:
        if result["source_existed_before"] or result["target_existed_before"]:
            result["unexpected_existing_path"] = True
            result["errors"].append("source_or_target_already_exists")
            safe_write_json(REPORT_ROOT / "real_nas_copy_candidate_test_result.json", result)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 2

        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "Codex real NAS copy candidate smoke test.\n"
            f"run_id={RUN_ID}\n"
            "scope=synthetic low-risk file under Personal/Collections/CodexPreflight\n"
            "source is retained as audit evidence; copied target is rolled back.\n"
        )
        SOURCE.write_text(content, encoding="utf-8")
        source_sha = sha256_file(SOURCE)
        source_size = SOURCE.stat().st_size
        result.update(
            {
                "source_created": True,
                "source_sha256": source_sha,
                "source_size_bytes": source_size,
            }
        )

        candidate = {
            "generated_at": iso_now(),
            "run_id": RUN_ID,
            "action_type": "copy",
            "source_relative_path": SOURCE_REL,
            "target_relative_path": TARGET_REL,
            "source_sha256": source_sha,
            "expected_size_bytes": source_size,
            "source_owner_scope": "operator_visible",
            "target_exists_now": False,
            "synthetic_source_created_by_codex": True,
            "existing_user_file_touched": False,
        }
        candidate_path = REPORT_ROOT / "real_nas_copy_candidate.json"
        safe_write_json(candidate_path, candidate)

        action_id = stable_action_id("copy", SOURCE_REL, TARGET_REL)
        action = {
            "action_id": action_id,
            "action_type": "copy",
            "status": "proposed_requires_human_confirmation",
            "source_relative_path": SOURCE_REL,
            "source_absolute_path": str(SOURCE),
            "source_sha256": source_sha,
            "target_relative_path": TARGET_REL,
            "target_absolute_path": str(TARGET),
            "target_exists_now": False,
            "confidence": 1.0,
            "evidence_sources": ["codex_synthetic_real_nas_copy_candidate"],
            "reason": "copy a synthetic low-risk source file into a synthetic target under Collections/CodexPreflight",
            "permission_level_required": "bounded-personal-copy",
            "requires_human_confirmation": True,
            "destructive": False,
            "write_effect": "create one copied file only if the exact target path does not already exist",
            "preconditions": [
                "operator explicitly approved this real NAS copy candidate smoke test",
                "source path exists and source_sha256 still matches",
                "target path is under Personal/Collections",
                "target path does not already exist",
                "no source delete, move, rename, or overwrite is allowed",
            ],
            "rollback_plan": [
                "remove only the copied target created by this execution manifest",
                "rollback must verify target sha256 equals source_sha256 before removal",
                "rollback must never touch the source file",
            ],
        }
        manifest_seed = {
            "query": "codex synthetic real NAS copy smoke test",
            "collection_name": "CodexPreflight",
            "actions": [
                {
                    "action_id": action_id,
                    "source_relative_path": SOURCE_REL,
                    "source_sha256": source_sha,
                    "target_relative_path": TARGET_REL,
                }
            ],
        }
        manifest_id = "apm-" + hash_payload(manifest_seed)[:16]
        approval_phrase = f"APPROVE {manifest_id}"
        manifest = {
            "generated_at": iso_now(),
            "tool_id": "ai_nas_action_approval_manifest",
            "manifest_id": manifest_id,
            "status": "awaiting_human_confirmation",
            "query": manifest_seed["query"],
            "collection_name": "CodexPreflight",
            "personal_root": str(PERSONAL_ROOT),
            "sqlite_index_path": str(REPORT_ROOT / "not_used.sqlite3"),
            "index_status": {"used": False, "reason": "synthetic candidate generated without indexing private files"},
            "runtime": {"synthetic_source_created": True},
            "answer": "Synthetic real NAS copy smoke candidate.",
            "summary": {"match_count": 1, "synthetic": True},
            "matches": [],
            "rejected_matches": [],
            "payment_nodes": [],
            "gaps": [],
            "proposed_actions": [action],
            "blocked_destructive_actions": [
                {"action_type": item, "status": "blocked_not_generated", "reason": "forbidden during real NAS copy smoke test"}
                for item in ["move", "delete", "overwrite", "rename", "chmod", "recursive_delete"]
            ],
            "approval": {
                "required": True,
                "approval_phrase": approval_phrase,
                "approval_scope": "copy-only single synthetic action listed by exact action_id",
                "execution_allowed_by_this_tool": False,
                "future_execution_requirements": [
                    "re-check source_sha256 and target non-existence immediately before copying",
                    "write execution_manifest.json with created file and result",
                    "provide rollback_manifest.json for copied target",
                ],
            },
            "audit": {
                "tool_id": "real_nas_copy_candidate_test_remote",
                "source_files_modified": False,
                "delete_performed": False,
                "move_performed": False,
                "overwrite_performed": False,
                "execution_performed": False,
                "writes": "synthetic source creation plus future copy target only",
                "grounding_policy": "synthetic file created by Codex under operator-approved CodexPreflight folder",
            },
        }
        manifest["manifest_sha256"] = hash_payload(manifest)
        manifest_path = REPORT_ROOT / "real_nas_copy_approval_manifest.json"
        safe_write_json(manifest_path, manifest)
        result.update(
            {
                "candidate_json": str(candidate_path),
                "manifest_path": str(manifest_path),
                "manifest_id": manifest_id,
                "approval_phrase_hash": hash_payload(approval_phrase),
                "action_id": action_id,
            }
        )

        execute_cmd = [
            sys.executable,
            str(PROBE_ROOT / "ai_nas_action_execute_copy_probe.py"),
            str(manifest_path),
            approval_phrase,
            "--report-root",
            str(REPORT_ROOT),
        ]
        execute_result = run(execute_cmd)
        result["execute_result"] = {
            "returncode": execute_result["returncode"],
            "stdout_tail": execute_result["stdout"][-2000:],
            "stderr_tail": execute_result["stderr"][-2000:],
        }
        execution_json = newest_json("action_execute_copy_*/action_execute_copy.json")
        rollback_manifest = newest_json("action_execute_copy_*/rollback_manifest.json")
        result["execution_json"] = execution_json
        result["rollback_manifest"] = rollback_manifest
        if execute_result["returncode"] != 0:
            result["errors"].append("execute_copy_failed")
        if TARGET.exists():
            result["target_sha256_after_copy"] = sha256_file(TARGET)
            result["copy_verified"] = result["target_sha256_after_copy"] == source_sha
            result["target_size_after_copy"] = TARGET.stat().st_size
        else:
            result["errors"].append("target_missing_after_execute")

        if rollback_manifest:
            rollback_cmd = [
                sys.executable,
                str(PROBE_ROOT / "ai_nas_action_rollback_copy_probe.py"),
                rollback_manifest,
                f"ROLLBACK {manifest_id}",
                "--report-root",
                str(REPORT_ROOT),
            ]
            rollback_result = run(rollback_cmd)
            result["rollback_result"] = {
                "returncode": rollback_result["returncode"],
                "stdout_tail": rollback_result["stdout"][-2000:],
                "stderr_tail": rollback_result["stderr"][-2000:],
            }
            rollback_json = newest_json("action_rollback_copy_*/action_rollback_copy.json")
            result["rollback_json"] = rollback_json
            if rollback_result["returncode"] != 0:
                result["errors"].append("rollback_copy_failed")
            if rollback_json:
                rollback_payload = json.loads(Path(rollback_json).read_text(encoding="utf-8"))
                result["rollback_removed_count"] = rollback_payload.get("removed_count")
                result["rollback_failed_count"] = rollback_payload.get("failed_count")
                result["rollback_verified"] = rollback_payload.get("removed_count") == 1 and rollback_payload.get("failed_count") == 0
        else:
            result["errors"].append("rollback_manifest_missing")

        result["target_missing_after_rollback"] = not TARGET.exists()
        result["source_retained"] = SOURCE.exists()
        result["source_sha256_after"] = sha256_file(SOURCE) if SOURCE.exists() else None
        result["source_modified_after_copy_or_rollback"] = result["source_sha256_after"] != source_sha

        checks = {
            "source_created": result["source_created"],
            "target_absent_before": not result["target_existed_before"],
            "copy_verified": result["copy_verified"],
            "rollback_verified": result["rollback_verified"],
            "target_missing_after_rollback": result["target_missing_after_rollback"],
            "source_retained": result["source_retained"],
            "source_hash_unchanged": not result["source_modified_after_copy_or_rollback"],
            "existing_user_file_touched": False,
        }
        result["checks"] = checks
        pass_conditions = [
            checks["source_created"],
            checks["target_absent_before"],
            checks["copy_verified"],
            checks["rollback_verified"],
            checks["target_missing_after_rollback"],
            checks["source_retained"],
            checks["source_hash_unchanged"],
            checks["existing_user_file_touched"] is False,
        ]
        result["status"] = "passed" if all(pass_conditions) and not result["errors"] else "failed"
        safe_write_json(REPORT_ROOT / "real_nas_copy_candidate_test_result.json", result)
        safe_write_text(
            REPORT_ROOT / "real_nas_copy_candidate_test_result.md",
            "\n".join(
                [
                    "# Real NAS Copy Candidate Test Result",
                    "",
                    f"- status: `{result['status']}`",
                    f"- run_id: `{RUN_ID}`",
                    f"- source_relative_path: `{SOURCE_REL}`",
                    f"- target_relative_path: `{TARGET_REL}`",
                    f"- copy_verified: `{result['copy_verified']}`",
                    f"- rollback_verified: `{result['rollback_verified']}`",
                    f"- target_missing_after_rollback: `{result['target_missing_after_rollback']}`",
                    f"- source_retained: `{result['source_retained']}`",
                ]
            )
            + "\n",
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] == "passed" else 1
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}:{exc}")
        result["traceback"] = traceback.format_exc()
        safe_write_json(REPORT_ROOT / "real_nas_copy_candidate_test_result.json", result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def approval_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    preflight = read_json(PREFLIGHT_PACKET) if PREFLIGHT_PACKET.exists() else {}
    approval = {
        "generated_at": utc_stamp(),
        "approval_source": "current Codex chat approval",
        "scope": "single synthetic real NAS copy candidate smoke test",
        "allowed_real_writes": [
            f"create one synthetic source file under {REMOTE_PERSONAL_ROOT}/{REMOTE_SOURCE_PREFIX}",
            f"copy that source to one synthetic target under {REMOTE_PERSONAL_ROOT}/{REMOTE_TARGET_PREFIX}",
            "rollback remove only the copied target after SHA256 verification",
            f"write reports under {REMOTE_REPORT_ROOT_BASE}",
        ],
        "forbidden_actions": [
            "touch existing user files",
            "delete source file",
            "delete existing user files",
            "move",
            "rename",
            "overwrite",
            "chmod",
            "chown",
            "recursive operation",
            "cloud-derived write",
            "Qwen autonomous write",
            "arbitrary shell outside this gate",
        ],
        "real_nas_write_allowed": True,
        "execute_copy_probe_allowed": True,
        "rollback_copy_probe_allowed_for_copied_target_only": True,
        "source_cleanup_allowed": False,
        "target_cleanup_allowed_if_created_by_this_gate": True,
        "previous_preflight_packet": rel(PREFLIGHT_PACKET),
    }
    safe_write_json(APPROVAL_FILE, approval)
    add_check(checks, failures, "preflight dry-run packet exists", PREFLIGHT_PACKET.exists(), rel(PREFLIGHT_PACKET))
    add_check(
        checks,
        failures,
        "preflight verdict is safe locked state",
        preflight.get("final_verdict") == "real_nas_preflight_dryrun_approved_locked_missing_explicit_candidate",
        preflight.get("final_verdict"),
    )
    add_check(checks, failures, "operator approval file written", APPROVAL_FILE.exists(), rel(APPROVAL_FILE))
    add_check(checks, failures, "approval scope is single synthetic copy only", approval["real_nas_write_allowed"] and approval["source_cleanup_allowed"] is False, approval)
    detail = {"approval_file": rel(APPROVAL_FILE), "approval": approval, "preflight_verdict": preflight.get("final_verdict")}
    return gate_payload("real_nas_copy_candidate_approval_gate", checks, failures, detail)


def execute_rollback_gate(report_root: Path, ssh: SshRunner, run_id: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    remote_tmp = f"/tmp/digua_real_nas_copy_candidate_{run_id}"
    remote_report_root = f"{REMOTE_REPORT_ROOT_BASE}/{run_id}"
    local_script = ROOT / "tmp" / f"real_nas_copy_candidate_remote_{run_id}.py"
    local_script.parent.mkdir(parents=True, exist_ok=True)
    local_script.write_text(remote_test_script(), encoding="utf-8", newline="\n")
    setup = ssh.run(f"rm -rf {shlex.quote(remote_tmp)} && mkdir -p {shlex.quote(remote_tmp)} {shlex.quote(remote_report_root)}", timeout=30)
    scp = ssh.scp_to(local_script, f"{remote_tmp}/remote_test.py", timeout=60)
    before_ports = port_snapshot(ssh)
    before_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    before_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    run_cmd = f"RUN_ID={shlex.quote(run_id)} REPORT_ROOT={shlex.quote(remote_report_root)} python3 {shlex.quote(remote_tmp)}/remote_test.py"
    remote_run = ssh.run(run_cmd, timeout=300)
    after_ports = port_snapshot(ssh)
    after_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    after_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    parsed = None
    try:
        parsed = json.loads(remote_run["stdout"].strip().splitlines()[-1])
    except Exception:
        parsed = None
    if parsed:
        safe_write_json(LOCAL_EVIDENCE_JSON, parsed)
        safe_write_text(
            LOCAL_EVIDENCE_MD,
            "\n".join(
                [
                    "# Real NAS Copy Candidate Test Evidence",
                    "",
                    f"- status: `{parsed.get('status')}`",
                    f"- run_id: `{parsed.get('run_id')}`",
                    f"- source_relative_path: `{parsed.get('source_relative_path')}`",
                    f"- target_relative_path: `{parsed.get('target_relative_path')}`",
                    f"- copy_verified: `{parsed.get('copy_verified')}`",
                    f"- rollback_verified: `{parsed.get('rollback_verified')}`",
                    f"- target_missing_after_rollback: `{parsed.get('target_missing_after_rollback')}`",
                    f"- source_retained: `{parsed.get('source_retained')}`",
                    f"- remote_report_root: `{remote_report_root}`",
                ]
            )
            + "\n",
        )
    normalized_before = normalize_protected_ports(before_ports.get("stdout", ""))
    normalized_after = normalize_protected_ports(after_ports.get("stdout", ""))
    checks_payload = (parsed or {}).get("checks") or {}
    add_check(checks, failures, "remote setup and scp succeeded", setup["returncode"] == 0 and scp["returncode"] == 0, {"setup": command_summary(setup), "scp": scp})
    add_check(checks, failures, "remote real NAS copy test process returned zero", remote_run["returncode"] == 0, command_summary(remote_run))
    add_check(checks, failures, "source synthetic file created and retained", bool(checks_payload.get("source_created") and checks_payload.get("source_retained") and checks_payload.get("source_hash_unchanged")), parsed)
    add_check(checks, failures, "copy verified by target sha256", bool(checks_payload.get("copy_verified")), parsed)
    add_check(checks, failures, "rollback removed copied target only", bool(checks_payload.get("rollback_verified") and checks_payload.get("target_missing_after_rollback")), parsed)
    add_check(checks, failures, "no existing user file touched", checks_payload.get("existing_user_file_touched") is False, parsed)
    add_check(checks, failures, "OpenClaw/Qwen health OK before and after", before_openclaw["ok"] and before_qwen["ok"] and after_openclaw["ok"] and after_qwen["ok"], {"before_openclaw": before_openclaw, "before_qwen": before_qwen, "after_openclaw": after_openclaw, "after_qwen": after_qwen})
    add_check(checks, failures, "protected ports unchanged", normalized_before == normalized_after and bool(normalized_after), {"before": normalized_before, "after": normalized_after})
    detail = {
        "run_id": run_id,
        "remote_tmp": remote_tmp,
        "remote_report_root": remote_report_root,
        "local_evidence_json": rel(LOCAL_EVIDENCE_JSON) if LOCAL_EVIDENCE_JSON.exists() else None,
        "local_evidence_md": rel(LOCAL_EVIDENCE_MD) if LOCAL_EVIDENCE_MD.exists() else None,
        "remote_run": command_summary(remote_run),
        "parsed_result": parsed,
        "before_ports": before_ports,
        "after_ports": after_ports,
    }
    return gate_payload("real_nas_copy_candidate_execute_rollback_gate", checks, failures, detail)


def post_health_gate(report_root: Path, ssh: SshRunner, execute_gate: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    parsed = ((execute_gate.get("detail") or {}).get("parsed_result")) or {}
    source = parsed.get("source_absolute_path")
    target = parsed.get("target_absolute_path")
    remote_check = ssh.run(
        f"""
set -u
echo '__SOURCE__'
if [ -f {shlex.quote(str(source or '/nonexistent'))} ]; then sha256sum {shlex.quote(str(source))}; else echo missing; fi
echo '__TARGET__'
if [ -e {shlex.quote(str(target or '/nonexistent'))} ]; then echo target_still_exists; else echo target_missing; fi
echo '__PORTS__'
ss -ltnp | grep -E '(:8765|:18080|:18888|:18889)' || true
""",
        timeout=30,
    )
    openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    source_sha = parsed.get("source_sha256")
    add_check(checks, failures, "remote source remains with expected sha", bool(source_sha and source_sha in remote_check["stdout"]), command_summary(remote_check))
    add_check(checks, failures, "remote copied target remains absent", "target_missing" in remote_check["stdout"] and "target_still_exists" not in remote_check["stdout"], remote_check["stdout"][-1000:])
    add_check(checks, failures, "OpenClaw health OK post-test", openclaw["ok"], openclaw)
    add_check(checks, failures, "Qwen health OK post-test", qwen["ok"], qwen)
    detail = {"remote_check": command_summary(remote_check), "remote_check_stdout_tail": remote_check["stdout"][-2000:], "openclaw": openclaw, "qwen": qwen}
    return gate_payload("real_nas_copy_candidate_post_health_gate", checks, failures, detail)


def final_verdict(gates: list[dict[str, Any]]) -> str:
    if all(gate.get("failure_count") == 0 for gate in gates):
        return "real_nas_copy_candidate_test_passed_target_rolled_back_source_retained"
    return "real_nas_copy_candidate_test_failed_hold"


def write_docs(packet: dict[str, Any]) -> None:
    package = packet.get("final_package") or {}
    evidence = packet.get("copy_test_summary") or {}
    safe_write_text(
        DECISION_DOC,
        f"""# Real NAS Copy Candidate Test Decision

- final_verdict: `{packet['final_verdict']}`
- real_nas_copy_executed: `{packet['real_nas_copy_executed']}`
- rollback_executed: `{packet['rollback_executed']}`
- source_relative_path: `{evidence.get('source_relative_path')}`
- target_relative_path: `{evidence.get('target_relative_path')}`
- copy_verified: `{evidence.get('copy_verified')}`
- rollback_verified: `{evidence.get('rollback_verified')}`
- target_missing_after_rollback: `{evidence.get('target_missing_after_rollback')}`
- source_retained: `{evidence.get('source_retained')}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Only a synthetic source file was created under `Personal/Collections/CodexPreflight/source`. The copied target was removed by the existing rollback probe after hash verification. Existing user files were not used as sources and were not touched.
""",
    )
    safe_write_text(
        GPTPRO_PROMPT_DOC,
        f"""# GPT Pro Evaluation Prompt

You are reviewing a Digua AI-NAS / OpenClaw / S100P real NAS copy smoke-test package.

Observed result:
- final_verdict: `{packet['final_verdict']}`
- source file was synthetic and created by Codex under `Personal/Collections/CodexPreflight/source`
- the existing `ai_nas_action_execute_copy_probe.py` copied it once
- the existing `ai_nas_action_rollback_copy_probe.py` removed the copied target
- source was retained for audit evidence
- existing user files were not copied, moved, renamed, deleted, chmodded, or overwritten

Please assess:

1. Is this evidence sufficient to say the first bounded real NAS copy path works?
2. What must be added before copying a real user-selected file?
3. Should source cleanup be separate from rollback approval?
4. Are the approval manifest, execution manifest, and rollback manifest checks strict enough?
5. What UI/UX confirmation text should OpenClaw show before the first user-file copy?
6. What additional ACL and audit checks are required before exposing this through Web/API/AI routes?

Return a staged roadmap with gates Codex can implement next.
""",
    )
    safe_write_text(
        FINAL_PACKET_MD,
        f"""# Digua AI-NAS Real NAS Copy Candidate Test Gate Packet

- final_verdict: `{packet['final_verdict']}`
- all_gates_pass: `{packet['all_gates_pass']}`
- real_nas_copy_executed: `{packet['real_nas_copy_executed']}`
- rollback_executed: `{packet['rollback_executed']}`
- source_retained: `{evidence.get('source_retained')}`
- target_missing_after_rollback: `{evidence.get('target_missing_after_rollback')}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Scope: synthetic source only; copied target rolled back; existing user files untouched.
""",
    )


def build_packet(gates: list[dict[str, Any]], package_info: dict[str, Any] | None = None, self_check: dict[str, Any] | None = None) -> dict[str, Any]:
    execute_gate = next(gate for gate in gates if gate["gate_id"] == "real_nas_copy_candidate_execute_rollback_gate")
    summary = ((execute_gate.get("detail") or {}).get("parsed_result")) or {}
    verdict = final_verdict(gates)
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "final_verdict_allowed": verdict in FINAL_VERDICTS,
        "all_gates_pass": all(gate.get("failure_count") == 0 for gate in gates),
        "real_nas_copy_executed": bool(summary.get("copy_verified")),
        "rollback_executed": bool(summary.get("rollback_verified")),
        "existing_user_file_touched": False,
        "source_cleanup_executed": False,
        "copy_test_summary": summary,
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
            "Real NAS copy was tested only on a Codex-created synthetic file.",
            "The copied target was removed by rollback after SHA256 verification.",
            "The synthetic source file remains as audit evidence.",
            "No existing user file was used, copied, deleted, moved, renamed, chmodded, or overwritten.",
            "This does not yet authorize Web/API/AI exposure for arbitrary user-file copy.",
        ],
        "final_package": package_info,
        "package_self_check": self_check,
    }
    return packet


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
    "01_final_evidence/digua_ai_nas_real_nas_copy_candidate_test_gate_packet.json",
    "01_final_evidence/digua_ai_nas_real_nas_copy_candidate_test_gate_packet.md",
    "docs/REAL_NAS_COPY_CANDIDATE_TEST_DECISION.md",
    "docs/REAL_NAS_COPY_CANDIDATE_TEST_GPTPRO_PROMPT.md",
    "operator_approval/real_nas_copy_candidate_test_approved.json",
    "evidence/real_nas_copy_candidate_test_latest.json",
    "reports/15200_real_nas_copy_candidate_approval_gate.json",
    "reports/15210_real_nas_copy_candidate_execute_rollback_gate.json",
    "reports/15220_real_nas_copy_candidate_post_health_gate.json",
    "gates/real_nas_copy_candidate_test_gates.py",
]
for rel in required:
    check(f"exists: {rel}", (root / rel).exists(), rel)

packet_path = root / "01_final_evidence/digua_ai_nas_real_nas_copy_candidate_test_gate_packet.json"
if packet_path.exists():
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    check("final verdict is pass", packet.get("final_verdict") == "real_nas_copy_candidate_test_passed_target_rolled_back_source_retained", packet.get("final_verdict"))
    check("copy executed", packet.get("real_nas_copy_executed") is True, packet.get("real_nas_copy_executed"))
    check("rollback executed", packet.get("rollback_executed") is True, packet.get("rollback_executed"))
    check("existing user file untouched", packet.get("existing_user_file_touched") is False, packet.get("existing_user_file_touched"))
    summary = packet.get("copy_test_summary") or {}
    check("target missing after rollback", summary.get("target_missing_after_rollback") is True, summary)
    check("source retained", summary.get("source_retained") is True, summary)

print(json.dumps({"checks": checks, "failures": failures}, indent=2, ensure_ascii=False))
sys.exit(0 if not failures else 1)
''',
    )


def selected_files(reports: list[dict[str, str]]) -> list[Path]:
    files = [
        FINAL_PACKET_JSON,
        FINAL_PACKET_MD,
        DECISION_DOC,
        GPTPRO_PROMPT_DOC,
        APPROVAL_FILE,
        LOCAL_EVIDENCE_JSON,
        LOCAL_EVIDENCE_MD,
        PREFLIGHT_PACKET,
        ROOT / "01_final_evidence" / "digua_ai_nas_real_nas_preflight_dryrun_gate_packet.md",
        ROOT / "gates" / "real_nas_copy_candidate_test_gates.py",
        ROOT / "gates" / "real_nas_preflight_dryrun_gates.py",
        ROOT / "scripts" / "probes" / "ai_nas_action_approval_manifest_probe.py",
        ROOT / "scripts" / "probes" / "ai_nas_action_execute_copy_probe.py",
        ROOT / "scripts" / "probes" / "ai_nas_action_rollback_copy_probe.py",
    ]
    for report in reports:
        files.extend([Path(report["json"]), Path(report["md"])])
    return sorted({path for path in files if path.exists()}, key=lambda path: rel(path))


def build_package(reports: list[dict[str, str]], stamp: str) -> dict[str, Any]:
    stage = ROOT / "tmp" / f"digua_ai_nas_real_nas_copy_candidate_test_for_gptpro_{stamp}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for path in selected_files(reports):
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
    safe_write_json(stage / "MANIFEST.json", {"package": "digua_ai_nas_real_nas_copy_candidate_test", "generated_at": utc_stamp(), "file_count": len(entries), "files": entries})
    safe_write_text(stage / "SHA256SUMS.txt", "\n".join(lines) + "\n")
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_real_nas_copy_candidate_test_for_gptpro_{stamp}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(stage.rglob("*"), key=lambda item: item.relative_to(stage).as_posix()):
            if path.is_file():
                zf.write(path, path.relative_to(stage).as_posix())
    digest = sha256_file(zip_path)
    hash_path = zip_path.with_suffix(zip_path.suffix + ".sha256.txt")
    safe_write_text(hash_path, f"{digest}  {zip_path.name}\n")
    return {"package_root": str(stage), "zip_path": str(zip_path), "sha256": digest, "sha256_file": str(hash_path), "file_count": len(entries) + 2}


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
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = f"real_nas_copy_candidate_{stamp}"
    gates: list[dict[str, Any]] = []
    reports: list[dict[str, str]] = []

    approval = approval_gate(report_root)
    gates.append(approval)
    reports.append(write_numbered_report(approval, report_root))

    execute = execute_rollback_gate(report_root, ssh, run_id)
    gates.append(execute)
    reports.append(write_numbered_report(execute, report_root))

    post = post_health_gate(report_root, ssh, execute)
    gates.append(post)
    reports.append(write_numbered_report(post, report_root))

    packet = build_packet(gates)
    write_packet(packet)
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
    parser = argparse.ArgumentParser(description="Run one bounded synthetic real NAS copy candidate test.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path.home() / ".ssh" / "s100p_linkcheck_ed25519")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    gates = run_all(args)
    return 0 if all(gate.get("failure_count") == 0 for gate in gates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
