from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS smart_categories (
  category_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  name_zh TEXT,
  name_en TEXT,
  icon TEXT,
  description TEXT,
  rule_json TEXT NOT NULL,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS smart_category_memberships (
  category_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  score REAL,
  matched_by_json TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(category_id, asset_id)
);

CREATE TABLE IF NOT EXISTS smart_asset_names (
  asset_id TEXT PRIMARY KEY,
  display_name_zh TEXT NOT NULL,
  suggested_filename_zh TEXT NOT NULL,
  naming_reason_json TEXT NOT NULL,
  risk_flags_json TEXT NOT NULL,
  source_title_redacted TEXT,
  updated_at TEXT NOT NULL
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def migrate(db_path: str | Path) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        for column, decl in {
            "name_zh": "TEXT",
            "name_en": "TEXT",
            "icon": "TEXT",
        }.items():
            try:
                conn.execute(f"ALTER TABLE smart_categories ADD COLUMN {column} {decl}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
    finally:
        conn.close()
