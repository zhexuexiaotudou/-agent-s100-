from __future__ import annotations

import sqlite3
from pathlib import Path

from .labels import alias_rows


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mm_yolo_assets (
  asset_id TEXT PRIMARY KEY,
  modality TEXT NOT NULL,
  title_redacted TEXT,
  file_type TEXT,
  path_hash TEXT NOT NULL,
  size_bytes INTEGER,
  mtime INTEGER,
  privacy_level TEXT NOT NULL DEFAULT 'private_local_only',
  index_status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS mm_yolo_models (
  model_id TEXT PRIMARY KEY,
  model_name TEXT NOT NULL,
  model_family TEXT NOT NULL,
  backend TEXT NOT NULL,
  runtime_target TEXT NOT NULL,
  input_size TEXT,
  label_set TEXT,
  model_path_hash TEXT,
  weights_committed_to_repo INTEGER DEFAULT 0,
  local_only INTEGER DEFAULT 1,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS mm_yolo_detections (
  detection_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  keyframe_id TEXT,
  modality TEXT NOT NULL,
  label TEXT NOT NULL,
  label_zh TEXT,
  confidence REAL NOT NULL,
  bbox_x1 REAL,
  bbox_y1 REAL,
  bbox_x2 REAL,
  bbox_y2 REAL,
  bbox_units TEXT DEFAULT 'normalized_0_1',
  image_width INTEGER,
  image_height INTEGER,
  timestamp_sec REAL,
  model_id TEXT NOT NULL,
  model_backend TEXT NOT NULL,
  evidence_ref TEXT NOT NULL,
  trace_id TEXT,
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_mm_yolo_asset ON mm_yolo_detections(asset_id);
CREATE INDEX IF NOT EXISTS idx_mm_yolo_label ON mm_yolo_detections(label);
CREATE INDEX IF NOT EXISTS idx_mm_yolo_conf ON mm_yolo_detections(confidence);

CREATE TABLE IF NOT EXISTS mm_yolo_label_aliases (
  alias TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  language TEXT DEFAULT 'zh-CN'
);

CREATE TABLE IF NOT EXISTS mm_video_keyframes (
  keyframe_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  timestamp_sec REAL NOT NULL,
  thumbnail_id TEXT,
  frame_hash TEXT,
  yolo_index_status TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS mm_search_results (
  run_id TEXT,
  rank INTEGER,
  asset_id TEXT,
  chunk_id TEXT,
  keyframe_id TEXT,
  score REAL,
  score_components_json TEXT,
  evidence_ref TEXT,
  retrieval_method TEXT,
  PRIMARY KEY(run_id, rank)
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
        conn.executemany(
            "INSERT OR REPLACE INTO mm_yolo_label_aliases(alias,label,language) VALUES(:alias,:label,:language)",
            alias_rows(),
        )
        conn.commit()
    finally:
        conn.close()
