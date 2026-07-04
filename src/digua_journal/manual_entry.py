from __future__ import annotations

from typing import Any

from .event_model import make_event
from .journal_db import JournalDB
from .journal_privacy_guard import sanitize_text


def create_manual_entry(
    db: JournalDB,
    *,
    project_id: str,
    title: str,
    body: str,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    safe_title, title_redactions = sanitize_text(title)
    safe_body, body_redactions = sanitize_text(body)
    event = make_event(
        source="manual",
        event_type="manual_note",
        project_id=project_id,
        folder_hint=f"manual/{project_id}",
        title=safe_title,
        summary=safe_body[:500],
        evidence_refs=evidence_refs or [],
        metadata={"redaction_count": title_redactions + body_redactions},
    )
    db.insert_event(event)
    entry_id = db.insert_manual_entry(
        project_id=project_id,
        title=safe_title,
        body=safe_body,
        evidence_refs=evidence_refs or [],
        event_id=event.event_id,
    )
    return {"entry_id": entry_id, "event_id": event.event_id, "redaction_count": title_redactions + body_redactions}
