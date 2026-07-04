#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import threading
import tempfile
import re
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from src.harness.token_budget_integration import TokenBudgetIntegration
except Exception:
    TokenBudgetIntegration = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.harness_status_routes import harness_status_response
    from src.openclaw.routes.journal_routes import journal_route_response
    from src.openclaw.routes.nas_copy_routes import (
        copy_confirm_response,
        copy_dry_run_response,
        copy_execute_response,
        copy_preview_response,
        copy_rollback_response,
    )
except Exception:
    harness_status_response = None  # type: ignore[assignment]
    journal_route_response = None  # type: ignore[assignment]
    copy_preview_response = None  # type: ignore[assignment]
    copy_dry_run_response = None  # type: ignore[assignment]
    copy_confirm_response = None  # type: ignore[assignment]
    copy_execute_response = None  # type: ignore[assignment]
    copy_rollback_response = None  # type: ignore[assignment]

from ai_nas_app_ecosystem import AppEcosystem
from ai_nas_backup import BackupManager
from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    StoragePathError,
    latest_file_operations,
    list_storage_directory,
    log_file_operation,
    normalize_storage_relative_path,
    resolve_storage_path,
    storage_status,
)
from ai_nas_identity import IdentityStore, parse_bearer_token
from ai_nas_media import MediaCenter
from ai_nas_ops import OpsManager
from ai_nas_snapshot import SnapshotStore
try:
    from ai_nas_operator_portal_contract_probe import latest_report, read_json
except Exception:
    def read_json(path: Path) -> dict | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _fallback_report_sort_key(path: Path) -> tuple[float, float, str]:
        payload = read_json(path) or {}
        generated_at = payload.get("generated_at")
        generated_ts = 0.0
        if isinstance(generated_at, str):
            try:
                generated_ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                generated_ts = 0.0
        try:
            mtime_ts = path.stat().st_mtime
        except OSError:
            mtime_ts = 0.0
        return generated_ts, mtime_ts, str(path)

    def latest_report(evidence_roots: list[Path], filename: str) -> dict:
        candidates: list[Path] = []
        for root in evidence_roots:
            if not root.exists():
                continue
            try:
                candidates.extend(path for path in root.rglob(filename) if path.is_file())
            except OSError:
                continue
        if not candidates:
            return {
                "found": False,
                "filename": filename,
                "path": None,
                "verdict": None,
                "generated_at": None,
                "selection_policy": "fallback_generated_at_then_mtime",
                "payload": None,
            }
        selected = max(candidates, key=_fallback_report_sort_key)
        payload = read_json(selected)
        return {
            "found": payload is not None,
            "filename": filename,
            "path": str(selected),
            "verdict": payload.get("verdict") if payload else None,
            "generated_at": payload.get("generated_at") if payload else None,
            "selection_policy": "fallback_generated_at_then_mtime",
            "payload": payload,
        }


TOOL_ID = "ai_nas_operator_portal_server"
REPORT_FILENAMES = {
    "operator_portal_contract": "operator_portal_contract.json",
    "production_readiness_gate": "production_readiness_gate.json",
    "operational_slo_rollup_contract": "operational_slo_rollup_contract.json",
    "objective_traceability_contract": "objective_traceability_contract.json",
    "production_dependency_bundle": "production_dependency_bundle.json",
    "production_blocker_runbook_contract": "production_blocker_runbook_contract.json",
    "dream7b_perf_identity": "dream7b_perf_identity.json",
    "nas_backed_long_soak": "nas_backed_long_soak.json",
    "soak_completion_gate_watcher": "soak_completion_gate_watcher_latest.json",
    "goal_completion_audit": "goal_completion_audit.json",
    "goal_completion_finalizer": "goal_completion_finalizer_latest.json",
}
REMOTE_SYNC_EXTRA_FILENAMES = [
    "model_service_real_recovery_drill.json",
    "index_systemd_daemon_install.json",
    "services.json",
]
OPERATOR_DECISION_DIRNAME = "operator_decisions"


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def compact_timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [report_root]
    tmp_root = Path("tmp")
    if tmp_root.exists():
        roots.append(tmp_root)
    return roots


def report_without_payload(report: dict) -> dict:
    return {key: value for key, value in report.items() if key != "payload"}


def run_checked(cmd: list[str], timeout: int = 5, env: dict[str, str] | None = None) -> dict:
    started = time.perf_counter()
    try:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        completed = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=merged_env, check=False)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout": completed.stdout.strip()[:2000],
            "stderr": completed.stderr.strip()[:2000],
            "command": cmd,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "ok": False,
            "returncode": None,
            "elapsed_ms": elapsed_ms,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "command": cmd,
        }


def http_health(name: str, url: str, timeout: int = 5) -> dict:
    started = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4096).decode("utf-8", errors="replace")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            payload = {}
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:1000]}
            return {
                "name": name,
                "kind": "http",
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "elapsed_ms": elapsed_ms,
                "url": url,
                "payload": payload,
            }
    except urllib.error.URLError as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "name": name,
            "kind": "http",
            "ok": False,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "error": str(exc),
        }


def normalize_health_url(base_or_url: str) -> str:
    text = base_or_url.rstrip("/")
    return text if text.endswith("/health") else f"{text}/health"


def required_check(check: dict, required: bool = True) -> dict:
    check["required"] = required
    return check


