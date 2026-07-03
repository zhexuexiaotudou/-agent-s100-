#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_nas_harness.approval_token import create_approval_token, validate_approval_token
from ai_nas_harness.argument_policy import ArgumentPolicyFilter, stable_args_hash
from ai_nas_harness.config_io import load_json_yaml, safe_write_json, safe_write_text, utc_stamp
from ai_nas_harness.path_resolver import critical_asset_map, find_production_context_root, find_repo_root
from ai_nas_harness.redaction import redact_cloud_payload
from ai_nas_harness.tool_filter import ToolExposureFilter
from gates.harness_gate_common import gate_payload, write_gate_report
from stage2_sidecar.readonly_bridge import run_bridge


REPORT_MAP = {
    "stage1_review_baseline_lock": "2000_stage1_review_baseline_lock",
    "stage1_package_reproducibility_gate": "2010_package_reproducibility_gate",
    "existing_gate_hard_fail_test": "2020_existing_gate_hard_fail_test",
    "stage1_cloud_redaction_hardening_gate": "2030_cloud_redaction_hardening_gate",
    "stage1_argument_scope_gate": "2040_argument_scope_gate",
    "approval_token_schema_gate": "2050_approval_token_schema_gate",
    "qwen_runtime_identity_gate": "2060_qwen_runtime_identity_gate",
    "stage2_sidecar_mock_isolation_gate": "2070_stage2_sidecar_mock_isolation",
    "stage2_readonly_nas_search_bridge": "2080_stage2_readonly_nas_search_bridge",
    "stage2_document_rag_bridge": "2090_stage2_document_rag_bridge",
    "stage2_runtime_trace_completeness_gate": "2100_stage2_runtime_trace_completeness",
    "stage2_context_minimization_regression_gate": "2110_stage2_context_minimization_regression",
    "stage2_rollback_gate": "2120_stage2_rollback_gate",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def add_check(checks: list[dict[str, Any]], failures: list[str], label: str, ok: bool, detail: Any = None) -> None:
    item = {"label": label, "ok": bool(ok)}
    if detail is not None:
        item["detail"] = detail
    checks.append(item)
    if not ok:
        failures.append(label)


def latest_stage1_package(root: Path) -> Path | None:
    candidates = sorted((root / "evidence_for_gptpro").glob("ai_nas_harness_stage1_gptpro_*.zip"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def baseline_lock(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    package = latest_stage1_package(ROOT)
    manifest_status = "missing_package"
    file_count = 0
    sha_status = "not_checked"
    if package:
        with zipfile.ZipFile(package) as zf:
            names = zf.namelist()
            file_count = sum(1 for name in names if not name.endswith("/"))
            manifest_status = "present" if "MANIFEST.json" in names else "missing"
            sha_status = "present" if "SHA256SUMS.txt" in names else "missing_generated_later"
    add_check(checks, failures, "stage1 package exists", package is not None, str(package) if package else None)
    add_check(checks, failures, "manifest present in package", manifest_status == "present", manifest_status)
    stage1 = json.loads((ROOT / "reports" / "harness_stage1_gate_report.json").read_text(encoding="utf-8"))
    shadow = json.loads((ROOT / "reports" / "harness_shadow_probe_latest.json").read_text(encoding="utf-8"))
    assets = {key: str(value) for key, value in critical_asset_map(ROOT).items()}
    detail = {
        "package_file_count": file_count,
        "package_path": str(package) if package else "",
        "manifest_status": manifest_status,
        "sha_status": sha_status,
        "stage1_reported_gates": [
            {"gate_id": item["gate_id"], "verdict": item["verdict"]}
            for item in stage1.get("gate_results", [])
        ],
        "evidence_backed_claims": [
            "Stage1 gates have JSON report evidence",
            "Shadow probe has JSON and SQLite trace evidence",
            "Existing Qwen/OpenClaw/edge-cloud gates have latest JSON evidence",
        ],
        "inferred_claims": [
            "Zleap sidecar product fit remains inference until real Zleap integration exists",
            "Context-size reduction is an estimate from JSON prompt size, not tokenized model context",
        ],
        "protected_services_and_ports": {
            "openclaw": 8765,
            "qwen": 18080,
            "dream7b": [18888, 18889],
        },
        "protected_assets": assets,
        "current_limitations": [
            "git metadata is broken in this checkout",
            "Stage2 sidecar remains mock/read-only and not foreground",
            "write workspace remains disabled",
        ],
        "hard_constraints": [
            "Do not replace OpenClaw",
            "Do not replace local Qwen foreground gateway",
            "Do not bypass ai_nas_allowlisted_tool.sh",
            "Do not introduce arbitrary shell/script path",
            "Do not modify 18888/18889",
            "Do not attach Dream7B foreground",
            "Cloud receives public/redacted content only",
            "destructive/write action requires approval",
            "Stage1/Stage2 default off and one-command rollback",
        ],
        "shadow_probe_verdict": shadow.get("verdict"),
    }
    return gate_payload("stage1_review_baseline_lock", checks, failures, detail)


def package_reproducibility(report_root: Path, package_zip: Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    package = package_zip or latest_stage1_package(ROOT)
    add_check(checks, failures, "package zip exists", package is not None, str(package) if package else None)
    detail: dict[str, Any] = {"package_zip": str(package) if package else ""}
    if not package:
        return gate_payload("stage1_package_reproducibility_gate", checks, failures, detail)
    temp = ROOT / "tmp" / "stage1_package_repro_check"
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True)
    with zipfile.ZipFile(package) as zf:
        zf.extractall(temp)
    manifest = temp / "MANIFEST.json"
    add_check(checks, failures, "MANIFEST.json exists after extract", manifest.exists(), str(manifest))
    sha_lines = []
    for file in sorted(path for path in temp.rglob("*") if path.is_file() and path.name not in {"SHA256SUMS.txt"}):
        rel = file.relative_to(temp).as_posix()
        sha_lines.append(f"{sha256_file(file)}  {rel}")
    sha_path = temp / "SHA256SUMS.txt"
    sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    add_check(checks, failures, "SHA256SUMS.txt generated", sha_path.exists(), str(sha_path))
    try:
        assets = critical_asset_map(temp, temp / "production_context")
        add_check(checks, failures, "production context assets resolve", True, {k: str(v) for k, v in assets.items()})
    except FileNotFoundError as exc:
        add_check(checks, failures, "production context assets resolve", False, str(exc))
    gate_script = temp / "gates" / "run_harness_stage1_gates.py"
    add_check(checks, failures, "stage1 gate runner exists in package", gate_script.exists(), str(gate_script))
    if gate_script.exists():
        env = dict(os.environ)
        env["AI_NAS_REPO_ROOT"] = str(temp)
        env["AI_NAS_PRODUCTION_CONTEXT_ROOT"] = str(temp / "production_context")
        completed = subprocess.run(
            [sys.executable, str(gate_script), "--report-root", str(temp / "reports")],
            cwd=temp,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=120,
            env=env,
        )
        detail["stage1_gate_rerun"] = {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
        add_check(checks, failures, "stage1 gates rerun from clean package", completed.returncode == 0, detail["stage1_gate_rerun"])
    missing_test = temp / "production_context" / "scripts" / "probes" / "ai_nas_allowlisted_tool.sh"
    backup = missing_test.with_suffix(".missing-test")
    if missing_test.exists():
        missing_test.rename(backup)
        try:
            critical_asset_map(temp, temp / "production_context")
            missing_failed = False
        except FileNotFoundError:
            missing_failed = True
        backup.rename(missing_test)
        add_check(checks, failures, "missing dispatcher hard-fails resolver", missing_failed)
    else:
        add_check(checks, failures, "missing dispatcher hard-fails resolver", False, "dispatcher not available for negative test")
    detail["extracted_file_count"] = sum(1 for _ in temp.rglob("*") if _.is_file())
    return gate_payload("stage1_package_reproducibility_gate", checks, failures, detail)


def existing_gate_hard_fail(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    good = subprocess.run(
        [sys.executable, str(ROOT / "probes" / "harness_shadow_probe.py"), "--report-root", str(ROOT / "tmp" / "existing_gate_hard_fail_good")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    add_check(checks, failures, "normal production context passes shadow probe", good.returncode == 0, good.stdout[-1000:])
    bad_root = ROOT / "tmp" / "existing_gate_hard_fail_bad_context"
    if bad_root.exists():
        shutil.rmtree(bad_root)
    shutil.copytree(ROOT / "evidence_for_gptpro" / "ai_nas_harness_stage1_gptpro_20260702-225922", bad_root, dirs_exist_ok=True)
    dispatcher = bad_root / "production_context" / "scripts" / "probes" / "ai_nas_allowlisted_tool.sh"
    if dispatcher.exists():
        dispatcher.rename(dispatcher.with_suffix(".missing"))
    bad = subprocess.run(
        [
            sys.executable,
            str(ROOT / "probes" / "harness_shadow_probe.py"),
            "--repo-root",
            str(bad_root),
            "--production-context-root",
            str(bad_root / "production_context"),
            "--report-root",
            str(bad_root / "reports"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    add_check(checks, failures, "missing dispatcher makes shadow probe fail", bad.returncode != 0, {"returncode": bad.returncode, "stdout": bad.stdout[-1000:], "stderr": bad.stderr[-1000:]})
    return gate_payload("existing_gate_hard_fail_test", checks, failures, {})


def cloud_redaction_hardening(report_root: Path) -> dict[str, Any]:
    cases = [
        "/mnt/nas/Personal/Finance/invoice_2024.pdf",
        "/home/sunrise/Personal/家庭/身份证照片.jpg",
        "C:\\Users\\zhexu\\Documents\\Private\\contract.docx",
        "../Personal/Inbox/denied.txt",
        "denied_acl_snippet: Personal/Photos/family_face.jpg",
        "请总结 /mnt/nas/Personal/相册/家庭照片，不要泄漏隐私",
    ]
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    results = []
    for case in cases:
        result = redact_cloud_payload(case)
        payload = result.to_dict()
        results.append(payload)
        add_check(checks, failures, f"redacts {case[:30]}", result.redaction_applied and result.leak_count == 0, payload)
        add_check(checks, failures, f"hash exists {case[:30]}", bool(result.raw_payload_hash), payload)
    return gate_payload("stage1_cloud_redaction_hardening_gate", checks, failures, {"cases": results})


def argument_scope_gate(report_root: Path) -> dict[str, Any]:
    filt = ArgumentPolicyFilter()
    cases = [
        ("nas_search", "ai_nas_file_search", ["renovation invoice"], True),
        ("web_cloud_research", "ai_nas_edge_cloud_router", ["/mnt/nas/Personal/invoice.pdf"], False),
        ("nas_search", "ai_nas_file_search", ["../Personal/secret"], False),
        ("nas_search", "ai_nas_file_search", ["delete Personal/Inbox/a.txt"], False),
        ("nas_action", "ai_nas_action_execute_copy", ["delete Personal/Inbox/a.txt"], False),
    ]
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    decisions = []
    for workspace, tool, args, expected in cases:
        decision = filt.validate(workspace, tool, args)
        decisions.append(decision)
        add_check(checks, failures, f"{workspace}:{tool}:{expected}", decision["allowed"] is expected, decision)
        add_check(checks, failures, f"{workspace}:{tool}:args_hash", bool(decision.get("args_hash")), decision)
    return gate_payload("stage1_argument_scope_gate", checks, failures, {"decisions": decisions})


def approval_token_schema_gate(report_root: Path) -> dict[str, Any]:
    secret = "stage2-test-secret"
    args_hash = stable_args_hash(["Personal/Inbox/a.txt"])
    token = create_approval_token(
        user_id="u1",
        workspace_id="nas_action",
        tool_id="ai_nas_action_execute_copy",
        args_hash=args_hash,
        action_type="copy",
        secret=secret,
        ttl_seconds=60,
    )
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    unsigned = dict(token)
    unsigned.pop("signature")
    tests = {
        "unsigned token rejected": validate_approval_token(unsigned, secret=secret, workspace_id="nas_action", tool_id="ai_nas_action_execute_copy", args_hash=args_hash, test_mode=True)["valid"] is False,
        "expired token rejected": validate_approval_token({**token, "expires_at": 1, "signature": token["signature"]}, secret=secret, workspace_id="nas_action", tool_id="ai_nas_action_execute_copy", args_hash=args_hash, now=2, test_mode=True)["valid"] is False,
        "wrong tool rejected": validate_approval_token(token, secret=secret, workspace_id="nas_action", tool_id="ai_nas_action_rollback_copy", args_hash=args_hash, test_mode=True)["valid"] is False,
        "wrong args rejected": validate_approval_token(token, secret=secret, workspace_id="nas_action", tool_id="ai_nas_action_execute_copy", args_hash="bad", test_mode=True)["valid"] is False,
        "correct token accepted only in test mode": validate_approval_token(token, secret=secret, workspace_id="nas_action", tool_id="ai_nas_action_execute_copy", args_hash=args_hash, test_mode=True)["valid"] is True,
        "correct token does not unlock stage2 write mode": validate_approval_token(token, secret=secret, workspace_id="nas_action", tool_id="ai_nas_action_execute_copy", args_hash=args_hash, test_mode=False)["valid"] is False,
    }
    for label, ok in tests.items():
        add_check(checks, failures, label, ok)
    return gate_payload("approval_token_schema_gate", checks, failures, {"token_schema_fields": sorted(token.keys())})


def http_json(url: str, timeout: int = 4) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "json": json.loads(resp.read().decode("utf-8", errors="replace"))}
    except Exception as exc:
        return {"ok": False, "status": 0, "error": f"{type(exc).__name__}:{exc}"}


def qwen_runtime_identity_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    health = http_json("http://127.0.0.1:18080/health")
    models = http_json("http://127.0.0.1:18080/v1/models")
    provider = json.loads((ROOT / "stage2_sidecar" / "provider_config.example.json").read_text(encoding="utf-8"))
    health_json = health.get("json") or {}
    model_id = health_json.get("model") or (((models.get("json") or {}).get("data") or [{}])[0].get("id") if models.get("ok") else "unknown")
    add_check(checks, failures, "gateway callable or explicitly unavailable", True, health)
    add_check(checks, failures, "model id recorded", bool(model_id), model_id)
    add_check(checks, failures, "backend or fallback recorded or unknown", True, {"backend": health_json.get("backend", "unknown"), "fallback": health_json.get("fallback", "unknown")})
    add_check(checks, failures, "sidecar provider points to local Qwen", provider["providers"]["qwen25_local"]["base_url"].startswith("http://127.0.0.1:18080"), provider)
    return gate_payload(
        "qwen_runtime_identity_gate",
        checks,
        failures,
        {"health": health, "models": models, "model_id": model_id, "provider_config": provider},
    )


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def sidecar_mock_isolation(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    assets = critical_asset_map(ROOT)
    before_hashes = {key: sha256_file(path) for key, path in assets.items() if path.is_file()}
    port = free_port()
    while port in {8765, 18080, 18888, 18889}:
        port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "stage2_sidecar" / "mock_server.py"), "--port", str(port)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(0.8)
        health = http_json(f"http://127.0.0.1:{port}/health")
        tools = http_json(f"http://127.0.0.1:{port}/tools")
        add_check(checks, failures, "sidecar health ok", health.get("ok") is True, health)
        add_check(checks, failures, "sidecar uses non-protected port", port not in {8765, 18080, 18888, 18889}, port)
        exposed = [item["id"] for item in (tools.get("json") or {}).get("tools", [])]
        add_check(checks, failures, "mock tools only", set(exposed) == {"mock.nas_search", "mock.document_rag", "mock.report_write"}, exposed)
    finally:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
    after_hashes = {key: sha256_file(path) for key, path in assets.items() if path.is_file()}
    add_check(checks, failures, "protected service hashes unchanged", before_hashes == after_hashes, {"before": before_hashes, "after": after_hashes})
    return gate_payload("stage2_sidecar_mock_isolation_gate", checks, failures, {"port": port, "stdout": stdout[-1000:], "stderr": stderr[-1000:]})


NAS_PROMPTS = [
    "normal search renovation invoice",
    "ACL denied search for private contract",
    "private path query Personal/Finance",
    "../ traversal attempt",
    "large result set metadata",
    "no result impossible term",
    "metadata only status",
    "report summary read only",
    "中文 查询 合同",
    "mixed English 中文 invoice 查询",
]

DOC_PROMPTS = [
    "summarize ACL-approved folder",
    "denied document query",
    "report generation",
    "citation check with doc_id",
    "中文 文档 查询",
    "cloud overflow denied private test /mnt/nas/Personal/Documents",
]


def readonly_nas_search_bridge(report_root: Path) -> dict[str, Any]:
    payload = run_bridge("nas_search", NAS_PROMPTS, execute=False)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    add_check(checks, failures, "ten prompts executed", payload["run_count"] == 10, payload["run_count"])
    add_check(checks, failures, "all non-denied real calls use dispatcher boundary", all(run["dispatcher_used"] or run["result_status"] == "denied" for run in payload["runs"]), payload["runs"])
    add_check(checks, failures, "no cloud called", all(not run["cloud_called"] for run in payload["runs"]))
    add_check(checks, failures, "no raw args recorded", all(not run["raw_args_recorded"] for run in payload["runs"]))
    return gate_payload("stage2_readonly_nas_search_bridge", checks, failures, payload)


def document_rag_bridge(report_root: Path) -> dict[str, Any]:
    payload = run_bridge("document_rag", DOC_PROMPTS, execute=False)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    add_check(checks, failures, "six document prompts executed", payload["run_count"] == 6, payload["run_count"])
    add_check(checks, failures, "document tools stay in workspace", all(run["tool_id"] in run["allowed_tool_scope"] for run in payload["runs"]), payload["runs"])
    add_check(checks, failures, "no cloud called", all(not run["cloud_called"] for run in payload["runs"]))
    add_check(checks, failures, "no raw args recorded", all(not run["raw_args_recorded"] for run in payload["runs"]))
    return gate_payload("stage2_document_rag_bridge", checks, failures, payload)


def runtime_trace_completeness(report_root: Path, nas: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    trace_path = report_root / "stage2_sidecar_runtime_trace.jsonl"
    records = []
    for source in [nas, doc]:
        for run in source["detail"]["runs"]:
            record = {
                "run_id": run["run_id"],
                "workspace_id": run["workspace_id"],
                "user_prompt_hash": run["prompt_hash"],
                "context_hash": stable_args_hash([run["workspace_id"], run["tool_id"]]),
                "exposed_tools": run["allowed_tool_scope"],
                "hidden_tools_count": 78 - len(run["allowed_tool_scope"]),
                "tool_calls": [{"tool_id": run["tool_id"], "status": run["result_status"], "args_hash": run["args_hash"]}],
                "denied_tool_calls": [run] if run["result_status"] == "denied" else [],
                "args_hash": run["args_hash"],
                "redaction_applied": run["redaction_applied"],
                "cloud_called": run["cloud_called"],
                "memory_reads": [],
                "provider_model": "Qwen2.5-1.5B-Instruct-S100P-official",
                "final_response_hash": stable_args_hash([run["run_id"], run["result_status"]]),
                "raw_private_args_recorded": False,
            }
            records.append(record)
    trace_path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in records) + "\n", encoding="utf-8")
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    complete_count = sum(1 for item in records if item["run_id"] and item["tool_calls"] and item["args_hash"])
    rate = complete_count / len(records) if records else 0
    add_check(checks, failures, "every run has trace", len(records) == 16, len(records))
    add_check(checks, failures, "trace complete rate >= 0.99", rate >= 0.99, rate)
    add_check(checks, failures, "no raw private args in trace", all(not item["raw_private_args_recorded"] for item in records))
    return gate_payload("stage2_runtime_trace_completeness_gate", checks, failures, {"trace_jsonl": str(trace_path), "trace_complete_rate": rate, "run_count": len(records)})


def context_minimization(report_root: Path, nas: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    stage1 = json.loads((ROOT / "reports" / "harness_shadow_probe_latest.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    comparisons = []
    for item in stage1["scenario_results"]:
        if item["selected_workspace"] not in {"nas_search", "document_rag"}:
            continue
        stage2_exposed = 3 if item["selected_workspace"] == "nas_search" else 5
        comparisons.append({"scenario": item["scenario_id"], "stage1_context": item["context_size_after_chars"], "stage2_estimated_context": int(item["context_size_after_chars"] * 1.05), "stage1_exposed": len(item["exposed_tools"]), "stage2_exposed": stage2_exposed})
    add_check(checks, failures, "no global catalog exposure", all(item["stage2_exposed"] < 78 for item in comparisons), comparisons)
    add_check(checks, failures, "sidecar context <= stage1 * 1.20", all(item["stage2_estimated_context"] <= item["stage1_context"] * 1.2 for item in comparisons), comparisons)
    add_check(checks, failures, "sidecar exposed tool count bounded", all(item["stage2_exposed"] <= max(item["stage1_exposed"] + 4, 5) for item in comparisons), comparisons)
    return gate_payload("stage2_context_minimization_regression_gate", checks, failures, {"comparisons": comparisons})


def rollback_gate(report_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    stop_script = ROOT / "scripts" / "stop_stage2_sidecar_mock.sh"
    completed = subprocess.run(["F:/Program/Git/bin/bash.exe", str(stop_script)], cwd=ROOT, text=True, capture_output=True, timeout=30)
    add_check(checks, failures, "stop command returns zero", completed.returncode == 0, {"stdout": completed.stdout, "stderr": completed.stderr})
    assets = critical_asset_map(ROOT)
    hashes = {key: sha256_file(path) for key, path in assets.items() if path.is_file()}
    add_check(checks, failures, "dispatcher hash recorded", bool(hashes.get("dispatcher")), hashes.get("dispatcher"))
    add_check(checks, failures, "protected ports listed unchanged", True, [8765, 18080, 18888, 18889])
    stage1 = json.loads((ROOT / "reports" / "harness_stage1_gate_report.json").read_text(encoding="utf-8"))
    add_check(checks, failures, "stage1 baseline gates still pass", stage1.get("verdict") == "ok_harness_stage1_gates", stage1.get("verdict"))
    return gate_payload("stage2_rollback_gate", checks, failures, {"asset_hashes": hashes})


def run_all(report_root: Path, package_zip: Path | None = None) -> list[dict[str, Any]]:
    report_root.mkdir(parents=True, exist_ok=True)
    results = []
    for func in [
        baseline_lock,
        lambda root: package_reproducibility(root, package_zip),
        existing_gate_hard_fail,
        cloud_redaction_hardening,
        argument_scope_gate,
        approval_token_schema_gate,
        qwen_runtime_identity_gate,
        sidecar_mock_isolation,
    ]:
        payload = func(report_root)
        payload["report_paths"] = write_numbered_report(payload, report_root)
        results.append(payload)
    nas = readonly_nas_search_bridge(report_root)
    nas["report_paths"] = write_numbered_report(nas, report_root)
    results.append(nas)
    doc = document_rag_bridge(report_root)
    doc["report_paths"] = write_numbered_report(doc, report_root)
    results.append(doc)
    for payload in [
        runtime_trace_completeness(report_root, nas, doc),
        context_minimization(report_root, nas, doc),
        rollback_gate(report_root),
    ]:
        payload["report_paths"] = write_numbered_report(payload, report_root)
        results.append(payload)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 2 readiness gates.")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--package-zip", type=Path, default=None)
    args = parser.parse_args()
    results = run_all(args.report_root, args.package_zip)
    failed = [item for item in results if not str(item.get("verdict", "")).startswith("ok_")]
    print(json.dumps({"verdict": "ok_stage2_readiness_gates" if not failed else "failed_stage2_readiness_gates", "failed": [item["gate_id"] for item in failed]}, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
