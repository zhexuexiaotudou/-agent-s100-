#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import mimetypes
import zipfile
import threading
import tempfile
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from src.harness.token_budget_integration import TokenBudgetIntegration
except Exception:
    TokenBudgetIntegration = None  # type: ignore[assignment]

try:
    from src.digua_journal.event_model import redact_private_text
except Exception:
    def redact_private_text(text: object) -> tuple[str, int]:  # type: ignore[no-redef]
        return str(text or ""), 0

try:
    from src.openclaw.routes.agent_runtime_routes import agent_runtime_route_response
    from src.openclaw.routes.harness_status_routes import harness_status_response
    from src.openclaw.routes.journal_routes import journal_route_response
    from src.openclaw.routes.multimodal_search_routes import multimodal_route_response
    from src.openclaw.routes.nas_copy_routes import (
        copy_confirm_response,
        copy_dry_run_response,
        copy_execute_response,
        copy_preview_response,
        copy_rollback_response,
    )
except Exception:
    agent_runtime_route_response = None  # type: ignore[assignment]
    harness_status_response = None  # type: ignore[assignment]
    journal_route_response = None  # type: ignore[assignment]
    multimodal_route_response = None  # type: ignore[assignment]
    copy_preview_response = None  # type: ignore[assignment]
    copy_dry_run_response = None  # type: ignore[assignment]
    copy_confirm_response = None  # type: ignore[assignment]
    copy_execute_response = None  # type: ignore[assignment]
    copy_rollback_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.yolo_index_routes import yolo_route_response
except Exception:
    yolo_route_response = None  # type: ignore[assignment]

try:
    from src.yolo_index.labels import labels_from_query
except Exception:
    def labels_from_query(query: str) -> list[str]:  # type: ignore[no-redef]
        text = str(query or "").lower()
        labels: list[str] = []
        if any(term in text for term in ["person", "people"]) or any(term in str(query or "") for term in ["人", "人物", "行人", "有人"]):
            labels.append("person")
        if any(term in text for term in ["car", "vehicle"]) or any(term in str(query or "") for term in ["车", "汽车"]):
            labels.append("car")
        return labels

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
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_QWEN_GATEWAY_URL = "http://127.0.0.1:18080"
DEFAULT_QWEN_MODEL = "Qwen2.5-1.5B-Instruct-S100P-official"
COPILOT_SEARCH_VERBS = (
    "search",
    "find",
    "locate",
    "show",
    "list",
    "搜索",
    "查找",
    "检索",
    "寻找",
    "找",
    "列出",
    "显示",
    "看看",
)
COPILOT_NAS_SCOPE_TERMS = ("nas", "个人盘", "网盘", "文件", "文档", "照片", "图片", "图像", "相册", "视频", "file", "document", "photo", "image", "picture", "video")
COPILOT_IMAGE_TERMS = ("photo", "image", "picture", "照片", "图片", "图像", "相册")
COPILOT_VIDEO_TERMS = ("video", "movie", "clip", "视频", "录像", "影片")
COPILOT_DOCUMENT_TERMS = ("document", "doc", "pdf", "invoice", "file", "文档", "文件", "发票", "合同", "报告")
COPILOT_PRIVACY_TERMS = (
    "nas",
    "personal",
    "private",
    "local",
    "file",
    "document",
    "photo",
    "image",
    "video",
    "audio",
    "invoice",
    "contract",
    "password",
    "token",
    "secret",
    "\u79c1\u4eba",
    "\u9690\u79c1",
    "\u672c\u5730",
    "\u6587\u4ef6",
    "\u6587\u6863",
    "\u7167\u7247",
    "\u56fe\u7247",
    "\u56fe\u50cf",
    "\u89c6\u9891",
    "\u97f3\u9891",
    "\u53d1\u7968",
    "\u5408\u540c",
    "\u5bc6\u7801",
    "\u4ee4\u724c",
)
COPILOT_STRONG_PRIVACY_TERMS = (
    "private",
    "personal",
    "photo",
    "image",
    "video",
    "audio",
    "invoice",
    "contract",
    "password",
    "token",
    "secret",
    "\u79c1\u4eba",
    "\u9690\u79c1",
    "\u7167\u7247",
    "\u56fe\u7247",
    "\u56fe\u50cf",
    "\u89c6\u9891",
    "\u97f3\u9891",
    "\u53d1\u7968",
    "\u5408\u540c",
    "\u5bc6\u7801",
    "\u4ee4\u724c",
)
COPILOT_LOCAL_CONTENT_TERMS = ("nas", "local", "file", "document", "\u672c\u5730", "\u6587\u4ef6", "\u6587\u6863")
COPILOT_PUBLIC_ONLY_TERMS = ("public", "non-private", "non private", "do not reference local", "\u516c\u5f00", "\u975e\u9690\u79c1", "\u4e0d\u5f15\u7528\u672c\u5730")
COPILOT_PUBLIC_COMPLEX_TERMS = (
    "market",
    "strategy",
    "industry",
    "trend",
    "launch",
    "competitor",
    "public",
    "\u5e02\u573a",
    "\u6218\u7565",
    "\u884c\u4e1a",
    "\u8d8b\u52bf",
    "\u53d1\u5e03",
    "\u7ade\u54c1",
    "\u516c\u5f00",
)
COPILOT_RENAME_TERMS = ("rename", "renamed", "\u91cd\u547d\u540d", "\u6539\u540d")
COPILOT_COPY_TERMS = ("copy", "duplicate", "\u590d\u5236", "\u62f7\u8d1d")
COPILOT_LIST_TERMS = ("list", "open", "browse", "show files", "\u5217\u51fa", "\u6253\u5f00", "\u6d4f\u89c8", "\u770b\u770b", "\u76ee\u5f55")
COPILOT_INSPECT_TERMS = (
    "inspect",
    "check path",
    "path status",
    "file info",
    "folder info",
    "\u68c0\u67e5",
    "\u67e5\u770b\u8def\u5f84",
    "\u68c0\u67e5\u8def\u5f84",
    "\u67e5\u770b\u6587\u4ef6\u5939",
    "\u68c0\u67e5\u6587\u4ef6\u5939",
    "\u6587\u4ef6\u5939\u72b6\u6001",
    "\u8def\u5f84\u72b6\u6001",
)
COPILOT_CREATE_FOLDER_TERMS = ("create folder", "new folder", "mkdir", "\u65b0\u5efa\u6587\u4ef6\u5939", "\u521b\u5efa\u6587\u4ef6\u5939")
COPILOT_SNAPSHOT_TERMS = ("snapshot", "\u5feb\u7167")
COPILOT_BACKUP_TERMS = ("backup", "sync", "\u5907\u4efd", "\u540c\u6b65")
COPILOT_RUN_TERMS = ("run", "execute", "start", "\u8fd0\u884c", "\u6267\u884c", "\u5f00\u59cb")
COPILOT_MEDIA_TERMS = ("media", "photo", "album", "movie", "\u5a92\u4f53", "\u7167\u7247", "\u76f8\u518c", "\u7535\u5f71")
COPILOT_INDEX_TERMS = ("index", "rebuild", "scan", "\u7d22\u5f15", "\u91cd\u5efa", "\u626b\u63cf")
COPILOT_ALBUM_TERMS = ("album", "\u76f8\u518c")
COPILOT_JOURNAL_TERMS = ("journal", "diary", "log", "\u65e5\u8bb0", "\u65e5\u5fd7")
COPILOT_SUMMARY_TERMS = ("summary", "summarize", "report", "\u603b\u7ed3", "\u6458\u8981", "\u62a5\u544a", "\u5468\u62a5")
COPILOT_DOCUMENT_QUERY_TERMS = (
    "document",
    "doc",
    "pdf",
    "invoice",
    "contract",
    "rag",
    "\u6587\u6863",
    "\u6587\u4ef6",
    "\u53d1\u7968",
    "\u5408\u540c",
    "\u95ee\u7b54",
)
COPILOT_STATUS_TERMS = ("status", "health", "summary", "list", "report", "audit", "\u72b6\u6001", "\u5065\u5eb7", "\u6982\u89c8", "\u6c47\u603b", "\u5217\u8868", "\u62a5\u544a", "\u5ba1\u8ba1")


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


def normalize_chat_completions_url(base_or_url: str) -> str:
    text = base_or_url.rstrip("/")
    if text.endswith("/v1/chat/completions") or text.endswith("/chat/completions"):
        return text
    if text.endswith("/v1"):
        return f"{text}/chat/completions"
    return f"{text}/v1/chat/completions"


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def infer_copilot_search_intent(message: str) -> dict | None:
    text = str(message or "").strip()
    if not text:
        return None
    lower = text.lower()
    has_search_verb = contains_any(text, COPILOT_SEARCH_VERBS)
    has_nas_scope = contains_any(text, COPILOT_NAS_SCOPE_TERMS)
    labels = labels_from_query(text)
    has_image = contains_any(text, COPILOT_IMAGE_TERMS)
    has_video = contains_any(text, COPILOT_VIDEO_TERMS)
    has_document = contains_any(text, COPILOT_DOCUMENT_TERMS)
    if not has_search_verb or not (has_nas_scope or labels):
        return None
    modality = "all"
    if has_image and not has_video:
        modality = "image"
    elif has_video and not has_image:
        modality = "video"
    elif has_document and not (has_image or has_video):
        modality = "document"
    prefer_yolo = bool(labels) and modality in {"all", "image", "video"}
    return {
        "query": text,
        "query_lower": lower,
        "modality": modality,
        "labels": labels,
        "prefer_yolo": prefer_yolo,
        "search_verb_detected": has_search_verb,
    }


def copilot_quoted_segments(message: str) -> list[str]:
    pattern = "\"([^\"]+)\"|'([^']+)'|\u201c([^\u201d]+)\u201d|\u300c([^\u300d]+)\u300d|\u300e([^\u300f]+)\u300f"
    segments: list[str] = []
    for match in re.findall(pattern, str(message or "")):
        value = next((part for part in match if part), "")
        if value:
            segments.append(value.strip())
    return segments


def copilot_default_path_for_message(message: str, fallback: str = "") -> str:
    text = str(message or "")
    lower = text.lower()
    if "documents" in lower or "\u6587\u6863" in text:
        return "Documents"
    if "photos" in lower or "pictures" in lower or "\u7167\u7247" in text or "\u76f8\u518c" in text:
        return "Photos"
    if "videos" in lower or "movies" in lower or "\u89c6\u9891" in text or "\u7535\u5f71" in text:
        return "Videos"
    if "reports" in lower or "\u62a5\u544a" in text:
        return "Reports"
    if "root" in lower or "\u6839\u76ee\u5f55" in text:
        return ""
    return fallback


def copilot_action_tool_id(action: str | None) -> str | None:
    if not action:
        return None
    mapping = {
        "search": "local_nas_search",
        "document_query": "local_document_rag",
        "storage_list": "local_storage_list",
        "storage_list_or_inspect": "local_storage_list_or_inspect",
        "storage_inspect": "local_storage_inspect",
        "storage_copy": "harness_copy_route",
        "storage_rename": "disabled_rename_guardrail",
        "storage_create_folder": "local_storage_create_folder",
        "snapshot_create": "local_snapshot_create",
        "backup_create_task": "local_backup_create_task",
        "backup_run": "local_backup_run",
        "media_index": "local_media_index",
        "media_create_album": "local_media_create_album",
        "media_summary": "local_media_summary",
        "journal_summary": "local_journal_summary",
        "journal_manual_entry": "local_journal_manual_entry",
        "storage_status": "local_storage_status",
        "ops_summary": "local_ops_summary",
        "apps_summary": "local_apps_summary",
        "audit_summary": "local_audit_summary",
        "reports_list": "local_reports_list",
    }
    return mapping.get(action, action)


