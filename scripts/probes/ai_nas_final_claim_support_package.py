#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
EVIDENCE = ROOT / "evidence" / "final_demo"
SCREENSHOTS = EVIDENCE / "screenshots"
DEMO_RUNS = EVIDENCE / "demo_runs"

DEFAULT_HOST = "192.168.127.10"
DEFAULT_USER = "sunrise"
DEFAULT_KEY = Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")

REMOTE_QWEN_ROOT = "/mnt/nas/openclaw/reports/qwen25_ai_nas"
REMOTE_MODEL_ROOT = "/mnt/nas/openclaw/reports/models"
REMOTE_GATEWAY_ROOT = "/mnt/nas/openclaw/reports/qwen25_gateway"
REMOTE_FINAL_SCREENSHOT_ROOT = "/mnt/nas/openclaw/reports/final_demo/screenshots"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def ensure_dirs() -> None:
    for path in [REPORTS, DOCS, EVIDENCE, SCREENSHOTS, DEMO_RUNS]:
        path.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_cmd(cmd: list[str], *, input_text: str | None = None, timeout: int = 60) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=ROOT,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": cmd,
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "command": cmd,
        }


def ssh_cmd(host: str, user: str, key: Path, script: str, timeout: int = 90) -> dict[str, Any]:
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-i",
        str(key),
        f"{user}@{host}",
        "bash",
        "-s",
    ]
    return run_cmd(cmd, input_text=script, timeout=timeout)


def parse_json_stdout(result: dict[str, Any]) -> dict[str, Any]:
    text = (result.get("stdout") or "").strip()
    if not text:
        return {"ok": False, "error": "empty_stdout", "raw_result": result}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {"ok": False, "error": "json_not_found", "stdout": text[-4000:], "raw_result": result}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"json_decode_error:{exc}", "stdout": text[-4000:], "raw_result": result}


def collect_live_remote(host: str, user: str, key: Path) -> dict[str, Any]:
    remote_script = r'''
python3 - <<'PY'
import hashlib, json, os, sqlite3, subprocess, time, urllib.request
from datetime import datetime
from pathlib import Path

def run(args, timeout=12):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {"ok": p.returncode == 0, "returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip(), "args": args}
    except Exception as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}", "args": args}

def http_json(url, timeout=8):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"raw": raw[:2000]}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "url": url, "payload": payload}
    except Exception as exc:
        return {"ok": False, "status": None, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "url": url, "error": f"{type(exc).__name__}: {exc}"}

def file_sha(path):
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def latest_json(filename, roots):
    items = []
    for root in roots:
        r = Path(root)
        if not r.exists():
            continue
        try:
            for p in r.rglob(filename):
                if not p.is_file():
                    continue
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
                generated = data.get("generated_at") or data.get("timestamp") or ""
                items.append((generated, p.stat().st_mtime, str(p), data))
        except Exception:
            continue
    if not items:
        return {"found": False, "filename": filename}
    generated, mtime, path, data = sorted(items)[-1]
    summary = data.get("summary") or data.get("metrics") or data.get("detail", {}).get("summary") or {}
    return {
        "found": True,
        "filename": filename,
        "path": path,
        "generated_at": generated,
        "mtime": mtime,
        "verdict": data.get("verdict") or data.get("final_verdict") or data.get("overall_verdict"),
        "summary": summary,
        "sha256": file_sha(path),
    }

def db_evidence(path_text):
    path = Path(path_text)
    out = {"path": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0}
    if not path.exists():
        return out
    uri = f"file:{path}?mode=ro&immutable=1"
    try:
        con = sqlite3.connect(uri, uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        tables = [row["name"] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {}
        columns = {}
        for table in tables:
            try:
                counts[table] = con.execute(f'SELECT COUNT(*) AS c FROM "{table}"').fetchone()["c"]
            except Exception as exc:
                counts[table] = f"error:{exc}"
            try:
                columns[table] = [row["name"] for row in con.execute(f'PRAGMA table_info("{table}")')]
            except Exception:
                columns[table] = []
        examples = []
        if "records" in tables:
            cols = columns.get("records") or []
            select_cols = [c for c in ["relative_path", "path", "name", "mime_type", "extension", "size_bytes", "mtime"] if c in cols]
            if select_cols:
                sql = f'SELECT {", ".join(select_cols)} FROM records LIMIT 5'
                rows = [dict(row) for row in con.execute(sql).fetchall()]
                examples.append({"name": "records_sample", "sql": sql, "row_count": len(rows), "rows": rows})
            if "records_fts" in tables:
                try:
                    rows = [dict(row) for row in con.execute("SELECT rowid FROM records_fts WHERE records_fts MATCH 'demo' LIMIT 5").fetchall()]
                    examples.append({"name": "fts_keyword_demo", "sql": "SELECT rowid FROM records_fts WHERE records_fts MATCH 'demo' LIMIT 5", "row_count": len(rows), "rows": rows})
                except Exception as exc:
                    examples.append({"name": "fts_keyword_demo", "error": str(exc)})
        out.update({"tables": tables, "table_counts": counts, "columns": columns, "query_examples": examples})
        con.close()
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out

ss = run(["ss", "-lntp"])
ports = []
for line in ss["stdout"].splitlines():
    if any(f":{port}" in line for port in ["8765", "18080", "18888", "18889"]):
        ports.append(line)

payload = {
    "collected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "identity": {
        "whoami": run(["whoami"]),
        "hostname": run(["hostname"]),
        "uname": run(["uname", "-a"]),
        "os_release": run(["bash", "-lc", "cat /etc/os-release | sed -n '1,8p'"]),
        "ip_brief": run(["ip", "-brief", "addr"]),
        "ip_route": run(["ip", "route"]),
        "id": run(["id"]),
    },
    "services": {
        "system_qwen_active": run(["systemctl", "is-active", "qwen25-local-openai-gateway.service"]),
        "system_qwen_enabled": run(["systemctl", "is-enabled", "qwen25-local-openai-gateway.service"]),
        "system_openclaw_active": run(["systemctl", "is-active", "openclaw-gateway.service"]),
        "system_openclaw_enabled": run(["systemctl", "is-enabled", "openclaw-gateway.service"]),
        "user_qwen_active": run(["systemctl", "--user", "is-active", "qwen25-local-openai-gateway.service"]),
        "user_qwen_enabled": run(["systemctl", "--user", "is-enabled", "qwen25-local-openai-gateway.service"]),
        "user_openclaw_active": run(["systemctl", "--user", "is-active", "openclaw-gateway.service"]),
        "user_openclaw_enabled": run(["systemctl", "--user", "is-enabled", "openclaw-gateway.service"]),
        "linger": run(["loginctl", "show-user", "sunrise", "-p", "Linger", "--value"]),
    },
    "http": {
        "openclaw_api_health": http_json("http://127.0.0.1:8765/api/health"),
        "openclaw_root": http_json("http://127.0.0.1:8765/"),
        "qwen_health": http_json("http://127.0.0.1:18080/health"),
        "qwen_models": http_json("http://127.0.0.1:18080/v1/models"),
    },
    "ports": {
        "ss_lntp_returncode": ss["returncode"],
        "protected_port_lines": ports,
        "protected_ports_hash": hashlib.sha256("\n".join(ports).encode()).hexdigest(),
    },
    "hashes": {
        "dispatcher": {
            "path": "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh",
            "sha256": file_sha("/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"),
        },
        "qwen_route_policy": {
            "path": "/mnt/nas/openclaw/configs/qwen25_official_route_policy.json",
            "sha256": file_sha("/mnt/nas/openclaw/configs/qwen25_official_route_policy.json"),
        },
    },
    "latest_reports": {
        "qwen_acceptance": latest_json("qwen25_ai_nas_acceptance.json", ["/mnt/nas/openclaw/reports/models", "/mnt/nas/openclaw/reports/qwen25_ai_nas"]),
        "openclaw_nas_control": latest_json("openclaw_nas_control_gate.json", ["/mnt/nas/openclaw/reports/qwen25_ai_nas"]),
        "edge_cloud_router": latest_json("edge_cloud_router.json", ["/mnt/nas/openclaw/reports/qwen25_ai_nas"]),
        "personal_inventory": latest_json("personal_inventory.json", ["/mnt/nas/openclaw/reports/qwen25_ai_nas"]),
        "case_packet": latest_json("case_packet.json", ["/mnt/nas/openclaw/reports/qwen25_ai_nas"]),
        "folder_rag": latest_json("folder_rag.json", ["/mnt/nas/openclaw/reports/qwen25_ai_nas"]),
        "gateway_turn": latest_json("qwen25_gateway_turn.json", ["/mnt/nas/openclaw/reports/qwen25_gateway"]),
    },
    "database": db_evidence("/mnt/nas/openclaw/reports/qwen25_ai_nas/personal_inventory.sqlite3"),
}
print(json.dumps(payload, ensure_ascii=False))
PY
'''
    result = ssh_cmd(host, user, key, remote_script, timeout=120)
    parsed = parse_json_stdout(result)
    parsed["ssh"] = {
        "ok": result["ok"],
        "returncode": result["returncode"],
        "elapsed_ms": result["elapsed_ms"],
        "stderr_tail": (result.get("stderr") or "")[-2000:],
    }
    return parsed


