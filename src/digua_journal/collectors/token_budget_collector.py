from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..event_model import JournalEvent, make_event


def collect_sample_token_budget_events(count: int = 6) -> list[JournalEvent]:
    start = datetime(2026, 7, 4, 5, 45, tzinfo=timezone.utc)
    events: list[JournalEvent] = []
    for idx in range(count):
        events.append(
            make_event(
                source="token_budget",
                event_type="route_decision",
                project_id="project_ai_nas",
                folder_hint="token-budget/local-first",
                title=f"Token route sample {idx}",
                summary="Token budget route stayed local-only for private Journal evidence.",
                evidence_refs=["reports/21090_journal_token_privacy_trace_gate.json"],
                event_ts=(start + timedelta(minutes=idx * 6)).isoformat().replace("+00:00", "Z"),
                token_counts={"prompt": 24 + idx, "evidence": 80 + idx * 3, "output": 60 + idx},
                metadata={"cloud_allowed": False, "redaction_lookup_exported": False},
            )
        )
    return events
