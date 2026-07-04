from __future__ import annotations

from src.digua_journal.collectors import collect_sample_system_events


def test_system_collectors_cover_required_sources() -> None:
    events = collect_sample_system_events()
    sources = {event.source for event in events}
    assert len(events) >= 40
    assert {
        "openclaw",
        "workspace_harness",
        "document_rag",
        "report",
        "token_budget",
        "copy_route",
    } <= sources
    assert all(not event.raw_content_stored for event in events)
