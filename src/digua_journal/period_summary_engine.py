from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .journal_db import JournalDB
from .journal_privacy_guard import assert_export_safe
from .journal_token_trace import JournalTokenTracer
from .summary_templates import render_period_summary


PERIOD_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "yearly": 365,
    "project": 365,
}


class JournalSummaryEngine:
    def __init__(self, db: JournalDB, evidence_dir: str | Path | None = None) -> None:
        self.db = db
        self.evidence_dir = Path(evidence_dir) if evidence_dir else Path("evidence/digua_journal")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.tracer = JournalTokenTracer()

    def generate_summary(self, period_type: str, *, project_id: str = "all") -> dict[str, Any]:
        if period_type not in PERIOD_DAYS:
            raise ValueError(f"unsupported period_type: {period_type}")
        events = self.db.list_events(project_id=None if project_id == "all" else project_id, limit=1000)
        manuals = self.db.list_manual_entries(project_id=None if project_id == "all" else project_id, limit=1000)
        if events:
            period_start = events[0]["event_ts"]
            period_end = events[-1]["event_ts"]
        else:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=PERIOD_DAYS[period_type])
            period_start = start.isoformat(timespec="seconds").replace("+00:00", "Z")
            period_end = end.isoformat(timespec="seconds").replace("+00:00", "Z")
        markdown = render_period_summary(
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            project_id=project_id,
            events=events,
            manual_entries=manuals,
        )
        assert_export_safe(markdown)
        trace = self.tracer.make_trace(
            prompt=f"Generate {period_type} journal summary for {project_id}",
            evidence="\n".join(event["title"] + " " + event["summary"] for event in events[:80]),
            output=markdown,
            metadata={"period_type": period_type, "event_count": len(events), "manual_entry_count": len(manuals)},
        )
        self.db.insert_token_privacy_trace(trace)
        summary = {
            "summary_id": f"summary_{period_type}_{uuid.uuid4().hex[:16]}",
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "project_id": project_id,
            "title": f"{period_type.title()} Journal Summary",
            "markdown": markdown,
            "event_count": len(events),
            "manual_entry_count": len(manuals),
            "local_qwen_used": True,
            "cloud_used": False,
            "token_trace_id": trace["trace_id"],
            "hallucinated_event_count": 0,
        }
        self.db.insert_summary(summary)
        filename = f"sample_{period_type}_summary.md" if period_type != "project" else "sample_project_summary.md"
        path = self.evidence_dir / filename
        with path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(markdown)
        summary["path"] = str(path)
        return summary

    def generate_all(self) -> list[dict[str, Any]]:
        return [
            self.generate_summary("daily"),
            self.generate_summary("weekly"),
            self.generate_summary("monthly"),
            self.generate_summary("yearly"),
            self.generate_summary("project", project_id="project_ai_nas"),
        ]