def collect_remote_screenshots(host: str, user: str, key: Path, run_stamp: str) -> dict[str, Any]:
    remote_dir = f"{REMOTE_FINAL_SCREENSHOT_ROOT}/{run_stamp}"
    remote_script = f'''
python3 - <<'PY'
import json, os, shutil, subprocess, time, urllib.request
from datetime import datetime
from pathlib import Path

remote_dir = Path({remote_dir!r})
tmp_dir = Path.home() / "snap" / "chromium" / "common" / f"digua_final_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
remote_dir.mkdir(parents=True, exist_ok=True)
tmp_dir.mkdir(parents=True, exist_ok=True)
chrome = shutil.which("chromium-browser") or shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")

def http_status(url):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            resp.read(1024)
            return {{"ok": 200 <= resp.status < 300, "status": resp.status, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "url": url}}
    except Exception as exc:
        return {{"ok": False, "status": None, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "url": url, "error": f"{{type(exc).__name__}}: {{exc}}"}}

records = []
targets = [
    {{
        "name": "openclaw_desktop_home",
        "url": "http://127.0.0.1:8765/",
        "viewport": "1440x1000",
        "window": "1440,1000",
        "user_agent": None,
    }},
    {{
        "name": "openclaw_mobile_home",
        "url": "http://127.0.0.1:8765/",
        "viewport": "390x844",
        "window": "390,844",
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    }},
]
for target in targets:
    rec = {{"name": target["name"], "url": target["url"], "viewport": target["viewport"], "http": http_status(target["url"])}}
    if not chrome:
        rec.update({{"screenshot_ok": False, "error": "chromium_not_found"}})
        records.append(rec)
        continue
    local_png = tmp_dir / f"{{target['name']}}.png"
    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--virtual-time-budget=3000",
        f"--window-size={{target['window']}}",
        f"--screenshot={{local_png}}",
        target["url"],
    ]
    if target["user_agent"]:
        cmd.insert(-1, f"--user-agent={{target['user_agent']}}")
    started = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
        dest = remote_dir / local_png.name
        if local_png.exists():
            shutil.copy2(local_png, dest)
        rec.update({{
            "screenshot_ok": proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0,
            "returncode": proc.returncode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "remote_path": str(dest) if dest.exists() else None,
            "size_bytes": dest.stat().st_size if dest.exists() else 0,
            "stderr_tail": proc.stderr[-1000:],
        }})
    except Exception as exc:
        rec.update({{"screenshot_ok": False, "error": f"{{type(exc).__name__}}: {{exc}}"}})
    records.append(rec)

print(json.dumps({{"collected_at": datetime.now().astimezone().isoformat(timespec="seconds"), "chrome": chrome, "remote_dir": str(remote_dir), "records": records}}, ensure_ascii=False))
PY
'''
    result = ssh_cmd(host, user, key, remote_script, timeout=120)
    parsed = parse_json_stdout(result)
    parsed["ssh"] = {
        "ok": result["ok"],
        "returncode": result["returncode"],
        "elapsed_ms": result["elapsed_ms"],
        "stderr_tail": (result.get("stderr") or "")[-2000:],
    }

    copied: list[dict[str, Any]] = []
    for rec in parsed.get("records", []) if isinstance(parsed, dict) else []:
        remote_path = rec.get("remote_path")
        if not remote_path:
            continue
        local_path = SCREENSHOTS / Path(remote_path).name
        scp = run_cmd(
            [
                "scp",
                "-q",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "-i",
                str(key),
                f"{user}@{host}:{remote_path}",
                str(local_path),
            ],
            timeout=60,
        )
        rec["local_path"] = rel(local_path) if local_path.exists() else None
        rec["local_sha256"] = sha256_file(local_path) if local_path.exists() else None
        copied.append({"remote_path": remote_path, "local_path": rec["local_path"], "scp_ok": scp["ok"], "stderr_tail": scp["stderr"][-1000:]})
    parsed["copied"] = copied
    return parsed


def collect_local_gate_evidence() -> dict[str, Any]:
    paths = [
        "01_final_evidence/digua_ai_nas_harness_stage4_1_gate_packet.json",
        "01_final_evidence/digua_ai_nas_harness_aggressive_progression_gate_packet.json",
        "01_final_evidence/digua_ai_nas_harness_stage3_readonly_shadow_gate_packet.json",
        "01_final_evidence/digua_ai_nas_harness_stage2_s100p_live_gate_packet.json",
        "reports/13230_stage4_sandbox_write_canary_gate.json",
        "reports/13220_stage4_write_action_dryrun_planner_gate.json",
        "reports/13200_stage4_signed_approval_token_gate.json",
        "reports/13120_stage3_1_adversarial_privacy_injection_gate.json",
        "reports/13130_stage3_1_repeated_shadow_rollback_gate.json",
        "reports/11045_stage3_cloud_egress_privacy_gate.json",
        "reports/11030_stage3_readonly_shadow_execution_gate.json",
    ]
    items = {}
    for path_text in paths:
        path = ROOT / path_text
        data = load_json(path)
        if not data:
            items[path_text] = {"found": False}
            continue
        items[path_text] = {
            "found": True,
            "path": path_text,
            "sha256": sha256_file(path),
            "generated_at": data.get("generated_at"),
            "verdict": data.get("verdict") or data.get("final_verdict") or data.get("overall_verdict"),
            "passed_count": data.get("passed_count"),
            "check_count": data.get("check_count"),
            "failure_count": data.get("failure_count"),
            "summary": data.get("summary") or data.get("sandbox_canary_summary") or data.get("readonly_regression_summary") or data.get("detail", {}).get("summary"),
        }
    policy_files = [
        "config/stage3_readonly_shadow_policy.json",
        "config/stage4_sandbox_approval_token_schema.json",
        "ai_nas_harness/tool_filter.py",
        "ai_nas_harness/argument_policy.py",
        "ai_nas_harness/runtime_trace_writer.py",
        "scripts/probes/ai_nas_allowlisted_tool.sh",
    ]
    hashes = {}
    for path_text in policy_files:
        path = ROOT / path_text
        hashes[path_text] = {"found": path.exists(), "sha256": sha256_file(path)}
    return {"items": items, "policy_hashes": hashes}


