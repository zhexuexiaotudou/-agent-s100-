from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..event_model import JournalEvent, make_event


def collect_sample_openclaw_events(count: int = 8) -> list[JournalEvent]:
    start = datetime(2026, 7, 4, 2, 30, tzinfo=timezone.utc)
    events: list[JournalEvent] = []
    actions = ["health_check", "timeline_view", "manual_entry", "summary_request"]
    for idx in range(count):
        action = actions[idx % len(actions)]
        events.append(
            make_event(
                source="openclaw",
                event_type="conversation" if idx % 3 else "tool_call",
                project_id="project_openclaw_ops",
                folder_hint="openclaw/default-service",
                title=f"OpenClaw journal action {action}",
                summary=f"OpenClaw default service observed {action}; no foreground takeover and no port changes.",
                evidence_refs=["reports/21050_journal_system_collectors_gate.json"],
                event_ts=(start + timedelta(minutes=idx * 11)).isoformat().replace("+00:00", "Z"),
                metadata={"port_8765_changed": False, "qwen_tool_execution": False},
            )
        )
    return events
