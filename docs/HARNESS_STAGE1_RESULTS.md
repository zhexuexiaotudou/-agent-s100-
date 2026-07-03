# AI-NAS Workspace Harness Stage 1 Results

Generated on 2026-07-02 from the current `F:\Project\Digua` worktree.

## Verdict

Stage 0 and Stage 1 shadow prototype are implemented and verified locally.
The harness remains default-off and does not replace the production path:
OpenClaw -> Qwen local gateway -> AI-NAS allowlist dispatcher -> existing
probes/gates.

## What Changed

- Added Stage 0 asset map: `docs/HARNESS_CURRENT_ASSET_MAP.md`.
- Added workspace registry: `config/workspace_registry.yaml`.
- Added workspace tool policy: `config/workspace_tool_policy.yaml`.
- Added workspace prompt files under `config/prompts/`.
- Added harness package:
  - `ai_nas_harness/config_io.py`
  - `ai_nas_harness/context_builder.py`
  - `ai_nas_harness/tool_filter.py`
  - `ai_nas_harness/runtime_trace_writer.py`
  - `ai_nas_harness/memory_store.py`
- Added trace schema: `db/runtime_trace_schema.sql`.
- Added shadow probe: `probes/harness_shadow_probe.py`.
- Added Stage 1 gates:
  - `gates/workspace_isolation_gate.py`
  - `gates/tool_exposure_minimization_gate.py`
  - `gates/memory_boundary_gate.py`
  - `gates/runtime_trace_completeness_gate.py`
  - `gates/cloud_egress_redaction_gate.py`
  - `gates/run_harness_stage1_gates.py`
- Added rollback script: `scripts/disable_harness_shadow.sh`.

## What Did Not Change

- Did not modify `configs/systemd/openclaw-gateway.service`.
- Did not modify `configs/systemd/qwen25-local-openai-gateway.service`.
- Did not modify `scripts/qwen25_openai_gateway.py`.
- Did not modify `scripts/probes/ai_nas_allowlisted_tool.sh`.
- Did not modify Dream7B service configs or ports `18888` / `18889`.
- Did not attach Dream7B to any foreground workspace.
- Did not add arbitrary script-path execution.

Rollback verification confirmed:

- `AI_NAS_HARNESS_SHADOW=0`
- production route: `openclaw-gateway:8765 -> qwen25-local-openai-gateway:18080 -> ai_nas_allowlisted_tool.sh`
- protected ports unchanged: `18888,18889`
- env file: `tmp/harness_shadow.env`

## Gates Passed

Stage 1 combined gate report:
`reports/harness_stage1_gate_report.json`

| Gate | Verdict | Checks |
| --- | --- | ---: |
| `workspace_isolation_gate` | `ok_workspace_isolation_gate` | 81/81 |
| `tool_exposure_minimization_gate` | `ok_tool_exposure_minimization_gate` | 37/37 |
| `memory_boundary_gate` | `ok_memory_boundary_gate` | 11/11 |
| `runtime_trace_completeness_gate` | `ok_runtime_trace_completeness_gate` | 19/19 |
| `cloud_egress_redaction_gate` | `ok_cloud_egress_redaction_gate` | 11/11 |

Combined verdict: `ok_harness_stage1_gates`.

Existing AI-NAS gates rechecked:

| Existing gate | Verdict | Evidence |
| --- | --- | --- |
| Qwen AI-NAS acceptance packet | `ok_qwen25_ai_nas_acceptance_packet` | `tmp/harness_existing_gates/qwen_acceptance/qwen25_ai_nas_acceptance_latest.json` |
| Qwen gateway turn | `ok_qwen25_ai_nas_gateway_turn` | `/mnt/nas/openclaw/reports/qwen25_gateway/qwen25_gateway_turn_20260702-225126-350406/qwen25_gateway_turn.json` |
| OpenClaw NAS control gate | `ok_ai_nas_openclaw_nas_control_gate` | `tmp/harness_existing_gates/openclaw/openclaw_nas_control_gate_latest.json`, 10/10 |
| Edge/cloud router | `ok_ai_nas_edge_cloud_router` | `tmp/harness_existing_gates/edge_cloud/edge_cloud_router_20260702-224942-839120/edge_cloud_router.json` |