def infer_copilot_action_intent(message: str) -> dict | None:
    text = str(message or "").strip()
    if not text:
        return None
    quoted = copilot_quoted_segments(text)
    search_intent = infer_copilot_search_intent(text)
    has_snapshot = contains_any(text, COPILOT_SNAPSHOT_TERMS)
    has_backup = contains_any(text, COPILOT_BACKUP_TERMS)
    has_media = contains_any(text, COPILOT_MEDIA_TERMS)
    has_index = contains_any(text, COPILOT_INDEX_TERMS)
    has_album = contains_any(text, COPILOT_ALBUM_TERMS)
    has_journal = contains_any(text, COPILOT_JOURNAL_TERMS)
    has_summary = contains_any(text, COPILOT_SUMMARY_TERMS)
    has_document = contains_any(text, COPILOT_DOCUMENT_QUERY_TERMS)
    has_status = contains_any(text, COPILOT_STATUS_TERMS)
    has_inspect = contains_any(text, COPILOT_INSPECT_TERMS)
    if has_snapshot:
        return {
            "action": "snapshot_create",
            "path": quoted[0] if quoted else copilot_default_path_for_message(text),
            "name": quoted[1] if len(quoted) >= 2 else f"assistant-snapshot-{compact_timestamp()}",
            "quoted": quoted,
        }
    if has_backup:
        if contains_any(text, COPILOT_RUN_TERMS):
            return {"action": "backup_run", "name": quoted[0] if quoted else "", "quoted": quoted}
        return {
            "action": "backup_create_task",
            "source": quoted[0] if len(quoted) >= 1 else "",
            "dest": quoted[1] if len(quoted) >= 2 else "",
            "name": quoted[2] if len(quoted) >= 3 else f"assistant-backup-{compact_timestamp()}",
            "quoted": quoted,
        }
    if has_media and has_album and ("create" in text.lower() or "\u521b\u5efa" in text or "\u65b0\u5efa" in text):
        return {
            "action": "media_create_album",
            "name": quoted[0] if quoted else "",
            "description": quoted[1] if len(quoted) >= 2 else "",
            "quoted": quoted,
        }
    if has_media and has_index:
        return {"action": "media_index", "path": quoted[0] if quoted else copilot_default_path_for_message(text, "Photos"), "quoted": quoted}
    if has_journal and has_summary:
        period = "weekly" if "week" in text.lower() or "\u5468" in text else "daily"
        return {"action": "journal_summary", "period_type": period, "project_id": "all", "quoted": quoted}
    if has_journal and ("write" in text.lower() or "record" in text.lower() or "\u8bb0" in text or "\u5199" in text):
        return {
            "action": "journal_manual_entry",
            "project_id": "manual",
            "title": quoted[0] if quoted else "",
            "body": quoted[1] if len(quoted) >= 2 else "",
            "quoted": quoted,
        }
    if contains_any(text, COPILOT_CREATE_FOLDER_TERMS):
        return {"action": "storage_create_folder", "path": quoted[0] if quoted else "", "quoted": quoted}
    if has_inspect:
        inspect_path = quoted[0] if quoted else copilot_default_path_for_message(text)
        if inspect_path or quoted or "root" in text.lower() or "\u6839\u76ee\u5f55" in text:
            return {"action": "storage_list_or_inspect", "path": inspect_path, "quoted": quoted}
    if has_document and (has_summary or "query" in text.lower() or "\u67e5" in text or "\u627e" in text or "\u95ee" in text):
        return {
            "action": "document_query",
            "query": text,
            "path": quoted[0] if quoted and ("/" in quoted[0] or "\\" in quoted[0]) else copilot_default_path_for_message(text, "Documents"),
            "quoted": quoted,
        }
    lower = text.lower()
    if has_status and ("storage" in lower or "nas" in lower or "\u5b58\u50a8" in text):
        return {"action": "storage_status", "quoted": quoted}
    if has_status and ("media" in lower or "\u5a92\u4f53" in text or "\u76f8\u518c" in text):
        return {"action": "media_summary", "quoted": quoted}
    if has_status and ("ops" in lower or "health" in lower or "\u8fd0\u884c" in text or "\u5065\u5eb7" in text):
        return {"action": "ops_summary", "quoted": quoted}
    if has_status and ("app" in lower or "plugin" in lower or "\u5e94\u7528" in text or "\u63d2\u4ef6" in text):
        return {"action": "apps_summary", "quoted": quoted}
    if has_status and ("audit" in lower or "\u5ba1\u8ba1" in text):
        return {"action": "audit_summary", "quoted": quoted}
    if has_status and ("report" in lower or "\u62a5\u544a" in text):
        return {"action": "reports_list", "quoted": quoted}
    if len(quoted) >= 2:
        action = "storage_rename" if contains_any(text, COPILOT_RENAME_TERMS) or "renamed" in quoted[1].lower() else "storage_copy"
        return {"action": action, "source": quoted[0], "target": quoted[1], "quoted": quoted}
    if quoted:
        return {"action": "storage_list_or_inspect", "path": quoted[0], "quoted": quoted}
    if contains_any(text, COPILOT_LIST_TERMS):
        return {"action": "storage_list", "path": copilot_default_path_for_message(text), "quoted": quoted}
    if search_intent:
        return {"action": "search", "search_intent": search_intent, "quoted": quoted}
    return None


def build_copilot_qwen_router_prompt(message: str) -> str:
    return (
        "You are the local Qwen router for Digua AI-NAS. Classify the original user query. "
        "Do not answer the user. Return exactly one JSON object with keys: "
        "route, privacy_level, task_complexity, reason, local_tool_id. "
        "route must be local or cloud. privacy_level must be none, low, medium, or high. "
        "Use local for private NAS data, local files, photos, invoices, contracts, backups, "
        "snapshots, media search, storage actions, journal actions, or any uncertain request. "
        "Use cloud only for public non-private complex reasoning. Qwen must not execute tools. "
        f"Original user query:\n{message}"
    )


def chat_completion_content(result: dict) -> tuple[str, dict, dict]:
    upstream = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    choices = upstream.get("choices") if isinstance(upstream.get("choices"), list) else []
    first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message_payload = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
    content = str(message_payload.get("content") or "")
    metadata = message_payload.get("metadata") if isinstance(message_payload.get("metadata"), dict) else {}
    return content, metadata, upstream


def parse_json_object_from_text(text: str) -> dict | None:
    content = str(text or "").strip()
    if not content:
        return None
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(r"\s*```$", "", content).strip()
    candidates = [content]
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        candidates.append(content[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def normalize_copilot_router(parsed: dict, *, classifier: str, raw_content: str = "", elapsed_ms: object = None) -> dict | None:
    route = str(parsed.get("route") or "").lower()
    if route not in {"local", "cloud"}:
        return None
    privacy_level = str(parsed.get("privacy_level") or "none").lower().replace("-", "_")
    if privacy_level in {"public", "non_private", "nonprivate"}:
        privacy_level = "none"
    if privacy_level not in {"none", "low", "medium", "high"}:
        privacy_level = "none"
    task_complexity = str(parsed.get("task_complexity") or ("complex" if route == "cloud" else "simple")).lower()
    if task_complexity not in {"simple", "complex"}:
        task_complexity = "complex" if route == "cloud" else "simple"
    local_tool_id = parsed.get("local_tool_id")
    if local_tool_id in {"", "none", "null"}:
        local_tool_id = None
    return {
        "route": route,
        "privacy_level": privacy_level,
        "task_complexity": task_complexity,
        "reason": str(parsed.get("reason") or "Qwen returned a structured route."),
        "local_tool_id": local_tool_id,
        "classifier": classifier,
        "raw_content_preview": raw_content[:500],
        "elapsed_ms": elapsed_ms,
        "original_query_sent": True,
        "qwen_execution_authority": False,
    }


def copilot_policy_route(message: str, action_intent: dict | None = None) -> dict:
    text = str(message or "")
    has_public_complex = contains_any(text, COPILOT_PUBLIC_COMPLEX_TERMS) or len(text) > 160
    explicit_public_only = contains_any(text, COPILOT_PUBLIC_ONLY_TERMS)
    if contains_any(text, COPILOT_STRONG_PRIVACY_TERMS) and not (has_public_complex and explicit_public_only and not contains_any(text, ("invoice", "contract", "password", "token", "\u53d1\u7968", "\u5408\u540c", "\u5bc6\u7801", "\u4ee4\u724c"))):
        privacy_level = "high"
    elif contains_any(text, COPILOT_LOCAL_CONTENT_TERMS) and not (has_public_complex and explicit_public_only):
        privacy_level = "medium"
    else:
        privacy_level = "none"
    local_tool_id = copilot_action_tool_id((action_intent or {}).get("action"))
    if local_tool_id or privacy_level != "none" or not has_public_complex:
        route = "local"
        reason = "local route required by NAS action, privacy floor, or simple request"
    else:
        route = "cloud"
        reason = "public non-private complex request may use cloud overflow"
    return {
        "route": route,
        "privacy_level": privacy_level,
        "task_complexity": "complex" if has_public_complex else "simple",
        "reason": reason,
        "local_tool_id": local_tool_id,
        "classifier": "portal_policy_guardrail",
        "original_query_sent": False,
        "qwen_execution_authority": False,
    }


def apply_copilot_guardrail(qwen_route: dict | None, policy_route: dict) -> dict:
    route = dict(qwen_route or policy_route)
    route.setdefault("classifier", "portal_policy_guardrail")
    route["policy_route"] = {
        "route": policy_route.get("route"),
        "privacy_level": policy_route.get("privacy_level"),
        "task_complexity": policy_route.get("task_complexity"),
        "local_tool_id": policy_route.get("local_tool_id"),
    }
    if policy_route.get("privacy_level") in {"medium", "high"} or policy_route.get("local_tool_id"):
        if route.get("route") != "local":
            route["guardrail_applied"] = True
            route["guardrail_reason"] = "privacy or local NAS tool intent cannot be sent to cloud"
        route["route"] = "local"
        route["privacy_level"] = policy_route.get("privacy_level") or route.get("privacy_level") or "none"
        route["local_tool_id"] = policy_route.get("local_tool_id") or route.get("local_tool_id")
    elif policy_route.get("route") == "cloud" and policy_route.get("privacy_level") == "none" and not policy_route.get("local_tool_id"):
        if route.get("route") != "cloud":
            route["guardrail_applied"] = True
            route["guardrail_reason"] = "explicit public non-private complex request can use cloud overflow"
        route["route"] = "cloud"
        route["privacy_level"] = "none"
        route["local_tool_id"] = None
    route["qwen_execution_authority"] = False
    return route


def summarize_search_result_titles(results: list[dict], limit: int = 3) -> str:
    titles: list[str] = []
    for item in results[:limit]:
        display = item.get("display") if isinstance(item.get("display"), dict) else {}
        title = str(display.get("name") or item.get("title_redacted") or item.get("name") or item.get("asset_id") or "").strip()
        if title:
            titles.append(title)
    return "、".join(titles)


def mtime_to_display(value: object) -> str:
    try:
        return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def bytes_to_display(value: object) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    if idx == 0:
        return f"{int(size)} {units[idx]}"
    return f"{size:.1f} {units[idx]}"


def modality_display_label(modality: object, file_type: object = None) -> str:
    normalized = str(modality or "").lower()
    file_norm = str(file_type or "").lower()
    if normalized == "image" or file_norm in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
        return "照片"
    if normalized == "video" or file_norm in {".mp4", ".mov", ".mkv", ".avi"}:
        return "视频"
    if normalized == "document":
        return "文档"
    if normalized == "audio":
        return "音频"
    return "文件"


def privacy_display_label(value: object) -> str:
    normalized = str(value or "").lower()
    if "private" in normalized or normalized in {"high", "local_only"}:
        return "本地私有"
    if normalized in {"medium", "internal"}:
        return "本地受限"
    if normalized in {"none", "public", "low"}:
        return "普通"
    return "本地保护"


def object_label_display(label: object, label_zh_value: object = None) -> str:
    zh = str(label_zh_value or "").strip()
    if zh and zh.lower() != str(label or "").lower():
        return zh
    mapping = {
        "person": "人物",
        "car": "车辆",
        "bus": "公交车",
        "truck": "卡车",
        "bicycle": "自行车",
        "motorcycle": "摩托车",
        "dog": "宠物",
        "cat": "宠物",
        "book": "书本",
        "laptop": "电脑",
        "keyboard": "键盘",
        "mouse": "鼠标",
        "kite": "风筝",
    }
    return mapping.get(str(label or "").lower(), str(label or "目标"))


def search_result_match_display(item: dict) -> tuple[str, float | None]:
    detections = item.get("detections") if isinstance(item.get("detections"), list) else []
    best = None
    for det in detections:
        if not isinstance(det, dict):
            continue
        if best is None or float(det.get("confidence") or 0) > float(best.get("confidence") or 0):
            best = det
    if best:
        return object_label_display(best.get("label"), best.get("label_zh")), float(best.get("confidence") or 0)
    labels = item.get("object_labels") if isinstance(item.get("object_labels"), list) else []
    if labels:
        return object_label_display(labels[0]), float(item.get("score") or 0)
    return "本地索引匹配", float(item.get("score") or 0) if item.get("score") is not None else None


def sanitize_copilot_search_result(item: dict) -> dict:
    allowed = {
        "rank",
        "asset_id",
        "keyframe_id",
        "title_redacted",
        "modality",
        "file_type",
        "size_bytes",
        "mtime",
        "score",
        "matched_by",
        "object_labels",
        "detections",
        "evidence_ref",
        "timestamp_sec",
        "path_hash",
        "privacy_level",
        "score_components",
        "display",
        "preview_url",
        "preview_kind",
    }
    return {key: value for key, value in item.items() if key in allowed}


def http_post_json(name: str, url: str, payload: dict, timeout: int = 60) -> dict:
    started = time.perf_counter()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            try:
                payload_out = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload_out = {"raw": raw[:2000]}
            return {
                "name": name,
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "elapsed_ms": elapsed_ms,
                "url": url,
                "payload": payload_out,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(65536).decode("utf-8", errors="replace")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        try:
            payload_out = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload_out = {"raw": raw[:2000]}
        return {
            "name": name,
            "ok": False,
            "status": exc.code,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "payload": payload_out,
            "error": str(exc),
        }
    except urllib.error.URLError as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "name": name,
            "ok": False,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "payload": {},
            "error": str(exc),
        }


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

DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".rst", ".docx", ".pdf"}
TEXT_DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".rst"}


