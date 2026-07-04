from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..event_model import JournalEvent, make_event, short_hash


def diff_index_rows(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_by_id = {row["stable_id"]: row for row in previous}
    current_by_id = {row["stable_id"]: row for row in current}
    diffs: list[dict[str, Any]] = []
    for stable_id, row in current_by_id.items():
        if stable_id not in previous_by_id:
            diffs.append({"diff_type": "file_added", "row": row})
            continue
        old = previous_by_id[stable_id]
        if row.get("content_hash") != old.get("content_hash") or row.get("mtime") != old.get("mtime"):
            diffs.append({"diff_type": "file_modified", "row": row})
    for stable_id, row in previous_by_id.items():
        if stable_id not in current_by_id:
            diffs.append({"diff_type": "file_removed", "row": row})
    return diffs


def event_from_diff(diff: dict[str, Any], *, event_ts: str | None = None) -> JournalEvent:
    row = diff["row"]
    project_id = row.get("project_id") or "project_ai_nas"
    folder_hint = row.get("folder_hash") or row.get("folder_label") or "openclaw-redacted-folder"
    title = f"{diff['diff_type']} in {row.get('safe_name', 'redacted item')}"
    summary = (
        f"NAS index detected {diff['diff_type']} for a redacted item. "
        f"content_hash={row.get('content_hash', short_hash(title))}; size_bucket={row.get('size_bucket', 'unknown')}."
    )
    return make_event(
        source="nas_index_diff",
        event_type=diff["diff_type"],
        project_id=project_id,
        folder_hint=folder_hint,
        title=title,
        summary=summary,
        evidence_refs=[row.get("evidence_ref", "reports/journal_nas_index_diff_sample_events.jsonl")],
        event_ts=event_ts,
        metadata={
            "stable_id": row.get("stable_id"),
            "content_hash": row.get("content_hash"),
            "real_nas_write": False,
            "raw_path": row.get("raw_path"),
        },
    )


def collect_nas_index_diff_events(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[JournalEvent]:
    return [event_from_diff(diff) for diff in diff_index_rows(previous, current)]


def collect_sample_nas_index_diff_events(count: int = 32) -> list[JournalEvent]:
    start = datetime(2026, 7, 4, 1, 0, tzinfo=timezone.utc)
    previous: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    projects = ["project_ai_nas", "project_openclaw_ops", "project_reports"]
    for idx in range(count):
        project_id = projects[idx % len(projects)]
        stable_id = "nas_" + short_hash(f"{project_id}-{idx}", 12)
        base = {
            "stable_id": stable_id,
            "project_id": project_id,
            "folder_label": f"{project_id}/folder-{idx % 5}",
            "folder_hash": "folder_" + short_hash(f"{project_id}/folder-{idx % 5}", 16),
            "safe_name": f"journal-safe-item-{idx:02d}.md",
            "size_bucket": "small" if idx % 4 else "medium",
            "evidence_ref": "reports/journal_nas_index_diff_sample_events.jsonl",
            "raw_path": f"/mnt/nas/openclaw/Personal/private-{idx}.md" if idx % 7 == 0 else None,
        }
        if idx % 5 != 0:
            previous.append({**base, "content_hash": "old_" + short_hash(stable_id, 12), "mtime": idx})
        current.append({**base, "content_hash": "new_" + short_hash(stable_id, 12), "mtime": idx + 1})
    events: list[JournalEvent] = []
    for offset, diff in enumerate(diff_index_rows(previous, current)):
        events.append(event_from_diff(diff, event_ts=(start + timedelta(minutes=offset * 7)).isoformat().replace("+00:00", "Z")))
    return events[:count]
