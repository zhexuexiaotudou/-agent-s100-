#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import threading
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    PHOTO_EXTS,
    SCAN_DIRS,
    StoragePathError,
    _record_from_sqlite_row,
    build_sqlite_inventory,
    ensure_image_captions_for_photos,
    ensure_image_embeddings_for_photos,
    image_caption_summary,
    image_embedding_runtime_status,
    image_embedding_summary,
    latest_file_operations,
    list_storage_directory,
    log_file_operation,
    ocr_candidate_record,
    ocr_engine_status,
    ocr_results_summary,
    open_index_db,
    normalize_storage_relative_path,
    resolve_storage_path,
    run_ocr_for_record,
    safe_write_json,
    search_photo_semantic_index,
    storage_entry_payload,
    storage_status,
    upsert_ocr_result,
    vision_caption_runtime_status,
)
from ai_nas_vision_runtime import vision_product_runtime_status
from ai_nas_vision_schema import vision_product_schema_status
from ai_nas_vision_index import ensure_photo_visual_states, photo_visual_state_summary
from ai_nas_vision_search import search_product_visual_index
from ai_nas_ocr_adapter import run_product_ocr_for_record, upsert_product_ocr_evidence
from ai_nas_embedding_adapter import (
    product_embedding_summary,
    run_product_image_embedding_for_record,
    upsert_product_image_embedding,
)
from ai_nas_region_adapter import (
    product_region_summary,
    run_product_region_analysis_for_record,
    upsert_product_region_evidence,
)
from ai_nas_operator_portal_contract_probe import latest_report, read_json
try:
    from ai_nas_identity import IdentityStore, parse_bearer_token
    _HAS_IDENTITY = True
except ImportError:
    _HAS_IDENTITY = False
try:
    from ai_nas_snapshot import SnapshotStore
    _HAS_SNAPSHOT = True
except ImportError:
    _HAS_SNAPSHOT = False
try:
    from ai_nas_backup import BackupManager
    _HAS_BACKUP = True
except ImportError:
    _HAS_BACKUP = False
try:
    from ai_nas_media import MediaCenter
    _HAS_MEDIA = True
except ImportError:
    _HAS_MEDIA = False
try:
    from ai_nas_ops import OpsManager
    _HAS_OPS = True
except ImportError:
    _HAS_OPS = False
try:
    from ai_nas_app_ecosystem import AppEcosystem
    _HAS_APP_ECOSYSTEM = True
except ImportError:
    _HAS_APP_ECOSYSTEM = False
try:
    from ai_nas_schedule import ScheduleRuleManager
    _HAS_SCHEDULE = True
except ImportError:
    _HAS_SCHEDULE = False


TOOL_ID = "ai_nas_operator_portal_server"
DEFAULT_OPENCLAW_GATEWAY_URL = "http://127.0.0.1:18789"
DEFAULT_OPENCLAW_MODEL_GATEWAY_URL = "http://127.0.0.1:18888"
DEFAULT_OPENCLAW_MODEL = "OpenClaw-Dream7B-S100P-local"
DEFAULT_QWEN_GATEWAY_URL = "http://127.0.0.1:18080"
DEFAULT_QWEN_MODEL = "Qwen2.5-1.5B-Instruct-S100P-official"
DEFAULT_PORTAL_LOCAL_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "openclaw_nas_portal.local.json"
COPILOT_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".heic", ".heif"}
COPILOT_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".3gp"}
STORAGE_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"}
STORAGE_DOCUMENT_EXTS = {".txt", ".md", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".json", ".yaml", ".yml"}
STORAGE_ARCHIVE_EXTS = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"}
STORAGE_CODE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".sh", ".ps1", ".bat", ".sql", ".xml"}
STORAGE_MODEL_EXTS = {".onnx", ".pt", ".pth", ".safetensors", ".bin", ".gguf", ".hbm", ".hbo", ".bc"}


def default_official_manager_url() -> str:
    env_url = os.environ.get("OPENCLAW_OFFICIAL_MANAGER_URL", "").strip()
    if env_url:
        return env_url
    try:
        cfg = json.loads(DEFAULT_PORTAL_LOCAL_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(cfg.get("official_manager_url") or cfg.get("nas_manager_url") or "").strip()
IMAGE_QUERY_TERMS = (
    "image", "images", "photo", "photos", "picture", "pictures", "album",
    "图片", "图像", "照片", "相册", "截图", "白底", "发票", "车", "汽车",
)
VIDEO_QUERY_TERMS = ("video", "videos", "movie", "movies", "影片", "视频", "录像", "电影")
FILE_QUERY_TERMS = ("file", "files", "document", "documents", "doc", "docs", "文件", "文档", "合同", "发票")
NAS_DOMAIN_QUERY_TERMS = IMAGE_QUERY_TERMS + VIDEO_QUERY_TERMS + FILE_QUERY_TERMS + (
    "nas", "qnap", "qfinder", "qts", "storage", "folder", "directory", "album",
    "backup", "snapshot", "restore", "acl", "permission",
    "存储", "目录", "文件夹", "相册", "备份", "同步", "快照", "恢复", "回收站",
    "上传", "下载", "预览", "权限", "用户", "官方管理器",
)
NAS_ACTION_QUERY_TERMS = (
    "find", "search", "show", "open", "list", "filter", "upload", "download",
    "copy", "move", "rename", "delete",
    "找", "查找", "搜索", "筛选", "打开", "列出", "查看", "上传", "下载",
    "复制", "移动", "重命名", "删除", "最近",
)
BROAD_SEARCH_TERMS = IMAGE_QUERY_TERMS + VIDEO_QUERY_TERMS + FILE_QUERY_TERMS + (
    "帮我找", "查找", "筛选", "搜索", "打开", "最近", "latest", "recent", "find", "show",
)
REPORT_FILENAMES = {
    "operator_portal_contract": "operator_portal_contract.json",
    "production_readiness_gate": "production_readiness_gate.json",
    "operational_slo_rollup_contract": "operational_slo_rollup_contract.json",
    "objective_traceability_contract": "objective_traceability_contract.json",
    "production_dependency_bundle": "production_dependency_bundle.json",
    "production_blocker_runbook_contract": "production_blocker_runbook_contract.json",
    "dream7b_perf_identity": "dream7b_perf_identity.json",
    "dream7b_product_decision_packet": "dream7b_product_decision_packet.json",
    "dream7b_fast_path_regression": "dream7b_fast_path_regression.json",
    "dream7b_product_guardrail_snapshot": "dream7b_product_guardrail_snapshot.json",
    "dream7b_queue_health_snapshot": "dream7b_queue_health_snapshot.json",
    "dream7b_workstream_overlap_audit": "dream7b_workstream_overlap_audit.json",
    "dream7b_default_service_freshness_gate": "dream7b_default_service_freshness_gate_latest.json",
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
PWA_MANIFEST = {
    "name": "OpenClaw NAS",
    "short_name": "OpenClaw",
    "description": "OpenClaw NAS home dashboard, file manager, media library, and AI assistant.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "any",
    "background_color": "#f4fbf1",
    "theme_color": "#f4fbf1",
    "icons": [
        {"src": "/assets/openclaw/openclaw_app_icon.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
    ],
    "shortcuts": [
        {"name": "OpenClaw", "short_name": "Home", "url": "/", "icons": [{"src": "/assets/openclaw/openclaw_app_icon.png", "sizes": "512x512", "type": "image/png"}]},
        {"name": "Files", "short_name": "Files", "url": "/#files", "icons": [{"src": "/assets/openclaw/openclaw_app_icon.png", "sizes": "512x512", "type": "image/png"}]},
    ],
}
PWA_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="112" fill="#f4fbf1"/>
<circle cx="160" cy="158" r="54" fill="#59b52f"/>
<circle cx="256" cy="126" r="58" fill="#59b52f"/>
<circle cx="352" cy="158" r="54" fill="#59b52f"/>
<circle cx="126" cy="260" r="50" fill="#59b52f"/>
<circle cx="386" cy="260" r="50" fill="#59b52f"/>
<path d="M146 344c0-73 53-132 110-132s110 59 110 132c0 43-31 66-66 54-17-6-29-14-44-14s-27 8-44 14c-35 12-66-11-66-54z" fill="#59b52f"/>
<path d="M218 305c14 18 62 18 76 0" fill="none" stroke="#fff" stroke-width="18" stroke-linecap="round"/>
</svg>
"""
PWA_SW_JS = """const CACHE_NAME='openclaw-nas-pwa-v8';
const SHELL_ASSETS=[
  '/',
  '/manifest.webmanifest',
  '/assets/openclaw/openclaw_app_icon.png',
  '/assets/openclaw/openclaw_mascot.png',
  '/assets/openclaw/home_room_bg.png',
  '/assets/openclaw/nav_home.png',
  '/assets/openclaw/nav_photos.png',
  '/assets/openclaw/nav_movies.png',
  '/assets/openclaw/nav_music.png',
  '/assets/openclaw/nav_files.png',
  '/assets/openclaw/nav_recovery.png',
  '/assets/openclaw/nav_backup.png',
  '/assets/openclaw/nav_users.png',
  '/assets/openclaw/nav_system.png',
  '/assets/openclaw/nav_apps.png',
  '/assets/openclaw/action_official.png',
  '/assets/openclaw/action_install.png',
  '/assets/openclaw/action_refresh.png',
  '/assets/openclaw/action_logout.png',
  '/assets/openclaw/action_send.png',
  '/assets/openclaw/action_chevron.png',
  '/assets/openclaw/weather_sunny.png',
  '/assets/openclaw/weather_partly_cloudy.png',
  '/assets/openclaw/weather_cloudy.png',
  '/assets/openclaw/weather_light_rain.png',
  '/assets/openclaw/weather_heavy_rain.png',
  '/assets/openclaw/weather_thunderstorm.png',
  '/assets/openclaw/weather_snow.png',
  '/assets/openclaw/weather_fog.png'
];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(SHELL_ASSETS)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET') return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin || url.pathname.startsWith('/api/')) return;
  const cacheable=url.pathname==='/' || url.pathname==='/operator_portal.html' || url.pathname==='/manifest.webmanifest' || url.pathname==='/pwa-icon.svg' || url.pathname.startsWith('/assets/openclaw/');
  if(!cacheable && req.mode!=='navigate') return;
  event.respondWith(fetch(req).then(resp=>{
    const copy=resp.clone();
    caches.open(CACHE_NAME).then(cache=>cache.put(cacheable?req:'/',copy)).catch(()=>{});
    return resp;
  }).catch(()=>caches.match(req).then(cached=>cached||caches.match('/'))));
});
"""


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


def post_json(url: str, payload: dict, timeout: int = 60) -> dict:
    started = time.perf_counter()
    try:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=raw,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"raw": body[:2000]}
            return {
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "payload": parsed,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:2000]}
        return {
            "ok": False,
            "status": exc.code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "payload": parsed,
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "payload": {},
            "error": f"{type(exc).__name__}:{exc}",
        }


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
    for key in [
        "goal_completion",
        "goal_finalizer",
        "nas_soak",
        "operator_portal",
        "dream7b_service_guardrails",
        "dream7b_interaction",
    ]:
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
        elif key == "dream7b_service_guardrails":
            evidence = (
                f"product={item.get('product_verdict')}; "
                f"fast={item.get('fast_path_verdict')}; "
                f"guardrail={item.get('guardrail_verdict')}; "
                f"freshness={item.get('freshness_verdict')}; "
                f"default={item.get('queue_batch_service_remains_default')}; "
                f"s100p_runtime_now={item.get('s100p_runtime_experiment_now')}; "
                f"quick_ready={item.get('quick_ready_first_content_ms')}ms via {item.get('quick_ready_execution_path')}; "
                f"rollback={item.get('default_rollback_dry_run_ready')}; "
                f"listener_match={item.get('gateway_listener_matches_systemd_main_pid')}; "
                f"orphan_listener={item.get('gateway_orphan_listener_detected')}; "
                f"drift_gate={item.get('gateway_listener_drift_gate_verdict')}"
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


def render_storage_browser_html() -> str:
    return """
  <section class="section" data-testid="nas-storage" id="nas-storage"><h2>NAS Storage</h2>
    <div class="command-grid">
      <div>
        <input id="storage-path" value="" aria-label="Storage path">
        <button id="storage-open" type="button">Open</button>
        <button id="storage-up" type="button">Up</button>
        <button id="storage-refresh" type="button">Refresh</button>
      </div>
      <form id="storage-upload-form">
        <input id="storage-upload-file" name="file" type="file">
        <button type="submit">Upload</button>
      </form>
      <p id="storage-status"><code>idle</code></p>
    </div>
    <table>
      <thead><tr><th>Name</th><th>Kind</th><th>Size</th><th>Modified</th><th>Actions</th></tr></thead>
      <tbody id="storage-entries"><tr><td colspan="5">Loading...</td></tr></tbody>
    </table>
    <details>
      <summary>Operation Log</summary>
      <pre id="storage-operations">[]</pre>
    </details>
    <script>
      let aiNasStoragePath = '';
      function storageHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      }
      async function storageJson(url, options) {
        const response = await fetch(url, options);
        const payload = await response.json();
        if (!response.ok || payload.ok === false) throw new Error(payload.error || response.statusText);
        return payload;
      }
      async function loadStorage(path) {
        const status = document.getElementById('storage-status');
        aiNasStoragePath = path || '';
        document.getElementById('storage-path').value = aiNasStoragePath;
        status.innerHTML = '<code>loading</code>';
        try {
          const payload = await storageJson('/api/storage/list?path=' + encodeURIComponent(aiNasStoragePath));
          const rows = payload.entries.map(entry => {
            const rel = entry.relative_path;
            const open = entry.is_dir
              ? '<button type="button" data-open="' + storageHtml(rel) + '">Open</button>'
              : '<a href="/api/storage/download?path=' + encodeURIComponent(rel) + '">Download</a>';
            return '<tr><td><code>' + storageHtml(entry.name) + '</code></td><td>' +
              (entry.is_dir ? 'dir' : 'file') + '</td><td>' + storageHtml(entry.size_bytes) +
              '</td><td>' + storageHtml(entry.mtime) + '</td><td>' + open +
              ' <button type="button" data-rename="' + storageHtml(rel) + '">Rename</button>' +
              ' <button type="button" data-copy="' + storageHtml(rel) + '">Copy</button>' +
              ' <button type="button" data-move="' + storageHtml(rel) + '">Move</button>' +
              ' <button type="button" data-delete="' + storageHtml(rel) + '">Delete</button></td></tr>';
          }).join('');
          document.getElementById('storage-entries').innerHTML = rows || '<tr><td colspan="5">Empty</td></tr>';
          document.getElementById('storage-operations').textContent = JSON.stringify(payload.operations || [], null, 2);
          status.innerHTML = '<code>root=' + storageHtml(payload.root) + ' entries=' + payload.entry_count + '</code>';
        } catch (error) {
          status.innerHTML = '<code>failed: ' + storageHtml(String(error).slice(0, 160)) + '</code>';
        }
      }
      document.getElementById('storage-open').addEventListener('click', () => loadStorage(document.getElementById('storage-path').value));
      document.getElementById('storage-refresh').addEventListener('click', () => loadStorage(aiNasStoragePath));
      document.getElementById('storage-up').addEventListener('click', () => {
        const parts = aiNasStoragePath.split('/').filter(Boolean);
        parts.pop();
        loadStorage(parts.join('/'));
      });
      document.getElementById('storage-entries').addEventListener('click', async event => {
        const button = event.target.closest('button');
        if (!button) return;
        try {
          if (button.dataset.open !== undefined) {
            await loadStorage(button.dataset.open);
            return;
          }
          if (button.dataset.delete !== undefined) {
            if (!confirm('Delete ' + button.dataset.delete + '?')) return;
            await storageJson('/api/storage/file?path=' + encodeURIComponent(button.dataset.delete), {method: 'DELETE'});
          } else if (button.dataset.rename !== undefined) {
            const name = prompt('New name', button.dataset.rename.split('/').pop());
            if (!name) return;
            await storageJson('/api/storage/rename', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:button.dataset.rename, new_name:name})});
          } else if (button.dataset.copy !== undefined) {
            const target = prompt('Copy target path', button.dataset.copy + '.copy');
            if (!target) return;
            await storageJson('/api/storage/copy', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source:button.dataset.copy, target})});
          } else if (button.dataset.move !== undefined) {
            const target = prompt('Move target path', button.dataset.move);
            if (!target) return;
            await storageJson('/api/storage/move', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source:button.dataset.move, target})});
          }
          await loadStorage(aiNasStoragePath);
        } catch (error) {
          document.getElementById('storage-status').innerHTML = '<code>failed: ' + storageHtml(String(error).slice(0, 160)) + '</code>';
        }
      });
      document.getElementById('storage-upload-form').addEventListener('submit', async event => {
        event.preventDefault();
        const fileInput = document.getElementById('storage-upload-file');
        if (!fileInput.files.length) return;
        const body = new FormData();
        body.append('file', fileInput.files[0]);
        await fetch('/api/storage/upload?path=' + encodeURIComponent(aiNasStoragePath), {method:'POST', body});
        fileInput.value = '';
        await loadStorage(aiNasStoragePath);
      });
      loadStorage('');
    </script>
  </section>