def extract_docx_text(path: Path, *, max_chars: int = 20000) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return ""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    parts = [node.text or "" for node in root.findall(".//w:t", ns)]
    return " ".join(part for part in parts if part).strip()[:max_chars]


def extract_local_document_text(path: Path, *, max_chars: int = 20000) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(path, max_chars=max_chars)
    if suffix not in TEXT_DOCUMENT_EXTENSIONS:
        return ""
    try:
        raw = path.read_bytes()[: max_chars * 4]
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")[:max_chars]


def query_terms(query: str) -> list[str]:
    cleaned = query.strip().lower()
    parts = [item for item in re.split(r"[\s,，。；;:：/\\|()（）]+", cleaned) if len(item) >= 2]
    if cleaned and cleaned not in parts:
        parts.insert(0, cleaned)
    return parts[:12]


def local_snippet(text: str, terms: list[str], *, max_chars: int = 180) -> str:
    if not text:
        return ""
    lower = text.lower()
    index = -1
    for term in terms:
        index = lower.find(term)
        if index >= 0:
            break
    if index < 0:
        index = 0
    start = max(0, index - 40)
    snippet = text[start : start + max_chars].replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", snippet).strip()


def sqlite_readonly_uri(path: Path) -> str:
    resolved = path.resolve(strict=False)
    return "file:" + quote(str(resolved), safe="/:\\") + "?mode=ro"


def readonly_sqlite_summary(db_path: Path | None) -> dict:
    if not db_path:
        return {"configured": False, "ok": True, "status": "not_configured", "operation_log_count": 0}
    if not db_path.exists():
        return {"configured": True, "ok": True, "status": "missing", "path": str(db_path), "operation_log_count": 0}
    try:
        con = sqlite3.connect(sqlite_readonly_uri(db_path), uri=True)
        try:
            row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_operations'").fetchone()
            count = 0
            if row:
                count = int(con.execute("SELECT COUNT(*) FROM file_operations").fetchone()[0])
            return {
                "configured": True,
                "ok": True,
                "status": "readonly_ok",
                "path": str(db_path),
                "operation_log_count": count,
            }
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        return {
            "configured": True,
            "ok": False,
            "status": "degraded",
            "path": str(db_path),
            "operation_log_count": None,
            "error": f"{type(exc).__name__}:{exc}",
        }
    except OSError as exc:
        return {
            "configured": True,
            "ok": False,
            "status": "degraded",
            "path": str(db_path),
            "operation_log_count": None,
            "error": f"{type(exc).__name__}:{exc}",
        }


def split_document_chunks(text: str, *, chunk_chars: int = 900) -> list[str]:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return []
    return [compact[index : index + chunk_chars] for index in range(0, min(len(compact), 20000), chunk_chars)]


def fts_query_from_terms(terms: list[str]) -> str:
    cleaned: list[str] = []
    for term in terms:
        token = re.sub(r"[^\w\u4e00-\u9fff]+", " ", term, flags=re.UNICODE).strip()
        if not token:
            continue
        cleaned.extend(part for part in token.split() if part)
    if not cleaned:
        return ""
    return " OR ".join(f'"{item}"' for item in cleaned[:12])


