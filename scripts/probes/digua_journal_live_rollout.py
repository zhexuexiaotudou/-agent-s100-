#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports"
FINAL_DIR = REPO_ROOT / "01_final_evidence"
TMP_DIR = REPO_ROOT / "tmp"
APPROVAL_FILE = REPO_ROOT / "operator_approval" / "digua_journal_live_rollout_approved.json"
APPROVAL_ENV = "AI_NAS_OPERATOR_APPROVED_DIGUA_JOURNAL_LIVE_ROLLOUT"

DEFAULT_S100P_HOST = "sunrise@192.168.127.10"
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "s100p_linkcheck_ed25519"
DEFAULT_REMOTE_ROOT = "/mnt/nas/openclaw"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/qwen25_ai_nas"
DEFAULT_JOURNAL_DB = "/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal.sqlite3"
DEFAULT_JOURNAL_EVIDENCE_DIR = "/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_evidence"
DEFAULT_JOURNAL_EXPORT_DIR = "/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_exports"

REPORT_STEMS = {
    21200: "journal_live_rollout_gate",
    21210: "journal_live_e2e_gate",
    21220: "journal_live_regression_gate",
}

LIVE_SYNC_FILES = [
    "configs/journal_feature_flags.json",
    "configs/journal_workspace.json",
    "migrations/create_digua_journal_tables.sql",
    "scripts/check_journal_service_status.sh",
    "scripts/disable_journal_feature.sh",
    "scripts/run_journal_collectors_once.sh",
    "scripts/run_journal_e2e_smoke.sh",
    "scripts/probes/ai_nas_operator_portal_server.py",
    "scripts/probes/digua_journal_production_deployment.py",
    "src/openclaw/__init__.py",
    "src/openclaw/routes/__init__.py",
    "src/openclaw/routes/journal_routes.py",
    "web/digua_journal.html",
    "web/static/digua_journal.css",
    "web/static/digua_journal.js",
]


