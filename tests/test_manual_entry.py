from __future__ import annotations

from src.digua_journal.journal_db import JournalDB
from src.digua_journal.manual_entry import create_manual_entry


def test_manual_entry_creates_event_and_entry(tmp_path) -> None:
    db = JournalDB(tmp_path / "journal.sqlite3")
    db.migrate()
    result = create_manual_entry(
        db,
        project_id="project_ai_nas",
        title="Operator note",
        body="Accepted local-only journal behavior.",
    )
    assert result["entry_id"].startswith("manual_")
    assert db.stats()["journal_events"] == 1
    assert db.stats()["journal_manual_entries"] == 1
