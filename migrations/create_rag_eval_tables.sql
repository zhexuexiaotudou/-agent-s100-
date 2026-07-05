CREATE TABLE IF NOT EXISTS rag_eval_runs(
  run_id TEXT PRIMARY KEY,
  verdict TEXT NOT NULL,
  case_count INTEGER NOT NULL,
  citation_coverage REAL NOT NULL,
  no_evidence_refusal_rate REAL NOT NULL,
  private_leak_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
