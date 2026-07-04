from __future__ import annotations


DEFAULT_RETENTION_POLICY = {
    "events_days": 366,
    "manual_entries_days": 3660,
    "summaries_days": 3660,
    "exports_days": 3660,
    "raw_content_stored": False,
    "redaction_lookup_exported": False,
}
