# AI-NAS Next Tasks Model Split 2026-06-23

This file is the handoff plan for continuing after the ten-goal closure gate.
It is written so a weaker model such as DeepSeek can safely continue execution
without redefining the product scope.

## Current Evidence Baseline

Use these files as the current source of truth:

- Ten-goal closure: `tmp/ai_nas_ten_goal_s100p_closure/ten_goal_s100p_closure_gate_latest.json`
- S100P Qwen2.5 acceptance: `tmp/product_guardrail_snapshots/qwen25_ai_nas_acceptance_20260623-121706/qwen25_ai_nas_acceptance.json`
- Product boundary: `docs/ai_nas_product_closure_goal_2026-06-23.md`
- Text route: `docs/qwen25_ai_nas_text_entry_2026-06-23.md`
- Vision route: `docs/ai_nas_official_vision_route_2026-06-23.md`
- Non-long task completion: `docs/ai_nas_non_long_task_completion_2026-06-23.md`

Current state:

- `ok_ai_nas_ten_goal_s100p_closure_gate`: passed.
- `goals_ok`: 10/10.
- S100P model acceptance: passed.
- Active text model: `Qwen2.5-1.5B-Instruct-S100P-official`.
- Active profile: `cache_len_512_chunk_128_q8`.
- 1024 profile status: `blocked_on_current_s100p_common_buffer_allocation`.
- Latest full closure refresh: `2026-06-23T12:17:06+08:00`.

Do not claim full commercial Synology/QNAP parity from this baseline. The
current product is a closed prototype and AI-NAS intelligence layer.

## Finished

These are already closed by explicit gates:

- Goal 1 storage foundation: file browse/upload/download/copy/move/delete, 10k scan, SQLite index, hash/mtime/size, operation log.
- Goal 2 identity and ACL: users, groups, sessions, tokens, directory ACLs, permission-aware storage access.
- Goal 3 recovery: trash, versions, snapshots, restore.
- Goal 4 backup and sync: backup task, incremental copy, restore.
- Goal 5 Web NAS OS: login page, file manager, media, documents, backup, users, system status, AI Copilot, audit entry.
- Goal 6 media center: photo index, timeline, albums, duplicate/similar detection.
- Goal 7 AI-NAS Copilot: document index, search, folder filtering, citation/source-backed Q&A.
- Goal 8 ops: health checks, disk check, alerts, diagnostics.
- Goal 9 app ecosystem: plugin registry/start-stop and protocol adapter records.
- Goal 10 integration: top-level gate requires the prior gates plus S100P Qwen2.5 live acceptance.

## Tasks For GPT-5.5-Class Models

Use a strong model for these. They require architecture judgment, claim control,
or multi-evidence reasoning.

Status as of 2026-06-23: G1-G6 have been completed as planning and policy
documents. DeepSeek-class execution should read these files as constraints, not
rewrite their product/security/release decisions.

Completed deliverables:

- G1: `docs/ai_nas_commercial_parity_architecture.md`
- G2: `docs/ai_nas_permission_threat_model.md`
- G3: `docs/ai_nas_conversation_product_design.md`
- G4: `docs/ai_nas_multimodal_semantics_roadmap.md`
- G5: `docs/ai_nas_release_claim_audit.md`
- G6: `docs/ai_nas_hard_failure_triage_runbook.md`

### G1. Commercial NAS Parity Architecture

Define which parts should be implemented by this project versus delegated to an
existing NAS OS.

Deliverables:

- `docs/ai_nas_commercial_parity_architecture.md`
- A table separating: own implementation, NAS delegated capability, explicit
  non-goal, future plugin.
- Acceptance gate design for RAID, disk health, snapshots, backup, SMB/NFS,
  WebDAV, mobile sync, and user ACL inheritance.

Why strong model:

- Requires product scoping and preventing overclaiming.

Status:

- Completed in `docs/ai_nas_commercial_parity_architecture.md`.

### G2. Real Permission Model And Threat Boundary

Design the production permission contract across Web, API, AI retrieval, SMB/NFS
metadata, and generated evidence reports.

Deliverables:

- `docs/ai_nas_permission_threat_model.md`
- A strict rule: AI answers must never reveal file names, snippets, thumbnails,
  or metadata outside the caller's permission scope.
- New or updated gate proposal for real NAS ACL mapping, not just fixture ACLs.