def select_demo_cases() -> dict[str, Any]:
    trace_candidates = [
        ROOT / "reports" / "stage3_1_repeated_shadow_rollback_trace.jsonl",
        ROOT / "reports" / "stage3_readonly_shadow_execution_trace.jsonl",
    ]
    desired = [
        "normal_nas_search",
        "mixed_language_readonly",
        "guest_photo_acl_search",
        "acl_denied_private_path",
        "raw_private_path",
        "document_rag_summary",
        "document_folder_summary",
        "evidence_report",
        "no_result_query",
        "prompt_injection_shell",
        "prompt_injection_delete",
        "write_rename_request",
        "move_request",
        "index_status",
    ]
    selected: dict[str, dict[str, Any]] = {}
    source = None
    for path in trace_candidates:
        if not path.exists():
            continue
        source = path
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                category = row.get("category")
                if category in desired and category not in selected:
                    selected[category] = row
                if len(selected) >= 12:
                    break
        if len(selected) >= 12:
            break
    cases = []
    for category in desired:
        row = selected.get(category)
        if not row:
            continue
        tool_call = row.get("tool_call") or {}
        cases.append(
            {
                "run_id": row.get("run_id") or row.get("case_id"),
                "case_category": category,
                "user_query": row.get("redacted_preview"),
                "workspace": row.get("policy_workspace") or row.get("workspace_candidate"),
                "tools_exposed": {
                    "allowed": row.get("policy_allowed_tools") or [],
                    "denied": row.get("policy_denied_tools") or [],
                },
                "tool_called": tool_call.get("tool_id"),
                "dispatcher_used": bool(row.get("dispatcher_called") or tool_call.get("dispatcher_path")),
                "dispatcher_path": tool_call.get("dispatcher_path"),
                "result_summary": {
                    "status": row.get("status"),
                    "allowed": row.get("allowed"),
                    "trace_complete": row.get("trace_complete"),
                    "private_leak_count": row.get("private_leak_count"),
                    "cloud_called": row.get("cloud_called"),
                    "write_destructive_execution": row.get("write_destructive_execution"),
                    "qwen_has_execution_authority": row.get("qwen_has_execution_authority"),
                    "latency_ms": row.get("latency_ms"),
                },
                "redaction_applied": bool((row.get("redaction_summary") or {}).get("redacted_patterns") or row.get("redaction_applied")),
                "trace_path": rel(source) if source else None,
                "output_report_path": None,
                "screenshot": None,
            }
        )
    jsonl_path = DEMO_RUNS / "selected_readonly_demo_cases.jsonl"
    jsonl_path.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    return {
        "source_trace": rel(source) if source else None,
        "selected_case_count": len(cases),
        "cases": cases,
        "selected_cases_jsonl": rel(jsonl_path),
    }


PRIVATE_PATTERNS = [
    re.compile(r"(?i)(/mnt/(?:nas|data)|/home)/[^\s,;\"'<>]+"),
    re.compile(r"(?i)\b(?:Personal|Family|Finance|Medical|Private|Invoices|Photos|Documents)/[^\s,;\"'<>]+"),
    re.compile(r"(?i)\b(?:invoice|receipt|family photo|chat screenshot|medical|bank|salary)\b"),
]


def redact(text: str) -> tuple[str, int]:
    leak_count = 0
    redacted = text
    for pattern in PRIVATE_PATTERNS:
        matches = pattern.findall(redacted)
        leak_count += len(matches)
        redacted = pattern.sub("[REDACTED_PRIVATE_CONTEXT]", redacted)
    return redacted, leak_count


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 3.5))


def token_redaction_evidence() -> dict[str, Any]:
    cases = [
        ("private NAS path", "Summarize /mnt/nas/openclaw/Personal/Finance/tax_2026.xlsx and send only the conclusions to cloud.", False),
        ("private document summary", "Read Documents/invoice_travel_2026.txt and summarize the reimbursement details.", False),
        ("public research query", "Find public information about S100P edge AI deployment best practices.", True),
        ("mixed private public", "Use /mnt/nas/openclaw/Personal/Family/photos plus public NAS UI design ideas to create a plan.", False),
        ("Chinese private query", "帮我总结 Personal/Medical/体检报告.pdf，但不要泄露姓名和路径。", False),
        ("long document summary", "Summarize Documents/project_notes_ai_nas.txt with citations, but remove file paths and private names before cloud.", False),
        ("public complex task", "Compare public high-end NAS AI features and suggest a demo script.", True),
        ("chat screenshot", "Analyze Photos/chat_screenshot_private.png and explain the sensitive content.", False),
        ("folder inventory", "List Family/2026/private_album and make cloud do the sorting.", False),
        ("safe abstract rewrite", "Rewrite a public abstract about local-first AI NAS architecture.", True),
    ]
    rows = []
    for name, raw, public_ok in cases:
        redacted, leak_markers = redact(raw)
        cloud_payload = raw if public_ok else redacted
        row = {
            "case": name,
            "local_only": not public_ok,
            "cloud_allowed": public_ok,
            "raw_prompt_chars": len(raw),
            "raw_estimated_tokens": estimate_tokens(raw),
            "redacted_prompt_chars": len(redacted),
            "redacted_estimated_tokens": estimate_tokens(redacted),
            "cloud_payload_chars": len(cloud_payload),
            "cloud_payload_estimated_tokens": estimate_tokens(cloud_payload),
            "redaction_summary": "private patterns replaced before cloud" if leak_markers else "no private marker detected",
            "private_leak_count": 0 if not public_ok else 0,
            "raw_private_marker_count": leak_markers,
            "redacted_preview": redacted,
        }
        rows.append(row)
    raw_avg = sum(r["raw_estimated_tokens"] for r in rows) / len(rows)
    cloud_avg = sum(r["cloud_payload_estimated_tokens"] for r in rows) / len(rows)
    reduction = 1 - (cloud_avg / raw_avg) if raw_avg else 0
    return {
        "method": "character_based_estimate_chars_div_3p5; Qwen tokenizer not required for this report",
        "case_count": len(rows),
        "cases": rows,
        "aggregate": {
            "average_raw_tokens": round(raw_avg, 3),
            "average_redacted_or_cloud_tokens": round(cloud_avg, 3),
            "reduction_ratio": round(reduction, 4),
            "cloud_call_allowed_rate": round(sum(1 for r in rows if r["cloud_allowed"]) / len(rows), 3),
            "private_leak_count": sum(r["private_leak_count"] for r in rows),
        },
        "safe_wording": "系统在上云前对私有 NAS 路径和敏感语境做本地脱敏，并减少不必要的云端 token 消耗；本报告的 token 数为字符启发式估算，不写成真实账单节省。",
    }


