CREATE TABLE IF NOT EXISTS harness_runs (
  run_id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  user_request TEXT NOT NULL,
  selected_workspace TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS harness_steps (
  step_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  step_type TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES harness_runs(run_id)
);

CREATE TABLE IF NOT EXISTS workspace_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  confidence REAL NOT NULL,
  alternatives_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES harness_runs(run_id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  status TEXT NOT NULL,
  args_json TEXT NOT NULL DEFAULT '[]',
  result_json TEXT NOT NULL DEFAULT '{}',
  elapsed_ms REAL,
  dispatcher_used INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES harness_runs(run_id)
);

CREATE TABLE IF NOT EXISTS policy_denials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  requested_args_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES harness_runs(run_id)
);

CREATE TABLE IF NOT EXISTS memory_reads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  memory_type TEXT NOT NULL,
  scope TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  record_count INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES harness_runs(run_id)
);

CREATE TABLE IF NOT EXISTS gate_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  gate_id TEXT NOT NULL,
  verdict TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES harness_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_harness_runs_workspace ON harness_runs(selected_workspace);
CREATE INDEX IF NOT EXISTS idx_tool_calls_workspace_tool ON tool_calls(workspace_id, tool_id);
CREATE INDEX IF NOT EXISTS idx_policy_denials_workspace_tool ON policy_denials(workspace_id, tool_id);
