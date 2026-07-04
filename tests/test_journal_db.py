from __future__ import annotations

from src.digua_journal.event_model import make_event
from src.digua_journal.journal_db import JournalDB


def test_journal_db_migration_insert_and_search(tmp_path) -> None:
    db = JournalDB(tmp_path / "journal.sqlite3")
    migration = db.migrate()
    assert migration["schema_version"] == 1
    event = make_event(
        source="report",
        event_type="report_generated",
        project_id="project_reports",
        folder_hint="reports",
        title="Gate report indexed",
        summary="Journal indexed a gate report.",
    )
    db.insert_event(event)
    rows = db.list_events()
    assert len(rows) == 1
    assert rows[0]["event_id"] == event.event_id
    hits = db.search_events("Journal")
    assert len(hits) == 1