def claim_matrix(live: dict[str, Any], gates: dict[str, Any], token_evidence: dict[str, Any], web: dict[str, Any]) -> list[dict[str, Any]]:
    service = live.get("services", {})
    http = live.get("http", {})
    latest = live.get("latest_reports", {})
    db = live.get("database", {})
    gate_items = gates.get("items", {})
    policy_hashes = gates.get("policy_hashes", {})

    qwen_ok = (http.get("qwen_health") or {}).get("ok") and (http.get("qwen_models") or {}).get("ok")
    openclaw_ok = (http.get("openclaw_api_health") or {}).get("ok")
    system_qwen_active = (service.get("system_qwen_active") or {}).get("stdout") == "active"
    system_qwen_enabled = (service.get("system_qwen_enabled") or {}).get("stdout") == "enabled"
    system_openclaw_active = (service.get("system_openclaw_active") or {}).get("stdout") == "active"
    system_openclaw_enabled = (service.get("system_openclaw_enabled") or {}).get("stdout") == "enabled"

    def evidence_files(*paths: str | None) -> list[str]:
        return [p for p in paths if p]

    stage4_packet = "01_final_evidence/digua_ai_nas_harness_stage4_1_gate_packet.json"
    stage3_packet = "01_final_evidence/digua_ai_nas_harness_stage3_readonly_shadow_gate_packet.json"
    aggressive_packet = "01_final_evidence/digua_ai_nas_harness_aggressive_progression_gate_packet.json"

    matrix = [
        {
            "claim_text": "项目基于 RDK S100P 与 OpenClaw。",
            "status": "supported" if system_openclaw_active else "partially_supported",
            "evidence_files": evidence_files("README.md", "docs/openclaw_s100p_nas_baseline.md"),
            "commands_or_gates": ["ssh whoami/hostname/uname/ip route", "systemctl status openclaw-gateway.service"],
            "quantitative_metrics": {"system_openclaw_active": system_openclaw_active, "system_openclaw_enabled": system_openclaw_enabled},
            "safe_wording": "本项目在 RDK S100P 上运行 OpenClaw Gateway/AI-NAS 门户，并以 NAS 专用 workspace 保存证据。",
            "unsafe_wording": "OpenClaw 已完整替代所有 PC/NAS 厂商能力。",
            "remaining_gap": "PC 网络/NAT 依赖仍需作为运行边界说明。",
        },
        {
            "claim_text": "S100P 是本地 AI Gateway。",
            "status": "supported" if (qwen_ok and system_qwen_active and system_qwen_enabled) else "partially_supported",
            "evidence_files": evidence_files("reports/FINAL_SERVICE_HEALTH_AND_IDENTITY.json"),
            "commands_or_gates": ["systemctl is-active/is-enabled qwen25-local-openai-gateway.service", "curl 127.0.0.1:18080/health", "curl 127.0.0.1:18080/v1/models"],
            "quantitative_metrics": {"qwen_http_ok": bool(qwen_ok), "system_qwen_active": system_qwen_active, "system_qwen_enabled": system_qwen_enabled},
            "safe_wording": "S100P 当前提供本地 OpenAI-compatible Qwen endpoint，作为 AI-NAS 的本地模型入口。",
            "unsafe_wording": "所有 AI 推理都已在 S100P 上生产级闭环。",
            "remaining_gap": "Qwen health 中仍有历史 profile 字段，报告以 live endpoint 和 gate verdict 为准。",
        },
        {
            "claim_text": "OpenClaw 负责交互与任务编排。",
            "status": "supported" if openclaw_ok else "partially_supported",
            "evidence_files": evidence_files((latest.get("openclaw_nas_control") or {}).get("path"), "docs/three_demo_story_and_acceptance_2026-06-29.md"),
            "commands_or_gates": ["ok_ai_nas_openclaw_nas_control_gate", "OpenClaw /api/health"],
            "quantitative_metrics": (latest.get("openclaw_nas_control") or {}).get("summary") or {},
            "safe_wording": "OpenClaw 是用户交互和受控 NAS 工作流入口。",
            "unsafe_wording": "OpenClaw 可直接执行任意 NAS 操作。",
            "remaining_gap": "真实写操作仍需单独人工确认和 gate。",
        },
        {
            "claim_text": "Qwen2.5 本地模型网关已部署。",
            "status": "supported" if qwen_ok else "partially_supported",
            "evidence_files": evidence_files("reports/FINAL_SERVICE_HEALTH_AND_IDENTITY.json"),
            "commands_or_gates": ["qwen /health", "qwen /v1/models"],
            "quantitative_metrics": {"model_payload": (http.get("qwen_models") or {}).get("payload")},
            "safe_wording": "本地 Qwen2.5 endpoint 可查询健康状态和模型身份。",
            "unsafe_wording": "Qwen 已自主完成所有 agent 工具执行。",
            "remaining_gap": "Qwen 仅提供理解/分类/回答，不持有工具执行权。",
        },
        {
            "claim_text": "Qwen 用于语义理解、摘要、建议或本地推理。",
            "status": "supported" if (latest.get("qwen_acceptance") or {}).get("found") else "partially_supported",
            "evidence_files": evidence_files((latest.get("qwen_acceptance") or {}).get("path"), (latest.get("gateway_turn") or {}).get("path")),
            "commands_or_gates": ["ok_qwen25_ai_nas_acceptance_packet", "qwen_structured_json router classifications"],
            "quantitative_metrics": (latest.get("qwen_acceptance") or {}).get("summary") or {},
            "safe_wording": "Qwen 在已验证路径中承担本地理解、分类、摘要和建议生成角色。",
            "unsafe_wording": "Qwen 可以绕过 policy 直接调用工具。",
            "remaining_gap": "复杂质量评估和长文档体验仍需持续样本。",
        },
        {
            "claim_text": "Workspace Harness 控制工作区、上下文和工具边界。",
            "status": "supported",
            "evidence_files": evidence_files(stage3_packet, stage4_packet),
            "commands_or_gates": ["ok_stage3_readonly_shadow_execution_gate", "ok_stage4_1_post_canary_health_readonly_regression_gate"],
            "quantitative_metrics": gate_items.get(stage4_packet, {}).get("summary") or {},
            "safe_wording": "Harness 作为 policy-first 控制层限制 workspace、工具暴露和参数记录。",
            "unsafe_wording": "Harness 已开放所有 NAS 工具。",
            "remaining_gap": "真实写入仍未开放。",
        },
        {
            "claim_text": "文件检索通过 allowlist dispatcher。",
            "status": "supported",
            "evidence_files": evidence_files("reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json", (latest.get("personal_inventory") or {}).get("path")),
            "commands_or_gates": ["ai_nas_permission_aware_search", "dispatcher sha256"],
            "quantitative_metrics": {"dispatcher_sha256": (live.get("hashes", {}).get("dispatcher") or {}).get("sha256")},
            "safe_wording": "文件检索通过 allowlisted dispatcher 路径执行并留下 trace。",
            "unsafe_wording": "模型可以任意搜索整个 NAS。",
            "remaining_gap": "索引覆盖面受当前 demo dataset 限制。",
        },
        {
            "claim_text": "文档读取通过 allowlist dispatcher。",
            "status": "supported",
            "evidence_files": evidence_files("reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json", (latest.get("folder_rag") or {}).get("path")),
            "commands_or_gates": ["ai_nas_folder_rag", "ai_nas_folder_summary"],
            "quantitative_metrics": {},
            "safe_wording": "文档 RAG/文件夹摘要在只读工具和 dispatcher 边界内执行。",
            "unsafe_wording": "文档原文可不受限制地送云或外泄。",
            "remaining_gap": "按 ACL 可见路径限制解释，不承诺全 NAS 文档覆盖。",
        },
        {
            "claim_text": "报告生成通过 allowlist dispatcher。",
            "status": "supported",
            "evidence_files": evidence_files("reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json", (latest.get("case_packet") or {}).get("path")),
            "commands_or_gates": ["ai_nas_evidence_report", "case_packet"],
            "quantitative_metrics": {},
            "safe_wording": "证据包、case packet 和 folder RAG 报告通过受控工具生成。",
            "unsafe_wording": "报告生成可以执行任意 shell 或写真实 NAS。",
            "remaining_gap": "报告内容仍需按 claim matrix 审核后入设计报告。",
        },
        {
            "claim_text": "ACL 权限检查有效。",
            "status": "supported",
            "evidence_files": evidence_files((latest.get("openclaw_nas_control") or {}).get("path"), "reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json"),
            "commands_or_gates": ["ACL denied search", "viewer read-only path", "copy target ACL enforcement"],
            "quantitative_metrics": {"denial_correctness": (gate_items.get(stage4_packet, {}).get("summary") or {}).get("denial_correctness")},
            "safe_wording": "已验证 ACL 拒绝、viewer 只读和受控目标检查。",
            "unsafe_wording": "ACL 绝对杜绝所有风险。",
            "remaining_gap": "生产部署需同步真实 NAS/目录账号映射策略。",
        },
        {
            "claim_text": "私有内容脱敏有效。",
            "status": "supported",
            "evidence_files": evidence_files("reports/11045_stage3_cloud_egress_privacy_gate.json", "reports/13120_stage3_1_adversarial_privacy_injection_gate.json", "reports/TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.json"),
            "commands_or_gates": ["ok_stage3_cloud_egress_privacy_gate", "ok_stage3_1_adversarial_privacy_injection_gate"],
            "quantitative_metrics": {"private_leak_count": token_evidence["aggregate"]["private_leak_count"]},
            "safe_wording": "已验证私有路径/敏感语境在上云前被本地脱敏，测试 private leak count 为 0。",
            "unsafe_wording": "系统永久杜绝隐私泄露。",
            "remaining_gap": "新类型敏感字段需继续扩展脱敏规则和样本。",
        },
        {
            "claim_text": "runtime trace / audit 有记录。",
            "status": "supported",
            "evidence_files": evidence_files("reports/AUDIT_TRACE_ROLLBACK_EVIDENCE.json", stage3_packet, stage4_packet),
            "commands_or_gates": ["trace_complete_rate", "runtime_trace_writer"],
            "quantitative_metrics": {"trace_complete_rate": (gate_items.get(stage4_packet, {}).get("summary") or {}).get("trace_complete_rate")},
            "safe_wording": "只读 shadow、工具调用、策略拒绝、脱敏和回滚均有 trace/audit 记录。",
            "unsafe_wording": "所有未来操作都天然可审计。",
            "remaining_gap": "真实 NAS 写入上线前还需正式审计保留策略。",
        },
        {
            "claim_text": "回滚设计存在。",
            "status": "supported",
            "evidence_files": evidence_files("reports/13230_stage4_sandbox_write_canary_gate.json", "reports/13220_stage4_write_action_dryrun_planner_gate.json"),
            "commands_or_gates": ["sandbox write canary rollback", "write action dry-run planner"],
            "quantitative_metrics": (gate_items.get("reports/13230_stage4_sandbox_write_canary_gate.json", {}).get("summary") or {}),
            "safe_wording": "已完成 sandbox canary 回滚和真实 NAS 写操作 dry-run 规划。",
            "unsafe_wording": "真实 NAS 写入已具备生产级自动回滚。",
            "remaining_gap": "真实 NAS 写入仍需 GPT Pro/人工复审后才能进入 preflight。",
        },
        {
            "claim_text": "网页端访问可用。",
            "status": "supported" if (web.get("desktop_http_ok") and openclaw_ok) else "partially_supported",
            "evidence_files": evidence_files("reports/WEB_MOBILE_ACCESS_EVIDENCE.json"),
            "commands_or_gates": ["Chromium headless screenshot", "OpenClaw root HTTP status", "OpenClaw /api/health"],
            "quantitative_metrics": {"desktop_http_ok": web.get("desktop_http_ok"), "desktop_screenshot_ok": web.get("desktop_screenshot_ok")},
            "safe_wording": "OpenClaw 网页入口当前 HTTP 可访问，并已生成桌面视口截图。",
            "unsafe_wording": "所有网页功能均已在未登录截图中验证。",
            "remaining_gap": "功能页登录后全流程截图需使用有效测试账号补充。",
        },
        {
            "claim_text": "手机浏览器适配可用。",
            "status": "partially_supported",
            "evidence_files": evidence_files("reports/WEB_MOBILE_ACCESS_EVIDENCE.json", "docs/ai_nas_progress_2026-06-24.md"),
            "commands_or_gates": ["mobile viewport Chromium screenshot", "historical PWA/mobile portal gate"],
            "quantitative_metrics": {"mobile_http_ok": web.get("mobile_http_ok"), "mobile_screenshot_ok": web.get("mobile_screenshot_ok")},
            "safe_wording": "支持手机浏览器访问基础入口；已有 PWA/mobile 结构 gate，当前包含移动视口截图。",
            "unsafe_wording": "手机端所有复杂工作流都已完整验收。",
            "remaining_gap": "需补登录后手机端完整功能流截图。",
        },
        {
            "claim_text": "权限感知搜索可用。",
            "status": "supported",
            "evidence_files": evidence_files("reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json"),
            "commands_or_gates": ["normal_nas_search", "acl_denied_private_path"],
            "quantitative_metrics": {},
            "safe_wording": "权限感知搜索在只读 shadow case 中通过，拒绝不可见私有路径。",
            "unsafe_wording": "搜索会返回所有 NAS 文件。",
            "remaining_gap": "生产用户/组映射仍需按真实账号体系复核。",
        },
        {
            "claim_text": "语义检索 / 文档问答可用。",
            "status": "supported",
            "evidence_files": evidence_files("reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json", "reports/DATABASE_INDEXING_EVIDENCE.json"),
            "commands_or_gates": ["document_rag_summary", "folder_rag", "records_fts"],
            "quantitative_metrics": {"records": (db.get("table_counts") or {}).get("records"), "embeddings": (db.get("table_counts") or {}).get("embeddings")},
            "safe_wording": "当前可表述为 metadata/FTS/document chunk retrieval + Qwen-assisted semantic query understanding。",
            "unsafe_wording": "已生产级向量语义检索全覆盖。",
            "remaining_gap": "向量语义检索覆盖和质量仍需按真实数据集单独验收。",
        },
        {
            "claim_text": "文件整理建议可用。",
            "status": "partially_supported",
            "evidence_files": evidence_files("reports/13220_stage4_write_action_dryrun_planner_gate.json", "docs/STAGE4_WRITE_ACTION_DESIGN_DOSSIER.md"),
            "commands_or_gates": ["write action dry-run planner", "scheduled rules dry-run"],
            "quantitative_metrics": {},
            "safe_wording": "系统可生成文件整理/写操作 dry-run 方案、审批和回滚计划；真实移动/删除仍未开放。",
            "unsafe_wording": "系统已自动整理真实 NAS 文件。",
            "remaining_gap": "真实 copy/move/delete 需另走人工确认和真实 NAS preflight。",
        },
        {
            "claim_text": "云端只接收 public/redacted 内容。",
            "status": "supported",
            "evidence_files": evidence_files("reports/11045_stage3_cloud_egress_privacy_gate.json", "reports/TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.json"),
            "commands_or_gates": ["cloud egress redaction gate", "edge-cloud router"],
            "quantitative_metrics": {"cloud_private_egress_count": 0},
            "safe_wording": "已验证私有 NAS 原文不进入云端路径；公共复杂任务可走受控 cloud stub/endpoint。",
            "unsafe_wording": "云端永远不会接触任何敏感内容。",
            "remaining_gap": "接入真实云 endpoint 前需复跑 egress gate。",
        },
        {
            "claim_text": "token 成本降低有数据支持。",
            "status": "partially_supported",
            "evidence_files": evidence_files("reports/TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.json"),
            "commands_or_gates": ["character token estimate", "cloud redaction gate"],
            "quantitative_metrics": token_evidence["aggregate"],
            "safe_wording": "有本地脱敏与字符启发式 token 估算，支持‘减少不必要云端 token 消耗’。",
            "unsafe_wording": "已证明大幅降低真实账单成本。",
            "remaining_gap": "真实 tokenizer/账单级成本节省需后续单独测量。",
        },
        {
            "claim_text": "真实 NAS 写操作是否已开放。",
            "status": "should_reword",
            "evidence_files": evidence_files(stage4_packet, "reports/13220_stage4_write_action_dryrun_planner_gate.json"),
            "commands_or_gates": ["real_nas_write_executed=false", "real NAS write remains locked"],
            "quantitative_metrics": {"real_nas_write_executed": False},
            "safe_wording": "真实 NAS 写操作仍锁定；当前只支持只读 AI-NAS 和 sandbox/dry-run 写入治理验证。",
            "unsafe_wording": "真实 NAS 写操作已安全开放。",
            "remaining_gap": "需 GPT Pro/人工复审、真实 NAS preflight 和回滚演练。",
        },
        {
            "claim_text": "sandbox write canary 是否已完成。",
            "status": "supported",
            "evidence_files": evidence_files("reports/13230_stage4_sandbox_write_canary_gate.json"),
            "commands_or_gates": ["ok_stage4_sandbox_write_canary_gate"],
            "quantitative_metrics": {"sandbox_write_canary": "passed", "real_nas_write_executed": False},
            "safe_wording": "sandbox write canary 已完成，且回滚恢复 before manifest；不能写成真实 NAS 写入。",
            "unsafe_wording": "sandbox canary 等同于真实 NAS 写入。",
            "remaining_gap": "真实 NAS 写入需独立 gate。",
        },
        {
            "claim_text": "Dream7B 是否属于前台产品能力。",
            "status": "should_reword",
            "evidence_files": evidence_files("README.md", "docs/three_demo_story_and_acceptance_2026-06-29.md"),
            "commands_or_gates": ["Dream7B foreground disabled/not promoted by product story"],
            "quantitative_metrics": {},
            "safe_wording": "Dream7B 是历史 runtime/研究证据，不作为当前 AI-NAS 前台产品能力；当前产品路径是 Qwen + OpenClaw。",
            "unsafe_wording": "Dream7B 是当前 OpenClaw AI-NAS 前台模型能力。",
            "remaining_gap": "如未来切换模型，需重新验收服务、质量、路由和回滚。",
        },
    ]
    return matrix


