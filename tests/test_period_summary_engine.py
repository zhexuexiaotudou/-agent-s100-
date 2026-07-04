from __future__ import annotations

from src.digua_journal.collectors import collect_sample_nas_index_diff_events, collect_sample_system_events
from src.digua_journal.journal_db import JournalDB
from src.digua_journal.period_summary_engine import JournalSummaryEngine


def test_period_summary_engine_generates_all_periods_without_cloud(tmp_path) -> None:
    db = JournalDB(tmp_path / "journal.sqlite3")
    db.migrate()
    db.insert_events(collect_sample_nas_index_diff_events(12) + collect_sample_system_events())
    engine = JournalSummaryEngine(db, evidence_dir=tmp_path / "evidence")
    summaries = engine.generate_all()
    assert {summary["period_type"] for summary in summaries} == {"daily", "weekly", "monthly", "yearly", "project"}
    assert all(summary["cloud_used"] is False for summary in summaries)
    assert all(summary["hallucinated_event_count"] == 0 for summary in summaries)
