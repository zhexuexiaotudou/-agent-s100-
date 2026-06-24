#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import (
    DEFAULT_REPORT_ROOT,
    ensure_report_dir,
    iso_now,
    open_sqlite_connection,
    safe_write_json,
    safe_write_text,
)


TOOL_ID = "ai_nas_evidence_catalog_contract"
FORBIDDEN_AUDIT_FLAGS = [
    "delete_performed",
    "move_performed",
    "overwrite_performed",
    "service_restart_performed",
    "kill_performed",
    "source_files_modified",
    "personal_source_modified",
    "real_personal_source_modified",
]

REPORT_TOOL_ID_BY_FILENAME = {
    "allowlist_governance_audit.json": "ai_nas_allowlist_governance_audit",
    "case_packet.json": "ai_nas_case_packet",
    "concurrency_stability.json": "ai_nas_concurrency_stability",
    "duplicate_report.json": "ai_nas_duplicate_report",
    "embedding_search.json": "ai_nas_embedding_search",
    "evidence_report.json": "ai_nas_evidence_report",
    "file_search.json": "ai_nas_file_search",
    "folder_rag.json": "ai_nas_folder_rag",
    "folder_summary.json": "ai_nas_folder_summary",
    "image_embedding_extract.json": "ai_nas_image_embedding_extract",
    "index_status.json": "ai_nas_index_status",
    "model_service_resilience.json": "ai_nas_model_service_resilience",
    "movie_sort_demo.json": "ai_nas_movie_sort_demo_probe",
    "movie_sort_enhanced.json": "ai_nas_movie_sort_enhanced",
    "ocr_extract.json": "ai_nas_ocr_extract",
    "ocr_readiness.json": "ai_nas_ocr_readiness",
    "perf_benchmark.json": "ai_nas_perf_benchmark",
    "personal_inventory.json": "ai_nas_personal_inventory",
    "photo_semantic_search.json": "ai_nas_photo_semantic_search",
    "photo_similarity.json": "ai_nas_photo_similarity",
    "task_queue.json": "ai_nas_task_queue",
}


def parse_report_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def read_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}:{exc}"
    if not isinstance(payload, dict):
        return None, "json_root_not_object"
    return payload, None


def default_evidence_roots(report_root: Path) -> list[Path]:
    roots = [report_root]
    tmp_root = Path("tmp")
    if tmp_root.exists():
        roots.append(tmp_root)
    return roots


def default_allowlist_candidates() -> list[Path]:
    script_path = Path(__file__).resolve()
    return [
        Path("tmp/ai_nas_deploy/scripts/tool_allowlist.json"),
        Path("scripts/tool_allowlist.json"),
        script_path.parents[1] / "tool_allowlist.json",
    ]


def load_allowlisted_ai_nas_tools(allowlist_path: Path | None) -> dict:
    candidates = [allowlist_path] if allowlist_path else default_allowlist_candidates()
    selected = next((path for path in candidates if path and path.exists()), None)
    if not selected:
        return {
            "loaded": False,
            "path": str(candidates[0]) if candidates else None,
            "error": "allowlist_not_found",
            "tool_ids": [],
        }
    payload, error = read_json(selected)
    if error or not payload:
        return {"loaded": False, "path": str(selected), "error": error or "allowlist_not_object", "tool_ids": []}
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return {"loaded": False, "path": str(selected), "error": "tools_not_list", "tool_ids": []}
    tool_ids = sorted(
        {
            str(item.get("id"))
            for item in tools
            if isinstance(item, dict) and item.get("id") and str(item.get("id")).startswith("ai_nas_")
        }
    )
    return {"loaded": True, "path": str(selected), "error": None, "tool_ids": tool_ids}


