#!/usr/bin/env python3
"""User-visible scheduled organizing rules for the AI-NAS portal.

The manager stores rule intent, executes bounded dry-runs, and writes reports.
It never deletes, moves, renames, or overwrites source files.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import (
    _record_from_sqlite_row,
    build_sqlite_inventory,
    duplicate_groups,
    ensure_report_dir,
    iso_now,
    open_index_db,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
)


RULE_TYPES = {"index_refresh", "duplicate_report", "folder_summary"}
DEFAULT_RULES = [
    {
        "name": "nightly-index-refresh",
        "rule_type": "index_refresh",
        "interval_seconds": 86400,
        "config": {"path": ""},
    },
    {
        "name": "weekly-duplicate-report",
        "rule_type": "duplicate_report",
        "interval_seconds": 604800,
        "config": {"path": ""},
    },
    {
        "name": "weekly-folder-summary",
        "rule_type": "folder_summary",
        "interval_seconds": 604800,
        "config": {"path": "Documents"},
    },
]


def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = open_sqlite_connection(db_path, row_factory=True)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS schedule_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                rule_type TEXT NOT NULL,
                interval_seconds INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_run_at TEXT,
                last_run_status TEXT DEFAULT 'never',
                last_report_path TEXT,
                last_run_summary_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL REFERENCES schedule_rules(id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                report_path TEXT,
                result_json TEXT NOT NULL DEFAULT '{}',
                source_mutations INTEGER NOT NULL DEFAULT 0,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_schedule_runs_rule ON schedule_runs(rule_id, started_at);
            """
        )
        con.commit()
    finally:
        con.close()


def _clean_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return text.strip("-")[:96]


def _read_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _records_from_index(index_path: Path) -> list[dict[str, Any]]:
    con = open_index_db(index_path)
    try:
        rows = con.execute("SELECT * FROM records ORDER BY relative_path").fetchall()
        return [_record_from_sqlite_row(row) for row in rows]
    finally:
        con.close()


def _filter_records(records: list[dict[str, Any]], folder: str) -> list[dict[str, Any]]:
    folder = folder.strip().strip("/").replace("\\", "/")
    if not folder:
        return records
    prefix = folder + "/"
    return [item for item in records if item.get("relative_path") == folder or str(item.get("relative_path") or "").startswith(prefix)]


def _write_schedule_report(report_root: Path, rule: dict[str, Any], result: dict[str, Any], lines: list[str]) -> tuple[Path, Path]:
    run_dir = ensure_report_dir(report_root, "scheduled_organizing_rule")
    payload = {
        "generated_at": iso_now(),
        "tool_id": "ai_nas_scheduled_organizing_rule",
        "rule": rule,
        "mode": "dry_run",
        "source_mutations": False,
        "delete_performed": False,
        "move_performed": False,
        "overwrite_performed": False,
        "result": result,
    }
    json_path = run_dir / "scheduled_organizing_rule.json"
    md_path = run_dir / "scheduled_organizing_rule.md"
    safe_write_json(json_path, payload)
    safe_write_text(md_path, "\n".join(lines) + "\n")
    return json_path, md_path


class ScheduleRuleManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        _init_db(db_path)

    def _connect(self) -> sqlite3.Connection:
        return open_sqlite_connection(self.db_path, row_factory=True)

    def seed_defaults(self) -> list[dict[str, Any]]:
        created = []
        for item in DEFAULT_RULES:
            result = self.create_rule(
                item["name"],
                item["rule_type"],
                int(item["interval_seconds"]),
                config=item.get("config") or {},
                enabled=True,
                replace=False,
            )
            if result.get("ok"):
                created.append(result["rule"])
        return created

    def create_rule(
        self,
        name: str,
        rule_type: str,
        interval_seconds: int,
        *,
        config: dict[str, Any] | None = None,
        enabled: bool = True,
        replace: bool = True,
    ) -> dict[str, Any]:
        clean = _clean_name(name)
        if not clean:
            return {"ok": False, "error": "rule_name_required"}
        if rule_type not in RULE_TYPES:
            return {"ok": False, "error": "unsupported_rule_type", "supported": sorted(RULE_TYPES)}
        interval = max(60, int(interval_seconds or 0))
        now = iso_now()
        config_json = json.dumps(config or {}, ensure_ascii=False)
        con = self._connect()
        try:
            if replace:
                con.execute(
                    """
                    INSERT INTO schedule_rules(name, rule_type, interval_seconds, enabled, config_json, created_at, updated_at)
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET
                        rule_type=excluded.rule_type,
                        interval_seconds=excluded.interval_seconds,
                        enabled=excluded.enabled,
                        config_json=excluded.config_json,
                        updated_at=excluded.updated_at
                    """,
                    (clean, rule_type, interval, 1 if enabled else 0, config_json, now, now),
                )
            else:
                con.execute(
                    """
                    INSERT OR IGNORE INTO schedule_rules(name, rule_type, interval_seconds, enabled, config_json, created_at, updated_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (clean, rule_type, interval, 1 if enabled else 0, config_json, now, now),
                )
            con.commit()
            row = con.execute("SELECT * FROM schedule_rules WHERE name=?", (clean,)).fetchone()
            return {"ok": True, "rule": self._rule_payload(row)}
        finally:
            con.close()

    def set_enabled(self, name: str, enabled: bool) -> dict[str, Any]:
        con = self._connect()
        try:
            cur = con.execute(
                "UPDATE schedule_rules SET enabled=?, updated_at=? WHERE name=?",
                (1 if enabled else 0, iso_now(), _clean_name(name)),
            )
            con.commit()
            if cur.rowcount < 1:
                return {"ok": False, "error": "rule_not_found"}
            row = con.execute("SELECT * FROM schedule_rules WHERE name=?", (_clean_name(name),)).fetchone()
            return {"ok": True, "rule": self._rule_payload(row)}
        finally:
            con.close()

    def list_rules(self) -> list[dict[str, Any]]:
        self.seed_defaults()
        con = self._connect()
        try:
            rows = con.execute("SELECT * FROM schedule_rules ORDER BY name").fetchall()
            return [self._rule_payload(row) for row in rows]
        finally:
            con.close()

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        con = self._connect()
        try:
            rows = con.execute(
                """
                SELECT r.*, s.name AS rule_name, s.rule_type AS rule_type
                FROM schedule_runs r JOIN schedule_rules s ON r.rule_id=s.id
                ORDER BY r.started_at DESC LIMIT ?
                """,
                (max(1, min(int(limit or 50), 200)),),
            ).fetchall()
            return [self._run_payload(row) for row in rows]
        finally:
            con.close()

    def summary(self) -> dict[str, Any]:
        rules = self.list_rules()
        runs = self.list_runs(limit=50)
        return {
            "ok": True,
            "stats": {
                "rule_count": len(rules),
                "enabled_count": sum(1 for item in rules if item.get("enabled")),
                "run_count": len(runs),
                "due_count": sum(1 for item in rules if item.get("is_due")),
            },
            "rules": rules,
            "runs": runs,
            "safety_policy": {
                "dry_run_only": True,
                "source_mutations": False,
                "delete_performed": False,
                "move_performed": False,
                "overwrite_performed": False,
            },
        }

    def run_dry(
        self,
        name: str,
        *,
        personal_root: Path,
        index_path: Path,
        report_root: Path,
        max_files: int = 50000,
    ) -> dict[str, Any]:
        con = self._connect()
        started_at = iso_now()
        try:
            row = con.execute("SELECT * FROM schedule_rules WHERE name=?", (_clean_name(name),)).fetchone()
            if not row:
                return {"ok": False, "error": "rule_not_found"}
            rule = self._rule_payload(row)
            run_id = con.execute(
                "INSERT INTO schedule_runs(rule_id, started_at, mode, status, source_mutations) VALUES(?,?,?,?,0)",
                (row["id"], started_at, "dry_run", "running"),
            ).lastrowid
            con.commit()
        finally:
            con.close()

        status = "completed"
        error = None
        report_path = None
        result: dict[str, Any] = {}
        try:
            result, report_path = self._execute_rule(rule, personal_root, index_path, report_root, max_files=max_files)
        except Exception as exc:
            status = "failed"
            error = f"{type(exc).__name__}:{exc}"
            result = {"error": error}

        finished_at = iso_now()
        con = self._connect()
        try:
            con.execute(
                """
                UPDATE schedule_runs
                SET finished_at=?, status=?, report_path=?, result_json=?, error=?
                WHERE id=?
                """,
                (finished_at, status, str(report_path) if report_path else None, json.dumps(result, ensure_ascii=False), error, run_id),
            )
            con.execute(
                """
                UPDATE schedule_rules
                SET last_run_at=?, last_run_status=?, last_report_path=?, last_run_summary_json=?, updated_at=?
                WHERE name=?
                """,
                (finished_at, status, str(report_path) if report_path else None, json.dumps(result, ensure_ascii=False), finished_at, rule["name"]),
            )
            con.commit()
        finally:
            con.close()
        return {
            "ok": status == "completed",
            "run": {
                "id": int(run_id),
                "rule_name": rule["name"],
                "rule_type": rule["rule_type"],
                "mode": "dry_run",
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "report_path": str(report_path) if report_path else None,
                "source_mutations": False,
                "result": result,
                "error": error,
            },
        }

    def _execute_rule(
        self,
        rule: dict[str, Any],
        personal_root: Path,
        index_path: Path,
        report_root: Path,
        *,
        max_files: int,
    ) -> tuple[dict[str, Any], Path]:
        rule_type = rule["rule_type"]
        config = rule.get("config") or {}
        folder = str(config.get("path") or "").strip().strip("/")
        if rule_type == "index_refresh":
            index_status = build_sqlite_inventory(personal_root, index_path, max_files=max_files)
            result = {
                "action": "index_refresh",
                "personal_root": str(personal_root),
                "file_count": index_status.get("file_count"),
                "failed_count": index_status.get("failed_count"),
                "index_status": index_status.get("status"),
                "source_mutations": False,
            }
            lines = [
                "# Scheduled Index Refresh Dry-Run",
                "",
                f"- rule: `{rule['name']}`",
                f"- personal_root: `{personal_root}`",
                f"- file_count: `{result['file_count']}`",
                f"- failed_count: `{result['failed_count']}`",
                "- safety: metadata/index refresh only; source files were not modified",
            ]
            json_path, _ = _write_schedule_report(report_root, rule, result, lines)
            return result, json_path

        build_sqlite_inventory(personal_root, index_path, max_files=max_files)
        records = _filter_records(_records_from_index(index_path), folder)
        if rule_type == "duplicate_report":
            groups = duplicate_groups(records)
            result = {
                "action": "duplicate_report",
                "path": folder,
                "file_count": len(records),
                "duplicate_group_count": len(groups),
                "potential_reclaim_bytes": sum(int(group.get("potential_reclaim_bytes") or 0) for group in groups),
                "groups_preview": groups[:5],
                "source_mutations": False,
                "requires_human_confirmation": True,
            }
            lines = [
                "# Scheduled Duplicate Report Dry-Run",
                "",
                f"- rule: `{rule['name']}`",
                f"- path: `{folder or '/'}`",
                f"- scanned_files: `{result['file_count']}`",
                f"- duplicate_group_count: `{result['duplicate_group_count']}`",
                f"- potential_reclaim_bytes: `{result['potential_reclaim_bytes']}`",
                "- safety: report only; no delete, no move",
            ]
            for group in groups[:10]:
                lines.append(f"- sha256 `{str(group.get('sha256',''))[:16]}...` count `{group.get('count')}`")
            json_path, _ = _write_schedule_report(report_root, rule, result, lines)
            return result, json_path

        type_counts = Counter(str(item.get("type") or "unknown") for item in records)
        byte_counts: defaultdict[str, int] = defaultdict(int)
        for item in records:
            byte_counts[str(item.get("type") or "unknown")] += int(item.get("size_bytes") or 0)
        top_files = sorted(records, key=lambda x: int(x.get("size_bytes") or 0), reverse=True)[:10]
        result = {
            "action": "folder_summary",
            "path": folder,
            "file_count": len(records),
            "total_bytes": sum(int(item.get("size_bytes") or 0) for item in records),
            "type_counts": dict(sorted(type_counts.items())),
            "bytes_by_type": dict(sorted(byte_counts.items())),
            "largest_files": [
                {
                    "relative_path": item.get("relative_path"),
                    "size_bytes": item.get("size_bytes"),
                    "type": item.get("type"),
                    "summary": item.get("summary"),
                }
                for item in top_files
            ],
            "source_mutations": False,
        }
        lines = [
            "# Scheduled Folder Summary Dry-Run",
            "",
            f"- rule: `{rule['name']}`",
            f"- path: `{folder or '/'}`",
            f"- file_count: `{result['file_count']}`",
            f"- total_bytes: `{result['total_bytes']}`",
            f"- type_counts: `{result['type_counts']}`",
            "- safety: summary report only; source files were not modified",
            "",
            "## Largest Files",
        ]
        for item in result["largest_files"]:
            lines.append(f"- `{item['relative_path']}` | `{item['size_bytes']}` bytes | `{item['type']}`")
        json_path, _ = _write_schedule_report(report_root, rule, result, lines)
        return result, json_path

    def _rule_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        config = _read_json(row["config_json"])
        last_run = _parse_iso(row["last_run_at"])
        interval = int(row["interval_seconds"] or 0)
        is_due = not last_run or (datetime.now(timezone.utc).astimezone() - last_run).total_seconds() >= interval
        return {
            "id": int(row["id"]),
            "name": row["name"],
            "rule_type": row["rule_type"],
            "interval_seconds": interval,
            "enabled": bool(row["enabled"]),
            "config": config,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_run_at": row["last_run_at"],
            "last_run_status": row["last_run_status"],
            "last_report_path": row["last_report_path"],
            "last_run_summary": _read_json(row["last_run_summary_json"]),
            "is_due": bool(row["enabled"]) and is_due,
        }

    def _run_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "rule_name": row["rule_name"],
            "rule_type": row["rule_type"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "mode": row["mode"],
            "status": row["status"],
            "report_path": row["report_path"],
            "result": _read_json(row["result_json"]),
            "source_mutations": bool(row["source_mutations"]),
            "error": row["error"],
        }