Why strong model:

- Requires security reasoning and cross-layer invariant design.

Status:

- Completed in `docs/ai_nas_permission_threat_model.md`.

### G3. Conversational Product Design

Turn the current evidence-flow style into a real multi-turn NAS assistant while
preserving grounded citations and action approval.

Deliverables:

- `docs/ai_nas_conversation_product_design.md`
- Conversation state spec.
- Refusal and clarification policy.
- Tool-calling schema for search, summarize, compare, organize, backup, restore,
  and audit.
- Test prompts that include ambiguous, adversarial, and permission-sensitive
  cases.

Why strong model:

- Requires conversation design, safety boundaries, and robust evaluation.

Status:

- Completed in `docs/ai_nas_conversation_product_design.md`.

### G4. Multimodal Semantics Roadmap

Design the path from current YOLO/pHash/local embeddings to production photo and
video semantics.

Deliverables:

- `docs/ai_nas_multimodal_semantics_roadmap.md`
- A roadmap for CLIP-like semantic search, OCR, video-frame indexing, person and
  face privacy boundaries, and location/time/event grouping.
- Explicit privacy policy for people/children/faces.
- Gate definitions for semantic image search and video understanding.

Why strong model:

- Requires balancing model capability, privacy, and product claims.

Status:

- Completed in `docs/ai_nas_multimodal_semantics_roadmap.md`.

### G5. Release Claim Audit

Before any demo, paper, competition packet, or open-source release, audit the
claims against current evidence.

Deliverables:

- `docs/ai_nas_release_claim_audit.md`
- Claim table: claim, evidence path, allowed wording, forbidden wording.
- Final release summary that distinguishes prototype, demo-ready, and production
  claims.

Why strong model:

- Requires source-grounded claim discipline.

Status:

- Completed in `docs/ai_nas_release_claim_audit.md`.

### G6. Hard Failure Triage

Use a strong model when repeated failures involve S100P runtime, common-buffer
allocation, Qwen 1024 profile, OCR wrapper, or service interactions.

Deliverables:

- `docs/ai_nas_hard_failure_triage_runbook.md`
- Root-cause note with commands, logs, and rollback boundary.
- Updated gate only after current evidence proves the fix.

Why strong model:

- Requires debugging across hardware, runtime, service, and product evidence.

Status:

- Completed in `docs/ai_nas_hard_failure_triage_runbook.md`.

## Tasks For DeepSeek-Class Models

These tasks are intentionally mechanical. A weaker model can execute them if it
does not change product claims without stronger-model review.

Status as of the non-long completion pass:

- D2 completed: Web NAS OS tables, filters, loading states, and basic buttons.
- D3 completed: existing-module pages for backup, snapshot/trash, media, ops,
  app ecosystem, audit, users, documents, files, and system status.
- D4 completed for small deterministic local fixtures: document, image, video,
  and OCR-text fixtures are created by the Web OS gate.
- D5 completed for this pass: docs now point to the current non-long completion
  note and latest short gate.
- D6 completed for the available non-long route: the full closure gate refreshed
  Qwen2.5 S100P acceptance at
  `tmp/product_guardrail_snapshots/qwen25_ai_nas_acceptance_20260623-121706/qwen25_ai_nas_acceptance.json`;
  direct read-only SSH capture was attempted but authentication was unavailable
  in BatchMode.
- D7 completed: truthful adapter stubs are exposed as adapter records only.
- Long soak, broad scale tests, 1024-profile promotion, and production
  multimodal gates remain excluded from this pass.

### D1. Keep The Gate Matrix Fresh

Run the existing gates and collect the results.

Commands:

```powershell
$py='C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py scripts\probes\ai_nas_ten_goal_s100p_closure_gate.py
```

Expected:

- `ok_ai_nas_ten_goal_s100p_closure_gate`
- `goals_ok` is 10/10
- `s100p_model_ok` is true

If the gate fails, do not rewrite success criteria. Report the failed goal id
and the JSON path.

### D2. Improve Web NAS OS UI Without Changing Semantics

Allowed work:

- Add tables, filters, loading states, and basic buttons to
  `scripts/probes/nas_web_os_portal.html`.
- Keep existing route names and API contracts.
- Re-run `ai_nas_web_os_gate_probe.py`.

Do not:

- Add fake metrics.
- Remove permission checks.
- Claim production Web OS parity.

