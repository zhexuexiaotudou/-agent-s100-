from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS media_transcripts (
  transcript_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  modality TEXT NOT NULL,
  language TEXT,
  backend TEXT,
  model_name TEXT,
  duration_sec REAL,
  transcript_redacted TEXT,
  srt_path TEXT,
  vtt_path TEXT,
  evidence_ref TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  cloud_used INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media_transcript_segments (
  segment_id TEXT PRIMARY KEY,
  transcript_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  start_sec REAL NOT NULL,
  end_sec REAL NOT NULL,
  text_redacted TEXT NOT NULL,
  confidence REAL,
  evidence_ref TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS media_transcript_segments_fts
USING fts5(segment_id UNINDEXED, asset_id UNINDEXED, text_redacted);
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
