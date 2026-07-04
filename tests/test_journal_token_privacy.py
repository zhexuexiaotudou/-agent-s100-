from __future__ import annotations

from src.digua_journal.journal_privacy_guard import export_safety_report, sanitize_text
from src.digua_journal.journal_token_trace import JournalTokenTracer


def test_token_trace_stays_local_and_detects_private_markers() -> None:
    safe, redactions = sanitize_text("/mnt/nas/openclaw/Personal/private.docx")
    assert redactions == 1
    assert "/mnt/nas/openclaw/Personal" not in safe
    trace = JournalTokenTracer().make_trace(prompt="Summarize", evidence=safe, output="Safe output")
    assert trace["cloud_allowed"] is False
    assert trace["private_leak_count"] == 0


def test_export_safety_report_flags_raw_private_path() -> None:
    report = export_safety_report("bad /mnt/nas/openclaw/Personal/private.docx")
    assert report["ok"] is False
    assert report["private_leak_count"] == 1