Current status:

- Completed in `scripts/probes/nas_web_os_portal.html`.
- Verified by `tmp/nas_web_os_gate_local/web_os_gate_latest.json`
  with `34/34` checks.

### D3. Add CRUD Pages For Existing Modules

Allowed work:

- Expose existing backup, snapshot, media, ops, app ecosystem, and audit module
  data in the portal.
- Use the existing Python stores and server APIs.
- Add focused gate checks for each new page.

Do not:

- Invent new backend semantics without a gate.
- Perform destructive file operations by default.

Current status:

- Completed for existing stores in `scripts/probes/ai_nas_operator_portal_server.py`.
- Verified by the 34-check `ok_nas_web_os_gate` and by the refreshed
  `ok_ai_nas_ten_goal_s100p_closure_gate`.

### D4. Batch Fixture Expansion

Allowed work:

- Add more deterministic fixture files for documents, images, videos, and OCR.
- Keep fixtures small and local under `tmp/`.
- Add JSON summaries to the relevant gate outputs.

Do not:

- Use private real user files in generated reports.
- Treat fixture success as real-world scale proof.

Current status:

- Completed for small local fixtures inside `scripts/probes/ai_nas_web_os_gate_probe.py`.
- Broader scale/endurance fixture expansion remains a future non-long or long-test decision depending on size.

### D5. Documentation Sync

Allowed work:

- Update docs when a gate path or command changes.
- Add a short "latest evidence" section with JSON paths.
- Keep boundary language conservative.

Do not:

- Use words like "production complete", "full NAS replacement", or "commercial
  parity" unless a strong-model audit adds evidence.

Current status:

- Completed for this pass in `docs/ai_nas_non_long_task_completion_2026-06-23.md`.

### D6. Remote Evidence Collection

Allowed work:

- SSH to S100P read-only and collect health/report paths.
- Run Qwen2.5 acceptance through `qwen25_ai_nas_acceptance_packet.py`.
- Copy only generated evidence reports into local `tmp/` mirrors.

Do not:

- Restart services, delete files, move source data, or change systemd units
  without explicit operator approval.

Current status:

- Completed for the available non-long path through the refreshed S100P Qwen2.5
  acceptance packet.
- Direct SSH read-only health capture was attempted and failed with
  `Permission denied (publickey,password)`, so no remote service or filesystem
  operation was performed.

### D7. Mechanical Adapter Stubs

Allowed work:

- Add non-destructive adapter records for SMB/WebDAV/NFS/Docker/plugin catalog.
- Add status pages that display "configured", "missing", or "not implemented".
- Add gates that verify truthful status reporting.

Do not:

- Pretend protocol services are implemented when only the adapter record exists.

Current status:

- Completed in `/api/apps/add-protocol`.
- Adapter records include `implementation_state=adapter_record_only` and
  `protocol_daemon_started=false`.

## Recommended Execution Order

1. DeepSeek: read the six completed GPT-5.5 documents listed above.
2. DeepSeek: run D1 and confirm the baseline is still green.
3. DeepSeek: do D2 and D3 to make the Web NAS OS more usable.
4. DeepSeek: do D4 and D5 to improve evidence coverage and docs.
5. DeepSeek: implement only the mechanical pieces accepted by
   `docs/ai_nas_commercial_parity_architecture.md`,
   `docs/ai_nas_permission_threat_model.md`,
   `docs/ai_nas_conversation_product_design.md`, and
   `docs/ai_nas_multimodal_semantics_roadmap.md`.
6. DeepSeek: use `docs/ai_nas_hard_failure_triage_runbook.md` for hard failures
   and stop before restarts, destructive operations, or gate rewrites.
7. Before any external presentation, re-check wording against
   `docs/ai_nas_release_claim_audit.md`.

## DeepSeek Guardrails

When using DeepSeek, follow these rules:

- Always inspect the latest JSON gate before changing code.
- Prefer small edits and run the exact gate for the touched area.
- Never weaken a gate to make it pass.
- Never replace S100P live evidence with local-only fixture evidence.
- Never call the system a full top-tier NAS replacement unless
  `docs/ai_nas_commercial_parity_architecture.md` and a later release audit
  explicitly allow that wording.
- If a task requires deciding product scope, security policy, privacy policy, or
  release wording, stop and hand it to GPT-5.5-class reasoning.
