from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS auto_organize_plans (
  plan_id TEXT PRIMARY KEY,
  source_root TEXT NOT NULL,
  target_root TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  item_count INTEGER NOT NULL DEFAULT 0,
  approved_by TEXT,
  approval_mode TEXT,
  created_at TEXT NOT NULL,
  approved_at TEXT,
  executed_at TEXT,
  rolled_back_at TEXT
);

CREATE TABLE IF NOT EXISTS auto_organize_items (
  item_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  source_rel TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  source_sha256 TEXT,
  target_category_zh TEXT NOT NULL,
  target_rel TEXT NOT NULL,
  target_hash TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  suggested_filename_zh TEXT NOT NULL,
  final_filename TEXT,
  operation TEXT NOT NULL,
  status TEXT NOT NULL,
  classification_basis_json TEXT NOT NULL,
  naming_basis_json TEXT NOT NULL,
  conflict_policy TEXT NOT NULL,
  rollback_json TEXT,
  created_at TEXT NOT NULL,
  executed_at TEXT,
  FOREIGN KEY(plan_id) REFERENCES auto_organize_plans(plan_id) ON DELETE CASCADE
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
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