def relative_to_any(path: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return str(path)


def audit_flags(payload: dict) -> list[str]:
    audit = payload.get("audit") or {}
    if not isinstance(audit, dict):
        return []
    flags = []
    for key in FORBIDDEN_AUDIT_FLAGS:
        value = audit.get(key)
        if value is True:
            flags.append(key)
    return flags


def nested_summary(payload: dict) -> dict:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def infer_tool_id(path: Path, payload: dict | None) -> tuple[str | None, str | None]:
    if payload and payload.get("tool_id"):
        return str(payload.get("tool_id")), "top_level"
    audit = payload.get("audit") if payload else None
    if isinstance(audit, dict) and audit.get("tool_id"):
        return str(audit.get("tool_id")), "audit"
    mapped = REPORT_TOOL_ID_BY_FILENAME.get(path.name)
    if mapped:
        return mapped, "filename_map"
    return None, None


def report_type(path: Path, payload: dict | None, tool_id: str | None = None) -> str:
    if tool_id:
        return tool_id
    stem = path.stem
    if stem.endswith("_report"):
        return stem[:-7]
    return stem


def collect_reports(evidence_roots: list[Path], max_reports: int) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    failures: list[dict] = []
    seen_paths: set[str] = set()
    candidates: list[Path] = []
    for root in evidence_roots:
        if not root.exists():
            continue
        try:
            candidates.extend(path for path in root.rglob("*.json") if path.is_file())
        except OSError as exc:
            failures.append({"root": str(root), "error": f"{type(exc).__name__}:{exc}"})
    candidates = sorted(candidates, key=lambda item: str(item))[:max_reports]
    for path in candidates:
        resolved = str(path.resolve())
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        payload, error = read_json(path)
        digest = sha256_file(path)
        try:
            stat = path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            size_bytes = stat.st_size
        except OSError:
            mtime = None
            size_bytes = None
        generated_at = parse_report_time(payload.get("generated_at") if payload else None)
        tool_id, tool_id_source = infer_tool_id(path, payload)
        verdict = payload.get("verdict") if payload else None
        summary = nested_summary(payload or {})
        flags = audit_flags(payload or {})
        record = {
            "path": str(path),
            "relative_path": relative_to_any(path, evidence_roots),
            "filename": path.name,
            "report_type": report_type(path, payload, tool_id),
            "tool_id": tool_id,
            "tool_id_source": tool_id_source,
            "verdict": verdict,
            "generated_at": generated_at.isoformat() if generated_at else None,
            "mtime": mtime.isoformat() if mtime else None,
            "size_bytes": size_bytes,
            "sha256": digest,
            "parse_error": error,
            "summary_json": summary,
            "forbidden_audit_flags": flags,
            "is_ai_nas_report": bool((tool_id and str(tool_id).startswith("ai_nas_")) or (verdict and "ai_nas" in str(verdict))),
        }
        records.append(record)
    return records, failures


def latest_key(record: dict) -> tuple[float, float, str]:
    generated = parse_report_time(record.get("generated_at"))
    mtime = parse_report_time(record.get("mtime"))
    return (
        generated.timestamp() if generated else 0.0,
        mtime.timestamp() if mtime else 0.0,
        record.get("path") or "",
    )


def mark_latest(records: list[dict]) -> None:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        key = record.get("report_type") or record.get("filename") or "unknown"
        grouped.setdefault(str(key), []).append(record)
        record["is_latest_for_type"] = False
    for items in grouped.values():
        latest = max(items, key=latest_key)
        latest["is_latest_for_type"] = True


def write_catalog(db_path: Path, records: list[dict]) -> dict:
    con = open_sqlite_connection(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                tool_id TEXT,
                tool_id_source TEXT,
                verdict TEXT,
                generated_at TEXT,
                mtime TEXT,
                path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                filename TEXT NOT NULL,
                size_bytes INTEGER,
                sha256 TEXT,
                parse_error TEXT,
                is_ai_nas_report INTEGER NOT NULL,
                is_latest_for_type INTEGER NOT NULL,
                forbidden_audit_flags_json TEXT NOT NULL,
                summary_json TEXT NOT NULL
            )
            """
        )
        con.execute("DELETE FROM evidence_reports")
        for record in records:
            con.execute(
                """
                INSERT INTO evidence_reports(
                    report_type, tool_id, tool_id_source, verdict, generated_at, mtime, path, relative_path,
                    filename, size_bytes, sha256, parse_error, is_ai_nas_report, is_latest_for_type,
                    forbidden_audit_flags_json, summary_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["report_type"],
                    record.get("tool_id"),
                    record.get("tool_id_source"),
                    record.get("verdict"),
                    record.get("generated_at"),
                    record.get("mtime"),
                    record["path"],
                    record["relative_path"],
                    record["filename"],
                    record.get("size_bytes"),
                    record.get("sha256"),
                    record.get("parse_error"),
                    1 if record.get("is_ai_nas_report") else 0,
                    1 if record.get("is_latest_for_type") else 0,
                    json.dumps(record.get("forbidden_audit_flags") or [], ensure_ascii=False, sort_keys=True),
                    json.dumps(record.get("summary_json") or {}, ensure_ascii=False, sort_keys=True),
                ),
            )
        con.execute("CREATE INDEX IF NOT EXISTS idx_evidence_reports_type_latest ON evidence_reports(report_type, is_latest_for_type)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_evidence_reports_tool ON evidence_reports(tool_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_evidence_reports_generated ON evidence_reports(generated_at)")
        con.execute("DROP VIEW IF EXISTS latest_evidence_reports")
        con.execute(
            """
            CREATE VIEW latest_evidence_reports AS
            SELECT
                report_type,
                tool_id,
                tool_id_source,
                verdict,
                generated_at,
                mtime,
                path,
                relative_path,
                filename,
                size_bytes,
                sha256,
                parse_error,
                is_ai_nas_report,
                forbidden_audit_flags_json,
                summary_json
            FROM evidence_reports
            WHERE is_latest_for_type = 1
            """
        )
        con.commit()
        total = con.execute("SELECT COUNT(*) FROM evidence_reports").fetchone()[0]
        ai_nas = con.execute("SELECT COUNT(*) FROM evidence_reports WHERE is_ai_nas_report=1").fetchone()[0]
        latest = con.execute("SELECT COUNT(*) FROM evidence_reports WHERE is_latest_for_type=1").fetchone()[0]
        parsed = con.execute("SELECT COUNT(*) FROM evidence_reports WHERE parse_error IS NULL").fetchone()[0]
        latest_view = con.execute("SELECT COUNT(*) FROM latest_evidence_reports").fetchone()[0]
        latest_ai_nas_view = con.execute("SELECT COUNT(*) FROM latest_evidence_reports WHERE is_ai_nas_report=1").fetchone()[0]
        attributed = con.execute("SELECT COUNT(*) FROM evidence_reports WHERE tool_id IS NOT NULL").fetchone()[0]
        inferred = con.execute("SELECT COUNT(*) FROM evidence_reports WHERE tool_id_source IN ('audit', 'filename_map')").fetchone()[0]
        return {
            "sqlite_report_count": total,
            "sqlite_ai_nas_report_count": ai_nas,
            "sqlite_latest_type_count": latest,
            "sqlite_parsed_count": parsed,
            "sqlite_latest_view_count": latest_view,
            "sqlite_latest_ai_nas_view_count": latest_ai_nas_view,
            "sqlite_attributed_tool_id_count": attributed,
            "sqlite_inferred_tool_id_count": inferred,
            "sqlite_runtime": {
                "journal_mode": con.execute("PRAGMA journal_mode").fetchone()[0],
                "locking_mode": con.execute("PRAGMA locking_mode").fetchone()[0],
            },
        }
    finally:
        con.close()


