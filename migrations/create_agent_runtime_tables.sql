-- Digua Agent Runtime v1 local tables. Raw private content is intentionally
-- excluded; source paths are represented as hashes in exported rows.
CREATE TABLE IF NOT EXISTS agent_runtime_context_packs(
  pack_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  workspace TEXT NOT NULL,
  user_id_hash TEXT NOT NULL,
  evidence_refs_json TEXT NOT NULL,
  token_estimate INTEGER NOT NULL,
  private_leak_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_runtime_traces(
  trace_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  trace_hash TEXT NOT NULL,
  private_leak_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
