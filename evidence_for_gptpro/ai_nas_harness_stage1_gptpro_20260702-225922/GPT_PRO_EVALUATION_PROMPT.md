# GPT Pro Evaluation Prompt

You are a senior AI product architect, edge AI/NAS systems engineer, security
reviewer, and deployment planner. I am giving you a packaged evidence bundle
for the Digua AI-NAS Workspace Harness Stage 0 + Stage 1 shadow prototype.

Please evaluate the package rigorously and propose the next implementation
roadmap. Treat files in the package as evidence. Distinguish clearly between
claims directly supported by package evidence and your own inference.

## Project Context

Current production mainline:

`OpenClaw gateway -> Qwen local gateway -> AI-NAS allowlist dispatcher -> gates`

Hard constraints:

1. Do not replace OpenClaw.
2. Do not replace the local Qwen foreground gateway.
3. Do not bypass the existing allowlist dispatcher.
4. Do not introduce arbitrary shell execution or user-selected script paths.
5. Do not modify ports `18888` or `18889`.
6. Do not attach Dream7B to the foreground product path.
7. Cloud calls may receive only public or redacted content.
8. Destructive/write actions must require approval.
9. Stage 1 must remain default-off and one-command reversible.

The Stage 1 implementation introduces a lightweight Workspace Harness shadow
prototype:

- `main_router`
- `nas_search`
- `nas_action`
- `media_photo`
- `document_rag`
- `ops_recovery`
- `web_cloud_research`
- `admin_audit`

Each workspace has a prompt file, default model, cloud/write permissions,
approval-required tools, allowed tool IDs, data scope, and trace requirements.

## Files To Read First

Read these in order:

1. `README_FOR_GPT_PRO.md`
2. `docs/HARNESS_STAGE1_RESULTS.md`
3. `docs/HARNESS_CURRENT_ASSET_MAP.md`
4. `reports/harness_stage1_gate_report.json`
5. `reports/harness_shadow_probe_latest.json`
6. `config/workspace_registry.yaml`
7. `config/workspace_tool_policy.yaml`
8. `ai_nas_harness/context_builder.py`
9. `ai_nas_harness/tool_filter.py`
10. `ai_nas_harness/runtime_trace_writer.py`
11. `ai_nas_harness/memory_store.py`
12. `probes/harness_shadow_probe.py`
13. `gates/*.py`
14. `scripts/disable_harness_shadow.sh`

Also inspect production-context evidence:

- `production_context/configs/systemd/openclaw-gateway.service`
- `production_context/configs/systemd/qwen25-local-openai-gateway.service`
- `production_context/configs/qwen25_official_route_policy.json`
- `production_context/scripts/qwen25_openai_gateway.py`
- `production_context/scripts/probes/ai_nas_allowlisted_tool.sh`
- `existing_gate_evidence/*`

## What I Need From You

### 1. Current-State Assessment

Evaluate whether Stage 0 and Stage 1 are actually implemented, not just
documented. Check:

- asset map completeness;
- workspace registry completeness;
- policy/tool partition correctness;
- context builder behavior;
- tool filter safety;
- runtime trace completeness;
- memory boundary design;
- shadow probe coverage;
- gate coverage;
- rollback behavior;
- existing gate evidence.

Give a verdict:

- `ready_for_stage2_sidecar`
- `ready_with_fixes`
- `not_ready`

Explain the reasons.

### 2. Boundary And Security Review

Audit whether the implementation respects the hard constraints:

- OpenClaw/Qwen/dispatcher mainline not replaced;
- dispatcher not bypassed;
- no arbitrary shell/script path;
- workspace tools are isolated;
- unauthorized tools are denied and logged;
- destructive actions require approval;
- cloud egress is redacted;
- Dream7B is not foreground;
- `18888/18889` are protected;
- rollback is plausible.

Identify any design that looks safe in shadow mode but would become unsafe in
Stage 2 or Stage 3.

### 3. Engineering Quality Review

Review code and data design:

- Is JSON-compatible YAML acceptable here?
- Is SQLite memory/trace enough for Stage 1?
- Are trace tables sufficient for debugging and audit?
- Are gate checks too narrow or appropriately scoped?
- Are report schemas useful enough for product QA?
- Is context-size measurement meaningful or only approximate?
- Does policy duplication between registry and policy create maintenance risk?
- What tests should be added before Stage 2?

### 4. Product Impact

Assess likely product improvements:

- lower tool-selection confusion;
- smaller prompts/context;
- safer NAS search and action boundary;
- better auditability;
- better cloud/privacy governance;
- stronger path from demo to shippable AI-NAS product.

Also identify user-experience risks:

- wrong workspace routing;
- missing tools because of over-minimization;
- more latency;
- denial messages that confuse users;
- approval flow friction;
- cloud redaction over-redacts useful context.

### 5. Stage 2 Zleap Sidecar Plan

Design a conservative Stage 2 sidecar experiment. Requirements:

- Only read-only `nas_search` and `document_rag` are eligible.
- Do not enable write/destructive actions.
- Do not enable `ops_recovery` drills.
- Do not enable `web_cloud_research` production cloud calls yet.
- Do not route Dream7B foreground.
- Keep OpenClaw/Qwen/dispatcher as the production path.
- Use the harness only as a sidecar/shadow or controlled read-only router.

Please provide:

- target architecture;
- exact request flow;
- components to modify;
- new files/configs/gates to add;
- rollout sequence;
- rollback sequence;
- metrics to collect;
- acceptance gates;
- stop conditions.

### 6. Stage 2 Gate Design

Propose concrete gates for Stage 2. At minimum cover:

- sidecar disabled-by-default gate;
- read-only route parity gate;
- no-write/no-delete proof gate;
- dispatcher-only execution gate;
- workspace route accuracy gate;
- tool exposure regression gate;
- trace completeness gate;
- latency overhead gate;
- rollback gate;
- user-facing denial-message gate.

For each gate, give:

- gate ID;
- purpose;
- input evidence;
- pass/fail criteria;
- report fields;
- whether it can run locally or must run on S100P.

### 7. Roadmap Beyond Stage 2

Give a staged roadmap:

- Stage 2: read-only sidecar;
- Stage 3: approval-backed `nas_action`;
- Stage 4: cloud research with redaction and audit;
- Stage 5: production gate integration and release closure.

For each stage, give:

- scope;
- non-goals;
- required gates;
- deployment difficulty;
- estimated risk;
- rollback;
- what evidence must be collected before advancing.

### 8. Final Output Format

Return your answer in Chinese.

Use this structure:

1. 总体结论
2. 证据充分性
3. 当前实现的优点
4. 当前实现的问题和风险
5. 是否可以进入 Stage 2
6. Stage 2 Zleap sidecar 详细推进路线
7. Stage 2 gate 清单
8. Stage 3-5 路线图
9. 最优先的 10 个行动项
10. 暂时不要做的事项

Be critical. If the package evidence is insufficient, say exactly what is
missing and what command/report/gate would prove it.