## Shadow Probe

Shadow probe report:
`reports/harness_shadow_probe_latest.json`

Verdict: `ok_harness_shadow_probe`

| Scenario | Workspace | Exposed | Denied | Context before | Context after |
| --- | --- | ---: | ---: | ---: | ---: |
| `nas_search_read_only` | `nas_search` | 1 | 1 | 15748 | 1397 |
| `nas_denied_acl_search` | `nas_search` | 1 | 1 | 15752 | 1405 |
| `nas_destructive_action_requires_approval` | `nas_action` | 2 | 1 | 15735 | 1447 |
| `document_report_generation` | `document_rag` | 2 | 1 | 15733 | 1512 |
| `web_cloud_research_redacted` | `web_cloud_research` | 2 | 1 | 15786 | 1486 |
| `ops_health_check` | `ops_recovery` | 2 | 1 | 15740 | 1576 |

Average context size:

- before: 15749.0 chars, all 78 catalog tools visible baseline
- after: 1470.5 chars, selected workspace tools only
- reduction: about 90.7%

## Runtime Trace

Trace DB:
`reports/harness_shadow_probe_20260702-225400-128474/harness_runtime_trace.sqlite3`

| Table | Rows |
| --- | ---: |
| `harness_runs` | 6 |
| `harness_steps` | 6 |
| `workspace_decisions` | 6 |
| `tool_calls` | 16 |
| `policy_denials` | 7 |
| `memory_reads` | 6 |
| `gate_results` | 6 |

All tool call records preserve the dispatcher boundary.

## Denied Action Examples

- `nas_search` denied `ai_nas_action_execute_copy`: `tool_not_allowed_in_workspace`.
- `nas_search` denied `ai_nas_audit_trail_contract`: `tool_not_allowed_in_workspace`.
- `nas_action` denied `ai_nas_action_execute_copy`: `approval_required`.
- `nas_action` denied `ai_nas_file_search`: `tool_not_allowed_in_workspace`.
- `document_rag` denied `ai_nas_photo_semantic_search`: `tool_not_allowed_in_workspace`.
- `web_cloud_research` denied `ai_nas_file_search`: `tool_not_allowed_in_workspace`.
- `ops_recovery` denied `dream7b_perf_identity`: `tool_not_allowed_in_workspace`.

## Cloud Redaction Example

Input:

`Compare public AI-NAS market trends; redact my invoice, family photo, and /mnt/nas/Personal paths first.`

Egress preview:

`Compare public AI-NAS market trends; redact my [REDACTED_PRIVATE_NAS_CONTEXT], [REDACTED_PRIVATE_NAS_CONTEXT] photo, and [REDACTED_PRIVATE_NAS_CONTEXT]/Personal paths first.`

Redacted terms:

- `/mnt/nas`
- `family`
- `invoice`

`contains_private_terms_after_redaction=false`.

## Rollback Test Result

Command used on this Windows host:

`F:\Program\Git\bin\bash.exe scripts/disable_harness_shadow.sh`

Result:

- `harness_shadow_disabled=true`
- `AI_NAS_HARNESS_SHADOW=0`
- production route unchanged
- protected ports unchanged

On S100P/Linux, the same script can be run as:

`bash scripts/disable_harness_shadow.sh`

## Recommendation For Stage 2 Zleap Sidecar Experiment

Proceed only as a sidecar, not as a production replacement.

Stage 2 scope should be:

- enable workspace routing for read-only `nas_search` and `document_rag` only;
- keep OpenClaw/Qwen/dispatcher unchanged;
- require `AI_NAS_HARNESS_SHADOW=1` for any non-dry-run sidecar call;
- keep write actions, recovery drills, cloud routing and Dream7B out of Stage 2 foreground;
- add a Zleap sidecar gate that compares direct Qwen+dispatcher output against harness-routed output on the same read-only prompts;
- rollback by setting `AI_NAS_HARNESS_SHADOW=0` and removing the sidecar from the caller path.

Do not move `nas_action`, `ops_recovery`, or `web_cloud_research` to production
until approval tokens, redaction audit logs, and user-facing failure states are
covered by gates.
