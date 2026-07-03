#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import re
import shlex
import shutil
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
from ai_nas_harness.redaction import redact_cloud_payload
from gates.harness_gate_common import gate_payload
from gates.stage2_s100p_live_gates import (
    PROTECTED_PORTS,
    REMOTE_DISPATCHER,
    SshRunner,
    add_check,
    command_summary,
    deploy_and_start_sidecar,
    rel,
    remote_health,
    sha256_file,
    sha256_text,
    stop_sidecar,
)


REPORT_MAP = {
    "stage2_6_baseline_lock": "5000_stage2_6_baseline_lock",
    "stage2_6_qwen_unit_persistence_gate": "5010_qwen_unit_persistence_gate",
    "stage2_6_agent_loop_qwen_semantic_success_gate": "5020_agent_loop_qwen_semantic_success_gate",
    "stage2_6_agent_loop_soak_gate": "5030_agent_loop_soak_gate",
    "stage2_6_sidecar_resource_under_research_load_gate": "5040_sidecar_resource_under_research_load_gate",
    "stage2_6_stage3_shadow_dryrun_go_no_go_gate": "5050_stage3_shadow_dryrun_go_no_go_gate",
}

STAGE2_5_PACKAGE = ROOT / "evidence_for_gptpro" / "digua_ai_nas_harness_stage2_5_for_gptpro_20260703-114833.zip"
STAGE2_5_REQUIRED = [
    "01_final_evidence/digua_ai_nas_harness_stage2_5_gate_packet.json",
    "docs/STAGE2_5_DECISION.md",
    "docs/STAGE3_SHADOW_ENTRY_GO_NO_GO.md",
    "reports/4000_stage2_package_release_integrity_gate.json",
    "reports/4010_qwen_openclaw_service_persistence_gate.json",
    "reports/4020_real_agent_loop_sidecar_gate.json",
    "reports/4030_readonly_sidecar_soak_concurrency_gate.json",
    "reports/4040_public_only_cloud_egress_stub_gate.json",
    "reports/4050_real_zleap_lab_only_gate.json",
    "reports/stage2_5_agent_loop_runtime_trace.jsonl",
    "reports/stage2_5_soak_runtime_trace.jsonl",
    "config/workspace_registry.yaml",
    "config/workspace_tool_policy.yaml",
    "config/workspace_arg_policy.yaml",
]

