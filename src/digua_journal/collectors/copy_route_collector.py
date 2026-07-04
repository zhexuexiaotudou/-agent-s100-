from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..event_model import JournalEvent, make_event


def collect_sample_copy_route_events(count: int = 6) -> list[JournalEvent]:
    start = datetime(2026, 7, 4, 6, 15, tzinfo=timezone.utc)
    events: list[JournalEvent] = []
    for idx in range(count):
        events.append(
            make_event(
                source="copy_route",
                event_type="tool_call",
                project_id="project_openclaw_ops",
                folder_hint="copy-route/synthetic",
                title=f"Copy route readonly trace {idx}",
                summary="Copy route trace was ingested as readonly metadata; no real NAS copy/delete/move was executed.",
                evidence_refs=["reports/21050_journal_system_collectors_gate.json"],
                event_ts=(start + timedelta(minutes=idx * 8)).isoformat().replace("+00:00", "Z"),
                metadata={"execute_called": False, "dryrun_only": True},
            )
        )
    return events
