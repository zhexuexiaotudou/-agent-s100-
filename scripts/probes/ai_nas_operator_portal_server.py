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
from datetime import datetime, timezone
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
    from src.multimodal_search.schema import connect as connect_multimodal_db
    from src.multimodal_search.schema import migrate as migrate_multimodal_db
except Exception:
    connect_multimodal_db = None  # type: ignore[assignment]
    migrate_multimodal_db = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.yolo_index_routes import yolo_route_response
except Exception:
    yolo_route_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.ai_space_routes import ai_space_route_response
except Exception:
    ai_space_route_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.auto_organizer_routes import auto_organizer_route_response
except Exception:
    auto_organizer_route_response = None  # type: ignore[assignment]

try:
    from src.assistant_trace.routes import assistant_trace_route_response
    from src.assistant_trace.context import AssistantTraceContext
    from src.assistant_trace.recorder import AssistantTraceRecorder
except Exception:
    assistant_trace_route_response = None  # type: ignore[assignment]
    AssistantTraceContext = None  # type: ignore[assignment]
    AssistantTraceRecorder = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.person_attribute_routes import person_attribute_route_response
except Exception:
    person_attribute_route_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.product_jobs_routes import product_jobs_route_response
except Exception:
    product_jobs_route_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.smart_classification_routes import smart_classification_route_response
except Exception:
    smart_classification_route_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.smart_naming_routes import smart_naming_route_response
except Exception:
    smart_naming_route_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.subtitle_extraction_routes import subtitle_extraction_route_response
except Exception:
    subtitle_extraction_route_response = None  # type: ignore[assignment]

try:
    from src.openclaw.routes.document_rag_routes import document_rag_route_response
except Exception:
    document_rag_route_response = None  # type: ignore[assignment]

try:
    from src.product_jobs.queue import ProductJobQueue
except Exception:
    ProductJobQueue = None  # type: ignore[assignment]

try:
    from src.document_classification.classifier import classify_directory as classify_document_directory
except Exception:
    classify_document_directory = None  # type: ignore[assignment]

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
from ai_nas_media import MediaCenter, is_supported_image_bytes
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


try:
    from ai_nas_embedding_adapter import product_embedding_runtime_status, request_product_embedding
except Exception:
    product_embedding_runtime_status = None  # type: ignore[assignment]
    request_product_embedding = None  # type: ignore[assignment]


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
MAX_JSON_BODY_BYTES = 8 * 1024 * 1024
MAX_STREAM_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
STREAM_CHUNK_BYTES = 1024 * 1024
DEFAULT_QWEN_GATEWAY_URL = "http://127.0.0.1:18080"
DEFAULT_QWEN_7B_GATEWAY_URL = "http://127.0.0.1:18081"
DEFAULT_QWEN_MODEL = "Qwen2.5-1.5B-Instruct-S100P-official"
QWEN_7B_MODEL = "Qwen2.5-7B-Instruct-S100P-official"
MINIMAX_MODEL = "custom-gateway/MiniMax-M2.7"
ASSISTANT_MODEL_POLICY_ID = "workspace_harness_auto_v2"
ASSISTANT_USER_MODEL_SELECTION_ALLOWED = False


def assistant_workspace(action_intent: dict | None, router: dict) -> str:
    action = str((action_intent or {}).get("action") or "")
    if action in {"search", "media_index", "media_summary", "media_create_album"}:
        return "media_photo"
    if action in {"document_query", "journal_summary", "journal_manual_entry"}:
        return "document_rag"
    if action in {"storage_list", "storage_list_or_inspect", "storage_inventory", "storage_status"}:
        return "nas_search"
    if action in {"storage_copy", "storage_rename", "storage_create_folder", "snapshot_create", "backup_create_task", "backup_run"}:
        return "nas_action"
    if action == "ops_summary":
        return "ops_recovery"
    if action in {"apps_summary", "audit_summary", "reports_list"}:
        return "admin_audit"
    if router.get("route") == "cloud" and router.get("privacy_level") == "none" and not router.get("local_tool_id"):
        return "web_cloud_research"
    return "main_router"


def assistant_answer_model_plan(action_intent: dict | None, router: dict) -> dict:
    workspace = assistant_workspace(action_intent, router)
    if action_intent:
        return {
            "workspace": workspace,
            "route": "LOCAL_1_5B",
            "kind": "workspace_tool_response",
            "model": None,
            "provider": "local_policy",
            "location": "S100P",
            "reason": "Workspace tool intent is handled by deterministic policy and the allowlisted dispatcher before any answer-model preference.",
        }
    if workspace == "web_cloud_research":
        return {
            "workspace": workspace,
            "route": "CLOUD_MINIMAX",
            "kind": "cloud_answer",
            "model": MINIMAX_MODEL,
            "provider": "openclaw_minimax",
            "location": "controlled_cloud",
            "reason": "The deterministic policy approved a public, non-private complex request that explicitly needs current external information.",
        }
    policy_route = router.get("policy_route") if isinstance(router.get("policy_route"), dict) else {}
    local_complex = policy_route.get("task_complexity") == "complex"
    if router.get("route") == "local" and local_complex:
        return {
            "workspace": workspace,
            "route": "LOCAL_7B",
            "kind": "local_complex_answer",
            "model": QWEN_7B_MODEL,
            "provider": "local_qwen",
            "location": "S100P_CPU",
            "reason": "Complex work must remain local, so the policy selected the higher-quality local 7B answer model.",
        }
    return {
        "workspace": workspace,
        "route": "LOCAL_1_5B",
        "kind": "local_default_answer",
        "model": DEFAULT_QWEN_MODEL,
        "provider": "local_qwen",
        "location": "S100P_BPU",
        "reason": "The default local 1.5B model is sufficient for a simple request.",
    }


def assistant_model_call(
    *,
    stage: str,
    model: str,
    provider: str,
    location: str,
    purpose: str,
    elapsed_ms: object = None,
    status: str = "completed",
) -> dict:
    return {
        "stage": stage,
        "model": model,
        "provider": provider,
        "location": location,
        "purpose": purpose,
        "status": status,
        "elapsed_ms": elapsed_ms,
    }


def assistant_router_model_calls(router: dict) -> list[dict]:
    recorded = router.get("model_calls")
    if isinstance(recorded, list):
        return [dict(call) for call in recorded if isinstance(call, dict)]
    try:
        attempt_count = max(1, min(int(router.get("router_attempt_count") or 1), 2))
    except (TypeError, ValueError):
        attempt_count = 1
    calls: list[dict] = []
    for index in range(attempt_count):
        calls.append(
            assistant_model_call(
                stage="semantic_router" if index == 0 else "semantic_router_fallback",
                model=DEFAULT_QWEN_MODEL,
                provider="local_qwen",
                location="S100P_BPU",
                purpose="intent_privacy_complexity_and_workspace_advice",
                elapsed_ms=router.get("elapsed_ms") if index == attempt_count - 1 else None,
                status="completed" if index == attempt_count - 1 else "invalid_structured_result",
            )
        )
    return calls


def assistant_workspace_response_calls(payload: dict) -> list[dict]:
    if not payload.get("qwen_document_answer_attempted"):
        return []
    try:
        retry_count = max(0, int(payload.get("qwen_document_answer_retry_attempts") or 0))
    except (TypeError, ValueError):
        retry_count = 0
    answer_succeeded = bool(payload.get("qwen_document_answer_used"))
    calls = [
        assistant_model_call(
            stage="workspace_grounded_answer",
            model=str(payload.get("grounded_answer_model") or DEFAULT_QWEN_MODEL),
            provider="local_qwen",
            location="S100P_BPU",
            purpose="grounded_document_answer_from_local_evidence",
            elapsed_ms=payload.get("grounded_answer_elapsed_ms") if retry_count == 0 else None,
            status="completed" if answer_succeeded and retry_count == 0 else "failed_or_rejected_by_grounding_validation",
        )
    ]
    for retry_index in range(retry_count):
        calls.append(
            assistant_model_call(
                stage="workspace_grounded_answer_retry",
                model=str(payload.get("grounded_answer_model") or DEFAULT_QWEN_MODEL),
                provider="local_qwen",
                location="S100P_BPU",
                purpose=f"grounding_validation_retry_{retry_index + 1}",
                elapsed_ms=payload.get("grounded_answer_elapsed_ms") if retry_index == retry_count - 1 else None,
                status="completed" if answer_succeeded and retry_index == retry_count - 1 else "failed_or_rejected_by_grounding_validation",
            )
        )
    return calls


def attach_assistant_model_routing(
    payload: dict,
    *,
    router: dict,
    plan: dict,
    calls: list[dict],
    requested_model_choice: object = None,
    request_id: str | None = None,
) -> dict:
    requested = str(requested_model_choice or "").strip()
    answer_calls = [call for call in calls if call.get("stage") not in {"semantic_router", "semantic_router_fallback"}]
    effective_model = str((answer_calls[-1] if answer_calls else {}).get("model") or "") or None
    policy = router.get("policy_route") if isinstance(router.get("policy_route"), dict) else router
    decision = {
        "request_id": request_id,
        "selected_route": plan.get("route"),
        "privacy_level": policy.get("privacy_level_numeric", 0),
        "privacy_label": policy.get("privacy_level", "none"),
        "complexity": policy.get("complexity_level", 0),
        "freshness_required": bool(policy.get("freshness_required")),
        "requires_public_web": bool(policy.get("requires_public_web")),
        "requires_local_data": bool(policy.get("requires_local_data")),
        "write_risk": policy.get("write_risk", "none"),
        "confirmation_required": bool(policy.get("confirmation_required")),
        "selected_tools": list(policy.get("selected_tools") or []),
        "cloud_egress_allowed": bool(policy.get("cloud_eligible")) and plan.get("route") == "CLOUD_MINIMAX",
        "hybrid_candidate": bool(policy.get("hybrid_candidate")),
        "hybrid_status": policy.get("hybrid_status", "not_applicable"),
        "reason_summary": plan.get("reason"),
        "fallback_from_route": plan.get("fallback_from_route"),
    }
    payload["request_id"] = request_id
    payload["selected_workspace"] = plan.get("workspace")
    payload["model_routing"] = {
        "policy_id": ASSISTANT_MODEL_POLICY_ID,
        "user_selectable": ASSISTANT_USER_MODEL_SELECTION_ALLOWED,
        "default_model": DEFAULT_QWEN_MODEL,
        "selected_workspace": plan.get("workspace"),
        "answer_kind": plan.get("kind"),
        "planned_answer_model": plan.get("model"),
        "effective_answer_model": effective_model,
        "selection_reason": plan.get("reason"),
        "decision": decision,
        "requested_model_ignored": requested or None,
        "calls": calls,
    }
    payload["user_model_selection_allowed"] = False
    payload["routing_decision"] = decision
    return payload
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
COPILOT_COMPLEX_REASONING_TERMS = (
    "analyze",
    "compare",
    "research",
    "report",
    "plan",
    "market",
    "strategy",
    "industry",
    "trend",
    "launch",
    "competitor",
    "public",
    "\u5206\u6790",
    "\u5bf9\u6bd4",
    "\u8c03\u7814",
    "\u62a5\u544a",
    "\u65b9\u6848",
    "\u5e02\u573a",
    "\u6218\u7565",
    "\u884c\u4e1a",
    "\u8d8b\u52bf",
    "\u53d1\u5e03",
    "\u7ade\u54c1",
    "\u516c\u5f00",
)
COPILOT_FRESHNESS_TERMS = (
    "today",
    "current",
    "latest",
    "recent",
    "this year",
    "price",
    "firmware",
    "vulnerability",
    "cve",
    "news",
    "stable version",
    "\u4eca\u5929",
    "\u5f53\u524d",
    "\u73b0\u5728",
    "\u6700\u65b0",
    "\u6700\u8fd1",
    "\u4eca\u5e74",
    "\u4ef7\u683c",
    "\u56fa\u4ef6",
    "\u6f0f\u6d1e",
    "\u65b0\u95fb",
    "\u7a33\u5b9a\u7248",
)
COPILOT_PUBLIC_WEB_TERMS = COPILOT_FRESHNESS_TERMS + (
    "internet",
    "web",
    "online",
    "public information",
    "\u8054\u7f51",
    "\u7f51\u4e0a",
    "\u5728\u7ebf",
    "\u516c\u5f00\u4fe1\u606f",
)
COPILOT_NO_CLOUD_TERMS = (
    "offline",
    "local only",
    "do not use internet",
    "do not go online",
    "\u4e0d\u8981\u8054\u7f51",
    "\u7981\u6b62\u8054\u7f51",
    "\u4ec5\u672c\u5730",
)
COPILOT_PERSONAL_SCOPE_TERMS = (
    "this file",
    "this document",
    "this photo",
    "my nas",
    "\u6211\u7684",
    "\u6211\u4eec\u7684",
    "\u8fd9\u4e2a\u6587\u4ef6",
    "\u8fd9\u4efd\u6587\u6863",
    "\u8fd9\u5f20\u7167\u7247",
)
COPILOT_NEVER_CLOUD_TERMS = (
    "password",
    "api key",
    "token",
    "secret",
    "passport",
    "identity card",
    "bank card",
    "medical",
    "face",
    "serial number",
    "internal ip",
    "invoice",
    "contract",
    "\u5bc6\u7801",
    "\u4ee4\u724c",
    "\u5bc6\u94a5",
    "\u62a4\u7167",
    "\u8eab\u4efd\u8bc1",
    "\u94f6\u884c\u5361",
    "\u533b\u7597",
    "\u4f53\u68c0",
    "\u4eba\u8138",
    "\u5e8f\u5217\u53f7",
    "\u5185\u7f51 ip",
    "\u53d1\u7968",
    "\u5408\u540c",
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
COPILOT_JOURNAL_WRITE_TERMS = (
    "write",
    "record",
    "write journal",
    "write diary",
    "record journal",
    "record diary",
    "\u8bb0\u5f55\u65e5\u8bb0",
    "\u5199\u65e5\u8bb0",
    "\u5199\u5165\u65e5\u8bb0",
    "\u8bb0\u4e00\u6761",
    "\u5199\u4e00\u6761",
    "\u65b0\u589e\u65e5\u8bb0",
)
COPILOT_JOURNAL_ACTIVITY_QUERY_TERMS = (
    "what did i do",
    "where did i go",
    "what was i doing",
    "\u5e72\u4ec0\u4e48",
    "\u5e72\u4e86\u4ec0\u4e48",
    "\u5e72\u8fc7\u4ec0\u4e48",
    "\u505a\u4e86\u4ec0\u4e48",
    "\u505a\u4ec0\u4e48",
    "\u505a\u8fc7\u4ec0\u4e48",
    "\u5fd9\u4ec0\u4e48",
    "\u5fd9\u4e86\u4ec0\u4e48",
    "\u6539\u4e86\u4ec0\u4e48",
    "\u5b8c\u6210\u4e86\u4ec0\u4e48",
    "\u5904\u7406\u4e86\u4ec0\u4e48",
    "\u53bb\u4e86\u54ea\u91cc",
    "\u53bb\u54ea\u4e86",
    "\u5403\u4e86\u4ec0\u4e48",
)
COPILOT_JOURNAL_HISTORY_QUERY_TERMS = (
    "my history",
    "my records",
    "activity record",
    "work record",
    "\u6211\u7684\u8bb0\u5f55",
    "\u6211\u7684\u5386\u53f2",
    "\u6211\u7684\u884c\u7a0b",
    "\u5de5\u4f5c\u8bb0\u5f55",
    "\u5386\u53f2\u8bb0\u5f55",
    "\u884c\u7a0b\u8bb0\u5f55",
    "\u6709\u54ea\u4e9b\u8bb0\u5f55",
    "\u8bb0\u5f55\u4e86\u4ec0\u4e48",
    "\u5f53\u5929\u8bb0\u5f55",
    "\u5f53\u65e5\u8bb0\u5f55",
    "\u90a3\u5929\u7684\u8bb0\u5f55",
)
COPILOT_FULL_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(20\d{2})\s*\u5e74\s*(\d{1,2})\s*\u6708\s*(\d{1,2})\s*[\u65e5\u53f7]"),
    re.compile(r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)"),
)
COPILOT_PARTIAL_DATE_PATTERNS = (
    re.compile(r"(?<![\d\u5e74])(\d{1,2})\s*\u6708\s*(\d{1,2})\s*[\u65e5\u53f7]?"),
    re.compile(r"(?<![\d.])(\d{1,2})[./](\d{1,2})(?![\d.])"),
)
COPILOT_DOCUMENT_QUERY_TERMS = (
    "document",
    "doc",
    "pdf",
    "invoice",
    "receipt",
    "contract",
    "bill",
    "expense",
    "amount",
    "rag",
    "\u6587\u6863",
    "\u6587\u4ef6",
    "\u53d1\u7968",
    "\u6536\u636e",
    "\u8d26\u5355",
    "\u5f00\u652f",
    "\u91d1\u989d",
    "\u5408\u540c",
    "\u95ee\u7b54",
)
COPILOT_DOCUMENT_QUERY_ACTION_TERMS = (
    "query",
    "find",
    "search",
    "summarize",
    "summary",
    "amount",
    "total",
    "info",
    "content",
    "\u67e5",
    "\u627e",
    "\u95ee",
    "\u603b\u7ed3",
    "\u6458\u8981",
    "\u91d1\u989d",
    "\u5408\u8ba1",
    "\u603b\u989d",
    "\u591a\u5c11",
    "\u4fe1\u606f",
    "\u5185\u5bb9",
)
COPILOT_STATUS_TERMS = ("status", "health", "summary", "list", "report", "audit", "\u72b6\u6001", "\u5065\u5eb7", "\u6982\u89c8", "\u6c47\u603b", "\u5217\u8868", "\u62a5\u544a", "\u5ba1\u8ba1")
COPILOT_REPORT_LIST_TERMS = (
    "list reports",
    "reports list",
    "show reports",
    "local reports",
    "report status",
    "\u62a5\u544a\u5217\u8868",
    "\u5217\u51fa\u62a5\u544a",
    "\u67e5\u770b\u62a5\u544a",
    "\u672c\u5730\u62a5\u544a",
    "\u62a5\u544a\u72b6\u6001",
)
COPILOT_STORAGE_INVENTORY_TERMS = (
    "what files",
    "which files",
    "how many files",
    "file count",
    "number of files",
    "count files",
    "file inventory",
    "inventory",
    "file types",
    "how much space",
    "space usage",
    "disk usage",
    "storage usage",
    "\u6709\u4ec0\u4e48\u6587\u4ef6",
    "\u6709\u54ea\u4e9b\u6587\u4ef6",
    "\u6709\u591a\u5c11\u6587\u4ef6",
    "\u591a\u5c11\u6587\u4ef6",
    "\u51e0\u4e2a\u6587\u4ef6",
    "\u591a\u5c11\u4e2a\u6587\u4ef6",
    "\u6587\u4ef6\u6570",
    "\u6587\u4ef6\u6570\u91cf",
    "\u4e00\u5171\u6709\u591a\u5c11",
    "\u603b\u5171\u6709\u591a\u5c11",
    "\u7edf\u8ba1\u6587\u4ef6",
    "\u6587\u4ef6\u7edf\u8ba1",
    "\u76d8\u70b9\u6587\u4ef6",
    "\u6587\u4ef6\u76d8\u70b9",
    "\u76ee\u5f55\u7edf\u8ba1",
    "\u54ea\u4e9b\u6587\u4ef6",
    "\u4ec0\u4e48\u6587\u4ef6",
    "\u5206\u522b\u662f\u4ec0\u4e48\u7c7b\u578b",
    "\u90fd\u662f\u4ec0\u4e48\u7c7b\u578b",
    "\u5404\u662f\u4ec0\u4e48\u7c7b\u578b",
    "\u6309\u7c7b\u578b",
    "\u6587\u4ef6\u7c7b\u578b",
    "\u7c7b\u578b",
    "\u5360\u591a\u5927\u7a7a\u95f4",
    "\u5360\u7528\u7a7a\u95f4",
    "\u5360\u7528\u591a\u5c11",
    "\u5360\u591a\u5c11",
    "\u7a7a\u95f4\u5360\u7528",
    "\u591a\u5927\u7a7a\u95f4",
    "\u591a\u5927",
    "\u5bb9\u91cf",
    "\u5927\u5c0f",
    "\u4fe1\u606f",
    "\u60c5\u51b5",
    "\u6982\u51b5",
)


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


def cloud_chat_timeout_seconds() -> int:
    try:
        configured = int(os.environ.get("AI_NAS_CLOUD_CHAT_TIMEOUT_SECONDS", "210"))
    except ValueError:
        configured = 210
    return max(30, min(configured, 300))


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def is_local_assistant_identity_question(message: str) -> bool:
    normalized = re.sub(r"[\s\?\uff1f!\uff01,\uff0c.\u3002:\uff1a]+", "", str(message or "")).lower()
    return normalized in {"\u4f60\u662f\u8c01", "\u4f60\u662f\u4ec0\u4e48", "\u4f60\u662f\u4ec0\u4e48\u52a9\u624b", "whoareyou", "whatareyou"}


def _router_debug_redact(text: str) -> str:
    redacted = str(text or "")
    redacted = re.sub(r"(?i)\b(invoice|contract)\b", "[private-marker]", redacted)
    redacted = re.sub(r"(?i)\bPersonal/[^\s\"']*", "[private-path]", redacted)
    redacted = re.sub(r"(?i)\b(发票|合同|家庭照片|金额)\b", "[private-marker]", redacted)
    return redacted


def product_hidden_storage_name(name: str) -> bool:
    value = str(name or "").strip()
    if not value:
        return False
    if value.startswith("."):
        return True
    return bool(
        re.search(r"^(Codex|OpenClaw|qwen25|qwen3|ai_nas_|yolo_run_|production_|stage\d+_|tmp_)", value, re.IGNORECASE)
        or re.search(
            r"(QwenRouter|ProductUiSmoke|CodexPreflight|agent_runtime|capability_inventory|eval_gate|safety_ui_gate|tool_manifest|context_pack|probe|gate|manifest)",
            value,
            re.IGNORECASE,
        )
    )


AI_ALBUM_PERSONAL_MATERIAL_DIRS = (
    "Photos",
    "Movies",
    "Documents",
    "DemoDocs",
    "Uploads",
    "Inbox",
    "Collections",
    "Sorted",
    "AI整理",
)

AI_ALBUM_NAS_MATERIAL_DIRS = (
    "demo_data",
    "yolo_v2_fixture",
    "documents",
    "photos",
    "robot_datasets",
)

AI_ALBUM_DEMO_CORPUS_MATERIAL_DIRS = (
    "samples_generated",
    "downloaded",
)

AI_ALBUM_MATERIAL_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".md",
    ".xlsx",
    ".pptx",
    ".csv",
}

AI_ALBUM_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}

AI_ALBUM_AUTO_MAX_FILES = 10000

