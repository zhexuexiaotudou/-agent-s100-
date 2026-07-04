from __future__ import annotations

from pathlib import Path

from src.digua_journal.collectors import collect_sample_nas_index_diff_events
from src.digua_journal.journal_db import JournalDB
from src.digua_journal.journal_exporter import JournalExporter


def test_journal_exporter_writes_safe_markdown_and_json(tmp_path) -> None:
    db = JournalDB(tmp_path / "journal.sqlite3")
    db.migrate()
    db.insert_events(collect_sample_nas_index_diff_events(8))
    exporter = JournalExporter(db, tmp_path / "exports")
    md = exporter.export_markdown()
    js = exporter.export_json()
    assert Path(md["path"]).exists()
    assert Path(js["path"]).exists()
    assert md["private_leak_count"] == 0
    assert js["private_leak_count"] == 0
    assert md["redaction_lookup_exported"] is False
