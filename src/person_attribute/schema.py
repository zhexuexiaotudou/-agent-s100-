from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS person_attribute_detections (
  id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  keyframe_id TEXT,
  detection_id TEXT,
  modality TEXT NOT NULL,
  bbox_json TEXT NOT NULL,
  upper_color TEXT,
  lower_color TEXT,
  dominant_colors_json TEXT,
  attribute_tags_json TEXT NOT NULL,
  evidence_ref TEXT NOT NULL,
  confidence REAL,
  timestamp_sec REAL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_person_attr_asset ON person_attribute_detections(asset_id);
CREATE INDEX IF NOT EXISTS idx_person_attr_modality ON person_attribute_detections(modality);
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
