from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .context_pack import ContextPackCompiler, sample_context_candidates
from .memory_manager import AgentMemoryManager
from .multimodal_index import MultimodalIndex
from .rag_pipeline import AgentRuntimeRag
from .tool_manifest import load_manifest, validate_internal_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FLAGS_PATH = REPO_ROOT / "configs" / "agent_runtime_feature_flags.json"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "configs" / "internal_tool_manifest.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _safe_relative_path(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\\", "/").strip()
    if not text or text == ".":
        return ""
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ValueError("absolute_paths_are_not_allowed")
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("parent_traversal_is_not_allowed")
        parts.append(part)
    return "/".join(parts)


class AgentRuntimeService:
    def __init__(
        self,
        *,
        report_root: str | Path | None = None,
        personal_root: str | Path | None = None,
        feature_flags_path: str | Path | None = None,
        manifest_path: str | Path | None = None,
    ) -> None:
        self.report_root = Path(report_root) if report_root else REPO_ROOT / "reports" / "agent_runtime"
        self.personal_root = Path(personal_root) if personal_root else REPO_ROOT / "tmp" / "agent_runtime_personal"
        self.feature_flags_path = Path(feature_flags_path) if feature_flags_path else DEFAULT_FLAGS_PATH
        self.manifest_path = Path(manifest_path) if manifest_path else DEFAULT_MANIFEST_PATH
        self.flags = _read_json(self.feature_flags_path)
        self.runtime_root = self.report_root / "agent_runtime"
        self.runtime_root.mkdir(parents=True, exist_ok=True)

    @property
    def memory_db_path(self) -> Path:
        return self.runtime_root / "agent_runtime_memory.sqlite3"

    @property
    def multimodal_db_path(self) -> Path:
        return self.runtime_root / "agent_runtime_multimodal.sqlite3"

    @property
    def rag_db_path(self) -> Path:
        return self.runtime_root / "agent_runtime_rag.sqlite3"

    def status(self) -> dict[str, Any]:
        manifest = load_manifest(self.manifest_path) if self.manifest_path.exists() else {}
        manifest_check = validate_internal_manifest(manifest) if manifest else {"ok": False, "error": "manifest_missing"}
        memory = AgentMemoryManager(self.memory_db_path).stats()
        multimodal = MultimodalIndex(self.multimodal_db_path).status()
        return {
            "ok": bool(self.flags.get("agent_runtime_enabled", True)) and bool(manifest_check.get("ok")),
            "service": "agent_runtime",
            "schema": "digua_agent_runtime_status_v1",
            "feature_flags": {
                "agent_runtime_enabled": bool(self.flags.get("agent_runtime_enabled", True)),
                "context_pack_enabled": bool(self.flags.get("context_pack_enabled", True)),
                "memory_manager_enabled": bool(self.flags.get("memory_manager_enabled", True)),
                "multimodal_index_enabled": bool(self.flags.get("multimodal_index_enabled", True)),
                "rag_enabled": bool(self.flags.get("rag_enabled", True)),
                "rag_eval_enabled": bool(self.flags.get("rag_eval_enabled", True)),
                "public_mcp_enabled": False,
                "qwen_tool_execution_enabled": False,
                "cloud_private_raw_egress_enabled": False,
            },
            "routes": [
                "GET /api/agent-runtime/status",
                "GET /api/agent-runtime/tool-manifest",
                "GET /api/agent-runtime/memory/stats",
                "GET /api/agent-runtime/multimodal-index/status",
                "GET /api/agent-runtime/eval/status",
                "POST /api/agent-runtime/context-pack",
                "POST /api/agent-runtime/memory/record",
                "POST /api/agent-runtime/multimodal-index/scan",
                "POST /api/agent-runtime/rag/query",
            ],
            "datastores": {
                "memory_db": str(self.memory_db_path),
                "multimodal_db": str(self.multimodal_db_path),
                "rag_db": str(self.rag_db_path),
            },
            "memory": memory,
            "multimodal_index": multimodal,
            "internal_tool_manifest": manifest_check,
            "qwen_execution_authority": False,
            "cloud_private_raw_egress": False,
            "public_mcp_exposed": False,
            "raw_private_content_in_status": False,
        }

    def tool_manifest(self) -> dict[str, Any]:
        manifest = load_manifest(self.manifest_path) if self.manifest_path.exists() else {}
        check = validate_internal_manifest(manifest) if manifest else {"ok": False, "error": "manifest_missing"}
        safe_manifest = dict(manifest)
        safe_manifest["validation"] = check
        return {"ok": bool(check.get("ok")), "manifest": safe_manifest}

    def context_pack(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            case_index = int(payload.get("case_index") or 0)
            candidates = [candidate.__dict__ for candidate in sample_context_candidates(case_index)]
        pack = ContextPackCompiler(token_budget=int(self.flags.get("context_pack_token_budget", 4096))).compile(
            query=str(payload.get("query") or payload.get("message") or "agent runtime status"),
            workspace=str(payload.get("workspace") or "openclaw"),
            user_id=str(payload.get("user_id") or payload.get("username") or "operator"),
            candidates=candidates,
            request_id=str(payload.get("request_id") or ""),
        )
        return pack

    def memory_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.flags.get("memory_manager_enabled", True):
            return {"ok": False, "error": "memory_manager_disabled"}
        manager = AgentMemoryManager(self.memory_db_path)
        return manager.record_event(
            memory_type=str(payload.get("memory_type") or "event"),
            title=str(payload.get("title") or "Agent Runtime manual memory"),
            summary=str(payload.get("summary") or payload.get("body") or ""),
            evidence_refs=[str(item) for item in payload.get("evidence_refs", [])] if isinstance(payload.get("evidence_refs"), list) else [],
            source=str(payload.get("source") or "api"),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )

    def memory_stats(self) -> dict[str, Any]:
        return AgentMemoryManager(self.memory_db_path).stats()

    def scan_multimodal(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.flags.get("multimodal_index_enabled", True):
            return {"ok": False, "error": "multimodal_index_disabled"}
        try:
            relative_path = _safe_relative_path(payload.get("path") or "")
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        root = self.personal_root / relative_path if relative_path else self.personal_root
        return MultimodalIndex(self.multimodal_db_path).scan(root)

    def multimodal_status(self) -> dict[str, Any]:
        return MultimodalIndex(self.multimodal_db_path).status()

    def rag_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.flags.get("rag_enabled", True):
            return {"ok": False, "error": "rag_disabled"}
        rag = AgentRuntimeRag(self.rag_db_path)
        try:
            relative_path = _safe_relative_path(payload.get("path") or "Documents")
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        root = self.personal_root / (relative_path or "Documents")
        if root.exists():
            rag.sync_documents(root)
        return rag.answer(str(payload.get("query") or payload.get("message") or "agent runtime"))

    def eval_status(self) -> dict[str, Any]:
        candidates = [
            self.report_root / "24090_agent_runtime_eval_gate.json",
            REPO_ROOT / "reports" / "24090_agent_runtime_eval_gate.json",
        ]
        for path in candidates:
            if path.exists():
                payload = _read_json(path)
                return {"ok": bool(payload), "latest_eval": payload, "path": str(path)}
        return {"ok": False, "error": "eval_report_missing", "expected_report": "24090_agent_runtime_eval_gate.json"}
