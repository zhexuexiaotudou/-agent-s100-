# Digua Journal Production Architecture

Digua Journal is implemented as a local-first OpenClaw default-service extension. It adds a SQLite-backed workspace journal, readonly collectors, project classification, period summaries, and safe Markdown/JSON exports without replacing OpenClaw, replacing Qwen, changing service ports, or granting Qwen tool execution authority.

## Runtime Shape

- OpenClaw remains the user-facing service surface.
- Qwen remains a local summarization/classification model only.
- Journal state is stored in SQLite through `src/digua_journal/journal_db.py`.
- The route adapter is `src/openclaw/routes/journal_routes.py`.
- The page shell is `web/digua_journal.html` with static CSS/JS under `web/static/`.
- Cloud generation is disabled in `configs/journal_feature_flags.json`.

## Data Model

The migration `migrations/create_digua_journal_tables.sql` creates:

- `journal_events`
- `journal_events_fts`
- `journal_manual_entries`
- `journal_project_map`
- `journal_summary_runs`
- `journal_exports`
- `journal_token_privacy_traces`

Events store only redacted titles, summaries, evidence references, token counts, and metadata. Raw private content is not stored.

## Collectors

The production package includes readonly collectors for:

- NAS index diffs
- OpenClaw activity
- Workspace Harness traces
- Document/RAG citation metadata
- Gate/report metadata
- Token-budget route metadata
- Copy-route readonly metadata

The generated 21040 and 21050 gates use redacted sample events and do not perform real NAS write actions.

## Safety Boundaries

- No real NAS delete, move, rename, chmod, or uncontrolled write action.
- No raw private path in exportable reports.
- No cloud private egress.
- No desktop screenshot, keyboard tracking, mouse tracking, or employee monitoring.
- No Qwen tool execution authority.
- No changes to ports `8765`, `18080`, `18888`, or `18889`.

## Deployment Boundary

This repository change prepares and verifies the local production package. It does not SSH into S100P and does not mutate live systemd units. S100P rollout should be a separate operator-approved apply step using the generated gates and rollback script.
