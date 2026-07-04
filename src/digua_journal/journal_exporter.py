from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from .event_model import utc_now
from .journal_db import JournalDB
from .journal_privacy_guard import assert_export_safe, export_safety_report


class JournalExporter:
    def __init__(self, db: JournalDB, export_dir: str | Path) -> None:
        self.db = db
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_markdown(self, *, period_type: str = "daily", project_id: str = "all") -> dict[str, Any]:
        events = self.db.list_events(project_id=None if project_id == "all" else project_id, limit=1000)
        manuals = self.db.list_manual_entries(project_id=None if project_id == "all" else project_id, limit=1000)
        lines = [
            f"# Digua Journal Export: {period_type}",
            "",
            f"- Project: {project_id}",
            f"- Exported at: {utc_now()}",
            f"- Cloud generation: disabled",
            "",
            "## Events",
        ]
        for event in events:
            lines.append(f"- {event['event_ts']} [{event['source']}] {event['title']} - {event['summary']}")
        lines.extend(["", "## Manual Entries"])
        for entry in manuals:
            lines.append(f"- {entry['created_at']} {entry['title']} - {entry['body']}")
        text = "\n".join(lines) + "\n"
        assert_export_safe(text)
        return self._write_export(text.encode("utf-8"), "markdown", period_type, project_id, ".md")

    def export_json(self, *, period_type: str = "daily", project_id: str = "all") -> dict[str, Any]:
        payload = {
            "exported_at": utc_now(),
            "period_type": period_type,
            "project_id": project_id,
            "cloud_generation_enabled": False,
            "redaction_lookup_exported": False,
            "events": self.db.list_events(project_id=None if project_id == "all" else project_id, limit=1000),
            "manual_entries": self.db.list_manual_entries(project_id=None if project_id == "all" else project_id, limit=1000),
        }
        assert_export_safe(payload)
        return self._write_export(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"), "json", period_type, project_id, ".json")

    def _write_export(self, data: bytes, export_type: str, period_type: str, project_id: str, suffix: str) -> dict[str, Any]:
        export_id = "export_" + uuid.uuid4().hex[:16]
        path = self.export_dir / f"{export_id}_{period_type}_{project_id}{suffix}"
        path.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        safety = export_safety_report(data.decode("utf-8", errors="replace"))
        record = {
            "export_id": export_id,
            "created_at": utc_now(),
            "export_type": export_type,
            "period_type": period_type,
            "project_id": project_id,
            "path": str(path),
            "sha256": sha,
            "private_leak_count": safety["private_leak_count"],
            "redaction_lookup_exported": safety["redaction_lookup_exported"],
        }
        self.db.insert_export(record)
        return record