def generate_portal(report_root: Path, evidence_roots: list[Path]) -> dict:
    script_path = Path(__file__).with_name("ai_nas_operator_portal_contract_probe.py")
    cmd = [sys.executable, str(script_path), "--report-root", str(report_root)]
    for root in evidence_roots:
        cmd.extend(["--evidence-root", str(root)])
    completed = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
    return {
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def run_remote_evidence_sync(host: str, key: Path | None, remote_report_root: str, local_sync_dir: Path, timeout: int = 60) -> dict:
    started = time.perf_counter()
    local_sync_dir = local_sync_dir.resolve()
    local_sync_dir.mkdir(parents=True, exist_ok=True)
    filenames = sorted(set(REPORT_FILENAMES.values()) | set(REMOTE_SYNC_EXTRA_FILENAMES))
    remote_script = f"""set -eu
out=$(mktemp -d /tmp/ai_nas_portal_latest.XXXXXX)
export AI_NAS_PORTAL_SYNC_OUT="$out"
python3 - <<'PY'
import os
import json, pathlib, shutil, subprocess, time, urllib.request
src=pathlib.Path({remote_report_root!r})
out=pathlib.Path(os.environ['AI_NAS_PORTAL_SYNC_OUT'])
filenames={filenames!r}
def sort_key(p):
    try:
        d=json.load(open(p, encoding='utf-8'))
        ga=d.get('generated_at') or ''
    except Exception:
        ga=''
    return (ga, p.stat().st_mtime, str(p))
manifest=[]
for name in filenames:
    candidates=[p for p in src.rglob(name) if p.is_file()]
    if not candidates:
        continue
    selected=max(candidates, key=sort_key)
    sub=out/name.replace('.json','')
    sub.mkdir(parents=True, exist_ok=True)
    target=sub/name
    shutil.copy2(selected, target)
    manifest.append({{'filename':name,'source':str(selected),'copied':str(target)}})
status=src/'long_soak_jobs/soak_completion_gate_watcher_latest.json'
if status.exists():
    sub=out/'soak_completion_gate_watcher_latest'
    sub.mkdir(parents=True, exist_ok=True)
    target=sub/'soak_completion_gate_watcher_latest.json'
    shutil.copy2(status, target)
    manifest.append({{'filename':'soak_completion_gate_watcher_latest.json','source':str(status),'copied':str(target)}})
svc=src/'operator_portal_server_services_validation2/services.json'
if svc.exists():
    sub=out/'service_status'
    sub.mkdir(parents=True, exist_ok=True)
    target=sub/'services.json'
    shutil.copy2(svc, target)
    manifest.append({{'filename':'services.json','source':str(svc),'copied':str(target)}})
def http_health(name, url):
    started=time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            raw=resp.read().decode('utf-8', errors='replace')
            elapsed_ms=round((time.perf_counter()-started)*1000, 3)
            payload=json.loads(raw) if raw.strip().startswith('{{') else {{}}
            return {{'name':name,'kind':'http','ok':200 <= resp.status < 300,'status':resp.status,'elapsed_ms':elapsed_ms,'url':url,'payload':payload}}
    except Exception as exc:
        return {{'name':name,'kind':'http','ok':False,'status':None,'elapsed_ms':round((time.perf_counter()-started)*1000, 3),'url':url,'error':f'{{type(exc).__name__}}: {{exc}}'}}
def run_checked(name, kind, cmd, env=None):
    started=time.perf_counter()
    merged=os.environ.copy()
    if env:
        merged.update(env)
    try:
        proc=subprocess.run(cmd, text=True, capture_output=True, timeout=8, check=False, env=merged)
        stdout=proc.stdout.strip()
        return {{'name':name,'kind':kind,'ok':proc.returncode == 0,'returncode':proc.returncode,'elapsed_ms':round((time.perf_counter()-started)*1000, 3),'stdout':stdout,'stderr':proc.stderr.strip()[:1000],'command':cmd,'status':stdout or proc.returncode}}
    except Exception as exc:
        return {{'name':name,'kind':kind,'ok':False,'returncode':None,'elapsed_ms':round((time.perf_counter()-started)*1000, 3),'stdout':'','stderr':f'{{type(exc).__name__}}: {{exc}}','command':cmd,'status':'error'}}
user_systemctl_prefix=['sudo','-n','env','XDG_RUNTIME_DIR=/run/user/0'] if pathlib.Path('/run/user/0').exists() else []
checks=[
    http_health('dream7b_openai_gateway','http://127.0.0.1:18888/health'),
    http_health('openclaw_gateway','http://127.0.0.1:18789/health'),
    run_checked('ai_nas_index_daemon','systemd_system',['systemctl','is-active','ai-nas-index-daemon.service']),
    run_checked('dream7b_local_openai_gateway','systemd_user',user_systemctl_prefix+['systemctl','--user','is-active','dream7b-local-openai-gateway.service']),
    run_checked('openclaw_gateway','systemd_user',user_systemctl_prefix+['systemctl','--user','is-active','openclaw-gateway.service']),
]
live_services={{
    'generated_at_epoch': time.time(),
    'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    'ok_count': sum(1 for item in checks if item.get('ok') is True),
    'failed_count': sum(1 for item in checks if item.get('ok') is False),
    'unknown_count': sum(1 for item in checks if item.get('ok') is None),
    'checks': checks,
    'source': 'live_remote_sync_probe',
    'audit': {{'remote_read_only': True, 'service_restart_performed': False, 'delete_performed': False, 'move_performed': False, 'overwrite_performed': False}},
}}
sub=out/'service_status'
sub.mkdir(parents=True, exist_ok=True)
target=sub/'services.json'
target.write_text(json.dumps(live_services, ensure_ascii=False, indent=2)+'\\n', encoding='utf-8')
manifest.append({{'filename':'services.json','source':'live_remote_sync_probe','copied':str(target)}})
(out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\\n', encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=False))
PY
tar_path="${{out}}.tgz"
tar -C "$(dirname "$out")" -czf "$tar_path" "$(basename "$out")"
echo "AI_NAS_PORTAL_TAR=$tar_path"
"""
    ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
    scp_cmd = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
    if key:
        ssh_cmd.extend(["-i", str(key)])
        scp_cmd.extend(["-i", str(key)])
    ssh_cmd.extend([host, "bash", "-s"])
    remote_input = remote_script.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    remote = subprocess.run(ssh_cmd, input=remote_input, capture_output=True, timeout=timeout, check=False)
    remote_stdout = remote.stdout.decode("utf-8", errors="replace")
    remote_stderr = remote.stderr.decode("utf-8", errors="replace")
    tar_path = local_sync_dir.parent / f"{local_sync_dir.name}.tgz"
    scp_result = None
    manifest: list[dict] = []
    if remote.returncode == 0:
        remote_tar_path = ""
        for line in remote_stdout.splitlines():
            if line.startswith("AI_NAS_PORTAL_TAR="):
                remote_tar_path = line.split("=", 1)[1].strip()
        if not remote_tar_path:
            remote_tar_path = "/tmp/ai_nas_portal_latest.tgz"
        scp_cmd.extend([f"{host}:{remote_tar_path}", str(tar_path)])
        scp_result = subprocess.run(scp_cmd, text=True, capture_output=True, timeout=timeout, check=False)
        if scp_result.returncode == 0:
            with tempfile.TemporaryDirectory(prefix="ai_nas_portal_sync_") as tmp:
                tmp_path = Path(tmp)
                with tarfile.open(tar_path, "r:gz") as archive:
                    archive.extractall(tmp_path)
                extracted_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
                extracted = extracted_dirs[0] if extracted_dirs else tmp_path / "ai_nas_portal_latest"
                if extracted.exists():
                    for child in local_sync_dir.iterdir():
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                    for child in extracted.iterdir():
                        shutil.move(str(child), str(local_sync_dir / child.name))
                    manifest_path = local_sync_dir / "manifest.json"
                    if manifest_path.exists():
                        try:
                            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                            if isinstance(payload, list):
                                manifest = payload
                        except Exception:
                            manifest = []
    return {
        "ok": remote.returncode == 0 and scp_result is not None and scp_result.returncode == 0,
        "host": host,
        "remote_report_root": remote_report_root,
        "local_sync_dir": str(local_sync_dir),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "ssh_returncode": remote.returncode,
        "ssh_stdout": remote_stdout.strip()[-4000:],
        "ssh_stderr": remote_stderr.strip()[-4000:],
        "scp_returncode": scp_result.returncode if scp_result else None,
        "scp_stdout": scp_result.stdout.strip()[-1000:] if scp_result else "",
        "scp_stderr": scp_result.stderr.strip()[-1000:] if scp_result else "",
        "manifest_count": len(manifest),
        "manifest": manifest,
        "audit": {
            "remote_read_only": True,
            "local_copy_performed": remote.returncode == 0 and scp_result is not None and scp_result.returncode == 0,
            "nas_delete_move_overwrite_performed": False,
        },
    }


def render_service_status_html(service_status: dict) -> str:
    rows = []
    for item in service_status.get("checks") or []:
        status = item.get("status")
        if status is None:
            status = "ok" if item.get("ok") is True else "failed" if item.get("ok") is False else "unknown"
        detail = item.get("url") or " ".join(str(part) for part in item.get("command") or [])
        if item.get("payload"):
            detail = f"{detail} {json.dumps(item.get('payload'), ensure_ascii=False)[:300]}"
        if item.get("error"):
            detail = f"{detail} {item.get('error')}"
        if item.get("stderr"):
            detail = f"{detail} {item.get('stderr')}"
        rows.append(
            "<tr>"
            f"<td>{html_escape(item.get('name'))}</td>"
            f"<td>{html_escape(item.get('kind'))}</td>"
            f"<td>{html_escape(status)}</td>"
            f"<td>{html_escape(item.get('elapsed_ms'))}</td>"
            f"<td><code>{html_escape(detail)}</code></td>"
            "</tr>"
        )
    return f"""
  <section class="section" data-testid="service-status" id="service-status"><h2>Service Status</h2>
    <table><tbody>
      <tr><th>Source</th><td>{html_escape(service_status.get('source') or 'live_local_probe')}</td><th>Generated</th><td colspan="3">{html_escape(service_status.get('generated_at') or service_status.get('generated_at_epoch'))}</td></tr>
      <tr><th>OK</th><td>{html_escape(service_status.get('ok_count'))}</td><th>Failed</th><td>{html_escape(service_status.get('failed_count'))}</td><th>Unknown</th><td>{html_escape(service_status.get('unknown_count'))}</td></tr>
    </tbody></table>
    <table><thead><tr><th>Service</th><th>Kind</th><th>Status</th><th>ms</th><th>Detail</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
  </section>
"""


def render_operator_decisions_html(decisions: list[dict]) -> str:
    rows = []
    for item in decisions[:10]:
        audit = item.get("audit") or {}
        rows.append(
            "<tr>"
            f"<td>{html_escape(item.get('generated_at'))}</td>"
            f"<td>{html_escape(item.get('manifest_id'))}</td>"
            f"<td>{html_escape(item.get('decision'))}</td>"
            f"<td>{html_escape(item.get('risk_level'))}</td>"
            f"<td>{html_escape(audit.get('execution_performed'))}</td>"
            f"<td><code>{html_escape(item.get('path'))}</code></td>"
            "</tr>"
        )
    empty = "<tr><td colspan=\"6\">No operator decisions recorded in this local portal session.</td></tr>"
    return f"""
  <section class="section" data-testid="operator-decisions" id="operator-decisions"><h2>Operator Decisions</h2>
    <table><thead><tr><th>Time</th><th>Manifest</th><th>Decision</th><th>Risk</th><th>Executed</th><th>Audit record</th></tr></thead><tbody>{''.join(rows) or empty}</tbody></table>
  </section>
"""


def render_goal_progress_html(goal_progress: dict) -> str:
    rows = []
    for key in ["goal_completion", "goal_finalizer", "nas_soak", "operator_portal", "dream7b_interaction"]:
        item = goal_progress.get(key) or {}
        if key == "goal_completion":
            evidence = (
                f"passed={item.get('passed_check_count')}/{item.get('check_count')}; "
                f"blockers={item.get('blocker_count')}; "
                f"verdict={item.get('verdict')}"
            )
            gap = item.get("remaining_gap")
        elif key == "goal_finalizer":
            evidence = (
                f"pid={item.get('finalizer_pid')}; "
                f"watcher_ready={item.get('watcher_ready')}; "
                f"audit_rc={item.get('audit_returncode')}; "
                f"verdict={item.get('verdict')}"
            )
            gap = item.get("remaining_gap")
        elif key == "nas_soak":
            evidence = (
                f"progress={item.get('progress_percent')}%; "
                f"eta={item.get('estimated_completion_at')}; "
                f"gate={item.get('production_gate_verdict')}"
            )
            gap = item.get("next_required_evidence")
        elif key == "operator_portal":
            evidence = (
                f"contract={item.get('contract_verdict')}; "
                f"services={item.get('service_ok_count')} ok/{item.get('service_failed_count')} failed; "
                f"decisions={item.get('operator_decision_count')}"
            )
            gap = item.get("remaining_gap")
        else:
            evidence = (
                f"ttft={item.get('ttft_p50_ms')}ms; "
                f"first_progress={item.get('first_progress_p50_ms')}ms; "
                f"interval={item.get('progress_interval_sec')}s"
            )
            gap = item.get("remaining_gap")
        rows.append(
            "<tr>"
            f"<td>{html_escape(item.get('label') or key)}</td>"
            f"<td>{html_escape(item.get('status'))}</td>"
            f"<td><code>{html_escape(evidence)}</code></td>"
            f"<td>{html_escape(gap)}</td>"
            "</tr>"
        )
    return f"""
  <section class="section" data-testid="goal-progress" id="goal-progress"><h2>Goal Progress</h2>
    <table><thead><tr><th>Workstream</th><th>Status</th><th>Evidence</th><th>Remaining</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
  </section>
"""


def render_live_controls_html() -> str:
    return """
  <section class="section" data-testid="live-controls" id="live-controls"><h2>Live Controls</h2>
    <div class="command-grid">
      <div>
        <button id="refresh-portal" type="button">Refresh Evidence</button>
        <label><input id="auto-refresh-portal" type="checkbox"> Auto</label>
        <input id="refresh-interval-sec" type="number" min="15" max="900" step="15" value="60" aria-label="Refresh interval seconds">
      </div>
      <p id="refresh-status"><code>idle</code></p>
    </div>
    <script>
      let aiNasRefreshTimer = null;
      async function refreshPortalEvidence() {
        const status = document.getElementById('refresh-status');
        status.innerHTML = '<code>refreshing</code>';
        try {
          const response = await fetch('/api/refresh', { method: 'POST' });
          const payload = await response.json();
          const latestResponse = await fetch('/api/latest');
          const latest = await latestResponse.json();
          const soak = latest.soak_watcher_status || {};
          const remote = payload.remote_sync || {};
          status.innerHTML = '<code>' + (payload.ok ? 'refreshed' : 'failed') +
            ' remote=' + (remote.ok === true ? 'ok' : remote.ok === false ? 'failed' : 'n/a') +
            ' progress=' + (soak.progress_percent ?? 'n/a') + '%' +
            ' remaining=' + (soak.remaining_seconds ?? 'n/a') + 's' +
            ' eta=' + (soak.estimated_completion_at ?? 'n/a') +
            ' fresh=' + (soak.latest_soak_fresh_after_min_mtime ?? 'n/a') + '</code>';
          if (payload.ok) setTimeout(() => window.location.reload(), 800);
        } catch (error) {
          status.innerHTML = '<code>failed: ' + String(error).slice(0, 160) + '</code>';
        }
      }
      document.getElementById('refresh-portal').addEventListener('click', refreshPortalEvidence);
      document.getElementById('auto-refresh-portal').addEventListener('change', (event) => {
        if (aiNasRefreshTimer) {
          clearInterval(aiNasRefreshTimer);
          aiNasRefreshTimer = null;
        }
        if (event.target.checked) {
          const input = document.getElementById('refresh-interval-sec');
          const seconds = Math.max(15, Math.min(900, Number(input.value || 60)));
          aiNasRefreshTimer = setInterval(refreshPortalEvidence, seconds * 1000);
          refreshPortalEvidence();
        }
      });
    </script>
  </section>
"""


def html_escape(value: object) -> str:
    import html

    return html.escape("" if value is None else str(value), quote=True)


def inject_runtime_sections(html_text: str, latest_bundle: dict) -> str:
    marker = "</main>"
    service_status = latest_bundle.get("service_status") or {}
    decisions = ((latest_bundle.get("operator_decisions") or {}).get("items") or [])
    goal_progress = latest_bundle.get("goal_progress") or {}
    section = (
        render_goal_progress_html(goal_progress)
        + render_live_controls_html()
        + render_service_status_html(service_status)
        + render_operator_decisions_html(decisions)
    )
    if marker in html_text:
        return html_text.replace(marker, section + "\n</main>", 1)
    return html_text + section


NAS_PORTAL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AI-NAS Web OS</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; background: #f6f7f9; color: #1f2933; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: center; }
    h1 { margin: 0; font-size: 28px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 20px; }
    .tile { background: #fff; border: 1px solid #d9dee6; border-radius: 8px; padding: 14px; min-height: 72px; }
    .muted { color: #607080; font-size: 13px; }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>AI-NAS Web OS</h1>
      <div id="loginScreen" class="muted">loginScreen</div>
    </div>
    <div class="muted">nas_action runtime enabled</div>
  </header>
  <section class="grid" id="entryGrid">
    <div class="tile">File Manager</div>
    <div class="tile">Media Center</div>
    <div class="tile">Photos / Album</div>
    <div class="tile">Documents</div>
    <div class="tile">Backup Tasks</div>
    <div class="tile">Snapshots / Trash</div>
    <div class="tile">User Management</div>
    <div class="tile">System Status</div>
    <div class="tile">App Ecosystem</div>
    <div class="tile">AI Copilot</div>
    <div class="tile">Audit Log</div>
  </section>
  <script>
    function renderNasAction(nas_action) { return nas_action && nas_action.operation ? nas_action.operation : "none"; }
    window.renderNasAction = renderNasAction;
  </script>
</main>
</body>
</html>
"""


class PortalState:
    def __init__(
        self,
        report_root: Path,
        evidence_roots: list[Path],
        refresh_on_start: bool,
        service_status_json: Path | None = None,
        remote_sync_host: str | None = None,
        remote_sync_key: Path | None = None,
        remote_report_root: str = "/mnt/nas/openclaw/reports/ai_nas_mvp",
        remote_sync_dir: Path | None = None,
        personal_root: Path | None = None,
        sqlite_index_path: Path | None = None,
        identity_db_path: Path | None = None,
        snapshot_db_path: Path | None = None,
        backup_db_path: Path | None = None,
        media_db_path: Path | None = None,
        ops_db_path: Path | None = None,
        app_db_path: Path | None = None,
        nas_portal: bool = False,
        storage_max_files: int = 5000,
        official_manager_url: str | None = None,
        openclaw_gateway_url: str | None = None,
        openclaw_model_gateway_url: str | None = None,
        qwen_gateway_url: str | None = None,
        journal_report_root: Path | None = None,
        journal_evidence_dir: Path | None = None,
        journal_export_dir: Path | None = None,
    ) -> None:
        self.report_root = report_root
        self.evidence_roots = evidence_roots
        self.service_status_json = service_status_json
        self.remote_sync_host = remote_sync_host
        self.remote_sync_key = remote_sync_key
        self.remote_report_root = remote_report_root
        self.remote_sync_dir = remote_sync_dir
        self.last_remote_sync_result: dict | None = None
        self.refresh_lock = threading.Lock()
        self.refresh_result: dict | None = None
        self.personal_root = personal_root
        self.sqlite_index_path = sqlite_index_path
        self.identity_db_path = identity_db_path
        self.snapshot_db_path = snapshot_db_path
        self.backup_db_path = backup_db_path
        self.media_db_path = media_db_path
        self.ops_db_path = ops_db_path
        self.app_db_path = app_db_path
        self.nas_portal = nas_portal
        self.storage_max_files = storage_max_files
        self.official_manager_url = official_manager_url
        self.openclaw_gateway_url = openclaw_gateway_url
        self.openclaw_model_gateway_url = openclaw_model_gateway_url
        self.qwen_gateway_url = qwen_gateway_url
        self.journal_report_root = journal_report_root or report_root
        self.journal_evidence_dir = journal_evidence_dir or (report_root / "digua_journal_evidence")
        self.journal_export_dir = journal_export_dir or (report_root / "digua_journal_exports")
        self.identity_store: IdentityStore | None = None
        self.snapshot_store: SnapshotStore | None = None
        self.backup_manager: BackupManager | None = None
        self.media_center: MediaCenter | None = None
        self.ops_manager: OpsManager | None = None
        self.app_ecosystem: AppEcosystem | None = None
        if self.personal_root:
            self.personal_root.mkdir(parents=True, exist_ok=True)
            self.sqlite_index_path = self.sqlite_index_path or (self.report_root / "personal_inventory.sqlite3")
            self.identity_db_path = self.identity_db_path or (self.report_root / "identity.sqlite3")
            self.snapshot_db_path = self.snapshot_db_path or (self.report_root / "snapshot.sqlite3")
            self.backup_db_path = self.backup_db_path or (self.report_root / "backup.sqlite3")
            self.media_db_path = self.media_db_path or (self.report_root / "media.sqlite3")
            self.ops_db_path = self.ops_db_path or (self.report_root / "ops.sqlite3")
            self.app_db_path = self.app_db_path or (self.report_root / "apps.sqlite3")
            self.identity_store = IdentityStore(self.identity_db_path)
            self.snapshot_store = SnapshotStore(self.personal_root, self.snapshot_db_path)
            self.backup_manager = BackupManager(self.backup_db_path)
            self.media_center = MediaCenter(self.media_db_path)
            self.ops_manager = OpsManager(self.ops_db_path)
            self.app_ecosystem = AppEcosystem(self.app_db_path)
        if refresh_on_start:
            self.refresh_result = self.refresh()

    def product_enabled(self) -> bool:
        return self.personal_root is not None and self.identity_store is not None

    def user_count(self) -> int:
        if not self.identity_store:
            return 0
        return len(self.identity_store.list_users())

    def user_from_token(self, authorization_header: str | None) -> dict | None:
        if not self.identity_store:
            return None
        token = parse_bearer_token(authorization_header)
        if not token:
            return None
        return self.identity_store.validate_token(token)

    def require_user(self, authorization_header: str | None) -> tuple[int | None, dict | None, dict | None]:
        user = self.user_from_token(authorization_header)
        if not user:
            return HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "auth_required"}, None
        return None, None, user

    def require_admin(self, authorization_header: str | None) -> tuple[int | None, dict | None, dict | None]:
        status, error, user = self.require_user(authorization_header)
        if status:
            return status, error, None
        if not user or user.get("role") != "admin":
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "admin_required"}, user
        return None, None, user

    def can_read(self, user: dict, relative_path: str) -> bool:
        if not self.identity_store:
            return False
        return self.identity_store.check_acl(str(user.get("username") or ""), relative_path, "read")

    def can_write(self, user: dict, relative_path: str) -> bool:
        if not self.identity_store:
            return False
        return self.identity_store.check_acl(str(user.get("username") or ""), relative_path, "write")

    def storage_status_payload(self) -> dict:
        if not self.personal_root:
            return {"ok": False, "error": "personal_root_not_configured"}
        payload = storage_status(self.personal_root, self.sqlite_index_path)
        return {"ok": True, **payload}

    def storage_list_payload(self, relative_path: str = "", user: dict | None = None) -> tuple[int, dict]:
        if not self.personal_root:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "personal_root_not_configured"}
        rel = normalize_storage_relative_path(relative_path)
        if user and not self.can_read(user, rel):
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "read", "path": rel}
        try:
            payload = list_storage_directory(self.personal_root, rel)
            return HTTPStatus.OK, {"ok": True, **payload}
        except (StoragePathError, FileNotFoundError, NotADirectoryError) as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}

    def record_operation(self, action: str, source: str | None, target: str | None, status: str, detail: str | None = None) -> None:
        if not self.sqlite_index_path:
            return
        try:
            log_file_operation(self.sqlite_index_path, action, source, target, status, detail)
        except Exception:
            return

    def storage_rename(self, relative_path: str, new_name: str, user: dict) -> tuple[int, dict]:
        try:
            source_rel = normalize_storage_relative_path(relative_path)
        except StoragePathError:
            source_rel = ""
        self.record_operation("rename", source_rel, None, "disabled_by_harness_default_service", str(user.get("username")))
        return HTTPStatus.FORBIDDEN, {
            "ok": False,
            "error": "rename_disabled_by_harness_default_service",
            "qwen_execution_authority": False,
            "allowed_write_actions": ["copy"],
            "source_path_hash": hashlib.sha256(source_rel.encode("utf-8", errors="replace")).hexdigest() if source_rel else None,
        }

    def storage_copy(self, source_relative_path: str, target_relative_path: str, user: dict) -> tuple[int, dict]:
        try:
            source_rel = normalize_storage_relative_path(source_relative_path)
            target_rel = normalize_storage_relative_path(target_relative_path)
        except StoragePathError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
        self.record_operation("copy", source_rel, target_rel, "harness_route_required", str(user.get("username")))
        return HTTPStatus.ACCEPTED, {
            "ok": True,
            "nas_action": {
                "operation": "copy",
                "status": "harness_route_required",
                "routes": [
                    "/api/nas/copy/preview",
                    "/api/nas/copy/dry-run",
                    "/api/nas/copy/confirm",
                    "/api/nas/copy/execute",
                    "/api/nas/copy/rollback",
                ],
                "source_path_hash": hashlib.sha256(source_rel.encode("utf-8", errors="replace")).hexdigest(),
                "target_path_hash": hashlib.sha256(target_rel.encode("utf-8", errors="replace")).hexdigest(),
                "qwen_execution_authority": False,
                "dispatcher_required": True,
                "direct_copy_performed": False,
            },
        }

    def copilot_chat(self, message: str, user: dict) -> tuple[int, dict]:
        quoted = re.findall(r'"([^"]+)"', message or "")
        if len(quoted) >= 2:
            source, target = quoted[0], quoted[1]
            if "/" not in target and "\\" not in target:
                try:
                    source_rel = normalize_storage_relative_path(source)
                    parent = str(Path(source_rel).parent).replace("\\", "/")
                    target = target if parent in {"", "."} else f"{parent}/{target}"
                except StoragePathError:
                    pass
            if "renamed" in target.lower():
                status, payload = self.storage_rename(source, Path(target).name, user)
                return status, payload
            status, payload = self.storage_copy(source, target, user)
            return status, payload
        if quoted:
            rel = quoted[0]
            try:
                path = resolve_storage_path(self.personal_root, rel) if self.personal_root else Path(rel)
            except StoragePathError as exc:
                return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
            if path.is_dir():
                status, payload = self.storage_list_payload(rel, user)
                if status == HTTPStatus.OK:
                    payload["nas_action"] = {"operation": "list", "status": "completed", "entries": payload.get("entries") or []}
                return status, payload
            return HTTPStatus.OK, {"ok": True, "nas_action": {"operation": "delete", "status": "confirmation_required", "path": normalize_storage_relative_path(rel)}}
        return HTTPStatus.OK, {"ok": True, "nas_action": {"operation": "none", "status": "no_action"}}

    def audit_summary_payload(self) -> dict:
        operations = latest_file_operations(self.sqlite_index_path, limit=50) if self.sqlite_index_path else []
        return {"ok": True, "operations": operations}

    def refresh(self) -> dict:
        with self.refresh_lock:
            if self.remote_sync_host and self.remote_sync_dir:
                self.last_remote_sync_result = run_remote_evidence_sync(
                    self.remote_sync_host,
                    self.remote_sync_key,
                    self.remote_report_root,
                    self.remote_sync_dir,
                )
            self.refresh_result = generate_portal(self.report_root, self.evidence_roots)
            return self.refresh_result

    def latest(self, filename: str) -> dict:
        return latest_report(self.evidence_roots, filename)

    def portal_contract(self) -> dict:
        return self.latest("operator_portal_contract.json")

    def portal_payload(self) -> dict:
        return self.portal_contract().get("payload") or {}

    def portal_html_path(self) -> Path | None:
        path_value = self.portal_payload().get("portal_html")
        return Path(path_value) if path_value else None

    def portal_report_path(self) -> Path | None:
        path_value = self.portal_payload().get("portal_report_json")
        return Path(path_value) if path_value else None

    def portal_report_payload(self) -> dict:
        report_path = self.portal_report_path()
        if not report_path:
            return {}
        payload = read_json(report_path)
        return payload if isinstance(payload, dict) else {}

    def operator_decision_dir(self) -> Path:
        path = self.report_root / OPERATOR_DECISION_DIRNAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def latest_operator_decisions(self, limit: int = 20) -> list[dict]:
        decision_dir = self.report_root / OPERATOR_DECISION_DIRNAME
        if not decision_dir.exists():
            return []
        decisions: list[dict] = []
        for path in sorted(decision_dir.glob("operator_decision_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            payload = read_json(path)
            if isinstance(payload, dict):
                decisions.append({"path": str(path), **payload})
        return decisions

    def record_operator_decision(self, request_payload: dict) -> tuple[int, dict]:
        portal_report = self.portal_report_payload()
        inbox_rows = portal_report.get("approval_inbox") or []
        manifest = portal_report.get("approval_manifest") or {}
        manifest_id = str(request_payload.get("manifest_id") or "").strip()
        decision = str(request_payload.get("decision") or "").strip()
        phrase = str(request_payload.get("phrase") or "").strip()
        allowed_decisions = {
            "approve": "APPROVE",
            "rollback_draft": "ROLLBACK",
            "reject": "REJECT",
            "needs_review": "NEEDS_REVIEW",
        }
        if decision not in allowed_decisions:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "unsupported_decision", "allowed_decisions": sorted(allowed_decisions)}
        row = next((item for item in inbox_rows if str(item.get("manifest_id")) == manifest_id), None)
        if not row:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "manifest_not_in_current_portal_report", "manifest_id": manifest_id}
        expected_phrase = row.get("approval_phrase") if decision == "approve" else f"{allowed_decisions[decision]} {manifest_id}"
        if phrase != expected_phrase:
            return HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "phrase_mismatch",
                "manifest_id": manifest_id,
                "decision": decision,
                "expected_phrase": expected_phrase,
            }
        decision_dir = self.operator_decision_dir()
        record = {
            "generated_at": iso_timestamp(),
            "tool_id": TOOL_ID,
            "decision_id": f"opd-{int(time.time() * 1000)}",
            "decision": decision,
            "manifest_id": manifest_id,
            "phrase": phrase,
            "manifest_path": row.get("path"),
            "manifest_sha256": manifest.get("manifest_sha256") if manifest.get("manifest_id") == manifest_id else None,
            "approval_status": row.get("status"),
            "risk_level": row.get("risk_level"),
            "action_count": row.get("action_count"),
            "portal_report_json": str(self.portal_report_path()) if self.portal_report_path() else None,
            "decision_effect": "local_operator_decision_record_only",
            "next_step": {
                "approve": "run bounded execution tool with exact manifest path and phrase after source hashes are rechecked",
                "rollback_draft": "prepare rollback manifest only after a previous bounded execution manifest exists",
                "reject": "leave proposed actions unexecuted",
                "needs_review": "repair or re-review manifest evidence before any execution",
            }[decision],
            "audit": {
                "remote_read_only_sync": bool(self.last_remote_sync_result),
                "source_files_modified": False,
                "execution_performed": False,
                "rollback_performed": False,
                "delete_performed": False,
                "move_performed": False,
                "overwrite_performed": False,
                "copy_performed": False,
                "writes": "local operator decision JSON/JSONL audit record only",
            },
        }
        json_path = decision_dir / f"operator_decision_{compact_timestamp()}_{record['decision_id']}.json"
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with (decision_dir / "operator_decisions.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"path": str(json_path), **record}, ensure_ascii=False) + "\n")
        return HTTPStatus.OK, {"ok": True, "operator_decision": {"path": str(json_path), **record}}

    def latest_bundle(self) -> dict:
        reports = {key: report_without_payload(self.latest(filename)) for key, filename in REPORT_FILENAMES.items()}
        portal_payload = self.portal_payload()
        service_status = self.service_status()
        soak_watcher_payload = self.latest("soak_completion_gate_watcher_latest.json").get("payload") or {}
        latest_soak = soak_watcher_payload.get("latest_soak") or {}
        soak_process = soak_watcher_payload.get("soak_process") or ((soak_watcher_payload.get("summary") or {}).get("final_soak_process") or {})
        operator_decisions = self.latest_operator_decisions(limit=10)
        dream_report = self.latest("dream7b_perf_identity.json")
        dream_payload = dream_report.get("payload") or {}
        dream_summary = dream_payload.get("summary") or {}
        first_progress = dream_summary.get("first_progress_ms") or {}
        ttft = dream_summary.get("ttft_ms") or {}
        first_content = dream_summary.get("first_content_ms") or {}
        progress_interval = dream_summary.get("progress_interval_sec") or {}
        finalizer_report = self.latest("goal_completion_finalizer_latest.json")
        finalizer_payload = finalizer_report.get("payload") or {}
        finalizer_summary = finalizer_payload.get("summary") or {}
        goal_audit_report = self.latest("goal_completion_audit.json")
        goal_audit_payload = goal_audit_report.get("payload") or {}
        goal_audit_summary = goal_audit_payload.get("summary") or {}
        goal_audit_blockers = goal_audit_summary.get("blockers") or []
        dream_health_interval = None
        for item in service_status.get("checks") or []:
            if item.get("name") == "dream7b_openai_gateway":
                dream_health_interval = (item.get("payload") or {}).get("progress_interval_sec")
                break
        soak_status = {
            "status": soak_watcher_payload.get("status") or soak_watcher_payload.get("verdict"),
            "pid": soak_watcher_payload.get("pid"),
            "pid_running": soak_watcher_payload.get("pid_running"),
            "elapsed_seconds": soak_process.get("elapsed_seconds"),
            "target_seconds": soak_process.get("target_seconds"),
            "remaining_seconds": soak_process.get("remaining_seconds"),
            "estimated_completion_epoch": soak_process.get("estimated_completion_epoch"),
            "estimated_completion_at": soak_process.get("estimated_completion_at"),
            "progress_percent": soak_process.get("progress_percent"),
            "watcher_started_at": soak_watcher_payload.get("watcher_started_at"),
            "min_soak_report_mtime_epoch": soak_watcher_payload.get("min_soak_report_mtime_epoch"),
            "latest_soak_report": soak_watcher_payload.get("latest_soak_report")
            or latest_soak.get("path"),
            "latest_soak_meets_precheck": soak_watcher_payload.get("latest_soak_meets_precheck")
            if "latest_soak_meets_precheck" in soak_watcher_payload
            else latest_soak.get("meets_precheck"),
            "latest_soak_fresh_after_min_mtime": latest_soak.get("fresh_after_min_mtime"),
            "latest_soak_precheck_without_freshness": latest_soak.get("precheck_without_freshness"),
            "latest_soak_mtime_epoch": latest_soak.get("path_mtime_epoch"),
            "gate_report": soak_watcher_payload.get("gate_report") or ((soak_watcher_payload.get("summary") or {}).get("latest_gate_report")),
            "runbook_report": soak_watcher_payload.get("runbook_report") or ((soak_watcher_payload.get("summary") or {}).get("latest_runbook_report")),
        }
        soak_gate_verified = (
            soak_status.get("latest_soak_meets_precheck") is True
            and bool(soak_status.get("gate_report"))
            and bool(soak_status.get("runbook_report"))
        )
        if soak_status.get("pid_running"):
            nas_progress_status = "waiting_for_6h_soak"
            nas_next_evidence = "fresh 21600-second NAS-backed soak report, then watcher final gate/runbook"
        elif soak_gate_verified:
            nas_progress_status = "final_gate_verified"
            nas_next_evidence = "none"
        else:
            nas_progress_status = "ready_for_final_gate"
            nas_next_evidence = "watcher final gate/runbook"
        finalizer_complete = (finalizer_payload.get("verdict") or finalizer_report.get("verdict")) == "ok_ai_nas_goal_completion_finalizer"
        goal_progress = {
            "goal_completion": {
                "label": "Full goal completion audit",
                "status": "complete_ready" if goal_audit_report.get("verdict") == "ok_ai_nas_goal_completion_audit" else "waiting_on_evidence",
                "verdict": goal_audit_report.get("verdict"),
                "check_count": goal_audit_summary.get("check_count"),
                "passed_check_count": goal_audit_summary.get("passed_check_count"),
                "blocker_count": goal_audit_summary.get("blocker_count"),
                "blockers": goal_audit_blockers,
                "remaining_gap": "; ".join(goal_audit_blockers[:3]) if goal_audit_blockers else "none",
            },
            "goal_finalizer": {
                "label": "Post-soak finalizer",
                "status": finalizer_payload.get("status") or ("missing" if not finalizer_report.get("found") else finalizer_report.get("verdict")),
                "verdict": finalizer_payload.get("verdict") or finalizer_report.get("verdict"),
                "finalizer_pid": finalizer_payload.get("finalizer_pid") or finalizer_summary.get("finalizer_pid"),
                "watcher_ready": finalizer_payload.get("watcher_ready") if "watcher_ready" in finalizer_payload else finalizer_summary.get("watcher_ready"),
                "watcher_verdict": finalizer_payload.get("watcher_verdict"),
                "audit_returncode": finalizer_summary.get("audit_returncode"),
                "latest_goal_audit_verdict": finalizer_summary.get("latest_goal_audit_verdict"),
                "latest_goal_audit_report": finalizer_summary.get("latest_goal_audit_report"),
                "remaining_gap": "none" if finalizer_complete else "waiting for watcher final gate/runbook, then strict goal audit",
            },
            "nas_soak": {
                "label": "Controlled NAS Personal soak",
                "status": nas_progress_status,
                "progress_percent": soak_status.get("progress_percent"),
                "estimated_completion_at": soak_status.get("estimated_completion_at"),
                "latest_soak_meets_precheck": soak_status.get("latest_soak_meets_precheck"),
                "production_gate_verdict": reports.get("production_readiness_gate", {}).get("verdict"),
                "next_required_evidence": nas_next_evidence,
            },
            "operator_portal": {
                "label": "Operator Portal demo surface",
                "status": "demo_ready" if reports.get("operator_portal_contract", {}).get("verdict") == "ok_ai_nas_operator_portal_contract" and int(service_status.get("failed_count") or 0) == 0 else "needs_attention",
                "contract_verdict": reports.get("operator_portal_contract", {}).get("verdict"),
                "service_ok_count": service_status.get("ok_count"),
                "service_failed_count": service_status.get("failed_count"),
                "service_source": service_status.get("source") or "live_local_probe",
                "operator_decision_count": len(operator_decisions),
                "latest_decision": (operator_decisions[0] if operator_decisions else {}).get("decision"),
                "remaining_gap": "none",
            },
            "dream7b_interaction": {
                "label": "Dream7B interaction latency",
                "status": "interactive_stream_feedback_ready" if dream_report.get("verdict") == "ok_dream7b_perf_identity" and (first_progress.get("p50_ms") or 999999) <= 500 else "needs_attention",
                "verdict": dream_report.get("verdict"),
                "ttft_p50_ms": ttft.get("p50_ms"),
                "first_progress_p50_ms": first_progress.get("p50_ms"),
                "first_content_p50_ms": first_content.get("p50_ms"),
                "progress_interval_sec": progress_interval.get("p50") if progress_interval else dream_health_interval,
                "health_progress_interval_sec": dream_health_interval,
                "remaining_gap": "backend final content latency still needs model/runtime work",
            },
        }
        return {
            "tool_id": TOOL_ID,
            "report_root": str(self.report_root),
            "evidence_roots": [str(root) for root in self.evidence_roots],
            "portal_html": str(self.portal_html_path()) if self.portal_html_path() else None,
            "portal_report_json": str(self.portal_report_path()) if self.portal_report_path() else None,
            "portal_summary": portal_payload.get("summary") or {},
            "reports": reports,
            "service_status": service_status,
            "soak_watcher_status": soak_status,
            "goal_progress": goal_progress,
            "remote_sync": self.last_remote_sync_result,
            "refresh_on_start": self.refresh_result,
            "operator_decisions": {
                "count": len(operator_decisions),
                "latest": operator_decisions[0] if operator_decisions else None,
                "items": operator_decisions,
            },
            "audit": {
                "server_executes_actions": bool(self.remote_sync_host),
                "delete_performed": False,
                "move_performed": False,
                "overwrite_performed": False,
                "copy_performed": bool(self.last_remote_sync_result and self.last_remote_sync_result.get("ok")),
                "writes": "optional bounded operator_portal_contract report refresh plus optional read-only remote evidence sync",
            },
        }

    def service_status(self) -> dict:
        service_status_json = self.service_status_json
        if service_status_json is None and self.remote_sync_dir:
            candidate = self.remote_sync_dir / "service_status" / "services.json"
            if candidate.exists():
                service_status_json = candidate
        if service_status_json:
            payload = read_json(service_status_json)
            if isinstance(payload, dict):
                payload.setdefault("source", "service_status_json")
                payload.setdefault("source_path", str(service_status_json))
                return payload
        checks = [
            required_check(http_health("qwen_gateway", normalize_health_url(self.qwen_gateway_url or "http://127.0.0.1:18080"))),
        ]
        if self.openclaw_model_gateway_url and self.openclaw_model_gateway_url != self.qwen_gateway_url:
            checks.append(required_check(http_health("openclaw_model_gateway", normalize_health_url(self.openclaw_model_gateway_url))))
        if self.openclaw_gateway_url:
            checks.append(required_check(http_health("openclaw_gateway", normalize_health_url(self.openclaw_gateway_url))))
        else:
            checks.append(required_check(http_health("legacy_openclaw_gateway", "http://127.0.0.1:18789/health"), required=False))
        checks.append(required_check(http_health("legacy_dream7b_openai_gateway", "http://127.0.0.1:18888/health"), required=False))
        is_linux = platform.system().lower() == "linux"
        if is_linux:
            systemd_env = None
            runtime_dir = Path(f"/run/user/{os.getuid()}")
            if runtime_dir.exists():
                systemd_env = {"XDG_RUNTIME_DIR": str(runtime_dir)}
            checks.extend(
                [
                    required_check(
                        {
                            "name": "ai_nas_index_daemon",
                            "kind": "systemd_system",
                            **run_checked(["systemctl", "is-active", "ai-nas-index-daemon.service"]),
                        },
                        required=False,
                    ),
                    required_check(
                        {
                            "name": "qwen25_local_openai_gateway",
                            "kind": "systemd_user",
                            **run_checked(["systemctl", "--user", "is-active", "qwen25-local-openai-gateway.service"], env=systemd_env),
                        }
                    ),
                    required_check(
                        {
                            "name": "openclaw_gateway",
                            "kind": "systemd_user",
                            **run_checked(["systemctl", "--user", "is-active", "openclaw-gateway.service"], env=systemd_env),
                        }
                    ),
                    required_check(
                        {
                            "name": "legacy_dream7b_local_openai_gateway",
                            "kind": "systemd_user",
                            **run_checked(["systemctl", "--user", "is-active", "dream7b-local-openai-gateway.service"], env=systemd_env),
                        },
                        required=False,
                    ),
                ]
            )
        else:
            checks.append(
                required_check(
                    {
                        "name": "systemd_services",
                        "kind": "systemd",
                        "ok": None,
                        "status": "not_applicable",
                        "platform": platform.system(),
                        "note": "systemd service checks are available only on the S100P/Linux deployment.",
                    },
                    required=False,
                )
            )
        required_checks = [item for item in checks if item.get("required") is not False]
        optional_checks = [item for item in checks if item.get("required") is False]
        return {
            "generated_at_epoch": time.time(),
            "ok_count": sum(1 for item in checks if item.get("ok") is True),
            "failed_count": sum(1 for item in required_checks if item.get("ok") is False),
            "required_failed_count": sum(1 for item in required_checks if item.get("ok") is False),
            "optional_failed_count": sum(1 for item in optional_checks if item.get("ok") is False),
            "unknown_count": sum(1 for item in checks if item.get("ok") is None),
            "checks": checks,
        }


class PortalHandler(BaseHTTPRequestHandler):
    server_version = "AINASOperatorPortal/1.0"

    @property
    def state(self) -> PortalState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_text(self, text: str, content_type: str, status: int = HTTPStatus.OK) -> None:
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file_text(self, path: Path, content_type: str) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.send_json({"ok": False, "error": f"read_failed:{type(exc).__name__}:{exc}", "path": str(path)}, HTTPStatus.NOT_FOUND)
            return
        self.send_text(text, content_type)

    def send_portal_html(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.send_json({"ok": False, "error": f"read_failed:{type(exc).__name__}:{exc}", "path": str(path)}, HTTPStatus.NOT_FOUND)
            return
        self.send_text(inject_runtime_sections(text, self.state.latest_bundle()), "text/html; charset=utf-8")

    def read_json_body(self) -> tuple[int | None, dict | None]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid_json:{exc}"}
        if not isinstance(payload, dict):
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "json_object_required"}
        return None, payload

    def require_product(self) -> bool:
        if not self.state.product_enabled():
            self.send_json({"ok": False, "error": "nas_product_api_not_configured"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return False
        return True

    def token_budget_api(self):
        if TokenBudgetIntegration is None:
            self.send_json({"ok": False, "error": "token_budget_integration_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return None
        try:
            return TokenBudgetIntegration()
        except Exception as exc:
            self.send_json({"ok": False, "error": f"token_budget_init_failed:{type(exc).__name__}:{exc}"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return None

    def send_journal_response(self, method: str, route: str, payload: dict | None = None) -> None:
        if journal_route_response is None:
            self.send_json({"ok": False, "error": "digua_journal_routes_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        try:
            status_code, result = journal_route_response(
                route,
                method=method,
                payload=payload or {},
                report_root=self.state.journal_report_root,
                evidence_dir=self.state.journal_evidence_dir,
                export_dir=self.state.journal_export_dir,
            )
        except Exception as exc:
            self.send_json({"ok": False, "error": f"digua_journal_route_failed:{type(exc).__name__}:{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_json(result, status_code)

    def do_GET(self) -> None:
        route = urlparse(self.path).path.rstrip("/") or "/"
        if route in {"/", "/operator_portal.html"}:
            if self.state.nas_portal:
                self.send_text(NAS_PORTAL_HTML, "text/html; charset=utf-8")
                return
            html_path = self.state.portal_html_path()
            if not html_path:
                self.send_json({"ok": False, "error": "operator_portal_html_not_found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_portal_html(html_path)
            return
        if route == "/journal":
            self.send_file_text(REPO_ROOT / "web" / "digua_journal.html", "text/html; charset=utf-8")
            return
        if route == "/static/digua_journal.css":
            self.send_file_text(REPO_ROOT / "web" / "static" / "digua_journal.css", "text/css; charset=utf-8")
            return
        if route == "/static/digua_journal.js":
            self.send_file_text(REPO_ROOT / "web" / "static" / "digua_journal.js", "application/javascript; charset=utf-8")
            return
        if route.startswith("/api/journal") or route.startswith("/journal/"):
            self.send_journal_response("GET", route)
            return
        if route == "/api/storage/status":
            if not self.require_product():
                return
            self.send_json(self.state.storage_status_payload())
            return
        if route == "/api/storage/list":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            query = urlparse(self.path).query
            params = dict(item.split("=", 1) if "=" in item else (item, "") for item in query.split("&") if item)
            status_code, payload = self.state.storage_list_payload(params.get("path", ""), user)
            self.send_json(payload, status_code)
            return
        if route == "/api/storage/operations":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            self.send_json({"ok": True, "operations": latest_file_operations(self.state.sqlite_index_path, limit=50) if self.state.sqlite_index_path else []})
            return
        if route == "/api/identity/users":
            if not self.require_product():
                return
            status, error, _user = self.state.require_admin(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            self.send_json({"ok": True, "users": self.state.identity_store.list_users() if self.state.identity_store else []})
            return
        if route == "/api/snapshot/stats":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            self.send_json({"ok": True, "stats": self.state.snapshot_store.stats() if self.state.snapshot_store else {}})
            return
        if route == "/api/backup/summary":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            manager = self.state.backup_manager
            self.send_json({"ok": True, "tasks": manager.list_tasks() if manager else [], "runs": manager.list_runs(limit=20) if manager else [], "stats": manager.stats() if manager else {}})
            return
        if route == "/api/media/summary":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            media = self.state.media_center
            self.send_json({"ok": True, "stats": media.stats() if media else {}, "albums": media.list_albums() if media else []})
            return
        if route == "/api/ops/summary":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            ops = self.state.ops_manager
            self.send_json({"ok": True, "checks": ops.list_checks(limit=50) if ops else [], "alerts": ops.list_alerts(True) if ops else [], "stats": ops.stats() if ops else {}})
            return
        if route == "/api/apps/summary":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            apps = self.state.app_ecosystem
            self.send_json({"ok": True, "plugins": apps.list_plugins() if apps else [], "protocols": apps.list_protocols() if apps else [], "stats": apps.stats() if apps else {}})
            return
        if route == "/api/audit/summary":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            self.send_json(self.state.audit_summary_payload())
            return
        if route == "/api/harness/status":
            if harness_status_response is None:
                self.send_json({"ok": False, "error": "harness_default_service_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self.send_json(harness_status_response(report_root=self.state.report_root, personal_root=self.state.personal_root))
            return
        if route == "/api/health":
            contract = self.state.portal_contract()
            self.send_json(
                {
                    "ok": bool(contract.get("found")) or self.state.product_enabled(),
                    "tool_id": TOOL_ID,
                    "operator_portal_contract": report_without_payload(contract),
                    "portal_html": str(self.state.portal_html_path()) if self.state.portal_html_path() else None,
                    "refresh_on_start": self.state.refresh_result,
                }
            )
            return
        if route == "/api/latest":
            self.send_json(self.state.latest_bundle())
            return
        if route == "/api/latest.goal_progress":
            self.send_json({"ok": True, "goal_progress": self.state.latest_bundle().get("goal_progress") or {}})
            return
        if route == "/api/latest.operator_decisions":
            self.send_json({"ok": True, "operator_decisions": self.state.latest_operator_decisions(limit=50)})
            return
        if route == "/api/services":
            self.send_json(self.state.service_status())
            return
        if route == "/api/contracts/operator-portal":
            self.send_json(self.state.portal_contract())
            return
        if route == "/api/portal-report":
            report_path = self.state.portal_report_path()
            if not report_path:
                self.send_json({"ok": False, "error": "portal_report_json_not_found"}, HTTPStatus.NOT_FOUND)
                return
            payload = read_json(report_path)
            if payload is None:
                self.send_json({"ok": False, "error": "portal_report_json_unreadable", "path": str(report_path)}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(payload)
            return
        if route == "/api/operator-decisions":
            self.send_json({"ok": True, "operator_decisions": self.state.latest_operator_decisions(limit=50)})
            return
        if route == "/api/token-budget/summary":
            api = self.token_budget_api()
            if api is None:
                return
            self.send_json(api.summary())
            return
        if route == "/api/token-budget/benchmark-summary":
            api = self.token_budget_api()
            if api is None:
                return
            self.send_json(api.benchmark_summary())
            return
        if route.startswith("/api/token-budget/trace/"):
            api = self.token_budget_api()
            if api is None:
                return
            self.send_json(api.trace(route.rsplit("/", 1)[-1]))
            return
        self.send_json(
            {
                "ok": False,
                "error": "not_found",
                "routes": [
                    "/",
                    "/journal",
                    "/api/health",
                    "/api/journal/health",
                    "/api/journal/timeline",
                    "/api/journal/projects",
                    "/api/latest",
                    "/api/latest.goal_progress",
                    "/api/latest.operator_decisions",
                    "/api/services",
                    "/api/portal-report",
                    "/api/operator-decisions",
                    "/api/harness/status",
                    "/api/contracts/operator-portal",
                    "/api/token-budget/summary",
                    "/api/token-budget/benchmark-summary",
                    "/api/token-budget/trace/{run_id}",
                    "POST /api/nas/copy/preview",
                    "POST /api/nas/copy/dry-run",
                    "POST /api/nas/copy/confirm",
                    "POST /api/nas/copy/execute",
                    "POST /api/nas/copy/rollback",
                    "POST /api/refresh",
                    "POST /api/operator-decision",
                    "POST /api/token-budget/estimate",
                    "POST /api/token-budget/route",
                    "POST /api/journal/manual-entry",
                    "POST /api/journal/generate-summary",
                    "POST /api/journal/export",
                ],
            },
            HTTPStatus.NOT_FOUND,
        )

    def do_POST(self) -> None:
        route = urlparse(self.path).path.rstrip("/") or "/"
        if route.startswith("/api/journal") or route.startswith("/journal/"):
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            self.send_journal_response("POST", route, payload)
            return
        if route == "/api/identity/create-user":
            if not self.require_product():
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            if self.state.user_count() > 0:
                auth_status, error, _user = self.state.require_admin(self.headers.get("Authorization"))
                if auth_status:
                    self.send_json(error or {}, auth_status)
                    return
            result = self.state.identity_store.create_user(
                str(payload.get("username") or ""),
                str(payload.get("password") or ""),
                str(payload.get("role") or "user"),
            ) if self.state.identity_store else {"ok": False, "error": "identity_store_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/identity/login":
            if not self.require_product():
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            result = self.state.identity_store.login(
                str(payload.get("username") or ""),
                str(payload.get("password") or ""),
            ) if self.state.identity_store else {"ok": False, "error": "identity_store_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.UNAUTHORIZED)
            return
        if route == "/api/identity/set-acl":
            if not self.require_product():
                return
            auth_status, error, _user = self.state.require_admin(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            result = self.state.identity_store.set_acl(
                str(payload.get("path") or ""),
                str(payload.get("principal_type") or "user"),
                str(payload.get("principal_name") or ""),
                str(payload.get("permission") or "read"),
            ) if self.state.identity_store else {"ok": False, "error": "identity_store_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/storage/rename":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            status_code, result = self.state.storage_rename(str(payload.get("path") or ""), str(payload.get("new_name") or ""), user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/copilot/chat":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            status_code, result = self.state.copilot_chat(str(payload.get("message") or ""), user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/snapshot/create":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            path = str(payload.get("path") or "")
            if not self.state.can_read(user or {}, path):
                self.send_json({"ok": False, "error": "permission_denied", "required": "read", "path": path}, HTTPStatus.FORBIDDEN)
                return
            result = self.state.snapshot_store.create_snapshot(str(payload.get("name") or ""), path, str((user or {}).get("username") or "")) if self.state.snapshot_store else {"ok": False, "error": "snapshot_store_unavailable"}
            self.send_json({"ok": bool(result.get("ok")), "snapshot": result.get("snapshot"), "result": result}, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/backup/create-task":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            try:
                source_rel = normalize_storage_relative_path(payload.get("source"))
                dest_rel = normalize_storage_relative_path(payload.get("dest"))
                source = resolve_storage_path(self.state.personal_root, source_rel)
                dest = resolve_storage_path(self.state.personal_root, dest_rel)
            except StoragePathError as exc:
                self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if not self.state.can_read(user or {}, source_rel) or not self.state.can_write(user or {}, dest_rel):
                self.send_json({"ok": False, "error": "permission_denied"}, HTTPStatus.FORBIDDEN)
                return
            result = self.state.backup_manager.create_task(
                str(payload.get("name") or ""),
                str(source),
                str(dest),
                int(payload.get("interval_seconds") or 0),
            ) if self.state.backup_manager else {"ok": False, "error": "backup_manager_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/backup/run":
            if not self.require_product():
                return
            auth_status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            result = self.state.backup_manager.run_backup(str(payload.get("name") or "")) if self.state.backup_manager else {"ok": False, "error": "backup_manager_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/media/index":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            rel = str(payload.get("path") or "")
            if not self.state.can_read(user or {}, rel):
                self.send_json({"ok": False, "error": "permission_denied", "required": "read", "path": rel}, HTTPStatus.FORBIDDEN)
                return
            try:
                root = resolve_storage_path(self.state.personal_root, rel)
            except StoragePathError as exc:
                self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            result = self.state.media_center.index_photos(root) if self.state.media_center else {"scanned": 0, "indexed": 0, "skipped": 0}
            self.send_json({"ok": True, "index": result})
            return
        if route == "/api/media/create-album":
            if not self.require_product():
                return
            auth_status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            result = self.state.media_center.create_album(str(payload.get("name") or ""), str(payload.get("description") or "")) if self.state.media_center else {"ok": False, "error": "media_center_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/ops/health-check":
            if not self.require_product():
                return
            auth_status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            check = self.state.ops_manager.check_health(str(payload.get("service_name") or "nas-service")) if self.state.ops_manager else {"status": "unavailable"}
            self.send_json({"ok": True, "check": check})
            return
        if route == "/api/apps/register-plugin":
            if not self.require_product():
                return
            auth_status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            result = self.state.app_ecosystem.register_plugin(
                str(payload.get("name") or ""),
                str(payload.get("version") or "1.0.0"),
                str(payload.get("type") or "app"),
                str(payload.get("description") or ""),
                payload.get("config") if isinstance(payload.get("config"), dict) else None,
            ) if self.state.app_ecosystem else {"ok": False, "error": "app_ecosystem_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/apps/add-protocol":
            if not self.require_product():
                return
            auth_status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            result = self.state.app_ecosystem.add_protocol(
                str(payload.get("name") or ""),
                str(payload.get("protocol") or ""),
                int(payload.get("port") or 0),
                payload.get("config") if isinstance(payload.get("config"), dict) else None,
            ) if self.state.app_ecosystem else {"ok": False, "error": "app_ecosystem_unavailable"}
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/refresh":
            result = self.state.refresh()
            contract = self.state.portal_contract()
            self.send_json(
                {
                    "ok": result.get("returncode") == 0 and bool(contract.get("found")),
                    "tool_id": TOOL_ID,
                    "refresh_result": result,
                    "remote_sync": self.state.last_remote_sync_result,
                    "operator_portal_contract": report_without_payload(contract),
                    "portal_html": str(self.state.portal_html_path()) if self.state.portal_html_path() else None,
                    "portal_report_json": str(self.state.portal_report_path()) if self.state.portal_report_path() else None,
                    "audit": {
                        "server_executes_actions": bool(self.state.remote_sync_host),
                        "remote_read_only_sync": bool(self.state.last_remote_sync_result),
                        "delete_performed": False,
                        "move_performed": False,
                        "overwrite_performed": False,
                        "copy_performed": bool(self.state.last_remote_sync_result and self.state.last_remote_sync_result.get("ok")),
                        "writes": "bounded operator_portal_contract report refresh plus optional local evidence snapshot copy",
                    },
                },
                HTTPStatus.OK if result.get("returncode") == 0 else HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        if route == "/api/operator-decision":
            length = int(self.headers.get("Content-Length", "0") or "0")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self.send_json({"ok": False, "error": f"invalid_json:{exc}"}, HTTPStatus.BAD_REQUEST)
                return
            status, result = self.state.record_operator_decision(payload)
            self.send_json(result, status)
            return
        if route in {"/api/token-budget/estimate", "/api/token-budget/route"}:
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            api = self.token_budget_api()
            if api is None:
                return
            result = api.estimate(payload or {}) if route.endswith("/estimate") else api.route(payload or {})
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route in {
            "/api/nas/copy/preview",
            "/api/nas/copy/dry-run",
            "/api/nas/copy/confirm",
            "/api/nas/copy/execute",
            "/api/nas/copy/rollback",
        }:
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            route_map = {
                "/api/nas/copy/preview": copy_preview_response,
                "/api/nas/copy/dry-run": copy_dry_run_response,
                "/api/nas/copy/confirm": copy_confirm_response,
                "/api/nas/copy/execute": copy_execute_response,
                "/api/nas/copy/rollback": copy_rollback_response,
            }
            handler = route_map[route]
            if handler is None:
                self.send_json({"ok": False, "error": "harness_copy_route_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            status_code, result = handler(payload or {}, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_json(result, status_code)
            return
        self.send_json(
            {
                "ok": False,
                "error": "not_found",
                "routes": [
                    "POST /api/refresh",
                    "POST /api/operator-decision",
                    "POST /api/nas/copy/preview",
                    "POST /api/nas/copy/dry-run",
                    "POST /api/nas/copy/confirm",
                    "POST /api/nas/copy/execute",
                    "POST /api/nas/copy/rollback",
                    "POST /api/token-budget/estimate",
                    "POST /api/token-budget/route",
                    "POST /api/journal/manual-entry",
                    "POST /api/journal/generate-summary",
                    "POST /api/journal/export",
                ],
            },
            HTTPStatus.NOT_FOUND,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the latest AI-NAS operator portal HTML plus small JSON status APIs.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--service-status-json", type=Path, default=None, help="Serve a captured service status JSON instead of probing this host.")
    parser.add_argument("--remote-sync-host", default=None, help="Optional SSH host, for example sunrise@192.168.127.10, used to read latest S100P report JSON before refresh.")
    parser.add_argument("--remote-sync-key", type=Path, default=None, help="Optional SSH private key for --remote-sync-host.")
    parser.add_argument("--remote-report-root", default="/mnt/nas/openclaw/reports/ai_nas_mvp")
    parser.add_argument("--remote-sync-dir", type=Path, default=None, help="Local evidence directory populated by read-only remote sync before portal refresh.")
    parser.add_argument("--no-refresh", action="store_true", help="Serve the latest existing portal report without generating a fresh one on start.")
    parser.add_argument("--personal-root", type=Path, default=None, help="Enable NAS product APIs against this personal storage root.")
    parser.add_argument("--sqlite-index-path", type=Path, default=None)
    parser.add_argument("--identity-db-path", type=Path, default=None)
    parser.add_argument("--snapshot-db-path", type=Path, default=None)
    parser.add_argument("--backup-db-path", type=Path, default=None)
    parser.add_argument("--media-db-path", type=Path, default=None)
    parser.add_argument("--ops-db-path", type=Path, default=None)
    parser.add_argument("--app-db-path", type=Path, default=None)
    parser.add_argument("--storage-max-files", type=int, default=5000)
    parser.add_argument("--nas-portal", action="store_true", help="Serve the built-in AI-NAS Web OS portal instead of requiring generated operator HTML.")
    parser.add_argument("--official-manager-url", default=None)
    parser.add_argument("--openclaw-gateway-url", default=None)
    parser.add_argument("--openclaw-model-gateway-url", default=None)
    parser.add_argument("--qwen-gateway-url", default=None)
    parser.add_argument("--journal-report-root", type=Path, default=None)
    parser.add_argument("--journal-evidence-dir", type=Path, default=None)
    parser.add_argument("--journal-export-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    state = PortalState(
        args.report_root,
        evidence_roots,
        refresh_on_start=not args.no_refresh,
        service_status_json=args.service_status_json,
        remote_sync_host=args.remote_sync_host,
        remote_sync_key=args.remote_sync_key,
        remote_report_root=args.remote_report_root,
        remote_sync_dir=args.remote_sync_dir,
        personal_root=args.personal_root,
        sqlite_index_path=args.sqlite_index_path,
        identity_db_path=args.identity_db_path,
        snapshot_db_path=args.snapshot_db_path,
        backup_db_path=args.backup_db_path,
        media_db_path=args.media_db_path,
        ops_db_path=args.ops_db_path,
        app_db_path=args.app_db_path,
        nas_portal=args.nas_portal,
        storage_max_files=args.storage_max_files,
        official_manager_url=args.official_manager_url,
        openclaw_gateway_url=args.openclaw_gateway_url,
        openclaw_model_gateway_url=args.openclaw_model_gateway_url,
        qwen_gateway_url=args.qwen_gateway_url,
        journal_report_root=args.journal_report_root,
        journal_evidence_dir=args.journal_evidence_dir,
        journal_export_dir=args.journal_export_dir,
    )
    server = ThreadingHTTPServer((args.bind, args.port), PortalHandler)
    server.state = state  # type: ignore[attr-defined]
    print(f"http://{args.bind}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
