from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


ALLOWED_SOURCES = {
    "nas_index_diff",
    "openclaw",
    "workspace_harness",
    "document_rag",
    "report",
    "manual",
    "token_budget",
    "copy_route",
}

ALLOWED_EVENT_TYPES = {
    "file_added",
    "file_modified",
    "file_removed",
    "file_renamed",
    "conversation",
    "tool_call",
    "rag_hit",
    "report_generated",
    "manual_note",
    "summary_generated",
    "export_generated",
    "route_decision",
}

PRIVATE_PATTERNS = [
    re.compile(r"/mnt/nas/openclaw/Personal/[^\s,;]+", re.IGNORECASE),
    re.compile(r"\\\\[^\\\s]+\\[^\s]+"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\[^\s]+", re.IGNORECASE),
    re.compile(r"(?i)\bredaction_map\b"),
    re.compile(r"(?i)\bdenied snippet\b"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def short_hash(value: Any, length: int = 16) -> str:
    text = "" if value is None else str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def stable_event_id(payload: dict[str, Any]) -> str:
    serial = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "evt_" + short_hash(serial, 24)


def redact_private_text(text: Any) -> tuple[str, int]:
    value = "" if text is None else str(text)
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        raw = match.group(0)
        count += 1
        return f"<PRIVATE_PATH_HASH:{short_hash(raw, 12)}>"

    for pattern in PRIVATE_PATTERNS:
        value = pattern.sub(replace, value)
    return value, count


def hash_folder(path_or_label: Any) -> str:
    return "folder_" + short_hash(path_or_label, 16)


def _safe_list(values: Iterable[Any] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for value in values:
        redacted, _ = redact_private_text(value)
        out.append(redacted[:240])
    return out


@dataclass
class JournalEvent:
    event_id: str
    event_ts: str
    source: str
    event_type: str
    project_id: str
    folder_hash: str
    title: str
    summary: str
    evidence_refs: list[str] = field(default_factory=list)
    privacy_level: str = "local_private"
    raw_content_stored: bool = False
    denied: bool = False
    token_counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_ts": self.event_ts,
            "source": self.source,
            "event_type": self.event_type,
            "project_id": self.project_id,
            "folder_hash": self.folder_hash,
            "title": self.title,
            "summary": self.summary,
            "evidence_refs": list(self.evidence_refs),
            "privacy_level": self.privacy_level,
            "raw_content_stored": self.raw_content_stored,
            "denied": self.denied,
            "token_counts": dict(self.token_counts),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    def validate(self) -> None:
        if self.source not in ALLOWED_SOURCES:
            raise ValueError(f"unsupported journal source: {self.source}")
        if self.event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"unsupported journal event_type: {self.event_type}")
        if self.raw_content_stored:
            raise ValueError("raw_content_stored must remain false for journal exports")
        serial = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(serial):
                raise ValueError("journal event contains a raw private marker")


def make_event(
    *,
    source: str,
    event_type: str,
    project_id: str,
    folder_hint: str,
    title: str,
    summary: str,
    evidence_refs: Iterable[Any] | None = None,
    event_ts: str | None = None,
    privacy_level: str = "local_private",
    denied: bool = False,
    token_counts: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> JournalEvent:
    safe_title, title_redactions = redact_private_text(title)
    safe_summary, summary_redactions = redact_private_text(summary)
    safe_metadata: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if key in {"raw_path", "full_path", "redaction_map", "raw_content"}:
            safe_metadata[f"{key}_omitted"] = True
            continue
        if isinstance(value, str):
            safe_value, _ = redact_private_text(value)
            safe_metadata[key] = safe_value
        else:
            safe_metadata[key] = value
    safe_metadata["redaction_count"] = int(safe_metadata.get("redaction_count", 0)) + title_redactions + summary_redactions
    ts = event_ts or utc_now()
    base = {
        "event_ts": ts,
        "source": source,
        "event_type": event_type,
        "project_id": project_id,
        "folder_hash": hash_folder(folder_hint),
        "title": safe_title,
        "summary": safe_summary,
        "evidence_refs": _safe_list(evidence_refs),
    }
    event = JournalEvent(
        event_id=stable_event_id(base) if source != "manual" else "evt_" + uuid.uuid4().hex[:24],
        event_ts=ts,
        source=source,
        event_type=event_type,
        project_id=project_id,
        folder_hash=base["folder_hash"],
        title=safe_title,
        summary=safe_summary,
        evidence_refs=base["evidence_refs"],
        privacy_level=privacy_level,
        raw_content_stored=False,
        denied=denied,
        token_counts=token_counts or {},
        metadata=safe_metadata,
    )
    event.validate()
    return event
