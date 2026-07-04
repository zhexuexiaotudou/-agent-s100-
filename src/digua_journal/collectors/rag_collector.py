from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..event_model import JournalEvent, make_event


def collect_sample_rag_events(count: int = 8) -> list[JournalEvent]:
    start = datetime(2026, 7, 4, 4, 0, tzinfo=timezone.utc)
    topics = ["permission-aware retrieval", "local summary", "evidence citation", "report section"]
    events: list[JournalEvent] = []
    for idx in range(count):
        topic = topics[idx % len(topics)]
        events.append(
            make_event(
                source="document_rag",
                event_type="rag_hit",
                project_id="project_reports",
                folder_hint="docs/reporting",
                title=f"RAG hit for {topic}",
                summary=f"Document/RAG collector stored only citation metadata for {topic}; raw private content is not stored.",
                evidence_refs=["reports/21050_journal_system_collectors_gate.json"],
                event_ts=(start + timedelta(minutes=idx * 9)).isoformat().replace("+00:00", "Z"),
                metadata={"raw_content_stored": False, "acl_enforced": True},
            )
        )
    return events