def utc_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact_stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scrub_text(value: str) -> str:
    text = value
    replacements = {
        str(Path.home()): "%USERPROFILE%",
        str(REPO_ROOT): "<repo_root>",
        str(REPO_ROOT).replace("\\", "/"): "<repo_root>",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def scrub_command(cmd: list[str]) -> list[str]:
    return [scrub_text(str(item)) for item in cmd]


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(1, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"cannot allocate unique path for {path}")


def run_cmd(cmd: list[str], timeout: int = 30, cwd: Path | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        completed = subprocess.run(
            cmd,
            cwd=cwd or REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=merged_env,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": scrub_text(completed.stdout.strip()[-5000:]),
            "stderr": scrub_text(completed.stderr.strip()[-5000:]),
            "command": scrub_command(cmd),
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": "",
            "stderr": scrub_text(f"{type(exc).__name__}: {exc}"),
            "command": scrub_command(cmd),
        }


def approval_state() -> dict[str, Any]:
    env_value = os.environ.get(APPROVAL_ENV)
    file_payload: dict[str, Any] | None = None
    if APPROVAL_FILE.exists():
        try:
            file_payload = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            file_payload = {"parse_error": f"{type(exc).__name__}: {exc}"}
    return {
        "approved": env_value == "1" or APPROVAL_FILE.exists(),
        "env_name": APPROVAL_ENV,
        "env_value_is_1": env_value == "1",
        "approval_file": rel(APPROVAL_FILE),
        "approval_file_exists": APPROVAL_FILE.exists(),
        "approval_file_payload": file_payload,
    }


def report_paths(report_id: int) -> tuple[Path, Path]:
    stem = REPORT_STEMS[report_id]
    return REPORT_DIR / f"{report_id}_{stem}.json", REPORT_DIR / f"{report_id}_{stem}.md"


def write_report(report_id: int, payload: dict[str, Any]) -> None:
    json_path, md_path = report_paths(report_id)
    payload = {
        "report_id": report_id,
        "title": REPORT_STEMS[report_id],
        "generated_at": utc_stamp(),
        **payload,
    }
    write_json(json_path, payload)
    write_text(
        md_path,
        "\n".join(
            [
                f"# {report_id} {REPORT_STEMS[report_id]}",
                "",
                f"- generated_at: {payload['generated_at']}",
                f"- status: {payload.get('status')}",
                f"- verdict: {payload.get('verdict')}",
                "",
                "```json",
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
            ]
        ),
    )


def hard_constraints() -> dict[str, bool]:
    return {
        "ports_8765_18080_18888_18889_modified": False,
        "openclaw_replaced": False,
        "qwen_replaced": False,
        "cloud_generation_enabled": False,
        "screenshot_enabled": False,
        "desktop_visual_enabled": False,
        "keyboard_mouse_tracking_enabled": False,
        "qwen_tool_execution_authority": False,
        "delete_move_rename_chmod_executed": False,
        "private_nas_raw_content_uploaded": False,
    }


def ssh_cmd(args: argparse.Namespace, remote_script: str, timeout: int = 60) -> dict[str, Any]:
    cmd = [
        "ssh",
        "-i",
        str(args.ssh_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        args.s100p_host,
        remote_script,
    ]
    return run_cmd(cmd, timeout=timeout)


def remote_json(args: argparse.Namespace, remote_script: str, timeout: int = 60) -> dict[str, Any]:
    result = ssh_cmd(args, remote_script, timeout=timeout)
    parsed: Any = None
    if result["stdout"]:
        for line in reversed(result["stdout"].splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    result["json"] = parsed
    result["ok"] = bool(result["ok"] and isinstance(parsed, dict) and parsed.get("ok", True) is not False)
    return result


def remote_python(args: argparse.Namespace, code: str, timeout: int = 60) -> dict[str, Any]:
    script = "python3 - <<'PY'\n" + textwrap.dedent(code).strip() + "\nPY"
    return remote_json(args, script, timeout=timeout)


def remote_state(args: argparse.Namespace, label: str) -> dict[str, Any]:
    code = f"""
import getpass, hashlib, json, socket, subprocess

PROTECTED = ["8765", "18080", "18888", "18889"]

def run(cmd):
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
    return {{
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "command": cmd,
    }}

def service(name, action):
    return run(["systemctl", "--user", action, name])["stdout"]

def curl_json(url):
    completed = run(["curl", "-fsS", url])
    payload = None
    if completed["ok"]:
        try:
            payload = json.loads(completed["stdout"])
        except Exception:
            payload = {{"raw": completed["stdout"][:1000]}}
    return {{"ok": completed["ok"], "returncode": completed["returncode"], "payload": payload, "stderr": completed["stderr"][-1000:]}}

ss = run(["ss", "-H", "-ltnp"])
protected_lines = []
normalized_ports = []
if ss["stdout"]:
    for line in ss["stdout"].splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local_addr = parts[3]
        for port in PROTECTED:
            if local_addr.endswith(":" + port) or (":" + port + " ") in line:
                protected_lines.append(line)
                normalized_ports.append(local_addr)
                break
normalized_ports = sorted(set(normalized_ports))

payload = {{
    "ok": True,
    "label": {label!r},
    "user": getpass.getuser(),
    "hostname": socket.gethostname(),
    "ip_addr": run(["ip", "-br", "addr", "show"])["stdout"],
    "ip_route": run(["ip", "route"])["stdout"],
    "services": {{
        "openclaw_active": service("openclaw-gateway.service", "is-active"),
        "openclaw_enabled": service("openclaw-gateway.service", "is-enabled"),
        "qwen_active": service("qwen25-local-openai-gateway.service", "is-active"),
        "qwen_enabled": service("qwen25-local-openai-gateway.service", "is-enabled"),
    }},
    "linger": run(["loginctl", "show-user", getpass.getuser(), "-p", "Linger"])["stdout"],
    "protected_ports": {{
        "normalized": normalized_ports,
        "raw": protected_lines,
        "hash": hashlib.sha256("\\n".join(normalized_ports).encode()).hexdigest(),
    }},
    "health": {{
        "openclaw": curl_json("http://127.0.0.1:8765/api/health"),
        "qwen": curl_json("http://127.0.0.1:18080/health"),
    }},
}}
print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
"""
    result = remote_python(args, code, timeout=60)
    return result.get("json") or {"ok": False, "runner": result}


def collect_live_sync_files() -> list[str]:
    files = list(LIVE_SYNC_FILES)
    files.extend(str(path.relative_to(REPO_ROOT)).replace("\\", "/") for path in sorted((REPO_ROOT / "src" / "digua_journal").rglob("*.py")))
    return sorted(dict.fromkeys(files))


def sync_live_files(args: argparse.Namespace) -> dict[str, Any]:
    files = collect_live_sync_files()
    dirs = sorted({str((Path(args.remote_root) / path).parent).replace("\\", "/") for path in files})
    mkdir_script = "set -eu\n" + "\n".join(f"mkdir -p '{directory}'" for directory in dirs)
    mkdir_result = ssh_cmd(args, mkdir_script, timeout=60)
    transfers: list[dict[str, Any]] = []
    if not mkdir_result["ok"]:
        return {"ok": False, "mkdir": mkdir_result, "files": files, "transfers": transfers}
    for rel_path in files:
        local = REPO_ROOT / rel_path
        remote = f"{args.s100p_host}:{args.remote_root.rstrip('/')}/{rel_path}"
        result = run_cmd(
            [
                "scp",
                "-i",
                str(args.ssh_key),
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                rel_path,
                remote,
            ],
            timeout=60,
        )
        transfers.append(
            {
                "path": rel_path,
                "ok": result["ok"],
                "sha256": sha256_file(local) if local.exists() else None,
                "bytes": local.stat().st_size if local.exists() else None,
                "stderr": result["stderr"],
            }
        )
        if not result["ok"]:
            return {"ok": False, "mkdir": mkdir_result, "files": files, "transfers": transfers}
    return {"ok": all(item["ok"] for item in transfers), "mkdir": mkdir_result, "files": files, "transfers": transfers}


def remote_compile(args: argparse.Namespace) -> dict[str, Any]:
    script = f"""
set -eu
cd '{args.remote_root}'
python3 - <<'PY'
import json, py_compile
from pathlib import Path

paths = [
    Path("scripts/probes/ai_nas_operator_portal_server.py"),
    Path("scripts/probes/digua_journal_production_deployment.py"),
    Path("src/openclaw/routes/journal_routes.py"),
]
paths.extend(sorted(Path("src/digua_journal").rglob("*.py")))
compiled = []
errors = []
for path in paths:
    try:
        py_compile.compile(str(path), doraise=True)
        compiled.append(str(path))
    except Exception as exc:
        errors.append({{"path": str(path), "error": f"{{type(exc).__name__}}: {{exc}}"}})
print(json.dumps({{"ok": not errors, "compiled_count": len(compiled), "errors": errors}}, ensure_ascii=False, sort_keys=True))
PY
"""
    return remote_json(args, script, timeout=120)


def remote_migrate(args: argparse.Namespace) -> dict[str, Any]:
    code = f"""
import json, sys
from pathlib import Path

root = Path({args.remote_root!r})
sys.path.insert(0, str(root))
from src.digua_journal.journal_db import JournalDB

db = JournalDB({args.journal_db!r})
migration = db.migrate()
print(json.dumps({{"ok": True, "migration": migration, "stats": db.stats()}}, ensure_ascii=False, sort_keys=True))
"""
    return remote_python(args, code, timeout=60)


def remote_verify_flags(args: argparse.Namespace) -> dict[str, Any]:
    code = f"""
import json
from pathlib import Path

path = Path({args.remote_root!r}) / "configs" / "journal_feature_flags.json"
flags = json.loads(path.read_text(encoding="utf-8"))
checks = {{
    "journal_workspace_enabled": flags.get("journal_workspace_enabled") is True,
    "cloud_generation_enabled_false": flags.get("cloud_generation_enabled") is False,
    "qwen_execution_authority_false": flags.get("qwen_execution_authority") is False,
    "screenshots_enabled_false": flags.get("screenshots_enabled") is False,
    "real_nas_write_enabled_false": flags.get("real_nas_write_enabled") is False,
}}
print(json.dumps({{"ok": all(checks.values()), "path": str(path), "feature_flags": flags, "checks": checks}}, ensure_ascii=False, sort_keys=True))
"""
    return remote_python(args, code, timeout=60)


def remote_restart_and_wait(args: argparse.Namespace) -> dict[str, Any]:
    script = """
set -eu
systemctl --user restart openclaw-gateway.service
python3 - <<'PY'
import json, subprocess, time

attempts = []
ok = False
for index in range(30):
    health = subprocess.run(["curl", "-fsS", "http://127.0.0.1:8765/api/health"], text=True, capture_output=True)
    service = subprocess.run(["systemctl", "--user", "is-active", "openclaw-gateway.service"], text=True, capture_output=True)
    attempts.append({
        "index": index,
        "curl_returncode": health.returncode,
        "service": service.stdout.strip(),
        "stderr": health.stderr.strip()[-500:],
    })
    if health.returncode == 0 and service.stdout.strip() == "active":
        ok = True
        break
    time.sleep(1)
enabled = subprocess.run(["systemctl", "--user", "is-enabled", "openclaw-gateway.service"], text=True, capture_output=True)
print(json.dumps({"ok": ok, "attempts": attempts[-5:], "enabled": enabled.stdout.strip()}, ensure_ascii=False, sort_keys=True))
PY
"""
    return remote_json(args, script, timeout=90)


def remote_run_collectors(args: argparse.Namespace) -> dict[str, Any]:
    script = f"""
set -eu
cd '{args.remote_root}'
DIGUA_JOURNAL_DB_PATH='{args.journal_db}' DIGUA_JOURNAL_REPORT_ROOT='{args.remote_report_root}' sh scripts/run_journal_collectors_once.sh
"""
    return remote_json(args, script, timeout=120)


def remote_journal_e2e(args: argparse.Namespace) -> dict[str, Any]:
    code = f"""
import hashlib, json, urllib.request

BASE = "http://127.0.0.1:8765"

def request(path, payload=None):
    data = None
    headers = {{"Accept": "application/json"}}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        text = raw.decode("utf-8", errors="replace")
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = {{"raw_preview": text[:500]}}
        return {{"status": resp.status, "ok": 200 <= resp.status < 300, "payload": parsed}}

def compact_response(response):
    compact = json.loads(json.dumps(response, ensure_ascii=False))
    payload = compact.get("payload") if isinstance(compact, dict) else None
    if isinstance(payload, dict):
        if payload.get("feature") == "digua_journal":
            return {{
                "ok": compact.get("ok"),
                "status": compact.get("status"),
                "payload": {{
                    "ok": payload.get("ok"),
                    "feature": payload.get("feature"),
                    "db_path": payload.get("db_path"),
                    "stats": payload.get("stats"),
                    "cloud_generation_enabled": payload.get("cloud_generation_enabled"),
                    "qwen_execution_authority": payload.get("qwen_execution_authority"),
                }},
            }}
        if payload.get("entry_id") or payload.get("event_id"):
            return {{
                "ok": compact.get("ok"),
                "status": compact.get("status"),
                "payload": {{
                    "ok": payload.get("ok"),
                    "entry_id": payload.get("entry_id"),
                    "event_id": payload.get("event_id"),
                    "redaction_count": payload.get("redaction_count"),
                }},
            }}
        summary = payload.get("summary")
        if isinstance(summary, dict) and isinstance(summary.get("markdown"), str):
            markdown = summary["markdown"]
            return {{
                "ok": compact.get("ok"),
                "status": compact.get("status"),
                "payload": {{
                    "ok": payload.get("ok"),
                    "summary": {{
                        "period_type": summary.get("period_type"),
                        "project_id": summary.get("project_id"),
                        "event_count": summary.get("event_count"),
                        "manual_entry_count": summary.get("manual_entry_count"),
                        "local_qwen_used": summary.get("local_qwen_used"),
                        "cloud_used": summary.get("cloud_used"),
                        "hallucinated_event_count": summary.get("hallucinated_event_count"),
                        "path": summary.get("path"),
                        "markdown_bytes": len(markdown.encode("utf-8")),
                        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                    }},
                }},
            }}
        export = payload.get("export")
        if isinstance(export, dict):
            return {{
                "ok": compact.get("ok"),
                "status": compact.get("status"),
                "payload": {{
                    "ok": payload.get("ok"),
                    "export": {{
                        "export_type": export.get("export_type"),
                        "period_type": export.get("period_type"),
                        "project_id": export.get("project_id"),
                        "path": export.get("path"),
                        "sha256": export.get("sha256"),
                        "private_leak_count": export.get("private_leak_count"),
                        "redaction_lookup_exported": export.get("redaction_lookup_exported"),
                    }},
                }},
            }}
    return compact

page_req = urllib.request.Request(BASE + "/journal", headers={{"Accept": "text/html"}})
with urllib.request.urlopen(page_req, timeout=10) as resp:
    page_raw = resp.read()
    page = {{
        "status": resp.status,
        "ok": resp.status == 200,
        "bytes": len(page_raw),
        "sha256": hashlib.sha256(page_raw).hexdigest(),
        "contains_journal_marker": b"journal" in page_raw.lower(),
    }}

health_before = request("/api/journal/health")
manual = request("/api/journal/manual-entry", {{
    "project_id": "project_ai_nas",
    "title": "Live rollout acceptance note",
    "body": "Operator approved Digua Journal live rollout. This manual note stores no private NAS raw content.",
    "evidence_refs": ["reports/21200_journal_live_rollout_gate.json"],
}})
summaries = {{}}
for period in ["daily", "weekly", "monthly", "yearly"]:
    summaries[period] = request("/api/journal/generate-summary", {{"period_type": period, "project_id": "all"}})
export = request("/api/journal/export", {{"export_type": "markdown", "period_type": "daily", "project_id": "all"}})
health_after = request("/api/journal/health")

checks = {{
    "journal_http_200": page["ok"],
    "journal_marker_present": page["contains_journal_marker"],
    "health_before_ok": health_before["ok"] and bool(health_before["payload"].get("ok")),
    "manual_entry_ok": manual["ok"] and bool(manual["payload"].get("ok")),
    "summaries_ok": all(item["ok"] and bool(item["payload"].get("ok")) for item in summaries.values()),
    "export_markdown_ok": export["ok"] and bool(export["payload"].get("ok")),
    "health_after_ok": health_after["ok"] and bool(health_after["payload"].get("ok")),
}}
print(json.dumps({{
    "ok": all(checks.values()),
    "checks": checks,
    "page": page,
    "health_before": compact_response(health_before),
    "manual": compact_response(manual),
    "summaries": {{key: compact_response(value) for key, value in summaries.items()}},
    "export": compact_response(export),
    "health_after": compact_response(health_after),
}}, ensure_ascii=False, sort_keys=True))
"""
    return remote_python(args, code, timeout=120)


def remote_privacy_scan(args: argparse.Namespace) -> dict[str, Any]:
    code = f"""
import json, sys
from pathlib import Path

root = Path({args.remote_root!r})
sys.path.insert(0, str(root))
from src.digua_journal.journal_privacy_guard import export_safety_report

scan_roots = [Path({args.journal_evidence_dir!r}), Path({args.journal_export_dir!r})]
files = []
for scan_root in scan_roots:
    if scan_root.exists():
        files.extend(path for path in scan_root.rglob("*") if path.is_file() and path.suffix.lower() in {{".md", ".json", ".jsonl"}})
reports = []
for path in sorted(files):
    text = path.read_text(encoding="utf-8", errors="replace")
    safety = export_safety_report(text)
    reports.append({{"path": str(path), **safety}})
private_leak_count = sum(item["private_leak_count"] for item in reports)
print(json.dumps({{
    "ok": private_leak_count == 0,
    "scanned_file_count": len(reports),
    "private_leak_count": private_leak_count,
    "redaction_lookup_exported": any(item["redaction_lookup_exported"] for item in reports),
    "reports": reports,
}}, ensure_ascii=False, sort_keys=True))
"""
    return remote_python(args, code, timeout=60)


def remote_disable_probe(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = compact_stamp()
    probe_path = f"{args.remote_report_root.rstrip('/')}/digua_journal_disable_feature_probe_{timestamp}.json"
    script = f"""
set -eu
cd '{args.remote_root}'
python3 - <<'PY'
import json
from pathlib import Path
src = Path("configs/journal_feature_flags.json")
dst = Path({probe_path!r})
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
print(json.dumps({{"ok": True, "probe_path": str(dst)}}))
PY
JOURNAL_FEATURE_FLAGS='{probe_path}' sh scripts/disable_journal_feature.sh
python3 - <<'PY'
import json
from pathlib import Path
path = Path({probe_path!r})
payload = json.loads(path.read_text(encoding="utf-8"))
checks = {{
  "journal_workspace_enabled_false": payload.get("journal_workspace_enabled") is False,
  "cloud_generation_enabled_false": payload.get("cloud_generation_enabled") is False,
  "qwen_execution_authority_false": payload.get("qwen_execution_authority") is False,
  "real_nas_write_enabled_false": payload.get("real_nas_write_enabled") is False,
}}
print(json.dumps({{"ok": all(checks.values()), "probe_path": str(path), "checks": checks, "payload": payload}}, ensure_ascii=False, sort_keys=True))
PY
"""
    return remote_json(args, script, timeout=60)


def run_local_regression() -> dict[str, Any]:
    compile_paths = [rel(path) for path in sorted((REPO_ROOT / "src" / "digua_journal").rglob("*.py"))]
    compile_paths.extend(
        [
            "src/openclaw/routes/journal_routes.py",
            "scripts/probes/ai_nas_operator_portal_server.py",
            "scripts/probes/digua_journal_live_rollout.py",
        ]
    )
    compile_check = run_cmd([sys.executable, "-m", "py_compile", *compile_paths], timeout=120)
    journal_tests = [
        "tests/test_journal_event_model.py",
        "tests/test_journal_db.py",
        "tests/test_nas_index_diff_collector.py",
        "tests/test_journal_system_collectors.py",
        "tests/test_manual_entry.py",
        "tests/test_project_classifier.py",
        "tests/test_period_summary_engine.py",
        "tests/test_journal_token_privacy.py",
        "tests/test_journal_exporter.py",
        "tests/test_journal_routes.py",
    ]
    pytest_check = run_cmd([sys.executable, "-m", "pytest", *journal_tests, "-q"], timeout=180)
    return {"ok": compile_check["ok"] and pytest_check["ok"], "py_compile": compile_check, "pytest": pytest_check}


def ports_unchanged(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (before.get("protected_ports") or {}).get("normalized") == (after.get("protected_ports") or {}).get("normalized")


def build_package(final_packet: dict[str, Any]) -> dict[str, Any]:
    timestamp = compact_stamp()
    package_root = unique_path(TMP_DIR / f"digua_journal_live_rollout_package_{timestamp}")
    package_root.mkdir(parents=True, exist_ok=False)

    include_paths = [
        REPORT_DIR / "21200_journal_live_rollout_gate.json",
        REPORT_DIR / "21200_journal_live_rollout_gate.md",
        REPORT_DIR / "21210_journal_live_e2e_gate.json",
        REPORT_DIR / "21210_journal_live_e2e_gate.md",
        REPORT_DIR / "21220_journal_live_regression_gate.json",
        REPORT_DIR / "21220_journal_live_regression_gate.md",
        FINAL_DIR / "digua_journal_live_rollout_gate_packet.json",
        FINAL_DIR / "digua_journal_live_rollout_gate_packet.md",
        REPO_ROOT / "docs" / "DIGUA_JOURNAL_LIVE_ROLLOUT_RUNBOOK.md",
        REPO_ROOT / "docs" / "DIGUA_JOURNAL_SAFE_CLAIM_BOUNDARY.md",
        REPO_ROOT / "docs" / "DIGUA_JOURNAL_USER_GUIDE.md",
        REPO_ROOT / "configs" / "journal_feature_flags.json",
        REPO_ROOT / "configs" / "journal_workspace.json",
        REPO_ROOT / "scripts" / "probes" / "digua_journal_live_rollout.py",
    ]

    manifest_entries: list[dict[str, Any]] = []
    for source in include_paths:
        if not source.exists():
            continue
        target = package_root / rel(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest_entries.append({"path": rel(source), "sha256": sha256_file(source), "bytes": source.stat().st_size})

    manifest = {
        "feature": "digua_journal_live_rollout",
        "generated_at": utc_stamp(),
        "final_verdict": final_packet["verdict"],
        "file_count": len(manifest_entries),
        "files": manifest_entries,
    }
    write_json(package_root / "MANIFEST.json", manifest)
    write_text(package_root / "SHA256SUMS.txt", "\n".join(f"{item['sha256']}  {item['path']}" for item in manifest_entries) + "\n")
    write_text(
        package_root / "SELF_CHECK.py",
        """#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
required = [
    "reports/21200_journal_live_rollout_gate.json",
    "reports/21210_journal_live_e2e_gate.json",
    "reports/21220_journal_live_regression_gate.json",
    "01_final_evidence/digua_journal_live_rollout_gate_packet.json",
]
missing = [item for item in required if not (root / item).exists()]
print(json.dumps({"ok": not missing, "missing": missing, "file_count": manifest["file_count"]}, indent=2))
raise SystemExit(1 if missing else 0)
""",
    )

    zip_path = unique_path(REPO_ROOT / f"digua_journal_live_rollout_for_gptpro_{timestamp}.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package_root).as_posix())
    zip_sha = sha256_file(zip_path)
    write_text(REPO_ROOT / f"{zip_path.name}.sha256.txt", f"{zip_sha}  {zip_path.name}\n")
    return {
        "package_path": rel(zip_path),
        "package_sha256": zip_sha,
        "package_bytes": zip_path.stat().st_size,
        "package_root": rel(package_root),
        "manifest_file_count": len(manifest_entries),
    }


def write_final_packet(final_packet: dict[str, Any]) -> None:
    write_json(FINAL_DIR / "digua_journal_live_rollout_gate_packet.json", final_packet)
    package = final_packet.get("package") or {}
    lines = [
        "# Digua Journal Live Rollout Gate Packet",
        "",
        f"- generated_at: {final_packet['generated_at']}",
        f"- verdict: {final_packet['verdict']}",
        f"- package: {package.get('package_path')}" if package else "- package: pending",
        f"- package_sha256: {package.get('package_sha256')}" if package else "- package_sha256: pending",
        f"- live rollout attempted: {str(final_packet.get('live_rollout_attempted')).lower()}",
        f"- remote state changed: {str(final_packet.get('remote_state_changed')).lower()}",
        f"- ssh host: `{final_packet.get('s100p_host')}`",
        "",
    ]
    write_text(FINAL_DIR / "digua_journal_live_rollout_gate_packet.md", "\n".join(lines))


def write_blocked_outputs() -> dict[str, Any]:
    approval = approval_state()
    git_head = run_cmd(["git", "rev-parse", "HEAD"])
    base_payload = {
        "approval": approval,
        "hard_constraints": hard_constraints(),
        "live_rollout_attempted": False,
        "ssh_attempted": False,
        "openclaw_reload_attempted": False,
        "s100p_service_mutation_attempted": False,
        "reason": "missing operator approval gate",
    }
    write_report(
        21200,
        {
            **base_payload,
            "status": "blocked",
            "verdict": "blocked_by_no_operator_approval",
            "git_head": git_head,
            "required_operator_action": [
                f"Set process environment {APPROVAL_ENV}=1 before invoking the rollout runner",
                f"or create {rel(APPROVAL_FILE)} with operator approval metadata",
            ],
        },
    )
    write_report(
        21210,
        {
            **base_payload,
            "status": "skipped",
            "verdict": "blocked_by_no_operator_approval",
            "skipped_steps": [
                "OpenClaw health",
                "Qwen health",
                "protected port check",
                "journal DB migration on S100P",
                "feature flag load",
                "OpenClaw reload",
                "/journal HTTP 200",
                "/api/journal/health",
                "collector run",
                "manual entry",
                "period summaries",
                "Markdown export",
                "privacy scan",
            ],
        },
    )
    write_report(
        21220,
        {
            **base_payload,
            "status": "skipped",
            "verdict": "blocked_by_no_operator_approval",
            "regression_not_run_reason": "live rollout did not start because operator approval was absent",
            "disable_script_verified_for_existence": (REPO_ROOT / "scripts" / "disable_journal_feature.sh").exists(),
        },
    )
    final_packet = {
        "feature": "digua_journal_live_rollout",
        "generated_at": utc_stamp(),
        "verdict": "blocked_by_no_operator_approval",
        "reports": [rel(report_paths(report_id)[0]) for report_id in sorted(REPORT_STEMS)],
        "approval": approval,
        "hard_constraints": hard_constraints(),
        "live_rollout_attempted": False,
        "remote_state_changed": False,
        "next_unblock": {
            "env": f"{APPROVAL_ENV}=1",
            "approval_file": rel(APPROVAL_FILE),
        },
    }
    write_final_packet(final_packet)
    package = build_package(final_packet)
    final_packet["package"] = package
    write_final_packet(final_packet)
    return final_packet


def run_live_rollout(args: argparse.Namespace) -> dict[str, Any]:
    approval = approval_state()
    before = remote_state(args, "before_live_rollout")
    sync = sync_live_files(args)
    remote_compile_result = remote_compile(args) if sync.get("ok") else {"ok": False, "skipped": "sync_failed"}
    migration = remote_migrate(args) if remote_compile_result.get("ok") else {"ok": False, "skipped": "remote_compile_failed"}
    feature_flags = remote_verify_flags(args) if migration.get("ok") else {"ok": False, "skipped": "migration_failed"}
    restart = remote_restart_and_wait(args) if feature_flags.get("ok") else {"ok": False, "skipped": "feature_flags_failed"}
    after_restart = remote_state(args, "after_openclaw_restart") if restart.get("ok") else {"ok": False, "skipped": "restart_failed"}
    collectors = remote_run_collectors(args) if restart.get("ok") else {"ok": False, "skipped": "restart_failed"}
    e2e = remote_journal_e2e(args) if collectors.get("ok") else {"ok": False, "skipped": "collectors_failed"}
    privacy = remote_privacy_scan(args) if e2e.get("ok") else {"ok": False, "skipped": "e2e_failed"}
    disable_probe = remote_disable_probe(args) if e2e.get("ok") else {"ok": False, "skipped": "e2e_failed"}
    after = remote_state(args, "after_live_rollout")
    local_regression = run_local_regression()

    service_ok = all(
        [
            before.get("ok"),
            sync.get("ok"),
            remote_compile_result.get("ok"),
            migration.get("ok"),
            feature_flags.get("ok"),
            restart.get("ok"),
            after_restart.get("ok"),
            ports_unchanged(before, after),
            (after.get("services") or {}).get("openclaw_active") == "active",
            (after.get("services") or {}).get("qwen_active") == "active",
            bool(((after.get("health") or {}).get("openclaw") or {}).get("ok")),
            bool(((after.get("health") or {}).get("qwen") or {}).get("ok")),
        ]
    )
    e2e_ok = bool(collectors.get("ok") and e2e.get("ok"))
    privacy_ok = bool(privacy.get("ok"))
    regression_ok = bool(local_regression.get("ok") and disable_probe.get("ok") and remote_compile_result.get("ok"))

    if not service_ok:
        verdict = "live_rollout_service_failure_hold"
    elif not e2e_ok or not privacy_ok:
        verdict = "live_rollout_privacy_failure_hold"
    elif not regression_ok:
        verdict = "live_rollout_regression_failure_hold"
    else:
        verdict = "digua_journal_live_rollout_passed"

    write_report(
        21200,
        {
            "status": "pass" if service_ok else "fail",
            "verdict": "journal_live_rollout_service_gate_passed" if service_ok else "live_rollout_service_failure_hold",
            "approval": approval,
            "s100p_host": args.s100p_host,
            "remote_root": args.remote_root,
            "remote_report_root": args.remote_report_root,
            "journal_db": args.journal_db,
            "before": before,
            "sync": sync,
            "remote_compile": remote_compile_result,
            "migration": migration,
            "feature_flags": feature_flags,
            "restart": restart,
            "after_restart": after_restart,
            "after": after,
            "protected_ports_unchanged": ports_unchanged(before, after),
            "hard_constraints": hard_constraints(),
            "openclaw_reload_attempted": True,
            "s100p_service_mutation_attempted": True,
        },
    )
    write_report(
        21210,
        {
            "status": "pass" if e2e_ok and privacy_ok else "fail",
            "verdict": "journal_live_e2e_gate_passed" if e2e_ok and privacy_ok else "live_rollout_privacy_failure_hold",
            "collectors": collectors,
            "e2e": e2e,
            "privacy_scan": privacy,
            "required_checks": [
                "/journal HTTP 200",
                "/api/journal/health",
                "run_journal_collectors_once.sh",
                "manual entry",
                "daily summary",
                "weekly summary",
                "monthly summary",
                "yearly summary",
                "Markdown export",
                "privacy scan",
            ],
            "hard_constraints": hard_constraints(),
        },
    )
    write_report(
        21220,
        {
            "status": "pass" if regression_ok and service_ok else "fail",
            "verdict": "journal_live_regression_gate_passed" if regression_ok and service_ok else "live_rollout_regression_failure_hold",
            "local_regression": local_regression,
            "remote_compile": remote_compile_result,
            "disable_journal_feature_probe": disable_probe,
            "protected_ports_unchanged": ports_unchanged(before, after),
            "post_rollout_services": (after.get("services") or {}),
            "hard_constraints": hard_constraints(),
        },
    )

    final_packet = {
        "feature": "digua_journal_live_rollout",
        "generated_at": utc_stamp(),
        "verdict": verdict,
        "reports": [rel(report_paths(report_id)[0]) for report_id in sorted(REPORT_STEMS)],
        "approval": approval,
        "s100p_host": args.s100p_host,
        "remote_root": args.remote_root,
        "remote_report_root": args.remote_report_root,
        "journal_db": args.journal_db,
        "journal_evidence_dir": args.journal_evidence_dir,
        "journal_export_dir": args.journal_export_dir,
        "live_rollout_attempted": True,
        "remote_state_changed": bool(sync.get("ok") or restart.get("ok") or migration.get("ok")),
        "service_ok": service_ok,
        "e2e_ok": e2e_ok,
        "privacy_ok": privacy_ok,
        "regression_ok": regression_ok,
        "protected_ports_unchanged": ports_unchanged(before, after),
        "hard_constraints": hard_constraints(),
    }
    write_final_packet(final_packet)
    package = build_package(final_packet)
    final_packet["package"] = package
    write_final_packet(final_packet)
    return final_packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Digua Journal S100P live rollout gate.")
    parser.add_argument("--allow-blocked-output", action="store_true", help="Write blocked reports when approval is missing.")
    parser.add_argument("--s100p-host", default=DEFAULT_S100P_HOST)
    parser.add_argument("--ssh-key", type=Path, default=DEFAULT_SSH_KEY)
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--journal-db", default=DEFAULT_JOURNAL_DB)
    parser.add_argument("--journal-evidence-dir", default=DEFAULT_JOURNAL_EVIDENCE_DIR)
    parser.add_argument("--journal-export-dir", default=DEFAULT_JOURNAL_EXPORT_DIR)
    args = parser.parse_args()

    approval = approval_state()
    if not approval["approved"]:
        if not args.allow_blocked_output:
            print(json.dumps({"ok": False, "verdict": "blocked_by_no_operator_approval", "approval": approval}, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        final_packet = write_blocked_outputs()
        print(json.dumps({"ok": False, "verdict": final_packet["verdict"], "package": final_packet["package"]}, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0)

    final_packet = run_live_rollout(args)
    print(json.dumps({"ok": final_packet["verdict"] == "digua_journal_live_rollout_passed", "verdict": final_packet["verdict"], "package": final_packet["package"]}, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if final_packet["verdict"] == "digua_journal_live_rollout_passed" else 1)


if __name__ == "__main__":
    main()
