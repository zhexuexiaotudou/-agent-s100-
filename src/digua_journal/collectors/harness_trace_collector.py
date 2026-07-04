from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..event_model import JournalEvent, make_event


def collect_sample_harness_trace_events(count: int = 8) -> list[JournalEvent]:
    start = datetime(2026, 7, 4, 3, 0, tzinfo=timezone.utc)
    phases = ["readonly_shadow", "policy_check", "copy_preview", "rollback_check"]
    events: list[JournalEvent] = []
    for idx in range(count):
        phase = phases[idx % len(phases)]
        events.append(
            make_event(
                source="workspace_harness",
                event_type="tool_call",
                project_id="project_ai_nas",
                folder_hint="harness/default-service",
                title=f"Harness trace captured {phase}",
                summary=f"Workspace Harness trace captured {phase} with write execution disabled for Journal collection.",
                evidence_refs=["reports/21050_journal_system_collectors_gate.json"],
                event_ts=(start + timedelta(minutes=idx * 13)).isoformat().replace("+00:00", "Z"),
                metadata={"sidecar_foreground_takeover": False, "real_nas_write": False},
            )
        )
    return events
