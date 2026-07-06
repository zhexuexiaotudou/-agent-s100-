from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ai_space_asset_views (
  asset_id TEXT PRIMARY KEY,
  modality TEXT NOT NULL,
  title_redacted TEXT,
  asset_kind TEXT,
  capture_time TEXT,
  time_bucket TEXT,
  object_labels_json TEXT,
  person_attrs_json TEXT,
  ocr_status TEXT,
  transcript_status TEXT,
  category_names_json TEXT,
  summary_redacted TEXT,
  privacy_level TEXT,
  evidence_refs_json TEXT,
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
        conn.commit()
    finally:
        conn.close()