def allowlist_report_coverage(records: list[dict], allowlist_status: dict) -> dict:
    canonical = set(allowlist_status.get("tool_ids") or [])
    reported = {
        str(record.get("tool_id"))
        for record in records
        if record.get("is_ai_nas_report") and record.get("tool_id")
    }
    latest_reported = {
        str(record.get("tool_id"))
        for record in records
        if record.get("is_ai_nas_report") and record.get("is_latest_for_type") and record.get("tool_id")
    }
    return {
        "allowlist_loaded": bool(allowlist_status.get("loaded")),
        "allowlist_path": allowlist_status.get("path"),
        "allowlist_error": allowlist_status.get("error"),
        "canonical_ai_nas_tool_count": len(canonical),
        "canonical_tools_with_any_report_count": len(canonical & reported),
        "canonical_tools_with_latest_report_count": len(canonical & latest_reported),
        "canonical_tools_missing_any_report": sorted(canonical - reported),
        "canonical_tools_missing_latest_report": sorted(canonical - latest_reported),
    }


def verify_catalog(records: list[dict], sqlite_status: dict, root_failures: list[dict], min_ai_nas_reports: int) -> list[str]:
    failures = []
    ai_nas_records = [record for record in records if record.get("is_ai_nas_report")]
    latest_ai_nas = [record for record in ai_nas_records if record.get("is_latest_for_type")]
    parsed_ai_nas = [record for record in ai_nas_records if not record.get("parse_error")]
    if root_failures:
        failures.append(f"evidence_root_scan_failures:{len(root_failures)}")
    if len(ai_nas_records) < min_ai_nas_reports:
        failures.append(f"ai_nas_report_count_lt_{min_ai_nas_reports}")
    if not latest_ai_nas:
        failures.append("no_latest_ai_nas_reports")
    if len(parsed_ai_nas) != len(ai_nas_records):
        failures.append("ai_nas_report_parse_errors_present")
    if any(not record.get("sha256") for record in ai_nas_records):
        failures.append("ai_nas_report_missing_sha256")
    flagged = [record for record in ai_nas_records if record.get("forbidden_audit_flags")]
    if flagged:
        failures.append(f"forbidden_audit_flags_present:{len(flagged)}")
    if sqlite_status.get("sqlite_report_count") != len(records):
        failures.append("sqlite_catalog_count_mismatch")
    if sqlite_status.get("sqlite_ai_nas_report_count") != len(ai_nas_records):
        failures.append("sqlite_ai_nas_count_mismatch")
    if sqlite_status.get("sqlite_latest_view_count") != sqlite_status.get("sqlite_latest_type_count"):
        failures.append("sqlite_latest_view_count_mismatch")
    if sqlite_status.get("sqlite_latest_ai_nas_view_count") != len(latest_ai_nas):
        failures.append("sqlite_latest_ai_nas_view_count_mismatch")
    return failures