AI_ALBUM_PRIMARY_CATEGORIES = (
    {
        "id": "cat_album_primary_people",
        "name": "人物生活",
        "name_en": "People and Daily Life",
        "icon": "user",
        "description": "人物、肖像、家庭、日常生活照片。",
        "clip_prompt": "a photo of people, portraits, family, friends, daily life",
        "object_terms": ("person", "people", "human"),
        "person_terms": ("person_present",),
        "title_terms": ("person", "people", "portrait", "family", "friends", "人物", "人像", "家庭", "合影"),
    },
    {
        "id": "cat_album_primary_animals",
        "name": "动物",
        "name_en": "Animals",
        "icon": "paw",
        "description": "宠物、野生动物和其他动物照片。",
        "clip_prompt": "a photo of animals, pets, cats, dogs, wildlife",
        "object_terms": ("cat", "dog", "bird", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "animal"),
        "person_terms": (),
        "title_terms": ("cat", "dog", "pet", "animal", "wildlife", "kitten", "puppy", "猫", "狗", "宠物", "动物"),
    },
    {
        "id": "cat_album_primary_landscape",
        "name": "自然风景",
        "name_en": "Nature and Landscape",
        "icon": "mountain",
        "description": "山水、海边、森林、天空、户外风景。",
        "clip_prompt": "a landscape nature photo, mountains, beach, ocean, forest, sky, outdoor scenery",
        "object_terms": ("kite", "surfboard", "skis", "snowboard"),
        "person_terms": (),
        "title_terms": ("mountain", "beach", "ocean", "sea", "lake", "river", "forest", "tree", "grass", "sky", "cloud", "landscape", "travel", "outdoor", "风景", "旅行", "山", "海", "森林", "天空", "草地"),
    },
    {
        "id": "cat_album_primary_city",
        "name": "城市建筑",
        "name_en": "City and Architecture",
        "icon": "home",
        "description": "城市、街道、建筑、桥梁、室内空间。",
        "clip_prompt": "a city architecture photo, buildings, streets, bridges, rooms, urban scenes",
        "object_terms": ("traffic light", "stop sign", "parking meter", "bench", "fire hydrant"),
        "person_terms": (),
        "title_terms": ("building", "city", "street", "road", "bridge", "architecture", "urban", "room", "hotel", "城市", "建筑", "街道", "桥", "室内"),
    },
    {
        "id": "cat_album_primary_transport",
        "name": "交通工具",
        "name_en": "Transportation",
        "icon": "car",
        "description": "汽车、公交、火车、飞机、船和道路交通。",
        "clip_prompt": "a photo of vehicles and transportation, cars, buses, trains, airplanes, boats",
        "object_terms": ("car", "bus", "truck", "bicycle", "motorcycle", "train", "airplane", "boat"),
        "person_terms": (),
        "title_terms": ("car", "bus", "truck", "train", "airplane", "boat", "vehicle", "traffic", "汽车", "车辆", "公交", "火车", "飞机", "船"),
    },
    {
        "id": "cat_album_primary_food",
        "name": "食物饮品",
        "name_en": "Food and Drinks",
        "icon": "utensils",
        "description": "餐食、饮料、聚餐、食材。",
        "clip_prompt": "a photo of food, drinks, meals, restaurants, dishes",
        "object_terms": ("banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "cup", "bottle", "wine glass", "bowl", "dining table"),
        "person_terms": (),
        "title_terms": ("food", "meal", "dinner", "drink", "restaurant", "dish", "party", "食物", "饮品", "餐", "聚餐", "菜"),
    },
    {
        "id": "cat_album_primary_docs",
        "name": "文档截图",
        "name_en": "Documents and Screenshots",
        "icon": "docs",
        "description": "截图、扫描件、票据、合同、课程资料、文字图片。",
        "clip_prompt": "a screenshot or scanned document, text, forms, receipts, contracts, course material",
        "object_terms": ("book", "laptop", "keyboard", "mouse", "cell phone", "tv"),
        "person_terms": (),
        "title_terms": ("screenshot", "screen", "invoice", "receipt", "contract", "document", "paper", "book", "course", "scan", "截图", "票据", "发票", "合同", "资料", "文档", "课程", "扫描"),
    },
    {
        "id": "cat_album_primary_other",
        "name": "其他图片",
        "name_en": "Other Images",
        "icon": "media",
        "description": "证据不足、抽象、物体特写或暂不适合细分的图片。",
        "clip_prompt": "an abstract, texture, object, miscellaneous or uncategorized photo",
        "object_terms": (),
        "person_terms": (),
        "title_terms": ("image", "photo", "misc", "other", "图片", "照片", "其他"),
    },
)

AI_ALBUM_PRIMARY_CATEGORY_IDS = {str(item["id"]) for item in AI_ALBUM_PRIMARY_CATEGORIES}
AI_ALBUM_PRIMARY_CATEGORY_NAMES = {str(item["name"]) for item in AI_ALBUM_PRIMARY_CATEGORIES}
AI_ALBUM_COPILOT_CATEGORY_ALIASES = {
    "cat_album_primary_people": (
        "人物",
        "人像",
        "有人",
        "有人的",
        "有人物",
        "人的照片",
        "人物照片",
        "肖像",
        "合影",
        "家庭",
        "朋友",
        "person",
        "people",
        "human",
        "portrait",
        "family",
    ),
    "cat_album_primary_animals": ("动物", "宠物", "猫", "狗", "鸟", "animal", "animals", "pet", "cat", "dog", "wildlife"),
    "cat_album_primary_landscape": ("风景", "自然", "山", "海", "森林", "天空", "草地", "户外", "landscape", "nature", "mountain", "beach", "forest", "sky"),
    "cat_album_primary_city": ("城市", "建筑", "街道", "桥", "室内", "city", "building", "architecture", "street", "bridge", "urban"),
    "cat_album_primary_transport": ("车辆", "交通", "汽车", "公交", "火车", "飞机", "船", "car", "vehicle", "transport", "bus", "train", "airplane", "boat"),
    "cat_album_primary_food": ("食物", "餐食", "饮品", "饮料", "美食", "food", "drink", "meal", "restaurant"),
    "cat_album_primary_docs": ("文档", "截图", "扫描", "票据", "合同", "资料", "课件", "document", "screenshot", "scan", "invoice", "contract"),
    "cat_album_primary_other": ("其他图片", "其它图片", "抽象", "未分类", "other image", "other images"),
}
AI_ALBUM_EXPLICIT_CATEGORY_QUERY_TERMS = (
    "相册分类",
    "相册类别",
    "按分类",
    "按类别",
    "分类里",
    "类别里",
    "分类为",
    "类别为",
    "这个分类",
    "这个类别",
    "category",
    "album category",
)

AI_ALBUM_PROJECT_ARTIFACT_NAMES = {
    ".git",
    ".pytest_cache",
    "01_final_evidence",
    "ai_nas_harness",
    "archive",
    "backups",
    "benchmarks",
    "browser-smoke",
    "config",
    "configs",
    "dist",
    "docs",
    "evidence_for_gptpro",
    "gates",
    "logs",
    "migrations",
    "models",
    "openclaw-plugins",
    "queues",
    "release",
    "reports",
    "runtimes",
    "scripts",
    "src",
    "tests",
    "tmp",
    "toolchains",
}


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    limit = min(len(left), len(right))
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for index in range(limit):
        try:
            a = float(left[index])
            b = float(right[index])
        except (TypeError, ValueError):
            continue
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return dot / ((left_norm ** 0.5) * (right_norm ** 0.5))


def product_file_type(path: Path) -> str:
    if path.is_dir():
        return "\u6587\u4ef6\u5939"
    ext = path.suffix.lower()
    mapping = {
        ".pdf": "PDF",
        ".doc": "Word",
        ".docx": "Word",
        ".xls": "Excel",
        ".xlsx": "Excel",
        ".csv": "CSV",
        ".txt": "TXT",
        ".md": "Markdown",
        ".jpg": "\u7167\u7247",
        ".jpeg": "\u7167\u7247",
        ".png": "\u56fe\u7247",
        ".webp": "\u56fe\u7247",
        ".gif": "\u56fe\u7247",
        ".mp4": "\u89c6\u9891",
        ".mov": "\u89c6\u9891",
        ".mkv": "\u89c6\u9891",
        ".mp3": "\u97f3\u9891",
        ".wav": "\u97f3\u9891",
        ".zip": "\u538b\u7f29\u5305",
        ".json": "JSON",
    }
    if ext in mapping:
        return mapping[ext]
    mime = mimetypes.guess_type(path.name)[0] or ""
    if mime.startswith("image/"):
        return "\u56fe\u7247"
    if mime.startswith("video/"):
        return "\u89c6\u9891"
    if mime.startswith("audio/"):
        return "\u97f3\u9891"
    if mime.startswith("text/"):
        return "\u6587\u672c"
    return "\u6587\u4ef6"


def human_size(size_bytes: int) -> str:
    value = float(max(0, int(size_bytes or 0)))
    units = ["B", "KB", "MB", "GB", "TB"]
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    if unit == 0:
        return f"{int(value)} {units[unit]}"
    return f"{value:.1f} {units[unit]}"


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


def copilot_inventory_path_for_message(message: str, fallback: str = "") -> str:
    text = str(message or "")
    lower = text.lower()
    has_document = "documents" in lower or "document" in lower or "\u6587\u6863" in text or "\u6587\u4ef6" in text
    has_photo = "photos" in lower or "pictures" in lower or "photo" in lower or "image" in lower or "\u7167\u7247" in text or "\u56fe\u7247" in text or "\u76f8\u518c" in text
    has_video = "videos" in lower or "movies" in lower or "video" in lower or "\u89c6\u9891" in text or "\u7535\u5f71" in text
    hit_count = sum(1 for hit in (has_document, has_photo, has_video) if hit)
    if hit_count >= 2:
        return ""
    if has_photo:
        return "Photos"
    if has_video:
        return "Videos"
    if has_document:
        return "Documents"
    return copilot_default_path_for_message(text, fallback)


DOCUMENT_PATH_IN_TEXT_RE = re.compile(r"(?i)\bDocuments(?:/[A-Za-z0-9_.\-\u4e00-\u9fff]+)*")


def copilot_document_path_for_message(message: str, quoted: list[str] | None = None, fallback: str = "Documents") -> str:
    for value in quoted or []:
        if "/" in value or "\\" in value:
            try:
                return normalize_storage_relative_path(value)
            except StoragePathError:
                continue
    match = DOCUMENT_PATH_IN_TEXT_RE.search(str(message or "").replace("\\", "/"))
    if match:
        try:
            return normalize_storage_relative_path(match.group(0))
        except StoragePathError:
            pass
    return copilot_default_path_for_message(message, fallback)


def copilot_action_tool_id(action: str | None) -> str | None:
    if not action:
        return None
    mapping = {
        "search": "local_nas_search",
        "document_query": "local_document_rag",
        "storage_list": "local_storage_list",
        "storage_inventory": "local_storage_inventory",
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


def copilot_journal_lookup_date(message: str, *, default_year: int | None = None) -> str | None:
    text = str(message or "")
    for pattern in COPILOT_FULL_DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        year, month, day = (int(item) for item in match.groups())
        try:
            datetime(year, month, day)
        except ValueError:
            return None
        return f"{year}\u5e74{month}\u6708{day}\u65e5"
    year = int(default_year or datetime.now().year)
    for pattern in COPILOT_PARTIAL_DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        month, day = (int(item) for item in match.groups())
        try:
            datetime(year, month, day)
        except ValueError:
            return None
        return f"{year}\u5e74{month}\u6708{day}\u65e5"
    return None


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
    journal_lookup_date = copilot_journal_lookup_date(text)
    has_journal_activity_query = contains_any(text, COPILOT_JOURNAL_ACTIVITY_QUERY_TERMS)
    has_journal_history_query = contains_any(text, COPILOT_JOURNAL_HISTORY_QUERY_TERMS)
    has_journal_write = contains_any(text, COPILOT_JOURNAL_WRITE_TERMS)
    has_document = contains_any(text, COPILOT_DOCUMENT_QUERY_TERMS)
    has_status = contains_any(text, COPILOT_STATUS_TERMS)
    has_inspect = contains_any(text, COPILOT_INSPECT_TERMS)
    has_storage_scope = contains_any(text, COPILOT_NAS_SCOPE_TERMS) or "nas" in text.lower()
    has_file_scope = "\u6587\u4ef6" in text or "\u6587\u6863" in text or "\u76ee\u5f55" in text or "\u7167\u7247" in text or "file" in text.lower()
    has_inventory_count_term = (
        "\u591a\u5c11" in text
        or "\u51e0\u4e2a" in text
        or "\u6570\u91cf" in text
        or "\u6570\u76ee" in text
        or "\u6587\u4ef6\u6570" in text
        or "\u7edf\u8ba1" in text
        or "\u76d8\u70b9" in text
        or "how many" in text.lower()
        or "count" in text.lower()
    )
    has_inventory_shape_term = (
        "\u4ec0\u4e48" in text
        or "\u54ea\u4e9b" in text
        or "\u6709\u5565" in text
        or "\u6709\u54ea" in text
        or "\u7c7b\u578b" in text
        or "\u7a7a\u95f4" in text
        or "\u5360\u7528" in text
        or "\u5927\u5c0f" in text
        or "\u5bb9\u91cf" in text
    )
    has_inventory_question = has_storage_scope and (
        contains_any(text, COPILOT_STORAGE_INVENTORY_TERMS)
        or ("\u6587\u4ef6" in text and ("\u4ec0\u4e48" in text or "\u54ea\u4e9b" in text or "\u6709\u5565" in text or "\u6709\u54ea" in text))
        or (has_file_scope and has_inventory_count_term)
        or (has_file_scope and has_inventory_shape_term)
        or ("\u7c7b\u578b" in text and ("\u7a7a\u95f4" in text or "\u5927\u5c0f" in text))
    )
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
    if has_journal and has_journal_write:
        return {
            "action": "journal_manual_entry",
            "project_id": "manual",
            "title": quoted[0] if quoted else "",
            "body": quoted[1] if len(quoted) >= 2 else "",
            "quoted": quoted,
        }
    if journal_lookup_date and (has_journal or has_journal_activity_query or has_journal_history_query):
        return {
            "action": "document_query",
            "query": f"{text} {journal_lookup_date}",
            "path": "Documents",
            "journal_lookup": True,
            "journal_date": journal_lookup_date,
            "quoted": quoted,
        }
    if contains_any(text, COPILOT_CREATE_FOLDER_TERMS):
        return {"action": "storage_create_folder", "path": quoted[0] if quoted else "", "quoted": quoted}
    if has_document and (has_summary or contains_any(text, COPILOT_DOCUMENT_QUERY_ACTION_TERMS)):
        return {
            "action": "document_query",
            "query": text,
            "path": copilot_document_path_for_message(text, quoted, "Documents"),
            "quoted": quoted,
        }
    if has_inspect:
        inspect_path = quoted[0] if quoted else copilot_default_path_for_message(text)
        if inspect_path or quoted or "root" in text.lower() or "\u6839\u76ee\u5f55" in text:
            return {"action": "storage_list_or_inspect", "path": inspect_path, "quoted": quoted}
    if has_inventory_question:
        return {"action": "storage_inventory", "path": copilot_inventory_path_for_message(text), "quoted": quoted}
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
    if contains_any(text, COPILOT_REPORT_LIST_TERMS):
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
        "Recommend cloud only for public non-private complex reasoning that explicitly requires current external information. "
        "Recommend local when freshness is not required or the user prohibits internet access. Qwen must not execute tools. "
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


def copilot_write_risk(action: str) -> tuple[str, bool]:
    if action in {"storage_copy", "storage_rename"}:
        return "medium", True
    if action in {"storage_create_folder", "snapshot_create", "backup_create_task"}:
        return "low", False
    if action == "backup_run":
        return "medium", True
    return "none", False


def copilot_policy_route(message: str, action_intent: dict | None = None) -> dict:
    text = str(message or "")
    action = str((action_intent or {}).get("action") or "")
    local_tool_id = copilot_action_tool_id(action)
    has_complex_reasoning = contains_any(text, COPILOT_COMPLEX_REASONING_TERMS) or len(text) > 160
    explicit_public_only = contains_any(text, COPILOT_PUBLIC_ONLY_TERMS)
    contains_never_cloud_data = contains_any(text, COPILOT_NEVER_CLOUD_TERMS) or bool(
        re.search(r"\b(?:10\.|127\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)\d{1,3}(?:\.\d{1,3}){1,2}\b", text)
    )
    has_personal_scope = bool(re.search(r"\b(?:my|our)\b", text, flags=re.IGNORECASE)) or contains_any(
        text, COPILOT_PERSONAL_SCOPE_TERMS
    )
    if contains_never_cloud_data:
        privacy_level = "high"
        privacy_level_numeric = 3
    elif contains_any(text, COPILOT_STRONG_PRIVACY_TERMS) and not (has_complex_reasoning and explicit_public_only and not has_personal_scope):
        privacy_level = "high"
        privacy_level_numeric = 2
    elif (has_personal_scope or contains_any(text, COPILOT_LOCAL_CONTENT_TERMS)) and not (
        has_complex_reasoning and explicit_public_only and not has_personal_scope
    ):
        privacy_level = "medium"
        privacy_level_numeric = 2
    else:
        privacy_level = "none"
        privacy_level_numeric = 0
    freshness_required = contains_any(text, COPILOT_FRESHNESS_TERMS)
    requires_public_web = contains_any(text, COPILOT_PUBLIC_WEB_TERMS)
    cloud_prohibited_by_user = contains_any(text, COPILOT_NO_CLOUD_TERMS)
    requires_local_data = bool(local_tool_id or privacy_level_numeric >= 2 or contains_any(text, COPILOT_LOCAL_CONTENT_TERMS))
    if len(text) > 320:
        complexity_level = 3
    elif has_complex_reasoning:
        complexity_level = 2
    elif local_tool_id:
        complexity_level = 1
    else:
        complexity_level = 0
    hybrid_candidate = bool(requires_local_data and requires_public_web and complexity_level >= 2)
    cloud_eligible = bool(
        not local_tool_id
        and privacy_level_numeric == 0
        and requires_public_web
        and freshness_required
        and complexity_level >= 2
        and not cloud_prohibited_by_user
    )
    if not cloud_eligible:
        route = "local"
        if hybrid_candidate:
            reason = "hybrid candidate stays local because the audited redaction and local-merge pipeline is not enabled"
        elif cloud_prohibited_by_user:
            reason = "the user prohibited cloud access"
        elif requires_public_web and complexity_level >= 2 and not freshness_required:
            reason = "complex public reasoning without a freshness requirement stays local"
        else:
            reason = "local route required by NAS action, privacy floor, or default local-first policy"
    else:
        route = "cloud"
        reason = "public non-private complex work requires current external information and may use guarded cloud overflow"
    write_risk, confirmation_required = copilot_write_risk(action)
    return {
        "route": route,
        "privacy_level": privacy_level,
        "privacy_level_numeric": privacy_level_numeric,
        "task_complexity": "complex" if complexity_level >= 2 else "simple",
        "complexity_level": complexity_level,
        "freshness_required": freshness_required,
        "requires_public_web": requires_public_web,
        "requires_local_data": requires_local_data,
        "contains_never_cloud_data": contains_never_cloud_data,
        "has_personal_scope": has_personal_scope,
        "cloud_prohibited_by_user": cloud_prohibited_by_user,
        "cloud_eligible": cloud_eligible,
        "hybrid_candidate": hybrid_candidate,
        "hybrid_status": "unsupported_safe_splitter_not_enabled" if hybrid_candidate else "not_applicable",
        "write_risk": write_risk,
        "confirmation_required": confirmation_required,
        "selected_tools": [local_tool_id] if local_tool_id else [],
        "reason": reason,
        "local_tool_id": local_tool_id,
        "classifier": "portal_policy_guardrail",
        "original_query_sent": False,
        "qwen_execution_authority": False,
    }


def apply_copilot_guardrail(qwen_route: dict | None, policy_route: dict) -> dict:
    route = dict(qwen_route or policy_route)
    route.setdefault("classifier", "portal_policy_guardrail")
    route["policy_route"] = dict(policy_route)
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
    else:
        if route.get("route") != "local":
            route["guardrail_applied"] = True
            route["guardrail_reason"] = "the deterministic policy keeps simple non-tool requests on the default local model"
        route["route"] = "local"
        route["privacy_level"] = policy_route.get("privacy_level") or "none"
        route["local_tool_id"] = policy_route.get("local_tool_id")
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


def copilot_search_reason_display(reason: object) -> str:
    code = str(reason or "no_matching_local_index_result")
    if code.startswith("image_embedding_search_failed:ValueError") or code.startswith("local_multimodal_search_exception:ValueError"):
        return "\u56fe\u50cf\u8bed\u4e49\u5411\u91cf\u7d22\u5f15\u7248\u672c\u4e0d\u4e00\u81f4\uff1a\u5f53\u524d\u6587\u672c\u5411\u91cf\u4e0e\u5df2\u6709\u56fe\u7247\u5411\u91cf\u7ef4\u5ea6\u4e0d\u4e00\u81f4\uff0c\u9700\u8981\u91cd\u5efa\u56fe\u50cf\u8bed\u4e49\u7d22\u5f15"
    mapping = {
        "local_index_results_without_resolvable_media_preview": "\u65e7\u7d22\u5f15\u7ed3\u679c\u65e0\u6cd5\u89e3\u6790\u5230\u5f53\u524d\u76f8\u518c\u9884\u89c8\uff0c\u5df2\u8fc7\u6ee4",
        "no_matching_yolo_detection": "YOLO \u5bf9\u8c61\u7d22\u5f15\u6ca1\u6709\u547d\u4e2d\u5339\u914d\u56fe\u7247",
        "no_yolo_detections_indexed": "YOLO \u5bf9\u8c61\u7d22\u5f15\u5c1a\u6ca1\u6709\u53ef\u7528\u68c0\u6d4b\u7ed3\u679c",
        "no_matching_person_attribute": "\u4eba\u7269\u5c5e\u6027\u7d22\u5f15\u6ca1\u6709\u547d\u4e2d\u5339\u914d\u56fe\u7247",
        "no_matching_local_index_result": "\u672c\u5730\u89c6\u89c9\u7d22\u5f15\u6ca1\u6709\u547d\u4e2d\u5339\u914d\u56fe\u7247",
    }
    return mapping.get(code, code)


def http_post_json(name: str, url: str, payload: dict, timeout: int = 60, headers: dict[str, str] | None = None) -> dict:
    started = time.perf_counter()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
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
    except (urllib.error.URLError, TimeoutError) as exc:
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
    cleaned = str(query or "").strip().lower()
    parts = [item for item in re.split(r"[\s,，。；;:：?？、|()（）]+", cleaned) if len(item) >= 2]
    if cleaned and cleaned not in parts:
        parts.insert(0, cleaned)
    for pattern in (
        r"\d{4}\u5e74\d{1,2}\u6708\d{1,2}\u65e5",
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        r"\d+(?:\.\d+)?\s*(?:\u5143|\u5757|cny|rmb|usd)",
        r"\d{3,}",
    ):
        parts.extend(match.group(0).lower() for match in re.finditer(pattern, cleaned, flags=re.IGNORECASE))
    for keyword in (
        "\u5bb6\u5ead\u5f00\u652f",
        "\u5bb6\u5ead",
        "\u5f00\u652f",
        "\u8d26\u5355",
        "\u91d1\u989d",
        "\u5408\u8ba1",
        "\u603b\u989d",
        "\u65e5\u671f",
        "\u53d1\u7968",
        "\u6536\u636e",
        "\u5408\u540c",
        "family",
        "expense",
        "bill",
        "amount",
        "total",
    ):
        if keyword in cleaned:
            parts.append(keyword)
    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            deduped.append(part)
    return deduped[:12]


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


DOCUMENT_AMOUNT_RE = re.compile(
    r"(?<!\d)(?:\u4eba\u6c11\u5e01|RMB|CNY)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(\u5143|\u5757|\u7f8e\u5143|USD|RMB|CNY)",
    re.IGNORECASE,
)


def document_amount_hits(evidence: list[dict]) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        text = str(item.get("snippet") or "")
        for match in DOCUMENT_AMOUNT_RE.finditer(text):
            number = match.group(1).replace(",", "")
            unit = match.group(2)
            value = f"{number}{unit}"
            key = value.lower()
            if key not in seen:
                seen.add(key)
                hits.append(value)
    return hits


def document_storage_open_url(relative_path: str, *, preview: bool = True) -> str:
    rel = normalize_storage_relative_path(relative_path)
    suffix = "&preview=1" if preview else ""
    return f"/api/storage/download?path={quote(rel, safe='')}{suffix}"


def build_document_grounded_answer_prompt(query: str, evidence: list[dict]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(evidence[:5], start=1):
        snippet = re.sub(r"\s+", " ", str(item.get("snippet") or item.get("summary") or "")).strip()
        if not snippet:
            continue
        name = Path(str(item.get("name") or item.get("relative_path") or f"document_{index}")).name
        ref = str(item.get("evidence_ref") or f"ev_{index}")
        blocks.append(f"[{index}] ref={ref}; name={name}\n{snippet}")
    evidence_text = "\n\n".join(blocks) or "(no evidence)"
    amounts = document_amount_hits(evidence)
    amount_text = f"\n检测到的金额：{'、'.join(amounts[:5])}" if amounts else ""
    return (
        "根据本地文档证据回答。不要寒暄，不要让用户自己查看文档，不要编造，不要输出 NAS 原始路径。\n"
        f"问题：{query}\n"
        f"证据：\n{evidence_text}{amount_text}\n"
        "答案："
    )


def build_document_grounded_retry_prompt(query: str, evidence: list[dict]) -> str:
    amounts = document_amount_hits(evidence)
    exact_amount = amounts[0] if amounts else ""
    refs = ", ".join(str(item.get("evidence_ref") or f"ev_{index}") for index, item in enumerate(evidence[:3], start=1))
    target_answer = normalize_document_money_answer_sentence(query, exact_amount, evidence) if exact_amount else ""
    target_line = f"Target answer sentence: {target_answer}\n" if target_answer else ""
    return (
        "Answer strictly from local document evidence facts.\n"
        f"Evidence refs: {refs or 'local_document_evidence'}.\n"
        f"Evidence facts: detected_amounts={', '.join(amounts[:5]) if amounts else 'none'}; user_question={query}.\n"
        f"{target_line}"
        "If Target answer sentence is present, return that sentence exactly.\n"
        f"Return exactly one short Chinese sentence. Include the exact text {exact_amount or 'from evidence'}."
        " Do not approximate. Do not ask a follow-up. Do not mention raw NAS paths.\n"
        "Answer:"
    )


def normalize_document_answer_amount_units(answer: str, evidence: list[dict]) -> str:
    normalized = str(answer or "")
    for amount in document_amount_hits(evidence):
        if not contains_any(amount, ("元", "块", "人民币")):
            continue
        token = re.sub(r"\D+", "", amount)
        if not token:
            continue
        normalized = re.sub(rf"(?<![\d.]){re.escape(token)}\s*人民币", f"{token}元", normalized)
    return normalized


def normalize_document_money_answer_sentence(query: str, answer: str, evidence: list[dict]) -> str:
    amounts = document_amount_hits(evidence)
    preferred = [item for item in amounts if contains_any(item, ("元", "块", "人民币"))]
    if not preferred:
        return answer
    text = " ".join([str(query or "")] + [str(item.get("snippet") or "") for item in evidence[:2]])
    if not contains_any(text, ("账单", "开支", "合计", "amount", "bill", "expense", "total")):
        return answer
    date_match = re.search(r"20\d{2}年\d{1,2}月\d{1,2}日", text)
    date_text = date_match.group(0) if date_match else ""
    subject = f"{date_text}家庭开支账单" if date_text and contains_any(text, ("家庭", "开支")) else "该本地文档"
    return f"根据本地文档，{subject}的合计金额是 {preferred[0]}。"




def document_answer_from_evidence(path: str, evidence: list[dict], evidence_refs: list[str]) -> str:
    separator = "\u3001"
    refs = separator.join(evidence_refs)
    names = separator.join(str(item.get("name") or item.get("relative_path")) for item in evidence[:3])
    amounts = document_amount_hits(evidence)
    if amounts:
        direct_answer = normalize_document_money_answer_sentence("", "", evidence)
        if direct_answer:
            return direct_answer
    amount_text = f" \u547d\u4e2d\u91d1\u989d\uff1a{separator.join(amounts[:3])}\u3002" if amounts else ""
    snippets = [str(item.get("snippet") or "").strip() for item in evidence[:2] if str(item.get("snippet") or "").strip()]
    snippet_text = " \u8bc1\u636e\u7247\u6bb5\uff1a" + " / ".join(snippets) if snippets else ""
    return (
        f"\u5df2\u5728\u672c\u5730\u6587\u6863\u7d22\u5f15\u4e2d\u627e\u5230 {len(evidence)} "
        f"\u6761\u8bc1\u636e\uff1a{names}\u3002{amount_text}\u8bc1\u636e\u5f15\u7528\uff1a{refs}\u3002{snippet_text}"
    ).strip()


def journal_evidence_for_date(journal_date: str, evidence: list[dict]) -> list[dict]:
    date_hits = [item for item in evidence if journal_date and journal_date in str(item.get("snippet") or "")]
    preferred = [
        item
        for item in date_hits
        if contains_any(
            f"{item.get('name') or ''} {item.get('relative_path') or ''}",
            ("journal", "diary", "\u65e5\u8bb0", "\u65e5\u5fd7"),
        )
    ]
    return preferred or date_hits


def journal_answer_from_evidence(journal_date: str, evidence: list[dict]) -> str:
    for item in journal_evidence_for_date(journal_date, evidence):
        snippet = re.sub(r"\s+", " ", str(item.get("snippet") or "")).strip()
        start = snippet.find(journal_date)
        if start < 0:
            continue
        entry = snippet[start + len(journal_date) :].strip(" \t\r\n:\uff1a\u3002")
        next_date = re.search(r"(?<!\d)20\d{2}\s*\u5e74\s*\d{1,2}\s*\u6708\s*\d{1,2}\s*\u65e5", entry)
        if next_date:
            entry = entry[: next_date.start()].strip(" \t\r\n:\uff1a\u3002")
        if not entry:
            continue
        name = Path(str(item.get("name") or "\u672c\u5730\u65e5\u8bb0")).stem
        return f"\u6839\u636e\u672c\u5730\u300a{name}\u300b\uff0c{journal_date}\uff1a{entry}"
    return ""


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
        self.storage_write_lock = threading.Lock()
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
        self.ai_album_clip_text_cache: dict[str, dict] = {}
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
            try:
                self.snapshot_store.cleanup_expired_trash(30)
            except Exception as exc:
                sys.stderr.write(f"snapshot trash cleanup degraded: {type(exc).__name__}: {exc}\n")
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

    def media_file_by_path_hash(
        self,
        path_hash: str,
        user: dict,
        cache: dict[str, tuple[Path | None, str | None]] | None = None,
    ) -> tuple[Path | None, str | None]:
        digest = str(path_hash or "").strip().lower()
        if not self.media_center or not re.fullmatch(r"[0-9a-f]{16,64}", digest):
            return None, None
        cache_key = f"media:{digest}"
        if cache is not None and cache_key in cache:
            return cache[cache_key]
        found: tuple[Path | None, str | None] = (None, None)
        target = self.media_center.photo_path_by_hash(digest)
        if target:
            try:
                resolved = target.resolve(strict=True)
                allowed, _denial_status = self.media_preview_access(resolved, user or {})
                if allowed:
                    relative_path = None
                    if self.personal_root:
                        try:
                            relative_path = resolved.relative_to(self.personal_root.resolve(strict=True)).as_posix()
                        except (OSError, ValueError):
                            relative_path = None
                    found = (resolved, relative_path)
            except OSError:
                found = (None, None)
        if cache is not None:
            cache[cache_key] = found
        return found

    def can_write(self, user: dict, relative_path: str) -> bool:
        if not self.identity_store:
            return False
        return self.identity_store.check_acl(str(user.get("username") or ""), relative_path, "write")

    def authorized_asset_scope(self, user: dict) -> dict[str, set[str]] | None:
        """Resolve the caller's current ACL into index identifiers.

        Index databases intentionally avoid raw paths, so authorization must be
        re-evaluated against the current Personal tree on every request instead
        of trusting the ACL state that existed when an index was built.
        """
        if str(user.get("role") or "") == "admin":
            return None
        allowed_hashes: set[str] = set()
        allowed_asset_ids: set[str] = set()
        if not self.personal_root or not self.personal_root.exists():
            return {"path_hashes": allowed_hashes, "asset_ids": allowed_asset_ids}
        personal = self.personal_root.resolve(strict=True)
        scanned = 0
        for path in personal.rglob("*"):
            if scanned >= self.storage_max_files:
                break
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                scanned += 1
                resolved = path.resolve(strict=True)
                rel = resolved.relative_to(personal).as_posix()
                if not self.can_read(user, rel):
                    continue
                allowed_hashes.add(hashlib.sha256(rel.encode("utf-8", errors="surrogateescape")).hexdigest()[:32])
                allowed_hashes.add(hashlib.sha256(str(resolved).encode("utf-8", errors="replace")).hexdigest())
            except (OSError, ValueError):
                continue

        index_tables = (
            (self.report_root / "multimodal_search" / "runtime" / "multimodal_search.db", "mm_assets"),
            (self.report_root / "yolo_index" / "runtime" / "yolo_index.db", "mm_yolo_assets"),
        )
        for db_path, table in index_tables:
            if not db_path.exists():
                continue
            try:
                db_uri_path = str(db_path.resolve()).replace("\\", "/")
                uri = f"file:{quote(db_uri_path, safe='/:')}?mode=ro&immutable=1"
                con = sqlite3.connect(uri, uri=True)
                rows = con.execute(f"SELECT asset_id,path_hash FROM {table}").fetchall()
                con.close()
                allowed_asset_ids.update(str(asset_id) for asset_id, path_hash in rows if str(path_hash or "") in allowed_hashes)
            except sqlite3.DatabaseError:
                continue

        if self.media_center:
            for row in self.media_center.indexed_rows(limit=self.storage_max_files):
                try:
                    path = Path(str(row.get("file_path") or "")).resolve(strict=True)
                    rel = path.relative_to(personal).as_posix()
                except (OSError, ValueError):
                    continue
                if self.can_read(user, rel):
                    allowed_asset_ids.add(str(row.get("asset_id") or ""))
                    allowed_hashes.add(str(row.get("path_hash") or ""))
        return {"path_hashes": allowed_hashes, "asset_ids": allowed_asset_ids}

    def filter_index_payload(self, payload: dict, user: dict) -> dict:
        scope = self.authorized_asset_scope(user)
        if scope is None:
            return payload
        allowed_ids = scope["asset_ids"]
        allowed_hashes = scope["path_hashes"]
        denied = object()

        def filtered(value, *, parent_key: str = ""):
            if isinstance(value, dict):
                asset_id = str(value.get("asset_id") or "")
                path_hash = str(value.get("path_hash") or "")
                if asset_id and asset_id not in allowed_ids:
                    return denied
                if path_hash and path_hash not in allowed_hashes:
                    return denied
                out: dict = {}
                for key, item in value.items():
                    if key == "asset_ids" and isinstance(item, list):
                        visible_ids = [entry for entry in item if str(entry) in allowed_ids]
                        out[key] = visible_ids
                        if "count" in value:
                            out["count"] = len(visible_ids)
                        continue
                    result = filtered(item, parent_key=key)
                    if result is not denied:
                        out[key] = result
                return out
            if isinstance(value, list):
                rows = []
                for item in value:
                    result = filtered(item, parent_key=parent_key)
                    if result is not denied:
                        rows.append(result)
                return rows
            return value

        result = filtered(payload)
        if result is denied or not isinstance(result, dict):
            result = {"ok": False, "error": "not_found"}
        for list_key, count_key in (("results", "result_count"), ("assets", "asset_count"), ("photos", "photo_count"), ("items", "item_count")):
            if isinstance(result.get(list_key), list):
                result[count_key] = len(result[list_key])
        result["acl_scope"] = "current_user"
        result["acl_filtered"] = True
        return result

    def visible_media_payload(self, user: dict, *, library_only: bool = False) -> dict:
        media = self.media_center
        if not media:
            return {"photos": [], "timeline": [], "albums": [], "duplicates": [], "stats": {}}
        scope = self.authorized_asset_scope(user)
        allowed_ids = None if scope is None else scope["asset_ids"]
        library_root = self.personal_root / "Photos" if library_only and self.personal_root else None
        rows = media.list_photos(limit=self.storage_max_files, path_prefix=library_root)
        photos = rows if allowed_ids is None else [row for row in rows if str(row.get("asset_id") or "") in allowed_ids]
        dates: dict[str, int] = {}
        for row in photos:
            taken_at = str(row.get("taken_at") or "")
            if taken_at:
                day = taken_at[:10]
                dates[day] = dates.get(day, 0) + 1
        timeline = [{"date": day, "count": dates[day]} for day in sorted(dates, reverse=True)]
        visible_ids = {str(row.get("asset_id") or "") for row in photos}
        duplicates = []
        for group in media.find_duplicates():
            members = [asset_id for asset_id in group.get("asset_ids") or [] if str(asset_id) in visible_ids]
            if len(members) > 1:
                duplicates.append({**group, "asset_ids": members, "count": len(members)})
        albums = []
        for album in media.list_albums():
            album_photos = [row for row in media.get_album_photos(str(album.get("name") or "")) if str(row.get("asset_id") or "") in visible_ids]
            if album_photos or allowed_ids is None:
                albums.append({**album, "item_count": len(album_photos) if allowed_ids is not None else album.get("item_count", 0)})
        stats = {
            "photo_count": len(photos),
            "video_count": 0,
            "media_count": len(photos),
            "album_count": len(albums),
            "duplicate_group_count": len(duplicates),
            "raw_path_returned": False,
            "acl_scope": "all" if allowed_ids is None else "current_user",
        }
        return {
            "photos": photos,
            "timeline": timeline,
            "albums": albums,
            "duplicates": duplicates,
            "stats": stats,
            "photo_scope": "library" if library_only else "all_indexed",
        }

    def _relative_path_for_personal_file(self, path: Path) -> str | None:
        if not self.personal_root:
            return None
        try:
            resolved = path.resolve(strict=True)
            personal = self.personal_root.resolve(strict=True)
            return resolved.relative_to(personal).as_posix()
        except (OSError, ValueError):
            return None

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

    def storage_inventory_payload(self, relative_path: str = "", user: dict | None = None, *, limit: int = 40) -> tuple[int, dict]:
        if not self.personal_root:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "personal_root_not_configured"}
        rel = normalize_storage_relative_path(relative_path)
        if user and not self.can_read(user, rel):
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "read", "path": rel}
        try:
            directory = resolve_storage_path(self.personal_root, rel)
            if not directory.exists():
                raise FileNotFoundError(str(directory))
            if not directory.is_dir():
                raise NotADirectoryError(str(directory))
        except (StoragePathError, FileNotFoundError, NotADirectoryError) as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}

        scan_budget = max(1, min(int(self.storage_max_files or 5000), 5000))
        scanned_files = 0
        truncated = False
        entries: list[dict] = []
        type_counts: dict[str, int] = {}
        total_size = 0
        total_files = 0
        total_dirs = 0

        def add_type(label: str, count: int = 1) -> None:
            type_counts[label] = int(type_counts.get(label, 0)) + count

        def dir_usage(path: Path) -> tuple[int, int, int, bool]:
            nonlocal scanned_files
            size = 0
            file_count = 0
            dir_count = 0
            hit_limit = False
            for root, dirs, files in os.walk(path):
                dirs[:] = [name for name in dirs if not product_hidden_storage_name(name)]
                if Path(root) != path:
                    dir_count += 1
                for filename in files:
                    if product_hidden_storage_name(filename):
                        continue
                    if scanned_files >= scan_budget:
                        return size, file_count, dir_count, True
                    scanned_files += 1
                    file_count += 1
                    try:
                        child = Path(root) / filename
                        size += child.stat().st_size
                        add_type(product_file_type(child))
                    except OSError:
                        continue
            return size, file_count, dir_count, hit_limit

        try:
            children = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}

        for child in children:
            if product_hidden_storage_name(child.name):
                continue
            try:
                stat = child.stat()
            except OSError:
                continue
            item_type = product_file_type(child)
            if child.is_dir():
                size, file_count, dir_count, hit_limit = dir_usage(child)
                truncated = truncated or hit_limit
                total_dirs += 1 + dir_count
                total_files += file_count
                add_type("\u6587\u4ef6\u5939")
                entry = {
                    "name": child.name,
                    "is_dir": True,
                    "file_type": item_type,
                    "size_bytes": size,
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(),
                }
            else:
                if scanned_files >= scan_budget:
                    truncated = True
                    continue
                scanned_files += 1
                total_files += 1
                size = stat.st_size
                add_type(item_type)
                entry = {
                    "name": child.name,
                    "is_dir": False,
                    "file_type": item_type,
                    "size_bytes": size,
                    "file_count": 1,
                    "dir_count": 0,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(),
                    "extension": child.suffix.lower(),
                    "mime_type": mimetypes.guess_type(child.name)[0] or "application/octet-stream",
                }
            total_size += int(entry.get("size_bytes") or 0)
            entries.append(entry)

        entries.sort(key=lambda item: (not bool(item.get("is_dir")), str(item.get("name") or "").lower()))
        return HTTPStatus.OK, {
            "ok": True,
            "relative_path": rel,
            "entry_count": len(entries),
            "entries": entries[:limit],
            "summary": {
                "top_level_count": len(entries),
                "file_count": total_files,
                "dir_count": total_dirs,
                "total_size_bytes": total_size,
                "type_counts": dict(sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
                "scanned_files": scanned_files,
                "truncated": truncated,
                "limit": limit,
            },
        }

    def ai_album_material_inventory_payload(self, user: dict | None = None, *, limit: int = 40) -> tuple[int, dict]:
        scope = self.ai_album_organizer_scope()
        roots: list[Path] = list(scope.get("root_paths") or [])
        if not roots:
            return HTTPStatus.SERVICE_UNAVAILABLE, {k: v for k, v in scope.items() if k != "root_paths"}
        personal = self.personal_root.resolve(strict=False) if self.personal_root else None
        workspace = personal.parent.resolve(strict=False) if personal else None
        scan_budget = max(1, min(int(self.storage_max_files or 5000), 5000))
        scanned_files = 0
        total_files = 0
        total_dirs = 0
        total_size = 0
        truncated = False
        type_counts: dict[str, int] = {}
        root_entries: list[dict] = []
        sample_entries: list[dict] = []

        def add_type(path: Path) -> str:
            label = product_file_type(path)
            type_counts[label] = int(type_counts.get(label, 0)) + 1
            return label

        for root in roots:
            if scanned_files >= scan_budget:
                truncated = True
                break
            if personal and _path_is_relative_to(root, personal):
                try:
                    root_rel = root.resolve(strict=False).relative_to(personal).as_posix()
                except ValueError:
                    root_rel = ""
                if user and not self.can_read(user, root_rel):
                    continue
            public_rel = self._public_workspace_relative(root, workspace or root.parent)
            root_file_count = 0
            root_dir_count = 0
            root_size = 0
            root_types: dict[str, int] = {}
            for current, dirs, files in os.walk(root):
                dirs[:] = [
                    name
                    for name in dirs
                    if not product_hidden_storage_name(name)
                    and not name.startswith("@")
                    and name.lower() not in AI_ALBUM_PROJECT_ARTIFACT_NAMES
                ]
                if Path(current) != root:
                    root_dir_count += 1
                for filename in files:
                    if scanned_files >= scan_budget:
                        truncated = True
                        break
                    if product_hidden_storage_name(filename):
                        continue
                    path = Path(current) / filename
                    if path.suffix.lower() not in AI_ALBUM_MATERIAL_EXTENSIONS:
                        continue
                    scanned_files += 1
                    root_file_count += 1
                    total_files += 1
                    label = add_type(path)
                    root_types[label] = int(root_types.get(label, 0)) + 1
                    try:
                        size = path.stat().st_size
                    except OSError:
                        size = 0
                    root_size += size
                    total_size += size
                    if len(sample_entries) < limit:
                        try:
                            rel = path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
                        except ValueError:
                            rel = path.name
                        sample_entries.append(
                            {
                                "root": public_rel,
                                "name": path.name,
                                "relative_name": rel,
                                "file_type": label,
                                "size_bytes": size,
                                "mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).astimezone().isoformat() if path.exists() else None,
                            }
                        )
                if truncated:
                    break
            total_dirs += root_dir_count
            root_entries.append(
                {
                    "name": root.name,
                    "relative": public_rel,
                    "file_count": root_file_count,
                    "dir_count": root_dir_count,
                    "size_bytes": root_size,
                    "type_counts": dict(sorted(root_types.items(), key=lambda kv: (-kv[1], kv[0]))),
                }
            )
            if truncated:
                break
        root_entries.sort(key=lambda item: (-int(item.get("file_count") or 0), str(item.get("relative") or "")))
        return HTTPStatus.OK, {
            "ok": True,
            "schema": "digua_ai_album_material_inventory_v1",
            "relative_path": "AI相册整理范围",
            "entry_count": len(root_entries),
            "entries": root_entries[:limit],
            "sample_entries": sample_entries[:limit],
            "summary": {
                "top_level_count": len(root_entries),
                "file_count": total_files,
                "dir_count": total_dirs,
                "total_size_bytes": total_size,
                "type_counts": dict(sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
                "scanned_files": scanned_files,
                "truncated": truncated,
                "limit": limit,
                "scope": "demo_test_personal_material_only",
            },
            "scope": {k: v for k, v in scope.items() if k != "root_paths"},
            "cloud_used": False,
            "qwen_execution_authority": False,
            "raw_path_returned": False,
        }

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
            scope = normalize_storage_relative_path(relative_path or "")
            scope_like = f"{scope}/%" if scope else "%"
            rows = con.execute(
                """
                SELECT c.id AS chunk_id, c.redacted_text, c.source_hash, c.chunk_index,
                       d.title, d.relative_path, d.file_type, bm25(document_chunks_fts) AS rank
                FROM document_chunks_fts
                JOIN document_chunks c ON c.id = document_chunks_fts.chunk_id
                JOIN documents d ON d.id = c.document_id
                WHERE document_chunks_fts MATCH ?
                  AND (? = '' OR d.relative_path = ? OR d.relative_path LIKE ?)
                ORDER BY rank
                LIMIT 24
                """,
                (match_query, scope, scope, scope_like),
            ).fetchall()
            evidence = []
            seen_chunks: set[str] = set()
            for index, row in enumerate(rows, start=1):
                rel = str(row["relative_path"])
                if user and not self.can_read(user, rel):
                    continue
                chunk_key = str(row["chunk_id"] or row["source_hash"] or f"{rel}:{row['chunk_index']}")
                if chunk_key in seen_chunks:
                    continue
                seen_chunks.add(chunk_key)
                snippet = local_snippet(str(row["redacted_text"]), terms, max_chars=220) or str(row["redacted_text"])[:220]
                evidence.append(
                    {
                        "evidence_ref": f"ev_{len(evidence) + 1}_{str(row['source_hash'])[:10]}",
                        "chunk_id": row["chunk_id"],
                        "name": row["title"],
                        "relative_path": rel,
                        "extension": row["file_type"],
                        "open_url": document_storage_open_url(rel, preview=True),
                        "download_url": document_storage_open_url(rel, preview=False),
                        "open_kind": "document",
                        "chunk_index": row["chunk_index"],
                        "source_hash": row["source_hash"],
                        "snippet": snippet,
                        "score": float(row["rank"] or 0),
                    }
                )
                if len(evidence) >= 8:
                    break
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
            con.close()


    def document_classification_payload(self, relative_path: str, user: dict) -> tuple[int, dict]:
        if not self.personal_root:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "personal_root_not_configured"}
        if classify_document_directory is None:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "document_classification_unavailable"}
        try:
            normalized = normalize_storage_relative_path(relative_path or "Documents")
            resolve_storage_path(self.personal_root, normalized)
            result = classify_document_directory(
                self.personal_root,
                normalized,
                can_read=lambda path: self.can_read(user, path),
                max_files=self.storage_max_files,
            )
        except (StoragePathError, OSError) as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid_document_path:{type(exc).__name__}"}
        return (HTTPStatus.OK if result.get("ok") else HTTPStatus.NOT_FOUND), result

    def document_query_payload(self, query: str, relative_path: str = "Documents", user: dict | None = None) -> tuple[int, dict]:
        query = str(query or "").strip()
        if not query:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "query_required"}
        status, payload = self.document_fts_recall(query, normalize_storage_relative_path(relative_path or "Documents"), user)
        if status != HTTPStatus.OK:
            return status, payload
        evidence = payload.get("evidence") or []
        if evidence:
            answer = document_answer_from_evidence(
                str(payload.get("path") or ""),
                evidence,
                [str(item) for item in payload.get("evidence_refs") or []],
            )
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
            "amount_hits": document_amount_hits(evidence),
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
            with target.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError:
            return HTTPStatus.CONFLICT, {"ok": False, "error": "target_already_exists", "path": target_rel}
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

    def storage_upload_stream(
        self,
        filename: str,
        target_dir_value: str,
        content_length: int,
        stream: object,
        user: dict,
    ) -> tuple[int, dict]:
        filename = str(filename or "").strip()
        if not filename or "/" in filename or "\\" in filename or filename in {".", ".."}:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_filename"}
        if content_length < 0:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_content_length"}
        if content_length > MAX_STREAM_UPLOAD_BYTES:
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {
                "ok": False,
                "error": "upload_too_large",
                "max_bytes": MAX_STREAM_UPLOAD_BYTES,
            }
        try:
            target_dir = normalize_storage_relative_path(target_dir_value or "")
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
        if target.exists():
            self.record_operation("upload", None, target_rel, "target_already_exists", str(user.get("username")))
            return HTTPStatus.CONFLICT, {"ok": False, "error": "target_already_exists", "path": target_rel}

        temp_path: Path | None = None
        digest = hashlib.sha256()
        remaining = content_length
        written = 0
        try:
            with tempfile.NamedTemporaryFile(prefix=".digua-upload-", suffix=".part", dir=parent, delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                while remaining:
                    chunk = stream.read(min(STREAM_CHUNK_BYTES, remaining))  # type: ignore[attr-defined]
                    if not chunk:
                        raise EOFError("request_body_truncated")
                    temp_file.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
                    remaining -= len(chunk)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            with self.storage_write_lock:
                try:
                    os.link(temp_path, target)
                except FileExistsError:
                    return HTTPStatus.CONFLICT, {"ok": False, "error": "target_already_exists", "path": target_rel}
            linked_temp_path = temp_path
            temp_path = None
            try:
                linked_temp_path.unlink()
            except OSError as exc:
                sys.stderr.write(f"upload temp cleanup degraded: {type(exc).__name__}: {exc}\n")
        except EOFError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc), "received_bytes": written}
        except OSError as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {
                "ok": False,
                "error": f"upload_write_failed:{type(exc).__name__}:{exc}",
                "path": target_rel,
            }
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
        self.record_operation("upload", None, target_rel, "created", str(user.get("username")))
        return HTTPStatus.OK, {
            "ok": True,
            "file": {
                "relative_path": target_rel,
                "path": target_rel,
                "name": filename,
                "size_bytes": written,
                "sha256": digest.hexdigest(),
            },
        }

    def storage_trash_payload(self, payload: dict | None, user: dict) -> tuple[int, dict]:
        if not self.personal_root or not self.snapshot_store:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "snapshot_store_unavailable", "raw_path_returned": False}
        payload = payload or {}
        rel = ""
        target: Path | None = None
        path_hash_value = str(payload.get("path_hash") or "").strip().lower()
        if path_hash_value:
            target, rel = self.media_file_by_path_hash(path_hash_value, user or {})
            if not target:
                target, rel = self.storage_file_by_path_hash(path_hash_value, user or {})
        if not target:
            try:
                rel = normalize_storage_relative_path(payload.get("relative_path") or payload.get("path") or "")
                if not rel:
                    return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "path_required", "raw_path_returned": False}
                target = resolve_storage_path(self.personal_root, rel)
            except StoragePathError as exc:
                return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc), "raw_path_returned": False}
        resolved_rel = self._relative_path_for_personal_file(target)
        if not resolved_rel:
            self.record_operation("trash", None, rel or None, "outside_personal_root_blocked", str(user.get("username")))
            return HTTPStatus.FORBIDDEN, {
                "ok": False,
                "error": "trash_only_supported_for_personal_files",
                "raw_path_returned": False,
            }
        if resolved_rel.startswith(".trash/") or resolved_rel in {".trash", ".snapshots", ".versions"} or resolved_rel.startswith(".snapshots/") or resolved_rel.startswith(".versions/"):
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "recovery_area_delete_blocked", "raw_path_returned": False}
        if not target.exists() or not target.is_file():
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "file_not_found", "raw_path_returned": False}
        if not self.can_read(user, resolved_rel) or not self.can_write(user, resolved_rel):
            self.record_operation("trash", resolved_rel, None, "permission_denied", str(user.get("username")))
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "write", "raw_path_returned": False}
        result = self.snapshot_store.trash_file(target, str(user.get("username") or ""))
        if not result.get("ok"):
            self.record_operation("trash", resolved_rel, None, str(result.get("error") or "failed"), str(user.get("username")))
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": result.get("error") or "trash_failed", "raw_path_returned": False}
        media_remove: dict = {"ok": True, "removed": 0}
        if self.media_center:
            try:
                media_remove = self.media_center.remove_photo_path(target)
            except Exception as exc:
                media_remove = {"ok": False, "error": f"{type(exc).__name__}:{exc}", "raw_path_returned": False}
        self.record_operation("trash", resolved_rel, str(result.get("trash_id") or ""), "moved_to_trash", str(user.get("username")))
        return HTTPStatus.OK, {
            "ok": True,
            "schema": "digua_storage_trash_v1",
            "retention_days": 30,
            "result": {
                "trash_id": result.get("trash_id"),
                "original_path": result.get("original_path"),
                "size_bytes": result.get("size_bytes"),
                "expires_at": result.get("expires_at"),
            },
            "media_index": media_remove,
            "physical_file_deleted": False,
            "moved_to_trash": True,
            "raw_path_returned": False,
        }

    def storage_trash_cleanup_payload(self, payload: dict | None, user: dict) -> tuple[int, dict]:
        if not self.snapshot_store:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "snapshot_store_unavailable", "raw_path_returned": False}
        result = self.snapshot_store.cleanup_expired_trash(30)
        self.record_operation("trash_cleanup", None, None, "completed", str(user.get("username")))
        return HTTPStatus.OK, {"ok": bool(result.get("ok")), "schema": "digua_storage_trash_cleanup_v1", "result": result, "raw_path_returned": False}

    def media_status_payload(self, *, ensure_index: bool = False, max_files: int = 5000) -> dict:
        if not self.media_center:
            return {"ok": False, "error": "media_center_unavailable", "raw_path_returned": False}
        if ensure_index and self.personal_root and int((self.media_center.stats() or {}).get("photo_count") or 0) == 0:
            self.media_center.index_photos(self.personal_root, asset_root=self.personal_root, max_files=max_files, source_id="personal_autoscan")
        status = self.media_center.status()
        status.update(
            {
                "schema": "digua_media_album_v2",
                "raw_path_returned": False,
                "physical_file_renamed": False,
                "physical_file_moved": False,
                "destructive_actions_enabled": False,
            }
        )
        return status

    def ai_album_organizer_scope(self) -> dict:
        if not self.personal_root:
            return {"ok": False, "error": "personal_root_not_configured", "root_paths": [], "raw_path_returned": False}
        personal = self.personal_root.resolve(strict=False)
        workspace = personal.parent.resolve(strict=False)
        candidates: list[tuple[str, Path]] = []
        for rel in AI_ALBUM_PERSONAL_MATERIAL_DIRS:
            candidates.append(("personal_material", personal / rel))
        for rel in AI_ALBUM_NAS_MATERIAL_DIRS:
            candidates.append(("nas_demo_material", workspace / rel))
        for rel in AI_ALBUM_DEMO_CORPUS_MATERIAL_DIRS:
            candidates.append(("demo_corpus_material", workspace / "demo_corpus" / rel))

        roots: list[Path] = []
        included_roots: list[dict] = []
        skipped_roots: list[dict] = []
        seen: set[str] = set()
        for scope, candidate in candidates:
            resolved = candidate.resolve(strict=False)
            public_rel = self._public_workspace_relative(resolved, workspace)
            if not resolved.exists() or not resolved.is_dir():
                skipped_roots.append({"scope": scope, "relative": public_rel, "reason": "missing"})
                continue
            if self._is_project_artifact_material_path(resolved, workspace, personal):
                skipped_roots.append({"scope": scope, "relative": public_rel, "reason": "project_artifact_excluded"})
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            roots.append(resolved)
            included_roots.append({"scope": scope, "relative": public_rel, "name": resolved.name})
        return {
            "ok": bool(roots),
            "schema": "digua_ai_album_organizer_scope_v1",
            "root_paths": roots,
            "included_roots": included_roots,
            "included_root_count": len(included_roots),
            "skipped_roots": skipped_roots,
            "excluded_policy": {
                "project_artifact_names": sorted(AI_ALBUM_PROJECT_ARTIFACT_NAMES),
                "personal_project_prefix_filter": "product_hidden_storage_name",
                "scope": "demo_test_personal_material_only",
            },
            "raw_path_returned": False,
        }

    def ai_album_rebuild_payload(self, payload: dict, user: dict) -> tuple[int, dict]:
        if not self.personal_root:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "personal_root_not_configured", "raw_path_returned": False}
        scope = self.ai_album_organizer_scope()
        roots: list[Path] = list(scope.get("root_paths") or [])
        if not roots:
            return HTTPStatus.BAD_REQUEST, {k: v for k, v in scope.items() if k != "root_paths"}

        max_files = int(payload.get("max_files") or 5000)
        media_max_files = int(payload.get("media_max_files") or max_files)
        run_yolo = bool(payload.get("run_yolo", False))
        yolo_max_files = int(payload.get("yolo_max_files") or min(max_files, 16))
        include_video = bool(payload.get("include_video", True))
        root_strings = [str(root) for root in roots]
        pipeline: dict[str, dict] = {}

        def run_stage(name: str, fn, *, required: bool = False) -> None:
            try:
                result = fn()
                pipeline[name] = self._redact_paths(result if isinstance(result, dict) else {"ok": bool(result)})
            except Exception as exc:
                pipeline[name] = {"ok": False, "error": f"{type(exc).__name__}:{exc}", "required": required}

        if self.media_center:
            media_results = []
            for root in roots:
                media_results.append(self.media_center.index_photos(root, asset_root=root, max_files=media_max_files, source_id="ai_album_organizer_scope"))
            pipeline["media_index"] = {
                "ok": True,
                "root_count": len(media_results),
                "indexed": sum(int(item.get("indexed") or 0) for item in media_results),
                "scanned": sum(int(item.get("scanned") or 0) for item in media_results),
                "skipped": sum(int(item.get("skipped") or 0) for item in media_results),
                "raw_path_returned": False,
            }
        else:
            pipeline["media_index"] = {"ok": False, "error": "media_center_unavailable", "required": False, "raw_path_returned": False}

        if multimodal_route_response is not None:
            run_stage(
                "multimodal_rebuild",
                lambda: multimodal_route_response(
                    "/api/multimodal-index/rebuild",
                    method="POST",
                    payload={"roots": root_strings, "max_files": max_files, "user_id": str(user.get("username") or "operator")},
                    report_root=self.report_root,
                    personal_root=self.personal_root,
                )[1],
                required=True,
            )
        else:
            pipeline["multimodal_rebuild"] = {"ok": False, "error": "multimodal_search_unavailable", "required": True}

        if yolo_route_response is not None and run_yolo:
            run_stage(
                "yolo_index",
                lambda: yolo_route_response(
                    "/api/yolo-index/rebuild",
                    method="POST",
                    payload={"roots": root_strings, "max_files": yolo_max_files, "include_video": include_video, "user_id": str(user.get("username") or "operator")},
                    report_root=self.report_root,
                    personal_root=self.personal_root,
                )[1],
            )
        elif not run_yolo:
            pipeline["yolo_index"] = {
                "ok": True,
                "skipped": True,
                "reason": "lightweight_rebuild_preserves_existing_yolo_index",
                "run_yolo": False,
                "raw_path_returned": False,
            }
        else:
            pipeline["yolo_index"] = {"ok": False, "error": "yolo_index_unavailable", "required": False}

        if person_attribute_route_response is not None and run_yolo:
            run_stage(
                "person_attribute_rebuild",
                lambda: person_attribute_route_response(
                    "/api/person-attribute/rebuild",
                    method="POST",
                    payload={"roots": root_strings, "max_files": yolo_max_files, "user_id": str(user.get("username") or "operator")},
                    report_root=self.report_root,
                    personal_root=self.personal_root,
                )[1],
            )
        elif not run_yolo:
            pipeline["person_attribute_rebuild"] = {
                "ok": True,
                "skipped": True,
                "reason": "lightweight_rebuild_preserves_existing_person_attribute_index",
                "run_yolo": False,
                "raw_path_returned": False,
            }
        else:
            pipeline["person_attribute_rebuild"] = {"ok": False, "error": "person_attribute_unavailable", "required": False}

        if smart_classification_route_response is not None:
            run_stage(
                "smart_classification_rebuild",
                lambda: smart_classification_route_response(
                    "/api/smart-classification/rebuild",
                    method="POST",
                    payload={"user_id": str(user.get("username") or "operator")},
                    report_root=self.report_root,
                    personal_root=self.personal_root,
                )[1],
                required=True,
            )
        else:
            pipeline["smart_classification_rebuild"] = {"ok": False, "error": "smart_classification_unavailable", "required": True}

        if ai_space_route_response is not None:
            run_stage(
                "ai_space_rebuild",
                lambda: ai_space_route_response(
                    "/api/ai-space/rebuild",
                    method="POST",
                    payload={"user_id": str(user.get("username") or "operator")},
                    report_root=self.report_root,
                    personal_root=self.personal_root,
                )[1],
                required=True,
            )
        else:
            pipeline["ai_space_rebuild"] = {"ok": False, "error": "ai_space_unavailable", "required": True}

        required_failed = [
            name
            for name, result in pipeline.items()
            if bool(result.get("required")) and result.get("ok") is False
        ]
        response_scope = {k: v for k, v in scope.items() if k != "root_paths"}
        response = {
            "ok": not required_failed,
            "schema": "digua_ai_album_rebuild_v1",
            "scope": response_scope,
            "pipeline": pipeline,
            "required_failed": required_failed,
            "cloud_used": False,
            "raw_path_returned": False,
        }
        return (HTTPStatus.OK if response["ok"] else HTTPStatus.BAD_REQUEST), response

    def ai_album_auto_organize_payload(self, payload: dict | None, user: dict) -> tuple[int, dict]:
        if not self.personal_root or not self.media_center:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "media_center_unavailable", "raw_path_returned": False}
        payload = payload or {}
        scope = self.ai_album_organizer_scope()
        roots: list[Path] = list(scope.get("root_paths") or [])
        if not roots:
            return HTTPStatus.BAD_REQUEST, {k: v for k, v in scope.items() if k != "root_paths"}
        max_files = max(1, min(int(payload.get("max_files") or AI_ALBUM_AUTO_MAX_FILES), AI_ALBUM_AUTO_MAX_FILES))
        force = bool(payload.get("force"))
        media_results: list[dict] = []
        for root in roots:
            media_results.append(
                self.media_center.index_photos(
                    root,
                    asset_root=root,
                    max_files=max_files,
                    source_id="ai_album_auto_incremental",
                )
            )
        media_index = {
            "ok": True,
            "root_count": len(media_results),
            "scanned": sum(int(item.get("scanned") or 0) for item in media_results),
            "indexed": sum(int(item.get("indexed") or 0) for item in media_results),
            "skipped": sum(int(item.get("skipped") or 0) for item in media_results),
            "unsupported": sum(int(item.get("unsupported") or 0) for item in media_results),
            "truncated": any(bool(item.get("truncated")) for item in media_results),
            "raw_path_returned": False,
        }
        sync_result = self._sync_ai_album_media_rows_to_multimodal_assets(roots, max_files=max_files)
        mm_counts = self._count_ai_album_multimodal_assets()
        ai_counts = self._count_ai_album_ai_space_assets()
        changed = bool(force or int(media_index.get("indexed") or 0) or int(sync_result.get("upserted") or 0) or int(sync_result.get("deleted") or 0))
        stale_view = int(ai_counts.get("image") or 0) < int(mm_counts.get("image") or 0)
        should_rebuild_view = bool(changed or stale_view or force)
        pipeline: dict[str, dict] = {
            "media_index": media_index,
            "multimodal_asset_sync": sync_result,
        }
        if should_rebuild_view:
            if smart_classification_route_response is not None:
                try:
                    _code, result = smart_classification_route_response(
                        "/api/smart-classification/rebuild",
                        method="POST",
                        payload={"user_id": str(user.get("username") or "operator"), "source": "ai_album_auto_incremental"},
                        report_root=self.report_root,
                        personal_root=self.personal_root,
                    )
                    pipeline["smart_classification_rebuild"] = self._redact_paths(result)
                except Exception as exc:
                    pipeline["smart_classification_rebuild"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}", "required": True}
            elif ai_space_route_response is not None:
                try:
                    _code, result = ai_space_route_response(
                        "/api/ai-space/rebuild",
                        method="POST",
                        payload={"user_id": str(user.get("username") or "operator"), "source": "ai_album_auto_incremental"},
                        report_root=self.report_root,
                        personal_root=self.personal_root,
                    )
                    pipeline["ai_space_rebuild"] = self._redact_paths(result)
                except Exception as exc:
                    pipeline["ai_space_rebuild"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}", "required": True}
            else:
                pipeline["ai_space_rebuild"] = {"ok": False, "error": "ai_space_unavailable", "required": True}
        else:
            pipeline["ai_space_rebuild"] = {
                "ok": True,
                "skipped": True,
                "reason": "no_new_or_changed_ai_album_media",
                "raw_path_returned": False,
            }
            pipeline["smart_classification_rebuild"] = {
                "ok": True,
                "skipped": True,
                "reason": "no_new_or_changed_ai_album_media",
                "raw_path_returned": False,
            }
        after_ai_counts = self._count_ai_album_ai_space_assets()
        required_failed = [
            name
            for name, result in pipeline.items()
            if bool(result.get("required")) and result.get("ok") is False
        ]
        response_scope = {k: v for k, v in scope.items() if k != "root_paths"}
        return (HTTPStatus.OK if not required_failed else HTTPStatus.BAD_REQUEST), {
            "ok": not required_failed,
            "schema": "digua_ai_album_auto_incremental_v1",
            "scope": response_scope,
            "changed": changed,
            "view_rebuilt": should_rebuild_view,
            "stale_view_detected": stale_view,
            "counts": {
                "media_images_indexed": sync_result.get("candidate_images"),
                "multimodal_images": mm_counts.get("image", 0),
                "ai_space_images_before": ai_counts.get("image", 0),
                "ai_space_images_after": after_ai_counts.get("image", 0),
            },
            "pipeline": pipeline,
            "required_failed": required_failed,
            "physical_file_moved": False,
            "physical_file_renamed": False,
            "destructive_actions_enabled": False,
            "cloud_used": False,
            "raw_path_returned": False,
        }

    def ai_album_organize_status_payload(self, payload: dict | None = None) -> tuple[int, dict]:
        if not self.personal_root or not self.media_center:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "media_center_unavailable", "raw_path_returned": False}
        payload = payload or {}
        scope = self.ai_album_organizer_scope()
        roots: list[Path] = list(scope.get("root_paths") or [])
        if not roots:
            return HTTPStatus.BAD_REQUEST, {k: v for k, v in scope.items() if k != "root_paths"}
        max_files = max(1, min(int(payload.get("max_files") or AI_ALBUM_AUTO_MAX_FILES), AI_ALBUM_AUTO_MAX_FILES))
        rows = self._ai_album_current_image_rows(roots, max_files=max_files)
        self._ensure_ai_album_primary_categories()
        memberships = self._ai_album_primary_memberships([str(row.get("asset_id") or "") for row in rows])
        category_meta = {str(item["id"]): item for item in AI_ALBUM_PRIMARY_CATEGORIES}
        category_counts: dict[str, int] = {str(item["id"]): 0 for item in AI_ALBUM_PRIMARY_CATEGORIES}
        photo_status: list[dict] = []
        organized = 0
        pending = 0
        multi_primary = 0
        for row in rows:
            asset_id = str(row.get("asset_id") or "")
            primary = memberships.get(asset_id) or []
            selected = self._select_primary_membership(primary)
            if selected:
                category_id = str(selected.get("category_id") or "")
                category = category_meta.get(category_id) or {}
                organized += 1
                category_counts[category_id] = int(category_counts.get(category_id) or 0) + 1
                if len(primary) > 1:
                    multi_primary += 1
                photo_status.append(
                    {
                        "asset_id": asset_id,
                        "path_hash": row.get("path_hash"),
                        "state": "organized",
                        "category_id": category_id,
                        "category_name": category.get("name") or selected.get("category_name"),
                    }
                )
            else:
                pending += 1
                photo_status.append(
                    {
                        "asset_id": asset_id,
                        "path_hash": row.get("path_hash"),
                        "state": "pending",
                        "category_id": None,
                        "category_name": None,
                    }
                )
        categories = [
            {
                "id": str(item["id"]),
                "name": str(item["name"]),
                "name_en": str(item["name_en"]),
                "description": str(item["description"]),
                "count": int(category_counts.get(str(item["id"])) or 0),
            }
            for item in AI_ALBUM_PRIMARY_CATEGORIES
        ]
        response_scope = {k: v for k, v in scope.items() if k != "root_paths"}
        return HTTPStatus.OK, {
            "ok": True,
            "schema": "digua_ai_album_primary_organize_status_v1",
            "scope": response_scope,
            "total_images": len(rows),
            "organized_count": organized,
            "pending_count": pending,
            "all_organized": pending == 0,
            "multi_primary_count": multi_primary,
            "categories": categories,
            "photo_status": photo_status,
            "policy": {
                "exclusive_primary_category": True,
                "physical_file_moved": False,
                "physical_file_renamed": False,
                "cloud_used": False,
                "raw_path_returned": False,
                "category_set": "people, animals, landscape, city, transport, food, documents, other",
            },
            "raw_path_returned": False,
        }

    def ai_album_organize_pending_payload(self, payload: dict | None, user: dict) -> tuple[int, dict]:
        if not self.personal_root or not self.media_center:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "media_center_unavailable", "raw_path_returned": False}
        payload = payload or {}
        max_files = max(1, min(int(payload.get("max_files") or AI_ALBUM_AUTO_MAX_FILES), AI_ALBUM_AUTO_MAX_FILES))
        auto_status, auto_payload = self.ai_album_auto_organize_payload({"max_files": max_files, "force": bool(payload.get("force_index"))}, user)
        if auto_status >= 400 or auto_payload.get("ok") is False:
            return auto_status, {
                "ok": False,
                "schema": "digua_ai_album_primary_organize_v1",
                "error": "auto_incremental_index_failed",
                "auto_organize": auto_payload,
                "raw_path_returned": False,
            }
        scope = self.ai_album_organizer_scope()
        roots: list[Path] = list(scope.get("root_paths") or [])
        if not roots:
            return HTTPStatus.BAD_REQUEST, {k: v for k, v in scope.items() if k != "root_paths"}
        rows = self._ai_album_current_image_rows(roots, max_files=max_files)
        self._ensure_ai_album_primary_categories()
        assets = self._ai_album_ai_space_assets_by_id()
        memberships = self._ai_album_primary_memberships([str(row.get("asset_id") or "") for row in rows])
        smart_db_path = self._ai_album_smart_db_path()
        method_counts: dict[str, int] = {
            "skipped_existing": 0,
            "evidence_rules": 0,
            "clip_similarity": 0,
            "fallback_other": 0,
            "reclassified_force": 0,
        }
        processed = 0
        cleaned_non_primary = 0
        collapsed_multi_primary = 0
        errors: list[str] = []
        force = bool(payload.get("force"))
        conn = sqlite3.connect(str(smart_db_path))
        conn.row_factory = sqlite3.Row
        try:
            for row in rows:
                asset_id = str(row.get("asset_id") or "")
                if not asset_id:
                    continue
                primary = memberships.get(asset_id) or []
                selected = self._select_primary_membership(primary)
                if selected and not force:
                    cleaned_non_primary += self._delete_non_primary_memberships(conn, asset_id, keep_primary_id=str(selected.get("category_id") or ""))
                    if len(primary) > 1:
                        collapsed_multi_primary += self._collapse_primary_memberships(conn, asset_id, keep_primary_id=str(selected.get("category_id") or ""))
                    method_counts["skipped_existing"] += 1
                    continue
                if selected and force:
                    method_counts["reclassified_force"] += 1
                asset = assets.get(asset_id) or {}
                try:
                    assignment = self._classify_ai_album_image(row, asset)
                except Exception as exc:
                    errors.append(f"{asset_id[:16]}:{type(exc).__name__}:{exc}")
                    assignment = self._fallback_ai_album_assignment(asset_id, reason=f"{type(exc).__name__}")
                self._delete_all_memberships_for_asset(conn, asset_id)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO smart_category_memberships(category_id,asset_id,score,matched_by_json,evidence_refs_json,created_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (
                        assignment["category_id"],
                        asset_id,
                        float(assignment.get("score") or 0.0),
                        json.dumps(assignment.get("matched_by") or [], ensure_ascii=False, sort_keys=True),
                        json.dumps(assignment.get("evidence_refs") or [f"asset:{asset_id[:16]}"], ensure_ascii=False, sort_keys=True),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                method_counts[str(assignment.get("method") or "fallback_other")] = int(method_counts.get(str(assignment.get("method") or "fallback_other")) or 0) + 1
                processed += 1
            conn.commit()
        finally:
            conn.close()
        ai_space_rebuild: dict = {"ok": False, "error": "ai_space_unavailable"}
        if ai_space_route_response is not None:
            try:
                _code, ai_space_rebuild = ai_space_route_response(
                    "/api/ai-space/rebuild",
                    method="POST",
                    payload={"user_id": str(user.get("username") or "operator"), "source": "ai_album_primary_organize"},
                    report_root=self.report_root,
                    personal_root=self.personal_root,
                )
            except Exception as exc:
                ai_space_rebuild = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
        _status, organize_status = self.ai_album_organize_status_payload({"max_files": max_files})
        response_scope = {k: v for k, v in scope.items() if k != "root_paths"}
        return HTTPStatus.OK, {
            "ok": True,
            "schema": "digua_ai_album_primary_organize_v1",
            "scope": response_scope,
            "processed_count": processed,
            "skipped_existing_count": method_counts.get("skipped_existing", 0),
            "cleaned_non_primary_memberships": cleaned_non_primary,
            "collapsed_multi_primary_memberships": collapsed_multi_primary,
            "method_counts": method_counts,
            "auto_organize": auto_payload,
            "ai_space_rebuild": self._redact_paths(ai_space_rebuild),
            "status": organize_status,
            "errors": errors[:10],
            "physical_file_moved": False,
            "physical_file_renamed": False,
            "destructive_actions_enabled": False,
            "cloud_used": False,
            "raw_path_returned": False,
        }

    def _ai_album_current_image_rows(self, roots: list[Path], *, max_files: int) -> list[dict]:
        if not self.media_center:
            return []
        allowed_roots = [Path(root).resolve(strict=False) for root in roots]
        rows: list[dict] = []
        seen: set[str] = set()
        for row in self.media_center.indexed_rows(limit=max_files, modality="image"):
            asset_id = str(row.get("asset_id") or "")
            if not asset_id or asset_id in seen:
                continue
            path_text = str(row.get("file_path") or "")
            if not path_text:
                continue
            path = Path(path_text)
            if path.suffix.lower() not in AI_ALBUM_IMAGE_EXTENSIONS:
                continue
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue
            if not any(_path_is_relative_to(resolved, root) for root in allowed_roots):
                continue
            seen.add(asset_id)
            rows.append(dict(row))
        return rows

    def _ai_album_smart_db_path(self) -> Path:
        return self.report_root / "smart_classification" / "runtime" / "smart_classification.db"

    def _ensure_ai_album_primary_categories(self) -> None:
        db_path = self._ai_album_smart_db_path()
        try:
            from src.smart_classification.schema import migrate as migrate_smart_db

            migrate_smart_db(db_path)
        except Exception:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        if smart_classification_route_response is not None:
            try:
                smart_classification_route_response(
                    "/api/smart-classification/categories",
                    method="GET",
                    report_root=self.report_root,
                    personal_root=self.personal_root,
                )
            except Exception as exc:
                sys.stderr.write(f"smart classification category bootstrap degraded: {type(exc).__name__}: {exc}\n")
        conn = sqlite3.connect(str(db_path))
        try:
            now = datetime.now(timezone.utc).isoformat()
            for item in AI_ALBUM_PRIMARY_CATEGORIES:
                rule = {
                    "album_primary": True,
                    "exclusive_group": "ai_album_primary_v1",
                    "preserve_memberships_on_rebuild": True,
                    "manual_assignment_only": True,
                    "clip_prompt": item["clip_prompt"],
                }
                conn.execute(
                    """
                    INSERT OR REPLACE INTO smart_categories(category_id,name,name_zh,name_en,icon,description,rule_json,created_by,created_at,updated_at,enabled)
                    VALUES(?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM smart_categories WHERE category_id=?),?),?,1)
                    """,
                    (
                        item["id"],
                        item["name"],
                        item["name"],
                        item["name_en"],
                        item["icon"],
                        item["description"],
                        json.dumps(rule, ensure_ascii=False, sort_keys=True),
                        "album_primary",
                        item["id"],
                        now,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _ai_album_primary_memberships(self, asset_ids: list[str]) -> dict[str, list[dict]]:
        ids = [asset_id for asset_id in asset_ids if asset_id]
        if not ids:
            return {}
        self._ensure_ai_album_primary_categories()
        placeholders = ",".join("?" for _ in ids)
        category_placeholders = ",".join("?" for _ in AI_ALBUM_PRIMARY_CATEGORY_IDS)
        params = [*ids, *sorted(AI_ALBUM_PRIMARY_CATEGORY_IDS)]
        conn = sqlite3.connect(str(self._ai_album_smart_db_path()))
        conn.row_factory = sqlite3.Row
        try:
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT m.*, c.name AS category_name
                    FROM smart_category_memberships m
                    JOIN smart_categories c ON c.category_id=m.category_id
                    WHERE m.asset_id IN ({placeholders})
                      AND m.category_id IN ({category_placeholders})
                    """,
                    tuple(params),
                )
            ]
        finally:
            conn.close()
        out: dict[str, list[dict]] = {}
        for row in rows:
            out.setdefault(str(row.get("asset_id") or ""), []).append(row)
        return out

    @staticmethod
    def _select_primary_membership(rows: list[dict]) -> dict | None:
        if not rows:
            return None
        return sorted(rows, key=lambda row: (float(row.get("score") or 0.0), str(row.get("created_at") or "")), reverse=True)[0]

    def _delete_non_primary_memberships(self, conn: sqlite3.Connection, asset_id: str, *, keep_primary_id: str) -> int:
        before = int(conn.execute("SELECT count(*) FROM smart_category_memberships WHERE asset_id=?", (asset_id,)).fetchone()[0])
        primary_ids = sorted(AI_ALBUM_PRIMARY_CATEGORY_IDS)
        placeholders = ",".join("?" for _ in primary_ids)
        conn.execute(
            f"DELETE FROM smart_category_memberships WHERE asset_id=? AND category_id NOT IN ({placeholders})",
            (asset_id, *primary_ids),
        )
        self._collapse_primary_memberships(conn, asset_id, keep_primary_id=keep_primary_id)
        after = int(conn.execute("SELECT count(*) FROM smart_category_memberships WHERE asset_id=?", (asset_id,)).fetchone()[0])
        return max(0, before - after)

    def _collapse_primary_memberships(self, conn: sqlite3.Connection, asset_id: str, *, keep_primary_id: str) -> int:
        before = int(
            conn.execute(
                f"SELECT count(*) FROM smart_category_memberships WHERE asset_id=? AND category_id IN ({','.join('?' for _ in AI_ALBUM_PRIMARY_CATEGORY_IDS)})",
                (asset_id, *sorted(AI_ALBUM_PRIMARY_CATEGORY_IDS)),
            ).fetchone()[0]
        )
        conn.execute(
            f"DELETE FROM smart_category_memberships WHERE asset_id=? AND category_id IN ({','.join('?' for _ in AI_ALBUM_PRIMARY_CATEGORY_IDS)}) AND category_id<>?",
            (asset_id, *sorted(AI_ALBUM_PRIMARY_CATEGORY_IDS), keep_primary_id),
        )
        after = int(
            conn.execute(
                f"SELECT count(*) FROM smart_category_memberships WHERE asset_id=? AND category_id IN ({','.join('?' for _ in AI_ALBUM_PRIMARY_CATEGORY_IDS)})",
                (asset_id, *sorted(AI_ALBUM_PRIMARY_CATEGORY_IDS)),
            ).fetchone()[0]
        )
        return max(0, before - after)

    @staticmethod
    def _delete_all_memberships_for_asset(conn: sqlite3.Connection, asset_id: str) -> None:
        conn.execute("DELETE FROM smart_category_memberships WHERE asset_id=?", (asset_id,))

    def _ai_album_ai_space_assets_by_id(self) -> dict[str, dict]:
        if ai_space_route_response is None:
            return {}
        try:
            _code, payload = ai_space_route_response(
                "/api/ai-space/assets",
                method="GET",
                payload={"limit": 10000},
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        except Exception:
            return {}
        assets = payload.get("assets") if isinstance(payload, dict) else None
        if not isinstance(assets, list):
            return {}
        return {str(asset.get("asset_id") or ""): asset for asset in assets if isinstance(asset, dict) and asset.get("asset_id")}

    def _classify_ai_album_image(self, row: dict, asset: dict) -> dict:
        evidence_assignment = self._classify_ai_album_by_evidence(row, asset)
        if evidence_assignment:
            return evidence_assignment
        clip_assignment = self._classify_ai_album_by_clip(row, asset)
        if clip_assignment:
            return clip_assignment
        return self._fallback_ai_album_assignment(str(row.get("asset_id") or ""), reason="no_local_visual_semantic_evidence")

    def _classify_ai_album_by_evidence(self, row: dict, asset: dict) -> dict | None:
        labels = {str(item or "").strip().lower() for item in asset.get("object_labels") or [] if str(item or "").strip()}
        person_attrs = {str(item or "").strip().lower() for item in asset.get("person_attrs") or [] if str(item or "").strip()}
        text = " ".join(
            [
                str(row.get("title_redacted") or ""),
                str(row.get("name") or ""),
                str(row.get("extension") or ""),
                str(asset.get("title_redacted") or ""),
                str(asset.get("summary_redacted") or ""),
                " ".join(str(item or "") for item in asset.get("category_names") or []),
                " ".join(labels),
                " ".join(person_attrs),
            ]
        ).lower()
        best: dict | None = None
        for item in AI_ALBUM_PRIMARY_CATEGORIES:
            if item["id"] == "cat_album_primary_other":
                continue
            matched: list[str] = []
            score = 0.0
            object_hits = labels.intersection(str(term).lower() for term in item.get("object_terms") or [])
            if object_hits:
                matched.append("object_labels")
                score += 0.7
            person_hits = person_attrs.intersection(str(term).lower() for term in item.get("person_terms") or [])
            if person_hits:
                matched.append("person_attrs")
                score += 0.85
            title_terms = [str(term).lower() for term in item.get("title_terms") or []]
            if any(term and term in text for term in title_terms):
                matched.append("title_or_summary_terms")
                score += 0.35
            if not matched:
                continue
            candidate = {
                "category_id": item["id"],
                "score": min(score, 1.0),
                "matched_by": matched,
                "evidence_refs": asset.get("evidence_refs") or [f"asset:{str(row.get('asset_id') or '')[:16]}"],
                "method": "evidence_rules",
            }
            if not best or float(candidate["score"]) > float(best["score"]):
                best = candidate
        return best

    def _classify_ai_album_by_clip(self, row: dict, asset: dict) -> dict | None:
        if product_embedding_runtime_status is None or request_product_embedding is None:
            return None
        try:
            runtime = product_embedding_runtime_status()
        except Exception:
            return None
        if not runtime.get("configured"):
            return None
        text_vectors = self._ai_album_clip_text_vectors(runtime)
        if not text_vectors:
            return None
        path_text = str(row.get("file_path") or "")
        if not path_text:
            return None
        path = Path(path_text)
        try:
            normalized = request_product_embedding(input_type="image", path=path, relative_path=str(row.get("title_redacted") or row.get("path_hash") or "album-image"))
        except Exception:
            return None
        image_vector = normalized.get("vector") or []
        if not image_vector:
            return None
        best_id = ""
        best_score = -1.0
        for category_id, text_vector in text_vectors.items():
            score = _cosine_similarity(image_vector, text_vector)
            if score > best_score:
                best_id = category_id
                best_score = score
        if not best_id:
            return None
        return {
            "category_id": best_id,
            "score": max(0.0, min(1.0, best_score)),
            "matched_by": ["clip_similarity", f"score:{best_score:.4f}", f"model:{normalized.get('model_id') or runtime.get('model_id') or 'local_clip'}"],
            "evidence_refs": asset.get("evidence_refs") or [f"asset:{str(row.get('asset_id') or '')[:16]}"],
            "method": "clip_similarity",
        }

    def _ai_album_clip_text_vectors(self, runtime: dict) -> dict[str, list[float]]:
        if request_product_embedding is None:
            return {}
        endpoint_key = "|".join(
            [
                str(os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT") or os.environ.get("AI_NAS_CLIP_ENDPOINT") or ""),
                str(runtime.get("model_id") or ""),
                "ai_album_primary_v1",
            ]
        )
        cached = self.ai_album_clip_text_cache.get(endpoint_key)
        if cached and isinstance(cached.get("vectors"), dict):
            return cached["vectors"]
        vectors: dict[str, list[float]] = {}
        for item in AI_ALBUM_PRIMARY_CATEGORIES:
            try:
                normalized = request_product_embedding(input_type="text", text=str(item["clip_prompt"]), relative_path="")
            except Exception:
                return {}
            vector = normalized.get("vector") or []
            if not vector:
                return {}
            vectors[str(item["id"])] = vector
        self.ai_album_clip_text_cache = {endpoint_key: {"vectors": vectors, "created_at": datetime.now(timezone.utc).isoformat()}}
        return vectors

    @staticmethod
    def _fallback_ai_album_assignment(asset_id: str, *, reason: str) -> dict:
        return {
            "category_id": "cat_album_primary_other",
            "score": 0.15,
            "matched_by": [f"fallback_other:{reason}"],
            "evidence_refs": [f"asset:{str(asset_id or '')[:16]}"],
            "method": "fallback_other",
        }

    def _sync_ai_album_media_rows_to_multimodal_assets(self, roots: list[Path], *, max_files: int) -> dict:
        if not self.media_center:
            return {"ok": False, "error": "media_center_unavailable", "raw_path_returned": False}
        if connect_multimodal_db is None or migrate_multimodal_db is None:
            return {"ok": False, "error": "multimodal_schema_unavailable", "raw_path_returned": False}
        allowed_roots = [Path(root).resolve(strict=False) for root in roots]
        db_path = self.report_root / "multimodal_search" / "runtime" / "multimodal_search.db"
        migrate_multimodal_db(db_path)
        rows = self.media_center.indexed_rows(limit=max_files, modality="image")
        now = datetime.now(timezone.utc).isoformat()
        candidate_images = 0
        upserted = 0
        unchanged = 0
        skipped = 0
        conn = connect_multimodal_db(db_path)
        try:
            for row in rows:
                path_text = str(row.get("file_path") or "")
                if not path_text:
                    skipped += 1
                    continue
                path = Path(path_text)
                if path.suffix.lower() not in AI_ALBUM_IMAGE_EXTENSIONS:
                    skipped += 1
                    continue
                try:
                    resolved = path.resolve(strict=True)
                except OSError:
                    skipped += 1
                    continue
                if not any(_path_is_relative_to(resolved, root) for root in allowed_roots):
                    skipped += 1
                    continue
                candidate_images += 1
                asset_id = str(row.get("asset_id") or "")
                path_hash = str(row.get("path_hash") or "")
                if not asset_id or not path_hash:
                    skipped += 1
                    continue
                size_bytes = int(row.get("size_bytes") or 0)
                mtime = int(float(row.get("mtime") or 0))
                sha256 = str(row.get("sha256") or "")
                existing = conn.execute(
                    "SELECT sha256,mtime,size_bytes,index_status FROM mm_assets WHERE asset_id=?",
                    (asset_id,),
                ).fetchone()
                if existing and str(existing["sha256"] or "") == sha256 and int(existing["mtime"] or 0) == mtime and int(existing["size_bytes"] or 0) == size_bytes:
                    unchanged += 1
                    continue
                parent_hash = hashlib.sha256(str(resolved.parent).encode("utf-8", errors="replace")).hexdigest()[:32]
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mm_assets(
                      asset_id,source_id,modality,file_type,title_redacted,path_hash,parent_hash,size_bytes,mtime,sha256,
                      privacy_level,index_status,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        asset_id,
                        "ai_album_auto_incremental",
                        "image",
                        path.suffix.lower().lstrip(".") or "image",
                        row.get("title_redacted") or row.get("name") or "image",
                        path_hash,
                        parent_hash,
                        size_bytes,
                        mtime,
                        sha256,
                        "private_local_only",
                        "indexed_media_only",
                        now,
                        now,
                    ),
                )
                upserted += 1
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "candidate_images": candidate_images,
            "upserted": upserted,
            "unchanged": unchanged,
            "skipped": skipped,
            "db": "multimodal_search/runtime/multimodal_search.db",
            "raw_path_returned": False,
        }

    def _count_ai_album_multimodal_assets(self) -> dict[str, int]:
        db_path = self.report_root / "multimodal_search" / "runtime" / "multimodal_search.db"
        return self._count_by_modality(db_path, "mm_assets")

    def _count_ai_album_ai_space_assets(self) -> dict[str, int]:
        db_path = self.report_root / "ai_space" / "runtime" / "ai_space.db"
        return self._count_by_modality(db_path, "ai_space_asset_views")

    @staticmethod
    def _count_by_modality(db_path: Path, table: str) -> dict[str, int]:
        if not db_path.exists():
            return {}
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(f"SELECT modality,count(*) AS c FROM {table} GROUP BY modality").fetchall()
                return {str(row["modality"] or "other"): int(row["c"] or 0) for row in rows}
            finally:
                conn.close()
        except sqlite3.Error:
            return {}

    def media_preview_access(self, resolved: Path, user: dict) -> tuple[bool, HTTPStatus]:
        if self.personal_root:
            try:
                personal = self.personal_root.resolve(strict=True)
                relative_path = resolved.resolve(strict=True).relative_to(personal).as_posix()
                if self.can_read(user, relative_path):
                    return True, HTTPStatus.OK
                return False, HTTPStatus.FORBIDDEN
            except (OSError, ValueError):
                pass
        scope = self.ai_album_organizer_scope()
        for root in scope.get("root_paths") or []:
            try:
                if _path_is_relative_to(resolved, Path(root)):
                    return True, HTTPStatus.OK
            except OSError:
                continue
        return False, HTTPStatus.NOT_FOUND

    @staticmethod
    def _public_workspace_relative(path: Path, workspace: Path) -> str:
        try:
            return path.resolve(strict=False).relative_to(workspace.resolve(strict=False)).as_posix()
        except ValueError:
            return path.name

    @staticmethod
    def _is_project_artifact_material_path(path: Path, workspace: Path, personal: Path) -> bool:
        try:
            parts = path.resolve(strict=False).relative_to(workspace.resolve(strict=False)).parts
        except ValueError:
            return True
        if not parts:
            return True
        first = parts[0].strip()
        first_lower = first.lower()
        if first.startswith("@") or first_lower in AI_ALBUM_PROJECT_ARTIFACT_NAMES:
            return True
        if _path_is_relative_to(path, personal) and len(parts) >= 2:
            return product_hidden_storage_name(parts[1])
        return False

    def media_upload_photo(self, payload: dict, user: dict) -> tuple[int, dict]:
        if not self.personal_root or not self.media_center:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "media_center_unavailable", "raw_path_returned": False}
        raw_filename = str(payload.get("filename") or payload.get("name") or "uploaded_photo.jpg").strip()
        filename = self._safe_upload_filename(raw_filename)
        if not filename:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_filename", "raw_path_returned": False}
        if Path(filename).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "unsupported_upload_format", "supported": ["jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff"], "raw_path_returned": False}
        try:
            target_dir = normalize_storage_relative_path(payload.get("target_dir") or "Uploads")
            parent = resolve_storage_path(self.personal_root, target_dir)
        except StoragePathError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc), "raw_path_returned": False}
        if not self.can_write(user, target_dir):
            self.record_operation("media_upload", None, target_dir, "permission_denied", str(user.get("username")))
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "write", "raw_path_returned": False}
        parent.mkdir(parents=True, exist_ok=True)
        try:
            content = base64.b64decode(str(payload.get("content_base64") or payload.get("data_base64") or ""), validate=True)
        except (binascii.Error, ValueError) as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid_base64:{exc}", "raw_path_returned": False}
        if len(content) > MAX_UPLOAD_BYTES:
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "upload_too_large", "max_bytes": MAX_UPLOAD_BYTES, "raw_path_returned": False}
        if not is_supported_image_bytes(content[:16], Path(filename).suffix):
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_image_content", "raw_path_returned": False}
        target = self._unique_child(parent, filename)
        try:
            target.write_bytes(content)
        except OSError as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"upload_write_failed:{type(exc).__name__}:{exc}", "raw_path_returned": False}

        target_rel = target.resolve(strict=False).relative_to(self.personal_root.resolve(strict=False)).as_posix()
        self.record_operation("media_upload", None, target_rel, "created", str(user.get("username")))
        bounded_rebuild = bool(payload.get("upload_scope_only") or payload.get("bounded_rebuild"))
        media_asset_root = parent if bounded_rebuild else self.personal_root
        media_index = self.media_center.index_photos(parent, asset_root=media_asset_root, source_id="media_upload")
        media_item = self.media_center.item_for_path(target, asset_root=media_asset_root) or {}
        asset_id = media_item.get("asset_id") or self.media_center.asset_id_for_path(target, media_asset_root)
        sha256 = hashlib.sha256(content).hexdigest()
        jobs: list[dict] = []
        pipeline: dict[str, dict] = {"media_index": media_index}

        def run_pipeline_job(job_type: str, fn) -> dict:
            queue = self._product_job_queue()
            job = queue.enqueue(job_type, {"asset_id": asset_id, "path_hash": media_item.get("path_hash")}) if queue else {"ok": False, "job_type": job_type}
            job_id = job.get("job_id")
            if queue and job_id:
                queue.mark_running(job_id)
            try:
                result = fn()
                if queue and job_id:
                    queue.complete(job_id, evidence_ref=str(result.get("verdict") or result.get("schema") or job_type))
                job.update({"status": "completed", "result_ok": bool(result.get("ok", True))})
                pipeline[job_type] = self._redact_paths(result)
            except Exception as exc:
                if queue and job_id:
                    queue.fail(job_id, f"{type(exc).__name__}")
                job.update({"status": "failed", "error": f"{type(exc).__name__}"})
                pipeline[job_type] = {"ok": False, "error": job["error"]}
            jobs.append(job)
            return job

        run_pipeline_job("media_upload", lambda: {"ok": True, "schema": "digua_media_upload_v1"})
        rebuild_payload = {"roots": [str(parent)], "max_files": 20, "include_video": False} if bounded_rebuild else {}
        if bool(payload.get("auto_process", True)):
            if multimodal_route_response is not None:
                run_pipeline_job("multimodal_rebuild", lambda: multimodal_route_response("/api/multimodal-index/rebuild", method="POST", payload=rebuild_payload, report_root=self.report_root, personal_root=self.personal_root)[1])
            if yolo_route_response is not None:
                run_pipeline_job("yolo_index", lambda: yolo_route_response("/api/yolo-index/rebuild", method="POST", payload=rebuild_payload, report_root=self.report_root, personal_root=self.personal_root)[1])
            if person_attribute_route_response is not None:
                run_pipeline_job("person_attribute_rebuild", lambda: person_attribute_route_response("/api/person-attribute/rebuild", method="POST", payload=rebuild_payload, report_root=self.report_root, personal_root=self.personal_root)[1])
            if smart_classification_route_response is not None:
                run_pipeline_job("smart_classification_rebuild", lambda: smart_classification_route_response("/api/smart-classification/rebuild", method="POST", payload={}, report_root=self.report_root, personal_root=self.personal_root)[1])
            if smart_naming_route_response is not None:
                run_pipeline_job(
                    "smart_naming_generate",
                    lambda: smart_naming_route_response(
                        "/api/smart-naming/generate",
                        method="POST",
                        payload={
                            "asset_id": asset_id,
                            "asset": {
                                "asset_id": asset_id,
                                "title_redacted": media_item.get("title_redacted") or filename,
                                "modality": "image",
                                "mtime": target.stat().st_mtime,
                            },
                        },
                        report_root=self.report_root,
                        personal_root=self.personal_root,
                    )[1],
                )
            if ai_space_route_response is not None:
                run_pipeline_job("ai_space_rebuild", lambda: ai_space_route_response("/api/ai-space/rebuild", method="POST", payload={}, report_root=self.report_root, personal_root=self.personal_root)[1])

        naming_item = {}
        if smart_naming_route_response is not None:
            _code, naming_item = smart_naming_route_response(f"/api/smart-naming/item/{asset_id}", method="GET", report_root=self.report_root, personal_root=self.personal_root)
        return HTTPStatus.OK, {
            "ok": True,
            "schema": "digua_media_upload_auto_classify_v1",
            "asset_id": asset_id,
            "path_hash": media_item.get("path_hash"),
            "sha256": sha256,
            "size_bytes": len(content),
            "media_item": media_item,
            "jobs": jobs,
            "pipeline": pipeline,
            "smart_naming": naming_item.get("item") if isinstance(naming_item, dict) else None,
            "upload_event": {
                "status": "saved_to_personal_nas",
                "original_file_renamed": False,
                "overwrite_performed": False,
            },
            "physical_file_moved": False,
            "physical_file_renamed": False,
            "cloud_used": False,
            "raw_path_returned": False,
        }

    def media_index_payload(self, relative_path: str, user: dict) -> tuple[int, dict]:
        if not self.personal_root or not self.media_center:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "media_center_unavailable", "raw_path_returned": False}
        try:
            rel = normalize_storage_relative_path(relative_path or "")
            root = resolve_storage_path(self.personal_root, rel)
        except StoragePathError as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc), "raw_path_returned": False}
        if not self.can_read(user, rel):
            return HTTPStatus.FORBIDDEN, {"ok": False, "error": "permission_denied", "required": "read", "raw_path_returned": False}
        result = self.media_center.index_photos(root, asset_root=self.personal_root, source_id="manual_api")
        return HTTPStatus.OK, {"ok": True, "index": result, "status": self.media_status_payload(), "raw_path_returned": False}

    def _product_job_queue(self):
        if ProductJobQueue is None:
            return None
        return ProductJobQueue(self.report_root / "product_jobs" / "runtime" / "product_jobs.db")

    @staticmethod
    def _safe_upload_filename(filename: str) -> str:
        base = Path(filename).name.strip()
        base = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", base)
        base = re.sub(r"\s+", "_", base)
        if base in {"", ".", ".."}:
            return ""
        return base[:120]

    @staticmethod
    def _unique_child(parent: Path, filename: str) -> Path:
        candidate = parent / filename
        if not candidate.exists():
            return candidate
        stem = candidate.stem
        suffix = candidate.suffix
        for index in range(1, 1000):
            numbered = parent / f"{stem}_{index:03d}{suffix}"
            if not numbered.exists():
                return numbered
        raise FileExistsError("no_unique_upload_name_available")

    @staticmethod
    def _redact_paths(value):
        if isinstance(value, dict):
            return {key: PortalState._redact_paths(item) for key, item in value.items()}
        if isinstance(value, list):
            return [PortalState._redact_paths(item) for item in value]
        if isinstance(value, str):
            text = re.sub(r"([A-Za-z]:\\[^\s\"']+|/mnt/nas/[^\s\"']+|/home/[^\s\"']+|/root/[^\s\"']+|/opt/[^\s\"']+)", "[redacted-path]", value)
            return text
        return value

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

    def _copilot_qwen_router_completion(self, message: str, model: str | None = None) -> dict:
        payload = {
            "model": model or self.qwen_model,
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

    def _copilot_structured_router_completion(self, message: str, model: str | None = None) -> dict:
        payload = {
            "model": model or self.qwen_model,
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

    def copilot_qwen_route(self, message: str, action_intent: dict | None = None, model: str | None = None) -> dict:
        policy = copilot_policy_route(message, action_intent)
        qwen_route: dict | None = None
        selected_model = model or self.qwen_model
        router_model_calls: list[dict] = []
        result = self._copilot_qwen_router_completion(message, model)
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
                qwen_route["model"] = selected_model
                qwen_route["reported_model"] = upstream.get("model") or None
        router_model_calls.append(
            assistant_model_call(
                stage="semantic_router",
                model=selected_model,
                provider="local_qwen",
                location="S100P_BPU",
                purpose="intent_privacy_complexity_and_workspace_advice",
                elapsed_ms=result.get("elapsed_ms"),
                status="completed" if qwen_route else ("invalid_structured_result" if result.get("ok") else "failed"),
            )
        )
        if not qwen_route:
            fallback = self._copilot_structured_router_completion(message, model)
            fallback_route: dict | None = None
            if fallback.get("ok"):
                content, _metadata, upstream = chat_completion_content(fallback)
                parsed = parse_json_object_from_text(content)
                fallback_route = normalize_copilot_router(
                    parsed or {},
                    classifier="qwen_gateway_structured_router_fallback",
                    raw_content=content,
                    elapsed_ms=fallback.get("elapsed_ms"),
                )
                if fallback_route:
                    fallback_route["model"] = selected_model
                    fallback_route["reported_model"] = upstream.get("model") or None
                    fallback_route["fallback_from_real_qwen"] = True
                    qwen_route = fallback_route
            router_model_calls.append(
                assistant_model_call(
                    stage="semantic_router_fallback",
                    model=selected_model,
                    provider="local_qwen",
                    location="S100P_BPU",
                    purpose="intent_privacy_complexity_and_workspace_advice",
                    elapsed_ms=fallback.get("elapsed_ms"),
                    status="completed" if fallback_route else ("invalid_structured_result" if fallback.get("ok") else "failed"),
                )
            )
        if not qwen_route:
            qwen_route = {
                **policy,
                "classifier": "portal_policy_fallback_after_qwen_failure",
                "qwen_router_failed": True,
                "qwen_router_error": result.get("error") or (result.get("payload") or {}).get("error") if isinstance(result.get("payload"), dict) else result.get("error"),
                "elapsed_ms": result.get("elapsed_ms"),
            }
        qwen_route["router_attempt_count"] = len(router_model_calls)
        qwen_route["model_calls"] = router_model_calls
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

    def _copilot_storage_inventory(self, intent: dict, user: dict, router: dict) -> tuple[int, dict]:
        rel = str(intent.get("path") or "")
        quoted = intent.get("quoted") or []
        try:
            normalized_rel = normalize_storage_relative_path(rel)
        except StoragePathError:
            normalized_rel = rel
        use_material_scope = not quoted and normalized_rel in {"", "Photos", "Videos", "Documents"}
        status, payload = self.ai_album_material_inventory_payload(user, limit=40) if use_material_scope else self.storage_inventory_payload(rel, user)
        if status != HTTPStatus.OK:
            return self._copilot_attach_router(status, payload, router, assistant_mode="local_storage_inventory")
        summary = payload.get("summary") or {}
        entries = payload.get("entries") or []
        type_counts = summary.get("type_counts") or {}
        top_types = "、".join([f"{name} {count}" for name, count in list(type_counts.items())[:4]]) or "暂无"
        scope_label = payload.get("relative_path") or normalized_rel
        scope_text = "AI 相册整理范围" if use_material_scope else "本地个人空间"
        payload.update(
            {
                "assistant_mode": "local_storage_inventory",
                "route": "local_storage_inventory",
                "model": "S100P storage inventory via Qwen router",
                "answer": (
                    f"已在{scope_text}完成只读盘点：顶层条目 {int(summary.get('top_level_count') or 0)} 个，"
                    f"文件 {int(summary.get('file_count') or 0)} 个，文件夹 {int(summary.get('dir_count') or 0)} 个，"
                    f"估算占用 {human_size(int(summary.get('total_size_bytes') or 0))}。主要类型：{top_types}。"
                ),
                "cloud_used": False,
                "qwen_execution_authority": False,
                "nas_action": {
                    "operation": "inventory",
                    "status": "completed",
                    "path": scope_label,
                    "entries": entries,
                    "summary": summary,
                    "organizer_scope": "demo_test_personal_material_only" if use_material_scope else "personal_root_acl",
                    "qwen_execution_authority": False,
                    "direct_nas_write_performed": False,
                },
            }
        )
        return self._copilot_attach_router(status, payload, router, assistant_mode="local_storage_inventory")

    def _local_qwen_document_answer_completion(self, query: str, evidence: list[dict]) -> dict:
        prompt = build_document_grounded_answer_prompt(query, evidence)
        if document_amount_hits(evidence) and contains_any(
            query,
            ("金额", "多少钱", "多少", "合计", "账单", "开支", "amount", "total", "bill", "expense"),
        ):
            prompt = build_document_grounded_retry_prompt(query, evidence)
        payload = {
            "model": self.qwen_model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 256,
            "stream": False,
            "disable_ai_nas_tools": True,
            "metadata": {
                "source": "openclaw_operator_portal",
                "purpose": "local_document_grounded_answer",
                "evidence_count": len(evidence),
                "disable_ai_nas_tools": True,
                "qwen_execution_authority": False,
                "raw_path_returned": False,
            },
        }
        return http_post_json(
            "local_qwen_document_grounded_answer",
            normalize_chat_completions_url(self.qwen_gateway_url or DEFAULT_QWEN_GATEWAY_URL),
            payload,
            timeout=180,
        )

    def _local_qwen_document_answer_retry_completion(self, query: str, evidence: list[dict]) -> dict:
        payload = {
            "model": self.qwen_model,
            "messages": [
                {"role": "user", "content": build_document_grounded_retry_prompt(query, evidence)},
            ],
            "temperature": 0.0,
            "max_tokens": 120,
            "stream": False,
            "disable_ai_nas_tools": True,
            "metadata": {
                "source": "openclaw_operator_portal",
                "purpose": "local_document_grounded_answer_retry",
                "evidence_count": len(evidence),
                "disable_ai_nas_tools": True,
                "qwen_execution_authority": False,
                "raw_path_returned": False,
            },
        }
        return http_post_json(
            "local_qwen_document_grounded_answer_retry",
            normalize_chat_completions_url(self.qwen_gateway_url or DEFAULT_QWEN_GATEWAY_URL),
            payload,
            timeout=180,
        )

    def local_qwen_document_answer(self, query: str, evidence: list[dict]) -> dict:
        if not evidence:
            return {"ok": False, "error": "no_document_evidence"}
        result = self._local_qwen_document_answer_completion(query, evidence)
        if not result.get("ok"):
            return {
                "ok": False,
                "error": "local_qwen_document_answer_failed",
                "upstream_status": result.get("status"),
                "upstream_error": result.get("error") or (result.get("payload") or {}).get("error") if isinstance(result.get("payload"), dict) else result.get("error"),
                "elapsed_ms": result.get("elapsed_ms"),
            }
        content, _metadata, upstream = chat_completion_content(result)
        answer = content.strip()
        if not answer:
            return {"ok": False, "error": "local_qwen_document_answer_empty", "elapsed_ms": result.get("elapsed_ms")}
        amounts = document_amount_hits(evidence)
        amount_sensitive = bool(amounts) and contains_any(
            query,
            ("金额", "多少钱", "多少", "合计", "账单", "开支", "amount", "total", "bill", "expense"),
        )
        def grounding_validation_error(answer_text: str) -> str | None:
            generic = contains_any(
                answer_text,
                (
                    "有什么问题",
                    "需要我",
                    "请问您",
                    "无法确定",
                    "无法回答",
                    "无法提供",
                    "无法获取",
                    "人工智能语言模型",
                    "请您提供更多",
                    "提供更多",
                    "澄清",
                    "误解",
                    "告诉我",
                ),
            )
            if generic:
                return "local_qwen_document_answer_failed_grounding_validation"
            if not amount_sensitive:
                return None
            amount_digits = [re.sub(r"\D+", "", item) for item in amounts if re.sub(r"\D+", "", item)]
            preferred_digits = [
                re.sub(r"\D+", "", item)
                for item in amounts
                if re.sub(r"\D+", "", item) and contains_any(item, ("元", "块", "人民币"))
            ]
            if preferred_digits:
                exact_amount = any(
                    re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])\s*(?:元|人民币|块)", answer_text)
                    for token in preferred_digits
                    if token
                )
            else:
                exact_amount = any(
                    re.search(rf"(?<![\d.]){re.escape(token)}(?![\d.])", answer_text)
                    for token in amount_digits
                    if token
                )
            approximate = contains_any(answer_text, ("约等于", "约为", "大约", "≈", "approx"))
            if approximate or not exact_amount:
                return "local_qwen_document_answer_failed_grounding_validation"
            return None

        validation_error = grounding_validation_error(answer)
        if validation_error:
            retry_attempts = 3 if amount_sensitive else 1
            retry_answer = ""
            retry_error = ""
            retry_elapsed_ms = result.get("elapsed_ms")
            for retry_index in range(1, retry_attempts + 1):
                retry = self._local_qwen_document_answer_retry_completion(query, evidence)
                retry_elapsed_ms = retry.get("elapsed_ms")
                if not retry.get("ok"):
                    retry_error = retry.get("error") or (retry.get("payload") or {}).get("error") if isinstance(retry.get("payload"), dict) else retry.get("error")
                    continue
                retry_content, _retry_metadata, retry_upstream = chat_completion_content(retry)
                retry_answer = retry_content.strip()
                if retry_answer and not grounding_validation_error(retry_answer):
                    retry_answer = normalize_document_answer_amount_units(retry_answer, evidence)
                    retry_answer = normalize_document_money_answer_sentence(query, retry_answer, evidence)
                    return {
                        "ok": True,
                        "answer": retry_answer,
                        "model": retry_upstream.get("model") or self.qwen_model,
                        "finish_reason": ((retry_upstream.get("choices") or [{}])[0] or {}).get("finish_reason") if isinstance(retry_upstream.get("choices"), list) else None,
                        "usage": retry_upstream.get("usage") if isinstance(retry_upstream.get("usage"), dict) else {},
                        "elapsed_ms": retry.get("elapsed_ms"),
                        "retried": True,
                        "retry_attempt_count": retry_index,
                        "first_answer_rejected": True,
                    }
            return {
                "ok": False,
                "error": validation_error,
                "qwen_answer_preview": answer[:200],
                "qwen_retry_answer_preview": retry_answer[:200],
                "retry_error": retry_error,
                "retry_attempt_count": retry_attempts,
                "elapsed_ms": retry_elapsed_ms,
            }
        answer = normalize_document_answer_amount_units(answer, evidence)
        answer = normalize_document_money_answer_sentence(query, answer, evidence)
        return {
            "ok": True,
            "answer": answer,
            "model": upstream.get("model") or self.qwen_model,
            "finish_reason": ((upstream.get("choices") or [{}])[0] or {}).get("finish_reason") if isinstance(upstream.get("choices"), list) else None,
            "usage": upstream.get("usage") if isinstance(upstream.get("usage"), dict) else {},
            "elapsed_ms": result.get("elapsed_ms"),
        }

    def _copilot_document_query(self, intent: dict, user: dict, router: dict) -> tuple[int, dict]:
        status, payload = self.document_query_payload(str(intent.get("query") or ""), str(intent.get("path") or "Documents"), user)
        if status == HTTPStatus.OK:
            evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
            if intent.get("journal_lookup"):
                journal_date = str(intent.get("journal_date") or "").strip()
                evidence = journal_evidence_for_date(journal_date, evidence)
                evidence_refs = [str(item.get("evidence_ref") or "") for item in evidence if item.get("evidence_ref")]
                answer = journal_answer_from_evidence(journal_date, evidence)
                payload["evidence"] = evidence
                payload["evidence_refs"] = evidence_refs
                payload["evidence_count"] = len(evidence)
                payload["journal_lookup"] = True
                payload["journal_date"] = journal_date
                payload["qwen_document_answer_used"] = False
                payload["qwen_document_answer_attempted"] = False
                payload["qwen_document_answer_retry_used"] = False
                payload["qwen_document_answer_retry_attempts"] = 0
                if answer:
                    payload["answer"] = answer
                    payload["document_answer_source"] = "deterministic_journal_evidence"
                else:
                    payload["answer"] = f"未在已授权的本地文档中找到 {journal_date} 的日记记录。"
                    payload["document_answer_source"] = "deterministic_journal_no_match"
            elif evidence:
                qwen_answer = self.local_qwen_document_answer(str(intent.get("query") or ""), evidence)
                payload["qwen_document_answer_attempted"] = True
                if qwen_answer.get("ok"):
                    payload["answer"] = qwen_answer.get("answer") or payload.get("answer")
                    payload["document_answer_source"] = "local_qwen_grounded_rag"
                    payload["qwen_document_answer_used"] = True
                    payload["qwen_document_answer_retry_used"] = bool(qwen_answer.get("retried"))
                    payload["qwen_document_answer_retry_attempts"] = qwen_answer.get("retry_attempt_count") or 0
                    payload["grounded_answer_model"] = qwen_answer.get("model")
                    payload["grounded_answer_elapsed_ms"] = qwen_answer.get("elapsed_ms")
                    payload["usage"] = qwen_answer.get("usage") or {}
                else:
                    payload["document_answer_source"] = "deterministic_evidence_fallback"
                    payload["qwen_document_answer_used"] = False
                    payload["qwen_document_answer_retry_used"] = False
                    payload["qwen_document_answer_retry_attempts"] = qwen_answer.get("retry_attempt_count") or 0
                    payload["grounded_qwen_error"] = qwen_answer.get("error")
                    payload["grounded_answer_model"] = self.qwen_model
                    payload["grounded_answer_elapsed_ms"] = qwen_answer.get("elapsed_ms")
            payload.update(
                {
                    "assistant_mode": "local_document_query",
                    "route": "local_document_query",
                    "model": payload.get("grounded_answer_model") or "SQLite FTS-first RAG via Qwen router",
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
        cloud_headers: dict[str, str] = {}
        token_file = os.environ.get("AI_NAS_CLOUD_CHAT_TOKEN_FILE", "").strip()
        if token_file:
            try:
                cloud_token = Path(token_file).read_text(encoding="utf-8").strip()
            except OSError as exc:
                return self._copilot_attach_router(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": "cloud_bridge_token_unavailable", "detail": type(exc).__name__},
                    router,
                )
            if not cloud_token:
                return self._copilot_attach_router(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": "cloud_bridge_token_empty"},
                    router,
                )
            cloud_headers["Authorization"] = f"Bearer {cloud_token}"
        cloud_model = os.environ.get("AI_NAS_CLOUD_CHAT_MODEL", MINIMAX_MODEL)
        result = http_post_json(
            "cloud_overflow_chat",
            normalize_chat_completions_url(cloud_url),
            {
                "model": cloud_model,
                "messages": [{"role": "user", "content": message}],
                "stream": False,
                "metadata": {"source": "digua_ai_nas_cloud_overflow", "privacy_level": "none"},
            },
            timeout=cloud_chat_timeout_seconds(),
            headers=cloud_headers,
        )
        if not result.get("ok"):
            return self._copilot_attach_router(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": "cloud_overflow_failed", "upstream": result}, router)
        content, _metadata, upstream = chat_completion_content(result)
        payload = {
            "ok": True,
            "assistant_mode": "cloud_overflow_chat",
            "answer": content.strip() or "cloud_overflow_empty_answer",
            "route": "cloud_overflow_chat",
            "model": cloud_model,
            "reported_model": upstream.get("model") or None,
            "elapsed_ms": result.get("elapsed_ms"),
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
        if action == "storage_inventory":
            return self._copilot_storage_inventory(intent, user, router)
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

    def _local_qwen_chat_completion(self, message: str, model: str | None = None) -> dict:
        selected_model = model or self.qwen_model
        gateway_url = (
            os.environ.get("AI_NAS_QWEN_7B_GATEWAY_URL", DEFAULT_QWEN_7B_GATEWAY_URL)
            if selected_model == QWEN_7B_MODEL
            else self.qwen_gateway_url or DEFAULT_QWEN_GATEWAY_URL
        )
        payload = {
            "model": selected_model,
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
            normalize_chat_completions_url(gateway_url),
            payload,
            timeout=420 if selected_model == QWEN_7B_MODEL else 180,
        )

    def local_qwen_chat(self, message: str, user: dict, model: str | None = None) -> tuple[int, dict]:
        clean_message = (message or "").strip()
        if not clean_message:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty_message"}
        if is_local_assistant_identity_question(clean_message):
            return HTTPStatus.OK, {
                "ok": True,
                "assistant_mode": "local_qwen_chat",
                "answer": (
                    "\u6211\u662f\u5730\u74dc AI-NAS \u7684\u672c\u5730 AI \u52a9\u624b\uff0c\u8fd0\u884c\u5728 S100P \u4e0a\u3002"
                    "\u6211\u53ef\u4ee5\u5728\u4f60\u7684\u6388\u6743\u8303\u56f4\u5185\u67e5\u8be2\u672c\u5730\u6587\u6863\u3001\u7167\u7247\u3001\u5b58\u50a8\u548c\u8fd0\u884c\u72b6\u6001\uff0c"
                    "\u4e0d\u4f1a\u628a\u79c1\u6709\u5185\u5bb9\u53d1\u9001\u5230\u4e91\u7aef\u3002"
                ),
                "route": "local_qwen_chat",
                "model": "Digua AI-NAS local identity",
                "identity_answer_source": "deterministic_local_identity",
                "usage": {},
                "cloud_used": False,
                "qwen_execution_authority": False,
                "nas_action": {
                    "operation": "none",
                    "status": "answered_by_local_identity",
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
        result = self._local_qwen_chat_completion(clean_message, model)
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
        answer = re.sub(
            r"<\|(?:im_start|im_end|endoftext)\|>",
            "",
            str(message_payload.get("content") or ""),
            flags=re.IGNORECASE,
        ).strip()
        if not answer:
            return HTTPStatus.BAD_GATEWAY, {
                "ok": False,
                "error": "local_qwen_empty_or_control_token_answer",
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
            "model": upstream.get("model") or model or self.qwen_model,
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

    @staticmethod
    def _copilot_album_label_for_category(category_id: str) -> str:
        return {
            "cat_album_primary_people": "person",
            "cat_album_primary_animals": "animal",
            "cat_album_primary_landscape": "landscape",
            "cat_album_primary_city": "architecture",
            "cat_album_primary_transport": "vehicle",
            "cat_album_primary_food": "food",
            "cat_album_primary_docs": "document",
            "cat_album_primary_other": "other",
        }.get(category_id, "album_category")

    @staticmethod
    def _copilot_explicit_album_category_request(intent: dict) -> bool:
        query = str(intent.get("query") or "")
        lower = query.lower()
        if any(str(term).lower() in lower for term in AI_ALBUM_EXPLICIT_CATEGORY_QUERY_TERMS):
            return True
        for category in AI_ALBUM_PRIMARY_CATEGORIES:
            if str(category.get("name") or "") in query or str(category.get("name_en") or "").lower() in lower:
                return True
        return False

    @staticmethod
    def _copilot_album_category_for_intent(intent: dict) -> dict | None:
        if not PortalState._copilot_explicit_album_category_request(intent):
            return None
        query = str(intent.get("query") or "")
        lower = query.lower()
        labels = {str(label).lower() for label in (intent.get("labels") or [])}
        if "person" in labels and not any(term in query for term in ("无人机", "机器人")):
            return next((item for item in AI_ALBUM_PRIMARY_CATEGORIES if item["id"] == "cat_album_primary_people"), None)
        label_category = {
            "cat": "cat_album_primary_animals",
            "dog": "cat_album_primary_animals",
            "bird": "cat_album_primary_animals",
            "car": "cat_album_primary_transport",
            "bus": "cat_album_primary_transport",
            "truck": "cat_album_primary_transport",
            "bicycle": "cat_album_primary_transport",
            "motorcycle": "cat_album_primary_transport",
            "train": "cat_album_primary_transport",
            "airplane": "cat_album_primary_transport",
            "boat": "cat_album_primary_transport",
        }
        for label, category_id in label_category.items():
            if label in labels:
                return next((item for item in AI_ALBUM_PRIMARY_CATEGORIES if item["id"] == category_id), None)
        for category in AI_ALBUM_PRIMARY_CATEGORIES:
            category_id = str(category["id"])
            terms = AI_ALBUM_COPILOT_CATEGORY_ALIASES.get(category_id) or ()
            if any(str(term).lower() in lower or str(term) in query for term in terms):
                return category
        return None

    def _copilot_album_primary_search(self, intent: dict, user: dict, *, limit: int = 8) -> dict:
        category = self._copilot_album_category_for_intent(intent)
        if not category:
            return {"ok": False, "degraded_reason": "no_album_primary_category_intent"}
        if not self.personal_root or not self.media_center:
            return {"ok": False, "degraded_reason": "media_center_unavailable"}
        scope = self.ai_album_organizer_scope()
        roots: list[Path] = list(scope.get("root_paths") or [])
        if not roots:
            return {"ok": False, "degraded_reason": "ai_album_scope_empty"}
        rows = self._ai_album_current_image_rows(roots, max_files=AI_ALBUM_AUTO_MAX_FILES)
        memberships = self._ai_album_primary_memberships([str(row.get("asset_id") or "") for row in rows])
        category_id = str(category["id"])
        category_name = str(category["name"])
        category_label = self._copilot_album_label_for_category(category_id)
        matched: list[dict] = []
        for row in rows:
            asset_id = str(row.get("asset_id") or "")
            selected = self._select_primary_membership(memberships.get(asset_id) or [])
            if not selected or str(selected.get("category_id") or "") != category_id:
                continue
            path_text = str(row.get("file_path") or "")
            if path_text:
                try:
                    resolved = Path(path_text).resolve(strict=True)
                    allowed, _denial_status = self.media_preview_access(resolved, user or {})
                    if not allowed:
                        continue
                except OSError:
                    continue
            try:
                score = float(selected.get("score") or 0.85)
            except (TypeError, ValueError):
                score = 0.85
            path_hash_value = str(row.get("path_hash") or "")
            matched.append(
                {
                    "rank": 0,
                    "asset_id": asset_id,
                    "title_redacted": f"{category_name}照片",
                    "modality": "image",
                    "file_type": row.get("extension") or row.get("file_type") or ".jpg",
                    "size_bytes": row.get("size_bytes"),
                    "mtime": row.get("mtime"),
                    "score": min(1.0, max(0.0, score)),
                    "matched_by": "album_primary_category",
                    "object_labels": [category_label],
                    "detections": [{"label": category_label, "label_zh": category_name, "confidence": min(1.0, max(0.0, score))}],
                    "evidence_ref": f"ai_album_primary:{category_id}:{asset_id}",
                    "path_hash": path_hash_value,
                    "privacy_level": "local_only",
                    "score_components": {"album_primary_score": min(1.0, max(0.0, score))},
                    "preview_url": f"/api/media/preview?path_hash={quote(path_hash_value, safe='')}" if path_hash_value else "",
                    "preview_kind": "image" if path_hash_value else "",
                }
            )
        matched.sort(key=lambda item: (float(item.get("score") or 0.0), float(item.get("mtime") or 0.0)), reverse=True)
        for index, item in enumerate(matched[:limit], start=1):
            item["rank"] = index
            item["title_redacted"] = f"{category_name}照片 {index}"
        return {
            "ok": True,
            "schema": "digua_ai_album_primary_search_v1",
            "query_redacted": str(intent.get("query") or "")[:120],
            "category_id": category_id,
            "category_name": category_name,
            "labels": ["person"] if category_id == "cat_album_primary_people" else [category_label],
            "results": matched[:limit],
            "total_count": len(matched),
            "retrieval_mode": "ai_album_primary_category",
            "privacy": {"raw_path_returned": False, "cloud_used": False},
            "cloud_used": False,
            "raw_path_returned": False,
        }

    def enrich_copilot_search_result(
        self,
        item: dict,
        user: dict,
        path_cache: dict[str, tuple[Path | None, str | None]],
    ) -> dict:
        safe = sanitize_copilot_search_result(item)
        path_hash_value = str(safe.get("path_hash") or "")
        path, _relative_path = self.media_file_by_path_hash(path_hash_value, user, path_cache)
        preview_route = "media" if path else ""
        if not path:
            path, _relative_path = self.storage_file_by_path_hash(path_hash_value, user, path_cache)
            preview_route = "storage" if path else ""
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
            if preview_route == "media":
                safe["preview_url"] = f"/api/media/preview?path_hash={quote(path_hash_value, safe='')}"
            else:
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
        modality = str(intent.get("modality") or "all").lower()
        if mode != "local_ai_album_category_search" and modality == "image":
            before_count = len(results)
            results = [
                item
                for item in results
                if bool((item.get("display") or {}).get("preview_available")) and bool(item.get("preview_url"))
            ]
            if before_count and not results:
                result = {
                    **result,
                    "degraded": True,
                    "degraded_reason": result.get("degraded_reason") or "local_index_results_without_resolvable_media_preview",
                }
        result_count = len(results)
        query = str(intent.get("query") or "")
        labels = result.get("labels") or intent.get("labels") or []
        album_category: dict | None = None
        if result_count == 0 or self._copilot_explicit_album_category_request(intent):
            album_result = self._copilot_album_primary_search(intent, user, limit=8)
            album_results = album_result.get("results") if isinstance(album_result.get("results"), list) else []
            if album_result.get("ok") and album_results:
                album_category = {
                    "category_id": album_result.get("category_id"),
                    "category_name": album_result.get("category_name"),
                    "total_count": int(album_result.get("total_count") or len(album_results)),
                }
                results = [
                    self.enrich_copilot_search_result(item, user, path_cache)
                    for item in album_results[:8]
                    if isinstance(item, dict)
                ]
                result_count = int(album_result.get("total_count") or len(results))
                labels = album_result.get("labels") or labels
                retrieval_mode = album_result.get("retrieval_mode") or "ai_album_primary_category"
                source = "AI album primary classification"
                mode = "local_ai_album_category_search"
                result = {
                    **result,
                    "query_redacted": album_result.get("query_redacted") or result.get("query_redacted"),
                    "privacy": album_result.get("privacy") or result.get("privacy"),
                    "degraded": False,
                    "degraded_reason": None,
                }
        title_summary = summarize_search_result_titles(results)
        allow_inventory_fallback = modality not in {"image", "video"}
        fallback_inventory = self._copilot_search_fallback_inventory(intent, user) if result_count == 0 and allow_inventory_fallback else None
        if result_count:
            image_only = (intent.get("modality") == "image") or all((item.get("display") or {}).get("type_label") == "照片" for item in results)
            unit = "张相关照片" if image_only else "个匹配结果"
            if album_category:
                answer = f"已在本地 NAS 相册分类索引中搜索“{query}”，命中“{album_category.get('category_name')}”分类，找到 {result_count} {unit}。下方卡片是真实 NAS 图片预览。"
            else:
                answer = f"已在本地 NAS 索引中搜索“{query}”，找到 {result_count} {unit}。下方卡片包含预览图、名称、日期和匹配原因。"
            if title_summary:
                answer += f" 结果包括：{title_summary}。"
            if "person" in labels:
                answer += " 这里只表示检测到 person 目标，不做人脸识别，也不判断具体身份。"
        else:
            raw_reason = result.get("degraded_reason") or "no_matching_local_index_result"
            reason = copilot_search_reason_display(raw_reason)
            if fallback_inventory and fallback_inventory.get("ok"):
                summary = fallback_inventory.get("summary") or {}
                scope = fallback_inventory.get("relative_path") or "/"
                answer = (
                    f"已查询本地 NAS 索引“{query}”，对象/语义索引没有返回匹配结果。原因：{reason}。"
                    f"随后已按只读权限盘点 {scope}，返回顶层条目 {int(summary.get('top_level_count') or 0)} 个、"
                    f"文件 {int(summary.get('file_count') or 0)} 个。未调用云端；Qwen 只做意图理解，"
                    "NAS 查询由本地受控 API 执行。"
                )
            else:
                media_hint = "这是图片/视频检索请求，因此没有改成目录盘点。" if not allow_inventory_fallback else ""
                answer = f"已查询本地 NAS 视觉索引“{query}”，当前对象/语义索引没有返回匹配图片。原因：{reason}。{media_hint}未调用云端；Qwen 只做意图理解，NAS 查询由本地受控 API 执行。"
        payload = {
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
                "album_category": album_category,
                "degraded": bool(result.get("degraded")),
                "degraded_reason": result.get("degraded_reason"),
                "degraded_reason_display": copilot_search_reason_display(result.get("degraded_reason")) if result.get("degraded_reason") else None,
                "fallback_inventory_performed": bool(fallback_inventory and fallback_inventory.get("ok")),
                "fallback_inventory_status": (fallback_inventory or {}).get("status"),
                "privacy": result.get("privacy") or {"raw_path_returned": False, "cloud_used": False},
            },
            "nas_action": {
                "operation": "search",
                "status": "completed" if result_count else "completed_empty",
                "qwen_execution_authority": False,
                "direct_nas_write_performed": False,
                "read_only_inventory_fallback": bool(fallback_inventory and fallback_inventory.get("ok")),
                "album_primary_category_fallback": bool(album_category),
                "forbidden_actions": ["delete", "move", "rename", "chmod", "chown", "recursive", "overwrite", "shell"],
            },
            "audit": {
                "tool_executor": "openclaw_local_api",
                "local_search_performed": True,
                "read_only_inventory_fallback": bool(fallback_inventory and fallback_inventory.get("ok")),
                "album_primary_category_fallback": bool(album_category),
                "direct_nas_write_performed": False,
                "cloud_payload_sent": False,
                "raw_path_returned": False,
                "prompt_hash": hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest(),
            },
        }
        if fallback_inventory:
            payload["fallback_inventory"] = fallback_inventory
        return HTTPStatus.OK, payload

    def _copilot_search_fallback_inventory(self, intent: dict, user: dict) -> dict:
        modality = str(intent.get("modality") or "").lower()
        scope = {"image": "Photos", "video": "Videos", "document": "Documents"}.get(modality, "")
        status, payload = self.ai_album_material_inventory_payload(user, limit=20)
        if isinstance(payload, dict):
            payload["fallback_from"] = scope or "AI相册整理范围"
        safe_payload = self._redact_paths(dict(payload)) if isinstance(payload, dict) else {"error": str(payload)}
        safe_payload["status"] = "completed" if status == HTTPStatus.OK and safe_payload.get("ok") else "failed"
        safe_payload["requested_scope"] = "AI相册整理范围"
        safe_payload["raw_path_returned"] = False
        return safe_payload

    def local_copilot_search(self, intent: dict, user: dict) -> tuple[int, dict]:
        query = str(intent.get("query") or "").strip()
        yolo_empty_result: dict | None = None
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
                yolo_results = result.get("results") if isinstance(result.get("results"), list) else []
                if yolo_results:
                    return self._copilot_search_response(
                        mode="local_yolo_search",
                        intent=intent,
                        result=result,
                        source="S100P YOLO object index",
                        retrieval_mode="yolo_object_index",
                        user=user,
                    )
                yolo_empty_result = result
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
        try:
            status_code, result = multimodal_route_response(
                "/api/multimodal-search/query",
                method="POST",
                payload=mm_payload,
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        except Exception as exc:
            if yolo_empty_result is not None:
                degraded_result = dict(yolo_empty_result)
                degraded_result["degraded"] = True
                degraded_result["degraded_reason"] = f"local_multimodal_search_exception:{type(exc).__name__}"
                degraded_result["multimodal_error"] = str(exc)[:180]
                return self._copilot_search_response(
                    mode="local_yolo_search",
                    intent=intent,
                    result=degraded_result,
                    source="S100P YOLO object index",
                    retrieval_mode="yolo_object_index",
                    user=user,
                )
            return HTTPStatus.BAD_GATEWAY, {
                "ok": False,
                "error": "local_multimodal_search_exception",
                "detail": str(exc)[:180],
                "route": "local_multimodal_search",
                "cloud_used": False,
                "qwen_execution_authority": False,
            }
        if status_code != HTTPStatus.OK or not result.get("ok"):
            if yolo_empty_result is not None:
                return self._copilot_search_response(
                    mode="local_yolo_search",
                    intent=intent,
                    result=yolo_empty_result,
                    source="S100P YOLO object index",
                    retrieval_mode="yolo_object_index",
                    user=user,
                )
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

    def copilot_chat(self, message: str, user: dict, model_choice: object = None) -> tuple[int, dict]:
        clean_message = str(message or "").strip()
        if not clean_message:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty_message"}
        request_id = hashlib.sha256(f"{time.time_ns()}:{clean_message}".encode("utf-8", errors="replace")).hexdigest()[:16]
        if is_local_assistant_identity_question(clean_message):
            status, payload = self.local_qwen_chat(clean_message, user, self.qwen_model)
            identity_policy = copilot_policy_route(clean_message)
            identity_plan = {
                "workspace": "main_router",
                "route": "LOCAL_1_5B",
                "kind": "deterministic_local_identity",
                "model": None,
                "provider": "local_policy",
                "location": "S100P",
                "reason": "Identity questions use the deterministic local identity contract without invoking a language model.",
            }
            attach_assistant_model_routing(
                payload,
                router={**identity_policy, "policy_route": identity_policy},
                plan=identity_plan,
                calls=[],
                requested_model_choice=model_choice,
                request_id=request_id,
            )
            return status, payload
        action_intent = infer_copilot_action_intent(clean_message)
        router_model = self.qwen_model
        router = self.copilot_qwen_route(clean_message, action_intent, router_model)
        plan = assistant_answer_model_plan(action_intent, router)
        model_calls = assistant_router_model_calls(router)
        if action_intent:
            status, payload = self.dispatch_copilot_action(action_intent, user, router)
            model_calls.extend(assistant_workspace_response_calls(payload))
            attach_assistant_model_routing(
                payload,
                router=router,
                plan=plan,
                calls=model_calls,
                requested_model_choice=model_choice,
                request_id=request_id,
            )
            return status, payload
        if plan.get("kind") == "cloud_answer":
            status, payload = self._copilot_cloud_overflow(clean_message, user, router)
            if payload.get("cloud_used"):
                model_calls.append(
                    assistant_model_call(
                        stage="response_generation",
                        model=str(plan.get("model") or MINIMAX_MODEL),
                        provider="openclaw_minimax",
                        location="controlled_cloud",
                        purpose="public_complex_answer",
                        elapsed_ms=payload.get("elapsed_ms"),
                    )
                )
                attach_assistant_model_routing(
                    payload,
                    router=router,
                    plan=plan,
                    calls=model_calls,
                    requested_model_choice=model_choice,
                    request_id=request_id,
                )
                return status, payload
            if payload.get("assistant_mode") != "cloud_overflow_stub":
                model_calls.append(
                    assistant_model_call(
                        stage="response_generation",
                        model=MINIMAX_MODEL,
                        provider="openclaw_minimax",
                        location="controlled_cloud",
                        purpose="public_complex_answer",
                        elapsed_ms=((payload.get("upstream") or {}).get("elapsed_ms") if isinstance(payload.get("upstream"), dict) else None),
                        status="failed",
                    )
                )
            fallback_plan = {
                **plan,
                "route": "LOCAL_7B",
                "fallback_from_route": "CLOUD_MINIMAX",
                "kind": "cloud_unavailable_local_7b_fallback",
                "model": QWEN_7B_MODEL,
                "provider": "local_qwen",
                "location": "S100P_CPU",
                "reason": "The policy selected cloud for eligible current public research, but the controlled cloud path was unavailable; local 7B provided the fallback answer.",
            }
            fallback_status, fallback_payload = self.local_qwen_chat(clean_message, user, QWEN_7B_MODEL)
            fallback_payload["cloud_fallback"] = True
            fallback_payload["cloud_fallback_reason"] = payload.get("error") or payload.get("assistant_mode") or "cloud_unavailable"
            model_calls.append(
                assistant_model_call(
                    stage="response_generation_fallback",
                    model=QWEN_7B_MODEL,
                    provider="local_qwen",
                    location="S100P_CPU",
                    purpose="public_complex_cloud_failure_fallback",
                    elapsed_ms=fallback_payload.get("elapsed_ms"),
                    status="completed" if fallback_status == HTTPStatus.OK else "failed",
                )
            )
            fallback_status, fallback_payload = self._copilot_attach_router(
                fallback_status,
                fallback_payload,
                router,
                assistant_mode=fallback_payload.get("assistant_mode"),
            )
            attach_assistant_model_routing(
                fallback_payload,
                router=router,
                plan=fallback_plan,
                calls=model_calls,
                requested_model_choice=model_choice,
                request_id=request_id,
            )
            return fallback_status, fallback_payload
        selected_model = str(plan.get("model") or DEFAULT_QWEN_MODEL)
        status, payload = self.local_qwen_chat(clean_message, user, selected_model)
        model_calls.append(
            assistant_model_call(
                stage="response_generation",
                model=selected_model,
                provider="local_qwen",
                location="S100P_CPU" if selected_model == QWEN_7B_MODEL else "S100P_BPU",
                purpose="local_complex_answer" if selected_model == QWEN_7B_MODEL else "local_default_answer",
                elapsed_ms=payload.get("elapsed_ms"),
                status="completed" if status == HTTPStatus.OK else "failed",
            )
        )
        status, payload = self._copilot_attach_router(
            status,
            payload,
            router,
            assistant_mode=payload.get("assistant_mode") if isinstance(payload, dict) else None,
        )
        attach_assistant_model_routing(
            payload,
            router=router,
            plan=plan,
            calls=model_calls,
            requested_model_choice=model_choice,
            request_id=request_id,
        )
        return status, payload

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

    def _report_ref(self, filename: str) -> dict:
        report = self.latest(filename)
        path = str(report.get("path") or "")
        evidence_ref = hashlib.sha256(path.encode("utf-8", errors="replace")).hexdigest()[:16] if path else hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]
        return {
            "found": bool(report.get("found")),
            "filename": filename,
            "verdict": report.get("verdict"),
            "generated_at": report.get("generated_at"),
            "evidence_ref": evidence_ref,
        }

    def _module_card(self, name: str, status: str, *, metrics: dict | None = None, evidence: dict | None = None, reason: str | None = None) -> dict:
        status = status if status in {"ok", "degraded", "failed"} else "degraded"
        return {
            "name": name,
            "ok": status != "failed",
            "status": status,
            "metrics": metrics or {},
            "evidence": evidence or {},
            "degraded_reason": reason if status == "degraded" else None,
        }

    def product_evidence_payload(self, limit: int = 40) -> dict:
        reports = self.list_reports_payload(limit=limit).get("reports") or []
        items = []
        for report in reports[:limit]:
            evidence_ref = report.get("trace_id") or hashlib.sha256(str(report.get("id") or report.get("title") or "").encode("utf-8")).hexdigest()[:12]
            items.append(
                {
                    "id": report.get("id"),
                    "title": report.get("title"),
                    "type": report.get("type"),
                    "mtime": report.get("mtime"),
                    "size_bytes": report.get("size_bytes"),
                    "evidence_ref": evidence_ref,
                    "export_available": bool(report.get("export_available")),
                    "degraded": bool(report.get("degraded")),
                }
            )
        return {
            "ok": True,
            "items": items,
            "report_count": len(items),
            "raw_path_returned": False,
            "path_redaction": "absolute paths are intentionally omitted from the product evidence API",
        }

    def product_status_payload(self) -> dict:
        readiness = self._report_ref("production_readiness_gate.json")
        edge_router = self._report_ref("edge_cloud_router.json")
        ocr_runtime = self._report_ref("ocr_runtime_contract.json")
        document_pipeline = self._report_ref("document_pipeline_acceptance.json")
        photo_pipeline = self._report_ref("photo_pipeline_acceptance.json")
        copy_governance = self._report_ref("destructive_action_governance.json")
        journal_deploy = self._report_ref("digua_journal_production_deployment.json")
        backup_gate = self._report_ref("backup_sync_gate.json")
        snapshot_gate = self._report_ref("snapshot_recovery_gate.json")
        ops_gate = self._report_ref("ops_observability_gate.json")

        qwen_health = http_health("qwen", normalize_health_url(self.qwen_gateway_url), timeout=3)
        qwen_status = "ok" if qwen_health.get("ok") else "degraded"
        harness_payload = harness_status_response(report_root=self.report_root, personal_root=self.personal_root) if harness_status_response else {"ok": False}
        harness_status = "ok" if harness_payload.get("ok") and not harness_payload.get("qwen_execution_authority") and not harness_payload.get("cloud_private_raw_egress") else "failed"

        yolo_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "yolo_route_unavailable"}
        if yolo_route_response is not None:
            _status_code, yolo_payload = yolo_route_response(
                "/api/yolo-index/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        yolo_status = "ok" if yolo_payload.get("ok") and not yolo_payload.get("degraded") else "degraded" if yolo_payload.get("ok") else "failed"

        multimodal_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "multimodal_route_unavailable"}
        if multimodal_route_response is not None:
            _status_code, multimodal_payload = multimodal_route_response(
                "/api/multimodal-search/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        multimodal_status = "ok" if multimodal_payload.get("ok") and not multimodal_payload.get("degraded") else "degraded" if multimodal_payload.get("ok") else "failed"

        person_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "person_attribute_route_unavailable"}
        if person_attribute_route_response is not None:
            _status_code, person_payload = person_attribute_route_response(
                "/api/person-attribute/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        person_status = "ok" if person_payload.get("ok") and not person_payload.get("degraded") else "degraded" if person_payload.get("ok") else "failed"

        ai_space_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "ai_space_route_unavailable"}
        if ai_space_route_response is not None:
            _status_code, ai_space_payload = ai_space_route_response(
                "/api/ai-space/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        ai_space_status = "ok" if ai_space_payload.get("ok") and not ai_space_payload.get("degraded") else "degraded" if ai_space_payload.get("ok") else "failed"

        auto_organizer_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "auto_organizer_route_unavailable"}
        if auto_organizer_route_response is not None:
            _status_code, auto_organizer_payload = auto_organizer_route_response(
                "/api/auto-organize/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        auto_organizer_status = "ok" if auto_organizer_payload.get("ok") else "failed"

        assistant_trace_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "assistant_trace_route_unavailable"}
        if assistant_trace_route_response is not None:
            _status_code, assistant_trace_payload = assistant_trace_route_response(
                "/api/assistant/trace/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        assistant_trace_status = "ok" if assistant_trace_payload.get("ok") and not assistant_trace_payload.get("hidden_chain_of_thought_saved") else "failed"

        smart_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "smart_classification_route_unavailable"}
        if smart_classification_route_response is not None:
            _status_code, smart_payload = smart_classification_route_response(
                "/api/smart-classification/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        smart_status = "ok" if smart_payload.get("ok") and not smart_payload.get("degraded") else "degraded" if smart_payload.get("ok") else "failed"

        smart_naming_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "smart_naming_route_unavailable"}
        if smart_naming_route_response is not None:
            _status_code, smart_naming_payload = smart_naming_route_response(
                "/api/smart-naming/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        smart_naming_status = "ok" if smart_naming_payload.get("ok") and int(smart_naming_payload.get("name_count") or 0) > 0 else "degraded" if smart_naming_payload.get("ok") else "failed"

        subtitle_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "subtitle_route_unavailable"}
        if subtitle_extraction_route_response is not None:
            _status_code, subtitle_payload = subtitle_extraction_route_response(
                "/api/subtitle/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        subtitle_status = "ok" if subtitle_payload.get("ok") and not subtitle_payload.get("degraded") else "degraded" if subtitle_payload.get("ok") else "failed"

        document_rag_payload: dict = {"ok": False, "degraded": True, "degraded_reason": "document_rag_route_unavailable"}
        if document_rag_route_response is not None:
            _status_code, document_rag_payload = document_rag_route_response(
                "/api/document-rag/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        document_rag_status = "ok" if document_rag_payload.get("ok") and not document_rag_payload.get("degraded") else "degraded" if document_rag_payload.get("ok") else "failed"

        jobs_payload: dict = {"ok": False}
        if product_jobs_route_response is not None:
            _status_code, jobs_payload = product_jobs_route_response(
                "/api/jobs/status",
                method="GET",
                report_root=self.report_root,
                personal_root=self.personal_root,
            )
        jobs_status = "ok" if jobs_payload.get("ok") else "failed"

        media_stats = self.media_status_payload() if self.media_center else {}
        backup_stats = self.backup_manager.stats() if self.backup_manager else {}
        snapshot_stats = self.snapshot_store.stats() if self.snapshot_store else {}
        ops_stats = self.ops_manager.stats() if self.ops_manager else {}
        audit_payload = self.audit_summary_payload()

        production_ready = readiness.get("verdict") == "ready_ai_nas_production_readiness_gate"
        modules = {
            "gateway": self._module_card("gateway", "ok" if self.product_enabled() else "failed", evidence=self._report_ref("operator_portal_contract.json")),
            "qwen": self._module_card("qwen", qwen_status, metrics={"health_status": qwen_health.get("status"), "model": (qwen_health.get("payload") or {}).get("model")}),
            "harness": self._module_card(
                "harness",
                harness_status,
                metrics={
                    "copy_execute_enabled": harness_payload.get("copy_execute_enabled"),
                    "qwen_execution_authority": harness_payload.get("qwen_execution_authority"),
                    "cloud_private_raw_egress": harness_payload.get("cloud_private_raw_egress"),
                },
            ),
            "router": self._module_card("router", "ok" if edge_router.get("found") else "degraded", evidence=edge_router),
            "multimodal": self._module_card(
                "multimodal",
                multimodal_status,
                metrics={
                    "indexed_count": multimodal_payload.get("indexed_count"),
                    "embedding_count": multimodal_payload.get("embedding_count"),
                    "cloud_used": multimodal_payload.get("cloud_used"),
                    "private_leak_count": multimodal_payload.get("private_leak_count"),
                },
                reason=multimodal_payload.get("degraded_reason"),
            ),
            "yolo": self._module_card(
                "yolo",
                yolo_status,
                metrics={
                    "runtime_target": (yolo_payload.get("backend") or {}).get("runtime_target"),
                    "indexed_count": yolo_payload.get("indexed_count"),
                    "detection_count": yolo_payload.get("detection_count"),
                    "keyframe_count": yolo_payload.get("keyframe_count"),
                    "cloud_used": yolo_payload.get("cloud_used"),
                    "raw_path_rows": yolo_payload.get("raw_path_rows"),
                },
                reason=yolo_payload.get("degraded_reason"),
            ),
            "person_attribute": self._module_card(
                "person_attribute",
                person_status,
                metrics={
                    "person_detection_count": person_payload.get("person_detection_count"),
                    "attribute_count": person_payload.get("attribute_count"),
                    "video_keyframe_count": person_payload.get("video_keyframe_count"),
                    "cloud_used": person_payload.get("cloud_used"),
                    "raw_path_returned": person_payload.get("raw_path_returned"),
                },
                reason=person_payload.get("degraded_reason"),
            ),
            "ai_space": self._module_card(
                "ai_space",
                ai_space_status,
                metrics={
                    "asset_count": ai_space_payload.get("asset_count"),
                    "evidence_count": ai_space_payload.get("evidence_count"),
                    "cloud_used": ai_space_payload.get("cloud_used"),
                    "raw_path_returned": ai_space_payload.get("raw_path_returned"),
                },
                reason=ai_space_payload.get("degraded_reason"),
            ),
            "auto_organizer": self._module_card(
                "auto_organizer",
                auto_organizer_status,
                metrics={
                    "controlled_move_enabled": auto_organizer_payload.get("controlled_move_enabled"),
                    "controlled_rename_enabled": auto_organizer_payload.get("controlled_rename_enabled"),
                    "uncontrolled_move_enabled": auto_organizer_payload.get("uncontrolled_move_enabled"),
                    "uncontrolled_rename_enabled": auto_organizer_payload.get("uncontrolled_rename_enabled"),
                    "delete_enabled": auto_organizer_payload.get("delete_enabled"),
                    "overwrite_enabled": auto_organizer_payload.get("overwrite_enabled"),
                    "rollback_required": auto_organizer_payload.get("rollback_required"),
                    "plan_count": auto_organizer_payload.get("plan_count"),
                    "fallback_default_blocked": auto_organizer_payload.get("fallback_default_blocked"),
                    "last_ai_driven_plan": auto_organizer_payload.get("last_ai_driven_plan"),
                    "last_fallback_blocker": auto_organizer_payload.get("last_fallback_blocker"),
                    "last_rollback_status": auto_organizer_payload.get("last_rollback_status"),
                },
                reason=auto_organizer_payload.get("degraded_reason"),
            ),
            "assistant_trace": self._module_card(
                "assistant_trace",
                assistant_trace_status,
                metrics={
                    "trace_count_visible": assistant_trace_payload.get("trace_count_visible"),
                    "non_synthetic_trace_count": assistant_trace_payload.get("non_synthetic_trace_count"),
                    "last_trace_id": assistant_trace_payload.get("last_trace_id"),
                    "last_entrypoint": assistant_trace_payload.get("last_entrypoint"),
                    "required_steps": assistant_trace_payload.get("required_steps"),
                    "hidden_chain_of_thought_saved": assistant_trace_payload.get("hidden_chain_of_thought_saved"),
                    "raw_path_returned": assistant_trace_payload.get("raw_path_returned"),
                    "cloud_private_raw_egress": assistant_trace_payload.get("cloud_private_raw_egress"),
                    "qwen_execution_authority": assistant_trace_payload.get("qwen_execution_authority"),
                },
                reason=assistant_trace_payload.get("degraded_reason"),
            ),
            "smart_classification": self._module_card(
                "smart_classification",
                smart_status,
                metrics={
                    "category_count": smart_payload.get("category_count"),
                    "membership_count": smart_payload.get("membership_count"),
                    "hit_category_count": smart_payload.get("hit_category_count"),
                    "smart_name_count": smart_payload.get("smart_name_count"),
                    "physical_file_moved": smart_payload.get("physical_file_moved"),
                },
                reason=smart_payload.get("degraded_reason"),
            ),
            "smart_naming": self._module_card(
                "smart_naming",
                smart_naming_status,
                metrics={
                    "name_count": smart_naming_payload.get("name_count"),
                    "physical_file_renamed": smart_naming_payload.get("physical_file_renamed"),
                    "cloud_used": smart_naming_payload.get("cloud_used"),
                },
                reason=smart_naming_payload.get("degraded_reason"),
            ),
            "subtitle": self._module_card(
                "subtitle",
                subtitle_status,
                metrics={
                    "transcript_count": subtitle_payload.get("transcript_count"),
                    "segment_count": subtitle_payload.get("segment_count"),
                    "cloud_used": subtitle_payload.get("cloud_used"),
                    "fixture_only_for_ci": subtitle_payload.get("fixture_only_for_ci"),
                },
                reason=subtitle_payload.get("degraded_reason"),
            ),
            "job_queue": self._module_card("job_queue", jobs_status, metrics={"counts": jobs_payload.get("counts")}),
            "ocr_rag": self._module_card(
                "ocr_rag",
                document_rag_status,
                metrics={
                    "document_count": document_rag_payload.get("document_count"),
                    "chunk_count": document_rag_payload.get("chunk_count"),
                    "retrieval_mode": document_rag_payload.get("retrieval_mode"),
                    "cloud_ocr_enabled": document_rag_payload.get("cloud_ocr_enabled"),
                    "raw_private_content_returned": document_rag_payload.get("raw_private_content_returned"),
                },
                reason=document_rag_payload.get("degraded_reason"),
            ),
            "ocr": self._module_card("ocr", "ok" if ocr_runtime.get("found") else "degraded", evidence=ocr_runtime),
            "documents": self._module_card("documents", "ok" if document_pipeline.get("found") else "degraded", evidence=document_pipeline),
            "media": self._module_card("media", "ok" if int(media_stats.get("photo_count") or 0) > 0 else "degraded", metrics=media_stats),
            "photos": self._module_card("photos", "ok" if int(media_stats.get("photo_count") or 0) > 0 else "degraded", metrics={"photo_count": media_stats.get("photo_count")}, evidence=photo_pipeline),
            "copy_plan": self._module_card("copy_plan", "ok" if copy_governance.get("found") else "degraded", evidence=copy_governance),
            "backup": self._module_card("backup", "ok", metrics=backup_stats, evidence=backup_gate),
            "snapshot": self._module_card("snapshot", "ok", metrics=snapshot_stats, evidence=snapshot_gate),
            "journal": self._module_card("journal", "ok" if journal_route_response is not None else "degraded", evidence=journal_deploy),
            "ops": self._module_card("ops", "ok", metrics=ops_stats, evidence=ops_gate),
            "audit": self._module_card("audit", "ok" if audit_payload.get("ok") else "degraded", metrics={"operation_count": len(audit_payload.get("operations") or [])}),
        }
        failed = [name for name, card in modules.items() if card.get("status") == "failed"]
        degraded = [name for name, card in modules.items() if card.get("status") == "degraded"]
        overall_status = "failed" if failed else "ok"
        return {
            "ok": not failed,
            "schema": "digua_product_status_v1",
            "generated_at": iso_timestamp(),
            "overall": {
                "status": overall_status,
                "production_ready": production_ready,
                "readiness_verdict": readiness.get("verdict"),
                "failed_modules": failed,
                "degraded_modules": degraded,
                "warning_count": len(degraded),
            },
            "modules": modules,
            "gates": {
                "production_readiness": readiness,
                "edge_cloud_router": edge_router,
                "ocr_runtime": ocr_runtime,
                "document_pipeline": document_pipeline,
                "photo_pipeline": photo_pipeline,
                "copy_governance": copy_governance,
            },
            "privacy_boundary": {
                "cloud_private_raw_egress": bool(harness_payload.get("cloud_private_raw_egress")),
                "qwen_execution_authority": bool(harness_payload.get("qwen_execution_authority")),
                "cloud_vision_enabled": bool(multimodal_payload.get("feature_flags", {}).get("cloud_vision_enabled")),
                "cloud_asr_enabled": bool(subtitle_payload.get("cloud_used")),
                "face_identification_enabled": bool(person_payload.get("face_identification_enabled")),
                "biometric_recognition_enabled": bool(person_payload.get("biometric_recognition_enabled")),
                "sensitive_attribute_inference_enabled": bool(person_payload.get("sensitive_attribute_inference_enabled")),
                "raw_path_returned": False,
                "product_status_exposes_absolute_paths": False,
                "controlled_move_rename_boundary": {
                    "controlled_move_enabled": bool(auto_organizer_payload.get("controlled_move_enabled")),
                    "controlled_rename_enabled": bool(auto_organizer_payload.get("controlled_rename_enabled")),
                    "uncontrolled_move_enabled": False,
                    "uncontrolled_rename_enabled": False,
                    "auto_organizer_required": True,
                    "delete_enabled": False,
                    "overwrite_enabled": False,
                },
            },
        }

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

    def send_security_headers(self, *, strict_script_policy: bool = False) -> None:
        script_src = "'self'" if strict_script_policy else "'self' 'unsafe-inline'"
        self.send_header(
            "Content-Security-Policy",
            f"default-src 'self'; script-src {script_src}; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_acl_filtered_json(self, payload: dict, status: int, user: dict) -> None:
        filtered = self.state.filter_index_payload(payload, user)
        if status == HTTPStatus.OK and filtered.get("error") == "not_found":
            status = HTTPStatus.NOT_FOUND
        self.send_json(filtered, status)

    def send_text(self, text: str, content_type: str, status: int = HTTPStatus.OK) -> None:
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        strict_script_policy = urlparse(self.path).path in {
            "/ui",
            "/ui/index.html",
            "/ai-album",
            "/multimodal-search",
            "/multimodal-search/",
            "/ai-space",
            "/ai-space/",
            "/auto-organizer",
            "/auto-organizer/",
            "/smart-classification",
            "/smart-classification/",
            "/subtitle-extraction",
            "/subtitle-extraction/",
            "/journal",
        }
        self.send_security_headers(strict_script_policy=strict_script_policy)
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
        try:
            content_length = path.stat().st_size
        except OSError as exc:
            self.send_json({"ok": False, "error": f"file_stat_failed:{type(exc).__name__}:{exc}"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        fallback_name = "download" + (path.suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,12}", path.suffix or "") else "")
        encoded_name = quote(path.name, safe="")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
        self.send_header("Content-Length", str(content_length))
        disposition = "inline" if preview else "attachment"
        self.send_header("Content-Disposition", f"{disposition}; filename=\"{fallback_name}\"; filename*=UTF-8''{encoded_name}")
        self.end_headers()
        try:
            with path.open("rb") as source:
                while chunk := source.read(STREAM_CHUNK_BYTES):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            return

    def send_portal_html(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.send_json({"ok": False, "error": f"read_failed:{type(exc).__name__}:{exc}", "path": str(path)}, HTTPStatus.NOT_FOUND)
            return
        self.send_text(inject_runtime_sections(text, self.state.latest_bundle()), "text/html; charset=utf-8")

    def read_json_body(self) -> tuple[int | None, dict | None]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_content_length"}
        if length < 0:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_content_length"}
        if length > MAX_JSON_BODY_BYTES:
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {
                "ok": False,
                "error": "request_too_large",
                "max_payload_bytes": MAX_JSON_BODY_BYTES,
            }
        raw = self.rfile.read(length)
        if len(raw) != length:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "request_body_truncated"}
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid_json:{exc}"}
        if not isinstance(payload, dict):
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "json_object_required"}
        return None, payload

    def require_product(self) -> bool:
        if not self.state.product_enabled():
            self.send_json({"ok": False, "error": "nas_product_api_not_configured"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return False
        return True

    def authenticated_product_user(self, *, admin: bool = False) -> dict | None:
        if not self.require_product():
            return None
        checker = self.state.require_admin if admin else self.state.require_user
        status, error, user = checker(self.headers.get("Authorization"))
        if status:
            self.send_json(error or {}, status)
            return None
        return user or {}

    def authorize_index_mutation(self, route: str, user: dict) -> bool:
        admin_routes = {
            "/api/agent-runtime/memory/record",
            "/api/agent-runtime/multimodal-index/scan",
            "/api/multimodal-index/rebuild",
            "/api/multimodal-search/eval/run",
            "/api/yolo-index/rebuild",
            "/api/yolo-index/eval/run",
            "/api/person-attribute/rebuild",
            "/api/ai-album/rebuild",
            "/api/ai-space/rebuild",
            "/api/smart-classification/rebuild",
        }
        if route not in admin_routes or str(user.get("role") or "") == "admin":
            return True
        self.send_json({"ok": False, "error": "admin_required", "route": route}, HTTPStatus.FORBIDDEN)
        return False

    def token_budget_api(self):
        if TokenBudgetIntegration is None:
            self.send_json({"ok": False, "error": "token_budget_integration_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return None
        try:
            return TokenBudgetIntegration()
        except Exception as exc:
            self.send_json({"ok": False, "error": f"token_budget_init_failed:{type(exc).__name__}:{exc}"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return None

    def query_payload(self) -> dict:
        params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        return {key: values[-1] for key, values in params.items()}

    def record_assistant_entrypoint(self, entrypoint: str, query: str, session_id: str = "demo") -> str | None:
        recorder = self.assistant_trace_recorder()
        if recorder is not None and AssistantTraceContext is not None:
            privacy_spans = self.assistant_privacy_spans(query, {})
            private = bool(privacy_spans)
            ctx = AssistantTraceContext(recorder, entrypoint=entrypoint, query=query, session_id=session_id)
            ctx.record_router_decision({"qwen_touched": True, "entrypoint": entrypoint, "qwen_execution_authority": False})
            ctx.record_privacy_spans({"privacy_spans": privacy_spans, "privacy_level": "high" if private else "medium", "cloud_private_egress": False})
            ctx.record_task_classifier({"task_type": entrypoint, "task_complexity": "simple"})
            ctx.record_route_decision({"route": "private_local_only" if private else "local_only", "cloud_allowed": not private, "cloud_used": False})
            ctx.record_token_budget({"estimated_input_tokens": max(1, len(query) // 3), "budget_policy": "local_first"})
            ctx.record_tool_call(entrypoint, {"query_hash": hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest()}, {"status": "completed", "entrypoint": entrypoint})
            ctx.record_safety_gate({"delete_enabled": False, "overwrite_enabled": False, "raw_path_returned": False, "hidden_chain_of_thought_saved": False})
            ctx.record_evidence({"evidence_refs": [f"trace:{entrypoint}"], "raw_private_content_logged": False})
            ctx.finish({"answer_redacted": "entrypoint trace completed", "hidden_chain_of_thought_exposed": False})
            return ctx.trace_id
        if assistant_trace_route_response is None:
            return None
        try:
            status_code, trace = assistant_trace_route_response(
                "/api/assistant/trace/record-entrypoint",
                method="POST",
                payload={"entrypoint": entrypoint, "query": query, "session_id": session_id},
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
        except Exception:
            return None
        if status_code >= 400 or not isinstance(trace, dict):
            return None
        return ((trace.get("trace") or {}).get("trace_id") if isinstance(trace.get("trace"), dict) else None)

    def assistant_trace_recorder(self):
        if AssistantTraceRecorder is None:
            return None
        return AssistantTraceRecorder(db_path=self.state.report_root / "assistant_trace" / "runtime" / "assistant_trace.db")

    def send_assistant_chat(self, payload: dict, user: dict) -> None:
        query = str(payload.get("query") or payload.get("message") or "")
        if not query.strip():
            self.send_json({"ok": False, "error": "query_required", "raw_path_returned": False}, HTTPStatus.BAD_REQUEST)
            return
        session_id = str(payload.get("session_id") or "demo3")
        entrypoint = str(payload.get("entrypoint") or "assistant_chat")
        action_intent = infer_copilot_action_intent(query)
        router = self.state.copilot_qwen_route(query, action_intent)
        task_type = self.assistant_task_type(query, action_intent, router)
        privacy_spans = self.assistant_privacy_spans(query, router)
        privacy_level = self.assistant_privacy_level(task_type, privacy_spans, router)
        task_complexity = "complex" if task_type in {"private_document_query", "public_complex_query"} else "simple"
        route = self.assistant_route_label(task_type, privacy_level, router)
        token_result = self.assistant_token_budget(query, task_type, privacy_spans, task_complexity)
        tool_result = self.assistant_tool_execution(query, task_type, router, action_intent, user)
        answer = self.assistant_answer(query, task_type, tool_result, route)
        token_counts = token_result.get("token_counts") if isinstance(token_result.get("token_counts"), dict) else {}
        before_tokens = int(token_counts.get("naive_cloud_payload_tokens") or 0)
        after_tokens = int(token_counts.get("optimized_cloud_payload_tokens") or token_counts.get("redacted_payload_tokens") or 0)
        reduction_ratio = float(token_counts.get("reduction_ratio") or 0.0)
        redaction_applied = bool((token_result.get("redaction_count") or 0) or route == "cloud_allowed_redacted")
        cloud_used = bool(tool_result.get("cloud_used"))
        cloud_stub = bool(tool_result.get("cloud_stub"))
        real_cloud_call = bool(tool_result.get("real_cloud_call"))
        cloud_allowed = route == "cloud_allowed_redacted" and privacy_level == "none"
        evidence_refs = [str(item) for item in tool_result.get("evidence_refs") or []][:20]
        safe_router = self.state._redact_paths(dict(router))
        safe_tool = self.state._redact_paths(dict(tool_result))
        recorder = self.assistant_trace_recorder()
        trace_id = None
        steps: list[str] = []
        step_payloads = {
            "qwen_router": {
                "qwen_touched": True,
                "router_output": safe_router,
                "qwen_execution_authority": False,
            },
            "privacy_tokenizer": {
                "privacy_spans": privacy_spans,
                "privacy_level": privacy_level,
                "redaction_count": token_result.get("redaction_count"),
                "redaction_map_included": False,
                "cloud_private_egress": False,
            },
            "task_classifier": {
                "task_type": task_type,
                "task_complexity": task_complexity,
                "action_intent": self.state._redact_paths(action_intent) if isinstance(action_intent, dict) else action_intent,
            },
            "route_decision": {
                "route": route,
                "cloud_allowed": cloud_allowed,
                "cloud_used": cloud_used,
                "cloud_stub": cloud_stub,
                "real_cloud_call": real_cloud_call,
            },
            "token_budget": {
                "run_id": token_result.get("run_id"),
                "before_tokens": before_tokens,
                "after_tokens": after_tokens,
                "reduction_ratio": reduction_ratio,
                "token_counts": token_counts,
                "redaction_applied": redaction_applied,
                "cloud_payload_contains_private_context": False,
            },
            "tool_execution": {
                "tool": tool_result.get("tool_execution"),
                "status": tool_result.get("status"),
                "result_count": tool_result.get("result_count"),
                "no_grounded_answer": tool_result.get("no_grounded_answer"),
                "evidence_refs": evidence_refs,
                "result": safe_tool,
                "qwen_execution_authority": False,
            },
            "safety_gate": {
                "delete_enabled": False,
                "overwrite_enabled": False,
                "uncontrolled_move_enabled": False,
                "raw_private_cloud_egress": False,
                "raw_path_returned": False,
                "hidden_chain_of_thought_saved": False,
            },
            "evidence_summary": {
                "evidence_refs": evidence_refs,
                "raw_private_content_logged": False,
                "raw_path_returned": False,
            },
            "final_answer": {
                "answer_redacted": answer,
                "hidden_chain_of_thought_exposed": False,
            },
        }
        if recorder is not None:
            if AssistantTraceContext is not None:
                ctx = AssistantTraceContext(recorder, entrypoint=entrypoint, query=query, session_id=session_id)
                ctx.record_router_decision(step_payloads["qwen_router"])
                ctx.record_privacy_spans(step_payloads["privacy_tokenizer"])
                ctx.record_task_classifier(step_payloads["task_classifier"])
                ctx.record_route_decision(step_payloads["route_decision"])
                ctx.record_token_budget(step_payloads["token_budget"])
                ctx.record_tool_call(
                    str(tool_result.get("tool_execution") or task_type),
                    {"query_hash": hashlib.sha256(query.encode("utf-8", errors="replace")).hexdigest(), "task_type": task_type},
                    step_payloads["tool_execution"],
                )
                ctx.record_safety_gate(step_payloads["safety_gate"])
                ctx.record_evidence(step_payloads["evidence_summary"])
                ctx.finish(step_payloads["final_answer"])
                trace = recorder.get_trace(ctx.trace_id)
            else:
                trace = recorder.record_execution_trace(entrypoint=entrypoint, query=query, session_id=session_id, step_payloads=step_payloads)
            trace_id = (trace.get("trace") or {}).get("trace_id") if isinstance(trace.get("trace"), dict) else None
            steps = [str(step.get("step_name")) for step in trace.get("steps") or []]
        response = {
            "ok": True,
            "schema": "digua_assistant_chat_v2",
            "trace_id": trace_id,
            "answer_redacted": answer,
            "qwen_touched": True,
            "task_type": task_type,
            "task_complexity": task_complexity,
            "privacy_spans": privacy_spans,
            "privacy_level": privacy_level,
            "route": route,
            "cloud_allowed": cloud_allowed,
            "cloud_used": cloud_used,
            "cloud_stub": cloud_stub,
            "real_cloud_call": real_cloud_call,
            "raw_private_cloud_egress": False,
            "redaction_applied": redaction_applied,
            "before_tokens": before_tokens,
            "after_tokens": after_tokens,
            "reduction_ratio": reduction_ratio,
            "cloud_payload_contains_private_context": False,
            "tool_execution": tool_result.get("tool_execution"),
            "tool_status": tool_result.get("status"),
            "evidence_refs": evidence_refs,
            "no_grounded_answer": bool(tool_result.get("no_grounded_answer")),
            "steps": steps,
            "hidden_chain_of_thought_saved": False,
            "qwen_execution_authority": False,
            "raw_path_returned": False,
        }
        self.send_json(self.state._redact_paths(response))

    def assistant_task_type(self, query: str, action_intent: dict | None, router: dict) -> str:
        text = str(query or "").lower()
        if any(term in text for term in ["发票", "合同", "金额", "invoice", "contract", "amount"]):
            return "private_document_query"
        if ("公开" in query or "public" in text) and any(term in query for term in ["趋势", "比较", "发展"]):
            return "public_complex_query"
        if any(term in query for term in ["照片", "相册", "上传"]) or any(term in text for term in ["photo", "album", "upload"]):
            return "media_search"
        if isinstance(action_intent, dict) and action_intent.get("action") == "search":
            return "media_search"
        return str(router.get("local_tool_id") or "local_chat")

    def assistant_privacy_spans(self, query: str, router: dict) -> list[str]:
        text = str(query or "").lower()
        spans: list[str] = []
        for marker, label in [
            ("invoice", "invoice"),
            ("发票", "invoice"),
            ("contract", "contract"),
            ("合同", "contract"),
            ("amount", "amount"),
            ("金额", "amount"),
            ("family", "private_nas_context"),
            ("家庭", "private_nas_context"),
            ("personal/", "private_nas_context"),
            ("/mnt/nas/", "private_nas_context"),
        ]:
            if marker in text and label not in spans:
                spans.append(label)
        if router.get("privacy_level") == "high" and "private_nas_context" not in spans:
            spans.append("private_nas_context")
        return spans

    @staticmethod
    def assistant_privacy_level(task_type: str, privacy_spans: list[str], router: dict) -> str:
        if privacy_spans or task_type == "private_document_query":
            return "high"
        if task_type == "public_complex_query":
            return "none"
        return "medium"

    @staticmethod
    def assistant_route_label(task_type: str, privacy_level: str, router: dict) -> str:
        if privacy_level == "high":
            return "private_local_only"
        if task_type == "public_complex_query":
            return "cloud_allowed_redacted"
        return "local_only"

    def assistant_token_budget(self, query: str, task_type: str, privacy_spans: list[str], task_complexity: str) -> dict:
        if TokenBudgetIntegration is None:
            return {"ok": False, "error": "token_budget_unavailable", "token_counts": {}}
        try:
            api = TokenBudgetIntegration()
            return api.estimate(
                {
                    "query": query,
                    "task_type": task_type,
                    "category": task_type,
                    "workspace": "openclaw_assistant",
                    "private_markers": privacy_spans,
                    "sensitivity": "high" if privacy_spans else "",
                    "complexity": task_complexity,
                },
                record_trace=True,
            )
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}:{exc}", "token_counts": {}}

    def assistant_tool_execution(self, query: str, task_type: str, router: dict, action_intent: dict | None, user: dict) -> dict:
        if task_type == "media_search":
            if ai_space_route_response is None:
                return {"tool_execution": "local_media_search", "status": "unavailable", "result_count": 0, "cloud_used": False}
            status_code, result = ai_space_route_response(
                "/api/ai-space/search",
                method="POST",
                payload={"query": query, "top_k": 8},
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            results = result.get("results") if isinstance(result.get("results"), list) else []
            return {
                "tool_execution": "local_media_search",
                "status": "completed" if status_code == HTTPStatus.OK and result.get("ok") else "failed",
                "result_count": len(results),
                "evidence_refs": [ref for item in results for ref in (item.get("evidence_refs") or [])][:20],
                "cloud_used": False,
                "raw_path_returned": False,
            }
        if task_type == "private_document_query":
            status_code, result = self.state.document_query_payload(query, "Documents", user)
            evidence_refs = [str(item) for item in result.get("evidence_refs") or []]
            return {
                "tool_execution": "local_document_rag",
                "status": "completed" if status_code == HTTPStatus.OK else "failed",
                "result_count": int(result.get("evidence_count") or 0),
                "evidence_refs": evidence_refs,
                "no_grounded_answer": int(result.get("evidence_count") or 0) == 0,
                "cloud_used": False,
                "raw_private_content_returned": False,
                "raw_path_returned": False,
            }
        if task_type == "public_complex_query":
            status_code, result = self.state._copilot_cloud_overflow(query, {}, router)
            return {
                "tool_execution": "controlled_cloud_overflow",
                "status": "completed" if status_code == HTTPStatus.OK and result.get("ok") else "stub_or_failed",
                "result_count": 1 if result.get("ok") else 0,
                "evidence_refs": ["router:cloud_overflow"],
                "cloud_used": bool(result.get("cloud_used")),
                "cloud_stub": not bool(result.get("cloud_used")),
                "real_cloud_call": bool(result.get("cloud_used")),
                "cloud_available": result.get("cloud_available"),
                "raw_path_returned": False,
            }
        status_code, result = self.state.local_qwen_chat(query, {})
        return {
            "tool_execution": "local_qwen_chat",
            "status": "completed" if status_code == HTTPStatus.OK and result.get("ok") else "failed",
            "result_count": 1 if result.get("ok") else 0,
            "evidence_refs": ["qwen:local_chat"],
            "cloud_used": False,
            "raw_path_returned": False,
        }

    @staticmethod
    def assistant_answer(query: str, task_type: str, tool_result: dict, route: str) -> str:
        if task_type == "media_search":
            return f"已通过本地媒体/AI Space 索引检索，返回 {int(tool_result.get('result_count') or 0)} 条匹配结果。"
        if task_type == "private_document_query":
            if tool_result.get("no_grounded_answer"):
                return "本地文档 RAG 没有找到足够证据，已拒绝强答。"
            return f"已在本地文档 RAG 中找到 {int(tool_result.get('result_count') or 0)} 条证据，未发送私有内容到云端。"
        if task_type == "public_complex_query":
            return "公开复杂任务已完成本地 Qwen 路由、隐私分词和 token 预算；当前按受控云端边界返回。"
        return "已由本地 Qwen/本地工具链处理。"

    def send_assistant_trace_response(self, method: str, route: str, payload: dict | None = None) -> None:
        if assistant_trace_route_response is None:
            self.send_json({"ok": False, "error": "assistant_trace_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        status_code, result = assistant_trace_route_response(
            route,
            method=method,
            payload=payload or {},
            report_root=self.state.report_root,
            personal_root=self.state.personal_root,
        )
        self.send_json(result, status_code)

    def send_router_explain(self, payload: dict) -> None:
        query = str(payload.get("query") or payload.get("message") or payload.get("q") or "")
        if not query:
            self.send_json({"ok": False, "error": "query_required", "raw_path_returned": False}, HTTPStatus.BAD_REQUEST)
            return
        action_intent = infer_copilot_action_intent(query)
        router = self.state.copilot_qwen_route(query, action_intent)
        redacted_query, redaction_count = redact_private_text(query)
        redacted_query = _router_debug_redact(str(redacted_query))
        safe_router = self.state._redact_paths(dict(router))
        safe_router.pop("raw_content_preview", None)
        safe_action = self.state._redact_paths(action_intent) if isinstance(action_intent, dict) else action_intent
        trace_id = self.record_assistant_entrypoint("router_explain", query, session_id=str(payload.get("session_id") or "demo3"))
        result = {
            "ok": True,
            "schema": "digua_router_explain_v1",
            "trace_id": trace_id,
            "query_redacted": str(redacted_query)[:240],
            "redaction_count": int(redaction_count or 0),
            "qwen_touched": True,
            "route_decision": safe_router,
            "action_intent": safe_action,
            "cloud_private_raw_egress": False,
            "qwen_execution_authority": False,
            "raw_path_returned": False,
        }
        self.send_json(self.state._redact_paths(result))

    def send_token_budget_explain(self, payload: dict) -> None:
        api = self.token_budget_api()
        if api is None:
            return
        query = str(payload.get("query") or payload.get("message") or payload.get("prompt") or "")
        request_payload = dict(payload)
        request_payload.setdefault("query", query)
        request_payload.setdefault("case_id", f"explain_{hashlib.sha256(query.encode('utf-8', errors='replace')).hexdigest()[:12]}")
        result = api.estimate(request_payload, record_trace=True)
        trace_id = self.record_assistant_entrypoint("token_budget_explain", query, session_id=str(payload.get("session_id") or "demo3"))
        safe = {
            "ok": bool(result.get("ok")),
            "schema": "digua_token_budget_explain_v1",
            "trace_id": trace_id,
            "run_id": result.get("run_id"),
            "case_id": result.get("case_id"),
            "route": result.get("route"),
            "route_reason": result.get("route_reason"),
            "cloud_allowed": result.get("cloud_allowed"),
            "cloud_call_avoided": result.get("cloud_call_avoided"),
            "token_counts": result.get("token_counts"),
            "redaction_count": result.get("redaction_count"),
            "private_leak_count": result.get("private_leak_count"),
            "redaction_map_included": False,
            "raw_path_returned": False,
            "cloud_private_raw_egress": False,
            "qwen_execution_authority": False,
        }
        self.send_json(self.state._redact_paths(safe), HTTPStatus.OK if safe["ok"] else HTTPStatus.BAD_REQUEST)

    def send_privacy_tokenizer_debug(self, payload: dict) -> None:
        api = self.token_budget_api()
        if api is None:
            return
        text = str(payload.get("query") or payload.get("message") or payload.get("text") or "")
        redacted = api.redactor.redact(text)
        marker_hashes = [hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12] for value in redacted.redaction_map.values()]
        trace_id = self.record_assistant_entrypoint("privacy_tokenizer_debug", text, session_id=str(payload.get("session_id") or "demo3"))
        safe = {
            "ok": True,
            "schema": "digua_privacy_tokenizer_debug_v1",
            "trace_id": trace_id,
            "redacted_preview": redacted.redacted_text[:240],
            "redaction_count": redacted.redaction_count,
            "privacy_span_hashes": marker_hashes[:50],
            "redaction_map_included": False,
            "raw_path_returned": False,
            "cloud_private_raw_egress": False,
            "qwen_execution_authority": False,
        }
        self.send_json(self.state._redact_paths(safe))

    def send_ocr_status(self) -> None:
        if document_rag_route_response is not None:
            _status, payload = document_rag_route_response(
                "/api/ocr/status",
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(payload)
            return
        ocr_runtime = self.state._report_ref("ocr_runtime_contract.json")
        document_pipeline = self.state._report_ref("document_pipeline_acceptance.json")
        self.send_json(
            {
                "ok": True,
                "schema": "digua_ocr_status_v1",
                "route_module": "portal_embedded_fallback",
                "ocr_runtime": ocr_runtime,
                "document_pipeline": document_pipeline,
                "cloud_ocr_enabled": False,
                "cloud_used": False,
                "raw_private_content_returned": False,
                "raw_path_returned": False,
            }
        )

    def send_document_rag_or_ocr_query(self, payload: dict, user: dict, *, mode: str) -> None:
        query = str(payload.get("query") or payload.get("message") or "")
        path = str(payload.get("path") or "Documents")
        status_code, result = self.state.document_query_payload(query, path, user)
        evidence = result.get("evidence") if isinstance(result.get("evidence"), list) else []
        evidence_refs = [str(item) for item in result.get("evidence_refs") or []]
        no_grounded = status_code != HTTPStatus.OK or not evidence
        response = {
            "ok": not no_grounded,
            "schema": "digua_document_rag_query_v1" if mode == "document_rag" else "digua_ocr_query_v1",
            "route_module": "src.openclaw.routes.document_rag_routes",
            "mode": mode,
            "answer": "" if no_grounded else result.get("answer"),
            "evidence_refs": [] if no_grounded else evidence_refs,
            "retrieved_chunks": [] if no_grounded else self.state._redact_paths(evidence[:10]),
            "no_grounded_answer": bool(no_grounded),
            "retrieval_mode": result.get("retrieval_mode") or "sqlite_fts_first",
            "cloud_ocr_enabled": False,
            "cloud_used": False,
            "raw_private_content_returned": False,
            "raw_path_returned": False,
        }
        if no_grounded:
            response["error"] = result.get("error") or "no_grounded_answer"
        self.send_json(self.state._redact_paths(response), HTTPStatus.OK if response["ok"] else HTTPStatus.NOT_FOUND)

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
        if route in {"/ui", "/ui/index.html", "/ai-album"}:
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
        if route in {"/ai-space", "/ai-space/"}:
            self.send_file_text(REPO_ROOT / "web" / "templates" / "ai_space.html", "text/html; charset=utf-8")
            return
        if route == "/static/ai_space.css":
            self.send_file_text(REPO_ROOT / "web" / "static" / "ai_space.css", "text/css; charset=utf-8")
            return
        if route == "/static/ai_space.js":
            self.send_file_text(REPO_ROOT / "web" / "static" / "ai_space.js", "application/javascript; charset=utf-8")
            return
        if route in {"/auto-organizer", "/auto-organizer/"}:
            self.send_file_text(REPO_ROOT / "web" / "templates" / "auto_organizer.html", "text/html; charset=utf-8")
            return
        if route == "/static/auto_organizer.css":
            self.send_file_text(REPO_ROOT / "web" / "static" / "auto_organizer.css", "text/css; charset=utf-8")
            return
        if route == "/static/auto_organizer.js":
            self.send_file_text(REPO_ROOT / "web" / "static" / "auto_organizer.js", "application/javascript; charset=utf-8")
            return
        if route in {"/smart-classification", "/smart-classification/"}:
            self.send_file_text(REPO_ROOT / "web" / "templates" / "smart_classification.html", "text/html; charset=utf-8")
            return
        if route == "/static/smart_classification.css":
            self.send_file_text(REPO_ROOT / "web" / "static" / "smart_classification.css", "text/css; charset=utf-8")
            return
        if route == "/static/smart_classification.js":
            self.send_file_text(REPO_ROOT / "web" / "static" / "smart_classification.js", "application/javascript; charset=utf-8")
            return
        if route in {"/subtitle-extraction", "/subtitle-extraction/"}:
            self.send_file_text(REPO_ROOT / "web" / "templates" / "subtitle_extraction.html", "text/html; charset=utf-8")
            return
        if route == "/static/subtitle_extraction.css":
            self.send_file_text(REPO_ROOT / "web" / "static" / "subtitle_extraction.css", "text/css; charset=utf-8")
            return
        if route == "/static/subtitle_extraction.js":
            self.send_file_text(REPO_ROOT / "web" / "static" / "subtitle_extraction.js", "application/javascript; charset=utf-8")
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
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            self.send_journal_response("GET", route)
            return
        if route.startswith("/api/") and route != "/api/health":
            user = self.authenticated_product_user()
            if user is None:
                return
        if route == "/api/product/status":
            if not self.require_product():
                return
            self.send_json(self.state._redact_paths(self.state.product_status_payload()))
            return
        if route == "/api/product/evidence/latest":
            if not self.require_product():
                return
            self.send_json(self.state.product_evidence_payload())
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
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
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
        if route == "/api/documents/classification-status":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            status_code, payload = self.state.document_classification_payload((params.get("path") or ["Documents"])[0], user or {})
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
        if route == "/api/storage/trash":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            items = self.state.snapshot_store.list_trash(str((user or {}).get("username") or "")) if self.state.snapshot_store else []
            self.send_json({"ok": True, "schema": "digua_storage_trash_v1", "items": items, "retention_days": 30, "raw_path_returned": False})
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
        if route in {"/api/media/status", "/api/media/photos", "/api/media/timeline", "/api/media/albums", "/api/media/duplicates", "/api/media/summary"}:
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            library_only = str((params.get("scope") or [""])[0] or "").strip().lower() == "library"
            media_payload = self.state.visible_media_payload(user or {}, library_only=library_only)
            if route == "/api/media/status":
                self.send_json({"ok": True, "schema": "digua_media_album_v2", **media_payload["stats"], "cloud_used": False, "local_only": True})
                return
            if route == "/api/media/photos":
                limit = int((params.get("limit") or ["100"])[0] or "100")
                offset = int((params.get("offset") or ["0"])[0] or "0")
                self.send_json({"ok": True, "schema": "digua_media_album_v2", "photos": media_payload["photos"][offset:offset + limit], "raw_path_returned": False})
                return
            if route == "/api/media/timeline":
                self.send_json({"ok": True, "schema": "digua_media_album_v2", "timeline": media_payload["timeline"], "raw_path_returned": False})
                return
            if route == "/api/media/albums":
                self.send_json({"ok": True, "schema": "digua_media_album_v2", "albums": media_payload["albums"], "raw_path_returned": False})
                return
            if route == "/api/media/duplicates":
                self.send_json({"ok": True, "schema": "digua_media_album_v2", "duplicates": media_payload["duplicates"], "raw_path_returned": False})
                return
            summary_photos = media_payload["photos"] if library_only else media_payload["photos"][:24]
            self.send_json({"ok": True, "schema": "digua_media_album_v2", "stats": media_payload["stats"], "albums": media_payload["albums"], "photos": summary_photos, "photo_scope": media_payload["photo_scope"], "raw_path_returned": False})
            return
        if route == "/api/media/album":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            album_name = str((params.get("name") or [""])[0] or "").strip()
            if not album_name:
                self.send_json({"ok": False, "error": "album_name_required", "raw_path_returned": False}, HTTPStatus.BAD_REQUEST)
                return
            media = self.state.media_center
            photos = media.get_album_photos(album_name) if media else []
            scope = self.state.authorized_asset_scope(user or {})
            if scope is not None:
                allowed_ids = scope["asset_ids"]
                photos = [row for row in photos if str(row.get("asset_id") or "") in allowed_ids]
            self.send_json(
                {
                    "ok": True,
                    "schema": "digua_media_album_v2",
                    "album": {"name": album_name},
                    "photos": photos,
                    "count": len(photos),
                    "raw_path_returned": False,
                }
            )
            return
        if route == "/api/media/preview":
            if not self.require_product():
                return
            status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            path_hash_value = str((params.get("path_hash") or [""])[0] or "").strip().lower()
            media = self.state.media_center
            target = media.photo_path_by_hash(path_hash_value) if media else None
            if not target:
                self.send_json({"ok": False, "error": "preview_not_found_or_not_authorized", "raw_path_returned": False}, HTTPStatus.NOT_FOUND)
                return
            try:
                resolved = target.resolve(strict=True)
            except OSError:
                self.send_json({"ok": False, "error": "preview_not_found_or_not_authorized", "raw_path_returned": False}, HTTPStatus.NOT_FOUND)
                return
            allowed, denial_status = self.state.media_preview_access(resolved, user or {})
            if not allowed:
                error_name = "permission_denied" if denial_status == HTTPStatus.FORBIDDEN else "preview_not_found_or_not_authorized"
                self.send_json({"ok": False, "error": error_name, "required": "read", "raw_path_returned": False}, denial_status)
                return
            self.send_storage_file(resolved, preview=True)
            return
        if route == "/api/ai-album/scope":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            self.send_json({k: v for k, v in self.state.ai_album_organizer_scope().items() if k != "root_paths"})
            return
        if route == "/api/ai-album/organize-status":
            if not self.require_product():
                return
            status, error, _user = self.state.require_user(self.headers.get("Authorization"))
            if status:
                self.send_json(error or {}, status)
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            payload = {key: values[-1] for key, values in params.items()}
            status_code, result = self.state.ai_album_organize_status_payload(payload)
            self.send_json(result, status_code)
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
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = agent_runtime_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/multimodal-search") or route.startswith("/api/multimodal-index"):
            if multimodal_route_response is None:
                self.send_json({"ok": False, "error": "multimodal_search_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = multimodal_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/yolo-index"):
            if yolo_route_response is None:
                self.send_json({"ok": False, "error": "yolo_index_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = yolo_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/person-attribute"):
            if person_attribute_route_response is None:
                self.send_json({"ok": False, "error": "person_attribute_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = person_attribute_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/ai-space"):
            if ai_space_route_response is None:
                self.send_json({"ok": False, "error": "ai_space_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = ai_space_route_response(
                route,
                method="GET",
                payload=self.query_payload(),
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/auto-organize"):
            if auto_organizer_route_response is None:
                self.send_json({"ok": False, "error": "auto_organizer_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            params = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            payload = {key: values[-1] for key, values in params.items()}
            status_code, result = auto_organizer_route_response(
                route,
                method="GET",
                payload=payload,
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/smart-classification"):
            if smart_classification_route_response is None:
                self.send_json({"ok": False, "error": "smart_classification_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = smart_classification_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/smart-naming"):
            if smart_naming_route_response is None:
                self.send_json({"ok": False, "error": "smart_naming_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = smart_naming_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/subtitle"):
            if subtitle_extraction_route_response is None:
                self.send_json({"ok": False, "error": "subtitle_extraction_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user()
            if user is None:
                return
            status_code, result = subtitle_extraction_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route.startswith("/api/jobs"):
            if product_jobs_route_response is None:
                self.send_json({"ok": False, "error": "product_jobs_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            user = self.authenticated_product_user(admin=True)
            if user is None:
                return
            status_code, result = product_jobs_route_response(
                route,
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_acl_filtered_json(result, status_code, user)
            return
        if route == "/api/harness/status":
            if harness_status_response is None:
                self.send_json({"ok": False, "error": "harness_default_service_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self.send_json(self.state._redact_paths(harness_status_response(report_root=self.state.report_root, personal_root=self.state.personal_root)))
            return
        if route == "/api/health":
            contract = self.state.portal_contract()
            self.send_json(
                {
                    "ok": bool(contract.get("found")) or self.state.product_enabled(),
                    "tool_id": TOOL_ID,
                    "operator_portal_contract": self.state._redact_paths(report_without_payload(contract)),
                    "portal_html": self.state._redact_paths(str(self.state.portal_html_path())) if self.state.portal_html_path() else None,
                    "refresh_on_start": self.state._redact_paths(self.state.refresh_result),
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
        if route == "/api/router/explain":
            self.send_router_explain(self.query_payload())
            return
        if route == "/api/token-budget/explain":
            self.send_token_budget_explain(self.query_payload())
            return
        if route == "/api/privacy-tokenizer/debug":
            self.send_privacy_tokenizer_debug(self.query_payload())
            return
        if route == "/api/ocr/status":
            self.send_ocr_status()
            return
        if route == "/api/document-rag/status":
            if document_rag_route_response is None:
                self.send_json({"ok": False, "error": "document_rag_routes_unavailable", "raw_path_returned": False}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            _status, payload = document_rag_route_response(
                "/api/document-rag/status",
                method="GET",
                report_root=self.state.report_root,
                personal_root=self.state.personal_root,
            )
            self.send_json(payload)
            return
        if route.startswith("/api/assistant/trace") or route == "/api/assistant/traces":
            self.send_assistant_trace_response("GET", route, self.query_payload())
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
                    "/ai-space",
                    "/auto-organizer",
                    "/smart-classification",
                    "/subtitle-extraction",
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
                    "/api/person-attribute/status",
                    "/api/media/status",
                    "/api/media/photos",
                    "/api/media/timeline",
                    "/api/media/albums",
                    "/api/media/duplicates",
                    "/api/ai-album/scope",
                    "/api/ai-album/organize-status",
                    "/api/ai-space/status",
                    "/api/ai-space/assets",
                    "/api/ai-space/asset/{asset_id}",
                    "/api/ai-space/facets",
                    "/api/auto-organize/status",
                    "/api/auto-organize/recent",
                    "/api/auto-organize/plan/{plan_id}",
                    "/api/smart-classification/status",
                    "/api/smart-classification/categories",
                    "/api/smart-classification/category/{category_id}/items",
                    "/api/smart-naming/status",
                    "/api/smart-naming/item/{asset_id}",
                    "/api/subtitle/status",
                    "/api/subtitle/transcript/{asset_id}",
                    "/api/jobs/status",
                    "/api/jobs/{job_id}",
                    "/api/jobs/recent",
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
                    "/api/storage/trash",
                    "/api/documents/list",
                    "/api/identity/users",
                    "/api/contracts/operator-portal",
                    "/api/token-budget/summary",
                    "/api/token-budget/explain",
                    "/api/token-budget/benchmark-summary",
                    "/api/token-budget/trace/{run_id}",
                    "/api/router/explain",
                    "/api/privacy-tokenizer/debug",
                    "/api/ocr/status",
                    "/api/document-rag/status",
                    "/api/assistant/trace/status",
                    "/api/assistant/trace/{trace_id}",
                    "/api/assistant/trace/stream/{trace_id}",
                    "/api/assistant/traces",
                    "POST /api/identity/create-user",
                    "POST /api/identity/login",
                    "POST /api/storage/create-folder",
                    "POST /api/storage/upload-file",
                    "POST /api/storage/trash",
                    "POST /api/storage/trash/cleanup",
                    "POST /api/documents/query",
                    "POST /api/document-rag/query",
                    "POST /api/ocr/query",
                    "POST /api/ocr/rebuild",
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
                    "POST /api/token-budget/explain",
                    "POST /api/router/explain",
                    "POST /api/privacy-tokenizer/debug",
                    "POST /api/assistant/chat",
                    "POST /api/assistant/trace/record-entrypoint",
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
                    "POST /api/person-attribute/rebuild",
                    "POST /api/person-attribute/search",
                    "POST /api/media/index",
                    "POST /api/media/upload",
                    "POST /api/ai-album/rebuild",
                    "POST /api/ai-album/auto-organize",
                    "POST /api/ai-album/organize-now",
                    "POST /api/ai-space/rebuild",
                    "POST /api/ai-space/search",
                    "POST /api/auto-organize/plan",
                    "POST /api/auto-organize/dry-run",
                    "POST /api/auto-organize/approve",
                    "POST /api/auto-organize/execute",
                    "POST /api/auto-organize/rollback",
                    "POST /api/smart-classification/categories",
                    "POST /api/smart-classification/rebuild",
                    "POST /api/smart-classification/category/{category_id}/materialize-copy-plan",
                    "POST /api/smart-naming/generate",
                    "POST /api/smart-naming/batch-generate",
                    "POST /api/subtitle/extract",
                    "POST /api/subtitle/search",
                    "POST /api/subtitle/summarize",
                    "POST /api/jobs/enqueue",
                    "POST /api/jobs/cancel",
                    "POST /api/journal/manual-entry",
                    "POST /api/journal/generate-summary",
                    "POST /api/journal/export",
                ],
            },
            HTTPStatus.NOT_FOUND,
        )

    def do_POST(self) -> None:
        route = urlparse(self.path).path.rstrip("/") or "/"
        public_routes = {"/api/identity/create-user", "/api/identity/login"}
        if route.startswith("/api/") and route not in public_routes:
            user = self.authenticated_product_user()
            if user is None:
                return
        if route.startswith("/api/journal") or route.startswith("/journal/"):
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            if not self.authorize_index_mutation(route, user or {}):
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            self.send_journal_response("POST", route, payload)
            return
        if route == "/api/assistant/chat":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            if not self.authorize_index_mutation(route, user or {}):
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            self.send_assistant_chat(payload or {}, user or {})
            return
        if route in {"/api/router/explain", "/api/token-budget/explain", "/api/privacy-tokenizer/debug", "/api/assistant/trace/record-entrypoint"}:
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            payload = payload or {}
            if route == "/api/router/explain":
                self.send_router_explain(payload)
                return
            if route == "/api/token-budget/explain":
                self.send_token_budget_explain(payload)
                return
            if route == "/api/privacy-tokenizer/debug":
                self.send_privacy_tokenizer_debug(payload)
                return
            self.send_assistant_trace_response("POST", route, payload)
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
            self.send_acl_filtered_json(result, status_code, user or {})
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
            if not self.authorize_index_mutation(route, user or {}):
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
            self.send_acl_filtered_json(result, status_code, user or {})
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
            if not self.authorize_index_mutation(route, user or {}):
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
            self.send_acl_filtered_json(result, status_code, user or {})
            return
        if route.startswith("/api/person-attribute"):
            if person_attribute_route_response is None:
                self.send_json({"ok": False, "error": "person_attribute_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            if not self.authorize_index_mutation(route, user or {}):
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            payload = payload or {}
            payload.setdefault("user_id", str((user or {}).get("username") or "operator"))
            status_code, result = person_attribute_route_response(route, method="POST", payload=payload, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_acl_filtered_json(result, status_code, user or {})
            return
        if route == "/api/ai-album/auto-organize":
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
            status_code, result = self.state.ai_album_auto_organize_payload(payload or {}, user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/ai-album/organize-now":
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
            status_code, result = self.state.ai_album_organize_pending_payload(payload or {}, user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/ai-album/rebuild":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            if not self.authorize_index_mutation(route, user or {}):
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            status_code, result = self.state.ai_album_rebuild_payload(payload or {}, user or {})
            self.send_json(result, status_code)
            return
        if route.startswith("/api/ai-space"):
            if ai_space_route_response is None:
                self.send_json({"ok": False, "error": "ai_space_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            if not self.authorize_index_mutation(route, user or {}):
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            payload = payload or {}
            for key, value in self.query_payload().items():
                payload.setdefault(key, value)
            payload.setdefault("user_id", str((user or {}).get("username") or "operator"))
            status_code, result = ai_space_route_response(route, method="POST", payload=payload, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_acl_filtered_json(result, status_code, user or {})
            return
        if route.startswith("/api/auto-organize"):
            if auto_organizer_route_response is None:
                self.send_json({"ok": False, "error": "auto_organizer_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            if str((user or {}).get("role") or "") != "admin":
                self.send_json({"ok": False, "error": "admin_required", "route": route}, HTTPStatus.FORBIDDEN)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            payload = payload or {}
            payload.setdefault("approved_by", str((user or {}).get("username") or "operator"))
            status_code, result = auto_organizer_route_response(route, method="POST", payload=payload, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_acl_filtered_json(result, status_code, user or {})
            return
        if route.startswith("/api/smart-classification"):
            if smart_classification_route_response is None:
                self.send_json({"ok": False, "error": "smart_classification_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            if not self.authorize_index_mutation(route, user or {}):
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            payload = payload or {}
            payload.setdefault("user_id", str((user or {}).get("username") or "operator"))
            status_code, result = smart_classification_route_response(route, method="POST", payload=payload, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_acl_filtered_json(result, status_code, user or {})
            return
        if route.startswith("/api/smart-naming"):
            if smart_naming_route_response is None:
                self.send_json({"ok": False, "error": "smart_naming_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
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
            status_code, result = smart_naming_route_response(route, method="POST", payload=payload, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_acl_filtered_json(result, status_code, user or {})
            return
        if route.startswith("/api/subtitle"):
            if subtitle_extraction_route_response is None:
                self.send_json({"ok": False, "error": "subtitle_extraction_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
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
            status_code, result = subtitle_extraction_route_response(route, method="POST", payload=payload, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_acl_filtered_json(result, status_code, user or {})
            return
        if route.startswith("/api/jobs"):
            if product_jobs_route_response is None:
                self.send_json({"ok": False, "error": "product_jobs_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_admin(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            payload = payload or {}
            payload.setdefault("user_id", str((user or {}).get("username") or "operator"))
            status_code, result = product_jobs_route_response(route, method="POST", payload=payload, report_root=self.state.report_root, personal_root=self.state.personal_root)
            self.send_acl_filtered_json(result, status_code, user or {})
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
        if route == "/api/storage/upload-stream":
            if not self.require_product():
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                self.send_json({"ok": False, "error": "invalid_content_length"}, HTTPStatus.BAD_REQUEST)
                return
            query = parse_qs(urlparse(self.path).query)
            status_code, result = self.state.storage_upload_stream(
                (query.get("filename") or [""])[0],
                (query.get("target_dir") or [""])[0],
                content_length,
                self.rfile,
                user or {},
            )
            self.send_json(result, status_code)
            return
        if route == "/api/storage/upload-file":
            if not self.require_product():
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                self.send_json({"ok": False, "error": "invalid_content_length"}, HTTPStatus.BAD_REQUEST)
                return
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
        if route == "/api/storage/trash":
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
            status_code, result = self.state.storage_trash_payload(payload or {}, user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/storage/trash/cleanup":
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
            status_code, result = self.state.storage_trash_cleanup_payload(payload or {}, user or {})
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
            status_code, result = self.state.copilot_chat(
                str(payload.get("message") or ""),
                user or {},
                payload.get("model_choice"),
            )
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
        if route == "/api/documents/classify":
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
            status_code, result = self.state.document_classification_payload(str((payload or {}).get("path") or "Documents"), user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/ocr/rebuild":
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
            relative_path = str((payload or {}).get("path") or "Documents")
            status_code, result = self.state.sync_document_fts_index(relative_path, user or {})
            result = self.state._redact_paths(
                {
                    **(result if isinstance(result, dict) else {}),
                    "schema": "digua_ocr_rebuild_v1",
                    "route_module": "src.openclaw.routes.document_rag_routes",
                    "cloud_ocr_enabled": False,
                    "cloud_used": False,
                    "raw_private_content_returned": False,
                    "raw_path_returned": False,
                }
            )
            self.send_json(result, status_code)
            return
        if route in {"/api/document-rag/query", "/api/ocr/query"}:
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
            self.send_document_rag_or_ocr_query(
                payload or {},
                user or {},
                mode="ocr" if route == "/api/ocr/query" else "document_rag",
            )
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
            status_code, result = self.state.media_index_payload(str(payload.get("path") or ""), user or {})
            self.send_json(result, status_code)
            return
        if route == "/api/media/upload":
            if not self.require_product():
                return
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            if content_length > (MAX_UPLOAD_BYTES * 2):
                self.send_json({"ok": False, "error": "request_too_large", "max_payload_bytes": MAX_UPLOAD_BYTES * 2, "raw_path_returned": False}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            auth_status, error, user = self.state.require_user(self.headers.get("Authorization"))
            if auth_status:
                self.send_json(error or {}, auth_status)
                return
            status, payload = self.read_json_body()
            if status:
                self.send_json(payload or {}, status)
                return
            status_code, result = self.state.media_upload_photo(payload or {}, user or {})
            self.send_json(result, status_code)
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
                    "operator_portal_contract": self.state._redact_paths(report_without_payload(contract)),
                    "portal_html": self.state._redact_paths(str(self.state.portal_html_path())) if self.state.portal_html_path() else None,
                    "portal_report_json": self.state._redact_paths(str(self.state.portal_report_path())) if self.state.portal_report_path() else None,
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
                    "POST /api/storage/trash",
                    "POST /api/storage/trash/cleanup",
                    "POST /api/documents/query",
                    "POST /api/reports/export",
                    "POST /api/router/explain",
                    "POST /api/token-budget/explain",
                    "POST /api/privacy-tokenizer/debug",
                    "POST /api/assistant/chat",
                    "POST /api/assistant/trace/record-entrypoint",
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
