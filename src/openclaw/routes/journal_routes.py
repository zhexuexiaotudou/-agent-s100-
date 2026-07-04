from __future__ import annotations

from pathlib import Path
from typing import Any

from src.digua_journal.journal_db import JournalDB
from src.digua_journal.journal_exporter import JournalExporter
from src.digua_journal.manual_entry import create_manual_entry
from src.digua_journal.period_summary_engine import JournalSummaryEngine
from src.digua_journal.project_classifier import ProjectClassifier


def _db(report_root: str | Path | None = None) -> JournalDB:
    root = Path(report_root) if report_root else Path("tmp/digua_journal")
    db = JournalDB(root / "digua_journal.sqlite3")
    db.migrate()
    return db


def journal_health_response(*, report_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    db = _db(report_root)
    return 200, {
        "ok": True,
        "feature": "digua_journal",
        "db_path": str(db.db_path),
        "stats": db.stats(),
        "cloud_generation_enabled": False,
        "qwen_execution_authority": False,
    }


def journal_timeline_response(payload: dict[str, Any] | None = None, *, report_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    db = _db(report_root)
    return 200, {
        "ok": True,
        "events": db.list_events(project_id=payload.get("project_id"), limit=int(payload.get("limit", 200))),
    }


def journal_projects_response(*, report_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    db = _db(report_root)
    events = db.list_events(limit=1000)
    classifier = ProjectClassifier()
    if events and not db.list_projects():
        classifier.persist_project_map(db, events)
    return 200, {"ok": True, "projects": db.list_projects()}


def journal_manual_entry_response(payload: dict[str, Any], *, report_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    required = {"project_id", "title", "body"}
    missing = sorted(required - set(payload))
    if missing:
        return 400, {"ok": False, "error": "missing_fields", "missing": missing}
    db = _db(report_root)
    result = create_manual_entry(
        db,
        project_id=str(payload["project_id"]),
        title=str(payload["title"]),
        body=str(payload["body"]),
        evidence_refs=[str(item) for item in payload.get("evidence_refs", [])],
    )
    return 200, {"ok": True, **result}


def journal_generate_summary_response(payload: dict[str, Any], *, report_root: str | Path | None = None, evidence_dir: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    period_type = str(payload.get("period_type", "daily"))
    project_id = str(payload.get("project_id", "all"))
    db = _db(report_root)
    summary = JournalSummaryEngine(db, evidence_dir=evidence_dir).generate_summary(period_type, project_id=project_id)
    redacted = dict(summary)
    redacted["markdown"] = summary["markdown"][:1200]
    return 200, {"ok": True, "summary": redacted}


def journal_export_response(payload: dict[str, Any], *, report_root: str | Path | None = None, export_dir: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    db = _db(report_root)
    exporter = JournalExporter(db, export_dir or Path("evidence/digua_journal/exports"))
    export_type = str(payload.get("export_type", "markdown"))
    period_type = str(payload.get("period_type", "daily"))
    project_id = str(payload.get("project_id", "all"))
    if export_type == "json":
        record = exporter.export_json(period_type=period_type, project_id=project_id)
    else:
        record = exporter.export_markdown(period_type=period_type, project_id=project_id)
    return 200, {"ok": True, "export": record}


def journal_route_response(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    report_root: str | Path | None = None,
    evidence_dir: str | Path | None = None,
    export_dir: str | Path | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = payload or {}
    normalized = path.rstrip("/")
    if normalized in {"/api/journal/health", "/journal/health"}:
        return journal_health_response(report_root=report_root)
    if normalized in {"/api/journal/timeline", "/journal/timeline"}:
        return journal_timeline_response(payload, report_root=report_root)
    if normalized in {"/api/journal/projects", "/journal/projects"}:
        return journal_projects_response(report_root=report_root)
    if normalized in {"/api/journal/manual-entry", "/journal/manual-entry"} and method.upper() == "POST":
        return journal_manual_entry_response(payload, report_root=report_root)
    if normalized in {"/api/journal/generate-summary", "/journal/generate-summary"} and method.upper() == "POST":
        return journal_generate_summary_response(payload, report_root=report_root, evidence_dir=evidence_dir)
    if normalized in {"/api/journal/export", "/journal/export"} and method.upper() == "POST":
        return journal_export_response(payload, report_root=report_root, export_dir=export_dir)
    return 404, {"ok": False, "error": "unknown_journal_route", "path": path}
