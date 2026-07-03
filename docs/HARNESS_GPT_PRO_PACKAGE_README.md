# AI-NAS Harness Stage 1 GPT Pro Review Package

This package is a self-contained review bundle for GPT Pro. It captures the
Stage 0 and Stage 1 Workspace Harness shadow prototype for the Digua AI-NAS
project.

## Project Boundary

The production path must remain:

`OpenClaw gateway -> Qwen local gateway -> AI-NAS allowlist dispatcher -> gates`

Hard constraints:

- Do not replace OpenClaw.
- Do not replace the Qwen local foreground gateway.
- Do not bypass `ai_nas_allowlisted_tool.sh`.
- Do not introduce arbitrary shell or user-selected script paths.
- Do not modify ports `18888` or `18889`.
- Do not attach Dream7B to the foreground path.
- Cloud calls must receive only public or redacted content.
- Stage 1 must remain default-off and reversible.

## Start Here

Recommended read order:

1. `GPT_PRO_EVALUATION_PROMPT.md`
2. `docs/HARNESS_STAGE1_RESULTS.md`
3. `docs/HARNESS_CURRENT_ASSET_MAP.md`
4. `reports/harness_stage1_gate_report.json`
5. `reports/harness_shadow_probe_latest.json`
6. `config/workspace_registry.yaml`
7. `config/workspace_tool_policy.yaml`
8. `ai_nas_harness/`, `probes/`, and `gates/` source files

## Included Evidence

Stage 1 harness:

- workspace registry and tool policy
- per-workspace prompts
- context builder
- tool exposure filter
- SQLite memory store
- runtime trace writer and schema
- 6-scenario shadow probe
- 5 Stage 1 gates plus combined gate report
- rollback script

Production-context evidence:

- OpenClaw and Qwen service files
- Qwen route policy
- allowlist dispatcher source
- Qwen gateway source
- existing Qwen AI-NAS acceptance result
- existing OpenClaw NAS control gate result
- existing edge/cloud router result

## Current Verified Results

- `ok_harness_shadow_probe`
- `ok_harness_stage1_gates`
- `ok_qwen25_ai_nas_acceptance_packet`
- `ok_qwen25_ai_nas_gateway_turn`
- `ok_ai_nas_openclaw_nas_control_gate`
- `ok_ai_nas_edge_cloud_router`

Context size estimate:

- before: 15749.0 chars
- after: 1470.5 chars
- reduction: about 90.7%

Runtime trace tables were populated:

- `harness_runs`
- `harness_steps`
- `workspace_decisions`
- `tool_calls`
- `policy_denials`
- `memory_reads`
- `gate_results`

## Review Goal

Use this bundle to evaluate whether Stage 1 is sound and what Stage 2 should do
next. The expected Stage 2 direction is a conservative Zleap sidecar experiment
for read-only `nas_search` and `document_rag` only.