"""


def html_escape(value: object) -> str:
    import html

    return html.escape("" if value is None else str(value), quote=True)


def parse_multipart_upload(content_type: str, raw: bytes) -> tuple[str, bytes]:
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not match:
        raise ValueError("multipart_boundary_missing")
    boundary = ("--" + match.group(1)).encode("utf-8")
    for chunk in raw.split(boundary):
        if not chunk:
            continue
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if chunk in {b"--", b"--\r\n"}:
            continue
        if chunk.endswith(b"--"):
            chunk = chunk[:-2].rstrip()
        header_blob, sep, body = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = header_blob.decode("utf-8", errors="replace")
        if 'name="file"' not in headers:
            continue
        filename_match = re.search(r'filename="([^"]+)"', headers)
        if not filename_match:
            raise ValueError("upload_filename_missing")
        if body.endswith(b"\r\n"):
            body = body[:-2]
        return filename_match.group(1), body
    raise ValueError("upload_file_part_missing")


def inject_runtime_sections(html_text: str, latest_bundle: dict) -> str:
    marker = "</main>"
    service_status = latest_bundle.get("service_status") or {}
    decisions = ((latest_bundle.get("operator_decisions") or {}).get("items") or [])
    goal_progress = latest_bundle.get("goal_progress") or {}
    section = (
        render_goal_progress_html(goal_progress)
        + render_live_controls_html()
        + render_storage_browser_html()
        + render_service_status_html(service_status)
        + render_operator_decisions_html(decisions)
    )
    if marker in html_text:
        return html_text.replace(marker, section + "\n</main>", 1)
    return html_text + section


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
        personal_root: Path = DEFAULT_PERSONAL_ROOT,
        sqlite_index_path: Path = DEFAULT_SQLITE_INDEX_PATH,
        storage_max_files: int = 50000,
        identity_db_path: Path | None = None,
        snapshot_db_path: Path | None = None,
        backup_db_path: Path | None = None,
        media_db_path: Path | None = None,
        ops_db_path: Path | None = None,
        app_db_path: Path | None = None,
        schedule_db_path: Path | None = None,
        nas_portal_enabled: bool = False,
        nas_portal_path: Path | None = None,
        official_manager_url: str = "",
        openclaw_gateway_url: str = DEFAULT_OPENCLAW_GATEWAY_URL,
        openclaw_model_gateway_url: str = DEFAULT_OPENCLAW_MODEL_GATEWAY_URL,
        openclaw_model: str = DEFAULT_OPENCLAW_MODEL,
        qwen_gateway_url: str = DEFAULT_QWEN_GATEWAY_URL,
        qwen_model: str = DEFAULT_QWEN_MODEL,
    ) -> None:
        self.report_root = report_root
        self.evidence_roots = evidence_roots
        self.service_status_json = service_status_json
        self.remote_sync_host = remote_sync_host
        self.remote_sync_key = remote_sync_key
        self.remote_report_root = remote_report_root
        self.remote_sync_dir = remote_sync_dir
        self.personal_root = personal_root
        self.sqlite_index_path = sqlite_index_path
        self.storage_max_files = storage_max_files
        self.identity_db_path = identity_db_path
        self._identity_store = None  # type: ignore[assignment]
        self.snapshot_db_path = snapshot_db_path
        self._snapshot_store = None
        self.backup_db_path = backup_db_path or (self.report_root / "nas_web_os_backup.sqlite3")
        self._backup_manager = None
        self.media_db_path = media_db_path or (self.report_root / "nas_web_os_media.sqlite3")
        self._media_center = None
        self.ops_db_path = ops_db_path or (self.report_root / "nas_web_os_ops.sqlite3")
        self._ops_manager = None
        self.app_db_path = app_db_path or (self.report_root / "nas_web_os_apps.sqlite3")
        self._app_ecosystem = None
        self.schedule_db_path = schedule_db_path or (self.report_root / "nas_web_os_schedule.sqlite3")
        self._schedule_manager = None
        self.nas_portal_enabled = nas_portal_enabled
        self.nas_portal_path = nas_portal_path
        self.official_manager_url = official_manager_url.strip()
        self.openclaw_gateway_url = openclaw_gateway_url.rstrip("/")
        self.openclaw_model_gateway_url = openclaw_model_gateway_url.rstrip("/")
        self.openclaw_model = openclaw_model
        self.qwen_gateway_url = qwen_gateway_url.rstrip("/")
        self.qwen_model = qwen_model
        self.last_remote_sync_result: dict | None = None
        self.refresh_lock = threading.Lock()
        self.storage_lock = threading.Lock()
        self.refresh_result: dict | None = None
        if refresh_on_start:
            self.refresh_result = self.refresh()
    @property
    def snapshot_store(self):
        if self._snapshot_store is None and _HAS_SNAPSHOT:
            self._snapshot_store = SnapshotStore(self.personal_root, self.snapshot_db_path)
        return self._snapshot_store

    @property
    def identity_store(self):
        if self._identity_store is None and _HAS_IDENTITY and self.identity_db_path:
            self._identity_store = IdentityStore(self.identity_db_path)
        return self._identity_store

    @property
    def backup_manager(self):
        if self._backup_manager is None and _HAS_BACKUP:
            self._backup_manager = BackupManager(self.backup_db_path)
        return self._backup_manager

    @property
    def media_center(self):
        if self._media_center is None and _HAS_MEDIA:
            self._media_center = MediaCenter(self.media_db_path)
        return self._media_center

    @property
    def ops_manager(self):
        if self._ops_manager is None and _HAS_OPS:
            self._ops_manager = OpsManager(self.ops_db_path)
        return self._ops_manager

    @property
    def app_ecosystem(self):
        if self._app_ecosystem is None and _HAS_APP_ECOSYSTEM:
            self._app_ecosystem = AppEcosystem(self.app_db_path)
        return self._app_ecosystem

    @property
    def schedule_manager(self):
        if self._schedule_manager is None and _HAS_SCHEDULE:
            self._schedule_manager = ScheduleRuleManager(self.schedule_db_path)
        return self._schedule_manager

    def _identity_user(self, handler) -> dict | None:
        if not _HAS_IDENTITY or not self.identity_store:
            return None
        token = parse_bearer_token(handler.headers.get("Authorization"))
        if not token:
            return None
        return self.identity_store.validate_token(token)



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

    def rescan_storage(self) -> dict:
        return build_sqlite_inventory(self.personal_root, self.sqlite_index_path, max_files=self.storage_max_files)

    def storage_status_payload(self) -> dict:
        status = storage_status(self.personal_root, self.sqlite_index_path)
        status["index_status"] = build_sqlite_inventory(
            self.personal_root,
            self.sqlite_index_path,
            max_files=self.storage_max_files,
        )
        status["operations"] = latest_file_operations(self.sqlite_index_path, limit=20)
        return {"ok": True, **status}

    def _storage_category(self, path: Path) -> tuple[str, str]:
        ext = path.suffix.lower()
        if ext in COPILOT_IMAGE_EXTS:
            return "image", "图片"
        if ext in COPILOT_VIDEO_EXTS:
            return "video", "视频"
        if ext in STORAGE_AUDIO_EXTS:
            return "audio", "音频"
        if ext in STORAGE_DOCUMENT_EXTS:
            return "document", "文档"
        if ext in STORAGE_ARCHIVE_EXTS:
            return "archive", "压缩包"
        if ext in STORAGE_MODEL_EXTS:
            return "model", "模型/编译产物"
        if ext in STORAGE_CODE_EXTS:
            return "code", "代码"
        return "other", "其他"

    def storage_insights_payload(self, user: dict | None = None) -> dict:
        root = self.personal_root.resolve(strict=False)
        status = storage_status(self.personal_root, self.sqlite_index_path)
        by_type: dict[str, dict] = {}
        by_top_dir: dict[str, dict] = {}
        by_extension: dict[str, dict] = {}
        largest: list[dict] = []
        recent: list[dict] = []
        total_visible_bytes = 0
        file_count = 0
        hidden_count = 0
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    rel = path.resolve(strict=False).relative_to(root).as_posix()
                except ValueError:
                    continue
                if not self._user_can_read(user, rel):
                    hidden_count += 1
                    continue
                stat = path.stat()
                size = int(stat.st_size)
                file_count += 1
                total_visible_bytes += size
                if rel.startswith(".versions/") or rel.startswith(".trash/"):
                    key, label = "protected", "版本/回收站"
                else:
                    key, label = self._storage_category(path)
                type_row = by_type.setdefault(key, {"key": key, "label": label, "bytes": 0, "count": 0})
                type_row["bytes"] += size
                type_row["count"] += 1
                top = rel.split("/", 1)[0] if "/" in rel else "根目录"
                dir_row = by_top_dir.setdefault(top, {"path": top, "bytes": 0, "count": 0})
                dir_row["bytes"] += size
                dir_row["count"] += 1
                ext = path.suffix.lower() or "(none)"
                ext_row = by_extension.setdefault(ext, {"extension": ext, "bytes": 0, "count": 0})
                ext_row["bytes"] += size
                ext_row["count"] += 1
                item = {
                    "name": path.name,
                    "relative_path": rel,
                    "type": key,
                    "extension": ext,
                    "size_bytes": size,
                    "mtime": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stat.st_mtime)),
                    "open_url": "/api/storage/download?path=" + quote(rel, safe=""),
                }
                largest.append(item)
                recent.append(item)
        def ranked(values: list[dict], key: str = "bytes", limit: int = 8) -> list[dict]:
            return sorted(values, key=lambda x: (int(x.get(key) or 0), str(x.get("label") or x.get("path") or "")), reverse=True)[:limit]
        type_rows = ranked(list(by_type.values()))
        dir_rows = ranked(list(by_top_dir.values()))
        ext_rows = ranked(list(by_extension.values()))
        return {
            "ok": True,
            "generated_at": status.get("generated_at"),
            "capacity": status.get("capacity") or {},
            "personal_root": status.get("personal_root"),
            "visible": {
                "bytes": total_visible_bytes,
                "file_count": file_count,
                "hidden_file_count": hidden_count,
            },
            "by_type": type_rows,
            "by_top_dir": dir_rows,
            "by_extension": ext_rows,
            "largest_files": sorted(largest, key=lambda x: int(x.get("size_bytes") or 0), reverse=True)[:8],
            "recent_files": sorted(recent, key=lambda x: str(x.get("mtime") or ""), reverse=True)[:8],
            "operations": latest_file_operations(self.sqlite_index_path, limit=10),
        }

    def storage_list_payload(self, relative_path: str) -> dict:
        payload = list_storage_directory(self.personal_root, relative_path)
        payload["ok"] = True
        payload["status"] = storage_status(self.personal_root, self.sqlite_index_path)
        payload["operations"] = latest_file_operations(self.sqlite_index_path, limit=20)
        return payload

    def storage_delete(self, relative_path: str, username: str = "") -> tuple[int, dict]:
        rel = normalize_storage_relative_path(relative_path)
        if not rel:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "cannot_delete_storage_root"}
        target = resolve_storage_path(self.personal_root, rel, allow_root=False)
        with self.storage_lock:
            try:
                if not target.exists():
                    raise FileNotFoundError(str(target))
                if target.is_dir():
                    if any(target.iterdir()):
                        raise OSError("refuse_delete_non_empty_directory")
                    target.rmdir()
                    size = 0
                    digest = None
                else:
                    size = target.stat().st_size
                    digest = None
                    if _HAS_SNAPSHOT and self.snapshot_store:
                        trash_result = self.snapshot_store.trash_file(target, username)
                        if not trash_result.get("ok"):
                            raise OSError(f"trash_failed:{trash_result.get('error','')}")
                    else:
                        target.unlink()
                op = log_file_operation(self.sqlite_index_path, "delete", rel, None, "ok", size_bytes=size, sha256=digest)
                index_status = self.rescan_storage()
                return HTTPStatus.OK, {"ok": True, "operation": op, "index_status": index_status}
            except Exception as exc:
                op = log_file_operation(self.sqlite_index_path, "delete", rel, None, "failed", f"{type(exc).__name__}:{exc}")
                return HTTPStatus.BAD_REQUEST, {"ok": False, "error": op["detail"], "operation": op}

    def storage_rename(self, relative_path: str, new_name: str) -> tuple[int, dict]:
        rel = normalize_storage_relative_path(relative_path)
        clean_name = normalize_storage_relative_path(new_name)
        if not rel or not clean_name or "/" in clean_name:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "rename_requires_single_new_name"}
        source = resolve_storage_path(self.personal_root, rel, allow_root=False)
        target_rel = str(Path(rel).parent / clean_name).replace("\\", "/")
        if target_rel.startswith("./"):
            target_rel = target_rel[2:]
        target = resolve_storage_path(self.personal_root, target_rel, allow_root=False)
        return self._storage_move_or_copy("rename", source, target, rel, target_rel, copy_mode=False)

    def storage_move(self, source_relative_path: str, target_relative_path: str) -> tuple[int, dict]:
        source_rel = normalize_storage_relative_path(source_relative_path)
        target_rel = normalize_storage_relative_path(target_relative_path)
        source = resolve_storage_path(self.personal_root, source_rel, allow_root=False)
        target = resolve_storage_path(self.personal_root, target_rel, allow_root=False)
        return self._storage_move_or_copy("move", source, target, source_rel, target_rel, copy_mode=False)

    def storage_copy(self, source_relative_path: str, target_relative_path: str) -> tuple[int, dict]:
        source_rel = normalize_storage_relative_path(source_relative_path)
        target_rel = normalize_storage_relative_path(target_relative_path)
        source = resolve_storage_path(self.personal_root, source_rel, allow_root=False)
        target = resolve_storage_path(self.personal_root, target_rel, allow_root=False)
        return self._storage_move_or_copy("copy", source, target, source_rel, target_rel, copy_mode=True)

    def _storage_move_or_copy(
        self,
        action: str,
        source: Path,
        target: Path,
        source_rel: str,
        target_rel: str,
        *,
        copy_mode: bool,
    ) -> tuple[int, dict]:
        with self.storage_lock:
            try:
                if not source.exists():
                    raise FileNotFoundError(str(source))
                if target.exists():
                    if _HAS_SNAPSHOT and self.snapshot_store:
                        self.snapshot_store.save_version(target)
                    if target.is_file():
                        target.unlink()
                    elif target.is_dir() and not copy_mode:
                        shutil.rmtree(str(target))
                target.parent.mkdir(parents=True, exist_ok=True)
                if copy_mode:
                    if source.is_dir():
                        shutil.copytree(source, target)
                        size = 0
                        digest = None
                    else:
                        shutil.copy2(source, target)
                        size = target.stat().st_size
                        digest = None
                else:
                    shutil.move(str(source), str(target))
                    size = 0 if target.is_dir() else target.stat().st_size
                    digest = None
                op = log_file_operation(
                    self.sqlite_index_path,
                    action,
                    source_rel,
                    target_rel,
                    "ok",
                    size_bytes=size,
                    sha256=digest,
                )
                index_status = self.rescan_storage()
                return HTTPStatus.OK, {"ok": True, "operation": op, "index_status": index_status}
            except Exception as exc:
                op = log_file_operation(
                    self.sqlite_index_path,
                    action,
                    source_rel,
                    target_rel,
                    "failed",
                    f"{type(exc).__name__}:{exc}",
                )
                return HTTPStatus.BAD_REQUEST, {"ok": False, "error": op["detail"], "operation": op}

    def storage_upload(self, directory_relative_path: str, filename: str, data: bytes) -> tuple[int, dict]:
        directory_rel = normalize_storage_relative_path(directory_relative_path)
        clean_name = normalize_storage_relative_path(filename)
        if not clean_name or "/" in clean_name:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "upload_requires_single_filename"}
        target_rel = str(Path(directory_rel) / clean_name).replace("\\", "/") if directory_rel else clean_name
        target = resolve_storage_path(self.personal_root, target_rel, allow_root=False)
        with self.storage_lock:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if _HAS_SNAPSHOT and self.snapshot_store:
                        self.snapshot_store.save_version(target)
                    target.unlink()
                target.write_bytes(data)
                digest = None
                op = log_file_operation(
                    self.sqlite_index_path,
                    "upload",
                    None,
                    target_rel,
                    "ok",
                    size_bytes=len(data),
                    sha256=digest,
                )
                index_status = self.rescan_storage()
                return HTTPStatus.OK, {"ok": True, "file": storage_entry_payload(target, self.personal_root), "operation": op, "index_status": index_status}
            except Exception as exc:
                op = log_file_operation(self.sqlite_index_path, "upload", None, target_rel, "failed", f"{type(exc).__name__}:{exc}")
                return HTTPStatus.BAD_REQUEST, {"ok": False, "error": op["detail"], "operation": op}

    def portal_config_payload(self) -> dict:
        openclaw_health = http_health("openclaw_gateway", self.openclaw_gateway_url + "/health", timeout=2)
        openclaw_model_health = http_health("openclaw_model_gateway", self.openclaw_model_gateway_url + "/health", timeout=2)
        qwen_health = http_health("qwen25_official_route", self.qwen_gateway_url + "/health", timeout=2)
        return {
            "ok": True,
            "official_manager_url": self.official_manager_url,
            "official_manager_configured": bool(self.official_manager_url),
            "openclaw_gateway_url": self.openclaw_gateway_url,
            "openclaw_model_gateway_url": self.openclaw_model_gateway_url,
            "openclaw_model": self.openclaw_model,
            "openclaw_health": openclaw_health,
            "openclaw_model_health": openclaw_model_health,
            "qwen_gateway_url": self.qwen_gateway_url,
            "qwen_model": self.qwen_model,
            "qwen_health": qwen_health,
            "active_copilot_gateway_url": self.qwen_gateway_url,
            "active_copilot_model": self.qwen_model,
            "chat_primary_route": "qwen25_official_primary",
            "features": {
                "official_manager_entry": True,
                "copilot_chat": True,
                "copilot_search": True,
                "copilot_nas_file_control": True,
                "vision_status": True,
                "vision_index": True,
                "vision_search": True,
                "official_s100_vision_route": self.official_vision_status_payload().get("official_route_found", False),
                "storage_upload": True,
                "storage_insights": True,
                "scheduled_organizing_rules": bool(self.schedule_manager),
                "pwa_mobile_entry": True,
                "authorized_media_links": True,
                "video_transcoding": False,
                "thumbnail_service": False,
            },
        }

    def official_vision_status_payload(self) -> dict:
        report = self.latest("official_vision_route_packet.json")
        readiness_report = self.latest("official_route_readiness_gate.json")
        payload = report.get("payload") or {}
        readiness_payload = readiness_report.get("payload") or {}
        readiness_summary = readiness_payload.get("summary") if isinstance(readiness_payload, dict) else {}
        candidates = payload.get("model_candidates") if isinstance(payload, dict) else []
        selected = [
            {
                "capability": item.get("capability"),
                "model": item.get("model"),
                "deployment_status": item.get("deployment_status"),
                "first_release_role": item.get("first_release_role"),
                "board_model_file": item.get("board_model_file"),
            }
            for item in candidates or []
            if isinstance(item, dict) and item.get("selected")
        ]
        evidence = payload.get("evidence") if isinstance(payload, dict) else {}
        image_boxes = int((readiness_summary or {}).get("vision_image_box_count") or (((evidence or {}).get("s100p_yolo_image") or {}).get("log") or {}).get("box_count") or 0)
        video_boxes = int((readiness_summary or {}).get("vision_video_box_count") or (((evidence or {}).get("s100p_video_frame") or {}).get("log") or {}).get("box_count") or 0)
        wrapper_ready = bool((readiness_summary or {}).get("official_ppocr_wrapper_ready"))
        route_ready = readiness_report.get("verdict") == "ready_ai_nas_official_route_readiness_gate"
        return {
            "ok": True,
            "official_route_found": bool(report.get("found")),
            "official_route_verdict": report.get("verdict"),
            "official_route_generated_at": report.get("generated_at"),
            "official_route_path": report.get("path"),
            "official_readiness_found": bool(readiness_report.get("found")),
            "official_readiness_verdict": readiness_report.get("verdict"),
            "official_readiness_generated_at": readiness_report.get("generated_at"),
            "official_readiness_path": readiness_report.get("path"),
            "official_route_ready": route_ready,
            "selected_official_models": selected,
            "s100p_yolo_image_boxes": image_boxes,
            "s100p_video_frame_boxes": video_boxes,
            "official_ppocr_wrapper_ready": wrapper_ready,
            "official_ppocr_hbm_model_info_verified": bool((readiness_summary or {}).get("official_ppocr_hbm_model_info_verified")),
            "warnings": readiness_payload.get("warnings") if isinstance(readiness_payload.get("warnings"), list) else [],
            "risks": payload.get("risks") if isinstance(payload.get("risks"), list) else [],
            "runtime": {
                "image_embedding": image_embedding_runtime_status(),
                "image_caption": vision_caption_runtime_status(),
                "ocr": ocr_engine_status(),
                "vision_product": vision_product_runtime_status(),
            },
            "vision_schema": vision_product_schema_status(self.sqlite_index_path),
            "integration_boundary": (
                "Official S100 vision readiness is verified for YOLO image/video-frame routing"
                + (" and PP-OCR wrapper evidence" if wrapper_ready else "")
                + "; "
                "the portal now prefers LLM image captions for semantic photo search, with "
                "local_visual_embedding_v1 retained only as fallback/plumbing evidence."
            ),
        }

    def _indexed_records(self, record_type: str | None = None, limit: int = 500) -> list[dict]:
        limit = max(1, min(int(limit or 500), 5000))
        con = open_index_db(self.sqlite_index_path)
        try:
            if record_type:
                rows = con.execute(
                    "SELECT * FROM records WHERE type = ? ORDER BY relative_path LIMIT ?",
                    (record_type, limit),
                ).fetchall()
            else:
                rows = con.execute("SELECT * FROM records ORDER BY relative_path LIMIT ?", (limit,)).fetchall()
            return [_record_from_sqlite_row(row) for row in rows]
        finally:
            con.close()

    def _indexed_photo_records(self, limit: int = 500) -> list[dict]:
        limit = max(1, min(int(limit or 500), 5000))
        photo_exts = tuple(sorted(PHOTO_EXTS))
        placeholders = ",".join("?" for _ in photo_exts)
        con = open_index_db(self.sqlite_index_path)
        try:
            rows = con.execute(
                f"""
                SELECT *
                FROM records
                WHERE lower(extension) IN ({placeholders})
                ORDER BY relative_path
                LIMIT ?
                """,
                (*photo_exts, limit),
            ).fetchall()
            return [_record_from_sqlite_row(row) for row in rows]
        finally:
            con.close()

    def vision_index_payload(self, limit: int = 500, include_ocr: bool = True, include_caption: bool = True) -> dict:
        limit = max(1, min(int(limit or 500), 5000))
        index_status = self.rescan_storage()
        caption_update = ensure_image_captions_for_photos(self.sqlite_index_path, limit=limit) if include_caption else {
            "attempted": 0,
            "completed": 0,
            "failed": 0,
            "blocked": 0,
            "runtime": vision_caption_runtime_status(),
        }
        embedding_update = ensure_image_embeddings_for_photos(self.sqlite_index_path, limit=limit)
        records = self._indexed_photo_records(limit=limit)
        product_runtime = vision_product_runtime_status()
        visual_state_update = ensure_photo_visual_states(self.sqlite_index_path, records, runtime=product_runtime)
        ocr_updates: list[dict] = []
        product_embedding_updates: list[dict] = []
        product_region_updates: list[dict] = []
        if include_ocr:
            for record in records:
                if not ocr_candidate_record(record, include_images=True):
                    continue
                result = run_product_ocr_for_record(record)
                if str(result.get("status") or "").startswith("blocked_"):
                    result = run_ocr_for_record(record)
                upsert_ocr_result(self.sqlite_index_path, result)
                product_evidence = upsert_product_ocr_evidence(self.sqlite_index_path, result)
                ocr_updates.append(
                    {
                        "relative_path": result.get("relative_path"),
                        "status": result.get("status"),
                        "engine": result.get("engine"),
                        "error": result.get("error"),
                        "product_evidence": product_evidence,
                    }
                )
        for record in records:
            product_embedding = run_product_image_embedding_for_record(record)
            embedding_evidence = upsert_product_image_embedding(self.sqlite_index_path, product_embedding)
            if not str(product_embedding.get("status") or "").startswith("blocked_"):
                product_embedding_updates.append(
                    {
                        "relative_path": product_embedding.get("relative_path"),
                        "status": product_embedding.get("status"),
                        "model_id": product_embedding.get("model_id"),
                        "dim": product_embedding.get("dim"),
                        "error": product_embedding.get("error"),
                        "product_evidence": embedding_evidence,
                    }
                )
            product_region = run_product_region_analysis_for_record(record)
            region_evidence = upsert_product_region_evidence(self.sqlite_index_path, product_region)
            if not str(product_region.get("status") or "").startswith("blocked_"):
                product_region_updates.append(
                    {
                        "relative_path": product_region.get("relative_path"),
                        "status": product_region.get("status"),
                        "model_id": product_region.get("model_id"),
                        "regions": len(product_region.get("regions") or []),
                        "error": product_region.get("error"),
                        "product_evidence": region_evidence,
                    }
                )
        if ocr_updates or product_embedding_updates or product_region_updates:
            visual_state_update = ensure_photo_visual_states(self.sqlite_index_path, records, runtime=product_runtime)
        return {
            "ok": True,
            "indexed_at": iso_timestamp(),
            "index_status": index_status,
            "image_caption_update": caption_update,
            "image_caption_summary": image_caption_summary(self.sqlite_index_path),
            "image_embedding_update": embedding_update,
            "image_embedding_summary": image_embedding_summary(self.sqlite_index_path),
            "product_embedding_update": {
                "attempted": len(product_embedding_updates),
                "items": product_embedding_updates[:20],
                "summary": product_embedding_summary(self.sqlite_index_path),
            },
            "product_region_update": {
                "attempted": len(product_region_updates),
                "items": product_region_updates[:20],
                "summary": product_region_summary(self.sqlite_index_path),
            },
            "ocr_update": {
                "attempted": len(ocr_updates),
                "items": ocr_updates[:20],
                "summary": ocr_results_summary(self.sqlite_index_path),
            },
            "visual_state_update": visual_state_update,
            "visual_state_summary": photo_visual_state_summary(self.sqlite_index_path),
            "vision_status": self.official_vision_status_payload(),
        }

    def _vision_result_payload(self, match: dict) -> dict:
        rel = str(match.get("relative_path") or "").strip().strip("/")
        target = resolve_storage_path(self.personal_root, rel, allow_root=False)
        stat = target.stat() if target.exists() else None
        encoded = quote(rel, safe="")
        download_url = f"/api/storage/download?path={encoded}"
        preview_url = f"/api/storage/download?path={encoded}&preview=1"
        return {
            "name": target.name if target.name else Path(rel).name,
            "relative_path": rel,
            "type": "image",
            "category": match.get("type") or "Photos",
            "extension": target.suffix.lower(),
            "mime_type": mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            "size_bytes": stat.st_size if stat else 0,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stat.st_mtime)) if stat else "",
            "download_url": download_url,
            "preview_url": preview_url,
            "open_url": preview_url,
            "score": match.get("score"),
            "confidence": match.get("confidence"),
            "matched_intents": match.get("matched_intents") or [],
            "missing_intents": match.get("missing_intents") or [],
            "reasons": match.get("reasons") or [],
            "evidence": match.get("evidence") or "",
            "summary": match.get("summary") or "",
            "ocr": match.get("ocr") or {},
            "image_caption": match.get("image_caption") or {},
            "image_embedding": match.get("image_embedding") or {},
            "visual_state": match.get("visual_state") or {},
            "degraded": bool(match.get("degraded")),
            "degradation": match.get("degradation") or [],
            "evidence_items": match.get("evidence_items") or [],
            "evidence_chips": match.get("evidence_chips") or [],
            "query_plan": match.get("query_plan") or {},
            "confidence_kind": match.get("confidence_kind") or "legacy_score",
            "privacy": match.get("privacy") or {},
            "source": "vision_semantic_search",
            "visual_source": match.get("source") or "sqlite_photo_llm_caption_semantic_search",
        }

    def vision_search_payload(self, query: str, limit: int = 10, user: dict | None = None, auto_index: bool = False) -> dict:
        query = str(query or "").strip()
        limit = max(1, min(int(limit or 10), 50))
        index_update = None
        if auto_index:
            index_update = self.vision_index_payload(limit=max(limit, 50), include_ocr=True)
        search_pool_limit = max(limit * 3, 50)
        product_search = search_product_visual_index(self.sqlite_index_path, query, limit=search_pool_limit)
        matches = product_search.get("matches") or []
        authorized_results = []
        for match in matches:
            rel = str(match.get("relative_path") or "").strip().strip("/")
            if not rel:
                continue
            if not self._user_can_read(user, rel):
                continue
            authorized_results.append(self._vision_result_payload(match))
        results = authorized_results[:limit]
        return {
            "ok": True,
            "query": query,
            "limit": limit,
            "display_limit": limit,
            "total_found": len(authorized_results),
            "displayed_count": len(results),
            "results": results,
            "query_plan": product_search.get("query_plan") or {},
            "degraded": bool(product_search.get("degraded")),
            "degradation": product_search.get("degradation") or [],
            "search_runtime": product_search.get("search_runtime"),
            "index_update": index_update,
            "vision_status": self.official_vision_status_payload(),
        }

    def _media_kind(self, path: Path) -> str:
        ext = path.suffix.lower()
        if ext in COPILOT_IMAGE_EXTS:
            return "image"
        if ext in COPILOT_VIDEO_EXTS:
            return "video"
        return "file"

    def _relative_media_path(self, path_value: str | None) -> str | None:
        if not path_value:
            return None
        root = self.personal_root.resolve(strict=False)
        try:
            return Path(path_value).resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            return None

    def _external_player_links(self, movie: dict, relative_path: str) -> list[dict]:
        title = str(movie.get("title") or movie.get("name") or "").strip()
        query = quote(title, safe="")
        encoded_path = quote(relative_path, safe="")
        links = [
            {
                "name": "OpenClaw direct preview",
                "kind": "direct_file",
                "configured": True,
                "url": f"/api/storage/download?path={encoded_path}&preview=1",
            }
        ]
        for env_name, label, path_tpl in [
            ("OPENCLAW_JELLYFIN_URL", "Jellyfin search", "/web/index.html#!/search.html?query={query}"),
            ("OPENCLAW_PLEX_URL", "Plex search", "/web/index.html#!/search?query={query}"),
            ("OPENCLAW_VENDOR_PLAYER_URL", "Vendor player", "?path={path}"),
        ]:
            base = os.environ.get(env_name, "").rstrip("/")
            links.append(
                {
                    "name": label,
                    "kind": "external_player",
                    "configured": bool(base),
                    "url": (base + path_tpl.format(query=query, path=encoded_path)) if base else "",
                    "config_env": env_name,
                }
            )
        return links

    def media_movie_payloads(self, movies: list[dict]) -> list[dict]:
        payloads: list[dict] = []
        for movie in movies:
            rel = self._relative_media_path(movie.get("file_path"))
            if not rel:
                continue
            encoded = quote(rel, safe="")
            poster_rel = self._relative_media_path(movie.get("poster_path"))
            item = dict(movie)
            item.update(
                {
                    "relative_path": rel,
                    "open_url": f"/api/storage/download?path={encoded}&preview=1",
                    "download_url": f"/api/storage/download?path={encoded}",
                    "poster_relative_path": poster_rel,
                    "poster_url": f"/api/storage/download?path={quote(poster_rel, safe='')}&preview=1" if poster_rel else "",
                    "player_links": self._external_player_links(movie, rel),
                    "transcoding_enabled": False,
                    "transcoding_policy": "no realtime transcoding in first release; use direct preview or configured external player",
                }
            )
            payloads.append(item)
        return payloads

    def _user_can_read(self, user: dict | None, relative_path: str) -> bool:
        store = self.identity_store
        if not store:
            return True
        if not user:
            return False
        if user.get("role") == "admin":
            return True
        return store.check_acl(str(user.get("username") or ""), relative_path, "read")

    def _user_can_write(self, user: dict | None, relative_path: str) -> bool:
        store = self.identity_store
        if not store:
            return True
        if not user:
            return False
        if user.get("role") == "admin":
            return True
        return store.check_acl(str(user.get("username") or ""), relative_path, "write")

    def _target_parent_path(self, relative_path: str) -> str:
        rel = normalize_storage_relative_path(relative_path)
        parent = Path(rel).parent.as_posix()
        return "" if parent == "." else parent

    def _filter_entries_for_identity_user(self, entries: list[dict], relative_path: str, user: dict | None) -> list[dict]:
        store = self.identity_store
        if not store or not user or user.get("role") == "admin":
            return entries
        username = str(user.get("username") or "")
        visible = set(store.get_visible_paths(username))
        filtered = []
        for entry in entries:
            rel = entry.get("relative_path") or ""
            if store.check_acl(username, rel, "read") or rel in visible or any(path.startswith(rel + "/") for path in visible):
                filtered.append(entry)
        return filtered

    def _extract_quoted_paths(self, message: str) -> list[str]:
        return [
            normalize_storage_relative_path(match.group(1))
            for match in re.finditer(r"[`\"']([^`\"']+)[`\"']", message)
            if normalize_storage_relative_path(match.group(1))
        ]

    def _parse_copilot_file_action(self, message: str) -> dict | None:
        raw = str(message or "").strip()
        lower = raw.lower()
        quoted = self._extract_quoted_paths(raw)
        if any(term in lower for term in ("删除", "delete", "移除", "清空")):
            target = quoted[0] if quoted else self._path_after_keywords(raw, ("删除", "delete", "移除"))
            if target:
                return {"operation": "delete", "path": target, "requires_confirmation": True}
        if len(quoted) >= 2:
            if any(term in lower for term in ("copy", "复制")):
                return {"operation": "copy", "source": quoted[0], "target": quoted[1]}
            if any(term in lower for term in ("move", "移动", "移到")):
                return {"operation": "move", "source": quoted[0], "target": quoted[1]}
            if any(term in lower for term in ("rename", "重命名", "改名")):
                return {"operation": "rename", "source": quoted[0], "new_name": Path(quoted[1]).name}
        for op, words in [
            ("rename", ("重命名为", "改名为", "rename to")),
            ("move", ("移动到", "移到", "move to")),
            ("copy", ("复制到", "copy to")),
        ]:
            for word in words:
                if word not in lower and word not in raw:
                    continue
                if len(quoted) >= 2:
                    source, target = quoted[0], quoted[1]
                else:
                    pattern = re.escape(word)
                    parts = re.split(pattern, raw, maxsplit=1, flags=re.IGNORECASE)
                    if len(parts) != 2:
                        continue
                    source = self._clean_action_path(parts[0])
                    target = self._clean_action_path(parts[1])
                if source and target:
                    payload = {"operation": op, "source": source}
                    if op == "rename":
                        payload["new_name"] = Path(target).name
                    else:
                        payload["target"] = target
                    return payload
        if any(term in lower for term in ("列出", "查看目录", "打开目录", "list", "ls ")) and not any(term in lower for term in ("图片", "照片", "image", "photo")):
            path = quoted[0] if quoted else self._path_after_keywords(raw, ("列出", "查看目录", "打开目录", "list", "ls"))
            return {"operation": "list", "path": path or ""}
        return None

    def _path_after_keywords(self, message: str, keywords: tuple[str, ...]) -> str:
        for keyword in keywords:
            idx = message.lower().find(keyword.lower())
            if idx >= 0:
                return self._clean_action_path(message[idx + len(keyword):])
        return ""

    def _clean_action_path(self, value: str) -> str:
        cleaned = re.sub(r"^(把|将|请|帮我|帮我把|please)\s*", "", str(value or "").strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*(这个文件|这个目录|文件|目录|文件夹)$", "", cleaned).strip()
        cleaned = cleaned.strip("：:，,。.;； ")
        if not cleaned:
            return ""
        parts = cleaned.split()
        candidate = parts[-1] if len(parts) > 1 and "/" not in parts[0] else parts[0]
        return normalize_storage_relative_path(candidate)

    def _action_open_url(self, relative_path: str) -> str:
        return f"/api/storage/download?path={quote(relative_path, safe='')}&preview=1"

    def execute_copilot_file_action(self, message: str, user: dict | None = None, limit: int = 20) -> dict | None:
        action = self._parse_copilot_file_action(message)
        if not action:
            return None
        operation = action.get("operation")
        try:
            if operation == "list":
                rel = normalize_storage_relative_path(action.get("path") or "")
                if rel and not self._user_can_read(user, rel):
                    return {"ok": False, "operation": operation, "status": "permission_denied", "error": "read_permission_required", "path": rel}
                payload = self.storage_list_payload(rel)
                entries = self._filter_entries_for_identity_user(payload.get("entries") or [], rel, user)
                return {
                    "ok": True,
                    "operation": operation,
                    "status": "completed",
                    "path": rel,
                    "entries": entries[: max(1, min(int(limit or 20), 50))],
                    "message": f"已列出 {rel or '根目录'}。",
                }
            if operation == "rename":
                source = normalize_storage_relative_path(action.get("source") or "")
                new_name = normalize_storage_relative_path(action.get("new_name") or "")
                target_parent = self._target_parent_path(source)
                if not self._user_can_write(user, source) or not self._user_can_write(user, target_parent):
                    return {"ok": False, "operation": operation, "status": "permission_denied", "error": "write_permission_required", "source": source}
                status, result = self.storage_rename(source, new_name)
                return {"ok": status == HTTPStatus.OK and result.get("ok"), "operation": operation, "status": "completed" if result.get("ok") else "failed", "source": source, "target": result.get("operation", {}).get("target_path"), "result": result}
            if operation == "move":
                source = normalize_storage_relative_path(action.get("source") or "")
                target = normalize_storage_relative_path(action.get("target") or "")
                if not self._user_can_write(user, source) or not self._user_can_write(user, self._target_parent_path(target)):
                    return {"ok": False, "operation": operation, "status": "permission_denied", "error": "write_permission_required", "source": source, "target": target}
                status, result = self.storage_move(source, target)
                return {"ok": status == HTTPStatus.OK and result.get("ok"), "operation": operation, "status": "completed" if result.get("ok") else "failed", "source": source, "target": target, "result": result}
            if operation == "copy":
                source = normalize_storage_relative_path(action.get("source") or "")
                target = normalize_storage_relative_path(action.get("target") or "")
                if not self._user_can_read(user, source) or not self._user_can_write(user, self._target_parent_path(target)):
                    return {"ok": False, "operation": operation, "status": "permission_denied", "error": "read_and_target_write_permission_required", "source": source, "target": target}
                status, result = self.storage_copy(source, target)
                return {"ok": status == HTTPStatus.OK and result.get("ok"), "operation": operation, "status": "completed" if result.get("ok") else "failed", "source": source, "target": target, "result": result}
            if operation == "delete":
                rel = normalize_storage_relative_path(action.get("path") or "")
                return {
                    "ok": False,
                    "operation": operation,
                    "status": "confirmation_required",
                    "path": rel,
                    "requires_confirmation": True,
                    "message": "删除属于危险操作，聊天里不会直接执行。请在文件管理器或审批动作里确认后执行。",
                }
        except Exception as exc:
            return {"ok": False, "operation": operation, "status": "failed", "error": f"{type(exc).__name__}:{exc}"}
        return None

    def copilot_search(self, query: str, requested_type: str = "file", limit: int = 20, user: dict | None = None) -> list[dict]:
        requested = (requested_type or "file").lower()
        if requested not in {"image", "video", "file", "all"}:
            requested = "file"
        limit = max(1, min(int(limit or 20), 100))
        root = self.personal_root.resolve(strict=False)
        query_terms = [part.lower() for part in re.split(r"\s+", query.strip()) if part.strip()]
        query_lower = query.lower()
        if requested in {"all", "file"}:
            if any(term in query_lower for term in ("image", "images", "photo", "photos", "picture", "图片", "照片", "相册")):
                requested = "image"
            elif any(term in query_lower for term in ("video", "videos", "movie", "movies", "视频", "录像", "影片")):
                requested = "video"
        if requested in {"image", "video"}:
            broad_terms = ("image", "images", "photo", "photos", "picture", "video", "videos", "movie", "movies", "图片", "照片", "相册", "视频", "录像", "影片", "帮我找", "查找", "筛选")
            query_terms = [term for term in query_terms if not any(broad in term for broad in broad_terms)]
        image_terms_ascii = ("image", "images", "photo", "photos", "picture", "\u56fe\u7247", "\u7167\u7247", "\u76f8\u518c")
        video_terms_ascii = ("video", "videos", "movie", "movies", "\u89c6\u9891", "\u5f55\u50cf", "\u5f71\u7247")
        if requested == "all":
            if any(term in query_lower for term in image_terms_ascii):
                requested = "image"
            elif any(term in query_lower for term in video_terms_ascii):
                requested = "video"
        if requested in {"image", "video"}:
            broad_terms_ascii = image_terms_ascii + video_terms_ascii + ("\u5e2e\u6211\u627e", "\u67e5\u627e", "\u7b5b\u9009")
            query_terms = [term for term in query_terms if not any(broad in term for broad in broad_terms_ascii)]
        results: list[dict] = []
        if not root.exists():
            return results
        for path in root.rglob("*"):
            if len(results) >= limit:
                break
            if not path.is_file():
                continue
            try:
                rel = path.resolve(strict=False).relative_to(root).as_posix()
            except ValueError:
                continue
            top_dir = rel.split("/", 1)[0]
            if top_dir not in SCAN_DIRS:
                continue
            kind = self._media_kind(path)
            if requested in {"image", "video"} and kind != requested:
                continue
            if requested == "file" and kind in {"image", "video"} and any(term in {"image", "images", "photo", "photos", "picture", "video", "videos", "图片", "照片", "视频"} for term in query_terms):
                continue
            haystack = f"{path.name} {rel} {path.suffix}".lower()
            if query_terms and not all(term in haystack for term in query_terms):
                loose_terms = [term for term in query_terms if term not in {"image", "images", "photo", "photos", "picture", "video", "videos", "file", "files", "图片", "照片", "视频", "文件"}]
                if loose_terms and not any(term in haystack for term in loose_terms):
                    continue
            if not self._user_can_read(user, rel):
                continue
            stat = path.stat()
            encoded = quote(rel, safe="")
            download_url = f"/api/storage/download?path={encoded}"
            preview_url = f"/api/storage/download?path={encoded}&preview=1"
            results.append(
                {
                    "name": path.name,
                    "relative_path": rel,
                    "type": kind,
                    "extension": path.suffix.lower(),
                    "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "size_bytes": stat.st_size,
                    "mtime": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stat.st_mtime)),
                    "download_url": download_url,
                    "preview_url": preview_url if kind in {"image", "video"} else download_url,
                    "open_url": preview_url if kind in {"image", "video"} else download_url,
                }
            )
        if requested == "file":
            results = [item for item in results if item.get("type") == "file"]
        elif requested in {"image", "video"}:
            results = [item for item in results if item.get("type") == requested]
        return results

    def copilot_chat(self, message: str, messages: list[dict] | None = None, search_type: str = "all", limit: int = 8, user: dict | None = None) -> dict:
        results = self.copilot_search(message, search_type, limit, user=user)
        if not results and search_type != "all":
            results = self.copilot_search(message, "all", limit, user=user)
        if not results:
            lower = message.lower()
            if any(term in lower for term in ("image", "images", "photo", "photos", "picture", "\u56fe\u7247", "\u7167\u7247", "\u76f8\u518c")):
                results = self.copilot_search("", "image", limit, user=user)
            elif any(term in lower for term in ("video", "videos", "movie", "movies", "\u89c6\u9891", "\u5f55\u50cf", "\u5f71\u7247")):
                results = self.copilot_search("", "video", limit, user=user)
        if not results and search_type == "all":
            results = self.copilot_search("", "image", limit, user=user)
            if len(results) < limit:
                results.extend(self.copilot_search("", "video", limit - len(results), user=user))
            if len(results) < limit:
                results.extend(self.copilot_search("", "file", limit - len(results), user=user))
            if any(term in lower for term in ("image", "images", "photo", "photos", "picture", "图片", "照片", "相册")):
                results = self.copilot_search("", "image", limit, user=user)
            elif any(term in lower for term in ("video", "videos", "movie", "movies", "视频", "录像", "影片")):
                results = self.copilot_search("", "video", limit, user=user)
        outbound_messages = messages if isinstance(messages, list) and messages else [
            {
                "role": "system",
                "content": (
                    "You are OpenClaw NAS Copilot. Answer briefly in Chinese when the user writes Chinese. "
                    "Do not invent file links. The server will attach authorized NAS search results separately."
                ),
            },
            {"role": "user", "content": message},
        ]
        primary_payload = {"model": self.qwen_model, "messages": outbound_messages, "temperature": 0.2, "stream": False}
        response = post_json(self.qwen_gateway_url + "/v1/chat/completions", primary_payload, timeout=60)
        upstream_name = "qwen25_official_primary"
        model_name = self.qwen_model
        if not response.get("ok"):
            fallback_payload = {"model": self.openclaw_model, "messages": outbound_messages, "temperature": 0.2, "stream": False}
            fallback = post_json(self.openclaw_model_gateway_url + "/v1/chat/completions", fallback_payload, timeout=10)
            if fallback.get("ok"):
                response = fallback
                upstream_name = "openclaw_model_fallback"
                model_name = self.openclaw_model
        if not response.get("ok"):
            return {
                "ok": False,
                "error": "openclaw_route_unavailable",
                "detail": response.get("error") or response.get("payload"),
                "model": model_name,
                "results": results,
            }
        payload = response.get("payload") or {}
        choices = payload.get("choices") or []
        text = ""
        if choices:
            msg = choices[0].get("message") or {}
            text = str(msg.get("content") or "")
        return {
            "ok": True,
            "model": payload.get("model") or model_name,
            "message": text,
            "results": results,
            "upstream": {"name": upstream_name, "status": response.get("status"), "elapsed_ms": response.get("elapsed_ms")},
        }

    def _looks_like_visual_query(self, message: str) -> bool:
        lower = str(message or "").lower()
        return any(term in lower for term in IMAGE_QUERY_TERMS) or any(
            term in lower for term in ("ocr", "识别", "看图", "图里", "画面", "截图", "白底", "车牌", "发票")
        )

    def _looks_like_copilot_search_query(self, message: str) -> bool:
        lower = str(message or "").lower()
        if not lower:
            return False
        if any(term in lower for term in NAS_DOMAIN_QUERY_TERMS):
            return True
        has_action = any(term in lower for term in NAS_ACTION_QUERY_TERMS)
        has_path_hint = bool(re.search(r"[`\"']|[/\\]|\.[a-z0-9]{2,6}\b", lower))
        return has_action and has_path_hint

    def _should_attach_copilot_results(self, message: str, search_type: str, nas_action: dict | None = None) -> bool:
        requested = (search_type or "all").lower()
        if nas_action:
            return True
        if requested == "none":
            return False
        if requested in {"image", "video", "file"}:
            return True
        return self._looks_like_copilot_search_query(message)

    def _clean_query_terms(self, query: str) -> list[str]:
        terms = [part.lower() for part in re.split(r"\s+", str(query or "").strip()) if part.strip()]
        return [term for term in terms if not any(broad.lower() in term for broad in BROAD_SEARCH_TERMS)]

    def copilot_search(self, query: str, requested_type: str = "file", limit: int = 20, user: dict | None = None) -> list[dict]:
        requested = (requested_type or "file").lower()
        if requested not in {"image", "video", "file", "all"}:
            requested = "file"
        limit = max(1, min(int(limit or 20), 100))
        query_lower = str(query or "").lower()
        if requested == "all":
            if any(term in query_lower for term in IMAGE_QUERY_TERMS):
                requested = "image"
            elif any(term in query_lower for term in VIDEO_QUERY_TERMS):
                requested = "video"
        query_terms = self._clean_query_terms(query) if requested in {"image", "video"} else [
            part.lower() for part in re.split(r"\s+", str(query or "").strip()) if part.strip()
        ]
        results: list[dict] = []
        root = self.personal_root.resolve(strict=False)
        if not root.exists():
            return results
        for path in root.rglob("*"):
            if len(results) >= limit:
                break
            if not path.is_file():
                continue
            try:
                rel = path.resolve(strict=False).relative_to(root).as_posix()
            except ValueError:
                continue
            top_dir = rel.split("/", 1)[0]
            if top_dir not in SCAN_DIRS:
                continue
            kind = self._media_kind(path)
            if requested in {"image", "video"} and kind != requested:
                continue
            if requested == "file" and kind in {"image", "video"}:
                continue
            haystack = f"{path.name} {rel} {path.suffix}".lower()
            if query_terms:
                loose_terms = [
                    term for term in query_terms
                    if term not in {"image", "images", "photo", "photos", "picture", "video", "videos", "file", "files"}
                ]
                if loose_terms and not any(term in haystack for term in loose_terms):
                    continue
            if not self._user_can_read(user, rel):
                continue
            stat = path.stat()
            encoded = quote(rel, safe="")
            download_url = f"/api/storage/download?path={encoded}"
            preview_url = f"/api/storage/download?path={encoded}&preview=1"
            results.append(
                {
                    "name": path.name,
                    "relative_path": rel,
                    "type": kind,
                    "extension": path.suffix.lower(),
                    "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "size_bytes": stat.st_size,
                    "mtime": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stat.st_mtime)),
                    "download_url": download_url,
                    "preview_url": preview_url if kind in {"image", "video"} else download_url,
                    "open_url": preview_url if kind in {"image", "video"} else download_url,
                    "source": "storage_filename_search",
                }
            )
        if requested == "file":
            results = [item for item in results if item.get("type") == "file"]
        elif requested in {"image", "video"}:
            results = [item for item in results if item.get("type") == requested]
        return results

    def copilot_chat(self, message: str, messages: list[dict] | None = None, search_type: str = "all", limit: int = 8, user: dict | None = None) -> dict:
        request_limit = max(1, min(int(limit or 8), 20))
        attachment_limit = min(request_limit, 3)
        requested_type = (search_type or "all").lower()
        nas_action = self.execute_copilot_file_action(message, user=user, limit=request_limit)
        should_attach_results = self._should_attach_copilot_results(message, requested_type, nas_action)
        visual_results: list[dict] = []
        results: list[dict] = []
        if should_attach_results and (requested_type == "image" or self._looks_like_visual_query(message)):
            try:
                visual_payload = self.vision_search_payload(message, limit=attachment_limit, user=user, auto_index=True)
                visual_results = visual_payload.get("results") or []
            except Exception as exc:
                visual_results = []
                visual_payload = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
        else:
            visual_payload = None
        if should_attach_results:
            effective_type = requested_type if requested_type in {"all", "image", "video", "file"} else "all"
            results = self.copilot_search(message, effective_type, attachment_limit, user=user)
            results = self._merge_result_lists(visual_results, results, limit=attachment_limit)
        lower = message.lower()
        if should_attach_results and requested_type == "all":
            if any(term in lower for term in FILE_QUERY_TERMS):
                results = self._merge_result_lists(self.copilot_search(message, "file", attachment_limit, user=user), results, limit=attachment_limit)
            if any(term in lower for term in VIDEO_QUERY_TERMS):
                results = self._merge_result_lists(self.copilot_search(message, "video", attachment_limit, user=user), results, limit=attachment_limit)
            if any(term in lower for term in IMAGE_QUERY_TERMS) and not any((item.get("type") == "image") for item in results):
                results = self._merge_result_lists(results, self.copilot_search(message, "image", attachment_limit, user=user), limit=attachment_limit)
        if should_attach_results and not results and requested_type not in {"all", "none"}:
            results = self.copilot_search(message, "all", attachment_limit, user=user)
        if should_attach_results and not results:
            if any(term in lower for term in IMAGE_QUERY_TERMS):
                results = self.copilot_search("", "image", attachment_limit, user=user)
            elif any(term in lower for term in VIDEO_QUERY_TERMS):
                results = self.copilot_search("", "video", attachment_limit, user=user)
        outbound_messages = messages if isinstance(messages, list) and messages else [
            {
                "role": "system",
                "content": (
                    "You are OpenClaw NAS Copilot. Answer briefly in Chinese when the user writes Chinese. "
                    "Do not invent file links. The server attaches authorized NAS search and vision-search results separately."
                ),
            },
            {"role": "user", "content": message},
        ]
        primary_payload = {"model": self.qwen_model, "messages": outbound_messages, "temperature": 0.2, "stream": False}
        response = post_json(self.qwen_gateway_url + "/v1/chat/completions", primary_payload, timeout=60)
        upstream_name = "qwen25_official_primary"
        model_name = self.qwen_model
        if not response.get("ok"):
            fallback_payload = {"model": self.openclaw_model, "messages": outbound_messages, "temperature": 0.2, "stream": False}
            fallback = post_json(self.openclaw_model_gateway_url + "/v1/chat/completions", fallback_payload, timeout=10)
            if fallback.get("ok"):
                response = fallback
                upstream_name = "openclaw_model_fallback"
                model_name = self.openclaw_model
        if not response.get("ok"):
            return {
                "ok": False,
                "error": "openclaw_route_unavailable",
                "detail": response.get("error") or response.get("payload"),
                "model": model_name,
                "results": results,
                "vision_results": visual_results,
                "vision_search": visual_payload,
                "nas_action": nas_action,
                "attachments_enabled": should_attach_results,
            }
        payload = response.get("payload") or {}
        choices = payload.get("choices") or []
        text = ""
        if choices:
            msg = choices[0].get("message") or {}
            text = str(msg.get("content") or "")
        if visual_results and ("不能" in text or "无法" in text or "不会" in text or "sorry" in text.lower()):
            text = "我已经按你的描述调用 NAS 视觉搜索，下面是授权可见的候选图片和证据。"
        if nas_action:
            if nas_action.get("status") == "completed":
                text = f"NAS action completed: {nas_action.get('operation')}"
            elif nas_action.get("status") == "confirmation_required":
                text = "This NAS action requires confirmation before execution."
            elif nas_action.get("status") == "permission_denied":
                text = "NAS action was not executed because this account lacks the required permission."
            elif nas_action.get("status") == "failed":
                text = f"NAS action failed: {nas_action.get('error') or 'unknown_error'}"
        return {
            "ok": True,
            "model": payload.get("model") or model_name,
            "message": text,
            "results": results,
            "vision_results": visual_results,
            "vision_search": visual_payload,
            "nas_action": nas_action,
            "attachments_enabled": should_attach_results,
            "upstream": {"name": upstream_name, "status": response.get("status"), "elapsed_ms": response.get("elapsed_ms")},
        }

    def _merge_result_lists(self, first: list[dict], second: list[dict], limit: int = 20) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for item in [*(first or []), *(second or [])]:
            key = str(item.get("relative_path") or item.get("open_url") or item.get("name") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                break
        return out

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
        dream_product_report = self.latest("dream7b_product_decision_packet.json")
        dream_product_payload = dream_product_report.get("payload") or {}
        dream_product_first_response = dream_product_payload.get("first_response") or {}
        dream_first_response_slo = (
            dream_product_payload.get("first_response_slo_tier_guard") or {}
        )
        dream_first_response_warning_triage = (
            dream_product_payload.get("first_response_warning_triage") or {}
        )
        dream_slo_limited_evidence_triage = (
            dream_product_payload.get("slo_limited_evidence_triage") or {}
        )
        dream_product_evidence = dream_product_payload.get("product_evidence") or {}
        dream_product_decision = dream_product_payload.get("decision") or {}
        dream_runtime_gate = dream_product_payload.get("runtime_experiment_gate") or {}
        dream_runtime_command_guard = dream_product_payload.get("runtime_command_guard") or {}
        dream_segment_drag = dream_product_payload.get("segment_drag_breakdown") or {}
        dream_segment_stability = dream_product_payload.get("segment_stability_audit") or {}
        dream_group_order = dream_product_payload.get("group_order_candidates") or {}
        dream_group_partition = dream_product_payload.get("group_partition_planner") or {}
        dream_group_inner_order_value = (
            dream_product_payload.get("group_inner_order_value_audit") or {}
        )
        dream_segment_group_schedule = (
            dream_product_payload.get("segment_group_schedule_scorecard") or {}
        )
        dream_group_switch = dream_product_payload.get("group_switch_accounting") or {}
        dream_scheduler = dream_product_payload.get("scheduler_overhead_budget") or {}
        dream_instrumentation = dream_product_payload.get("runtime_instrumentation") or {}
        dream_hbm_accounting = (
            dream_product_payload.get("hbm_load_accounting_contract") or {}
        )
        dream_bottleneck_closure = (
            dream_product_payload.get("bottleneck_closure_model") or {}
        )
        dream_post_instrumentation = (
            dream_product_payload.get("post_instrumentation_telemetry_gate") or {}
        )
        dream_post_overhead = (
            dream_product_payload.get("post_instrumentation_overhead_analysis") or {}
        )
        dream_post_segment = (
            dream_product_payload.get("post_instrumentation_segment_attribution") or {}
        )
        dream_hidden_buffer = (
            dream_product_payload.get("hidden_buffer_reuse_decision") or {}
        )
        dream_queue_health = dream_product_payload.get("queue_health_snapshot") or {}
        dream_workstream_overlap = dream_product_payload.get("workstream_overlap_audit") or {}
        dream_tuning_matrix = dream_product_payload.get("tuning_decision_matrix") or {}
        dream_final_logits_leverage = (
            dream_product_payload.get("final_logits_leverage_model") or {}
        )
        dream_last_token = dream_product_payload.get("last_token_candidate") or {}
        dream_last_token_gate = dream_product_payload.get("last_token_experiment_gate") or {}
        dream_last_token_validation_plan = (
            dream_product_payload.get("last_token_runtime_validation_plan") or {}
        )
        dream_last_token_validation_compare = (
            dream_product_payload.get("last_token_validation_compare") or {}
        )
        dream_compile_capacity = dream_product_payload.get("compile_capacity") or {}
        dream_compile_command_guard = dream_product_payload.get("compile_command_guard") or {}
        dream_next_action_pack = dream_product_payload.get("next_action_admission_pack") or {}
        dream_nas_inventory = dream_product_payload.get("true_batch_nas_inventory") or {}
        dream_refactor_backlog = dream_product_payload.get("runtime_refactor_backlog") or {}
        dream_refactor_source = dream_product_payload.get("runtime_refactor_source_contract") or {}
        dream_refactor_admission = (
            dream_product_payload.get("runtime_refactor_admission_contract") or {}
        )
        dream_runtime_source_map = (
            dream_product_payload.get("runtime_source_implementation_map") or {}
        )
        dream_fast_report = self.latest("dream7b_fast_path_regression.json")
        dream_fast_payload = dream_fast_report.get("payload") or {}
        dream_fast_cases = {str(case.get("id")): case for case in dream_fast_payload.get("cases") or []}
        quick_ready_case = dream_fast_cases.get("quick_ready") or {}
        quick_ready_meta = quick_ready_case.get("dream7b_candidate") or {}
        localized_status_case = dream_fast_cases.get("chinese_short") or {}
        localized_status_meta = localized_status_case.get("dream7b_candidate") or {}
        dream_guardrail_report = self.latest("dream7b_product_guardrail_snapshot.json")
        dream_guardrail_payload = dream_guardrail_report.get("payload") or {}
        dream_guardrail = dream_guardrail_payload.get("guardrail") or {}
        dream_status_contract = dream_guardrail_payload.get("default_status_contract") or {}
        dream_rollback_contract = dream_guardrail_payload.get("default_rollback_contract") or {}
        dream_freshness_report = self.latest("dream7b_default_service_freshness_gate_latest.json")
        dream_freshness_payload = dream_freshness_report.get("payload") or {}
        dream_freshness_decision = dream_freshness_payload.get("decision") or {}
        dream_freshness_checks = dream_freshness_payload.get("checks") or {}
        dream_freshness_summary = dream_freshness_payload.get("packet_summary") or {}
        dream_freshness = dream_freshness_payload.get("freshness") or {}
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
        runtime_instrumentation_ready = (
            dream_freshness_checks.get("runtime_instrumentation_ready") is True
            and dream_instrumentation.get("contract_verdict")
            == "ok_dream7b_true_batch_runtime_instrumentation_contract"
            and dream_instrumentation.get("deployment_verdict")
            == "ok_dream7b_true_batch_runtime_instrumentation_deployment_contract"
            and dream_instrumentation.get("default_cli_changed") is False
            and dream_instrumentation.get("runtime_order_changed") is False
            and dream_instrumentation.get("active_true_batch_python") == 0.0
            and dream_instrumentation.get("active_compile_true_batch") == 0.0
        )
        hbm_load_accounting_ready = (
            dream_freshness_checks.get("hbm_load_accounting_contract_ok") is True
            and dream_hbm_accounting.get("verdict")
            == "ok_dream7b_true_batch_hbm_load_accounting_contract"
            and dream_hbm_accounting.get("per_segment_load_accounting_ready") is True
            and dream_hbm_accounting.get("group_load_accounting_ready") is True
            and dream_hbm_accounting.get("prewarm_accounting_ready") is True
            and dream_hbm_accounting.get("timing_summary_accounts_load_and_prewarm")
            is True
            and dream_hbm_accounting.get("prewarm_hbm_default_changed") is False
            and dream_hbm_accounting.get("runtime_started") is False
            and dream_hbm_accounting.get("compile_started") is False
        )
        bottleneck_closure_ready = (
            dream_freshness_checks.get("bottleneck_closure_model_ok") is True
            and dream_bottleneck_closure.get("verdict")
            == "ok_dream7b_b4_bottleneck_closure_model"
            and dream_bottleneck_closure.get("primary_next_code_target")
            == "seg27_28_last_token_logits"
            and dream_bottleneck_closure.get(
                "run_more_group_size_or_inner_order_sweeps_now"
            )
            is False
            and dream_bottleneck_closure.get("projection_is_not_bpu_promotion_proof")
            is True
            and dream_bottleneck_closure.get(
                "requires_real_runtime_result_before_promotion"
            )
            is True
        )
        partial_batch_flush_ready = dream_product_evidence.get(
            "queue_partial_batch_flush_ready"
        )
        if partial_batch_flush_ready is None:
            partial_batch_flush_ready = dream_freshness_checks.get(
                "queue_partial_batch_flush_ready"
            )
        partial_batch_flush_live_summary_ready = dream_product_evidence.get(
            "queue_partial_batch_flush_live_summary_ready"
        )
        if partial_batch_flush_live_summary_ready is None:
            partial_batch_flush_live_summary_ready = dream_freshness_summary.get(
                "queue_partial_batch_flush_live_summary_ready"
            )
        partial_batch_flush_probe_ready = dream_product_evidence.get(
            "queue_partial_batch_flush_probe_ready"
        )
        if partial_batch_flush_probe_ready is None:
            partial_batch_flush_probe_ready = dream_freshness_checks.get(
                "queue_partial_batch_flush_probe_ready"
            )
        partial_batch_flush_health_ready = dream_product_evidence.get(
            "queue_partial_batch_flush_health_snapshot_ready"
        )
        if partial_batch_flush_health_ready is None:
            partial_batch_flush_health_ready = dream_freshness_checks.get(
                "queue_partial_batch_flush_health_snapshot_ready"
            )
        partial_batch_flush_probe_or_health_ready = (
            partial_batch_flush_probe_ready is True
            or partial_batch_flush_health_ready is True
        )
        partial_batch_flush_source = dream_product_evidence.get(
            "queue_partial_batch_flush_readiness_source"
        ) or dream_freshness_summary.get("queue_partial_batch_flush_readiness_source")
        dream_product_verdict_accepted = dream_product_report.get("verdict") in (
            "ok_dream7b_product_decision_packet",
            "warning_dream7b_product_decision_packet",
        )
        dream_freshness_verdict_accepted = dream_freshness_report.get("verdict") in (
            "ok_dream7b_default_service_freshness_gate",
            "warning_dream7b_default_service_freshness_gate",
        )
        dream_guardrails_status_ready = (
            dream_product_verdict_accepted
            and dream_fast_report.get("verdict") == "ok_dream7b_fast_path_regression"
            and dream_guardrail_report.get("verdict") == "ok_dream7b_product_guardrail_snapshot"
            and dream_freshness_verdict_accepted
            and not dream_freshness_payload.get("failed_checks")
            and dream_freshness_decision.get("queue_batch_service_remains_default") is True
            and dream_freshness_decision.get("do_not_promote_true_batch") is True
            and dream_freshness_checks.get("nas_inventory_prevents_duplicate_sweeps") is True
            and dream_freshness_checks.get("group_order_partition_prevents_duplicate_sweeps")
            is True
            and dream_freshness_checks.get(
                "scheduler_overhead_deprioritizes_python_gap_tuning"
            )
            is True
            and dream_freshness_checks.get("runtime_source_implementation_map_ok")
            is True
            and dream_freshness_checks.get(
                "runtime_source_implementation_map_blocks_runtime_compile_defaults"
            )
            is True
            and partial_batch_flush_ready is True
            and partial_batch_flush_probe_or_health_ready is True
            and runtime_instrumentation_ready is True
            and hbm_load_accounting_ready is True
            and bottleneck_closure_ready is True
            and quick_ready_meta.get("execution_path") == "gateway_fast_ready"
            and quick_ready_meta.get("backend_invoked") is False
            and (
                dream_guardrail.get("default_status_contract_ready") is True
                or dream_product_evidence.get("guardrail_default_status_contract_ready") is True
            )
            and (
                dream_guardrail.get("default_rollback_dry_run_ready") is True
                or dream_product_evidence.get("guardrail_default_rollback_dry_run_ready") is True
            )
            and dream_product_evidence.get("gateway_listener_ownership_verdict")
            == "ok_dream7b_gateway_listener_ownership"
            and dream_product_evidence.get("gateway_listener_matches_systemd_main_pid") is True
            and dream_product_evidence.get("gateway_orphan_listener_detected") is False
            and dream_product_evidence.get("gateway_listener_health_ok") is True
            and dream_product_evidence.get("gateway_listener_drift_gate_verdict")
            == "ok_dream7b_gateway_listener_drift_gate"
            and dream_product_evidence.get("gateway_listener_drift_snapshot_ok") is True
            and dream_product_evidence.get("gateway_listener_drift_live_matches_systemd_main_pid")
            is True
            and dream_product_evidence.get("gateway_listener_drift_live_orphan_detected") is False
            and dream_product_evidence.get("gateway_listener_drift_live_health_ok") is True
            and dream_queue_health.get("verdict") == "ok_dream7b_queue_health_snapshot"
            and dream_queue_health.get("queue_idle_at_probe") is True
            and dream_queue_health.get("no_true_batch_or_compile_process") is True
            and dream_workstream_overlap.get("verdict") == "ok_dream7b_workstream_overlap_audit"
            and dream_workstream_overlap.get("queue_batch_work_duplicates_prior_true_batch_rental")
            is False
            and dream_workstream_overlap.get("do_not_start_standard_true_batch_runtime_now")
            is True
            and dream_tuning_matrix.get("verdict") == "ok_dream7b_b4_tuning_decision_matrix"
            and dream_tuning_matrix.get("preferred_group_policy")
            == "keep_existing_5_group_segment_major_default"
            and dream_tuning_matrix.get("preferred_inner_order") == "segment-major"
            and dream_tuning_matrix.get("next_s100p_runtime_experiment_allowed") is False
            and dream_tuning_matrix.get("next_compile_allowed") is False
            and dream_tuning_matrix.get("primary_code_target_projected_saved_ms_per_request")
            == dream_final_logits_leverage.get("projection_saved_ms_per_request")
            and dream_tuning_matrix.get("primary_code_target_not_bpu_promotion_proof")
            is True
            and dream_tuning_matrix.get(
                "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
            )
            is True
            and dream_group_inner_order_value.get("verdict")
            == "ok_dream7b_b4_group_inner_order_value_audit"
            and dream_group_inner_order_value.get(
                "run_more_group_size_or_inner_order_sweeps_now"
            )
            is False
            and dream_group_inner_order_value.get(
                "group_size_and_inner_order_are_current_primary_levers"
            )
            is False
            and dream_group_inner_order_value.get("next_s100p_runtime_experiment_allowed_now")
            is False
            and dream_group_inner_order_value.get("next_compile_allowed_now") is False
            and dream_segment_group_schedule.get("verdict")
            == "ok_dream7b_b4_segment_group_schedule_scorecard"
            and dream_segment_group_schedule.get("primary_schedule_bottleneck")
            == "seg27_28_final_logits"
            and dream_segment_group_schedule.get("preferred_group_policy")
            == "keep_existing_5_group_segment_major_default"
            and dream_segment_group_schedule.get("preferred_inner_order") == "segment-major"
            and dream_segment_group_schedule.get(
                "run_more_standard_b4_group_or_inner_order_sweeps_now"
            )
            is False
            and dream_segment_group_schedule.get("run_new_group_partition_now") is False
            and dream_segment_group_schedule.get("run_s100p_runtime_now") is False
            and dream_segment_group_schedule.get("start_compile_now") is False
            and dream_segment_group_schedule.get("compile_preflight_only_now") is True
            and not (dream_segment_group_schedule.get("failed_checks") or [])
            and dream_final_logits_leverage.get("verdict")
            == "ok_dream7b_b4_final_logits_leverage_model"
            and dream_final_logits_leverage.get("projection_is_not_bpu_promotion_proof")
            is True
            and dream_final_logits_leverage.get("do_not_promote_without_runtime_result")
            is True
            and dream_refactor_backlog.get("verdict")
            == "ok_dream7b_b4_runtime_refactor_backlog"
            and dream_refactor_backlog.get("primary_runtime_refactor_target")
            == "final_logits_last_token_path"
            and dream_refactor_backlog.get("rank1_projected_saved_ms_per_request")
            == dream_final_logits_leverage.get("projection_saved_ms_per_request")
            and dream_refactor_backlog.get("rank1_projection_is_not_bpu_promotion_proof")
            is True
            and dream_refactor_backlog.get("rank1_blocks_standard_group_or_inner_order_sweeps")
            is True
            and dream_refactor_source.get("verdict")
            == "ok_dream7b_b4_runtime_refactor_source_contract"
            and dream_refactor_source.get("cli_defaults_preserved") is True
            and dream_refactor_source.get("last_token_path_supported") is True
            and dream_refactor_source.get("telemetry_contract_ready") is True
            and dream_refactor_source.get("protected_telemetry_field_count") == 22
            and dream_refactor_source.get("protected_telemetry_missing_count") == 0
            and dream_refactor_source.get("runtime_order_changed") is False
            and dream_refactor_source.get("default_promotes_experimental_flags") is False
            and dream_refactor_admission.get("verdict")
            == "ok_dream7b_b4_runtime_refactor_admission_contract"
            and dream_refactor_admission.get("local_report_only_refactor_allowed_now") is True
            and dream_refactor_admission.get("default_runtime_code_change_allowed_now")
            is False
            and dream_refactor_admission.get("s100p_runtime_experiment_allowed_now")
            is False
            and dream_refactor_admission.get("compile_start_allowed_now") is False
            and dream_refactor_admission.get("compile_preflight_only_allowed_now") is True
            and not (dream_refactor_admission.get("failed_checks") or [])
            and dream_runtime_source_map.get("verdict")
            == "ok_dream7b_b4_runtime_source_implementation_map"
            and dream_runtime_source_map.get("queue_batch_remains_default") is True
            and dream_runtime_source_map.get("primary_runtime_refactor_target")
            == "seg27_28_last_token_logits_or_output_avoidance"
            and dream_runtime_source_map.get("primary_schedule_bottleneck")
            == "seg27_28_final_logits"
            and dream_runtime_source_map.get("source_pattern_count") == 40
            and dream_runtime_source_map.get("missing_source_pattern_count") == 0
            and dream_runtime_source_map.get("s100p_runtime_experiment_allowed_now")
            is False
            and dream_runtime_source_map.get("compile_start_allowed_now") is False
            and dream_runtime_source_map.get("runtime_default_change_allowed_now")
            is False
            and dream_runtime_source_map.get("standard_group_inner_order_sweeps_blocked")
            is True
            and dream_runtime_source_map.get("runtime_compile_not_started") is True
            and dream_runtime_source_map.get("remote_access_not_performed") is True
            and not (dream_runtime_source_map.get("failed_checks") or [])
            and dream_runtime_gate.get("admission_evidence_ready") is True
            and dream_runtime_gate.get("final_logits_leverage_gate_ready") is True
            and dream_runtime_gate.get("runtime_refactor_gate_ready") is True
            and dream_runtime_gate.get("tuning_matrix_gate_ready") is True
            and dream_runtime_gate.get("admission_projected_saved_ms_per_request")
            == dream_final_logits_leverage.get("projection_saved_ms_per_request")
            and dream_runtime_gate.get("admission_not_bpu_promotion_proof") is True
            and dream_runtime_gate.get("admission_standard_sweeps_blocked") is True
            and dream_runtime_command_guard.get("verdict")
            == "ok_dream7b_b4_runtime_command_guard"
            and dream_runtime_command_guard.get("command_guard_active") is True
            and dream_runtime_command_guard.get("standard_sweep_commands_blocked") is True
            and dream_runtime_command_guard.get("command_admitted") is False
            and dream_runtime_command_guard.get("would_start_runtime") is False
            and dream_compile_command_guard.get("verdict")
            == "ok_dream7b_b4_compile_command_guard"
            and dream_compile_command_guard.get("compile_guard_active") is True
            and dream_compile_command_guard.get(
                "only_single_segment_last_token_compile_allowed"
            )
            is True
            and dream_compile_command_guard.get("b8_full_compile_blocked") is True
            and dream_compile_command_guard.get("command_admitted") is False
            and dream_compile_command_guard.get("would_start_compile") is False
            and dream_next_action_pack.get("verdict")
            == "ok_dream7b_b4_next_action_admission_pack"
            and dream_next_action_pack.get("would_start_runtime") is False
            and dream_next_action_pack.get("would_start_compile") is False
            and dream_next_action_pack.get("queue_batch_product_work_allowed_now") is True
            and dream_next_action_pack.get("compile_preflight_only_allowed_now") is True
            and dream_first_response_slo.get("verdict")
            == "ok_dream7b_first_response_slo_tier_guard"
            and dream_first_response_slo.get(
                "fast_paths_satisfy_interactive_first_content_slo"
            )
            is True
            and dream_first_response_slo.get(
                "sse_progress_satisfies_interactive_progress_slo"
            )
            is True
            and dream_first_response_slo.get(
                "backend_first_content_latency_is_not_true_batch_work"
            )
            is True
            and dream_first_response_slo.get("runtime_started") is False
            and dream_first_response_slo.get("compile_started") is False
        )
        dream_service_guardrails = {
            "status": "ready" if dream_guardrails_status_ready else "needs_attention",
            "product_verdict": dream_product_report.get("verdict"),
            "product_report": dream_product_report.get("path"),
            "production_default": dream_product_decision.get("production_default"),
            "queue_should_remain_default": dream_product_decision.get("queue_should_remain_default"),
            "runtime_experiment_gate_verdict": dream_runtime_gate.get("verdict"),
            "s100p_runtime_experiment_now": dream_product_decision.get(
                "s100p_runtime_experiment_now"
            ),
            "allowed_s100p_runtime_experiments": dream_product_decision.get(
                "allowed_s100p_runtime_experiments"
            )
            or [],
            "runtime_gate_blockers": dream_runtime_gate.get("blockers") or [],
            "next_nonduplicate_runtime_candidate": dream_runtime_gate.get(
                "next_nonduplicate_runtime_candidate"
            )
            or dream_product_decision.get("next_runtime_candidate"),
            "runtime_gate_admission_evidence_ready": dream_runtime_gate.get(
                "admission_evidence_ready"
            ),
            "runtime_gate_final_logits_leverage_gate_ready": dream_runtime_gate.get(
                "final_logits_leverage_gate_ready"
            ),
            "runtime_gate_runtime_refactor_gate_ready": dream_runtime_gate.get(
                "runtime_refactor_gate_ready"
            ),
            "runtime_gate_tuning_matrix_gate_ready": dream_runtime_gate.get(
                "tuning_matrix_gate_ready"
            ),
            "runtime_gate_admission_projected_saved_ms_per_request": dream_runtime_gate.get(
                "admission_projected_saved_ms_per_request"
            ),
            "runtime_gate_admission_not_bpu_promotion_proof": dream_runtime_gate.get(
                "admission_not_bpu_promotion_proof"
            ),
            "runtime_gate_admission_standard_sweeps_blocked": dream_runtime_gate.get(
                "admission_standard_sweeps_blocked"
            ),
            "runtime_command_guard_verdict": dream_runtime_command_guard.get("verdict"),
            "runtime_command_guard_active": dream_runtime_command_guard.get(
                "command_guard_active"
            ),
            "runtime_command_guard_standard_sweeps_blocked": dream_runtime_command_guard.get(
                "standard_sweep_commands_blocked"
            ),
            "runtime_command_guard_command_admitted": dream_runtime_command_guard.get(
                "command_admitted"
            ),
            "runtime_command_guard_would_start_runtime": dream_runtime_command_guard.get(
                "would_start_runtime"
            ),
            "runtime_gate_post_segment_blocks_standard_group_sweeps": dream_runtime_gate.get(
                "post_segment_blocks_standard_group_sweeps"
            ),
            "runtime_gate_post_segment_group_size_tuning_implication": dream_runtime_gate.get(
                "post_segment_group_size_tuning_implication"
            ),
            "runtime_gate_post_segment_inner_order_tuning_implication": dream_runtime_gate.get(
                "post_segment_inner_order_tuning_implication"
            ),
            "segment_stability_audit_verdict": dream_segment_stability.get("verdict"),
            "stable_primary_bottleneck": dream_segment_stability.get("stable_primary_bottleneck"),
            "final_logits_rank1_rate": dream_segment_stability.get("final_logits_rank1_rate"),
            "final_logits_top2_rate": dream_segment_stability.get("final_logits_top2_rate"),
            "final_logits_mean_positive_excess_ms_per_request": dream_segment_stability.get(
                "final_logits_mean_positive_excess_ms_per_request"
            ),
            "final_logits_cv_positive_excess": dream_segment_stability.get(
                "final_logits_cv_positive_excess"
            ),
            "final_to_token_excess_ratio": dream_segment_stability.get(
                "final_to_token_excess_ratio"
            ),
            "final_to_max_hidden_excess_ratio": dream_segment_stability.get(
                "final_to_max_hidden_excess_ratio"
            ),
            "do_not_run_hidden_order_sweeps_now": dream_segment_stability.get(
                "do_not_run_hidden_order_sweeps_now"
            ),
            "segment_drag_breakdown_verdict": dream_segment_drag.get("verdict"),
            "segment_drag_analyzed_run_count": dream_segment_drag.get(
                "analyzed_run_count"
            ),
            "segment_drag_latest_microbatch_count": dream_segment_drag.get(
                "latest_microbatch_count"
            ),
            "segment_drag_final_avg_run_ms": dream_segment_drag.get("final_avg_run_ms"),
            "segment_drag_hidden_mean_avg_run_ms": dream_segment_drag.get(
                "hidden_mean_avg_run_ms"
            ),
            "segment_drag_final_vs_hidden_mean_ratio": dream_segment_drag.get(
                "final_vs_hidden_mean_ratio"
            ),
            "segment_drag_final_excess_ms_per_request": dream_segment_drag.get(
                "final_excess_ms_per_request_if_hidden_speed"
            ),
            "segment_drag_token_excess_ms_per_request": dream_segment_drag.get(
                "token_excess_ms_per_request_if_hidden_speed"
            ),
            "segment_drag_top_group_by_accounted_ms": dream_segment_drag.get(
                "top_group_by_accounted_ms"
            ),
            "segment_drag_top_group_contains_final_logits": dream_segment_drag.get(
                "top_group_contains_final_logits"
            ),
            "segment_drag_top_segments": dream_segment_drag.get(
                "top_segments_by_avg_run_ms"
            )
            or [],
            "group_order_verdict": dream_group_order.get("verdict"),
            "group_order_baseline": dream_group_order.get("baseline"),
            "group_order_segment_major_preferred": dream_group_order.get(
                "segment_major_preferred_over_microbatch_major"
            ),
            "group_order_best_nonbaseline_variant": dream_group_order.get(
                "best_nonbaseline_observed_variant"
            ),
            "group_order_best_nonbaseline_delta_ms_per_request": dream_group_order.get(
                "best_nonbaseline_observed_variant_delta_ms_per_request"
            ),
            "group_order_no_variant_beats_baseline": dream_group_order.get(
                "no_observed_variant_beats_baseline"
            ),
            "group_order_more_mb512_sweeps_deprioritized": dream_group_order.get(
                "more_mb512_group_boundary_sweeps_deprioritized"
            ),
            "group_order_only_capacity_probe_if_needed": dream_group_order.get(
                "only_capacity_probe_if_needed"
            ),
            "segment_group_schedule_scorecard_verdict": dream_segment_group_schedule.get(
                "verdict"
            ),
            "segment_group_primary_schedule_bottleneck": dream_segment_group_schedule.get(
                "primary_schedule_bottleneck"
            ),
            "segment_group_primary_code_target": dream_segment_group_schedule.get(
                "primary_code_target"
            ),
            "segment_group_preferred_group_policy": dream_segment_group_schedule.get(
                "preferred_group_policy"
            ),
            "segment_group_preferred_inner_order": dream_segment_group_schedule.get(
                "preferred_inner_order"
            ),
            "segment_group_run_more_standard_sweeps_now": dream_segment_group_schedule.get(
                "run_more_standard_b4_group_or_inner_order_sweeps_now"
            ),
            "segment_group_run_s100p_runtime_now": dream_segment_group_schedule.get(
                "run_s100p_runtime_now"
            ),
            "segment_group_start_compile_now": dream_segment_group_schedule.get(
                "start_compile_now"
            ),
            "segment_group_compile_preflight_only_now": dream_segment_group_schedule.get(
                "compile_preflight_only_now"
            ),
            "segment_group_final_logits_compute_excess_ms_per_request": dream_segment_group_schedule.get(
                "final_logits_compute_excess_ms_per_request"
            ),
            "segment_group_final_excess_to_group_switch_gap_ratio": dream_segment_group_schedule.get(
                "final_excess_to_group_switch_gap_ratio"
            ),
            "segment_group_best_nonbaseline_group_delta_ms_per_request": dream_segment_group_schedule.get(
                "best_nonbaseline_group_delta_ms_per_request"
            ),
            "group_partition_verdict": dream_group_partition.get("verdict"),
            "group_partition_candidate_count": dream_group_partition.get(
                "candidate_count"
            ),
            "group_partition_run_new_partition_now": dream_group_partition.get(
                "run_new_partition_now"
            ),
            "group_partition_only_probe_if_memory_plan_changes": dream_group_partition.get(
                "only_probe_if_memory_plan_changes"
            ),
            "group_partition_top_capacity_probe_groups": dream_group_partition.get(
                "top_capacity_probe_groups"
            )
            or [],
            "group_partition_top_capacity_probe_max_group_hbm_mib": dream_group_partition.get(
                "top_capacity_probe_max_group_hbm_mib"
            ),
            "group_partition_top_capacity_probe_peak_delta_pct": dream_group_partition.get(
                "top_capacity_probe_peak_delta_pct"
            ),
            "group_partition_best_observed_nonbaseline_delta_ms_per_request": dream_group_partition.get(
                "best_observed_nonbaseline_delta_ms_per_request"
            ),
            "group_inner_order_value_audit_verdict": dream_group_inner_order_value.get(
                "verdict"
            ),
            "group_inner_order_run_more_sweeps_now": dream_group_inner_order_value.get(
                "run_more_group_size_or_inner_order_sweeps_now"
            ),
            "group_inner_order_current_primary_levers": dream_group_inner_order_value.get(
                "group_size_and_inner_order_are_current_primary_levers"
            ),
            "group_inner_order_best_nonbaseline_delta_ms_per_request": dream_group_inner_order_value.get(
                "best_nonbaseline_delta_ms_per_request"
            ),
            "group_inner_order_slower_or_equal_nonbaseline_count": dream_group_inner_order_value.get(
                "slower_or_equal_nonbaseline_count"
            ),
            "group_inner_order_capacity_probe_only_candidate_count": dream_group_inner_order_value.get(
                "capacity_probe_only_candidate_count"
            ),
            "group_inner_order_top_value_lever": dream_group_inner_order_value.get(
                "top_value_lever"
            ),
            "group_inner_order_next_runtime_allowed_now": dream_group_inner_order_value.get(
                "next_s100p_runtime_experiment_allowed_now"
            ),
            "group_inner_order_next_compile_allowed_now": dream_group_inner_order_value.get(
                "next_compile_allowed_now"
            ),
            "group_switch_accounting_verdict": dream_group_switch.get("verdict"),
            "group_switch_gap_ms_per_request": dream_group_switch.get(
                "group_switch_gap_ms_per_request"
            ),
            "group_release_ms_per_request": dream_group_switch.get(
                "group_release_ms_per_request"
            ),
            "unaccounted_gap_ms_per_request": dream_group_switch.get(
                "unaccounted_gap_ms_per_request"
            ),
            "latest_gap_intra_segment_run_gap_ms_per_request": dream_group_switch.get(
                "latest_gap_intra_segment_run_gap_ms_per_request"
            ),
            "final_excess_to_switch_gap_ratio": dream_group_switch.get(
                "final_excess_to_switch_gap_ratio"
            ),
            "group_release_and_unaccounted_gap_not_primary": dream_group_switch.get(
                "group_release_and_unaccounted_gap_not_primary"
            ),
            "scheduler_overhead_budget_verdict": dream_scheduler.get("verdict"),
            "scheduler_primary_code_target": dream_scheduler.get("primary_code_target"),
            "scheduler_final_excess_to_group_switch_gap": dream_scheduler.get(
                "final_excess_to_group_switch_gap"
            ),
            "scheduler_final_excess_to_intra_segment_gap": dream_scheduler.get(
                "final_excess_to_intra_segment_gap"
            ),
            "deprioritize_python_inter_segment_gap_tuning": dream_scheduler.get(
                "deprioritize_python_inter_segment_gap_tuning"
            ),
            "runtime_instrumentation_ready": runtime_instrumentation_ready,
            "runtime_instrumentation_contract_verdict": dream_instrumentation.get(
                "contract_verdict"
            ),
            "runtime_instrumentation_deployment_verdict": dream_instrumentation.get(
                "deployment_verdict"
            ),
            "runtime_instrumentation_new_fields": dream_instrumentation.get(
                "new_telemetry_fields"
            )
            or [],
            "runtime_instrumentation_default_cli_changed": dream_instrumentation.get(
                "default_cli_changed"
            ),
            "runtime_instrumentation_runtime_order_changed": dream_instrumentation.get(
                "runtime_order_changed"
            ),
            "runtime_instrumentation_requires_s100p_runtime": dream_instrumentation.get(
                "requires_s100p_runtime"
            ),
            "runtime_instrumentation_remote_probe_sha256": dream_instrumentation.get(
                "remote_probe_sha256"
            ),
            "runtime_instrumentation_remote_backup": dream_instrumentation.get(
                "remote_backup"
            ),
            "runtime_instrumentation_active_true_batch_python": dream_instrumentation.get(
                "active_true_batch_python"
            ),
            "runtime_instrumentation_active_compile_true_batch": dream_instrumentation.get(
                "active_compile_true_batch"
            ),
            "hbm_load_accounting_ready": hbm_load_accounting_ready,
            "hbm_load_accounting_contract_verdict": dream_hbm_accounting.get("verdict"),
            "hbm_per_segment_load_accounting_ready": dream_hbm_accounting.get(
                "per_segment_load_accounting_ready"
            ),
            "hbm_group_load_accounting_ready": dream_hbm_accounting.get(
                "group_load_accounting_ready"
            ),
            "hbm_prewarm_accounting_ready": dream_hbm_accounting.get(
                "prewarm_accounting_ready"
            ),
            "hbm_timing_summary_accounts_load_and_prewarm": dream_hbm_accounting.get(
                "timing_summary_accounts_load_and_prewarm"
            ),
            "hbm_prewarm_hbm_default_changed": dream_hbm_accounting.get(
                "prewarm_hbm_default_changed"
            ),
            "hbm_accounting_runtime_started": dream_hbm_accounting.get(
                "runtime_started"
            ),
            "hbm_accounting_compile_started": dream_hbm_accounting.get(
                "compile_started"
            ),
            "bottleneck_closure_ready": bottleneck_closure_ready,
            "bottleneck_closure_model_verdict": dream_bottleneck_closure.get(
                "verdict"
            ),
            "bottleneck_closure_latest_avg_bpu_gap_to_queue_points": dream_bottleneck_closure.get(
                "latest_avg_bpu_gap_to_queue_points"
            ),
            "bottleneck_closure_latest_nonzero_shortfall_points_for_93_avg": dream_bottleneck_closure.get(
                "latest_nonzero_shortfall_points_for_93_avg"
            ),
            "bottleneck_closure_primary_next_code_target": dream_bottleneck_closure.get(
                "primary_next_code_target"
            ),
            "bottleneck_closure_final_logits_projection_saved_ms_per_request": dream_bottleneck_closure.get(
                "final_logits_projection_saved_ms_per_request"
            ),
            "bottleneck_closure_hbm_group_load_ms_per_request": dream_bottleneck_closure.get(
                "hbm_group_load_ms_per_request"
            ),
            "bottleneck_closure_release_plus_unaccounted_group_gap_ms_per_request": dream_bottleneck_closure.get(
                "release_plus_unaccounted_group_gap_ms_per_request"
            ),
            "bottleneck_closure_small_python_and_gap_optimizations_combined_ms_per_request": dream_bottleneck_closure.get(
                "small_python_and_gap_optimizations_combined_ms_per_request"
            ),
            "bottleneck_closure_group_size_or_inner_order_current_primary_lever": dream_bottleneck_closure.get(
                "group_size_or_inner_order_current_primary_lever"
            ),
            "bottleneck_closure_projection_is_not_bpu_promotion_proof": dream_bottleneck_closure.get(
                "projection_is_not_bpu_promotion_proof"
            ),
            "bottleneck_closure_requires_real_runtime_result_before_promotion": dream_bottleneck_closure.get(
                "requires_real_runtime_result_before_promotion"
            ),
            "post_instrumentation_telemetry_gate_verdict": dream_post_instrumentation.get(
                "verdict"
            ),
            "post_instrumentation_success_count": dream_post_instrumentation.get(
                "post_instrumentation_success_count"
            ),
            "post_instrumentation_telemetry_ready": dream_post_instrumentation.get(
                "post_instrumentation_telemetry_ready"
            ),
            "input_output_overhead_quantified": dream_post_instrumentation.get(
                "input_output_overhead_quantified"
            ),
            "do_not_claim_input_output_overhead_yet": dream_post_instrumentation.get(
                "do_not_claim_input_output_overhead_yet"
            ),
            "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available": dream_post_instrumentation.get(
                "allow_one_post_instrumentation_baseline_measurement_when_s100p_budget_available"
            ),
            "post_instrumentation_next_measurement_purpose": dream_post_instrumentation.get(
                "next_measurement_purpose"
            ),
            "post_instrumentation_next_measurement_command": dream_post_instrumentation.get(
                "next_measurement_command"
            ),
            "post_instrumentation_overhead_analysis_verdict": dream_post_overhead.get(
                "verdict"
            ),
            "post_instrumentation_input_prepare_ms_per_request": dream_post_overhead.get(
                "input_prepare_ms_per_request"
            ),
            "post_instrumentation_output_postprocess_ms_per_request": dream_post_overhead.get(
                "output_postprocess_ms_per_request"
            ),
            "post_instrumentation_hidden_materialize_ms_per_request": dream_post_overhead.get(
                "hidden_materialize_ms_per_request"
            ),
            "post_instrumentation_final_output_postprocess_ms_per_request": dream_post_overhead.get(
                "final_output_postprocess_ms_per_request"
            ),
            "post_instrumentation_final_excess_ms_per_request_vs_hidden": dream_post_overhead.get(
                "final_excess_ms_per_request_vs_hidden"
            ),
            "post_instrumentation_final_logits_compute_still_primary": dream_post_overhead.get(
                "final_logits_compute_still_primary"
            ),
            "post_instrumentation_secondary_local_runtime_code_target": dream_post_overhead.get(
                "secondary_local_runtime_code_target"
            ),
            "post_instrumentation_segment_attribution_verdict": dream_post_segment.get(
                "verdict"
            ),
            "post_segment_primary_single_segment_bottleneck": dream_post_segment.get(
                "primary_single_segment_bottleneck"
            ),
            "post_segment_final_compute_excess_ms_per_request": dream_post_segment.get(
                "final_compute_excess_ms_per_request"
            ),
            "post_segment_top_group_by_segment_total": dream_post_segment.get(
                "top_group_by_segment_total"
            ),
            "post_segment_top_group_contains_final_logits": dream_post_segment.get(
                "top_group_contains_final_logits"
            ),
            "post_segment_group_size_tuning_implication": dream_post_segment.get(
                "group_size_tuning_implication"
            ),
            "post_segment_inner_order_tuning_implication": dream_post_segment.get(
                "inner_order_tuning_implication"
            ),
            "hidden_buffer_reuse_decision_verdict": dream_hidden_buffer.get("verdict"),
            "hidden_buffer_reuse_default": dream_hidden_buffer.get(
                "hidden_buffer_reuse_default"
            ),
            "preallocate_hidden_experimental_flag_only": dream_hidden_buffer.get(
                "preallocate_hidden_experimental_flag_only"
            ),
            "prealloc_ms_per_request_delta": dream_hidden_buffer.get(
                "prealloc_ms_per_request_delta"
            ),
            "prealloc_hidden_materialize_ms_per_request_delta": dream_hidden_buffer.get(
                "prealloc_hidden_materialize_ms_per_request_delta"
            ),
            "prealloc_reused_hidden_buffer_count": dream_hidden_buffer.get(
                "prealloc_reused_hidden_buffer_count"
            ),
            "reuse_buffer_implementation_measured_slower": dream_hidden_buffer.get(
                "reuse_buffer_implementation_measured_slower"
            ),
            "last_token_candidate": dream_last_token.get("compile_candidate"),
            "last_token_readiness_verdict": dream_last_token.get("readiness_verdict"),
            "last_token_compile_ready": dream_last_token.get("compile_ready"),
            "last_token_runtime_validation_ready": dream_last_token.get(
                "runtime_validation_ready"
            ),
            "last_token_readiness_blockers": dream_last_token.get("readiness_blockers")
            or [],
            "last_token_target_shape": dream_last_token.get("candidate_target_shape"),
            "last_token_saved_ms_projection": dream_last_token.get(
                "projection_only_hypothesis_saved_ms_per_request"
            ),
            "last_token_remote_manifest_verified": dream_last_token.get(
                "remote_last_token_manifest_verified"
            ),
            "last_token_remote_hbm_exists": dream_last_token.get(
                "remote_last_token_hbm_exists"
            ),
            "last_token_experiment_gate_verdict": dream_last_token_gate.get("verdict"),
            "last_token_gate_blockers": dream_last_token_gate.get("gate_blockers") or [],
            "last_token_gate_experiment_ready": dream_last_token_gate.get(
                "experiment_ready"
            ),
            "last_token_validation_plan_verdict": dream_last_token_validation_plan.get(
                "verdict"
            ),
            "last_token_validation_plan_generated_at": dream_last_token_validation_plan.get(
                "plan_generated_at"
            ),
            "last_token_validation_ready": dream_last_token_validation_plan.get(
                "validation_ready"
            ),
            "last_token_validation_blockers": dream_last_token_validation_plan.get(
                "blockers"
            )
            or [],
            "last_token_validation_remote_returncode": dream_last_token_validation_plan.get(
                "remote_returncode"
            ),
            "last_token_validation_final_hbm_root_exists": dream_last_token_validation_plan.get(
                "final_hbm_root_exists"
            ),
            "last_token_validation_hbm_exists": dream_last_token_validation_plan.get(
                "last_token_hbm_exists"
            ),
            "last_token_validation_manifest_exists": dream_last_token_validation_plan.get(
                "manifest_exists"
            ),
            "last_token_validation_manifest_verified": dream_last_token_validation_plan.get(
                "manifest_verified"
            ),
            "last_token_validation_hbm_path": dream_last_token_validation_plan.get(
                "hbm_path"
            ),
            "last_token_validation_compare_verdict": dream_last_token_validation_compare.get(
                "verdict"
            ),
            "last_token_compare_decision": dream_last_token_validation_compare.get(
                "decision"
            ),
            "last_token_candidate_result_exists": dream_last_token_validation_compare.get(
                "candidate_exists"
            ),
            "last_token_preflight_commit_headroom_gb": dream_last_token.get(
                "preflight_commit_headroom_gb"
            ),
            "last_token_preflight_commit_headroom_deficit_gb": dream_last_token.get(
                "latest_preflight_commit_headroom_deficit_gb"
            ),
            "last_token_largest_private_process": dream_last_token.get(
                "largest_private_process"
            ),
            "compile_capacity_verdict": dream_compile_capacity.get("verdict"),
            "compile_commit_headroom_gb": dream_compile_capacity.get("commit_headroom_gb"),
            "compile_commit_headroom_deficit_gb": dream_compile_capacity.get(
                "commit_headroom_deficit_gb"
            ),
            "compile_projected_headroom_after_reclaim_gb": dream_compile_capacity.get(
                "projected_commit_headroom_after_reclaim_gb"
            ),
            "compile_remaining_deficit_after_reclaim_gb": dream_compile_capacity.get(
                "remaining_headroom_deficit_after_reclaim_gb"
            ),
            "compile_recommended_additional_commit_limit_with_safety_gb": dream_compile_capacity.get(
                "recommended_additional_commit_limit_with_safety_gb"
            ),
            "compile_do_not_start_compile_now": dream_compile_capacity.get(
                "do_not_start_compile_now"
            ),
            "compile_command_guard_verdict": dream_compile_command_guard.get("verdict"),
            "compile_command_guard_active": dream_compile_command_guard.get(
                "compile_guard_active"
            ),
            "compile_command_guard_only_single_segment_last_token_compile_allowed": dream_compile_command_guard.get(
                "only_single_segment_last_token_compile_allowed"
            ),
            "compile_command_guard_b8_full_compile_blocked": dream_compile_command_guard.get(
                "b8_full_compile_blocked"
            ),
            "compile_command_guard_command_admitted": dream_compile_command_guard.get(
                "command_admitted"
            ),
            "compile_command_guard_would_start_compile": dream_compile_command_guard.get(
                "would_start_compile"
            ),
            "compile_command_guard_blocked_now_by_readiness": dream_compile_command_guard.get(
                "blocked_now_by_readiness"
            ),
            "compile_command_guard_blocked_now_by_capacity": dream_compile_command_guard.get(
                "blocked_now_by_capacity"
            ),
            "next_action_pack_verdict": dream_next_action_pack.get("verdict"),
            "next_action_pack_allowed_now_count": dream_next_action_pack.get(
                "allowed_now_count"
            ),
            "next_action_pack_preflight_only_count": dream_next_action_pack.get(
                "preflight_only_count"
            ),
            "next_action_pack_blocked_action_count": dream_next_action_pack.get(
                "blocked_action_count"
            ),
            "next_action_pack_would_start_runtime": dream_next_action_pack.get(
                "would_start_runtime"
            ),
            "next_action_pack_would_start_compile": dream_next_action_pack.get(
                "would_start_compile"
            ),
            "next_action_pack_compile_preflight_only_allowed_now": dream_next_action_pack.get(
                "compile_preflight_only_allowed_now"
            ),
            "next_action_pack_only_future_runtime_candidate": dream_next_action_pack.get(
                "only_future_runtime_candidate"
            ),
            "queue_health_snapshot_verdict": dream_queue_health.get("verdict"),
            "queue_health_queue_idle": dream_queue_health.get("queue_idle_at_probe"),
            "queue_health_no_true_batch_or_compile_process": dream_queue_health.get(
                "no_true_batch_or_compile_process"
            ),
            "queue_health_pending_count": dream_queue_health.get("pending_count"),
            "queue_health_processing_count": dream_queue_health.get("processing_count"),
            "queue_health_latest_text_queue_ms_per_request": dream_queue_health.get(
                "latest_text_queue_ms_per_request"
            ),
            "queue_health_partial_batch_flush_ms_per_request": dream_queue_health.get(
                "partial_batch_flush_ms_per_request"
            ),
            "workstream_overlap_audit_verdict": dream_workstream_overlap.get("verdict"),
            "workstream_current_workstream": dream_workstream_overlap.get("current_workstream"),
            "workstream_queue_work_duplicates_true_batch_rental": dream_workstream_overlap.get(
                "queue_batch_work_duplicates_prior_true_batch_rental"
            ),
            "workstream_remote_b4_group_major_report_count": dream_workstream_overlap.get(
                "remote_b4_group_major_report_count"
            ),
            "workstream_remote_b4_group_major_report_json_count": dream_workstream_overlap.get(
                "remote_b4_group_major_report_json_count"
            ),
            "workstream_local_b4_json_count": dream_workstream_overlap.get("local_b4_json_count"),
            "workstream_do_not_start_standard_true_batch_runtime_now": dream_workstream_overlap.get(
                "do_not_start_standard_true_batch_runtime_now"
            ),
            "tuning_decision_matrix_verdict": dream_tuning_matrix.get("verdict"),
            "tuning_preferred_group_policy": dream_tuning_matrix.get("preferred_group_policy"),
            "tuning_preferred_inner_order": dream_tuning_matrix.get("preferred_inner_order"),
            "tuning_primary_code_target": dream_tuning_matrix.get("primary_code_target"),
            "tuning_next_s100p_runtime_experiment_allowed": dream_tuning_matrix.get(
                "next_s100p_runtime_experiment_allowed"
            ),
            "tuning_next_compile_allowed": dream_tuning_matrix.get("next_compile_allowed"),
            "tuning_inner_order_decision": dream_tuning_matrix.get("inner_order_decision"),
            "tuning_group_count_decision": dream_tuning_matrix.get("group_count_decision"),
            "tuning_primary_code_target_projected_saved_ms_per_request": dream_tuning_matrix.get(
                "primary_code_target_projected_saved_ms_per_request"
            ),
            "tuning_primary_code_target_not_bpu_promotion_proof": dream_tuning_matrix.get(
                "primary_code_target_not_bpu_promotion_proof"
            ),
            "tuning_standard_sweeps_blocked_by_final_logits_leverage": dream_tuning_matrix.get(
                "standard_group_or_inner_order_sweeps_blocked_by_final_logits_leverage"
            ),
            "final_logits_leverage_model_verdict": dream_final_logits_leverage.get("verdict"),
            "final_logits_leverage_projection_saved_ms_per_request": dream_final_logits_leverage.get(
                "projection_saved_ms_per_request"
            ),
            "final_logits_leverage_projection_capture_pct": dream_final_logits_leverage.get(
                "projection_capture_of_final_excess_pct"
            ),
            "final_logits_leverage_latest_projected_latency_reduction_pct": dream_final_logits_leverage.get(
                "latest_projected_latency_reduction_pct"
            ),
            "final_logits_leverage_latest_nonzero_shortfall_points": dream_final_logits_leverage.get(
                "latest_nonzero_shortfall_points"
            ),
            "final_logits_leverage_low_load_nonzero_shortfall_points": dream_final_logits_leverage.get(
                "low_load_nonzero_shortfall_points"
            ),
            "final_logits_leverage_not_bpu_promotion_proof": dream_final_logits_leverage.get(
                "projection_is_not_bpu_promotion_proof"
            ),
            "final_logits_leverage_do_not_promote_without_runtime_result": dream_final_logits_leverage.get(
                "do_not_promote_without_runtime_result"
            ),
            "true_batch_nas_inventory_verdict": dream_nas_inventory.get("verdict"),
            "nas_remote_group_major_report_count": dream_nas_inventory.get(
                "remote_group_major_report_count"
            ),
            "nas_remote_group_major_report_json_count": dream_nas_inventory.get(
                "remote_group_major_report_json_count"
            ),
            "nas_remote_b4_group_major_report_count": dream_nas_inventory.get(
                "remote_b4_group_major_report_count"
            ),
            "nas_remote_b4_group_major_report_json_count": dream_nas_inventory.get(
                "remote_b4_group_major_report_json_count"
            ),
            "nas_local_b4_json_count": dream_nas_inventory.get("local_b4_json_count"),
            "nas_missing_report_json_dirs": dream_nas_inventory.get("missing_report_json_dirs")
            or [],
            "nas_b4_remote_json_local_count_match": dream_nas_inventory.get(
                "b4_remote_json_local_count_match"
            ),
            "nas_b4_hbm_count": dream_nas_inventory.get("b4_hbm_count"),
            "nas_b4_manifest_count": dream_nas_inventory.get("b4_manifest_count"),
            "nas_run_more_standard_b4_runtime_sweeps_now": dream_nas_inventory.get(
                "run_more_standard_b4_runtime_sweeps_now"
            ),
            "nas_last_token_candidate_already_ran": dream_nas_inventory.get(
                "last_token_candidate_already_ran"
            ),
            "nas_duplicate_stop_rules": dream_nas_inventory.get("duplicate_stop_rules")
            or [],
            "nas_remaining_nonduplicate_work": dream_nas_inventory.get(
                "remaining_nonduplicate_work"
            )
            or [],
            "runtime_refactor_backlog_verdict": dream_refactor_backlog.get("verdict"),
            "runtime_refactor_primary_target": dream_refactor_backlog.get(
                "primary_runtime_refactor_target"
            ),
            "runtime_refactor_secondary_target": dream_refactor_backlog.get(
                "secondary_research_target"
            ),
            "runtime_refactor_preallocate_hidden_rejected": dream_refactor_backlog.get(
                "current_preallocate_hidden_rejected_by_evidence"
            ),
            "runtime_refactor_preallocate_hidden_experimental_flag_only": dream_refactor_backlog.get(
                "preallocate_hidden_experimental_flag_only"
            ),
            "runtime_refactor_rank1_projected_saved_ms_per_request": dream_refactor_backlog.get(
                "rank1_projected_saved_ms_per_request"
            ),
            "runtime_refactor_rank1_not_bpu_promotion_proof": dream_refactor_backlog.get(
                "rank1_projection_is_not_bpu_promotion_proof"
            ),
            "runtime_refactor_rank1_blocks_standard_sweeps": dream_refactor_backlog.get(
                "rank1_blocks_standard_group_or_inner_order_sweeps"
            ),
            "runtime_refactor_ready_local_count": dream_refactor_backlog.get(
                "ready_local_refactor_count"
            ),
            "runtime_refactor_do_not_change_defaults_now": dream_refactor_backlog.get(
                "do_not_change_runtime_defaults_now"
            ),
            "runtime_refactor_do_not_start_s100p_now": dream_refactor_backlog.get(
                "do_not_start_s100p_runtime_now"
            ),
            "runtime_refactor_top_items": dream_refactor_backlog.get("top_backlog_items")
            or [],
            "runtime_refactor_source_contract_verdict": dream_refactor_source.get("verdict"),
            "runtime_refactor_source_cli_defaults_preserved": dream_refactor_source.get(
                "cli_defaults_preserved"
            ),
            "runtime_refactor_source_last_token_path_supported": dream_refactor_source.get(
                "last_token_path_supported"
            ),
            "runtime_refactor_source_telemetry_contract_ready": dream_refactor_source.get(
                "telemetry_contract_ready"
            ),
            "runtime_refactor_source_protected_telemetry_field_count": dream_refactor_source.get(
                "protected_telemetry_field_count"
            ),
            "runtime_refactor_source_protected_telemetry_missing_count": dream_refactor_source.get(
                "protected_telemetry_missing_count"
            ),
            "runtime_refactor_source_runtime_order_changed": dream_refactor_source.get(
                "runtime_order_changed"
            ),
            "runtime_refactor_source_default_promotes_experimental_flags": dream_refactor_source.get(
                "default_promotes_experimental_flags"
            ),
            "runtime_source_implementation_map_verdict": dream_runtime_source_map.get(
                "verdict"
            ),
            "runtime_source_implementation_area_count": dream_runtime_source_map.get(
                "implementation_area_count"
            ),
            "runtime_source_pattern_count": dream_runtime_source_map.get(
                "source_pattern_count"
            ),
            "runtime_source_missing_source_pattern_count": dream_runtime_source_map.get(
                "missing_source_pattern_count"
            ),
            "runtime_source_primary_runtime_refactor_target": dream_runtime_source_map.get(
                "primary_runtime_refactor_target"
            ),
            "runtime_source_primary_schedule_bottleneck": dream_runtime_source_map.get(
                "primary_schedule_bottleneck"
            ),
            "runtime_source_allowed_now": dream_runtime_source_map.get("allowed_now")
            or [],
            "runtime_source_duplicate_or_blocked_area_count": dream_runtime_source_map.get(
                "duplicate_or_blocked_area_count"
            ),
            "runtime_source_s100p_runtime_allowed_now": dream_runtime_source_map.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "runtime_source_compile_start_allowed_now": dream_runtime_source_map.get(
                "compile_start_allowed_now"
            ),
            "runtime_source_runtime_default_change_allowed_now": dream_runtime_source_map.get(
                "runtime_default_change_allowed_now"
            ),
            "runtime_source_standard_sweeps_blocked": dream_runtime_source_map.get(
                "standard_group_inner_order_sweeps_blocked"
            ),
            "runtime_source_runtime_compile_not_started": dream_runtime_source_map.get(
                "runtime_compile_not_started"
            ),
            "runtime_source_remote_access_not_performed": dream_runtime_source_map.get(
                "remote_access_not_performed"
            ),
            "runtime_source_failed_checks": dream_runtime_source_map.get("failed_checks")
            or [],
            "runtime_refactor_admission_contract_verdict": dream_refactor_admission.get(
                "verdict"
            ),
            "runtime_refactor_admission_local_report_only_allowed_now": dream_refactor_admission.get(
                "local_report_only_refactor_allowed_now"
            ),
            "runtime_refactor_admission_design_only_hidden_materialize_allowed_now": dream_refactor_admission.get(
                "design_only_hidden_materialize_allowed_now"
            ),
            "runtime_refactor_admission_default_runtime_change_allowed_now": dream_refactor_admission.get(
                "default_runtime_code_change_allowed_now"
            ),
            "runtime_refactor_admission_s100p_runtime_allowed_now": dream_refactor_admission.get(
                "s100p_runtime_experiment_allowed_now"
            ),
            "runtime_refactor_admission_compile_start_allowed_now": dream_refactor_admission.get(
                "compile_start_allowed_now"
            ),
            "runtime_refactor_admission_compile_preflight_only_allowed_now": dream_refactor_admission.get(
                "compile_preflight_only_allowed_now"
            ),
            "runtime_refactor_admission_block_standard_sweeps": dream_refactor_admission.get(
                "block_standard_group_or_inner_order_sweeps"
            ),
            "runtime_refactor_admission_block_prewarm_or_cache_default": dream_refactor_admission.get(
                "block_prewarm_or_cache_default"
            ),
            "routing_verdict": dream_product_first_response.get("routing_verdict"),
            "fast_status_verdict": dream_product_first_response.get("fast_status_verdict"),
            "fast_path_verdict": dream_product_first_response.get("fast_path_regression_verdict")
            or dream_fast_report.get("verdict"),
            "fast_path_report": dream_fast_report.get("path"),
            "first_response_slo_tier_guard_verdict": dream_first_response_slo.get("verdict"),
            "first_response_slo_fast_path_ready": dream_first_response_slo.get(
                "fast_paths_satisfy_interactive_first_content_slo"
            ),
            "first_response_slo_progress_ready": dream_first_response_slo.get(
                "sse_progress_satisfies_interactive_progress_slo"
            ),
            "first_response_backend_not_true_batch_work": dream_first_response_slo.get(
                "backend_first_content_latency_is_not_true_batch_work"
            ),
            "first_response_slo_fast_path_max_first_content_ms": dream_first_response_slo.get(
                "fast_path_max_first_content_ms"
            ),
            "first_response_slo_first_progress_p50_ms": dream_first_response_slo.get(
                "sse_first_progress_p50_ms"
            ),
            "first_response_slo_backend_explicit_first_content_p50_ms": dream_first_response_slo.get(
                "explicit_first_content_p50_ms"
            ),
            "first_response_warning_triage_verdict": dream_first_response_warning_triage.get(
                "verdict"
            ),
            "first_response_warning_triaged": dream_first_response_warning_triage.get(
                "warning_is_product_triaged"
            ),
            "first_response_warning_source_verdict": dream_first_response_warning_triage.get(
                "source_warning_verdict"
            ),
            "first_response_warning_quickpath_delta_ms": dream_first_response_warning_triage.get(
                "quickpath_delta_ms"
            ),
            "first_response_warning_backend_not_true_batch_work": dream_first_response_warning_triage.get(
                "backend_first_content_latency_is_not_true_batch_work"
            ),
            "slo_limited_evidence_triage_verdict": dream_slo_limited_evidence_triage.get(
                "verdict"
            ),
            "slo_limited_evidence_triaged": dream_slo_limited_evidence_triage.get(
                "limited_evidence_triaged"
            ),
            "slo_limited_evidence_release_blocker": dream_slo_limited_evidence_triage.get(
                "release_blocker"
            ),
            "slo_limited_warnings": dream_slo_limited_evidence_triage.get(
                "slo_warnings"
            ),
            "slo_limited_concurrency_verdict": dream_slo_limited_evidence_triage.get(
                "concurrency_verdict"
            ),
            "first_response_slo_runtime_started": dream_first_response_slo.get(
                "runtime_started"
            ),
            "first_response_slo_compile_started": dream_first_response_slo.get(
                "compile_started"
            ),
            "freshness_verdict": dream_freshness_report.get("verdict"),
            "freshness_report": dream_freshness_report.get("path"),
            "freshness_failed_checks": dream_freshness_payload.get("failed_checks") or [],
            "freshness_packet_age_minutes": dream_freshness.get("packet_age_minutes"),
            "queue_batch_service_remains_default": dream_freshness_decision.get(
                "queue_batch_service_remains_default"
            ),
            "do_not_promote_true_batch": dream_freshness_decision.get("do_not_promote_true_batch"),
            "rerun_product_packet_if_stale": dream_freshness_decision.get("rerun_product_packet_if_stale"),
            "queue_partial_batch_flush_ready": partial_batch_flush_ready,
            "queue_partial_batch_flush_live_summary_ready": partial_batch_flush_live_summary_ready,
            "queue_partial_batch_flush_probe_ready": partial_batch_flush_probe_ready,
            "queue_partial_batch_flush_health_snapshot_ready": partial_batch_flush_health_ready,
            "queue_partial_batch_flush_probe_or_health_ready": partial_batch_flush_probe_or_health_ready,
            "queue_partial_batch_flush_readiness_source": partial_batch_flush_source,
            "queue_partial_batch_probe_run_dir": dream_product_evidence.get(
                "queue_partial_batch_probe_run_dir"
            )
            or dream_freshness_summary.get("queue_partial_batch_probe_run_dir"),
            "queue_partial_batch_probe_ms_per_request": dream_product_evidence.get(
                "queue_partial_batch_probe_ms_per_request"
            )
            or dream_freshness_summary.get("queue_partial_batch_probe_ms_per_request"),
            "per_run_evidence_matrix_verdict": dream_product_evidence.get(
                "per_run_evidence_matrix_verdict"
            )
            or dream_freshness_summary.get("per_run_evidence_matrix_verdict"),
            "per_run_evidence_matrix_run_count": dream_product_evidence.get(
                "per_run_evidence_matrix_run_count"
            )
            or dream_freshness_summary.get("per_run_evidence_matrix_run_count"),
            "per_run_evidence_matrix_successful_run_count": dream_product_evidence.get(
                "per_run_evidence_matrix_successful_run_count"
            )
            or dream_freshness_summary.get(
                "per_run_evidence_matrix_successful_run_count"
            ),
            "per_run_evidence_matrix_failed_run_count": dream_product_evidence.get(
                "per_run_evidence_matrix_failed_run_count"
            )
            or dream_freshness_summary.get("per_run_evidence_matrix_failed_run_count"),
            "per_run_evidence_matrix_top_segment": dream_product_evidence.get(
                "per_run_evidence_matrix_top_segment"
            )
            or dream_freshness_summary.get("per_run_evidence_matrix_top_segment"),
            "per_run_evidence_matrix_top_segment_rate": dream_product_evidence.get(
                "per_run_evidence_matrix_top_segment_rate"
            )
            or dream_freshness_summary.get("per_run_evidence_matrix_top_segment_rate"),
            "per_run_evidence_matrix_standard_sweep_status": dream_product_evidence.get(
                "per_run_evidence_matrix_standard_sweep_status"
            )
            or dream_freshness_summary.get(
                "per_run_evidence_matrix_standard_sweep_status"
            ),
            "nas_inventory_prevents_duplicate_sweeps": dream_freshness_checks.get(
                "nas_inventory_prevents_duplicate_sweeps"
            ),
            "group_order_partition_prevents_duplicate_sweeps": dream_freshness_checks.get(
                "group_order_partition_prevents_duplicate_sweeps"
            ),
            "scheduler_overhead_deprioritizes_python_gap_tuning": dream_freshness_checks.get(
                "scheduler_overhead_deprioritizes_python_gap_tuning"
            ),
            "runtime_source_implementation_map_ok": dream_freshness_checks.get(
                "runtime_source_implementation_map_ok"
            ),
            "runtime_source_implementation_map_blocks_runtime_compile_defaults": dream_freshness_checks.get(
                "runtime_source_implementation_map_blocks_runtime_compile_defaults"
            ),
            "remote_queue_active_enabled": (
                dream_freshness_checks.get("remote_queue_active_enabled")
                and dream_freshness_checks.get("remote_gateway_active_enabled")
            ),
            "remote_listener_matches_gateway_pid": dream_freshness_checks.get(
                "remote_listener_matches_gateway_pid"
            ),
            "remote_health_ok": dream_freshness_checks.get("remote_health_ok"),
            "quick_ready_first_content_ms": quick_ready_case.get("first_content_ms")
            or dream_product_first_response.get("regression_quick_ready_first_content_ms"),
            "quick_ready_execution_path": quick_ready_meta.get("execution_path"),
            "quick_ready_backend_invoked": quick_ready_meta.get("backend_invoked"),
            "localized_status_first_content_ms": localized_status_case.get("first_content_ms")
            or dream_product_first_response.get("regression_localized_status_first_content_ms"),
            "localized_status_execution_path": localized_status_meta.get("execution_path"),
            "localized_status_backend_invoked": localized_status_meta.get("backend_invoked"),
            "guardrail_verdict": dream_guardrail_report.get("verdict"),
            "guardrail_report": dream_guardrail_report.get("path"),
            "default_status_contract_ready": dream_guardrail.get("default_status_contract_ready")
            or dream_product_evidence.get("guardrail_default_status_contract_ready"),
            "default_rollback_dry_run_ready": dream_guardrail.get("default_rollback_dry_run_ready")
            or dream_product_evidence.get("guardrail_default_rollback_dry_run_ready"),
            "status_script_sha256": ((dream_status_contract.get("script") or {}).get("sha256"))
            or dream_product_evidence.get("guardrail_status_script_sha256"),
            "rollback_script_sha256": ((dream_rollback_contract.get("script") or {}).get("sha256"))
            or dream_product_evidence.get("guardrail_rollback_script_sha256"),
            "gateway_listener_ownership_verdict": dream_product_evidence.get(
                "gateway_listener_ownership_verdict"
            ),
            "gateway_listener_pid": dream_product_evidence.get("gateway_listener_pid"),
            "gateway_main_pid": dream_product_evidence.get("gateway_main_pid"),
            "gateway_listener_matches_systemd_main_pid": dream_product_evidence.get(
                "gateway_listener_matches_systemd_main_pid"
            ),
            "gateway_orphan_listener_detected": dream_product_evidence.get(
                "gateway_orphan_listener_detected"
            ),
            "gateway_listener_health_ok": dream_product_evidence.get("gateway_listener_health_ok"),
            "gateway_listener_drift_gate_verdict": dream_product_evidence.get(
                "gateway_listener_drift_gate_verdict"
            ),
            "gateway_listener_drift_snapshot_ok": dream_product_evidence.get(
                "gateway_listener_drift_snapshot_ok"
            ),
            "gateway_listener_drift_live_matches_systemd_main_pid": dream_product_evidence.get(
                "gateway_listener_drift_live_matches_systemd_main_pid"
            ),
            "gateway_listener_drift_live_orphan_detected": dream_product_evidence.get(
                "gateway_listener_drift_live_orphan_detected"
            ),
            "gateway_listener_drift_live_health_ok": dream_product_evidence.get(
                "gateway_listener_drift_live_health_ok"
            ),
            "gateway_listener_drift_warning_count": dream_product_evidence.get(
                "gateway_listener_drift_warning_count"
            ),
            "segment_bottleneck_primary_runtime_lever": (
                dream_product_payload.get("segment_bottleneck_scorecard") or {}
            ).get("primary_runtime_lever"),
            "remaining_gap": "general backend first-content latency still tracked separately",
        }
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
            "dream7b_service_guardrails": {
                "label": "Dream7B service guardrails",
                **dream_service_guardrails,
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
            "dream7b_service_guardrails": dream_service_guardrails,
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
            http_health("dream7b_openai_gateway", "http://127.0.0.1:18888/health"),
            http_health("openclaw_gateway", "http://127.0.0.1:18789/health"),
        ]
        is_linux = platform.system().lower() == "linux"
        if is_linux:
            systemd_env = None
            if Path("/run/user/0").exists():
                systemd_env = {"XDG_RUNTIME_DIR": "/run/user/0"}
            checks.extend(
                [
                    {
                        "name": "ai_nas_index_daemon",
                        "kind": "systemd_system",
                        **run_checked(["systemctl", "is-active", "ai-nas-index-daemon.service"]),
                    },
                    {
                        "name": "dream7b_local_openai_gateway",
                        "kind": "systemd_user",
                        **run_checked(["systemctl", "--user", "is-active", "dream7b-local-openai-gateway.service"], env=systemd_env),
                    },
                    {
                        "name": "openclaw_gateway",
                        "kind": "systemd_user",
                        **run_checked(["systemctl", "--user", "is-active", "openclaw-gateway.service"], env=systemd_env),
                    },
                ]
            )
        else:
            checks.append(
                {
                    "name": "systemd_services",
                    "kind": "systemd",
                    "ok": None,
                    "status": "not_applicable",
                    "platform": platform.system(),
                    "note": "systemd service checks are available only on the S100P/Linux deployment.",
                }
            )
        return {
            "generated_at_epoch": time.time(),
            "ok_count": sum(1 for item in checks if item.get("ok") is True),
            "failed_count": sum(1 for item in checks if item.get("ok") is False),
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

    def send_file_binary(self, path: Path, download_name: str, *, inline: bool = False) -> None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            self.send_json({"ok": False, "error": f"read_failed:{type(exc).__name__}:{exc}", "path": str(path)}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        disposition = "inline" if inline else "attachment"
        self.send_header("Content-Disposition", f'{disposition}; filename="{download_name.replace(chr(34), "_")}"')
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_portal_html(self, path: Path, *, inject_runtime: bool = True) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.send_json({"ok": False, "error": f"read_failed:{type(exc).__name__}:{exc}", "path": str(path)}, HTTPStatus.NOT_FOUND)
            return
        if inject_runtime:
            text = inject_runtime_sections(text, self.state.latest_bundle())
        self.send_text(text, "text/html; charset=utf-8")

    def current_identity_user(self) -> dict | None:
        store = self.state.identity_store
        if not store:
            return None
        user = self.state._identity_user(self)
        if user:
            return user
        params = parse_qs(urlparse(self.path).query)
        token = params.get("token", [""])[0]
        if token:
            return store.validate_token(token)
        return None

    def require_storage_read(self, relative_path: str) -> tuple[bool, dict | None]:
        store = self.state.identity_store
        if not store:
            return True, None
        user = self.current_identity_user()
        if not user:
            return False, {"ok": False, "error": "not_authenticated"}
        if user.get("role") == "admin":
            return True, user
        if store.check_acl(user["username"], relative_path, "read"):
            return True, user
        return False, {"ok": False, "error": "StoragePathError:permission_denied"}

    def filter_storage_entries_for_user(self, entries: list[dict], relative_path: str) -> tuple[int, dict | None, list[dict]]:
        store = self.state.identity_store
        if not store:
            return HTTPStatus.OK, None, entries
        user = self.current_identity_user()
        if not user:
            requested = normalize_storage_relative_path(relative_path)
            if not requested:
                return HTTPStatus.OK, None, entries
            return HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "not_authenticated"}, []
        if user.get("role") == "admin":
            return HTTPStatus.OK, user, entries
        username = user["username"]
        requested = normalize_storage_relative_path(relative_path)
        visible = set(store.get_visible_paths(username))
        if requested and not store.check_acl(username, requested, "read") and not any(path.startswith(requested + "/") for path in visible):
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "StoragePathError:permission_denied"}, []
        filtered = []
        for entry in entries:
            rel = entry.get("relative_path") or ""
            if store.check_acl(username, rel, "read") or rel in visible or any(path.startswith(rel + "/") for path in visible):
                filtered.append(entry)
        return HTTPStatus.OK, user, filtered

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
        if route == "/manifest.webmanifest":
            self.send_text(json.dumps(PWA_MANIFEST, ensure_ascii=False, indent=2), "application/manifest+json; charset=utf-8")
            return
        if route == "/pwa-icon.svg":
            self.send_text(PWA_ICON_SVG, "image/svg+xml; charset=utf-8")
            return
        if route == "/sw.js":
            self.send_text(PWA_SW_JS, "text/javascript; charset=utf-8")
            return
        if route.startswith("/assets/"):
            relative = normalize_storage_relative_path(route.removeprefix("/assets/"))
            asset_root = Path(__file__).with_name("portal_assets").resolve()
            asset_path = (asset_root / relative).resolve()
            try:
                asset_path.relative_to(asset_root)
            except ValueError:
                self.send_json({"ok": False, "error": "asset_path_outside_root"}, HTTPStatus.FORBIDDEN)
                return
            if not asset_path.is_file():
                self.send_json({"ok": False, "error": "asset_not_found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_file_binary(asset_path, asset_path.name, inline=True)
            return
        if route in {"/", "/operator_portal.html"}:
            if self.state.nas_portal_enabled and self.state.nas_portal_path and self.state.nas_portal_path.exists():
                self.send_portal_html(self.state.nas_portal_path, inject_runtime=False)
                return
            html_path = self.state.portal_html_path()
            if not html_path:
                self.send_json({"ok": False, "error": "operator_portal_html_not_found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_portal_html(html_path)
            return
        if route == "/api/health":
            contract = self.state.portal_contract()
            self.send_json(
                {
                    "ok": bool(contract.get("found")),
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
        if route == "/api/latest.dream7b_service_guardrails":
            self.send_json(
                {
                    "ok": True,
                    "dream7b_service_guardrails": self.state.latest_bundle().get(
                        "dream7b_service_guardrails"
                    )
                    or {},
                }
            )
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
        if route == "/api/storage/status":
            try:
                self.send_json(self.state.storage_status_payload())
            except Exception as exc:
                self.send_json({"ok": False, "error": f"{type(exc).__name__}:{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if route == "/api/storage/insights":
            try:
                user = self.current_identity_user() if self.state.identity_store else None
                if self.state.identity_store and not user:
                    self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                    return
                self.send_json(self.state.storage_insights_payload(user))
            except Exception as exc:
                self.send_json({"ok": False, "error": f"{type(exc).__name__}:{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if route == "/api/storage/list":
            try:
                rel = params.get("path", [""])[0]
                payload = self.state.storage_list_payload(rel)
                status, error, entries = self.filter_storage_entries_for_user(payload.get("entries") or [], rel)
                if status != HTTPStatus.OK:
                    self.send_json(error or {"ok": False, "error": "permission_denied"}, status)
                    return
                payload["entries"] = entries
                self.send_json(payload)
            except (StoragePathError, FileNotFoundError, NotADirectoryError) as exc:
                self.send_json({"ok": False, "error": f"{type(exc).__name__}:{exc}"}, HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/storage/operations":
            self.send_json({"ok": True, "operations": latest_file_operations(self.state.sqlite_index_path, limit=100)})
            return
        if route == "/api/storage/download":
            try:
                rel = params.get("path", [""])[0]
                allowed, user_or_error = self.require_storage_read(rel)
                if not allowed:
                    status = HTTPStatus.UNAUTHORIZED if (user_or_error or {}).get("error") == "not_authenticated" else HTTPStatus.FORBIDDEN
                    self.send_json(user_or_error or {"ok": False, "error": "permission_denied"}, status)
                    return
                target = resolve_storage_path(self.state.personal_root, rel, allow_root=False)
                if not target.exists() or not target.is_file():
                    raise FileNotFoundError(str(target))
                inline = str(params.get("preview", [""])[0]).lower() in {"1", "true", "yes"}
                self.send_file_binary(target, target.name, inline=inline)
            except (StoragePathError, FileNotFoundError) as exc:
                self.send_json({"ok": False, "error": f"{type(exc).__name__}:{exc}"}, HTTPStatus.NOT_FOUND)
            return
        if route == "/api/identity/users":
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"ok": True, "users": store.list_users()})
            return
        if route == "/api/identity/groups":
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"ok": True, "groups": store.list_groups()})
            return
        if route == "/api/identity/acls":
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            path_filter = params.get("path", [None])[0]
            self.send_json({"ok": True, "acls": store.list_acls(path_filter if path_filter else None)})
            return
        if route == "/api/identity/session":
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self)
            if not usr:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json({"ok": True, "user": usr})
            return
        if route == "/api/identity/visible-paths":
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self)
            if not usr:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json({"ok": True, "paths": store.get_visible_paths(usr["username"])})
            return
        if route == "/api/storage/acl-list":
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": True, "entries": list_storage_directory(self.state.personal_root, params.get("path", [""])[0])})
                return
            usr = self.state._identity_user(self)
            if not usr:
                self.send_json({"ok": True, "entries": list_storage_directory(self.state.personal_root, params.get("path", [""])[0])})
                return
            if usr.get("role") == "admin":
                self.send_json({"ok": True, "entries": list_storage_directory(self.state.personal_root, params.get("path", [""])[0])})
                return
            visible = set(store.get_visible_paths(usr["username"]))
            if visible == {"*"}:
                self.send_json({"ok": True, "entries": list_storage_directory(self.state.personal_root, params.get("path", [""])[0])})
                return
            req_path = (params.get("path", [""])[0]).strip().strip("/")
            if req_path not in visible:
                self.send_json({"ok": False, "error": "StoragePathError:permission_denied"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json({"ok": True, "entries": list_storage_directory(self.state.personal_root, params.get("path", [""])[0])})
            return
        if route == "/api/snapshot/list":
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"ok": True, "snapshots": store.list_snapshots()})
            return
        if route == "/api/snapshot/browse":
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            result = store.browse_snapshot(params.get("name", [""])[0], params.get("path", [""])[0])
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/snapshot/stats":
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"ok": True, "stats": store.stats()})
            return
        if route == "/api/trash/list":
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            user = self.state._identity_user(self) if _HAS_IDENTITY else None
            uname = user["username"] if user else ""
            self.send_json({"ok": True, "trash": store.list_trash(uname)})
            return
        if route == "/api/version/list":
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            p = params.get("path", [""])[0]
            self.send_json({"ok": True, "versions": store.list_versions(p)})
            return
        if route == "/api/backup/summary":
            manager = self.state.backup_manager
            if not manager:
                self.send_json({"ok": False, "error": "backup_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json({"ok": True, "stats": manager.stats(), "tasks": manager.list_tasks(), "runs": manager.list_runs(limit=50)})
            return
        if route == "/api/schedule/summary":
            manager = self.state.schedule_manager
            if not manager:
                self.send_json({"ok": False, "error": "schedule_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json(manager.summary())
            return
        if route == "/api/media/summary":
            media = self.state.media_center
            if not media:
                self.send_json({"ok": False, "error": "media_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(
                {
                    "ok": True,
                    "stats": media.stats(),
                    "photos": media.list_photos(limit=100),
                    "movies": self.state.media_movie_payloads(media.list_movies(limit=100)),
                    "timeline": media.timeline(),
                    "duplicates": media.find_duplicates(),
                    "albums": media.list_albums(),
                }
            )
            return
        if route == "/api/vision/status":
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json(self.state.official_vision_status_payload())
            return
        if route == "/api/vision/search":
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            query = params.get("query", [""])[0]
            try:
                limit = int(params.get("limit", ["10"])[0])
            except ValueError:
                limit = 10
            auto_index = str(params.get("auto_index", [""])[0]).lower() in {"1", "true", "yes"}
            try:
                self.send_json(self.state.vision_search_payload(query, limit=limit, user=user, auto_index=auto_index))
            except Exception as exc:
                self.send_json({"ok": False, "error": f"{type(exc).__name__}:{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if route == "/api/portal/config":
            self.send_json(self.state.portal_config_payload())
            return
        if route == "/api/ops/summary":
            ops = self.state.ops_manager
            if not ops:
                self.send_json({"ok": False, "error": "ops_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(
                {
                    "ok": True,
                    "stats": ops.stats(),
                    "checks": ops.list_checks(limit=50),
                    "alerts": ops.list_alerts(include_resolved=True),
                    "disk": ops.disk_check(str(self.state.personal_root)),
                }
            )
            return
        if route == "/api/apps/summary":
            apps = self.state.app_ecosystem
            if not apps:
                self.send_json({"ok": False, "error": "app_ecosystem_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(
                {
                    "ok": True,
                    "stats": apps.stats(),
                    "plugins": apps.list_plugins(),
                    "protocols": apps.list_protocols(),
                    "truthfulness": "adapter records only; protocol daemons are not implemented by this endpoint",
                }
            )
            return
        if route == "/api/audit/summary":
            self.send_json(
                {
                    "ok": True,
                    "operations": latest_file_operations(self.state.sqlite_index_path, limit=100),
                    "operator_decisions": self.state.latest_operator_decisions(limit=50),
                }
            )
            return
        if route == "/api/copilot/search":
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            query = params.get("query", [""])[0]
            kind = params.get("type", ["file"])[0]
            try:
                limit = int(params.get("limit", ["20"])[0])
            except ValueError:
                limit = 20
            results = self.state.copilot_search(query, kind, limit, user)
            if kind == "file":
                results = [item for item in results if item.get("type") == "file"]
            elif kind in {"image", "video"}:
                results = [item for item in results if item.get("type") == kind]
            self.send_json({"ok": True, "query": query, "type": kind, "results": results})
            return
        self.send_json(
            {
                "ok": False,
                "error": "not_found",
                "routes": [
                    "/",
                    "/api/health",
                    "/api/portal/config",
                    "/api/latest",
                    "/api/latest.goal_progress",
                    "/api/latest.dream7b_service_guardrails",
                    "/api/latest.operator_decisions",
                    "/api/services",
                    "/api/portal-report",
                    "/api/operator-decisions",
                    "/api/contracts/operator-portal",
                    "/api/storage/status",
                    "/api/storage/insights",
                    "/api/storage/list",
                    "/api/storage/operations",
                    "/api/storage/download",
                    "/api/backup/summary",
                    "/api/schedule/summary",
                    "/api/media/summary",
                    "/api/vision/status",
                    "/api/vision/search",
                    "/api/ops/summary",
                    "/api/apps/summary",
                    "/api/audit/summary",
                    "/api/copilot/search",
                    "POST /api/refresh",
                    "POST /api/operator-decision",
                    "POST /api/copilot/chat",
                    "POST /api/schedule/create-rule",
                    "POST /api/schedule/set-enabled",
                    "POST /api/schedule/run-dry",
                    "POST /api/vision/index",
                    "POST /api/storage/upload",
                    "POST /api/storage/rename",
                    "POST /api/storage/move",
                    "POST /api/storage/copy",
                    "DELETE /api/storage/file",
                ],
            },
            HTTPStatus.NOT_FOUND,
        )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
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
        if route == "/api/copilot/chat":
            length = int(self.headers.get("Content-Length", "0") or "0")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self.send_json({"ok": False, "error": f"invalid_json:{exc}"}, HTTPStatus.BAD_REQUEST)
                return
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            message = str(payload.get("message") or payload.get("query") or "").strip()
            if not message:
                self.send_json({"ok": False, "error": "message_required"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                limit = int(payload.get("limit") or 8)
            except (TypeError, ValueError):
                limit = 8
            result = self.state.copilot_chat(
                message,
                payload.get("messages") if isinstance(payload.get("messages"), list) else None,
                str(payload.get("type") or "all"),
                limit,
                user,
            )
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if route == "/api/storage/upload":
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length)
                filename, data = parse_multipart_upload(self.headers.get("Content-Type", ""), raw)
                # ACL enforcement for upload
                store = self.state.identity_store
                if store:
                    usr = self.state._identity_user(self)
                    if usr and usr.get("role") != "admin":
                        target_dir = (params.get("path", [""])[0]).strip().strip("/")
                        if not store.check_acl(usr["username"], target_dir, "write"):
                            self.send_json({"ok": False, "error": "StoragePathError:permission_denied"}, HTTPStatus.FORBIDDEN)
                            return
                status, result = self.state.storage_upload(params.get("path", [""])[0], Path(filename).name, data)
                self.send_json(result, status)
            except Exception as exc:
                self.send_json({"ok": False, "error": f"{type(exc).__name__}:{exc}"}, HTTPStatus.BAD_REQUEST)
            return
        if route in {"/api/storage/rename", "/api/storage/move", "/api/storage/copy"}:
            length = int(self.headers.get("Content-Length", "0") or "0")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self.send_json({"ok": False, "error": f"invalid_json:{exc}"}, HTTPStatus.BAD_REQUEST)
                return
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            if route == "/api/storage/rename":
                source = normalize_storage_relative_path(str(payload.get("path") or ""))
                target_parent = self.state._target_parent_path(source)
                if not self.state._user_can_write(user, source) or not self.state._user_can_write(user, target_parent):
                    self.send_json({"ok": False, "error": "StoragePathError:permission_denied"}, HTTPStatus.FORBIDDEN)
                    return
                status, result = self.state.storage_rename(str(payload.get("path") or ""), str(payload.get("new_name") or ""))
            elif route == "/api/storage/move":
                source = normalize_storage_relative_path(str(payload.get("source") or ""))
                target = normalize_storage_relative_path(str(payload.get("target") or ""))
                if not self.state._user_can_write(user, source) or not self.state._user_can_write(user, self.state._target_parent_path(target)):
                    self.send_json({"ok": False, "error": "StoragePathError:permission_denied"}, HTTPStatus.FORBIDDEN)
                    return
                status, result = self.state.storage_move(str(payload.get("source") or ""), str(payload.get("target") or ""))
            else:
                source = normalize_storage_relative_path(str(payload.get("source") or ""))
                target = normalize_storage_relative_path(str(payload.get("target") or ""))
                if not self.state._user_can_read(user, source) or not self.state._user_can_write(user, self.state._target_parent_path(target)):
                    self.send_json({"ok": False, "error": "StoragePathError:permission_denied"}, HTTPStatus.FORBIDDEN)
                    return
                status, result = self.state.storage_copy(str(payload.get("source") or ""), str(payload.get("target") or ""))
            self.send_json(result, status)
            return
        if route == "/api/backup/create-task":
            length = int(self.headers.get("Content-Length", "0") or "0")
            manager = self.state.backup_manager
            if not manager:
                self.send_json({"ok": False, "error": "backup_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            source = str(payload.get("source") or "")
            dest = str(payload.get("dest") or "")
            if not Path(source).is_absolute():
                source = str(resolve_storage_path(self.state.personal_root, source, allow_root=True))
            if not Path(dest).is_absolute():
                dest = str(self.state.report_root / "nas_web_os_backups" / normalize_storage_relative_path(dest or "default"))
            result = manager.create_task(
                str(payload.get("name") or "webos-backup"),
                source,
                dest,
                int(payload.get("interval_seconds") or 0),
            )
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/backup/run":
            length = int(self.headers.get("Content-Length", "0") or "0")
            manager = self.state.backup_manager
            if not manager:
                self.send_json({"ok": False, "error": "backup_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = manager.run_backup(str(payload.get("name") or ""))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/backup/delete-task":
            length = int(self.headers.get("Content-Length", "0") or "0")
            manager = self.state.backup_manager
            if not manager:
                self.send_json({"ok": False, "error": "backup_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = manager.delete_task(str(payload.get("name") or ""))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.NOT_FOUND)
            return
        if route in {"/api/schedule/create-rule", "/api/schedule/set-enabled", "/api/schedule/run-dry"}:
            length = int(self.headers.get("Content-Length", "0") or "0")
            manager = self.state.schedule_manager
            if not manager:
                self.send_json({"ok": False, "error": "schedule_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            if user and user.get("role") != "admin":
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self.send_json({"ok": False, "error": f"invalid_json:{exc}"}, HTTPStatus.BAD_REQUEST)
                return
            if route == "/api/schedule/create-rule":
                result = manager.create_rule(
                    str(payload.get("name") or ""),
                    str(payload.get("rule_type") or "folder_summary"),
                    int(payload.get("interval_seconds") or 86400),
                    config=payload.get("config") if isinstance(payload.get("config"), dict) else {},
                    enabled=bool(payload.get("enabled", True)),
                )
                self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
                return
            if route == "/api/schedule/set-enabled":
                result = manager.set_enabled(str(payload.get("name") or ""), bool(payload.get("enabled", True)))
                self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.NOT_FOUND)
                return
            result = manager.run_dry(
                str(payload.get("name") or ""),
                personal_root=self.state.personal_root,
                index_path=self.state.sqlite_index_path,
                report_root=self.state.report_root,
                max_files=self.state.storage_max_files,
            )
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/media/index":
            length = int(self.headers.get("Content-Length", "0") or "0")
            media = self.state.media_center
            if not media:
                self.send_json({"ok": False, "error": "media_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            rel = str(payload.get("path") or "")
            root = resolve_storage_path(self.state.personal_root, rel, allow_root=True)
            result = media.index_photos(root)
            self.send_json({"ok": True, "index": result})
            return
        if route == "/api/vision/index":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            if user and user.get("role") != "admin":
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self.send_json({"ok": False, "error": f"invalid_json:{exc}"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                limit = int(payload.get("limit") or 500)
            except (TypeError, ValueError):
                limit = 500
            include_ocr = bool(payload.get("include_ocr", True))
            include_caption = bool(payload.get("include_caption", True))
            try:
                self.send_json(self.state.vision_index_payload(limit=limit, include_ocr=include_ocr, include_caption=include_caption))
            except Exception as exc:
                self.send_json({"ok": False, "error": f"{type(exc).__name__}:{exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if route == "/api/media/create-album":
            length = int(self.headers.get("Content-Length", "0") or "0")
            media = self.state.media_center
            if not media:
                self.send_json({"ok": False, "error": "media_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = media.create_album(str(payload.get("name") or ""), str(payload.get("description") or ""))
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/ops/health-check":
            length = int(self.headers.get("Content-Length", "0") or "0")
            ops = self.state.ops_manager
            if not ops:
                self.send_json({"ok": False, "error": "ops_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = ops.check_health(str(payload.get("service_name") or "ai-nas-web-os"))
            self.send_json({"ok": True, "check": result})
            return
        if route == "/api/ops/create-alert":
            length = int(self.headers.get("Content-Length", "0") or "0")
            ops = self.state.ops_manager
            if not ops:
                self.send_json({"ok": False, "error": "ops_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = ops.create_alert(
                str(payload.get("severity") or "info"),
                str(payload.get("source") or "web-os"),
                str(payload.get("message") or "operator note"),
            )
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/ops/resolve-alert":
            length = int(self.headers.get("Content-Length", "0") or "0")
            ops = self.state.ops_manager
            if not ops:
                self.send_json({"ok": False, "error": "ops_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = ops.resolve_alert(int(payload.get("alert_id") or 0))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.NOT_FOUND)
            return
        if route == "/api/apps/register-plugin":
            length = int(self.headers.get("Content-Length", "0") or "0")
            apps = self.state.app_ecosystem
            if not apps:
                self.send_json({"ok": False, "error": "app_ecosystem_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = apps.register_plugin(
                str(payload.get("name") or ""),
                str(payload.get("version") or "1.0.0"),
                str(payload.get("type") or "app"),
                str(payload.get("description") or ""),
                payload.get("config") if isinstance(payload.get("config"), dict) else {},
            )
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/apps/set-plugin-status":
            length = int(self.headers.get("Content-Length", "0") or "0")
            apps = self.state.app_ecosystem
            if not apps:
                self.send_json({"ok": False, "error": "app_ecosystem_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = apps.set_status(str(payload.get("name") or ""), str(payload.get("status") or "stopped"))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/apps/add-protocol":
            length = int(self.headers.get("Content-Length", "0") or "0")
            apps = self.state.app_ecosystem
            if not apps:
                self.send_json({"ok": False, "error": "app_ecosystem_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
            config.setdefault("implementation_state", "adapter_record_only")
            config.setdefault("protocol_daemon_started", False)
            result = apps.add_protocol(
                str(payload.get("name") or ""),
                str(payload.get("protocol") or ""),
                int(payload.get("port") or 0),
                config,
            )
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/identity/login":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = store.login(str(payload.get("username") or ""), str(payload.get("password") or ""))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.UNAUTHORIZED)
            return
        if route == "/api/identity/logout":
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            token = parse_bearer_token(self.headers.get("Authorization"))
            if not token:
                self.send_json({"ok": False, "error": "no_token"}, HTTPStatus.BAD_REQUEST)
                return
            result = store.logout(token)
            self.send_json(result)
            return
        if route == "/api/identity/create-user":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self)
            bootstrap = len(store.list_users()) == 0
            if not bootstrap and (not usr or usr.get("role") != "admin"):
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            role = str(payload.get("role") or ("admin" if bootstrap else "user"))
            result = store.create_user(str(payload.get("username") or ""), str(payload.get("password") or ""), role)
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/identity/delete-user":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self)
            if not usr or usr.get("role") != "admin":
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = store.delete_user(str(payload.get("username") or ""))
            self.send_json(result)
            return
        if route == "/api/identity/create-group":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self)
            if not usr or usr.get("role") != "admin":
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = store.create_group(str(payload.get("name") or ""))
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route in {"/api/identity/add-member", "/api/identity/remove-member"}:
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self)
            if not usr or usr.get("role") != "admin":
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            gn = str(payload.get("group") or "")
            un = str(payload.get("username") or "")
            if route.endswith("/add-member"):
                result = store.add_group_member(gn, un)
            else:
                result = store.remove_group_member(gn, un)
            self.send_json(result)
            return
        if route == "/api/identity/set-acl":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.identity_store
            if not store:
                self.send_json({"ok": False, "error": "identity_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self)
            if not usr or usr.get("role") != "admin":
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = store.set_acl(
                str(payload.get("path") or ""),
                str(payload.get("principal_type") or ""),
                str(payload.get("principal_name") or ""),
                str(payload.get("permission") or ""),
            )
            self.send_json(result)
            return
        if route == "/api/snapshot/create":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self) if _HAS_IDENTITY else None
            creator = usr["username"] if usr else ""
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = store.create_snapshot(str(payload.get("name") or ""), str(payload.get("path") or ""), creator)
            self.send_json(result, HTTPStatus.CREATED if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/snapshot/delete":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self) if _HAS_IDENTITY else None
            if usr and usr.get("role") != "admin":
                self.send_json({"ok": False, "error": "admin_required"}, HTTPStatus.FORBIDDEN)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = store.delete_snapshot(str(payload.get("name") or ""))
            self.send_json(result)
            return
        if route == "/api/snapshot/restore":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = store.restore_from_snapshot(str(payload.get("name") or ""), str(payload.get("path") or ""), str(payload.get("target") or ""))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/trash/restore":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            tid = payload.get("trash_id")
            if tid is None:
                self.send_json({"ok": False, "error": "trash_id_required"}, HTTPStatus.BAD_REQUEST)
                return
            result = store.restore_from_trash(int(tid))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/trash/empty":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            usr = self.state._identity_user(self) if _HAS_IDENTITY else None
            uname = usr["username"] if usr else ""
            result = store.empty_trash(uname)
            self.send_json(result)
            return
        if route == "/api/version/restore":
            length = int(self.headers.get("Content-Length", "0") or "0")
            store = self.state.snapshot_store
            if not store:
                self.send_json({"ok": False, "error": "snapshot_not_enabled"}, HTTPStatus.NOT_FOUND)
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            vid = payload.get("version_id")
            if vid is None:
                self.send_json({"ok": False, "error": "version_id_required"}, HTTPStatus.BAD_REQUEST)
                return
            result = store.restore_version(int(vid))
            self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
            return
        self.send_json(
            {
                "ok": False,
                "error": "not_found",
                "routes": [
                    "POST /api/refresh",
                    "POST /api/operator-decision",
                    "POST /api/schedule/create-rule",
                    "POST /api/schedule/set-enabled",
                    "POST /api/schedule/run-dry",
                    "POST /api/storage/upload",
                    "POST /api/storage/rename",
                    "POST /api/storage/move",
                    "POST /api/storage/copy",
                ],
            },
            HTTPStatus.NOT_FOUND,
        )

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
        if route == "/api/storage/file":
            rel = params.get("path", [""])[0]
            store = self.state.identity_store
            user = self.current_identity_user() if store else None
            if store and not user:
                self.send_json({"ok": False, "error": "not_authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            if not self.state._user_can_write(user, rel):
                self.send_json({"ok": False, "error": "StoragePathError:permission_denied"}, HTTPStatus.FORBIDDEN)
                return
            username = str((user or {}).get("username") or "")
            status, result = self.state.storage_delete(rel, username=username)
            self.send_json(result, status)
            return
        self.send_json({"ok": False, "error": "not_found", "routes": ["DELETE /api/storage/file"]}, HTTPStatus.NOT_FOUND)


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
    parser.add_argument("--identity-db-path", type=Path, default=None, help="Path to identity SQLite database for ACL enforcement")
    parser.add_argument("--snapshot-db-path", type=Path, default=None, help="Path to snapshot recovery SQLite database")
    parser.add_argument("--backup-db-path", type=Path, default=None, help="Path to backup/sync SQLite database")
    parser.add_argument("--media-db-path", type=Path, default=None, help="Path to media center SQLite database")
    parser.add_argument("--ops-db-path", type=Path, default=None, help="Path to operations SQLite database")
    parser.add_argument("--app-db-path", type=Path, default=None, help="Path to app ecosystem SQLite database")
    parser.add_argument("--schedule-db-path", type=Path, default=None, help="Path to scheduled organizing rules SQLite database")
    parser.add_argument("--nas-portal", action="store_true", default=False, help="Serve NAS Web OS portal instead of operator portal at /")
    parser.add_argument("--official-manager-url", default=default_official_manager_url(), help="Optional vendor NAS manager URL opened from the NAS portal.")
    parser.add_argument("--openclaw-gateway-url", default=os.environ.get("OPENCLAW_GATEWAY_URL", DEFAULT_OPENCLAW_GATEWAY_URL), help="OpenClaw control gateway base URL.")
    parser.add_argument("--openclaw-model-gateway-url", default=os.environ.get("OPENCLAW_MODEL_GATEWAY_URL", DEFAULT_OPENCLAW_MODEL_GATEWAY_URL), help="OpenAI-compatible model gateway used by OpenClaw chat.")
    parser.add_argument("--openclaw-model", default=os.environ.get("OPENCLAW_MODEL", DEFAULT_OPENCLAW_MODEL), help="Model id used for OpenClaw chat.")
    parser.add_argument("--qwen-gateway-url", default=os.environ.get("OPENCLAW_QWEN_GATEWAY_URL", DEFAULT_QWEN_GATEWAY_URL), help="OpenAI-compatible Qwen gateway base URL.")
    parser.add_argument("--qwen-model", default=os.environ.get("OPENCLAW_QWEN_MODEL", DEFAULT_QWEN_MODEL), help="Model id used for NAS Copilot chat.")
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--storage-max-files", type=int, default=50000)
    parser.add_argument("--no-refresh", action="store_true", help="Serve the latest existing portal report without generating a fresh one on start.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nas_portal_path = Path(__file__).with_name("nas_web_os_portal.html")
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
        storage_max_files=args.storage_max_files,
        identity_db_path=args.identity_db_path,
        snapshot_db_path=args.snapshot_db_path,
        backup_db_path=args.backup_db_path,
        media_db_path=args.media_db_path,
        ops_db_path=args.ops_db_path,
        app_db_path=args.app_db_path,
        schedule_db_path=args.schedule_db_path,
        nas_portal_enabled=args.nas_portal,
        nas_portal_path=nas_portal_path,
        official_manager_url=args.official_manager_url,
        openclaw_gateway_url=args.openclaw_gateway_url,
        openclaw_model_gateway_url=args.openclaw_model_gateway_url,
        openclaw_model=args.openclaw_model,
        qwen_gateway_url=args.qwen_gateway_url,
        qwen_model=args.qwen_model,
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
