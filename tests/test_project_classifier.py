from __future__ import annotations

from src.digua_journal.collectors import collect_sample_nas_index_diff_events, collect_sample_system_events
from src.digua_journal.journal_db import JournalDB
from src.digua_journal.project_classifier import ProjectClassifier


def test_project_classifier_persists_projects(tmp_path) -> None:
    db = JournalDB(tmp_path / "journal.sqlite3")
    db.migrate()
    events = collect_sample_nas_index_diff_events(12) + collect_sample_system_events()
    db.insert_events(events)
    classifier = ProjectClassifier()
    project_map = classifier.persist_project_map(db, db.list_events(limit=1000))
    assert len(project_map) >= 3
    assert db.stats()["journal_project_map"] >= 3
    assert all(project["qwen_execution_authority"] is False for project in project_map.values())
