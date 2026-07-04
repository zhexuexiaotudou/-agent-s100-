from __future__ import annotations

from ..event_model import JournalEvent
from .copy_route_collector import collect_sample_copy_route_events
from .harness_trace_collector import collect_sample_harness_trace_events
from .openclaw_collector import collect_sample_openclaw_events
from .rag_collector import collect_sample_rag_events
from .report_collector import collect_sample_report_events
from .token_budget_collector import collect_sample_token_budget_events


def collect_sample_system_events() -> list[JournalEvent]:
    events: list[JournalEvent] = []
    events.extend(collect_sample_openclaw_events())
    events.extend(collect_sample_harness_trace_events())
    events.extend(collect_sample_rag_events())
    events.extend(collect_sample_report_events())
    events.extend(collect_sample_token_budget_events())
    events.extend(collect_sample_copy_route_events())
    return events
