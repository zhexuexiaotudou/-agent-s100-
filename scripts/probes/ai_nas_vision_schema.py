#!/usr/bin/env python3
"""Product-grade vision schema for OpenClaw AI-NAS.

The older image_captions/image_embeddings tables remain compatibility tables.
These tables describe the final product data plane: indexed generations,
regions, attributes, embeddings, captions, artifacts, jobs, and search audits.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


VISION_PRODUCT_SCHEMA_VERSION = "ai_nas_vision_product_schema_v1"

VISION_PRODUCT_TABLES = (
    "photo_visual_state",
    "vision_generations",
    "vision_regions",
    "vision_attributes",
    "vision_embeddings_v2",
    "vision_captions_v2",
    "vision_artifacts",
    "vision_jobs",
    "vision_search_audit",
)


def ensure_vision_product_schema(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA foreign_keys=ON")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS photo_visual_state (
            path TEXT PRIMARY KEY,
            relative_path TEXT NOT NULL,
            source_revision TEXT NOT NULL DEFAULT '',
            acl_scope TEXT NOT NULL DEFAULT '',
            security_partition_id TEXT NOT NULL DEFAULT 'default',
            acl_epoch INTEGER NOT NULL DEFAULT 0,
            privacy_class TEXT NOT NULL DEFAULT 'standard',
            active_generation INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'not_indexed',
            degradation_json TEXT NOT NULL DEFAULT '[]',
            indexed_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_photo_visual_state_acl ON photo_visual_state(security_partition_id, acl_epoch)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_photo_visual_state_status ON photo_visual_state(status)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            generation INTEGER NOT NULL,
            source_revision TEXT NOT NULL DEFAULT '',
            model_bundle_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            activated_at TEXT,
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(path, generation),
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_generations_status ON vision_generations(status)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            generation INTEGER NOT NULL,
            region_kind TEXT NOT NULL,
            label TEXT NOT NULL,
            bbox_json TEXT NOT NULL DEFAULT '[]',
            mask_artifact_id TEXT,
            confidence REAL NOT NULL DEFAULT 0,
            model_id TEXT NOT NULL DEFAULT '',
            runtime TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_regions_path_generation ON vision_regions(path, generation)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_regions_label ON vision_regions(label, region_kind)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_id INTEGER,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            generation INTEGER NOT NULL,
            namespace TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            model_id TEXT NOT NULL DEFAULT '',
            runtime TEXT NOT NULL DEFAULT '',
            evidence_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(region_id) REFERENCES vision_regions(id) ON DELETE CASCADE,
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_attributes_name_value ON vision_attributes(namespace, name, value)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_attributes_path_generation ON vision_attributes(path, generation)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_embeddings_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            generation INTEGER NOT NULL,
            scope TEXT NOT NULL,
            region_id INTEGER,
            model_id TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            runtime TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(region_id) REFERENCES vision_regions(id) ON DELETE CASCADE,
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_embeddings_v2_model ON vision_embeddings_v2(model_id, dim, scope)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_embeddings_v2_path ON vision_embeddings_v2(path, generation)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_captions_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            generation INTEGER NOT NULL,
            provider TEXT NOT NULL,
            model_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            status TEXT NOT NULL,
            caption TEXT NOT NULL DEFAULT '',
            structured_json TEXT NOT NULL DEFAULT '{}',
            search_text TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0,
            error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_captions_v2_model ON vision_captions_v2(model_id, schema_version)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_captions_v2_status ON vision_captions_v2(status)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_artifacts (
            artifact_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            generation INTEGER NOT NULL,
            artifact_type TEXT NOT NULL,
            uri TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'application/json',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            model_id TEXT NOT NULL DEFAULT '',
            privacy_class TEXT NOT NULL DEFAULT 'standard',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(path) REFERENCES records(path) ON DELETE CASCADE
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_artifacts_path_generation ON vision_artifacts(path, generation)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_artifacts_type ON vision_artifacts(artifact_type)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_jobs (
            job_id TEXT PRIMARY KEY,
            requested_by TEXT NOT NULL DEFAULT '',
            request_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            error TEXT,
            stats_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_jobs_status ON vision_jobs(status, priority, created_at)")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS vision_search_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            principal TEXT NOT NULL DEFAULT '',
            query_hash TEXT NOT NULL,
            query_plan_json TEXT NOT NULL DEFAULT '{}',
            result_count INTEGER NOT NULL DEFAULT 0,
            degraded INTEGER NOT NULL DEFAULT 0,
            runtime_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_vision_search_audit_created ON vision_search_audit(created_at)")


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_count(con: sqlite3.Connection, table: str) -> int | None:
    if not _table_exists(con, table):
        return None
    try:
        row = con.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        return int(row["count"] if isinstance(row, sqlite3.Row) else row[0])
    except sqlite3.Error:
        return None


def vision_product_schema_status(db_path: Path) -> dict:
    path = Path(db_path)
    if not path.exists():
        return {
            "schema_version": VISION_PRODUCT_SCHEMA_VERSION,
            "db_exists": False,
            "schema_ready": False,
            "tables": {},
            "counts": {},
        }
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        tables = {name: _table_exists(con, name) for name in VISION_PRODUCT_TABLES}
        counts = {name: _table_count(con, name) for name in VISION_PRODUCT_TABLES}
        return {
            "schema_version": VISION_PRODUCT_SCHEMA_VERSION,
            "db_exists": True,
            "schema_ready": all(tables.values()),
            "tables": tables,
            "counts": counts,
        }
    finally:
        con.close()


def product_schema_report(db_path: Path) -> str:
    status = vision_product_schema_status(db_path)
    return json.dumps(status, ensure_ascii=False, indent=2)
