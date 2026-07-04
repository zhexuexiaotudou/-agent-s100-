from __future__ import annotations

from src.digua_journal.collectors.nas_index_diff_collector import collect_sample_nas_index_diff_events


def test_sample_nas_index_diff_events_are_redacted() -> None:
    events = collect_sample_nas_index_diff_events(24)
    assert len(events) >= 20
    for event in events:
        payload = event.to_dict()
        assert event.source == "nas_index_diff"
        assert payload["raw_content_stored"] is False
        assert "/mnt/nas/openclaw/Personal" not in str(payload)
