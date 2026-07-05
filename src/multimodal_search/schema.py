from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mm_assets (
  asset_id TEXT PRIMARY KEY,
  source_id TEXT,
  modality TEXT NOT NULL,
  file_type TEXT,
  title_redacted TEXT,
  path_hash TEXT NOT NULL,
  parent_hash TEXT,
  size_bytes INTEGER,
  mtime INTEGER,
  sha256 TEXT,
  privacy_level TEXT NOT NULL DEFAULT 'private_local_only',
  index_status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS mm_text_chunks (
  chunk_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  chunk_index INTEGER,
  text_redacted TEXT,
  page_no INTEGER,
  timestamp_start REAL,
  timestamp_end REAL,
  source_type TEXT,
  token_count INTEGER,
  privacy_level TEXT,
  FOREIGN KEY(asset_id) REFERENCES mm_assets(asset_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS mm_text_chunks_fts
USING fts5(chunk_id UNINDEXED, asset_id UNINDEXED, text_redacted);

CREATE TABLE IF NOT EXISTS mm_media_metadata (
  asset_id TEXT PRIMARY KEY,
  width INTEGER,
  height INTEGER,
  duration_sec REAL,
  codec TEXT,
  exif_json_redacted TEXT,
  dominant_time TEXT,
  gps_redacted TEXT,
  thumbnail_id TEXT,
  FOREIGN KEY(asset_id) REFERENCES mm_assets(asset_id)
);

CREATE TABLE IF NOT EXISTS mm_thumbnails (
  thumbnail_id TEXT PRIMARY KEY,
  asset_id TEXT,
  thumbnail_path TEXT,
  width INTEGER,
  height INTEGER,
  sha256 TEXT,
  generated_at TEXT
);

CREATE TABLE IF NOT EXISTS mm_embeddings (
  embedding_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  chunk_id TEXT,
  modality TEXT NOT NULL,
  model_id TEXT NOT NULL,
  vector_dim INTEGER NOT NULL,
  vector_store_ref TEXT NOT NULL,
  vector_sha256 TEXT,
  normalized INTEGER DEFAULT 1,
  created_at TEXT,
  FOREIGN KEY(asset_id) REFERENCES mm_assets(asset_id)
);

CREATE TABLE IF NOT EXISTS mm_video_keyframes (
  keyframe_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  timestamp_sec REAL,
  thumbnail_id TEXT,
  embedding_id TEXT,
  ocr_chunk_id TEXT,
  created_at TEXT,
  FOREIGN KEY(asset_id) REFERENCES mm_assets(asset_id)
);

CREATE TABLE IF NOT EXISTS mm_search_runs (
  run_id TEXT PRIMARY KEY,
  query_redacted TEXT,
  query_type TEXT,
  modality_filters TEXT,
  retrieval_mode TEXT,
  result_count INTEGER,
  trace_id TEXT,
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
        conn.commit()
    finally:
        conn.close()
