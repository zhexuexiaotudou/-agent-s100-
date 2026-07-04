from __future__ import annotations

from src.digua_journal.collectors import collect_sample_nas_index_diff_events
from src.digua_journal.journal_db import JournalDB
from src.openclaw.routes.journal_routes import journal_route_response


def test_journal_routes_health_timeline_manual_summary_export(tmp_path) -> None:
    db = JournalDB(tmp_path / "digua_journal.sqlite3")
    db.migrate()
    db.insert_events(collect_sample_nas_index_diff_events(8))
    status, health = journal_route_response("/api/journal/health", report_root=tmp_path)
    assert status == 200
    assert health["ok"] is True
    status, timeline = journal_route_response("/api/journal/timeline", report_root=tmp_path)
    assert status == 200
    assert len(timeline["events"]) == 8
    status, manual = journal_route_response(
        "/api/journal/manual-entry",
        method="POST",
        payload={"project_id": "project_ai_nas", "title": "Route note", "body": "Route body"},
        report_root=tmp_path,
    )
    assert status == 200
    assert manual["ok"] is True
    status, summary = journal_route_response(
        "/api/journal/generate-summary",
        method="POST",
        payload={"period_type": "daily"},
        report_root=tmp_path,
        evidence_dir=tmp_path / "evidence",
    )
    assert status == 200
    assert summary["summary"]["cloud_used"] is False
    status, export = journal_route_response(
        "/api/journal/export",
        method="POST",
        payload={"export_type": "markdown"},
        report_root=tmp_path,
        export_dir=tmp_path / "exports",
    )
    assert status == 200
    assert export["export"]["private_leak_count"] == 0
