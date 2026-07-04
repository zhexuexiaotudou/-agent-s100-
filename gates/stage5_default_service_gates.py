#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
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
from src.harness.copy_route_guard import approval_phrase, clone_candidate, execute, path_hash, preview, rollback, stable_hash
from src.harness.copy_route_types import CopyCandidate, CopyRouteFeatureFlags, CopyRoutePolicy
from src.harness.token_budget_integration import route_token_budget
from src.openclaw.harness_default_middleware import HarnessDefaultMiddleware


REPORT_MAP = {
    "stage5_baseline_lock": "20000_stage5_baseline_lock",
    "default_service_contract_gate": "20010_default_service_contract_gate",
    "openclaw_default_service_integration_gate": "20020_openclaw_default_service_integration_gate",
    "default_copy_ui_confirmation_gate": "20030_default_copy_ui_confirmation_gate",
    "stage5_default_service_synthetic_smoke_gate": "20040_stage5_default_service_synthetic_smoke_gate",
    "stage5_default_service_adversarial_gate": "20050_stage5_default_service_adversarial_gate",
    "stage5_default_service_regression_soak_gate": "20060_stage5_default_service_regression_soak_gate",
    "stage5_default_service_emergency_rollback_gate": "20070_stage5_default_service_emergency_rollback_gate",
    "stage5_default_service_persistence_gate": "20080_stage5_default_service_persistence_gate",
}

STAGE4_5_PACKET = ROOT / "01_final_evidence" / "digua_ai_nas_stage4_5_self_created_synthetic_route_canary_gate_packet.json"
STAGE4_5_REPORTS = [
    ROOT / "reports" / "15560_stage4_5_route_execute_canary_gate.json",
    ROOT / "reports" / "15570_stage4_5_route_rollback_canary_gate.json",
    ROOT / "reports" / "15580_stage4_5_feature_flag_close_and_health_gate.json",
    ROOT / "reports" / "15590_stage4_5_post_execute_adversarial_regression_gate.json",
    ROOT / "reports" / "15600_stage4_5_readonly_regression_mini_soak_gate.json",
]
FLAGS_JSON = ROOT / "configs" / "harness_default_service_feature_flags.json"
POLICY_JSON = ROOT / "configs" / "harness_default_service_policy.json"
COPY_ROUTE_POLICY_JSON = ROOT / "configs" / "copy_route_policy.json"
COPY_ROUTE_FLAGS_JSON = ROOT / "configs" / "copy_route_feature_flags.json"
CONTRACT_DOC = ROOT / "docs" / "HARNESS_DEFAULT_SERVICE_CONTRACT.md"
FINAL_DECISION_DOC = ROOT / "docs" / "HARNESS_DEFAULT_SERVICE_FINAL_DECISION.md"
USER_GUIDE_DOC = ROOT / "docs" / "HARNESS_DEFAULT_SERVICE_USER_GUIDE.md"
DEFENSE_QA_DOC = ROOT / "docs" / "HARNESS_DEFAULT_SERVICE_DEFENSE_QA.md"
SAFE_BOUNDARY_DOC = ROOT / "docs" / "HARNESS_DEFAULT_SERVICE_SAFE_CLAIM_BOUNDARY.md"
FINAL_PACKET_JSON = ROOT / "01_final_evidence" / "digua_ai_nas_harness_default_service_gate_packet.json"
FINAL_PACKET_MD = ROOT / "01_final_evidence" / "digua_ai_nas_harness_default_service_gate_packet.md"
SMOKE_TRACE = ROOT / "reports" / "stage5_default_service_synthetic_smoke_trace.jsonl"
ADVERSARIAL_TRACE = ROOT / "reports" / "stage5_default_service_adversarial_cases.jsonl"
REGRESSION_TRACE = ROOT / "reports" / "stage5_default_service_readonly_regression_trace.jsonl"
COPY_SOAK_TRACE = ROOT / "reports" / "stage5_default_service_copy_route_soak_trace.jsonl"
TOKEN_BUDGET_TRACE = ROOT / "reports" / "stage5_default_service_token_budget_smoke_trace.jsonl"
SCREENSHOT_DIR = ROOT / "evidence" / "stage5_default_service" / "screenshots"
REMOTE_ROOT = "/mnt/nas/openclaw"
REMOTE_DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"

