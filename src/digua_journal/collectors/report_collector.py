from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..event_model import JournalEvent, make_event


def collect_sample_report_events(count: int = 8) -> list[JournalEvent]:
    start = datetime(2026, 7, 4, 5, 0, tzinfo=timezone.utc)
    reports = ["17090", "17100", "20080", "21000"]
    events: list[JournalEvent] = []
    for idx in range(count):
        report_id = reports[idx % len(reports)]
        events.append(
            make_event(
                source="report",
                event_type="report_generated",
                project_id="project_reports",
                folder_hint="reports/gates",
                title=f"Gate report {report_id} indexed",
                summary=f"Report collector captured metadata for gate {report_id}; report body remains local evidence only.",
                evidence_refs=[f"reports/{report_id}_journal_reference.json"],
                event_ts=(start + timedelta(minutes=idx * 5)).isoformat().replace("+00:00", "Z"),
                metadata={"report_id": report_id, "export_safe": True},
            )
        )
    return events
