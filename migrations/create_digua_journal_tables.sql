PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS journal_schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal_events (
  event_id TEXT PRIMARY KEY,
  event_ts TEXT NOT NULL,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  project_id TEXT NOT NULL,
  folder_hash TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  raw_content_stored INTEGER NOT NULL DEFAULT 0,
  denied INTEGER NOT NULL DEFAULT 0,
  token_counts_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS journal_events_fts USING fts5(
  event_id UNINDEXED,
  title,
  summary,
  project_id,
  source
);

CREATE TABLE IF NOT EXISTS journal_manual_entries (
  entry_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  event_id TEXT,
  FOREIGN KEY(event_id) REFERENCES journal_events(event_id)
);

CREATE TABLE IF NOT EXISTS journal_project_map (
  project_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  folder_hashes_json TEXT NOT NULL,
  rule_version TEXT NOT NULL,
  manual_override INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal_summary_runs (
  summary_id TEXT PRIMARY KEY,
  period_type TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  markdown TEXT NOT NULL,
  event_count INTEGER NOT NULL,
  manual_entry_count INTEGER NOT NULL,
  local_qwen_used INTEGER NOT NULL DEFAULT 1,
  cloud_used INTEGER NOT NULL DEFAULT 0,
  token_trace_id TEXT NOT NULL,
  hallucinated_event_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal_exports (
  export_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  export_type TEXT NOT NULL,
  period_type TEXT NOT NULL,
  project_id TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  private_leak_count INTEGER NOT NULL DEFAULT 0,
  redaction_lookup_exported INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS journal_token_privacy_traces (
  trace_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  route TEXT NOT NULL,
  cloud_allowed INTEGER NOT NULL DEFAULT 0,
  prompt_tokens INTEGER NOT NULL,
  evidence_tokens INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  redaction_count INTEGER NOT NULL,
  private_leak_count INTEGER NOT NULL,
  metadata_json TEXT NOT NULL
);

INSERT OR IGNORE INTO journal_schema_version(version, applied_at)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