def init_document_fts_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents(
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              file_path_hash TEXT NOT NULL,
              file_type TEXT NOT NULL,
              relative_path TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS document_chunks(
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              chunk_index INTEGER NOT NULL,
              redacted_text TEXT NOT NULL,
              source_hash TEXT NOT NULL,
              page_no INTEGER
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts
              USING fts5(chunk_id UNINDEXED, redacted_text, source_hash UNINDEXED, tokenize='unicode61');
            """
        )
        con.commit()
    finally:
        con.close()


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
        operation_db_path: Path | None = None,
        document_fts_db_path: Path | None = None,
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
        qwen_model: str | None = None,
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
        self.operation_db_path = operation_db_path
        self.document_fts_db_path = document_fts_db_path
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
        self.qwen_gateway_url = (qwen_gateway_url or DEFAULT_QWEN_GATEWAY_URL).rstrip("/")
        self.qwen_model = qwen_model or DEFAULT_QWEN_MODEL
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
            self.operation_db_path = self.operation_db_path or (self.report_root / "operator_portal_operations.sqlite3")
            self.document_fts_db_path = self.document_fts_db_path or (self.report_root / "document_fts.sqlite3")
            self.identity_db_path = self.identity_db_path or (self.report_root / "identity.sqlite3")
            self.snapshot_db_path = self.snapshot_db_path or (self.report_root / "snapshot.sqlite3")
            self.backup_db_path = self.backup_db_path or (self.report_root / "backup.sqlite3")
            self.media_db_path = self.media_db_path or (self.report_root / "media.sqlite3")
            self.ops_db_path = self.ops_db_path or (self.report_root / "ops.sqlite3")
            self.app_db_path = self.app_db_path or (self.report_root / "apps.sqlite3")
            self.report_root.mkdir(parents=True, exist_ok=True)
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

    def storage_file_by_path_hash(
        self,
        path_hash: str,
        user: dict,
        cache: dict[str, tuple[Path | None, str | None]] | None = None,
    ) -> tuple[Path | None, str | None]:
        digest = str(path_hash or "").strip().lower()
        if not self.personal_root or not re.fullmatch(r"[0-9a-f]{64}", digest):
            return None, None
        if cache is not None and digest in cache:
            return cache[digest]
        scanned = 0
        found: tuple[Path | None, str | None] = (None, None)
        roots: list[tuple[Path, bool]] = [(self.personal_root, True)]
        yolo_fixture_root = self.personal_root.parent / "yolo_v2_fixture" / "images"
        if yolo_fixture_root.exists():
            roots.append((yolo_fixture_root, False))
        for root, requires_acl in roots:
            for path in root.rglob("*"):
                if scanned >= self.storage_max_files:
                    break
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                    scanned += 1
                    if not requires_acl and path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
                        continue
                    current_hash = hashlib.sha256(str(path.resolve()).encode("utf-8", errors="replace")).hexdigest()
                    if current_hash != digest:
                        continue
                    if requires_acl:
                        relative_path = path.relative_to(self.personal_root).as_posix()
                        if self.can_read(user, relative_path):
                            found = (path, relative_path)
                            break
                    else:
                        found = (path, None)
                        break
                except OSError:
                    continue
            if found[0] is not None or scanned >= self.storage_max_files:
                break
        if cache is not None:
            cache[digest] = found
        return found

    def can_write(self, user: dict, relative_path: str) -> bool:
        if not self.identity_store:
            return False
        return self.identity_store.check_acl(str(user.get("username") or ""), relative_path, "write")

    def storage_status_payload(self) -> dict:
        if not self.personal_root:
            return {"ok": False, "error": "personal_root_not_configured"}
        payload = storage_status(self.personal_root, None)
        inventory = readonly_sqlite_summary(self.sqlite_index_path)
        operation_log = readonly_sqlite_summary(self.operation_db_path)
        payload["sqlite_index_path"] = str(self.sqlite_index_path) if self.sqlite_index_path else None
        payload["sqlite_readonly_status"] = inventory
        payload["operation_db_path"] = str(self.operation_db_path) if self.operation_db_path else None
        payload["operation_log_count"] = operation_log.get("operation_log_count")
        payload["operation_log_status"] = operation_log
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

    def document_items_payload(self, relative_path: str = "Documents", user: dict | None = None, *, limit: int = 250) -> tuple[int, dict]:
        if not self.personal_root:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "personal_root_not_configured"}
        rel = normalize_storage_relative_path(relative_path or "Documents")
        if user and not self.can_read(user, rel):
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "read", "path": rel}
        try:
            root = resolve_storage_path(self.personal_root, rel)
        except StoragePathError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
        if not root.exists():
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "document_path_not_found", "path": rel}
        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for path in root.rglob("*"):
                if len(candidates) >= limit:
                    break
                if path.is_symlink() or not path.is_file():
                    continue
                if path.suffix.lower() not in DOCUMENT_EXTENSIONS:
                    continue
                candidates.append(path)
        items = []
        for path in candidates:
            item_rel = path.relative_to(self.personal_root).as_posix()
            if user and not self.can_read(user, item_rel):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append(
                {
                    "relative_path": item_rel,
                    "name": path.name,
                    "extension": path.suffix,
                    "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "size_bytes": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "is_dir": False,
                    "text_extractable": path.suffix.lower() in TEXT_DOCUMENT_EXTENSIONS or path.suffix.lower() == ".docx",
                }
            )
        return HTTPStatus.OK, {"ok": True, "path": rel, "items": items, "truncated": len(items) >= limit}

    def sync_document_fts_index(self, relative_path: str, user: dict | None = None) -> tuple[int, dict]:
        if not self.document_fts_db_path:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "document_fts_db_not_configured"}
        status, payload = self.document_items_payload(relative_path, user, limit=500)
        if status != HTTPStatus.OK:
            return status, payload
        try:
            init_document_fts_db(self.document_fts_db_path)
            con = sqlite3.connect(str(self.document_fts_db_path))
            con.execute("PRAGMA foreign_keys=ON")
        except sqlite3.DatabaseError as exc:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": f"document_fts_init_failed:{type(exc).__name__}:{exc}"}
        indexed_docs = 0
        indexed_chunks = 0
        try:
            with con:
                for item in payload.get("items") or []:
                    rel = str(item.get("relative_path") or "")
                    if not rel:
                        continue
                    path = resolve_storage_path(self.personal_root, rel) if self.personal_root else Path(rel)
                    text = extract_local_document_text(path)
                    chunks = split_document_chunks(text)
                    if not chunks:
                        continue
                    doc_id = hashlib.sha256(rel.encode("utf-8", errors="replace")).hexdigest()
                    file_path_hash = hashlib.sha256(str(path).encode("utf-8", errors="replace")).hexdigest()
                    con.execute(
                        """
                        INSERT OR REPLACE INTO documents(id,title,file_path_hash,file_type,relative_path,updated_at)
                        VALUES(?,?,?,?,?,?)
                        """,
                        (
                            doc_id,
                            str(item.get("name") or path.name),
                            file_path_hash,
                            str(item.get("extension") or path.suffix),
                            rel,
                            str(item.get("mtime") or datetime.fromtimestamp(path.stat().st_mtime).isoformat()),
                        ),
                    )
                    old_chunk_ids = [row[0] for row in con.execute("SELECT id FROM document_chunks WHERE document_id=?", (doc_id,)).fetchall()]
                    for chunk_id in old_chunk_ids:
                        con.execute("DELETE FROM document_chunks_fts WHERE chunk_id=?", (chunk_id,))
                    con.execute("DELETE FROM document_chunks WHERE document_id=?", (doc_id,))
                    for index, chunk in enumerate(chunks):
                        redacted_text, _redactions = redact_private_text(chunk)
                        source_hash = hashlib.sha256(f"{rel}:{index}".encode("utf-8", errors="replace")).hexdigest()
                        chunk_id = hashlib.sha256(f"{doc_id}:{index}".encode("utf-8", errors="replace")).hexdigest()
                        con.execute(
                            """
                            INSERT INTO document_chunks(id,document_id,chunk_index,redacted_text,source_hash,page_no)
                            VALUES(?,?,?,?,?,?)
                            """,
                            (chunk_id, doc_id, index, redacted_text, source_hash, None),
                        )
                        con.execute(
                            "INSERT INTO document_chunks_fts(chunk_id, redacted_text, source_hash) VALUES(?,?,?)",
                            (chunk_id, redacted_text, source_hash),
                        )
                        indexed_chunks += 1
                    indexed_docs += 1
            return HTTPStatus.OK, {
                "ok": True,
                "path": payload.get("path"),
                "retrieval_mode": "sqlite_fts_first",
                "embedding_feature_flag": False,
                "indexed_documents": indexed_docs,
                "indexed_chunks": indexed_chunks,
                "db_path": str(self.document_fts_db_path),
            }
        except (sqlite3.DatabaseError, OSError, StoragePathError) as exc:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": f"document_fts_sync_failed:{type(exc).__name__}:{exc}"}
        finally:
            con.close()

    def document_fts_recall(self, query: str, relative_path: str, user: dict | None = None) -> tuple[int, dict]:
        sync_status, sync_payload = self.sync_document_fts_index(relative_path, user)
        if sync_status != HTTPStatus.OK:
            return sync_status, sync_payload
        terms = query_terms(query)
        match_query = fts_query_from_terms(terms)
        if not match_query:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "query_terms_empty"}
        try:
            con = sqlite3.connect(str(self.document_fts_db_path))
            con.row_factory = sqlite3.Row
            rows = con.execute(
                """
                SELECT c.id AS chunk_id, c.redacted_text, c.source_hash, c.chunk_index,
                       d.title, d.relative_path, d.file_type, bm25(document_chunks_fts) AS rank
                FROM document_chunks_fts
                JOIN document_chunks c ON c.id = document_chunks_fts.chunk_id
                JOIN documents d ON d.id = c.document_id
                WHERE document_chunks_fts MATCH ?
                ORDER BY rank
                LIMIT 8
                """,
                (match_query,),
            ).fetchall()
            evidence = []
            for index, row in enumerate(rows, start=1):
                rel = str(row["relative_path"])
                if user and not self.can_read(user, rel):
                    continue
                snippet = local_snippet(str(row["redacted_text"]), terms, max_chars=220) or str(row["redacted_text"])[:220]
                evidence.append(
                    {
                        "evidence_ref": f"ev_{index}_{str(row['source_hash'])[:10]}",
                        "chunk_id": row["chunk_id"],
                        "name": row["title"],
                        "relative_path": rel,
                        "extension": row["file_type"],
                        "chunk_index": row["chunk_index"],
                        "source_hash": row["source_hash"],
                        "snippet": snippet,
                        "score": float(row["rank"] or 0),
                    }
                )
            return HTTPStatus.OK, {
                "ok": True,
                "query": query,
                "path": relative_path,
                "retrieval_mode": "sqlite_fts_first",
                "embedding_feature_flag": False,
                "embedding_enabled": False,
                "fts_sync": sync_payload,
                "evidence": evidence,
                "evidence_refs": [item["evidence_ref"] for item in evidence],
                "evidence_count": len(evidence),
            }
        except sqlite3.DatabaseError as exc:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": f"document_fts_query_failed:{type(exc).__name__}:{exc}", "retrieval_mode": "sqlite_fts_first_degraded"}
        finally:
            try:
                con.close()
            except Exception:
                pass

    def document_query_payload(self, query: str, relative_path: str = "Documents", user: dict | None = None) -> tuple[int, dict]:
        query = str(query or "").strip()
        if not query:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "query_required"}
        status, payload = self.document_fts_recall(query, normalize_storage_relative_path(relative_path or "Documents"), user)
        if status != HTTPStatus.OK:
            return status, payload
        evidence = payload.get("evidence") or []
        if evidence:
            refs = "、".join(payload.get("evidence_refs") or [])
            names = "、".join(str(item.get("name") or item.get("relative_path")) for item in evidence[:3])
            answer = f"SQLite FTS-first RAG 在 {payload.get('path')} 下召回 {len(evidence)} 条证据：{names}。证据引用：{refs}。"
        else:
            answer = f"未找到可靠证据：在 {payload.get('path')} 下没有与“{query}”匹配的 FTS 证据。"
        return HTTPStatus.OK, {
            "ok": True,
            "query": query,
            "path": payload.get("path"),
            "answer": answer,
            "evidence": evidence,
            "evidence_refs": payload.get("evidence_refs") or [],
            "evidence_count": len(evidence),
            "readable_count": payload.get("fts_sync", {}).get("indexed_documents", 0),
            "retrieval_mode": payload.get("retrieval_mode") or "sqlite_fts_first",
            "embedding_feature_flag": False,
            "embedding_enabled": False,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "raw_private_content_returned": False,
        }

    def record_operation(self, action: str, source: str | None, target: str | None, status: str, detail: str | None = None) -> None:
        if not self.operation_db_path:
            return
        try:
            log_file_operation(self.operation_db_path, action, source, target, status, detail)
        except Exception:
            return

    def storage_create_folder(self, relative_path: str, user: dict) -> tuple[int, dict]:
        try:
            rel = normalize_storage_relative_path(relative_path)
            if not rel:
                return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "folder_path_required"}
            parent_rel = str(Path(rel).parent).replace("\\", "/")
            if parent_rel == ".":
                parent_rel = ""
            target = resolve_storage_path(self.personal_root, rel) if self.personal_root else Path(rel)
            parent = resolve_storage_path(self.personal_root, parent_rel) if self.personal_root else target.parent
        except StoragePathError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
        if not self.can_write(user, rel):
            self.record_operation("mkdir", None, rel, "permission_denied", str(user.get("username")))
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "write", "path": rel}
        if not parent.exists() or not parent.is_dir():
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "parent_directory_not_found", "path": parent_rel}
        if target.exists():
            return HTTPStatus.CONFLICT, {"ok": False, "error": "target_already_exists", "path": rel}
        try:
            target.mkdir(parents=False, exist_ok=False)
        except OSError as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"mkdir_failed:{type(exc).__name__}:{exc}", "path": rel}
        self.record_operation("mkdir", None, rel, "created", str(user.get("username")))
        return HTTPStatus.OK, {"ok": True, "folder": {"relative_path": rel, "path": rel, "name": target.name}}

    def storage_upload_file(self, payload: dict, user: dict) -> tuple[int, dict]:
        filename = str(payload.get("filename") or "").strip()
        if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_filename"}
        try:
            target_dir = normalize_storage_relative_path(payload.get("target_dir") or "")
            target_rel = normalize_storage_relative_path(f"{target_dir}/{filename}" if target_dir else filename)
            target = resolve_storage_path(self.personal_root, target_rel) if self.personal_root else Path(target_rel)
            parent = resolve_storage_path(self.personal_root, target_dir) if self.personal_root else target.parent
        except StoragePathError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
        if not self.can_write(user, target_rel):
            self.record_operation("upload", None, target_rel, "permission_denied", str(user.get("username")))
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "write", "path": target_rel}
        if not parent.exists() or not parent.is_dir():
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "target_directory_not_found", "path": target_dir}
        if target.exists() and not bool(payload.get("overwrite")):
            self.record_operation("upload", None, target_rel, "target_already_exists", str(user.get("username")))
            return HTTPStatus.CONFLICT, {"ok": False, "error": "target_already_exists", "path": target_rel}
        if bool(payload.get("overwrite")):
            self.record_operation("upload", None, target_rel, "overwrite_disabled", str(user.get("username")))
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "overwrite_disabled_by_default_service", "path": target_rel}
        try:
            content = base64.b64decode(str(payload.get("content_base64") or ""), validate=True)
        except (binascii.Error, ValueError) as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid_base64:{exc}"}
        if len(content) > MAX_UPLOAD_BYTES:
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "upload_too_large", "max_bytes": MAX_UPLOAD_BYTES}
        try:
            target.write_bytes(content)
        except OSError as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"upload_write_failed:{type(exc).__name__}:{exc}", "path": target_rel}
        sha256 = hashlib.sha256(content).hexdigest()
        self.record_operation("upload", None, target_rel, "created", str(user.get("username")))
        return HTTPStatus.OK, {
            "ok": True,
            "file": {
                "relative_path": target_rel,
                "path": target_rel,
                "name": filename,
                "size_bytes": len(content),
                "sha256": sha256,
            },
        }

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

    def _copilot_qwen_router_completion(self, message: str) -> dict:
        payload = {
            "model": self.qwen_model,
            "messages": [
                {"role": "user", "content": message},
            ],
            "temperature": 0.0,
            "max_tokens": 96,
            "stream": False,
            "disable_ai_nas_tools": True,
            "metadata": {
                "source": "openclaw_operator_portal",
                "purpose": "edge_cloud_route_classifier",
                "original_query_sent": True,
                "disable_ai_nas_tools": True,
                "qwen_execution_authority": False,
            },
        }
        return http_post_json(
            "local_qwen_router",
            normalize_chat_completions_url(self.qwen_gateway_url or DEFAULT_QWEN_GATEWAY_URL),
            payload,
            timeout=12,
        )

    def _copilot_structured_router_completion(self, message: str) -> dict:
        payload = {
            "model": self.qwen_model,
            "messages": [
                {"role": "user", "content": message},
            ],
            "temperature": 0.0,
            "max_tokens": 96,
            "stream": False,
            "disable_ai_nas_tools": True,
            "metadata": {
                "source": "openclaw_operator_portal",
                "purpose": "edge_cloud_route_classifier",
                "original_query_sent": True,
                "disable_ai_nas_tools": True,
                "qwen_execution_authority": False,
            },
        }
        return http_post_json(
            "local_qwen_router_structured_fallback",
            normalize_chat_completions_url(self.qwen_gateway_url or DEFAULT_QWEN_GATEWAY_URL),
            payload,
            timeout=12,
        )

    def copilot_qwen_route(self, message: str, action_intent: dict | None = None) -> dict:
        policy = copilot_policy_route(message, action_intent)
        qwen_route: dict | None = None
        result = self._copilot_qwen_router_completion(message)
        if result.get("ok"):
            content, metadata, upstream = chat_completion_content(result)
            parsed = parse_json_object_from_text(content)
            qwen_route = normalize_copilot_router(
                parsed or {},
                classifier=str(metadata.get("classifier") or "qwen_gateway_structured_router"),
                raw_content=content,
                elapsed_ms=result.get("elapsed_ms"),
            )
            if qwen_route:
                qwen_route["model"] = upstream.get("model") or self.qwen_model
        if not qwen_route:
            fallback = self._copilot_structured_router_completion(message)
            if fallback.get("ok"):
                content, _metadata, upstream = chat_completion_content(fallback)
                parsed = parse_json_object_from_text(content)
                qwen_route = normalize_copilot_router(
                    parsed or {},
                    classifier="qwen_gateway_structured_router_fallback",
                    raw_content=content,
                    elapsed_ms=fallback.get("elapsed_ms"),
                )
                if qwen_route:
                    qwen_route["model"] = upstream.get("model") or self.qwen_model
                    qwen_route["fallback_from_real_qwen"] = True
        if not qwen_route:
            qwen_route = {
                **policy,
                "classifier": "portal_policy_fallback_after_qwen_failure",
                "qwen_router_failed": True,
                "qwen_router_error": result.get("error") or (result.get("payload") or {}).get("error") if isinstance(result.get("payload"), dict) else result.get("error"),
                "elapsed_ms": result.get("elapsed_ms"),
            }
        return apply_copilot_guardrail(qwen_route, policy)

    def _copilot_attach_router(self, status: int, payload: dict, router: dict, *, assistant_mode: str | None = None) -> tuple[int, dict]:
        if not isinstance(payload, dict):
            return status, payload
        if assistant_mode:
            payload.setdefault("assistant_mode", assistant_mode)
            payload.setdefault("route", assistant_mode)
        payload.setdefault("cloud_used", False)
        payload.setdefault("qwen_execution_authority", False)
        payload["qwen_router"] = router
        audit = payload.get("audit")
        if isinstance(audit, dict):
            audit.setdefault("qwen_router_classifier", router.get("classifier"))
            audit.setdefault("qwen_router_route", router.get("route"))
            audit.setdefault("qwen_execution_authority", False)
        return status, payload

    def _copilot_answer_payload(self, *, mode: str, answer: str, router: dict, nas_action: dict | None = None, extra: dict | None = None) -> tuple[int, dict]:
        payload = {
            "ok": True,
            "assistant_mode": mode,
            "answer": answer,
            "route": mode,
            "model": "S100P local API via Qwen router",
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": nas_action or {
                "operation": "none",
                "status": "completed",
                "qwen_execution_authority": False,
            },
            "audit": {
                "tool_executor": "openclaw_local_api",
                "tool_execution_performed": bool(nas_action and nas_action.get("operation") not in {"none", "inspect"}),
                "direct_nas_write_performed": bool(nas_action and nas_action.get("direct_nas_write_performed")),
                "cloud_payload_sent": False,
                "qwen_execution_authority": False,
            },
        }
        if extra:
            payload.update(extra)
        return self._copilot_attach_router(HTTPStatus.OK, payload, router, assistant_mode=mode)

    def _copilot_needs_params(self, action: str, missing: list[str], router: dict, example: str) -> tuple[int, dict]:
        answer = f"Qwen 已识别为 {action} 本地任务，但参数不完整。还需要：{', '.join(missing)}。示例：{example}"
        return self._copilot_answer_payload(
            mode="needs_parameters",
            answer=answer,
            router=router,
            nas_action={
                "operation": action,
                "status": "needs_parameters",
                "missing": missing,
                "qwen_execution_authority": False,
                "direct_nas_write_performed": False,
            },
        )

    def _copilot_storage_path(self, rel: str, user: dict, router: dict) -> tuple[int, dict]:
        try:
            path = resolve_storage_path(self.personal_root, rel) if self.personal_root else Path(rel)
        except StoragePathError as exc:
            return self._copilot_attach_router(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}, router)
        if path.is_dir():
            status, payload = self.storage_list_payload(rel, user)
            if status == HTTPStatus.OK:
                entries = payload.get("entries") or []
                payload.update(
                    {
                        "assistant_mode": "local_storage_list",
                        "route": "local_storage_list",
                        "model": "S100P storage API via Qwen router",
                        "answer": f"已通过本地 NAS 权限检查列出 {normalize_storage_relative_path(rel) or '/'}，返回 {len(entries)} 个条目。",
                        "nas_action": {
                            "operation": "list",
                            "status": "completed",
                            "entries": entries[:25],
                            "qwen_execution_authority": False,
                            "direct_nas_write_performed": False,
                        },
                        "cloud_used": False,
                        "qwen_execution_authority": False,
                    }
                )
            return self._copilot_attach_router(status, payload, router, assistant_mode=payload.get("assistant_mode"))
        return self._copilot_answer_payload(
            mode="local_storage_inspect",
            answer=f"已完成只读路径检查：{normalize_storage_relative_path(rel)}。不会把原始文件内容交给云端，也不会让 Qwen 获得写权限。",
            router=router,
            nas_action={
                "operation": "inspect",
                "status": "read_only_completed",
                "path": normalize_storage_relative_path(rel),
                "path_hash": hashlib.sha256(normalize_storage_relative_path(rel).encode("utf-8", errors="replace")).hexdigest(),
                "qwen_execution_authority": False,
                "direct_nas_write_performed": False,
                "forbidden_actions": ["delete", "move", "rename", "chmod", "chown", "recursive", "overwrite"],
            },
        )

    def _copilot_document_query(self, intent: dict, user: dict, router: dict) -> tuple[int, dict]:
        status, payload = self.document_query_payload(str(intent.get("query") or ""), str(intent.get("path") or "Documents"), user)
        if status == HTTPStatus.OK:
            payload.update(
                {
                    "assistant_mode": "local_document_query",
                    "route": "local_document_query",
                    "model": "SQLite FTS-first RAG via Qwen router",
                    "nas_action": {
                        "operation": "document_query",
                        "status": "completed",
                        "evidence_count": payload.get("evidence_count", 0),
                        "qwen_execution_authority": False,
                        "direct_nas_write_performed": False,
                    },
                }
            )
        return self._copilot_attach_router(status, payload, router, assistant_mode=payload.get("assistant_mode"))

    def _copilot_snapshot_create(self, intent: dict, user: dict, router: dict) -> tuple[int, dict]:
        rel = str(intent.get("path") or "").strip()
        name = str(intent.get("name") or "").strip()
        if not rel:
            return self._copilot_needs_params("snapshot_create", ["path"], router, '给 "Documents" 创建快照')
        if not self.snapshot_store:
            return self._copilot_attach_router(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "snapshot_store_unavailable"}, router)
        try:
            source_rel = normalize_storage_relative_path(rel)
        except StoragePathError as exc:
            return self._copilot_attach_router(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}, router)
        if not self.can_read(user, source_rel):
            return self._copilot_attach_router(HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "read", "path": source_rel}, router)
        result = self.snapshot_store.create_snapshot(name, source_rel, str(user.get("username") or ""))
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        payload = {
            "ok": bool(result.get("ok")),
            "assistant_mode": "local_snapshot_create",
            "answer": f"已为 {source_rel} 创建本地快照 {name}。" if result.get("ok") else f"快照创建失败：{result.get('error')}",
            "route": "local_snapshot_create",
            "model": "S100P snapshot API via Qwen router",
            "snapshot": result.get("snapshot"),
            "result": result,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": {
                "operation": "snapshot_create",
                "status": "completed" if result.get("ok") else "failed",
                "path": source_rel,
                "name": name,
                "qwen_execution_authority": False,
                "direct_nas_write_performed": bool(result.get("ok")),
            },
        }
        return self._copilot_attach_router(status, payload, router, assistant_mode="local_snapshot_create")

    def _copilot_backup_create_task(self, intent: dict, user: dict, router: dict) -> tuple[int, dict]:
        source_rel = str(intent.get("source") or "").strip()
        dest_rel = str(intent.get("dest") or "").strip()
        name = str(intent.get("name") or "").strip()
        if not source_rel or not dest_rel:
            return self._copilot_needs_params("backup_create_task", ["source", "dest"], router, '备份 "Documents" 到 "Backups/Documents"')
        if not self.backup_manager:
            return self._copilot_attach_router(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "backup_manager_unavailable"}, router)
        try:
            source_rel = normalize_storage_relative_path(source_rel)
            dest_rel = normalize_storage_relative_path(dest_rel)
            source = resolve_storage_path(self.personal_root, source_rel)
            dest = resolve_storage_path(self.personal_root, dest_rel)
        except StoragePathError as exc:
            return self._copilot_attach_router(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}, router)
        if not self.can_read(user, source_rel) or not self.can_write(user, dest_rel):
            return self._copilot_attach_router(HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "source": source_rel, "dest": dest_rel}, router)
        result = self.backup_manager.create_task(name, str(source), str(dest), 0)
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        payload = {
            "ok": bool(result.get("ok")),
            "assistant_mode": "local_backup_create_task",
            "answer": f"已创建本地备份任务 {name}：{source_rel} -> {dest_rel}。" if result.get("ok") else f"备份任务创建失败：{result.get('error')}",
            "route": "local_backup_create_task",
            "model": "S100P backup API via Qwen router",
            "result": result,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": {
                "operation": "backup_create_task",
                "status": "completed" if result.get("ok") else "failed",
                "source": source_rel,
                "dest": dest_rel,
                "name": name,
                "qwen_execution_authority": False,
                "direct_nas_write_performed": bool(result.get("ok")),
            },
        }
        return self._copilot_attach_router(status, payload, router, assistant_mode="local_backup_create_task")

    def _copilot_backup_run(self, intent: dict, router: dict) -> tuple[int, dict]:
        name = str(intent.get("name") or "").strip()
        if not name:
            return self._copilot_needs_params("backup_run", ["task_name"], router, '运行备份任务 "assistant-backup-20260705-120000"')
        if not self.backup_manager:
            return self._copilot_attach_router(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "backup_manager_unavailable"}, router)
        result = self.backup_manager.run_backup(name)
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        payload = {
            "ok": bool(result.get("ok")),
            "assistant_mode": "local_backup_run",
            "answer": f"备份任务 {name} 已运行，复制 {result.get('copied', 0)} 个文件。" if result.get("ok") else f"备份运行失败：{result.get('error')}",
            "route": "local_backup_run",
            "model": "S100P backup API via Qwen router",
            "result": result,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": {
                "operation": "backup_run",
                "status": "completed" if result.get("ok") else "failed",
                "name": name,
                "qwen_execution_authority": False,
                "direct_nas_write_performed": bool(result.get("ok")),
            },
        }
        return self._copilot_attach_router(status, payload, router, assistant_mode="local_backup_run")

    def _copilot_media_index(self, intent: dict, user: dict, router: dict) -> tuple[int, dict]:
        rel = str(intent.get("path") or "Photos").strip()
        try:
            rel = normalize_storage_relative_path(rel)
            root = resolve_storage_path(self.personal_root, rel)
        except StoragePathError as exc:
            return self._copilot_attach_router(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}, router)
        if not self.can_read(user, rel):
            return self._copilot_attach_router(HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "read", "path": rel}, router)
        result = self.media_center.index_photos(root) if self.media_center else {"scanned": 0, "indexed": 0, "skipped": 0}
        return self._copilot_answer_payload(
            mode="local_media_index",
            answer=f"已在本地扫描 {rel}，scanned={result.get('scanned', 0)}，indexed={result.get('indexed', 0)}，skipped={result.get('skipped', 0)}。",
            router=router,
            nas_action={
                "operation": "media_index",
                "status": "completed",
                "path": rel,
                "qwen_execution_authority": False,
                "direct_nas_write_performed": True,
            },
            extra={"index": result},
        )

    def _copilot_media_create_album(self, intent: dict, router: dict) -> tuple[int, dict]:
        name = str(intent.get("name") or "").strip()
        if not name:
            return self._copilot_needs_params("media_create_album", ["album_name"], router, '创建相册 "家庭照片"')
        result = self.media_center.create_album(name, str(intent.get("description") or "")) if self.media_center else {"ok": False, "error": "media_center_unavailable"}
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        payload = {
            "ok": bool(result.get("ok")),
            "assistant_mode": "local_media_create_album",
            "answer": f"已创建本地相册 {name}。" if result.get("ok") else f"相册创建失败：{result.get('error')}",
            "route": "local_media_create_album",
            "model": "S100P media API via Qwen router",
            "result": result,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": {
                "operation": "media_create_album",
                "status": "completed" if result.get("ok") else "failed",
                "name": name,
                "qwen_execution_authority": False,
                "direct_nas_write_performed": bool(result.get("ok")),
            },
        }
        return self._copilot_attach_router(status, payload, router, assistant_mode="local_media_create_album")

    def _copilot_journal_summary(self, intent: dict, router: dict) -> tuple[int, dict]:
        if journal_route_response is None:
            return self._copilot_attach_router(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "digua_journal_routes_unavailable"}, router)
        status, result = journal_route_response(
            "/api/journal/generate-summary",
            method="POST",
            payload={"period_type": intent.get("period_type") or "daily", "project_id": intent.get("project_id") or "all"},
            report_root=self.journal_report_root,
            evidence_dir=self.journal_evidence_dir,
            export_dir=self.journal_export_dir,
        )
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        payload = {
            "ok": bool(result.get("ok")),
            "assistant_mode": "local_journal_summary",
            "answer": str(summary.get("markdown") or "已生成本地日记摘要。")[:1200] if result.get("ok") else f"日记摘要失败：{result.get('error')}",
            "route": "local_journal_summary",
            "model": "S100P journal API via Qwen router",
            "result": result,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": {
                "operation": "journal_summary",
                "status": "completed" if result.get("ok") else "failed",
                "qwen_execution_authority": False,
                "direct_nas_write_performed": False,
            },
        }
        return self._copilot_attach_router(status, payload, router, assistant_mode="local_journal_summary")

    def _copilot_journal_manual_entry(self, intent: dict, router: dict) -> tuple[int, dict]:
        title = str(intent.get("title") or "").strip()
        body = str(intent.get("body") or "").strip()
        if not title or not body:
            return self._copilot_needs_params("journal_manual_entry", ["title", "body"], router, '记一条日记 "标题" "正文内容"')
        if journal_route_response is None:
            return self._copilot_attach_router(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "digua_journal_routes_unavailable"}, router)
        status, result = journal_route_response(
            "/api/journal/manual-entry",
            method="POST",
            payload={"project_id": intent.get("project_id") or "manual", "title": title, "body": body, "evidence_refs": []},
            report_root=self.journal_report_root,
            evidence_dir=self.journal_evidence_dir,
            export_dir=self.journal_export_dir,
        )
        payload = {
            "ok": bool(result.get("ok")),
            "assistant_mode": "local_journal_manual_entry",
            "answer": f"已写入本地日记：{title}。" if result.get("ok") else f"日记写入失败：{result.get('error')}",
            "route": "local_journal_manual_entry",
            "model": "S100P journal API via Qwen router",
            "result": result,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": {
                "operation": "journal_manual_entry",
                "status": "completed" if result.get("ok") else "failed",
                "qwen_execution_authority": False,
                "direct_nas_write_performed": bool(result.get("ok")),
            },
        }
        return self._copilot_attach_router(status, payload, router, assistant_mode="local_journal_manual_entry")

    def _copilot_summary_action(self, action: str, router: dict) -> tuple[int, dict]:
        if action == "storage_status":
            payload = self.storage_status_payload()
            answer = f"已读取本地 NAS 存储状态。Personal 空间{'已配置' if self.personal_root else '未配置'}，下方展示容量、索引和权限状态。"
        elif action == "media_summary":
            media = self.media_center
            payload = {"ok": True, "stats": media.stats() if media else {}, "albums": media.list_albums() if media else []}
            stats = payload.get("stats") or {}
            answer = (
                f"已读取媒体库概览：照片 {int(stats.get('photo_count') or 0)} 个，"
                f"视频 {int(stats.get('video_count') or 0)} 个，相册 {int(stats.get('album_count') or 0)} 个。"
            )
        elif action == "ops_summary":
            ops = self.ops_manager
            payload = {"ok": True, "checks": ops.list_checks(limit=50) if ops else [], "alerts": ops.list_alerts(True) if ops else [], "stats": ops.stats() if ops else {}}
            stats = payload.get("stats") or {}
            answer = (
                f"已读取运行健康概览：健康检查 {int(stats.get('health_check_count') or 0)} 项，"
                f"活动告警 {int(stats.get('active_alert_count') or 0)} 条。"
            )
        elif action == "apps_summary":
            apps = self.app_ecosystem
            payload = {"ok": True, "plugins": apps.list_plugins() if apps else [], "protocols": apps.list_protocols() if apps else [], "stats": apps.stats() if apps else {}}
            stats = payload.get("stats") or {}
            answer = (
                f"已读取应用生态概览：插件 {int(stats.get('plugin_count') or 0)} 个，"
                f"协议适配 {int(stats.get('adapter_count') or 0)} 个。"
            )
        elif action == "audit_summary":
            payload = self.audit_summary_payload()
            answer = f"已读取本地审计概览：最近 {len(payload.get('operations') or [])} 条操作记录，下方展示时间、动作和状态。"
        elif action == "reports_list":
            payload = self.list_reports_payload()
            answer = f"已读取本地报告列表：共 {len(payload.get('reports') or [])} 份，按最近可查看报告展示。"
        else:
            payload = {"ok": False, "error": "unknown_summary_action", "action": action}
            answer = payload["error"]
        payload.update(
            {
                "assistant_mode": f"local_{action}",
                "answer": answer,
                "route": f"local_{action}",
                "model": "S100P local API via Qwen router",
                "cloud_used": False,
                "qwen_execution_authority": False,
                "nas_action": {
                    "operation": action,
                    "status": "completed" if payload.get("ok") else "failed",
                    "qwen_execution_authority": False,
                    "direct_nas_write_performed": False,
                },
            }
        )
        return self._copilot_attach_router(HTTPStatus.OK if payload.get("ok") else HTTPStatus.BAD_REQUEST, payload, router, assistant_mode=f"local_{action}")

    def _copilot_cloud_overflow(self, message: str, user: dict, router: dict) -> tuple[int, dict]:
        if router.get("privacy_level") != "none":
            status, payload = self.local_qwen_chat(message, user)
            payload.setdefault("cloud_overflow_blocked", True)
            return self._copilot_attach_router(status, payload, router, assistant_mode=payload.get("assistant_mode"))
        cloud_url = os.environ.get("AI_NAS_CLOUD_CHAT_URL", "").strip()
        if not cloud_url:
            return self._copilot_answer_payload(
                mode="cloud_overflow_stub",
                answer="Qwen 判断这是非隐私的复杂公共任务，可以进入云端；当前实机环境未配置 AI_NAS_CLOUD_CHAT_URL，所以没有发送云端 payload，仅保留本地受控返回。",
                router=router,
                nas_action={
                    "operation": "cloud_overflow",
                    "status": "cloud_not_configured",
                    "qwen_execution_authority": False,
                    "direct_nas_write_performed": False,
                },
                extra={"cloud_available": False, "cloud_used": False},
            )
        result = http_post_json(
            "cloud_overflow_chat",
            normalize_chat_completions_url(cloud_url),
            {
                "model": os.environ.get("AI_NAS_CLOUD_CHAT_MODEL", "cloud-overflow"),
                "messages": [{"role": "user", "content": message}],
                "stream": False,
                "metadata": {"source": "digua_ai_nas_cloud_overflow", "privacy_level": "none"},
            },
            timeout=60,
        )
        if not result.get("ok"):
            return self._copilot_attach_router(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": "cloud_overflow_failed", "upstream": result}, router)
        content, _metadata, upstream = chat_completion_content(result)
        payload = {
            "ok": True,
            "assistant_mode": "cloud_overflow_chat",
            "answer": content.strip() or "cloud_overflow_empty_answer",
            "route": "cloud_overflow_chat",
            "model": upstream.get("model") or os.environ.get("AI_NAS_CLOUD_CHAT_MODEL", "cloud-overflow"),
            "cloud_used": True,
            "qwen_execution_authority": False,
            "nas_action": {"operation": "cloud_overflow", "status": "completed", "qwen_execution_authority": False},
            "audit": {"cloud_payload_sent": True, "privacy_level": "none", "qwen_execution_authority": False},
        }
        return self._copilot_attach_router(HTTPStatus.OK, payload, router, assistant_mode="cloud_overflow_chat")

    def dispatch_copilot_action(self, intent: dict, user: dict, router: dict) -> tuple[int, dict]:
        action = str(intent.get("action") or "")
        if action == "search":
            status, payload = self.local_copilot_search(intent.get("search_intent") or {}, user)
            return self._copilot_attach_router(status, payload, router, assistant_mode=payload.get("assistant_mode") if isinstance(payload, dict) else None)
        if action == "document_query":
            return self._copilot_document_query(intent, user, router)
        if action == "storage_list_or_inspect":
            return self._copilot_storage_path(str(intent.get("path") or ""), user, router)
        if action == "storage_list":
            return self._copilot_storage_path(str(intent.get("path") or ""), user, router)
        if action == "storage_create_folder":
            path = str(intent.get("path") or "").strip()
            if not path:
                return self._copilot_needs_params("storage_create_folder", ["path"], router, '新建文件夹 "Inbox/NewFolder"')
            status, payload = self.storage_create_folder(path, user)
            if status == HTTPStatus.OK:
                payload.update(
                    {
                        "assistant_mode": "local_storage_create_folder",
                        "answer": f"已新建文件夹 {normalize_storage_relative_path(path)}。",
                        "route": "local_storage_create_folder",
                        "model": "S100P storage API via Qwen router",
                        "cloud_used": False,
                        "qwen_execution_authority": False,
                        "nas_action": {
                            "operation": "mkdir",
                            "status": "completed",
                            "path": normalize_storage_relative_path(path),
                            "qwen_execution_authority": False,
                            "direct_nas_write_performed": True,
                        },
                    }
                )
            return self._copilot_attach_router(status, payload, router, assistant_mode=payload.get("assistant_mode"))
        if action in {"storage_copy", "storage_rename"}:
            source = str(intent.get("source") or "")
            target = str(intent.get("target") or "")
            if "/" not in target and "\\" not in target:
                try:
                    source_rel = normalize_storage_relative_path(source)
                    parent = str(Path(source_rel).parent).replace("\\", "/")
                    target = target if parent in {"", "."} else f"{parent}/{target}"
                except StoragePathError:
                    pass
            status, payload = self.storage_rename(source, Path(target).name, user) if action == "storage_rename" else self.storage_copy(source, target, user)
            if isinstance(payload, dict):
                payload.setdefault("assistant_mode", "local_storage_rename" if action == "storage_rename" else "local_storage_copy_route")
                payload.setdefault("route", payload["assistant_mode"])
                payload.setdefault("answer", "已进入受控 NAS 操作链路；直接高风险写操作未交给 Qwen 执行。")
            return self._copilot_attach_router(status, payload, router, assistant_mode=payload.get("assistant_mode") if isinstance(payload, dict) else None)
        if action == "snapshot_create":
            return self._copilot_snapshot_create(intent, user, router)
        if action == "backup_create_task":
            return self._copilot_backup_create_task(intent, user, router)
        if action == "backup_run":
            return self._copilot_backup_run(intent, router)
        if action == "media_index":
            return self._copilot_media_index(intent, user, router)
        if action == "media_create_album":
            return self._copilot_media_create_album(intent, router)
        if action == "journal_summary":
            return self._copilot_journal_summary(intent, router)
        if action == "journal_manual_entry":
            return self._copilot_journal_manual_entry(intent, router)
        if action in {"storage_status", "media_summary", "ops_summary", "apps_summary", "audit_summary", "reports_list"}:
            return self._copilot_summary_action(action, router)
        return self._copilot_answer_payload(
            mode="local_intent_unhandled",
            answer=f"Qwen 已完成本地路由判定，但当前 Copilot 尚未映射动作：{action}",
            router=router,
            nas_action={"operation": action or "unknown", "status": "unhandled", "qwen_execution_authority": False},
        )

    def _local_qwen_chat_completion(self, message: str) -> dict:
        payload = {
            "model": self.qwen_model,
            "messages": [
                {"role": "user", "content": message},
            ],
            "temperature": 0.2,
            "max_tokens": 256,
            "stream": False,
            "disable_ai_nas_tools": True,
            "metadata": {
                "source": "openclaw_operator_portal",
                "purpose": "local_general_chat",
                "disable_ai_nas_tools": True,
                "qwen_execution_authority": False,
            },
        }
        return http_post_json(
            "local_qwen_chat",
            normalize_chat_completions_url(self.qwen_gateway_url or DEFAULT_QWEN_GATEWAY_URL),
            payload,
            timeout=180,
        )

    def local_qwen_chat(self, message: str, user: dict) -> tuple[int, dict]:
        clean_message = (message or "").strip()
        if not clean_message:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty_message"}
        result = self._local_qwen_chat_completion(clean_message)
        if not result.get("ok"):
            return HTTPStatus.BAD_GATEWAY, {
                "ok": False,
                "error": "local_qwen_chat_failed",
                "route": "local_qwen_chat",
                "qwen_execution_authority": False,
                "cloud_used": False,
                "upstream_status": result.get("status"),
                "upstream_error": result.get("error") or (result.get("payload") or {}).get("error"),
                "elapsed_ms": result.get("elapsed_ms"),
            }
        upstream = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        choices = upstream.get("choices") if isinstance(upstream.get("choices"), list) else []
        first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message_payload = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
        answer = str(message_payload.get("content") or "").strip()
        if not answer:
            return HTTPStatus.BAD_GATEWAY, {
                "ok": False,
                "error": "local_qwen_empty_answer",
                "route": "local_qwen_chat",
                "qwen_execution_authority": False,
                "cloud_used": False,
                "elapsed_ms": result.get("elapsed_ms"),
            }
        return HTTPStatus.OK, {
            "ok": True,
            "assistant_mode": "local_qwen_chat",
            "answer": answer,
            "route": "local_qwen_chat",
            "model": upstream.get("model") or self.qwen_model,
            "finish_reason": first_choice.get("finish_reason"),
            "usage": upstream.get("usage") if isinstance(upstream.get("usage"), dict) else {},
            "elapsed_ms": result.get("elapsed_ms"),
            "cloud_used": False,
            "qwen_execution_authority": False,
            "nas_action": {
                "operation": "none",
                "status": "answered_by_local_qwen",
                "qwen_execution_authority": False,
                "forbidden_actions": ["delete", "move", "rename", "chmod", "chown", "recursive", "overwrite", "shell"],
            },
            "audit": {
                "caller": str(user.get("username") or "unknown"),
                "tool_execution_performed": False,
                "direct_nas_write_performed": False,
                "cloud_payload_sent": False,
                "prompt_hash": hashlib.sha256(clean_message.encode("utf-8", errors="replace")).hexdigest(),
            },
        }

    def enrich_copilot_search_result(
        self,
        item: dict,
        user: dict,
        path_cache: dict[str, tuple[Path | None, str | None]],
    ) -> dict:
        safe = sanitize_copilot_search_result(item)
        path_hash_value = str(safe.get("path_hash") or "")
        path, _relative_path = self.storage_file_by_path_hash(path_hash_value, user, path_cache)
        stat = None
        if path:
            try:
                stat = path.stat()
            except OSError:
                stat = None
        name = path.name if path else str(safe.get("title_redacted") or safe.get("asset_id") or "本地索引结果")
        modality = safe.get("modality")
        file_type = safe.get("file_type") or (path.suffix.lower() if path else "")
        type_label = modality_display_label(modality, file_type)
        mtime_value = safe.get("mtime")
        if not mtime_value and stat:
            mtime_value = stat.st_mtime
        size_value = safe.get("size_bytes")
        if not size_value and stat:
            size_value = stat.st_size
        match_label, match_score = search_result_match_display(safe)
        match_score_label = f"{round(match_score * 1000) / 10}%" if isinstance(match_score, float) else ""
        safe["display"] = {
            "name": name,
            "date_label": mtime_to_display(mtime_value),
            "type_label": type_label,
            "size_label": bytes_to_display(size_value),
            "match_label": match_label,
            "match_score": match_score,
            "match_score_label": match_score_label,
            "privacy_label": privacy_display_label(safe.get("privacy_level")),
            "location_label": "NAS 本地索引",
        }
        if path and type_label == "照片" and path_hash_value:
            safe["preview_url"] = f"/api/storage/preview-by-hash?path_hash={quote(path_hash_value, safe='')}"
            safe["preview_kind"] = "image"
            safe["display"]["preview_available"] = True
        else:
            safe["display"]["preview_available"] = False
        return safe

    def _copilot_search_response(self, *, mode: str, intent: dict, result: dict, source: str, retrieval_mode: str, user: dict) -> tuple[int, dict]:
        path_cache: dict[str, tuple[Path | None, str | None]] = {}
        results = [
            self.enrich_copilot_search_result(item, user, path_cache)
            for item in (result.get("results") or [])[:8]
            if isinstance(item, dict)
        ]
        result_count = len(results)
        query = str(intent.get("query") or "")
        labels = result.get("labels") or intent.get("labels") or []
        title_summary = summarize_search_result_titles(results)
        if result_count:
            image_only = (intent.get("modality") == "image") or all((item.get("display") or {}).get("type_label") == "照片" for item in results)
            unit = "张相关照片" if image_only else "个匹配结果"
            answer = f"已在本地 NAS 索引中搜索“{query}”，找到 {result_count} {unit}。下方卡片包含预览图、名称、日期和匹配原因。"
            if title_summary:
                answer += f" 结果包括：{title_summary}。"
            if "person" in labels:
                answer += " 这里只表示检测到 person 目标，不做人脸识别，也不判断具体身份。"
        else:
            reason = result.get("degraded_reason") or "no_matching_local_index_result"
            answer = f"已执行本地 NAS 搜索“{query}”，当前索引没有返回匹配结果。原因：{reason}。未调用云端，也没有让 Qwen 直接访问或执行 NAS 工具。"
        return HTTPStatus.OK, {
            "ok": True,
            "assistant_mode": mode,
            "answer": answer,
            "route": mode,
            "model": source,
            "cloud_used": False,
            "qwen_execution_authority": False,
            "search": {
                "query_redacted": result.get("query_redacted") or query[:120],
                "labels": labels,
                "modality": intent.get("modality") or "all",
                "retrieval_mode": retrieval_mode,
                "result_count": result_count,
                "results": results,
                "degraded": bool(result.get("degraded")),
                "degraded_reason": result.get("degraded_reason"),
                "privacy": result.get("privacy") or {"raw_path_returned": False, "cloud_used": False},
            },
            "nas_action": {
                "operation": "search",
                "status": "completed" if result_count else "completed_empty",
                "qwen_execution_authority": False,
                "direct_nas_write_performed": False,
                "forbidden_actions": ["delete", "move", "rename", "chmod", "chown", "recursive", "overwrite", "shell"],
            },
            "audit": {
                "tool_executor": "openclaw_local_api",
                "local_search_performed": True,
                "direct_nas_write_performed": False,
                "cloud_payload_sent": False,
                "raw_path_returned": False,
                "prompt_hash": hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest(),
            },
        }

    def local_copilot_search(self, intent: dict, user: dict) -> tuple[int, dict]:
        query = str(intent.get("query") or "").strip()
        if intent.get("prefer_yolo") and yolo_route_response is not None:
            yolo_payload = {"query": query, "top_k": 8, "user_id": str(user.get("username") or "operator")}
            if intent.get("modality") and intent.get("modality") != "all":
                yolo_payload["modality"] = intent["modality"]
            status_code, result = yolo_route_response(
                "/api/yolo-index/search",
                method="POST",
                payload=yolo_payload,
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
            if status_code == HTTPStatus.OK and result.get("ok"):
                return self._copilot_search_response(
                    mode="local_yolo_search",
                    intent=intent,
                    result=result,
                    source="S100P YOLO object index",
                    retrieval_mode="yolo_object_index",
                    user=user,
                )
        if multimodal_route_response is None:
            return HTTPStatus.SERVICE_UNAVAILABLE, {
                "ok": False,
                "error": "local_search_unavailable",
                "route": "local_search",
                "cloud_used": False,
                "qwen_execution_authority": False,
            }
        mm_payload = {
            "query": query,
            "top_k": 8,
            "user_id": str(user.get("username") or "operator"),
        }
        if intent.get("modality") and intent.get("modality") != "all":
            mm_payload["modality"] = intent["modality"]
        status_code, result = multimodal_route_response(
            "/api/multimodal-search/query",
            method="POST",
            payload=mm_payload,
            report_root=self.report_root,
            personal_root=self.personal_root,
        )
        if status_code != HTTPStatus.OK or not result.get("ok"):
            return HTTPStatus.BAD_GATEWAY, {
                "ok": False,
                "error": result.get("error") or "local_multimodal_search_failed",
                "route": "local_multimodal_search",
                "cloud_used": False,
                "qwen_execution_authority": False,
            }
        return self._copilot_search_response(
            mode="local_multimodal_search",
            intent=intent,
            result=result,
            source="Local multimodal NAS index",
            retrieval_mode=result.get("retrieval_mode") or "fts_first_plus_image_embedding",
            user=user,
        )

    def copilot_chat(self, message: str, user: dict) -> tuple[int, dict]:
        clean_message = str(message or "").strip()
        if not clean_message:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty_message"}
        action_intent = infer_copilot_action_intent(clean_message)
        router = self.copilot_qwen_route(clean_message, action_intent)
        if action_intent:
            return self.dispatch_copilot_action(action_intent, user, router)
        if router.get("route") == "cloud":
            return self._copilot_cloud_overflow(clean_message, user, router)
        status, payload = self.local_qwen_chat(clean_message, user)
        return self._copilot_attach_router(status, payload, router, assistant_mode=payload.get("assistant_mode") if isinstance(payload, dict) else None)

    def audit_summary_payload(self) -> dict:
        if not self.operation_db_path:
            return {"ok": True, "operations": []}
        try:
            operations = latest_file_operations(self.operation_db_path, limit=50)
        except Exception as exc:
            return {
                "ok": True,
                "operations": [],
                "warning": f"audit_operations_unavailable:{type(exc).__name__}:{exc}",
            }
        return {"ok": True, "operations": operations}

    def list_reports_payload(self, limit: int = 80) -> dict:
        roots = [self.report_root, *self.evidence_roots, self.journal_export_dir]
        seen: set[str] = set()
        reports: list[dict] = []
        type_map = [
            ("token", "Token Budget 报告"),
            ("gate", "Gate 报告"),
            ("evidence", "证据报告"),
            ("journal", "地瓜日记导出"),
            ("document", "文档问答报告"),
            ("folder", "文件夹摘要报告"),
        ]
        for root in roots:
            if not root or not root.exists():
                continue
            try:
                candidates = []
                scan_cap = max(limit * 5, 240)
                for path in root.rglob("*"):
                    if path.is_file() and path.suffix.lower() in {".md", ".json"}:
                        candidates.append(path)
                        if len(candidates) >= scan_cap:
                            break
            except OSError:
                continue
            for path in sorted(candidates, key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True):
                if len(reports) >= limit:
                    break
                key = str(path.resolve(strict=False))
                if key in seen:
                    continue
                seen.add(key)
                name_lower = path.name.lower()
                report_type = "证据报告"
                for needle, label in type_map:
                    if needle in name_lower:
                        report_type = label
                        break
                try:
                    stat = path.stat()
                    preview = path.read_text(encoding="utf-8", errors="replace")[:1600] if path.suffix.lower() == ".md" else json.dumps(read_json(path) or {}, ensure_ascii=False, indent=2)[:1600]
                except OSError:
                    continue
                reports.append(
                    {
                        "id": hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()[:16],
                        "title": path.name,
                        "type": report_type,
                        "path": str(path),
                        "relative_path": path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path),
                        "size_bytes": stat.st_size,
                        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "preview": preview,
                        "trace_id": hashlib.sha256(f"report:{key}".encode("utf-8", errors="replace")).hexdigest()[:12],
                        "export_available": True,
                    }
                )
        required_types = ["文件夹摘要报告", "文档问答报告", "证据报告", "Token Budget 报告", "Gate 报告", "地瓜日记导出"]
        present = {report["type"] for report in reports}
        for label in required_types:
            if label not in present:
                reports.append(
                    {
                        "id": hashlib.sha256(label.encode("utf-8")).hexdigest()[:16],
                        "title": label,
                        "type": label,
                        "path": None,
                        "relative_path": "",
                        "size_bytes": 0,
                        "mtime": None,
                        "preview": "当前没有可预览报告，入口保留 degraded 状态。",
                        "trace_id": f"missing_{hashlib.sha256(label.encode('utf-8')).hexdigest()[:8]}",
                        "export_available": False,
                        "degraded": True,
                    }
                )
        return {"ok": True, "reports": reports[:limit], "report_count": len(reports), "required_types": required_types}

    def export_report_payload(self, report_id: str) -> tuple[int, dict]:
        reports = self.list_reports_payload(limit=200).get("reports") or []
        selected = next((report for report in reports if str(report.get("id")) == str(report_id)), None)
        if not selected:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "report_not_found"}
        if selected.get("degraded") or not selected.get("path"):
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "report_export_degraded", "report": selected}
        source = Path(str(selected.get("path")))
        if not source.exists() or not source.is_file():
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "report_file_missing", "path": str(source)}
        export_dir = self.report_root / "ui_v2_report_exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        target = export_dir / f"{source.stem}_{compact_timestamp()}.md"
        if source.suffix.lower() == ".md":
            text = source.read_text(encoding="utf-8", errors="replace")
        else:
            text = "# Report export\n\n```json\n" + json.dumps(read_json(source) or {}, ensure_ascii=False, indent=2) + "\n```\n"
        target.write_text(text, encoding="utf-8")
        return HTTPStatus.OK, {
            "ok": True,
            "export": {
                "path": str(target),
                "relative_path": target.relative_to(REPO_ROOT).as_posix() if target.is_relative_to(REPO_ROOT) else str(target),
                "size_bytes": target.stat().st_size,
                "source": str(source),
            },
        }

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

    def send_storage_file(self, path: Path, *, preview: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self.send_json({"ok": False, "error": "file_not_found"}, HTTPStatus.NOT_FOUND)
            return
        raw = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        disposition = "inline" if preview else "attachment"
        self.send_header("Content-Disposition", f'{disposition}; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(raw)

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
        if route in {"/ui", "/ui/index.html"}:
            self.send_file_text(REPO_ROOT / "web" / "ai_nas_desktop_v2.html", "text/html; charset=utf-8")
            return
        if route == "/static/digua_ai_nas_v2.css":
            self.send_file_text(REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.css", "text/css; charset=utf-8")
            return
        if route == "/static/digua_ai_nas_v2.js":
            self.send_file_text(REPO_ROOT / "web" / "static" / "digua_ai_nas_v2.js", "application/javascript; charset=utf-8")
            return
        if route in {"/multimodal-search", "/multimodal-search/"}:
            self.send_file_text(REPO_ROOT / "web" / "templates" / "multimodal_search.html", "text/html; charset=utf-8")
            return
        if route == "/static/digua_multimodal_search.css":
            self.send_file_text(REPO_ROOT / "web" / "static" / "digua_multimodal_search.css", "text/css; charset=utf-8")
            return
        if route == "/static/digua_multimodal_search.js":
            self.send_file_text(REPO_ROOT / "web" / "static" / "digua_multimodal_search.js", "application/javascript; charset=utf-8")
            return
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
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            status_code, payload = self.state.storage_list_payload((params.get("path") or [""])[0], user)
            self.send_json(payload, status_code)
            return
        if route == "/api/storage/download":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            rel = (params.get("path") or [""])[0]
            try:
                normalized = normalize_storage_relative_path(rel)
                target = resolve_storage_path(self.state.personal_root, normalized)
            except StoragePathError as exc:
                self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            if not self.state.can_read(user or {}, normalized):
                self.send_json({"ok": False, "error": "permission_denied", "required": "read", "path": normalized}, HTTPStatus.FORBIDDEN)
                return
            preview = (params.get("preview") or [""])[0] in {"1", "true", "yes"}
            self.send_storage_file(target, preview=preview)
            return
        if route == "/api/storage/preview-by-hash":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            path_hash_value = (params.get("path_hash") or [""])[0]
            target, _relative_path = self.state.storage_file_by_path_hash(path_hash_value, user or {})
            if not target:
                self.send_json({"ok": False, "error": "preview_not_found_or_not_authorized"}, HTTPStatus.NOT_FOUND)
                return
            self.send_storage_file(target, preview=True)
            return
        if route == "/api/storage/operations":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            try:
                operations = latest_file_operations(self.state.operation_db_path, limit=50) if self.state.operation_db_path else []
                self.send_json({"ok": True, "operations": operations})
            except Exception as exc:
                self.send_json({"ok": True, "operations": [], "warning": f"operation_log_unavailable:{type(exc).__name__}:{exc}"})
            return
        if route == "/api/documents/list":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            status_code, payload = self.state.document_items_payload((params.get("path") or ["Documents"])[0], user)
            self.send_json(payload, status_code)
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
        if route == "/api/reports/list":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            self.send_json(self.state.list_reports_payload())
            return
        if route.startswith("/api/agent-runtime"):
            if agent_runtime_route_response is None:
                self.send_json({"ok": False, "error": "agent_runtime_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            status_code, result = agent_runtime_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(result, status_code)
            return
        if route.startswith("/api/multimodal-search") or route.startswith("/api/multimodal-index"):
            if multimodal_route_response is None:
                self.send_json({"ok": False, "error": "multimodal_search_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            status_code, result = multimodal_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(result, status_code)
            return
        if route.startswith("/api/yolo-index"):
            if yolo_route_response is None:
                self.send_json({"ok": False, "error": "yolo_index_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            status_code, result = yolo_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(result, status_code)
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
                    "/api/agent-runtime/status",
                    "/api/agent-runtime/tool-manifest",
                    "/api/agent-runtime/memory/stats",
                    "/api/agent-runtime/multimodal-index/status",
                    "/api/agent-runtime/eval/status",
                    "/api/multimodal-search/status",
                    "/api/multimodal-index/stats",
                    "/api/multimodal-index/item/{asset_id}",
                    "/api/multimodal-search/eval/summary",
                    "/api/yolo-index/status",
                    "/api/yolo-index/item/{asset_id}",
                    "/api/yolo-index/eval/summary",
                    "/api/latest",
                    "/api/latest.goal_progress",
                    "/api/latest.operator_decisions",
                    "/api/services",
                    "/api/portal-report",
                    "/api/operator-decisions",
                    "/api/harness/status",
                    "/api/reports/list",
                    "/api/storage/status",
                    "/api/storage/list",
                    "/api/storage/download",
                    "/api/documents/list",
                    "/api/identity/users",
                    "/api/contracts/operator-portal",
                    "/api/token-budget/summary",
                    "/api/token-budget/benchmark-summary",
                    "/api/token-budget/trace/{run_id}",
                    "POST /api/identity/create-user",
                    "POST /api/identity/login",
                    "POST /api/storage/create-folder",
                    "POST /api/storage/upload-file",
                    "POST /api/documents/query",
                    "POST /api/reports/export",
                    "POST /api/nas/copy/preview",
                    "POST /api/nas/copy/dry-run",
                    "POST /api/nas/copy/confirm",
                    "POST /api/nas/copy/execute",
                    "POST /api/nas/copy/rollback",
                    "POST /api/refresh",
                    "POST /api/operator-decision",
                    "POST /api/token-budget/estimate",
                    "POST /api/token-budget/route",
                    "POST /api/agent-runtime/context-pack",
                    "POST /api/agent-runtime/memory/record",
                    "POST /api/agent-runtime/multimodal-index/scan",
                    "POST /api/agent-runtime/rag/query",
                    "POST /api/multimodal-index/rebuild",
                    "POST /api/multimodal-search/query",
                    "POST /api/multimodal-search/eval/run",
                    "POST /api/yolo-index/rebuild",
                    "POST /api/yolo-index/search",
                    "POST /api/yolo-index/eval/run",
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
        if route.startswith("/api/agent-runtime"):
            if agent_runtime_route_response is None:
                self.send_json({"ok": False, "error": "agent_runtime_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
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
            payload = payload or {}
            payload.setdefault("user_id", str((user or {}).get("username") or "operator"))
            status_code, result = agent_runtime_route_response(
                route,
                method="POST",
                payload=payload,
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(result, status_code)
            return
        if route.startswith("/api/multimodal-search") or route.startswith("/api/multimodal-index"):
            if multimodal_route_response is None:
                self.send_json({"ok": False, "error": "multimodal_search_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
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
            payload = payload or {}
            payload.setdefault("user_id", str((user or {}).get("username") or "operator"))
            status_code, result = multimodal_route_response(
                route,
                method="POST",
                payload=payload,
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(result, status_code)
            return
        if route.startswith("/api/yolo-index"):
            if yolo_route_response is None:
                self.send_json({"ok": False, "error": "yolo_index_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
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
            payload = payload or {}
            payload.setdefault("user_id", str((user or {}).get("username") or "operator"))
            status_code, result = yolo_route_response(
                route,
                method="POST",
                payload=payload,
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(result, status_code)
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
        if route == "/api/storage/create-folder":
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
            status_code, result = self.state.storage_create_folder(str(payload.get("path") or ""), user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/storage/upload-file":
            if not self.require_product():
                return
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            if content_length > (MAX_UPLOAD_BYTES * 2):
                self.send_json({"ok": False, "error": "request_too_large", "max_payload_bytes": MAX_UPLOAD_BYTES * 2}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            status_code, result = self.state.storage_upload_file(payload or {}, user or {})
            self.send_json(result, status_code)
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
        if route == "/api/documents/query":
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
            status_code, result = self.state.document_query_payload(
                str(payload.get("query") or payload.get("message") or ""),
                str(payload.get("path") or "Documents"),
                user or {},
            )
            self.send_json(result, status_code)
            return
        if route == "/api/reports/export":
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
            status_code, result = self.state.export_report_payload(str(payload.get("report_id") or ""))
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
                    "POST /api/storage/create-folder",
                    "POST /api/storage/upload-file",
                    "POST /api/documents/query",
                    "POST /api/reports/export",
                    "POST /api/nas/copy/preview",
                    "POST /api/nas/copy/dry-run",
                    "POST /api/nas/copy/confirm",
                    "POST /api/nas/copy/execute",
                    "POST /api/nas/copy/rollback",
                    "POST /api/token-budget/estimate",
                    "POST /api/token-budget/route",
                    "POST /api/agent-runtime/context-pack",
                    "POST /api/agent-runtime/memory/record",
                    "POST /api/agent-runtime/multimodal-index/scan",
                    "POST /api/agent-runtime/rag/query",
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
    parser.add_argument("--operation-db-path", type=Path, default=None)
    parser.add_argument("--document-fts-db-path", type=Path, default=None)
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
    parser.add_argument("--qwen-model", default=None)
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
        operation_db_path=args.operation_db_path,
        document_fts_db_path=args.document_fts_db_path,
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
        qwen_model=args.qwen_model,
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