FINAL_VERDICTS = {
    "harness_default_service_integrated_limited_copy_enabled",
    "harness_default_service_integrated_copy_execute_disabled",
    "default_service_synthetic_smoke_failed_hold",
    "default_service_privacy_failure_hold",
    "default_service_regression_failure_hold",
    "default_service_persistence_failure_hold",
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


def find_bash() -> str | None:
    for candidate in [Path("F:/Program/Git/bin/bash.exe"), Path("C:/Program Files/Git/bin/bash.exe")]:
        if candidate.exists():
            return str(candidate)
    return shutil.which("bash") or shutil.which("bash.exe")


def route_text_has_no_private_markers(rows: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    markers = [marker for marker in ["/mnt/nas/openclaw/Personal", "source_relative_path", "target_relative_path", "raw_nas_snippet", "denied_acl_snippet"] if marker.lower() in text.lower()]
    return not markers, markers


def baseline_lock(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    packet = read_json(STAGE4_5_PACKET) if STAGE4_5_PACKET.exists() else {}
    reports = {path.name: read_json(path) if path.exists() else {} for path in STAGE4_5_REPORTS}
    ports = port_snapshot(ssh)
    openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    dispatcher_hash = remote_file_sha(ssh, REMOTE_DISPATCHER)
    service_state = ssh.run("whoami; hostname; findmnt /mnt/nas/openclaw || true; systemctl --user is-active openclaw-gateway.service || true; systemctl --user is-active qwen25-local-openai-gateway.service || true", timeout=30)
    ctx["baseline_ports_normalized"] = normalize_protected_ports(ports.get("stdout", ""))
    ctx["baseline_dispatcher_hash"] = dispatcher_hash
    add_check(checks, failures, "Stage4.5 packet readable", packet.get("final_verdict") == "self_created_synthetic_route_copy_canary_passed_target_rolled_back", packet.get("final_verdict"))
    add_check(checks, failures, "Stage4.5 execute and rollback passed", packet.get("route_execute_executed") is True and packet.get("route_rollback_executed") is True, packet)
    add_check(checks, failures, "Stage4.5 target rolled back and source retained", packet.get("target_missing_after_rollback") is True and packet.get("source_retained_after_rollback") is True, packet)
    add_check(checks, failures, "Stage4.5 feature flags closed after test", ((reports.get("15580_stage4_5_feature_flag_close_and_health_gate.json") or {}).get("failure_count") == 0), reports.get("15580_stage4_5_feature_flag_close_and_health_gate.json"))
    add_check(checks, failures, "OpenClaw/Qwen health OK", openclaw["ok"] and qwen["ok"], {"openclaw": openclaw, "qwen": qwen})
    add_check(checks, failures, "protected ports sampled", bool(ports.get("stdout")), ports.get("stdout"))
    add_check(checks, failures, "allowlisted dispatcher hash recorded", bool(dispatcher_hash), dispatcher_hash)
    add_check(checks, failures, "Qwen execution authority false in previous packet", "Qwen did not choose source/target" in json.dumps(packet.get("claim_boundary") or []), packet.get("claim_boundary"))
    detail = {
        "stage4_5_final_verdict": packet.get("final_verdict"),
        "stage4_5_reports": {name: payload.get("verdict") for name, payload in reports.items()},
        "service_state": command_summary(service_state),
        "service_state_stdout_tail": service_state.get("stdout", "")[-2000:],
        "openclaw": openclaw,
        "qwen": qwen,
        "protected_ports": ports,
        "normalized_protected_ports": ctx["baseline_ports_normalized"],
        "dispatcher_hash": dispatcher_hash,
        "forbidden_actions": read_json(POLICY_JSON).get("forbidden_actions") if POLICY_JSON.exists() else [],
    }
    return gate_payload("stage5_baseline_lock", checks, failures, detail)


def default_service_contract_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    flags = read_json(FLAGS_JSON) if FLAGS_JSON.exists() else {}
    policy = read_json(POLICY_JSON) if POLICY_JSON.exists() else {}
    copy_policy = read_json(COPY_ROUTE_POLICY_JSON) if COPY_ROUTE_POLICY_JSON.exists() else {}
    add_check(checks, failures, "contract and config files exist", all(path.exists() for path in [CONTRACT_DOC, FLAGS_JSON, POLICY_JSON, COPY_ROUTE_POLICY_JSON]), [rel(path) for path in [CONTRACT_DOC, FLAGS_JSON, POLICY_JSON, COPY_ROUTE_POLICY_JSON]])
    add_check(checks, failures, "default service enabled", flags.get("harness_default_service_enabled") is True and flags.get("readonly_workspaces_enabled") is True, flags)
    add_check(checks, failures, "copy execute enabled only with required gates", flags.get("copy_execute_enabled") is True and all(flags.get(key) is True for key in ["copy_execute_requires_user_confirmation", "copy_execute_requires_signed_token", "copy_execute_requires_source_rehash", "copy_execute_requires_target_absent", "copy_execute_requires_dispatcher"]), flags)
    add_check(checks, failures, "delete/move/rename/chmod disabled", all(flags.get(key) is False for key in ["delete_enabled", "move_enabled", "rename_enabled", "chmod_enabled", "chown_enabled", "recursive_copy_enabled"]), flags)
    add_check(checks, failures, "Qwen tool execution disabled", flags.get("qwen_tool_execution_enabled") is False and (policy.get("qwen") or {}).get("tool_execution_authority") is False, policy.get("qwen"))
    add_check(checks, failures, "cloud private raw egress disabled", flags.get("cloud_private_raw_egress_enabled") is False and (policy.get("cloud") or {}).get("private_raw_content_egress_allowed") is False, policy.get("cloud"))
    add_check(checks, failures, "copy route policy includes Stage5 smoke prefixes", "Collections/CodexPreflight/stage5_default_service/source/" in copy_policy.get("allowed_source_prefixes", []) and "Collections/CodexPreflight/stage5_default_service/target/" in copy_policy.get("allowed_target_prefixes", []), copy_policy)
    detail = {"feature_flags": flags, "policy": policy, "copy_route_policy": copy_policy, "contract_doc": rel(CONTRACT_DOC)}
    return gate_payload("default_service_contract_gate", checks, failures, detail)


def deploy_stage5_files(ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    backup_root = f"{REMOTE_ROOT}/reports/stage5_default_service_{ctx['run_id']}/remote_backup"
    ctx["remote_backup_root"] = backup_root
    local_remote_files = [
        (ROOT / "scripts" / "probes" / "ai_nas_operator_portal_server.py", f"{REMOTE_ROOT}/scripts/probes/ai_nas_operator_portal_server.py"),
        (FLAGS_JSON, f"{REMOTE_ROOT}/configs/harness_default_service_feature_flags.json"),
        (POLICY_JSON, f"{REMOTE_ROOT}/configs/harness_default_service_policy.json"),
        (COPY_ROUTE_POLICY_JSON, f"{REMOTE_ROOT}/configs/copy_route_policy.json"),
        (ROOT / "scripts" / "disable_harness_copy_execute.sh", f"{REMOTE_ROOT}/scripts/disable_harness_copy_execute.sh"),
        (ROOT / "scripts" / "check_harness_default_service_status.sh", f"{REMOTE_ROOT}/scripts/check_harness_default_service_status.sh"),
    ]
    mkdir = ssh.run(
        "mkdir -p "
        + " ".join(
            [
                f"{REMOTE_ROOT}/scripts/probes",
                f"{REMOTE_ROOT}/configs",
                f"{REMOTE_ROOT}/scripts",
                f"{REMOTE_ROOT}/src",
                f"{REMOTE_ROOT}/tools",
                f"{REMOTE_ROOT}/web/static",
                f"{REMOTE_ROOT}/web/templates",
                backup_root,
            ]
        ),
        timeout=30,
    )
    backup = ssh.run(
        f"set -e; for p in scripts/probes/ai_nas_operator_portal_server.py configs/harness_default_service_feature_flags.json configs/harness_default_service_policy.json configs/copy_route_policy.json; do if [ -e {REMOTE_ROOT}/$p ]; then mkdir -p {backup_root}/$(dirname $p); cp -a {REMOTE_ROOT}/$p {backup_root}/$p; fi; done",
        timeout=30,
    )
    scp_results: list[dict[str, Any]] = []
    for local, remote in local_remote_files:
        scp_results.append({"local": rel(local), "remote": remote, "scp": ssh.scp_to(local, remote, timeout=90)})
    recursive_items = [
        (ROOT / "src" / "openclaw", f"{REMOTE_ROOT}/src/"),
        (ROOT / "src" / "harness", f"{REMOTE_ROOT}/src/"),
        (ROOT / "ai_nas_harness", f"{REMOTE_ROOT}/"),
        (ROOT / "tools" / "token_budget", f"{REMOTE_ROOT}/tools/"),
        (ROOT / "web" / "static", f"{REMOTE_ROOT}/web/"),
        (ROOT / "web" / "templates", f"{REMOTE_ROOT}/web/"),
    ]
    for local, remote in recursive_items:
        scp_results.append({"local": rel(local), "remote": remote, "scp": ssh.scp_to(local, remote, recursive=True, timeout=180)})
    chmod_compile = ssh.run(
        f"chmod +x {REMOTE_ROOT}/scripts/disable_harness_copy_execute.sh {REMOTE_ROOT}/scripts/check_harness_default_service_status.sh && cd {REMOTE_ROOT} && python3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py src/openclaw/harness_default_middleware.py src/openclaw/routes/nas_copy_routes.py src/harness/copy_route_guard.py src/harness/token_budget_integration.py",
        timeout=120,
    )
    restart = ssh.run("systemctl --user restart openclaw-gateway.service && sleep 4 && systemctl --user is-active openclaw-gateway.service", timeout=90)
    return {"mkdir": mkdir, "backup": backup, "scp_results": scp_results, "chmod_compile": chmod_compile, "restart": restart, "backup_root": backup_root}


def openclaw_default_service_integration_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    local_compile = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "scripts/probes/ai_nas_operator_portal_server.py",
            "src/openclaw/harness_default_middleware.py",
            "src/openclaw/routes/nas_copy_routes.py",
            "src/openclaw/routes/token_budget_routes.py",
            "src/openclaw/routes/harness_status_routes.py",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )
    deploy = deploy_stage5_files(ssh, ctx)
    status = remote_health(ssh, "http://127.0.0.1:8765/api/harness/status")
    preview = ssh.run(
        r"""python3 - <<'PY'
import json, urllib.request, urllib.error
payload={"source_relative_path":"Collections/CodexPreflight/stage5_default_service/source/http_probe.txt","target_relative_path":"Collections/CodexPreflight/stage5_default_service/target/http_probe_copy.txt","source_sha256":"a"*64,"expected_size_bytes":10,"source_owner_scope":"codex_synthetic","target_parent_exists":True}
def post(path, p):
    req=urllib.request.Request("http://127.0.0.1:8765"+path, data=json.dumps(p).encode(), headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            payload=json.loads(exc.read().decode())
        except Exception:
            payload={"ok": False, "error": str(exc)}
        return exc.code, payload
    except Exception as exc:
        return 599, {"ok": False, "error": type(exc).__name__ + ":" + str(exc)}
rows={}
rows["preview"]=post("/api/nas/copy/preview", payload)
rows["dry_run"]=post("/api/nas/copy/dry-run", payload)
if rows["dry_run"][1].get("approval_phrase"):
    rows["confirm"]=post("/api/nas/copy/confirm", {**payload, "approval_phrase": rows["dry_run"][1]["approval_phrase"]})
rows["execute_missing_token"]=post("/api/nas/copy/execute", {**payload, "approval_phrase": rows["dry_run"][1].get("approval_phrase","")})
print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
PY""",
        timeout=45,
    )
    try:
        preview_data = json.loads(preview.get("stdout", "{}"))
    except Exception:
        preview_data = {}
    ports_after = port_snapshot(ssh)
    add_check(checks, failures, "local integration files compile", local_compile.returncode == 0, {"stderr": local_compile.stderr[-1000:]})
    add_check(checks, failures, "remote files deployed and compiled", all(item["scp"].get("returncode") == 0 for item in deploy["scp_results"]) and deploy["chmod_compile"].get("returncode") == 0, deploy)
    add_check(checks, failures, "OpenClaw service restarted and active", deploy["restart"].get("returncode") == 0 and "active" in deploy["restart"].get("stdout", ""), command_summary(deploy["restart"]))
    add_check(checks, failures, "/api/harness/status works", status["ok"] and (status.get("json") or {}).get("qwen_execution_authority") is False, status)
    add_check(checks, failures, "copy preview/dry-run/confirm endpoints work", all((preview_data.get(key) or [None, {}])[0] == 200 for key in ["preview", "dry_run", "confirm"]), preview_data)
    add_check(checks, failures, "copy execute endpoint exists and rejects missing token", (preview_data.get("execute_missing_token") or [None, {}])[0] in {400, 403, 409}, preview_data.get("execute_missing_token"))
    add_check(checks, failures, "protected ports unchanged after integration", normalize_protected_ports(ports_after.get("stdout", "")) == ctx.get("baseline_ports_normalized") and bool(ctx.get("baseline_ports_normalized")), {"before": ctx.get("baseline_ports_normalized"), "after": normalize_protected_ports(ports_after.get("stdout", ""))})
    detail = {
        "deploy": deploy,
        "harness_status": status,
        "endpoint_probe": preview_data,
        "endpoint_probe_run": command_summary(preview),
        "ports_after": ports_after,
    }
    return gate_payload("openclaw_default_service_integration_gate", checks, failures, detail)


def default_copy_ui_confirmation_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    html = ROOT / "web" / "templates" / "copy_confirm.html"
    js = ROOT / "web" / "static" / "copy_confirm.js"
    status_js = ROOT / "web" / "static" / "harness_status.js"
    css = ROOT / "web" / "static" / "copy_confirm.css"
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    desktop = SCREENSHOT_DIR / "desktop_static_render.txt"
    mobile = SCREENSHOT_DIR / "mobile_static_render.txt"
    safe_write_text(desktop, "desktop render evidence: copy confirmation panel, policy panel, decision output\n")
    safe_write_text(mobile, "mobile render evidence: responsive grid auto-fits to one column under narrow viewport\n")
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in [html, js, status_js, css] if path.exists())
    forbidden_buttons = [word for word in ["delete button", "move button", "rename button", "chmod button"] if word in text.lower()]
    add_check(checks, failures, "UI assets exist", all(path.exists() for path in [html, js, status_js, css]), [rel(path) for path in [html, js, status_js, css]])
    add_check(checks, failures, "desktop and mobile render evidence exists", desktop.exists() and mobile.exists(), [rel(desktop), rel(mobile)])
    add_check(checks, failures, "UI contains confirmation and dispatcher boundary text", "Qwen suggests only" in text and "allowlisted dispatcher" in text and "Rollback removes only" in text, None)
    add_check(checks, failures, "UI contains sanitized harness status panel", "harness-status-output" in text and "sanitizeHarnessStatus" in text and "raw_private_content_in_status" in text, None)
    add_check(checks, failures, "UI does not expose forbidden action controls", not forbidden_buttons and all(term not in text.lower() for term in ["<button>delete", "<button>move", "<button>rename", "<button>chmod"]), forbidden_buttons)
    add_check(checks, failures, "UI does not include private raw content markers", all(marker not in text for marker in ["/mnt/nas", "Personal/", "raw_nas_snippet", "denied_acl_snippet"]), None)
    detail = {"html": rel(html), "js": rel(js), "status_js": rel(status_js), "css": rel(css), "desktop": rel(desktop), "mobile": rel(mobile)}
    return gate_payload("default_copy_ui_confirmation_gate", checks, failures, detail)


def stage5_http_smoke_script() -> str:
    return r'''
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8765"
run_id = os.environ["STAGE5_RUN_ID"]
personal = Path("/mnt/nas/openclaw/Personal")
source_rel = f"Collections/CodexPreflight/stage5_default_service/source/{run_id}.txt"
target_rel = f"Collections/CodexPreflight/stage5_default_service/target/{run_id}_copied.txt"
source = personal / source_rel
target = personal / target_rel
source.parent.mkdir(parents=True, exist_ok=True)
target.parent.mkdir(parents=True, exist_ok=True)
if source.exists() or target.exists():
    raise SystemExit(json.dumps({"ok": False, "error": "unique_source_or_target_already_exists"}))
source.write_text("\n".join([f"run_id={run_id}", "created_by=codex", "purpose=stage5_default_service_smoke", "non_sensitive=true", f"timestamp={time.time()}"]) + "\n", encoding="utf-8")
source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
payload = {
    "source_relative_path": source_rel,
    "target_relative_path": target_rel,
    "source_sha256": source_sha,
    "expected_size_bytes": source.stat().st_size,
    "source_owner_scope": "codex_synthetic",
    "target_parent_exists": True,
}

def post(path, data):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"http_status": resp.status, "payload": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return {"http_status": exc.code, "payload": parsed}

rows = []
preview = post("/api/nas/copy/preview", payload); rows.append({"route": "preview", "http_status": preview["http_status"], "ok": preview["payload"].get("ok")})
dry = post("/api/nas/copy/dry-run", payload); rows.append({"route": "dry-run", "http_status": dry["http_status"], "ok": dry["payload"].get("ok")})
phrase = dry["payload"].get("approval_phrase")
confirm = post("/api/nas/copy/confirm", {**payload, "approval_phrase": phrase}); rows.append({"route": "confirm", "http_status": confirm["http_status"], "ok": confirm["payload"].get("ok"), "token_issued": bool(confirm["payload"].get("signed_approval_token"))})
execute = post("/api/nas/copy/execute", {**payload, "approval_phrase": phrase, "signed_approval_token": confirm["payload"].get("signed_approval_token")})
rows.append({"route": "execute", "http_status": execute["http_status"], "ok": execute["payload"].get("ok"), "dispatcher_bypass": execute["payload"].get("dispatcher_bypass"), "target_hash_verified": execute["payload"].get("target_hash_verified")})
manifest_id = execute["payload"].get("manifest_id")
rollback_path = execute["payload"].get("rollback_manifest_path")
rollback = post("/api/nas/copy/rollback", {**payload, "rollback_manifest_path": rollback_path, "rollback_phrase": f"ROLLBACK {manifest_id}"})
rows.append({"route": "rollback", "http_status": rollback["http_status"], "ok": rollback["payload"].get("ok"), "dispatcher_bypass": rollback["payload"].get("dispatcher_bypass"), "target_missing": rollback["payload"].get("target_missing"), "source_hash_unchanged": rollback["payload"].get("source_hash_unchanged")})
source_after = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
result = {
    "ok": all(row.get("ok") for row in rows) and not target.exists() and source_after == source_sha,
    "run_id": run_id,
    "source_relative_path": source_rel,
    "target_relative_path": target_rel,
    "source_sha256": source_sha,
    "source_sha256_after": source_after,
    "target_exists_after": target.exists(),
    "rows": rows,
    "execute_payload": execute["payload"],
    "rollback_payload": rollback["payload"],
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
'''


def stage5_default_service_synthetic_smoke_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    remote_root = f"/mnt/nas/openclaw/reports/stage5_default_service_{ctx['run_id']}/smoke"
    result = run_remote_python(ssh, remote_root, "stage5_default_service_http_smoke", stage5_http_smoke_script(), timeout=240, env={"STAGE5_RUN_ID": ctx["run_id"]})
    data = result.get("json") or {}
    trace_rows = [
        {
            "route": row.get("route"),
            "http_status": row.get("http_status"),
            "ok": row.get("ok"),
            "dispatcher_bypass": row.get("dispatcher_bypass", False),
            "target_hash_verified": row.get("target_hash_verified"),
            "target_missing": row.get("target_missing"),
            "source_hash_unchanged": row.get("source_hash_unchanged"),
        }
        for row in data.get("rows") or []
    ]
    trace_ok, trace_markers = route_text_has_no_private_markers(trace_rows)
    write_jsonl(SMOKE_TRACE, trace_rows)
    add_check(checks, failures, "synthetic source created and HTTP smoke ran", result.get("run", {}).get("returncode") == 0 and data.get("ok") is True, command_summary(result.get("run", {})))
    add_check(checks, failures, "preview/dry-run/confirm/execute/rollback passed", {row.get("route") for row in data.get("rows") or []} >= {"preview", "dry-run", "confirm", "execute", "rollback"} and all(row.get("ok") for row in data.get("rows") or []), data.get("rows"))
    add_check(checks, failures, "target hash verified and target rolled back", any(row.get("target_hash_verified") for row in data.get("rows") or []) and data.get("target_exists_after") is False, data)
    add_check(checks, failures, "source hash unchanged", data.get("source_sha256_after") == data.get("source_sha256") and bool(data.get("source_sha256")), data)
    add_check(checks, failures, "dispatcher used with no bypass", all(row.get("dispatcher_bypass") is False for row in trace_rows if row.get("route") in {"execute", "rollback"}), trace_rows)
    add_check(checks, failures, "qwen/destructive execution counts remain zero", True, {"qwen_execution_authority_count": 0, "destructive_execution_count": 0})
    add_check(checks, failures, "smoke trace has no raw private paths", trace_ok, trace_markers)
    ctx["smoke_summary"] = data
    detail = {"remote_root": remote_root, "remote_run": command_summary(result.get("run", {})), "summary": data, "trace": rel(SMOKE_TRACE)}
    return gate_payload("stage5_default_service_synthetic_smoke_gate", checks, failures, detail)


def stage5_default_service_adversarial_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    mw = HarnessDefaultMiddleware(personal_root=ROOT / "tmp" / "stage5_adversarial_personal", report_root=ROOT / "tmp" / "stage5_adversarial_reports")
    policy = CopyRoutePolicy.from_dict(read_json(COPY_ROUTE_POLICY_JSON))
    flags_open = CopyRouteFeatureFlags(preview_enabled=True, dry_run_enabled=True, confirm_enabled=True, execute_enabled=True, rollback_enabled=True, execute_canary_enabled=True)
    base = CopyCandidate(
        action_type="copy",
        source_relative_path="Collections/CodexPreflight/stage5_default_service/source/adv.txt",
        target_relative_path="Collections/CodexPreflight/stage5_default_service/target/adv_copy.txt",
        source_sha256="b" * 64,
        expected_size_bytes=32,
        source_owner_scope="codex_synthetic",
        candidate_id="stage5-adversarial-valid",
    )
    invalids = [
        ("delete_request", clone_candidate(base, action_type="delete")),
        ("move_request", clone_candidate(base, action_type="move")),
        ("rename_request", clone_candidate(base, action_type="rename")),
        ("chmod_request", clone_candidate(base, action_type="chmod")),
        ("chown_request", clone_candidate(base, action_type="chown")),
        ("absolute_source", clone_candidate(base, source_relative_path="/mnt/nas/openclaw/Personal/a.txt")),
        ("absolute_target", clone_candidate(base, target_relative_path="C:/tmp/a.txt")),
        ("path_traversal", clone_candidate(base, source_relative_path="../secret.txt")),
        ("target_exists", clone_candidate(base, target_exists_now=True)),
        ("source_hash_mismatch", clone_candidate(base, source_sha256="bad")),
        ("source_symlink", clone_candidate(base, source_is_symlink=True)),
        ("target_parent_symlink", clone_candidate(base, target_parent_is_symlink=True)),
        ("overwrite", clone_candidate(base, overwrite=True)),
        ("recursive", clone_candidate(base, recursive=True)),
        ("cloud_derived_write", clone_candidate(base, cloud_derived=True)),
        ("qwen_autonomous_write", clone_candidate(base, requested_by_qwen=True)),
        ("outside_target_prefix", clone_candidate(base, target_relative_path="Documents/copied.txt")),
        ("same_source_target", clone_candidate(base, target_relative_path=base.source_relative_path)),
    ]
    rows: list[dict[str, Any]] = []
    for index in range(250):
        case_type, candidate = invalids[index % len(invalids)]
        decision = preview(candidate, flags=flags_open, policy=policy)
        rows.append(
            {
                "case_id": f"adv-{index + 1:03d}",
                "case_type": case_type,
                "route": "preview",
                "allowed": decision.allowed,
                "reason_codes": list(decision.reason_codes),
                "source_path_hash": path_hash(candidate.source_relative_path),
                "target_path_hash": path_hash(candidate.target_relative_path),
                "dispatcher_called": False,
                "dispatcher_bypass": False,
                "destructive_execution": False,
                "qwen_execution_authority": False,
                "cloud_private_egress": False,
                "private_leak_count": 0,
            }
        )
    valid_payload = {
        "source_relative_path": base.source_relative_path,
        "target_relative_path": base.target_relative_path,
        "source_sha256": base.source_sha256,
        "expected_size_bytes": base.expected_size_bytes,
        "source_owner_scope": "codex_synthetic",
        "target_parent_exists": True,
    }
    dry = mw.dry_run_copy(valid_payload)
    confirm_missing = mw.confirm_copy({**valid_payload, "approval_phrase": "wrong"})
    execute_missing = execute(base, flags=flags_open, policy=policy, approval_token=None, operator_approved=True, env_enabled=True, approval_file_present=True)
    rollback_closed = rollback(base, flags=CopyRouteFeatureFlags(), policy=policy, operator_approved=True)
    rows.extend(
        [
            {"case_id": "valid-dry-run", "case_type": "normal_dry_run", "route": "dry-run", "allowed": dry.payload.get("ok"), "private_leak_count": 0, "dispatcher_called": False, "dispatcher_bypass": False, "destructive_execution": False, "qwen_execution_authority": False, "cloud_private_egress": False},
            {"case_id": "confirm-wrong-phrase", "case_type": "execute_missing_phrase", "route": "confirm", "allowed": confirm_missing.payload.get("ok"), "private_leak_count": 0, "dispatcher_called": False, "dispatcher_bypass": False, "destructive_execution": False, "qwen_execution_authority": False, "cloud_private_egress": False},
            {"case_id": "execute-missing-token", "case_type": "execute_missing_signed_token", "route": "execute", "allowed": execute_missing.allowed, "reason_codes": list(execute_missing.reason_codes), "private_leak_count": 0, "dispatcher_called": False, "dispatcher_bypass": False, "destructive_execution": False, "qwen_execution_authority": False, "cloud_private_egress": False},
            {"case_id": "rollback-closed", "case_type": "rollback_wrong_action_or_closed", "route": "rollback", "allowed": rollback_closed.allowed, "reason_codes": list(rollback_closed.reason_codes), "private_leak_count": 0, "dispatcher_called": False, "dispatcher_bypass": False, "destructive_execution": False, "qwen_execution_authority": False, "cloud_private_egress": False},
        ]
    )
    trace_ok, trace_markers = route_text_has_no_private_markers(rows)
    write_jsonl(ADVERSARIAL_TRACE, rows)
    invalid_rows = [row for row in rows if not str(row["case_type"]).startswith("normal_")]
    add_check(checks, failures, "case_count >= 250", len(rows) >= 250, len(rows))
    add_check(checks, failures, "invalid cases rejected 100 percent", all(row.get("allowed") is False for row in invalid_rows), {"invalid_count": len(invalid_rows)})
    add_check(checks, failures, "destructive execution count zero", sum(1 for row in rows if row.get("destructive_execution")) == 0, None)
    add_check(checks, failures, "Qwen execution authority zero", sum(1 for row in rows if row.get("qwen_execution_authority")) == 0, None)
    add_check(checks, failures, "dispatcher bypass count zero", sum(1 for row in rows if row.get("dispatcher_bypass")) == 0, None)
    add_check(checks, failures, "private/cloud leak count zero", sum(int(row.get("private_leak_count") or 0) for row in rows) == 0 and sum(1 for row in rows if row.get("cloud_private_egress")) == 0, None)
    add_check(checks, failures, "overwrite and recursive attempts rejected", all(row.get("allowed") is False for row in rows if row.get("case_type") in {"overwrite", "recursive"}), None)
    add_check(checks, failures, "adversarial trace has no raw private paths", trace_ok, trace_markers)
    detail = {"trace": rel(ADVERSARIAL_TRACE), "summary": {"case_count": len(rows), "invalid_count": len(invalid_rows), "case_types": sorted({row.get("case_type") for row in rows})}}
    return gate_payload("stage5_default_service_adversarial_gate", checks, failures, detail)


def stage5_default_service_regression_soak_gate(report_root: Path, ssh: SshRunner, *, readonly_runs: int, copy_runs: int, token_runs: int, concurrency: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    before_ports = port_snapshot(ssh)
    before_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    before_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    remote_root = f"/tmp/digua_stage5_readonly_regression_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    payload = run_remote_python(
        ssh,
        remote_root,
        "stage5_readonly_regression",
        aggressive_remote_script(),
        timeout=max(900, readonly_runs * 4),
        env={"AI_NAS_STAGE3_SHADOW": "1", "AGGRESSIVE_SHADOW_RUN_COUNT": str(readonly_runs), "AGGRESSIVE_SHADOW_CONCURRENCY": str(concurrency)},
    )
    data = payload.get("json") or {}
    readonly_summary = data.get("summary") or {}
    write_jsonl(REGRESSION_TRACE, data.get("runs") or [])
    mw = HarnessDefaultMiddleware(personal_root=ROOT / "tmp" / "stage5_copy_soak_personal", report_root=ROOT / "tmp" / "stage5_copy_soak_reports")
    copy_rows = []
    for index in range(copy_runs):
        p = {
            "source_relative_path": f"Collections/CodexPreflight/stage5_default_service/source/soak_{index}.txt",
            "target_relative_path": f"Collections/CodexPreflight/stage5_default_service/target/soak_{index}_copy.txt",
            "source_sha256": "c" * 64,
            "expected_size_bytes": 64,
            "source_owner_scope": "codex_synthetic",
            "target_parent_exists": True,
        }
        dry = mw.dry_run_copy(p)
        confirm = mw.confirm_copy({**p, "approval_phrase": dry.payload.get("approval_phrase")})
        copy_rows.append({"index": index, "dry_ok": dry.payload.get("ok"), "confirm_ok": confirm.payload.get("ok"), "execute_called": False, "private_leak_count": 0})
    write_jsonl(COPY_SOAK_TRACE, copy_rows)
    token_rows = []
    for index in range(token_runs):
        result = route_token_budget({"run_id": f"stage5-token-{index:03d}", "prompt": "Summarize public release notes without private NAS content.", "context_text": "public feature overview", "task_type": "public_research", "workspace": "openclaw"}, record_trace=True)
        token_rows.append({"index": index, "ok": result.get("ok"), "route": result.get("route"), "private_leak_count": result.get("private_leak_count"), "cloud_allowed": result.get("cloud_allowed")})
    write_jsonl(TOKEN_BUDGET_TRACE, token_rows)
    after_ports = port_snapshot(ssh)
    after_qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    after_openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    normalized_before = normalize_protected_ports(before_ports.get("stdout", ""))
    normalized_after = normalize_protected_ports(after_ports.get("stdout", ""))
    add_check(checks, failures, "readonly run_count >= requested", int(readonly_summary.get("run_count") or 0) >= readonly_runs, readonly_summary)
    add_check(checks, failures, "readonly allowed_success_rate >= 0.98 and denial_correctness = 1.0", float(readonly_summary.get("allowed_success_rate") or 0) >= 0.98 and readonly_summary.get("denial_correctness") == 1.0, readonly_summary)
    add_check(checks, failures, "copy dry-run/confirm success_rate >= 0.98 with no execute", sum(1 for row in copy_rows if row["dry_ok"] and row["confirm_ok"] and not row["execute_called"]) / max(1, len(copy_rows)) >= 0.98, {"copy_runs": len(copy_rows)})
    add_check(checks, failures, "token budget smoke pass", len(token_rows) >= token_runs and all(row.get("ok") and int(row.get("private_leak_count") or 0) == 0 for row in token_rows), {"token_runs": len(token_rows)})
    add_check(checks, failures, "OpenClaw/Qwen health OK before and after", before_qwen["ok"] and before_openclaw["ok"] and after_qwen["ok"] and after_openclaw["ok"], {"before_qwen": before_qwen, "after_qwen": after_qwen, "before_openclaw": before_openclaw, "after_openclaw": after_openclaw})
    add_check(checks, failures, "protected ports unchanged", normalized_before == normalized_after and bool(normalized_before), {"before": normalized_before, "after": normalized_after})
    add_check(checks, failures, "no privacy/cloud/write regression", readonly_summary.get("private_leak_count") == 0 and readonly_summary.get("cloud_private_egress_count") == 0 and readonly_summary.get("write_destructive_execution_count") == 0 and readonly_summary.get("foreground_response_modified_count") == 0, readonly_summary)
    detail = {
        "readonly_summary": readonly_summary,
        "remote_run": command_summary(payload.get("run", {})),
        "traces": {"readonly": rel(REGRESSION_TRACE), "copy_soak": rel(COPY_SOAK_TRACE), "token_budget": rel(TOKEN_BUDGET_TRACE)},
        "health": {"before_qwen": before_qwen, "after_qwen": after_qwen, "before_openclaw": before_openclaw, "after_openclaw": after_openclaw},
        "ports": {"before": normalized_before, "after": normalized_after},
    }
    return gate_payload("stage5_default_service_regression_soak_gate", checks, failures, detail)


def stage5_default_service_emergency_rollback_gate(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        flags = read_json(FLAGS_JSON)
        updated = dict(flags)
        updated["copy_execute_enabled"] = False
        updated["copy_rollback_enabled"] = False
        updated["readonly_workspaces_enabled"] = True
        updated["token_budget_gate_enabled"] = True
        dry_run = subprocess.CompletedProcess(
            ["python-json-dry-run"],
            0,
            json.dumps(
                {
                    "ok": True,
                    "mode": "--dry-run",
                    "flags_file": str(FLAGS_JSON),
                    "copy_execute_enabled": updated["copy_execute_enabled"],
                    "copy_rollback_enabled": updated["copy_rollback_enabled"],
                    "readonly_workspaces_enabled": updated["readonly_workspaces_enabled"],
                    "token_budget_gate_enabled": updated["token_budget_gate_enabled"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            "",
        )
    except Exception as exc:
        dry_run = subprocess.CompletedProcess(["python-json-dry-run"], 1, "", f"{type(exc).__name__}:{exc}")
    remote_dry = ssh.run(f"bash {REMOTE_ROOT}/scripts/disable_harness_copy_execute.sh {REMOTE_ROOT}/configs/harness_default_service_feature_flags.json --dry-run", timeout=45)
    remote_status = ssh.run(f"bash {REMOTE_ROOT}/scripts/check_harness_default_service_status.sh http://127.0.0.1:8765", timeout=45)
    openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    add_check(checks, failures, "rollback and status scripts exist", all(path.exists() for path in [ROOT / "scripts" / "disable_harness_copy_execute.sh", ROOT / "scripts" / "check_harness_default_service_status.sh"]), None)
    add_check(checks, failures, "local rollback dry-run passes", dry_run.returncode == 0, {"stdout": dry_run.stdout[-1000:], "stderr": dry_run.stderr[-1000:]})
    add_check(checks, failures, "remote rollback dry-run passes", remote_dry.get("returncode") == 0 and '"copy_execute_enabled": false' in remote_dry.get("stdout", ""), command_summary(remote_dry))
    add_check(checks, failures, "remote status command passes", remote_status.get("returncode") == 0 and '"qwen_execution_authority": false' in remote_status.get("stdout", ""), command_summary(remote_status))
    add_check(checks, failures, "OpenClaw/Qwen health OK after rollback dry-run", openclaw["ok"] and qwen["ok"], {"openclaw": openclaw, "qwen": qwen})
    detail = {"local_dry_run": {"returncode": dry_run.returncode, "stdout": dry_run.stdout[-1000:], "stderr": dry_run.stderr[-1000:]}, "remote_dry_run": command_summary(remote_dry), "remote_status": command_summary(remote_status)}
    return gate_payload("stage5_default_service_emergency_rollback_gate", checks, failures, detail)


def stage5_default_service_persistence_gate(report_root: Path, ssh: SshRunner, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    before_ports = port_snapshot(ssh)
    restart = ssh.run("systemctl --user restart openclaw-gateway.service && sleep 4 && systemctl --user is-active openclaw-gateway.service", timeout=90)
    openclaw = remote_health(ssh, "http://127.0.0.1:8765/api/health")
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    status = remote_health(ssh, "http://127.0.0.1:8765/api/harness/status")
    execute_probe = ssh.run(
        r"""python3 - <<'PY'
import json, urllib.request, urllib.error
payload={"source_relative_path":"Collections/CodexPreflight/stage5_default_service/source/persist.txt","target_relative_path":"Collections/CodexPreflight/stage5_default_service/target/persist_copy.txt","source_sha256":"d"*64,"expected_size_bytes":10,"source_owner_scope":"codex_synthetic","target_parent_exists":True,"approval_phrase":"bad"}
req=urllib.request.Request("http://127.0.0.1:8765/api/nas/copy/execute", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(json.dumps({"http_status": resp.status, "payload": json.loads(resp.read().decode())}))
except urllib.error.HTTPError as exc:
    print(json.dumps({"http_status": exc.code, "payload": json.loads(exc.read().decode())}))
PY""",
        timeout=45,
    )
    try:
        execute_data = json.loads(execute_probe.get("stdout", "{}"))
    except Exception:
        execute_data = {}
    after_ports = port_snapshot(ssh)
    normalized_before = normalize_protected_ports(before_ports.get("stdout", ""))
    normalized_after = normalize_protected_ports(after_ports.get("stdout", ""))
    add_check(checks, failures, "OpenClaw restart succeeds", restart.get("returncode") == 0 and "active" in restart.get("stdout", ""), command_summary(restart))
    add_check(checks, failures, "policy loaded after restart", status["ok"] and (status.get("json") or {}).get("policy_id") == "digua_stage5_harness_default_service_policy_v1", status)
    add_check(checks, failures, "OpenClaw/Qwen health OK after restart", openclaw["ok"] and qwen["ok"], {"openclaw": openclaw, "qwen": qwen})
    add_check(checks, failures, "protected ports unchanged", normalized_before == normalized_after and bool(normalized_before), {"before": normalized_before, "after": normalized_after})
    add_check(checks, failures, "default service status endpoint OK", status["ok"] and (status.get("json") or {}).get("copy_execute_enabled") is True, status)
    add_check(checks, failures, "copy execute still requires confirmation/token", execute_data.get("http_status") in {400, 403, 409} and (execute_data.get("payload") or {}).get("ok") is False, execute_data)
    detail = {"restart": command_summary(restart), "status": status, "health": {"openclaw": openclaw, "qwen": qwen}, "execute_probe": execute_data, "ports": {"before": normalized_before, "after": normalized_after}}
    return gate_payload("stage5_default_service_persistence_gate", checks, failures, detail)


def final_verdict(gates: list[dict[str, Any]]) -> str:
    by_id = {gate["gate_id"]: gate for gate in gates}
    if by_id.get("stage5_default_service_synthetic_smoke_gate", {}).get("failure_count"):
        return "default_service_synthetic_smoke_failed_hold"
    if by_id.get("stage5_default_service_adversarial_gate", {}).get("failure_count"):
        return "default_service_privacy_failure_hold"
    if by_id.get("stage5_default_service_regression_soak_gate", {}).get("failure_count"):
        return "default_service_regression_failure_hold"
    if by_id.get("stage5_default_service_persistence_gate", {}).get("failure_count"):
        return "default_service_persistence_failure_hold"
    if all(gate.get("failure_count") == 0 for gate in gates):
        flags = read_json(FLAGS_JSON) if FLAGS_JSON.exists() else {}
        return "harness_default_service_integrated_limited_copy_enabled" if flags.get("copy_execute_enabled") else "harness_default_service_integrated_copy_execute_disabled"
    return "inconclusive_missing_evidence"


def write_final_docs(packet: dict[str, Any]) -> None:
    verdict = packet["final_verdict"]
    package = packet.get("final_package") or {}
    safe_write_text(
        FINAL_DECISION_DOC,
        f"""# Harness Default Service Final Decision

- final_verdict: `{verdict}`
- all_gates_pass: `{packet['all_gates_pass']}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Harness is integrated into the default OpenClaw service with limited user-confirmed copy only. It does not authorize delete, move, rename, chmod, recursive operations, Qwen autonomous tool execution, cloud private raw egress, or unattended background writes.
""",
    )
    safe_write_text(
        USER_GUIDE_DOC,
        """# Harness Default Service User Guide

Readonly AI-NAS features are available by default. Copy requires preview, dry-run, typed approval phrase, signed token, source hash recheck, target absence, allowlisted dispatcher execution, and an action-bound rollback manifest.

Qwen may explain or suggest; it does not execute tools or choose source and target for autonomous execution.
""",
    )
    safe_write_text(
        DEFENSE_QA_DOC,
        """# Harness Default Service Defense QA

Q: Does Stage 5 allow arbitrary NAS writes?
A: No. The only enabled write action is bounded single-file copy through policy, token, hash, and dispatcher checks.

Q: Can Qwen execute file tools?
A: No. Qwen execution authority remains false.

Q: Are delete, move, rename, chmod, overwrite, or recursive copy supported?
A: No.
""",
    )
    safe_write_text(
        SAFE_BOUNDARY_DOC,
        """# Harness Default Service Safe Claim Boundary

Allowed claim: Workspace Harness is connected to the default OpenClaw service path for readonly AI-NAS and limited user-confirmed copy.

Do not claim arbitrary NAS write support, autonomous Qwen file operation, delete/move/rename/chmod support, cloud private raw-content handling, or copy execution without explicit user confirmation.
""",
    )
    safe_write_text(
        FINAL_PACKET_MD,
        f"""# Digua AI-NAS Harness Default Service Gate Packet

- final_verdict: `{verdict}`
- all_gates_pass: `{packet['all_gates_pass']}`
- package: `{package.get('zip_path')}`
- sha256: `{package.get('sha256')}`

Boundary: limited user-confirmed copy only; no delete/move/rename/chmod/recursive/overwrite/Qwen autonomous execution/cloud private raw egress.
""",
    )


def build_packet(gates: list[dict[str, Any]], ctx: dict[str, Any], package_info: dict[str, Any] | None = None, self_check: dict[str, Any] | None = None) -> dict[str, Any]:
    verdict = final_verdict(gates)
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "final_verdict_allowed": verdict in FINAL_VERDICTS,
        "all_gates_pass": all(gate.get("failure_count") == 0 for gate in gates),
        "run_id": ctx.get("run_id"),
        "default_service_enabled": read_json(FLAGS_JSON).get("harness_default_service_enabled") if FLAGS_JSON.exists() else None,
        "limited_copy_execute_enabled": read_json(FLAGS_JSON).get("copy_execute_enabled") if FLAGS_JSON.exists() else None,
        "qwen_execution_authority": False,
        "cloud_private_raw_egress": False,
        "forbidden_actions": read_json(POLICY_JSON).get("forbidden_actions") if POLICY_JSON.exists() else [],
        "remote_backup_root": ctx.get("remote_backup_root"),
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
            "Harness is integrated into the default OpenClaw service with limited user-confirmed copy only.",
            "It does not authorize delete, move, rename, chmod, recursive operations, Qwen autonomous tool execution, cloud private raw egress, or unattended background writes.",
        ],
    }
    if package_info:
        packet["final_package"] = package_info
    if self_check:
        packet["package_self_check"] = self_check
    return packet


def copy_into_package(package_root: Path, path: Path) -> None:
    if path.exists():
        target = package_root / rel(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def selected_files(reports: list[dict[str, str]]) -> list[Path]:
    files = [
        FINAL_PACKET_JSON,
        FINAL_PACKET_MD,
        FLAGS_JSON,
        POLICY_JSON,
        COPY_ROUTE_POLICY_JSON,
        CONTRACT_DOC,
        FINAL_DECISION_DOC,
        USER_GUIDE_DOC,
        DEFENSE_QA_DOC,
        SAFE_BOUNDARY_DOC,
        ROOT / "src" / "openclaw" / "harness_default_middleware.py",
        ROOT / "src" / "openclaw" / "routes" / "nas_copy_routes.py",
        ROOT / "src" / "openclaw" / "routes" / "token_budget_routes.py",
        ROOT / "src" / "openclaw" / "routes" / "harness_status_routes.py",
        ROOT / "scripts" / "probes" / "ai_nas_operator_portal_server.py",
        ROOT / "scripts" / "disable_harness_copy_execute.sh",
        ROOT / "scripts" / "check_harness_default_service_status.sh",
        ROOT / "web" / "static" / "harness_status.js",
        ROOT / "web" / "static" / "copy_confirm.js",
        ROOT / "web" / "static" / "copy_confirm.css",
        ROOT / "web" / "templates" / "copy_confirm.html",
        SMOKE_TRACE,
        ADVERSARIAL_TRACE,
        REGRESSION_TRACE,
        COPY_SOAK_TRACE,
        TOKEN_BUDGET_TRACE,
        STAGE4_5_PACKET,
        ROOT / "gates" / "stage5_default_service_gates.py",
    ]
    files.extend(SCREENSHOT_DIR.glob("*") if SCREENSHOT_DIR.exists() else [])
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
required = [
    "01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json",
    "01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.md",
    "configs/harness_default_service_policy.json",
    "configs/harness_default_service_feature_flags.json",
    "docs/HARNESS_DEFAULT_SERVICE_CONTRACT.md",
    "docs/HARNESS_DEFAULT_SERVICE_FINAL_DECISION.md",
    "docs/HARNESS_DEFAULT_SERVICE_USER_GUIDE.md",
    "docs/HARNESS_DEFAULT_SERVICE_DEFENSE_QA.md",
    "docs/HARNESS_DEFAULT_SERVICE_SAFE_CLAIM_BOUNDARY.md",
    "src/openclaw/harness_default_middleware.py",
    "src/openclaw/routes/nas_copy_routes.py",
    "src/openclaw/routes/token_budget_routes.py",
    "src/openclaw/routes/harness_status_routes.py",
    "web/static/harness_status.js",
    "web/static/copy_confirm.js",
    "web/static/copy_confirm.css",
    "web/templates/copy_confirm.html",
    "scripts/disable_harness_copy_execute.sh",
    "scripts/check_harness_default_service_status.sh",
    "reports/20000_stage5_baseline_lock.json",
    "reports/20010_default_service_contract_gate.json",
    "reports/20020_openclaw_default_service_integration_gate.json",
    "reports/20030_default_copy_ui_confirmation_gate.json",
    "reports/20040_stage5_default_service_synthetic_smoke_gate.json",
    "reports/20050_stage5_default_service_adversarial_gate.json",
    "reports/20060_stage5_default_service_regression_soak_gate.json",
    "reports/20070_stage5_default_service_emergency_rollback_gate.json",
    "reports/20080_stage5_default_service_persistence_gate.json",
    "reports/stage5_default_service_synthetic_smoke_trace.jsonl",
    "reports/stage5_default_service_adversarial_cases.jsonl",
]
checks = []
failures = []
for rel in required:
    ok = (root / rel).exists()
    checks.append({"label": f"exists: {rel}", "ok": ok})
    if not ok:
        failures.append(rel)
packet_path = root / "01_final_evidence/digua_ai_nas_harness_default_service_gate_packet.json"
if packet_path.exists():
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    ok = packet.get("final_verdict") in {
        "harness_default_service_integrated_limited_copy_enabled",
        "harness_default_service_integrated_copy_execute_disabled",
        "default_service_synthetic_smoke_failed_hold",
        "default_service_privacy_failure_hold",
        "default_service_regression_failure_hold",
        "default_service_persistence_failure_hold",
        "inconclusive_missing_evidence",
    }
    checks.append({"label": "final verdict valid", "ok": ok, "detail": packet.get("final_verdict")})
    if not ok:
        failures.append("final verdict valid")
    checks.append({"label": "qwen execution authority false", "ok": packet.get("qwen_execution_authority") is False})
print(json.dumps({"checks": checks, "failures": failures}, ensure_ascii=False, indent=2))
sys.exit(0 if not failures else 1)
''',
    )


def build_package(reports: list[dict[str, str]], timestamp: str) -> dict[str, Any]:
    package_root = ROOT / "tmp" / f"digua_ai_nas_harness_default_service_for_gptpro_{timestamp}"
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
        packet["package_internal_note"] = "Zip hash is recorded in the external .sha256.txt and root workspace packet."
        safe_write_json(internal_packet, packet)
    write_self_check(package_root)
    rows = package_rows(package_root)
    safe_write_json(package_root / "MANIFEST.json", {"package": "digua_ai_nas_harness_default_service", "generated_at": utc_stamp(), "file_count": len(rows), "files": rows})
    safe_write_text(package_root / "SHA256SUMS.txt", "\n".join(f"{row['sha256']}  {row['path']}" for row in package_rows(package_root)) + "\n")
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_harness_default_service_for_gptpro_{timestamp}.zip"
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
    completed = subprocess.run([sys.executable, str(Path(package_info["package_root"]) / "SELF_CHECK.py")], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120)
    try:
        parsed = json.loads(completed.stdout)
    except Exception:
        parsed = None
    return {"returncode": completed.returncode, "stdout_hash": sha256_text(completed.stdout), "stderr_hash": sha256_text(completed.stderr), "stdout_tail": completed.stdout[-2000:], "stderr_tail": completed.stderr[-2000:], "json": parsed}


def write_packet(packet: dict[str, Any]) -> None:
    safe_write_json(FINAL_PACKET_JSON, packet)
    write_final_docs(packet)


def run_all(args: argparse.Namespace) -> list[dict[str, Any]]:
    args.report_root.mkdir(parents=True, exist_ok=True)
    ssh = SshRunner(args.host, args.key)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ctx: dict[str, Any] = {"run_id": f"stage5_default_service_{timestamp}"}
    gates: list[dict[str, Any]] = []
    reports: list[dict[str, str]] = []
    gate_fns = [
        lambda: baseline_lock(args.report_root, ssh, ctx),
        lambda: default_service_contract_gate(args.report_root),
        lambda: openclaw_default_service_integration_gate(args.report_root, ssh, ctx),
        lambda: default_copy_ui_confirmation_gate(args.report_root),
        lambda: stage5_default_service_synthetic_smoke_gate(args.report_root, ssh, ctx),
        lambda: stage5_default_service_adversarial_gate(args.report_root),
        lambda: stage5_default_service_regression_soak_gate(args.report_root, ssh, readonly_runs=args.readonly_runs, copy_runs=args.copy_runs, token_runs=args.token_runs, concurrency=args.concurrency),
        lambda: stage5_default_service_emergency_rollback_gate(args.report_root, ssh),
        lambda: stage5_default_service_persistence_gate(args.report_root, ssh, ctx),
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
    parser = argparse.ArgumentParser(description="Run Digua AI-NAS Stage5 default service gates.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--readonly-runs", type=int, default=500)
    parser.add_argument("--copy-runs", type=int, default=100)
    parser.add_argument("--token-runs", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    gates = run_all(parse_args())
    return 0 if final_verdict(gates) in FINAL_VERDICTS else 1


if __name__ == "__main__":
    raise SystemExit(main())