def compact_latest(records: list[dict]) -> list[dict]:
    latest = [
        {
            "report_type": record["report_type"],
            "tool_id": record.get("tool_id"),
            "tool_id_source": record.get("tool_id_source"),
            "verdict": record.get("verdict"),
            "generated_at": record.get("generated_at"),
            "relative_path": record.get("relative_path"),
            "sha256": record.get("sha256"),
            "forbidden_audit_flags": record.get("forbidden_audit_flags"),
        }
        for record in records
        if record.get("is_latest_for_type") and record.get("is_ai_nas_report")
    ]
    return sorted(latest, key=lambda item: item["report_type"])


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS evidence catalog contract.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--evidence-root", action="append", type=Path, default=[])
    parser.add_argument("--allowlist-path", type=Path, default=None)
    parser.add_argument("--max-reports", type=int, default=5000)
    parser.add_argument("--min-ai-nas-reports", type=int, default=32)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "evidence_catalog_contract")
    evidence_roots = args.evidence_root or default_evidence_roots(args.report_root)
    records, root_failures = collect_reports(evidence_roots, max(1, args.max_reports))
    mark_latest(records)
    sqlite_path = run_dir / "evidence_catalog.sqlite3"
    sqlite_status = write_catalog(sqlite_path, records)
    allowlist_status = load_allowlisted_ai_nas_tools(args.allowlist_path)
    coverage = allowlist_report_coverage(records, allowlist_status)
    failures = verify_catalog(records, sqlite_status, root_failures, args.min_ai_nas_reports)
    ai_nas_records = [record for record in records if record.get("is_ai_nas_report")]
    latest_records = compact_latest(records)
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_evidence_catalog_contract" if not failures else "failed_ai_nas_evidence_catalog_contract",
        "scope": "read-only SQLite evidence catalog for AI-NAS report provenance, hashes, latest selection, and forbidden audit flag visibility",
        "evidence_roots": [str(root) for root in evidence_roots],
        "sqlite_catalog_path": str(sqlite_path),
        "summary": {
            "scanned_json_count": len(records),
            "ai_nas_report_count": len(ai_nas_records),
            "latest_ai_nas_report_count": len(latest_records),
            "parsed_ai_nas_report_count": sum(1 for record in ai_nas_records if not record.get("parse_error")),
            "forbidden_audit_flagged_count": sum(1 for record in ai_nas_records if record.get("forbidden_audit_flags")),
            "root_scan_failure_count": len(root_failures),
            "sqlite_status": sqlite_status,
            "allowlist_report_coverage": coverage,
            "failure_count": len(failures),
            "failures": failures,
        },
        "latest_ai_nas_reports": latest_records,
        "root_scan_failures": root_failures,
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "download_performed": False,
            "network_call_performed": False,
            "service_restart_performed": False,
            "kill_performed": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON evidence catalog reports and SQLite catalog only",
        },
    }
    json_path = run_dir / "evidence_catalog_contract.json"
    md_path = run_dir / "evidence_catalog_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Evidence Catalog Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- sqlite_catalog_path: `{sqlite_path}`",
        "- sqlite_view: `latest_evidence_reports`",
        f"- scanned_json_count: `{payload['summary']['scanned_json_count']}`",
        f"- ai_nas_report_count: `{payload['summary']['ai_nas_report_count']}`",
        f"- latest_ai_nas_report_count: `{payload['summary']['latest_ai_nas_report_count']}`",
        f"- canonical_ai_nas_tool_count: `{coverage['canonical_ai_nas_tool_count']}`",
        f"- canonical_tools_with_any_report_count: `{coverage['canonical_tools_with_any_report_count']}`",
        f"- canonical_tools_missing_any_report_count: `{len(coverage['canonical_tools_missing_any_report'])}`",
        f"- forbidden_audit_flagged_count: `{payload['summary']['forbidden_audit_flagged_count']}`",
        f"- failures: `{failures}`",
        "- policy: read-only report catalog; no downloads, network calls, service restarts, kills, deletes, moves, overwrites, or Personal source mutation",
        "",
        "## Allowlist Report Coverage",
        "",
    ]
    for tool_id in coverage["canonical_tools_missing_any_report"][:80]:
        lines.append(f"- missing report for `{tool_id}`")
    lines.extend([
        "",
        "## Latest AI-NAS Reports",
        "",
    ])
    for record in latest_records[:80]:
        lines.append(
            f"- `{record['report_type']}` verdict `{record.get('verdict')}` generated `{record.get('generated_at')}` sha256 `{str(record.get('sha256'))[:12]}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    print(sqlite_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