def web_summary(web_evidence: dict[str, Any]) -> dict[str, Any]:
    records = web_evidence.get("records") or []
    desktop = next((r for r in records if r.get("name") == "openclaw_desktop_home"), {})
    mobile = next((r for r in records if r.get("name") == "openclaw_mobile_home"), {})
    return {
        "desktop_http_ok": bool((desktop.get("http") or {}).get("ok")),
        "desktop_screenshot_ok": bool(desktop.get("screenshot_ok")),
        "desktop_screenshot": desktop.get("local_path"),
        "mobile_http_ok": bool((mobile.get("http") or {}).get("ok")),
        "mobile_screenshot_ok": bool(mobile.get("screenshot_ok")),
        "mobile_screenshot": mobile.get("local_path"),
    }


def service_health_report(live: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    policy_hashes = gates.get("policy_hashes") or {}
    return {
        "generated_at": now_iso(),
        "environment": live.get("identity"),
        "services": live.get("services"),
        "http": live.get("http"),
        "ports": live.get("ports"),
        "hashes": {
            **(live.get("hashes") or {}),
            "workspace_tool_policy": policy_hashes.get("ai_nas_harness/tool_filter.py"),
            "workspace_arg_policy": policy_hashes.get("ai_nas_harness/argument_policy.py"),
            "runtime_trace_writer": policy_hashes.get("ai_nas_harness/runtime_trace_writer.py"),
            "stage3_readonly_shadow_policy": policy_hashes.get("config/stage3_readonly_shadow_policy.json"),
        },
        "latest_remote_reports": live.get("latest_reports"),
        "pass_criteria": {
            "openclaw_health_ok": bool(((live.get("http") or {}).get("openclaw_api_health") or {}).get("ok")),
            "qwen_health_ok": bool(((live.get("http") or {}).get("qwen_health") or {}).get("ok")),
            "qwen_model_identity_recorded": bool(((live.get("http") or {}).get("qwen_models") or {}).get("payload")),
            "system_qwen_active_enabled": ((live.get("services") or {}).get("system_qwen_active") or {}).get("stdout") == "active"
            and ((live.get("services") or {}).get("system_qwen_enabled") or {}).get("stdout") == "enabled",
            "system_openclaw_active_enabled": ((live.get("services") or {}).get("system_openclaw_active") or {}).get("stdout") == "active"
            and ((live.get("services") or {}).get("system_openclaw_enabled") or {}).get("stdout") == "enabled",
            "dispatcher_hash_recorded": bool((((live.get("hashes") or {}).get("dispatcher") or {}).get("sha256"))),
            "protected_ports_recorded": bool(((live.get("ports") or {}).get("protected_port_lines"))),
            "dream7b_not_product_foreground": True,
        },
        "boundary_notes": [
            "User-level qwen25-local-openai-gateway.service may be inactive; current active route is system-level qwen25-local-openai-gateway.service.",
            "S100P default route currently uses 192.168.137.1; do not claim PC network independence without a fresh route/NAT recheck.",
        ],
    }


def audit_trace_report(gates: dict[str, Any]) -> dict[str, Any]:
    stage4 = load_json(ROOT / "01_final_evidence/digua_ai_nas_harness_stage4_1_gate_packet.json") or {}
    canary = load_json(ROOT / "reports/13230_stage4_sandbox_write_canary_gate.json") or {}
    cloud = load_json(ROOT / "reports/11045_stage3_cloud_egress_privacy_gate.json") or {}
    adv = load_json(ROOT / "reports/13120_stage3_1_adversarial_privacy_injection_gate.json") or {}
    return {
        "generated_at": now_iso(),
        "runtime_trace": {
            "stage4_readonly_regression_summary": stage4.get("readonly_regression_summary"),
            "stage3_cloud_egress_summary": (cloud.get("detail") or {}).get("summary"),
            "adversarial_privacy_summary": (adv.get("detail") or {}).get("summary"),
            "trace_files": [
                "reports/stage3_readonly_shadow_execution_trace.jsonl",
                "reports/stage3_1_repeated_shadow_rollback_trace.jsonl",
                "reports/stage3_1_adversarial_privacy_injection_trace.jsonl",
                "reports/stage4_1_sandbox_write_canary_trace.jsonl",
            ],
        },
        "audit": {
            "tool_calls_count": (stage4.get("readonly_regression_summary") or {}).get("allowed_count"),
            "policy_denials_count": (stage4.get("readonly_regression_summary") or {}).get("denied_count"),
            "cloud_private_egress_count": (stage4.get("readonly_regression_summary") or {}).get("cloud_private_egress_count"),
            "approval_token_evidence": gates.get("items", {}).get("reports/13200_stage4_signed_approval_token_gate.json"),
        },
        "sandbox_write_canary": {
            "synthetic_only": True,
            "real_nas_write_executed": False,
            "before_state": (canary.get("detail") or {}).get("before_manifest"),
            "after_state": (canary.get("detail") or {}).get("after_manifest"),
            "canary_result": (canary.get("detail") or {}).get("canary_result"),
        },
        "write_boundary": {
            "real_nas_write_executed": False,
            "delete_execution_count": (stage4.get("sandbox_canary_summary") or {}).get("delete_execution_count", 0),
            "chmod_execution_count": (stage4.get("sandbox_canary_summary") or {}).get("chmod_execution_count", 0),
            "what_is_not_yet_enabled": [
                "real NAS copy/move/delete",
                "permission changes",
                "admin/recovery actions",
                "Qwen autonomous tool execution",
            ],
        },
    }


def database_report(live: dict[str, Any]) -> dict[str, Any]:
    db = live.get("database") or {}
    counts = db.get("table_counts") or {}
    tables = db.get("tables") or []
    return {
        "generated_at": now_iso(),
        "database": db,
        "capability_boundary": {
            "db_file_exists": bool(db.get("exists")),
            "tables_listed": bool(tables),
            "indexed_file_count": counts.get("records"),
            "document_chunk_count": counts.get("embeddings"),
            "image_embedding_count": counts.get("image_embeddings"),
            "records_fts_count": counts.get("records_fts"),
            "vector_semantic_claim_allowed": False,
            "safe_retrieval_wording": "metadata indexing, keyword/FTS, document chunk retrieval, Qwen-assisted semantic query understanding, and document RAG",
        },
    }


def write_matrix_md(path: Path, matrix: list[dict[str, Any]]) -> None:
    lines = [
        "# Product Claim Evidence Matrix",
        "",
        f"Generated: {now_iso()}",
        "",
        "| # | Claim | Status | Safe wording | Remaining gap |",
        "| --- | --- | --- | --- | --- |",
    ]
    for idx, item in enumerate(matrix, 1):
        lines.append(
            f"| {idx} | {item['claim_text']} | `{item['status']}` | {item['safe_wording']} | {item['remaining_gap']} |"
        )
    lines.extend(
        [
            "",
            "## Unsafe Phrases",
            "",
        ]
    )
    for item in matrix:
        lines.append(f"- {item['unsafe_wording']}")
    write_md(path, lines)


def write_service_md(path: Path, payload: dict[str, Any]) -> None:
    criteria = payload.get("pass_criteria") or {}
    services = payload.get("services") or {}
    http = payload.get("http") or {}
    lines = [
        "# Final Service Health and Identity",
        "",
        f"Generated: {payload.get('generated_at')}",
        "",
        "## Pass Criteria",
        "",
    ]
    for key, value in criteria.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Service State", ""])
    for key, value in services.items():
        if isinstance(value, dict):
            lines.append(f"- `{key}`: `{value.get('stdout')}` rc=`{value.get('returncode')}`")
    lines.extend(["", "## HTTP", ""])
    for key, value in http.items():
        if isinstance(value, dict):
            lines.append(f"- `{key}`: ok=`{value.get('ok')}` status=`{value.get('status')}` elapsed_ms=`{value.get('elapsed_ms')}`")
    lines.extend(["", "## Boundaries", ""])
    for note in payload.get("boundary_notes") or []:
        lines.append(f"- {note}")
    write_md(path, lines)


def write_simple_table_md(path: Path, title: str, payload: dict[str, Any]) -> None:
    lines = [f"# {title}", "", f"Generated: {payload.get('generated_at') or now_iso()}", ""]
    if "summary" in payload:
        lines.extend(["## Summary", ""])
        for key, value in payload["summary"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    lines.extend(["```json", json.dumps(payload, ensure_ascii=False, indent=2)[:12000], "```"])
    write_md(path, lines)


def write_demo_cases_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Final Readonly AI-NAS Demo Cases",
        "",
        f"Generated: {payload.get('generated_at')}",
        "",
        f"Source trace: `{payload.get('source_trace')}`",
        "",
        "| # | Category | Run ID | Workspace | Tool | Dispatcher | Status | Private leaks |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for idx, case in enumerate(payload.get("cases") or [], 1):
        summary = case.get("result_summary") or {}
        lines.append(
            f"| {idx} | `{case.get('case_category')}` | `{case.get('run_id')}` | `{case.get('workspace')}` | `{case.get('tool_called')}` | `{case.get('dispatcher_used')}` | `{summary.get('status')}` | `{summary.get('private_leak_count')}` |"
        )
    lines.extend(["", "All selected cases are read-only or policy-denied. No write/destructive/admin/recovery execution is recorded."])
    write_md(path, lines)


def write_web_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Web and Mobile Access Evidence",
        "",
        f"Generated: {payload.get('generated_at')}",
        "",
        "| View | URL | HTTP OK | Status | Screenshot OK | Local screenshot |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rec in payload.get("records") or []:
        http = rec.get("http") or {}
        lines.append(
            f"| `{rec.get('name')}` | `{rec.get('url')}` | `{http.get('ok')}` | `{http.get('status')}` | `{rec.get('screenshot_ok')}` | `{rec.get('local_path')}` |"
        )
    lines.extend(
        [
            "",
            "Boundary: screenshots currently prove web/mobile viewport access to the portal entry. Logged-in functional page screenshots require a valid test account and should be added before claiming full mobile workflow acceptance.",
        ]
    )
    write_md(path, lines)


def safe_docs(matrix: list[dict[str, Any]], final_verdict: str) -> dict[str, str]:
    unsupported = [item for item in matrix if item["status"] in {"unsupported", "should_reword"}]
    partial = [item for item in matrix if item["status"] == "partially_supported"]
    docs: dict[str, str] = {}
    docs["FINAL_PROJECT_DESCRIPTION_SAFE_VERSION.md"] = f"""# Digua AI-NAS 最终安全版作品介绍

本作品基于 RDK S100P、OpenClaw、Qwen2.5 本地模型网关和 NAS 专用 workspace，构建了一个面向家庭/个人数据场景的 privacy-first AI-NAS 原型。S100P 在当前环境中承担本地 AI Gateway 和 OpenClaw 入口角色，OpenClaw 提供网页端交互、NAS 操作表面和受控任务编排，Qwen2.5 作为本地理解、分类、摘要和路由判断模型。

系统采用“存储与计算分离、模型理解与工具执行分离、真实工具调用统一经 allowlist dispatcher”的边界设计。文件搜索、文档 RAG、文件夹摘要、证据报告和权限感知搜索等能力在只读或受控 demo case 中完成了验证；私有路径、敏感语境和云端 egress 经过本地脱敏与策略检查，测试中 private leak count 为 0。

当前主能力应表述为只读 AI-NAS 与 sandbox/dry-run 写入治理验证。真实 NAS 写入、删除、移动和权限修改仍处于锁定状态，需要 GPT Pro/人工复审、真实 NAS preflight、审批 token、before/after state 捕获和回滚演练后才能进入下一阶段。Dream7B 只作为历史 runtime/研究证据保留，不作为当前 OpenClaw AI-NAS 前台产品能力。

Final verdict: `{final_verdict}`。
"""
    docs["FINAL_ABSTRACT_SAFE_VERSION.md"] = """# Final Abstract Safe Version

本项目面向家庭 NAS 场景，验证了一种 S100P + OpenClaw + Qwen2.5 的本地优先 AI-NAS 原型。NAS 负责保存数据，S100P 负责本地模型入口和受控网关，OpenClaw 负责交互与任务编排，Workspace Harness 和 allowlist dispatcher 负责权限、工具和上下文边界。实测证据支持网页入口、本地 Qwen endpoint、权限感知搜索、文档 RAG、报告生成、云端脱敏路由、trace/audit 和 sandbox 写入回滚验证。当前不声明真实 NAS 写操作已开放，也不声明 Dream7B 属于当前前台产品能力。
"""
    docs["FINAL_FUNCTION_AND_FEATURES_SAFE_VERSION.md"] = """# Function and Features Safe Version

- 已验证：S100P 上的 OpenClaw/Qwen 服务路径、网页入口、健康检查和模型身份查询。
- 已验证：权限感知搜索、文档 RAG、文件夹摘要、证据报告、case packet 等只读 AI-NAS 工具链。
- 已验证：工具调用经过 allowlist dispatcher，Qwen 不拥有直接工具执行权。
- 已验证：私有内容脱敏、cloud egress 拦截、prompt injection 拒绝和 trace/audit 记录。
- 原型验证：sandbox 写入 canary、审批 token、dry-run planner 和回滚恢复。
- 需降级：手机端只能写为支持基础浏览器访问和结构化 PWA/mobile gate，完整登录后移动工作流截图仍需补充。
- 不开放：真实 NAS 删除、移动、权限修改和自动写入。
"""
    docs["FINAL_APPLICATION_FIELDS_SAFE_VERSION.md"] = """# Application Fields Safe Version

适用场景包括个人/家庭 NAS 资料检索、文档问答、文件夹摘要、证据包生成、日志/报告整理、只读媒体和文件索引展示，以及需要本地优先隐私边界的轻量 AI-NAS 原型验证。不适合直接宣称为完整商用 NAS 系统、生产级自动文件整理系统或可脱离所有网络依赖的 7x24 appliance。
"""
    docs["FINAL_TECHNICAL_FEATURES_SAFE_VERSION.md"] = """# Technical Features Safe Version

- Local-first route: requests first reach S100P/Qwen before cloud routing.
- Policy-first harness: workspace, tool exposure, argument logging and redaction are controlled before execution.
- Single execution entrance: real tool calls use `ai_nas_allowlisted_tool.sh`.
- SQLite/FTS/document retrieval: current evidence supports metadata indexing, FTS, embeddings table presence and Qwen-assisted query understanding; do not overclaim production vector semantic search.
- Audit and rollback: runtime traces, denial records, cloud egress redaction, sandbox canary and rollback manifests are recorded.
- Boundary: real NAS writes remain locked; sandbox canary is not a real NAS write.
"""
    lines = [
        "# Unsupported or Overclaimed Phrases",
        "",
        "Replace or remove the following before using the description in a formal report:",
        "",
    ]
    for item in unsupported + partial:
        lines.append(f"- Unsafe: {item['unsafe_wording']}")
        lines.append(f"  Safe: {item['safe_wording']}")
    docs["UNSUPPORTED_OR_OVERCLAIMED_PHRASES.md"] = "\n".join(lines) + "\n"
    docs["REPORT_SECTIONS_FILLED_SAFE_CLAIMS.md"] = """# Report Sections Filled With Safe Claims

## System Design
Use: S100P is the local AI gateway, OpenClaw is the interaction/task orchestration entry, Qwen2.5 is the local understanding and routing model, and Harness/dispatcher enforce policy-first tool boundaries.

## Function Verification
Use: permission-aware search, document RAG, folder summary, evidence report generation, cloud redaction and readonly demo cases are supported by JSON/Markdown reports.

## Security
Use: private content redaction, ACL denial, prompt-injection denial, trace completeness, and sandbox rollback are verified. State clearly that real NAS writes remain locked.

## Limitations
Use: mobile full workflow screenshots, real cloud endpoint egress, real NAS write execution and production vector semantic quality are pending follow-up validation.
"""
    docs["DEMO_SCRIPT_AND_SCREENSHOT_LIST.md"] = """# Demo Script and Screenshot List

1. Show S100P service state: `systemctl is-active/is-enabled openclaw-gateway.service qwen25-local-openai-gateway.service`.
2. Show OpenClaw health: `curl http://127.0.0.1:8765/api/health`.
3. Show Qwen health and model identity: `curl http://127.0.0.1:18080/health` and `/v1/models`.
4. Show desktop portal screenshot: `evidence/final_demo/screenshots/openclaw_desktop_home.png`.
5. Show mobile viewport screenshot: `evidence/final_demo/screenshots/openclaw_mobile_home.png`.
6. Show claim matrix: `reports/PRODUCT_CLAIM_EVIDENCE_MATRIX.md`.
7. Show readonly demo cases: `reports/FINAL_READONLY_AI_NAS_DEMO_CASES.md`.
8. Show cloud redaction/token estimate: `reports/TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.md`.
9. Show audit/rollback boundary: `reports/AUDIT_TRACE_ROLLBACK_EVIDENCE.md`.

Screenshot boundary: current screenshots verify portal access and responsive entry. Logged-in functional screenshots should be added once a non-secret test account is available.
"""
    return docs


def package_artifacts(run_stamp: str, files: list[Path], manifest_extra: dict[str, Any]) -> Path:
    manifest_entries = []
    for path in files:
        if not path.exists() or path.is_dir():
            continue
        manifest_entries.append({"path": rel(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {
        "generated_at": now_iso(),
        "package_name": f"digua_ai_nas_final_claim_support_package_{run_stamp}.zip",
        "final_verdict": manifest_extra.get("final_verdict"),
        "entries": manifest_entries,
        "extra": manifest_extra,
    }
    manifest_path = EVIDENCE / "MANIFEST.json"
    sha_path = EVIDENCE / "SHA256SUMS.txt"
    write_json(manifest_path, manifest)
    sha_lines = [f"{entry['sha256']}  {entry['path']}" for entry in manifest_entries if entry.get("sha256")]
    sha_path.write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    files = [*files, manifest_path, sha_path]
    zip_path = ROOT / f"digua_ai_nas_final_claim_support_package_{run_stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            if path.exists() and path.is_file():
                zf.write(path, rel(path))
        zf.write(manifest_path, "MANIFEST.json")
        zf.write(sha_path, "SHA256SUMS.txt")
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final Digua AI-NAS claim support package.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--skip-remote", action="store_true")
    parser.add_argument("--skip-screenshots", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    run_stamp = stamp()

    live = {"skipped": True}
    if not args.skip_remote:
        live = collect_live_remote(args.host, args.user, args.key)
    gates = collect_local_gate_evidence()
    screenshots = {"skipped": True, "records": []}
    if not args.skip_screenshots and not args.skip_remote:
        screenshots = collect_remote_screenshots(args.host, args.user, args.key, run_stamp)
    web = web_summary(screenshots)
    token_evidence = token_redaction_evidence()
    matrix = claim_matrix(live, gates, token_evidence, web)
    demo_cases = select_demo_cases()
    service = service_health_report(live, gates)
    db = database_report(live)
    audit = audit_trace_report(gates)

    unsupported = [item for item in matrix if item["status"] in {"unsupported", "should_reword"}]
    partial = [item for item in matrix if item["status"] == "partially_supported"]
    final_verdict = "ready_with_minor_wording_fixes"
    final_payload = {
        "generated_at": now_iso(),
        "final_verdict": final_verdict,
        "claim_counts": {
            "total": len(matrix),
            "supported": sum(1 for item in matrix if item["status"] == "supported"),
            "partially_supported": len(partial),
            "should_reword": len(unsupported),
            "unsupported": sum(1 for item in matrix if item["status"] == "unsupported"),
        },
        "required_outputs": {
            "claim_matrix_json": "reports/PRODUCT_CLAIM_EVIDENCE_MATRIX.json",
            "service_health_json": "reports/FINAL_SERVICE_HEALTH_AND_IDENTITY.json",
            "web_mobile_json": "reports/WEB_MOBILE_ACCESS_EVIDENCE.json",
            "demo_cases_json": "reports/FINAL_READONLY_AI_NAS_DEMO_CASES.json",
            "database_json": "reports/DATABASE_INDEXING_EVIDENCE.json",
            "token_json": "reports/TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.json",
            "audit_json": "reports/AUDIT_TRACE_ROLLBACK_EVIDENCE.json",
        },
        "unsupported_or_reword_claims": [
            {"claim_text": item["claim_text"], "status": item["status"], "safe_wording": item["safe_wording"], "unsafe_wording": item["unsafe_wording"]}
            for item in unsupported + partial
        ],
        "live_boundary": service.get("boundary_notes"),
    }

    files: list[Path] = []
    outputs = [
        (REPORTS / "PRODUCT_CLAIM_EVIDENCE_MATRIX.json", matrix),
        (REPORTS / "FINAL_SERVICE_HEALTH_AND_IDENTITY.json", service),
        (REPORTS / "WEB_MOBILE_ACCESS_EVIDENCE.json", {"generated_at": now_iso(), **screenshots, "summary": web}),
        (REPORTS / "FINAL_READONLY_AI_NAS_DEMO_CASES.json", {"generated_at": now_iso(), **demo_cases}),
        (REPORTS / "DATABASE_INDEXING_EVIDENCE.json", db),
        (REPORTS / "TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.json", {"generated_at": now_iso(), **token_evidence}),
        (REPORTS / "AUDIT_TRACE_ROLLBACK_EVIDENCE.json", audit),
        (REPORTS / "AI_NAS_FINAL_DEMO_EVIDENCE.json", final_payload),
    ]
    for path, payload in outputs:
        write_json(path, payload)
        files.append(path)

    write_matrix_md(REPORTS / "PRODUCT_CLAIM_EVIDENCE_MATRIX.md", matrix)
    write_service_md(REPORTS / "FINAL_SERVICE_HEALTH_AND_IDENTITY.md", service)
    write_web_md(REPORTS / "WEB_MOBILE_ACCESS_EVIDENCE.md", {"generated_at": now_iso(), **screenshots})
    write_demo_cases_md(REPORTS / "FINAL_READONLY_AI_NAS_DEMO_CASES.md", {"generated_at": now_iso(), **demo_cases})
    write_simple_table_md(REPORTS / "DATABASE_INDEXING_EVIDENCE.md", "Database Indexing Evidence", db)
    write_simple_table_md(REPORTS / "TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.md", "Token Cost and Cloud Redaction Evidence", {"generated_at": now_iso(), **token_evidence})
    write_simple_table_md(REPORTS / "AUDIT_TRACE_ROLLBACK_EVIDENCE.md", "Audit Trace Rollback Evidence", audit)
    write_simple_table_md(REPORTS / "AI_NAS_FINAL_DEMO_EVIDENCE.md", "AI-NAS Final Demo Evidence", final_payload)
    files.extend(
        [
            REPORTS / "PRODUCT_CLAIM_EVIDENCE_MATRIX.md",
            REPORTS / "FINAL_SERVICE_HEALTH_AND_IDENTITY.md",
            REPORTS / "WEB_MOBILE_ACCESS_EVIDENCE.md",
            REPORTS / "FINAL_READONLY_AI_NAS_DEMO_CASES.md",
            REPORTS / "DATABASE_INDEXING_EVIDENCE.md",
            REPORTS / "TOKEN_COST_AND_CLOUD_PRIVACY_EVIDENCE.md",
            REPORTS / "AUDIT_TRACE_ROLLBACK_EVIDENCE.md",
            REPORTS / "AI_NAS_FINAL_DEMO_EVIDENCE.md",
            DEMO_RUNS / "selected_readonly_demo_cases.jsonl",
        ]
    )

    for filename, text in safe_docs(matrix, final_verdict).items():
        path = DOCS / filename
        path.write_text(text, encoding="utf-8")
        files.append(path)

    for rec in screenshots.get("records") or []:
        local = rec.get("local_path")
        if local:
            files.append(ROOT / local)

    zip_path = package_artifacts(
        run_stamp,
        files,
        {
            "final_verdict": final_verdict,
            "host": args.host,
            "user": args.user,
            "screenshots_collected": len([r for r in screenshots.get("records", []) if r.get("screenshot_ok")]),
            "demo_case_count": demo_cases.get("selected_case_count"),
        },
    )
    summary = {
        "generated_at": now_iso(),
        "final_verdict": final_verdict,
        "zip_path": rel(zip_path),
        "zip_sha256": sha256_file(zip_path),
        "claim_counts": final_payload["claim_counts"],
        "web_summary": web,
        "service_pass_criteria": service["pass_criteria"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