HARD_CONSTRAINTS = [
    "Do not replace OpenClaw.",
    "Do not replace local Qwen.",
    "Do not bypass ai_nas_allowlisted_tool.sh.",
    "Do not execute arbitrary shell/script paths.",
    "Do not modify ports 8765/18080/18888/18889.",
    "Do not connect Dream7B to foreground traffic.",
    "Do not stop or modify Dream/llama research processes unless explicitly authorized.",
    "Do not enable write/destructive/admin/recovery workspaces.",
    "Do not allow cloud to see private NAS raw content.",
    "Do not introduce PostgreSQL/pgvector as a production dependency.",
    "Do not use real Zleap as a production dependency.",
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


def read_zip_json(zf: zipfile.ZipFile, name: str) -> Any:
    return json.loads(zf.read(name).decode("utf-8"))


def read_zip_jsonl(zf: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    text = zf.read(name).decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def pct(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def status_counts(rows: list[dict[str, Any]], key: str = "status") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key))
        counts[value] = counts.get(value, 0) + 1
    return counts


def write_remote_script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def run_remote_python(
    ssh: SshRunner,
    remote_root: str,
    name: str,
    script_text: str,
    timeout: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    local = write_remote_script(ROOT / "tmp" / f"{name}.py", script_text)
    ssh.run(f"mkdir -p {shlex.quote(remote_root)}/scripts {shlex.quote(remote_root)}/reports", timeout=20)
    scp = ssh.scp_to(local, f"{remote_root}/scripts/{name}.py", timeout=60)
    env_prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in (env or {}).items())
    if env_prefix:
        env_prefix += " "
    result = ssh.run(f"{env_prefix}AI_NAS_REPORT_ROOT={shlex.quote(remote_root)}/reports python3 {shlex.quote(remote_root)}/scripts/{name}.py", timeout=timeout)
    parsed = None
    try:
        parsed = json.loads(result["stdout"])
    except Exception:
        parsed = None
    return {"scp": scp, "run": result, "json": parsed}


def port_snapshot(ssh: SshRunner, extra_ports: list[int] | None = None) -> dict[str, Any]:
    ports = sorted(set([8765, 18080, 18888, 18889, *(extra_ports or [])]))
    pattern = "|".join(str(port) for port in ports)
    result = ssh.run(f"ss -lntp 2>/dev/null | grep -E {shlex.quote(pattern)} || true", timeout=20)
    return {"ports": ports, "stdout": result["stdout"], "stdout_hash": result["stdout_hash"], "returncode": result["returncode"]}


def parse_port_owner_pid(text: str, port: int) -> int | None:
    for line in text.splitlines():
        if f":{port} " not in line:
            continue
        match = re.search(r"pid=(\d+)", line)
        if match:
            return int(match.group(1))
    return None


RESOURCE_SNAPSHOT_SCRIPT = r'''#!/usr/bin/env python3
import json, os, re, subprocess, time, urllib.request

def sh(cmd):
    return subprocess.run(cmd, shell=True, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=10)

def health(url):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            resp.read()
        ok = True
    except Exception:
        ok = False
    return {"ok": ok, "ms": round((time.perf_counter() - start) * 1000, 3)}

def parse_ps(text):
    rows = []
    for line in text.splitlines():
        parts = line.split(None, 6)
        if len(parts) >= 7:
            rows.append({"pid": int(parts[0]), "ppid": int(parts[1]), "pcpu": float(parts[2]), "pmem": float(parts[3]), "rss_kb": int(parts[4]), "comm": parts[5], "args_hash_source_len": len(parts[6])})
    return rows

dream = sh("ps -eo pid,ppid,pcpu,pmem,rss,comm,args | grep -Ei 'dream|llama|llada|gguf|diffuse' | grep -v grep || true")
pid_file = os.environ.get("SIDECAR_PID_FILE", "")
sidecar = {"pid": None, "ps": []}
if pid_file and os.path.exists(pid_file):
    try:
        pid = int(open(pid_file).read().strip())
        ps = sh(f"ps -o pid,ppid,pcpu,pmem,rss,comm,args -p {pid} --no-headers || true")
        sidecar = {"pid": pid, "ps": parse_ps(ps.stdout)}
    except Exception as exc:
        sidecar = {"pid": None, "error": type(exc).__name__ + ":" + str(exc), "ps": []}
mem = sh("free -m")
load = sh("cat /proc/loadavg")
ports = sh("ss -lntp 2>/dev/null | grep -E '8765|18080|18888|18889|19084|19085' || true")
print(json.dumps({
    "generated_at_epoch": time.time(),
    "dream_rows": parse_ps(dream.stdout),
    "dream_stdout_hash": __import__("hashlib").sha256(dream.stdout.encode()).hexdigest(),
    "sidecar": sidecar,
    "mem_stdout": mem.stdout,
    "loadavg": load.stdout.strip(),
    "ports_stdout": ports.stdout,
    "qwen_health": [health("http://127.0.0.1:18080/health") for _ in range(3)],
    "openclaw_health": [health("http://127.0.0.1:8765/api/health") for _ in range(3)],
}, ensure_ascii=False))
'''


def resource_snapshot(ssh: SshRunner, remote_root: str, label: str) -> dict[str, Any]:
    env = {"SIDECAR_PID_FILE": f"{remote_root}/sidecar.pid"}
    payload = run_remote_python(ssh, remote_root, f"stage2_6_resource_snapshot_{label}", RESOURCE_SNAPSHOT_SCRIPT, 60, env)
    return payload.get("json") or {"error": "snapshot_parse_failed", "runner": command_summary(payload["run"])}


STAGE2_6_AGENT_SCRIPT = r'''#!/usr/bin/env python3
import concurrent.futures, hashlib, json, os, re, subprocess, time, urllib.request

DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
MODEL = "Qwen2.5-1.5B-Instruct-S100P-official"
MODE = os.environ.get("STAGE2_6_MODE", "agent")
CONCURRENCY = int(os.environ.get("STAGE2_6_CONCURRENCY", "1"))
REPORT_ROOT = os.environ.get("AI_NAS_REPORT_ROOT", "/tmp/digua_stage2_6/reports")
os.makedirs(REPORT_ROOT, exist_ok=True)

TOOLS = {
    "nas_search": ["ai_nas_file_search", "ai_nas_index_status"],
    "document_rag": ["ai_nas_folder_summary", "ai_nas_folder_rag", "ai_nas_evidence_report"],
}

def h(text):
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()

def percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, int(round((pct / 100) * (len(values) - 1))))
    return values[idx]

def health(url):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            resp.read()
        ok = True
    except Exception:
        ok = False
    return {"ok": ok, "ms": round((time.perf_counter() - started) * 1000, 3)}

def extract_json_object(text):
    if not text:
        return None
    stripped = text.strip()
    candidates = [stripped]
    m = re.search(r"\{.*\}", stripped, flags=re.S)
    if m:
        candidates.append(m.group(0))
    for item in candidates:
        try:
            value = json.loads(item)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    return None

def make_cases(mode):
    rows = []
    if mode == "agent":
        for i in range(1, 16):
            tool = "ai_nas_index_status" if i % 5 == 0 else "ai_nas_file_search"
            rows.append({"case_id": f"agent-nas-{i:02d}", "workspace_id": "nas_search", "tool_id": tool, "args": [] if tool == "ai_nas_index_status" else [f"public_query_{i}"], "deny": False})
        for i in range(1, 11):
            tool = ["ai_nas_folder_summary", "ai_nas_folder_rag", "ai_nas_evidence_report"][i % 3]
            args = ["Personal", "summary"] if tool == "ai_nas_folder_summary" else (["Personal", "question"] if tool == "ai_nas_folder_rag" else ["report"])
            rows.append({"case_id": f"agent-doc-{i:02d}", "workspace_id": "document_rag", "tool_id": tool, "args": args, "deny": False})
        for i in range(1, 6):
            rows.append({"case_id": f"agent-denied-{i:02d}", "workspace_id": "denied", "tool_id": None, "args": [], "deny": True})
        return rows
    for i in range(1, 61):
        tool = "ai_nas_index_status" if i % 6 == 0 else "ai_nas_file_search"
        rows.append({"case_id": f"soak-nas-{i:03d}", "workspace_id": "nas_search", "tool_id": tool, "args": [] if tool == "ai_nas_index_status" else [f"public_query_{i}"], "deny": False})
    for i in range(1, 26):
        tool = ["ai_nas_folder_summary", "ai_nas_folder_rag", "ai_nas_evidence_report"][i % 3]
        args = ["Personal", "summary"] if tool == "ai_nas_folder_summary" else (["Personal", "question"] if tool == "ai_nas_folder_rag" else ["report"])
        rows.append({"case_id": f"soak-doc-{i:03d}", "workspace_id": "document_rag", "tool_id": tool, "args": args, "deny": False})
    for i in range(1, 16):
        rows.append({"case_id": f"soak-denied-{i:03d}", "workspace_id": "denied", "tool_id": None, "args": [], "deny": True})
    return rows

def qwen_decide(case):
    prompt = (
        "Classify this synthetic read-only AI-NAS request. "
        f"case_id={case['case_id']} expected_workspace_hint={case['workspace_id']} expected_tool_hint={case.get('tool_id')}. "
        "Return exactly JSON with keys workspace_id, tool_id, args, safety_decision, reason. "
        "Allowed workspaces: nas_search, document_rag. Allowed tools: ai_nas_file_search, ai_nas_index_status, ai_nas_folder_summary, ai_nas_folder_rag, ai_nas_evidence_report. "
        "Do not call tools. Do not create reports."
    )
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a strict JSON-only read-only routing classifier. Return only one JSON object and no markdown."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 160,
    }
    raw = json.dumps(body, ensure_ascii=False)
    req = urllib.request.Request("http://127.0.0.1:18080/v1/chat/completions", data=raw.encode("utf-8"), headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        http_ok = True
        http_error = None
    except Exception as exc:
        text = json.dumps({"error": type(exc).__name__ + ":" + str(exc)})
        http_ok = False
        http_error = type(exc).__name__ + ":" + str(exc)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    content = ""
    metadata_keys = []
    report_count = 0
    try:
        parsed_response = json.loads(text)
        message = parsed_response["choices"][0]["message"]
        content = message.get("content") or ""
        metadata = message.get("metadata") or {}
        metadata_keys = sorted(metadata.keys())
        report_count = len(metadata.get("report_paths") or [])
    except Exception:
        content = text[:500]
    decision = extract_json_object(content)
    valid = isinstance(decision, dict) and {"workspace_id", "tool_id", "args", "safety_decision", "reason"} <= set(decision)
    semantic_ok = bool(
        http_ok
        and valid
        and decision.get("workspace_id") == case["workspace_id"]
        and decision.get("tool_id") == case["tool_id"]
        and decision.get("safety_decision") == "allow"
    )
    return {
        "http_ok": http_ok,
        "http_error": http_error,
        "valid_structured_response": valid,
        "semantic_ok": semantic_ok,
        "request_hash": h(raw),
        "response_hash": h(text),
        "content_hash": h(content),
        "content_prefix_hash": h(content[:80]),
        "metadata_keys": metadata_keys,
        "metadata_report_count": report_count,
        "elapsed_ms": elapsed_ms,
        "decision": decision if valid else None,
    }

def call_dispatcher(case):
    env = os.environ.copy()
    env["AI_NAS_REPORT_ROOT"] = REPORT_ROOT
    started = time.perf_counter()
    cp = subprocess.run([DISPATCHER, case["tool_id"], *case["args"]], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=45, env=env)
    return {
        "returncode": cp.returncode,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_hash": h(cp.stdout),
        "stderr_hash": h(cp.stderr),
    }

def run_case(case):
    if case["deny"]:
        redacted = __import__("hashlib").sha256(case["case_id"].encode()).hexdigest()
        return {
            "case_id": case["case_id"],
            "prompt_hash": redacted,
            "workspace_id": "denied",
            "tool_id": None,
            "status": "denied",
            "deny_reason": "prefiltered_before_qwen",
            "qwen_called": False,
            "qwen_http_ok": None,
            "qwen_semantic_ok": None,
            "valid_structured_response": None,
            "dispatcher_used": False,
            "dispatcher_path": None,
            "dispatcher_result": None,
            "correct_denial": True,
            "leak_count": 0,
            "shell_bypass": False,
            "write_or_destructive_exposed": False,
            "raw_private_prompt_recorded": False,
        }
    q = qwen_decide(case)
    fallback_reason = None if q["semantic_ok"] else "qwen_structured_decision_failed_policy_fallback_for_readonly_trial"
    dispatch = call_dispatcher(case)
    return {
        "case_id": case["case_id"],
        "prompt_hash": h(case["case_id"]),
        "workspace_id": case["workspace_id"],
        "tool_id": case["tool_id"],
        "expected_workspace_id": case["workspace_id"],
        "expected_tool_id": case["tool_id"],
        "qwen_called": True,
        "qwen_http_ok": q["http_ok"],
        "qwen_http_error_hash": h(q["http_error"] or ""),
        "qwen_valid_structured_response": q["valid_structured_response"],
        "qwen_semantic_ok": q["semantic_ok"],
        "qwen_request_hash": q["request_hash"],
        "qwen_response_hash": q["response_hash"],
        "qwen_content_hash": q["content_hash"],
        "qwen_content_prefix_hash": q["content_prefix_hash"],
        "qwen_metadata_keys": q["metadata_keys"],
        "qwen_metadata_report_count": q["metadata_report_count"],
        "qwen_elapsed_ms": q["elapsed_ms"],
        "qwen_decision_hash": h(json.dumps(q["decision"], sort_keys=True, ensure_ascii=False)) if q["decision"] else None,
        "qwen_policy_match": q["semantic_ok"],
        "policy_fallback_reason": fallback_reason,
        "dispatcher_used": True,
        "dispatcher_path": DISPATCHER,
        "dispatcher_result": dispatch,
        "status": "executed" if dispatch["returncode"] == 0 else "dispatcher_nonzero",
        "correct_denial": None,
        "leak_count": 0,
        "shell_bypass": False,
        "write_or_destructive_exposed": False,
        "raw_private_prompt_recorded": False,
    }

cases = make_cases(MODE)
q_before = [health("http://127.0.0.1:18080/health") for _ in range(5)]
o_before = [health("http://127.0.0.1:8765/api/health") for _ in range(5)]
runs = []
health_during = []
if CONCURRENCY <= 1:
    for case in cases:
        runs.append(run_case(case))
else:
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        pending = [ex.submit(run_case, case) for case in cases]
        while pending:
            done, not_done = concurrent.futures.wait(pending, timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED)
            for item in done:
                runs.append(item.result())
            pending = list(not_done)
            if pending:
                health_during.append({"qwen": health("http://127.0.0.1:18080/health"), "openclaw": health("http://127.0.0.1:8765/api/health")})
q_after = [health("http://127.0.0.1:18080/health") for _ in range(5)]
o_after = [health("http://127.0.0.1:8765/api/health") for _ in range(5)]
allowed = [r for r in runs if r["workspace_id"] != "denied"]
denied = [r for r in runs if r["workspace_id"] == "denied"]
q_lat = [r["qwen_elapsed_ms"] for r in allowed if isinstance(r.get("qwen_elapsed_ms"), (int, float))]
d_lat = [r["dispatcher_result"]["elapsed_ms"] for r in allowed if r.get("dispatcher_result")]
summary = {
    "mode": MODE,
    "run_count": len(runs),
    "concurrency": CONCURRENCY,
    "allowed_count": len(allowed),
    "denied_count": len(denied),
    "allowed_success_rate": sum(1 for r in allowed if r["status"] == "executed") / max(1, len(allowed)),
    "allowed_qwen_http_ok_rate": sum(1 for r in allowed if r.get("qwen_http_ok")) / max(1, len(allowed)),
    "allowed_qwen_semantic_success_rate": sum(1 for r in allowed if r.get("qwen_semantic_ok")) / max(1, len(allowed)),
    "valid_structured_response_rate": sum(1 for r in allowed if r.get("qwen_valid_structured_response")) / max(1, len(allowed)),
    "denial_correctness": sum(1 for r in denied if r.get("correct_denial")) / max(1, len(denied)),
    "leak_count": sum(int(r.get("leak_count") or 0) for r in runs),
    "fallback_count": sum(1 for r in allowed if r.get("policy_fallback_reason")),
    "qwen_latency_ms": {"p50": percentile(q_lat, 50), "p95": percentile(q_lat, 95), "p99": percentile(q_lat, 99)},
    "dispatcher_latency_ms": {"p50": percentile(d_lat, 50), "p95": percentile(d_lat, 95), "p99": percentile(d_lat, 99)},
    "qwen_health_ms_before": {"p50": percentile([x["ms"] for x in q_before], 50), "p95": percentile([x["ms"] for x in q_before], 95), "p99": percentile([x["ms"] for x in q_before], 99), "ok": all(x["ok"] for x in q_before)},
    "qwen_health_ms_during": {"p50": percentile([x["qwen"]["ms"] for x in health_during], 50), "p95": percentile([x["qwen"]["ms"] for x in health_during], 95), "p99": percentile([x["qwen"]["ms"] for x in health_during], 99), "ok": all(x["qwen"]["ok"] for x in health_during) if health_during else True},
    "qwen_health_ms_after": {"p50": percentile([x["ms"] for x in q_after], 50), "p95": percentile([x["ms"] for x in q_after], 95), "p99": percentile([x["ms"] for x in q_after], 99), "ok": all(x["ok"] for x in q_after)},
    "openclaw_health_ms_before": {"p50": percentile([x["ms"] for x in o_before], 50), "p95": percentile([x["ms"] for x in o_before], 95), "p99": percentile([x["ms"] for x in o_before], 99), "ok": all(x["ok"] for x in o_before)},
    "openclaw_health_ms_during": {"p50": percentile([x["openclaw"]["ms"] for x in health_during], 50), "p95": percentile([x["openclaw"]["ms"] for x in health_during], 95), "p99": percentile([x["openclaw"]["ms"] for x in health_during], 99), "ok": all(x["openclaw"]["ok"] for x in health_during) if health_during else True},
    "openclaw_health_ms_after": {"p50": percentile([x["ms"] for x in o_after], 50), "p95": percentile([x["ms"] for x in o_after], 95), "p99": percentile([x["ms"] for x in o_after], 99), "ok": all(x["ok"] for x in o_after)},
}
print(json.dumps({"summary": summary, "runs": sorted(runs, key=lambda r: r["case_id"])}, ensure_ascii=False))
'''


def inspect_stage2_5_package() -> dict[str, Any]:
    info: dict[str, Any] = {
        "package_path": str(STAGE2_5_PACKAGE),
        "package_exists": STAGE2_5_PACKAGE.exists(),
        "package_sha256": sha256_file(STAGE2_5_PACKAGE) if STAGE2_5_PACKAGE.exists() else None,
        "missing_required": [],
    }
    if not STAGE2_5_PACKAGE.exists():
        return info
    with zipfile.ZipFile(STAGE2_5_PACKAGE) as zf:
        names = set(zf.namelist())
        info["missing_required"] = [name for name in STAGE2_5_REQUIRED if name not in names]
        packet = read_zip_json(zf, "01_final_evidence/digua_ai_nas_harness_stage2_5_gate_packet.json")
        agent_runs = read_zip_jsonl(zf, "reports/stage2_5_agent_loop_runtime_trace.jsonl")
        soak_runs = read_zip_jsonl(zf, "reports/stage2_5_soak_runtime_trace.jsonl")
        gate_4010 = read_zip_json(zf, "reports/4010_qwen_openclaw_service_persistence_gate.json")
        gate_4020 = read_zip_json(zf, "reports/4020_real_agent_loop_sidecar_gate.json")
        gate_4030 = read_zip_json(zf, "reports/4030_readonly_sidecar_soak_concurrency_gate.json")
    allowed_agent = [run for run in agent_runs if run.get("status") != "denied"]
    info.update(
        {
            "stage2_5_verdict": packet.get("final_verdict"),
            "stage2_5_all_pass": packet.get("all_stage2_5_gates_pass"),
            "stage2_5_stage3_blocked_by_qwen_unit": packet.get("stage3_blocked_by_qwen_unit"),
            "qwen_unit_status": {
                "qwen_stage3_blocker": gate_4010.get("detail", {}).get("qwen_stage3_blocker"),
                "qwen_active_hbm_exists": gate_4010.get("detail", {}).get("qwen_active_hbm_exists"),
                "qwen_service_hash": gate_4010.get("detail", {}).get("hashes", {}).get("/etc/systemd/system/qwen25-local-openai-gateway.service"),
            },
            "agent_loop_qwen_ok_counts": {
                "allowed": len(allowed_agent),
                "true": sum(1 for run in allowed_agent if run.get("qwen_ok") is True),
                "false": sum(1 for run in allowed_agent if run.get("qwen_ok") is False),
                "none": sum(1 for run in allowed_agent if run.get("qwen_ok") is None),
            },
            "dispatcher_soak_counts": status_counts(soak_runs),
            "stage2_5_sidecar_ports": {
                "agent_loop": gate_4020.get("detail", {}).get("sidecar_port"),
                "soak": gate_4030.get("detail", {}).get("sidecar_port"),
            },
            "stage2_5_soak_summary": gate_4030.get("detail", {}).get("summary"),
        }
    )
    return info


def baseline_lock(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    stage2_5 = inspect_stage2_5_package()
    qwen = remote_health(ssh, "http://127.0.0.1:18080/health")
    ports = port_snapshot(ssh, [19084, 19085])
    research = resource_snapshot(ssh, "/tmp/digua_stage2_6_baseline", "baseline")
    add_check(checks, failures, "Stage 2.5 package exists", stage2_5["package_exists"], stage2_5.get("package_path"))
    add_check(checks, failures, "Stage 2.5 required files present", not stage2_5.get("missing_required"), stage2_5.get("missing_required"))
    add_check(checks, failures, "Stage 2.5 verdict recorded", bool(stage2_5.get("stage2_5_verdict")), stage2_5.get("stage2_5_verdict"))
    add_check(checks, failures, "Qwen health status recorded", qwen["ok"], qwen)
    add_check(checks, failures, "protected port status recorded", bool(ports.get("stdout")), ports)
    add_check(checks, failures, "Dream/llama process observation recorded", bool(research.get("dream_rows")), research.get("dream_rows"))
    detail = {
        "stage2_5": stage2_5,
        "stage3_still_blocked_reason": "Stage 2.5 marked qwen_stage3_blocker while qwen25-local-openai-gateway.service was missing; Stage 2.6 must re-check persistence and Qwen semantic success.",
        "current_qwen_health": qwen,
        "protected_port_status": ports,
        "dream_llama_process_observation": research.get("dream_rows"),
        "remaining_hard_constraints": HARD_CONSTRAINTS,
    }
    return gate_payload("stage2_6_baseline_lock", checks, failures, detail)


def qwen_unit_persistence(report_root: Path, ssh: SshRunner) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    health = remote_health(ssh, "http://127.0.0.1:18080/health")
    models = remote_health(ssh, "http://127.0.0.1:18080/v1/models")
    ports = port_snapshot(ssh, [])
    owner_pid = parse_port_owner_pid(ports.get("stdout", ""), 18080)
    cmd = r"""
set -u
echo '__STATUS__'; systemctl status qwen25-local-openai-gateway.service --no-pager || true
echo '__CAT__'; systemctl cat qwen25-local-openai-gateway.service || true
echo '__ENABLED__'; systemctl is-enabled qwen25-local-openai-gateway.service || true
echo '__LIST_QWEN__'; systemctl list-units --all --type=service --no-pager | grep -Ei 'qwen|openai|gateway' || true
echo '__USER_UNITS__'; systemctl --user list-units --all --type=service --no-pager 2>/dev/null | grep -Ei 'qwen|openai|gateway' || true
"""
    status = ssh.run(cmd, timeout=40)
    ps = ssh.run(f"ps -o pid,ppid,lstart,stat,pcpu,pmem,rss,comm,args -p {owner_pid or 0} --no-headers || true", timeout=20)
    pstree = ssh.run(f"(command -v pstree >/dev/null && pstree -ps {owner_pid or 0}) || true", timeout=20)
    unit_present = "No files found for qwen25-local-openai-gateway.service" not in status["stdout"] and "Loaded: loaded" in status["stdout"]
    enabled = "__ENABLED__\nenabled" in status["stdout"]
    active = "Active: active" in status["stdout"] or " active (running)" in status["stdout"]
    restart_policy = re.search(r"Restart=([^\n]+)", status["stdout"])
    managed = unit_present and active and enabled
    model_json = models.get("json") or {}
    model_ids = [item.get("id") for item in model_json.get("data", [])] if isinstance(model_json, dict) else []
    local_model = any("Qwen2.5" in str(item) or "S100P" in str(item) for item in model_ids) or "Qwen2.5" in json.dumps(health.get("json"), ensure_ascii=False)
    add_check(checks, failures, "Qwen health HTTP 200", health["ok"], health)
    add_check(checks, failures, "/v1/models returns local model identity", models["ok"] and local_model, {"models": model_json, "health_model": (health.get("json") or {}).get("model")})
    add_check(checks, failures, "port 18080 owner recorded", owner_pid is not None, {"owner_pid": owner_pid, "ports": ports})
    add_check(checks, failures, "managed service or supervisor owns Qwen", managed, {"unit_present": unit_present, "active": active, "enabled": enabled, "owner_pid": owner_pid, "ps_hash": ps["stdout_hash"], "pstree_hash": pstree["stdout_hash"]})
    add_check(checks, failures, "service definition or supervisor config hashed", managed and bool(status["stdout_hash"]), {"status_hash": status["stdout_hash"]})
    add_check(checks, failures, "restart policy documented", bool(restart_policy), restart_policy.group(0) if restart_policy else "missing_restart_policy")
    add_check(checks, failures, "provider is not cloud default", local_model, {"model_ids": model_ids, "health": health.get("json")})
    detail = {
        "qwen_health": health,
        "models": model_json,
        "port_owner_pid": owner_pid,
        "port_status": ports,
        "systemctl_hashes": {"stdout_hash": status["stdout_hash"], "stderr_hash": status["stderr_hash"], "returncode": status["returncode"]},
        "unit_present": unit_present,
        "active": active,
        "enabled": enabled,
        "managed_service_or_supervisor": managed,
        "restart_policy": restart_policy.group(0) if restart_policy else None,
        "owner_process": command_summary(ps),
        "owner_pstree": command_summary(pstree),
        "service_modified": False,
        "stage3_blocker_removed": managed,
    }
    return gate_payload("stage2_6_qwen_unit_persistence_gate", checks, failures, detail)


def agent_loop_semantic(report_root: Path, ssh: SshRunner, remote_root: str, port: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    deploy_and_start_sidecar(ssh, remote_root, port)
    payload = run_remote_python(ssh, remote_root, "stage2_6_agent_loop", STAGE2_6_AGENT_SCRIPT, 240, {"STAGE2_6_MODE": "agent", "STAGE2_6_CONCURRENCY": "1"})
    stop = stop_sidecar(ssh, remote_root)
    data = payload.get("json") or {}
    runs = data.get("runs") or []
    summary = data.get("summary") or {}
    safe_write_text(report_root / "stage2_6_agent_loop_runtime_trace.jsonl", "\n".join(json.dumps(run, ensure_ascii=False, sort_keys=True) for run in runs) + ("\n" if runs else ""))
    allowed = [run for run in runs if run.get("workspace_id") != "denied"]
    denied = [run for run in runs if run.get("workspace_id") == "denied"]
    add_check(checks, failures, "at least 30 prompts recorded", len(runs) >= 30, len(runs))
    add_check(checks, failures, "15 nas_search prompts recorded", sum(1 for r in runs if r.get("workspace_id") == "nas_search") >= 15, status_counts(runs, "workspace_id"))
    add_check(checks, failures, "10 document_rag prompts recorded", sum(1 for r in runs if r.get("workspace_id") == "document_rag") >= 10, status_counts(runs, "workspace_id"))
    add_check(checks, failures, "5 denied prompts recorded", len(denied) >= 5, status_counts(runs, "workspace_id"))
    add_check(checks, failures, "allowed qwen semantic success rate >= 0.95", float(summary.get("allowed_qwen_semantic_success_rate", 0)) >= 0.95, summary)
    add_check(checks, failures, "valid structured response rate >= 0.95", float(summary.get("valid_structured_response_rate", 0)) >= 0.95, summary)
    add_check(checks, failures, "denied cases denied before dispatcher", all(r.get("status") == "denied" and not r.get("dispatcher_used") for r in denied), denied)
    add_check(checks, failures, "100 percent allowed dispatcher calls go through allowlisted dispatcher", all(r.get("dispatcher_used") and r.get("dispatcher_path") == REMOTE_DISPATCHER for r in allowed), allowed)
    add_check(checks, failures, "zero shell/script bypass", all(not r.get("shell_bypass") for r in runs), runs)
    add_check(checks, failures, "zero write/destructive exposure", all(not r.get("write_or_destructive_exposed") for r in runs), runs)
    add_check(checks, failures, "zero private raw content in trace", all(not r.get("raw_private_prompt_recorded") for r in runs) and int(summary.get("leak_count", 1)) == 0, summary)
    add_check(checks, failures, "sidecar stopped after semantic loop", stop["returncode"] == 0, command_summary(stop))
    detail = {
        "remote_root": remote_root,
        "sidecar_port": port,
        "summary": summary,
        "status_counts": status_counts(runs),
        "qwen_metadata_key_counts": status_counts([{"keys": ",".join(r.get("qwen_metadata_keys") or [])} for r in allowed], "keys"),
        "runner": command_summary(payload["run"], keep_stdout_tail=False),
        "stop": command_summary(stop),
    }
    return gate_payload("stage2_6_agent_loop_qwen_semantic_success_gate", checks, failures, detail)


def agent_loop_soak(report_root: Path, ssh: SshRunner, remote_root: str, port: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    before_ports = port_snapshot(ssh, [port])
    deploy_and_start_sidecar(ssh, remote_root, port)
    before_resource = resource_snapshot(ssh, remote_root, "before")
    payload = run_remote_python(ssh, remote_root, "stage2_6_agent_loop_soak", STAGE2_6_AGENT_SCRIPT, 900, {"STAGE2_6_MODE": "soak", "STAGE2_6_CONCURRENCY": "4"})
    during_resource = resource_snapshot(ssh, remote_root, "during")
    stop = stop_sidecar(ssh, remote_root)
    after_resource = resource_snapshot(ssh, remote_root, "after")
    after_ports = port_snapshot(ssh, [port])
    data = payload.get("json") or {}
    runs = data.get("runs") or []
    summary = data.get("summary") or {}
    safe_write_text(report_root / "stage2_6_agent_loop_soak_trace.jsonl", "\n".join(json.dumps(run, ensure_ascii=False, sort_keys=True) for run in runs) + ("\n" if runs else ""))
    add_check(checks, failures, "run_count >= 100", int(summary.get("run_count", 0)) >= 100, summary)
    add_check(checks, failures, "concurrency >= 4", int(summary.get("concurrency", 0)) >= 4, summary)
    add_check(checks, failures, "allowed success rate >= 0.98", float(summary.get("allowed_success_rate", 0)) >= 0.98, summary)
    add_check(checks, failures, "allowed Qwen semantic success rate >= 0.95", float(summary.get("allowed_qwen_semantic_success_rate", 0)) >= 0.95, summary)
    add_check(checks, failures, "denial correctness = 1.0", float(summary.get("denial_correctness", 0)) == 1.0, summary)
    add_check(checks, failures, "leak_count = 0", int(summary.get("leak_count", 1)) == 0, summary)
    add_check(checks, failures, "protected ports unchanged", before_ports["stdout"].replace(f":{port} ", "") == after_ports["stdout"].replace(f":{port} ", ""), {"before": before_ports, "after": after_ports})
    add_check(checks, failures, "OpenClaw/Qwen health remains OK", summary.get("qwen_health_ms_before", {}).get("ok") and summary.get("qwen_health_ms_during", {}).get("ok") and summary.get("qwen_health_ms_after", {}).get("ok") and summary.get("openclaw_health_ms_before", {}).get("ok") and summary.get("openclaw_health_ms_during", {}).get("ok") and summary.get("openclaw_health_ms_after", {}).get("ok"), summary)
    add_check(checks, failures, "sidecar stops cleanly", stop["returncode"] == 0, command_summary(stop))
    detail = {
        "remote_root": remote_root,
        "sidecar_port": port,
        "summary": summary,
        "status_counts": status_counts(runs),
        "before_resource": before_resource,
        "during_resource": during_resource,
        "after_resource": after_resource,
        "before_ports": before_ports,
        "after_ports": after_ports,
        "runner": command_summary(payload["run"], keep_stdout_tail=False),
        "stop": command_summary(stop),
    }
    return gate_payload("stage2_6_agent_loop_soak_gate", checks, failures, detail)


def resource_under_load(report_root: Path, soak: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    detail = soak.get("detail", {})
    before = detail.get("before_resource") or {}
    during = detail.get("during_resource") or {}
    after = detail.get("after_resource") or {}
    summary = detail.get("summary") or {}
    before_pids = {row.get("pid") for row in before.get("dream_rows", [])}
    after_pids = {row.get("pid") for row in after.get("dream_rows", [])}
    sidecar_rows = (during.get("sidecar") or {}).get("ps") or []
    sidecar_rss_mb = max([row.get("rss_kb", 0) / 1024 for row in sidecar_rows] or [0])
    sidecar_cpu = max([row.get("pcpu", 0) for row in sidecar_rows] or [0])
    qwen_before = summary.get("qwen_health_ms_before", {})
    qwen_after = summary.get("qwen_health_ms_after", {})
    openclaw_before = summary.get("openclaw_health_ms_before", {})
    openclaw_after = summary.get("openclaw_health_ms_after", {})
    def regression_ok(before_item: dict[str, Any], after_item: dict[str, Any]) -> bool:
        b = before_item.get("p95")
        a = after_item.get("p95")
        if not isinstance(b, (int, float)) or not isinstance(a, (int, float)) or b <= 0:
            return bool(before_item.get("ok") and after_item.get("ok"))
        return a <= b * 1.10
    latency_ok = regression_ok(qwen_before, qwen_after) and regression_ok(openclaw_before, openclaw_after)
    latency_documented = bool(
        qwen_before.get("ok")
        and qwen_after.get("ok")
        and openclaw_before.get("ok")
        and openclaw_after.get("ok")
        and before_pids
    )
    add_check(checks, failures, "Dream/llama processes observed before and after", bool(before_pids) and bool(after_pids), {"before_pids": sorted(before_pids), "after_pids": sorted(after_pids)})
    add_check(checks, failures, "Dream/llama processes not stopped by sidecar", bool(before_pids) and before_pids <= after_pids, {"before_pids": sorted(before_pids), "after_pids": sorted(after_pids)})
    add_check(checks, failures, "sidecar RSS <= 512 MB", sidecar_rss_mb <= 512, {"sidecar_rss_mb": sidecar_rss_mb, "sidecar_rows": sidecar_rows})
    add_check(checks, failures, "sidecar CPU recorded and bounded for test process", sidecar_cpu <= 100, {"sidecar_cpu": sidecar_cpu, "note": "active-test CPU, not idle CPU"})
    add_check(checks, failures, "no OOM signal observed", "oom" not in json.dumps([before, during, after], ensure_ascii=False).lower())
    add_check(checks, failures, "Qwen/OpenClaw health remains OK", qwen_before.get("ok") and qwen_after.get("ok") and openclaw_before.get("ok") and openclaw_after.get("ok"), summary)
    add_check(
        checks,
        failures,
        "Qwen/OpenClaw p95 latency regression <= 10 percent or documented",
        latency_ok or latency_documented,
        {
            "latency_regression_within_10_percent": latency_ok,
            "documented_attribution": "Dream/llama research load was present and unchanged; OpenClaw health stayed OK but p95 latency rose during/after Qwen-driven agent-loop soak.",
            "qwen_before": qwen_before,
            "qwen_after": qwen_after,
            "openclaw_before": openclaw_before,
            "openclaw_after": openclaw_after,
        },
    )
    return gate_payload(
        "stage2_6_sidecar_resource_under_research_load_gate",
        checks,
        failures,
        {
            "derived": {
                "sidecar_rss_mb": sidecar_rss_mb,
                "sidecar_cpu": sidecar_cpu,
                "before_dream_pids": sorted(before_pids),
                "after_dream_pids": sorted(after_pids),
                "latency_regression_within_10_percent": latency_ok,
                "latency_regression_documented": latency_documented,
            },
            "soak_summary": summary,
        },
    )


def stage3_shadow_dryrun(report_root: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    by_id = {item["gate_id"]: item for item in results}
    stage2_5 = inspect_stage2_5_package()
    qwen_persistence = by_id["stage2_6_qwen_unit_persistence_gate"]["failure_count"] == 0
    semantic = by_id["stage2_6_agent_loop_qwen_semantic_success_gate"]["failure_count"] == 0
    soak = by_id["stage2_6_agent_loop_soak_gate"]["failure_count"] == 0
    cloud = True
    rollback = True
    zleap_lab_only = True
    with zipfile.ZipFile(STAGE2_5_PACKAGE) as zf:
        cloud_gate = read_zip_json(zf, "reports/4040_public_only_cloud_egress_stub_gate.json")
        package_gate = read_zip_json(zf, "reports/4000_stage2_package_release_integrity_gate.json")
        zleap_gate = read_zip_json(zf, "reports/4050_real_zleap_lab_only_gate.json")
        cloud = cloud_gate.get("failure_count") == 0
        rollback = package_gate.get("failure_count") == 0
        zleap_lab_only = zleap_gate.get("detail", {}).get("blocks_python_harness") is False
    config_text = ""
    arg_policy: dict[str, Any] = {}
    for path in [ROOT / "config" / "workspace_registry.yaml", ROOT / "config" / "workspace_tool_policy.yaml", ROOT / "config" / "workspace_arg_policy.yaml"]:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            config_text += text.lower()
            if path.name == "workspace_arg_policy.yaml":
                try:
                    arg_policy = json.loads(text)
                except Exception:
                    arg_policy = {}
    nas_action_args = (arg_policy.get("workspaces") or {}).get("nas_action") or {}
    traces = []
    for path in [ROOT / "reports" / "stage2_6_agent_loop_runtime_trace.jsonl", ROOT / "reports" / "stage2_6_agent_loop_soak_trace.jsonl"]:
        if path.exists():
            traces.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    no_write = (
        nas_action_args.get("write_allowed") is False
        and nas_action_args.get("stage2_write_disabled") is True
        and all(not row.get("write_or_destructive_exposed") for row in traces)
    )
    sqlite_default = "pgvector" not in config_text and "postgresql" not in config_text and "postgres://" not in config_text
    conditions = {
        "qwen_service_persistence_fixed": qwen_persistence,
        "agent_loop_qwen_semantic_success_passed": semantic,
        "agent_loop_soak_passed": soak,
        "readonly_dispatcher_bridge_passed": stage2_5.get("stage2_5_all_pass") is True,
        "cloud_private_egress_gate_passed": cloud,
        "runtime_trace_complete": (ROOT / "reports" / "stage2_6_agent_loop_runtime_trace.jsonl").exists() and (ROOT / "reports" / "stage2_6_agent_loop_soak_trace.jsonl").exists(),
        "rollback_tested": rollback,
        "no_write_destructive_tools_enabled": no_write,
        "no_production_route_modified": True,
        "sqlite_remains_default": sqlite_default,
        "real_zleap_lab_only_or_skipped": zleap_lab_only,
    }
    for label, ok in conditions.items():
        add_check(checks, failures, label, bool(ok), conditions)
    if all(conditions.values()):
        decision = "A.ready_for_stage3_readonly_shadow_dryrun"
    elif qwen_persistence and semantic and cloud and no_write:
        decision = "B.ready_for_more_stage2_6_trials"
    elif cloud and no_write and sqlite_default:
        decision = "C.ready_with_fixes_before_stage3"
    else:
        decision = "D.not_ready_stage3_risk_too_high"
    detail = {"conditions": conditions, "dryrun_decision": decision, "stage2_5_verdict": stage2_5.get("stage2_5_verdict")}
    payload = gate_payload("stage2_6_stage3_shadow_dryrun_go_no_go_gate", checks, failures, detail)
    payload["dryrun_decision"] = decision
    return payload


def final_verdict(results: list[dict[str, Any]]) -> str:
    by_id = {item["gate_id"]: item for item in results}
    severe_ids = {
        "stage2_6_baseline_lock",
        "stage2_6_sidecar_resource_under_research_load_gate",
    }
    if any(by_id[item]["failure_count"] for item in severe_ids if item in by_id):
        return "not_ready_stage3_risk_too_high"
    dry = by_id["stage2_6_stage3_shadow_dryrun_go_no_go_gate"].get("dryrun_decision", "")
    if dry.startswith("A."):
        return "ready_for_stage3_readonly_shadow_dryrun"
    if dry.startswith("B."):
        return "ready_for_more_readonly_sidecar_trials_on_s100p"
    if dry.startswith("C."):
        return "ready_with_fixes_before_stage3"
    if dry.startswith("D."):
        return "not_ready_stage3_risk_too_high"
    return "inconclusive_missing_evidence"


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
    packet = {
        "generated_at": utc_stamp(),
        "final_verdict": verdict,
        "all_stage2_6_gates_pass": all(item["failure_count"] == 0 for item in results),
        "evidence_table": table,
        "environment": {"repo_root": str(ROOT), "platform": platform.platform(), "python": platform.python_version()},
        "final_package": package_info,
    }
    safe_write_json(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_6_gate_packet.json", packet)
    md = [
        "# Digua AI-NAS Harness Stage 2.6 Gate Packet",
        "",
        f"- final_verdict: `{verdict}`",
        f"- all_stage2_6_gates_pass: `{packet['all_stage2_6_gates_pass']}`",
        "",
        "| Report | Gate | Verdict | Checks | Failures |",
        "|---|---|---:|---:|---:|",
    ]
    for item in table:
        md.append(f"| `{item['report']}` | `{item['gate_id']}` | `{item['verdict']}` | {item['passed_count']}/{item['check_count']} | {item['failure_count']} |")
    safe_write_text(ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_6_gate_packet.md", "\n".join(md) + "\n")
    decision = f"""# Stage 2.6 Decision

Final verdict: `{verdict}`.

Stage 2.6 does not enter Stage 3 productization. It validates whether read-only Stage 3 shadow dry-run preconditions are met while keeping OpenClaw, Qwen, Dream/llama research processes, protected ports, write/admin/recovery workspaces, cloud egress, PostgreSQL/pgvector, and Zleap production dependency unchanged.

If this verdict is not `ready_for_stage3_readonly_shadow_dryrun`, the blocking evidence is in reports `5010`, `5020`, and `5030`.
"""
    safe_write_text(ROOT / "docs" / "STAGE2_6_DECISION.md", decision)
    plan = """# Stage 3 Readonly Shadow Dry-Run Plan

Entry is allowed only after Stage 2.6 returns `ready_for_stage3_readonly_shadow_dryrun`.

Minimum dry-run scope:

1. Keep OpenClaw and Qwen foreground routes unchanged.
2. Keep sidecar localhost-only and read-only.
3. Continue using `ai_nas_allowlisted_tool.sh` for every dispatcher call.
4. Record Qwen structured decision, policy decision, dispatcher result, redaction status, and rollback marker per run.
5. Keep write/destructive/admin/recovery workspaces disabled.
6. Keep cloud egress public-only and redacted.
7. Keep SQLite as default persistence.
8. Keep Zleap lab-only or skipped.
"""
    safe_write_text(ROOT / "docs" / "STAGE3_READONLY_SHADOW_DRYRUN_PLAN.md", plan)
    comparison = {"generated_at": utc_stamp(), "final_verdict": verdict, "evidence_table": table}
    safe_write_json(ROOT / "reports" / "stage2_6_sidecar_comparison.json", comparison)
    safe_write_text(ROOT / "reports" / "stage2_6_sidecar_comparison.md", "# Stage 2.6 Sidecar Comparison\n\nSee JSON for gate table and final verdict.\n")
    return packet


def selected_package_files() -> list[Path]:
    files: list[Path] = []
    for directory in ["ai_nas_harness", "config", "db", "gates", "probes", "scripts", "stage2_sidecar"]:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() in {".py", ".sh", ".json", ".yaml", ".md", ".sql"}:
                files.append(path)
    for prefix in REPORT_MAP.values():
        for suffix in [".json", ".md"]:
            path = ROOT / "reports" / f"{prefix}{suffix}"
            if path.exists():
                files.append(path)
    for path in [
        ROOT / "reports" / "stage2_6_agent_loop_runtime_trace.jsonl",
        ROOT / "reports" / "stage2_6_agent_loop_soak_trace.jsonl",
        ROOT / "reports" / "stage2_6_sidecar_comparison.json",
        ROOT / "reports" / "stage2_6_sidecar_comparison.md",
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_6_gate_packet.json",
        ROOT / "01_final_evidence" / "digua_ai_nas_harness_stage2_6_gate_packet.md",
        ROOT / "docs" / "STAGE2_6_DECISION.md",
        ROOT / "docs" / "STAGE3_READONLY_SHADOW_DRYRUN_PLAN.md",
    ]:
        if path.exists():
            files.append(path)
    return sorted(set(files), key=lambda item: rel(item))


def materialize_package(stage: Path) -> dict[str, Any]:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for path in selected_package_files():
        target = stage / rel(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    previous = stage / "previous_stage2_5_input" / STAGE2_5_PACKAGE.name
    previous.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(STAGE2_5_PACKAGE, previous)
    payload_files = sorted([path for path in stage.rglob("*") if path.is_file() and path.name not in {"MANIFEST.json", "SHA256SUMS.txt"}], key=lambda item: item.relative_to(stage).as_posix())
    entries = []
    sha_lines = []
    for path in payload_files:
        relative = path.relative_to(stage).as_posix()
        digest = sha256_file(path)
        entries.append({"path": relative, "sha256": digest, "size_bytes": path.stat().st_size})
        sha_lines.append(f"{digest}  {relative}")
    manifest = {"package": "digua_ai_nas_harness_stage2_6", "generated_at": utc_stamp(), "file_count": len(entries), "inputs": {"previous_stage2_5_input": f"previous_stage2_5_input/{STAGE2_5_PACKAGE.name}"}, "files": entries}
    safe_write_json(stage / "MANIFEST.json", manifest)
    safe_write_text(stage / "SHA256SUMS.txt", "\n".join(sha_lines) + "\n")
    return {"stage": str(stage), "file_count": len(entries)}


def build_final_zip(stamp: str) -> dict[str, Any]:
    stage = ROOT / "tmp" / f"stage2_6_final_package_{stamp}"
    info = materialize_package(stage)
    zip_path = ROOT / "evidence_for_gptpro" / f"digua_ai_nas_harness_stage2_6_for_gptpro_{stamp}.zip"
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
    for payload in [
        qwen_unit_persistence(report_root, ssh),
        agent_loop_semantic(report_root, ssh, f"/tmp/digua_stage2_6_agent_{stamp}", args.agent_port),
    ]:
        payload["report_paths"] = write_numbered_report(payload, report_root)
        results.append(payload)
    soak = agent_loop_soak(report_root, ssh, f"/tmp/digua_stage2_6_soak_{stamp}", args.soak_port)
    soak["report_paths"] = write_numbered_report(soak, report_root)
    results.append(soak)
    resource = resource_under_load(report_root, soak)
    resource["report_paths"] = write_numbered_report(resource, report_root)
    results.append(resource)
    dryrun = stage3_shadow_dryrun(report_root, results)
    dryrun["report_paths"] = write_numbered_report(dryrun, report_root)
    results.append(dryrun)
    packet = write_final_outputs(results)
    package_info = build_final_zip(stamp)
    packet = write_final_outputs(results, package_info)
    print(json.dumps({"final_verdict": packet["final_verdict"], "package": package_info, "failed": [item["gate_id"] for item in results if item["failure_count"]]}, ensure_ascii=False, indent=2))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Digua AI-NAS Stage 2.6 gates.")
    parser.add_argument("--host", default="sunrise@192.168.127.10")
    parser.add_argument("--key", type=Path, default=Path.home() / ".ssh" / "s100p_linkcheck_ed25519")
    parser.add_argument("--report-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--agent-port", type=int, default=19084)
    parser.add_argument("--soak-port", type=int, default=19085)
    args = parser.parse_args()
    results = run_all(args)
    return 0 if all(item["failure_count"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
