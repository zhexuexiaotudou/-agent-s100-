# 090 Digua Journal Audit

- Repo state is dirty, so repo_merged is false for this audit even though live rollout evidence exists.

| field | value |
| --- | --- |
| generated_at | 2026-07-05T13:44:26+08:00 |
| production_package_ready | True |
| repo_merged | False |
| live_s100p_rollout | True |
| journal_workspace | tmp/digua_journal/digua_journal.sqlite3 |
| sqlite_migration | reports/21020_journal_db_migration_gate.json |
| collectors | reports/21040_nas_index_diff_collector_gate.json and reports/21050_journal_system_collectors_gate.json |
| manual_entry | reports/21060_journal_manual_entry_gate.json |
| project_classifier | reports/21070_journal_project_classifier_gate.json |
| period_summaries | reports/21080_journal_period_summary_engine_gate.json |
| openclaw_page_api | reports/21100_openclaw_journal_page_api_gate.json |
| markdown_export | reports/21110_journal_export_gate.json |
| token_privacy_trace | reports/21090_journal_token_privacy_trace_gate.json |
