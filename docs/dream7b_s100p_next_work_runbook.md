# Dream7B S100P Next Work Runbook

This is the execution path for the next report and demo cycle.

## 0. Final Goal And Current Status

Final goal: converge the project into a demonstrable, repeatable, and
deliverable low-cost AI-NAS local intelligence layer.

- Route A is the product route:
  `OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF`.
- Route B is isolated BPU model-runtime R&D. It keeps the queue-batch baseline
  intact and only promotes a candidate after quality, latency, and rollback
  gates pass.

Latest goal status packet:

```text
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_goal_status_packet_20260622-194351/dream7b_ai_nas_goal_status_packet.json
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_goal_status_packet_20260622-194351/dream7b_ai_nas_goal_status_packet.md
```

Latest acceptance packet:

```text
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_acceptance_packet_20260622-194358/dream7b_ai_nas_acceptance_packet.json
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_acceptance_packet_20260622-194358/dream7b_ai_nas_acceptance_packet.md
```

Latest final goal audit:

```text
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_final_goal_audit_20260622-194358/dream7b_ai_nas_final_goal_audit.json
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_final_goal_audit_20260622-194358/dream7b_ai_nas_final_goal_audit.md
```

Latest delivery manifest:

```text
LATEST:/mnt/nas/openclaw/reports/models/dream7b_ai_nas_delivery_manifest_*/dream7b_ai_nas_delivery_manifest.json
LATEST:/mnt/nas/openclaw/reports/models/dream7b_ai_nas_delivery_manifest_*/dream7b_ai_nas_delivery_manifest.md
```

Latest post-reboot resume runner:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_reboot_resume_runner_20260622-193506/dream7b_bpu_quality_post_reboot_resume_runner.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_reboot_resume_runner_20260622-193506/dream7b_bpu_quality_post_reboot_resume_runner.md
```

Current status:

- `verdict=ready_route_a_blocked_route_b_goal_status`
- `goal_complete=false`
- Acceptance packet verdict is
  `partial_dream7b_ai_nas_acceptance_packet_route_a_ready_route_b_blocked`:
  Route A is demo-deliverable, Route B is isolated and blocked, and the full
  goal is not complete.
- Final goal audit verdict is
  `partial_dream7b_ai_nas_final_goal_audit_route_a_ready_route_b_blocked`:
  6 of 9 full-goal requirements pass, 3 are blocked, and 0 fail. The blocked
  requirements are `route_b_capacity_ready_after_reboot`,
  `route_b_post_compile_quality_latency_rollback_gates`, and
  `final_goal_complete`.
- Delivery manifest verdict is
  `partial_dream7b_ai_nas_delivery_manifest_route_a_ready_route_b_blocked`:
  all 35 release files are present, the NAS readback passed, Route A is
  package-ready for demo, and Route B remains blocked by capacity and
  promotion gates.
- Route A is `ready_for_demo`: 18789 and 18888 are live, OpenClaw is live, and
  the fast-path/SLO/OpenClaw entry plus AI-NAS demo-readiness reports are
  accepted. The latest Route A quality-boundary packet also passed: fixed
  ready/identity/local-status prompts returned through fast paths in <=2.713 ms
  with `backend_invoked=false`, while one generic resident generation was
  recorded as a 6688.118 ms boundary with `promotion_claim=false`.
- Route B is `candidate_preflight_done_capacity_blocked`: candidate order,
  state-dict preflight, capacity audit, and admission guard are in place, but
  compile remains blocked until Windows commit capacity is raised and the
  capacity/preflight gates are rerun. A separate promotion gate is now also in
  place and remains blocked until post-compile logits, Chinese generation,
  same-workload, and rollback evidence pass. The current rollback report proves
  the production path is unchanged and seq16 baselines are still present, but it
  remains blocked because the rank-1 candidate artifact and manifest do not yet
  exist.
- Safe compile handoff is now part of goal-status and acceptance. It currently
  reports `operator_may_run_compile=false`, and Route B errors include
  `safe_compile_handoff_not_ready`, so no rank-1 compile command is executable
  yet.
- No compile was started, no service was restarted, and no production write was
  performed by the status packet.
- Latest post-reboot resume runner reports
  `rank1_preflight_matches_candidate=false` because the latest preflight is the
  seq256 state-dict sentinel. After pagefile handoff and reboot, rerun it with
  `--run-preflight` so rank-1 compile admission is based on fresh rank-1
  state-dict and compile-preflight evidence instead of the seq256 exploratory
  preflight.
- The goal status packet resolves changing Route B report inputs through
  `LATEST:/mnt/nas/openclaw/reports/models/...` path specs, so the release
  packet follows the newest capacity, admission, matrix, rollback, and
  promotion evidence instead of a stale hardcoded timestamp.

## 1. Performance And Identity

Run on S100P:

```bash
cd /root/.openclaw/workspace
python3 scripts/probes/dream7b_perf_identity_probe.py \
  --base-url http://127.0.0.1:18888 \
  --model Dream7B-S100P-local
```

For the current OpenClaw default path, also run the short default-latency probe.
It does not override `max_tokens` or diffusion steps:

```bash
python3 scripts/probes/dream7b_openclaw_default_latency_probe.py \
  --base-url http://127.0.0.1:18888 \
  --model Dream7B-S100P-local
```

For the current interactive demo gate, run the fast-path regression and SLO tier
guard from the Windows workspace:

```powershell
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  scripts\probes\dream7b_fast_path_regression_probe.py

& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  scripts\probes\dream7b_first_response_slo_tier_guard.py
```

Latest accepted evidence:

```text
/mnt/nas/openclaw/reports/models/dream7b_fast_path_regression_20260622-174547/dream7b_fast_path_regression.json
/mnt/nas/openclaw/reports/models/dream7b_first_response_slo_tier_guard_20260622-174823/dream7b_first_response_slo_tier_guard.json
```

Required report fields:

- `preflight.model_id_confirmed=true`
- `summary.failed_case_count=0`
- `summary.ttft_ms`
- `summary.prefill_tokens_per_s`
- `summary.decode_tokens_per_s`
- generated response text for the self-introduction prompt

Interactive fast-path acceptance:

- `quick_ready`, `identity_short`, `chinese_identity`, and `chinese_short`
  return through `gateway_fast_*` paths.
- `backend_invoked=false` for the fast-path cases.
- fast-path first content is under 100 ms; latest max was 2.935 ms.
- generic Dream diffusion first-content latency remains tracked separately and
  must not be treated as a true-batch promotion reason.

Interpretation rule: if `stream_supported_case_count=0`, treat `ttft_ms` as first response byte / non-stream upper bound, not native token streaming.

Current default chat route: OpenClaw -> local OpenAI gateway on `127.0.0.1:18888`
-> `diffuse-resident` -> Dream7B GGUF. Queue-batch remains the BPU throughput
baseline and telemetry route, but it is not the single-user chat default.

The local OpenAI gateway must be launched with the tokenizer venv:

```text
/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv/bin/python /root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py
```

Do not replace this with system `python3`. The resident path tokenizes inside
the gateway process, and the system Python tokenizer stack was the root cause of
the 2026-06-22 degraded identity/output regression.

## 2. Resident Gateway Demo

Preflight:

```bash
dream7b-default-status
systemctl is-active dream7b-bpu-batch-queue.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active openclaw-gateway.service
XDG_RUNTIME_DIR=/run/user/0 systemctl --user status --no-pager -l dream7b-local-openai-gateway.service
curl -s http://127.0.0.1:18888/health
curl -s http://127.0.0.1:18789/health
```

OpenClaw entry layer evidence:

```bash
bash /root/.openclaw/workspace/scripts/probes/openclaw_entry_demo_probe.sh \
  /mnt/nas/openclaw/reports/models
```

Latest accepted evidence:

```text
/mnt/nas/openclaw/reports/models/openclaw_entry_demo_20260622-174732/openclaw_entry_demo.json
```

Expected 18888 health fields:

- `backend=diffuse-resident`
- `resident_enabled=true`
- `resident_available=true`
- `resident_running=true` after the first real Dream7B request

Expected service command line:

```text
/mnt/nas/openclaw/runtimes/dream7b-tokenizer-venv/bin/python /root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py
```

Narrative: S100P is the always-on local intelligence gateway. NAS remains storage; Dream7B and OpenClaw provide local reasoning and audited tools.

## 3. OpenClaw AI-NAS Demo

Use fixed tool IDs:

```bash
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_personal_inventory
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_file_search "2024 renovation invoice"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_case_packet "2024 renovation payment contract invoice receipt chat screenshot"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_folder_rag Documents "What payment dates and amounts are in this folder?"
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_duplicate_report
scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_movie_sort_enhanced
```

Acceptance: every action writes Markdown/JSON evidence, keeps source files unchanged, and reports no delete/no move/no overwrite.

Latest Route A demo-readiness evidence:

```text
/mnt/nas/openclaw/reports/models/ai_nas_route_a_demo_readiness_packet_20260622-182319/ai_nas_route_a_demo_readiness_packet.json
```

This packet ran `personal_inventory`, `file_search`, `case_packet`,
`folder_rag`, `duplicate_report`, `movie_sort_enhanced`, and
`edge_cloud_router` through the fixed dispatcher. All seven returned `0`, 18789
and 18888 stayed live before and after, and the cloud router stayed dry-run with
`privacy_query_sent_to_cloud=false`.

## 4. Edge + Cloud Router Demo

Run:

```bash
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py
```

Optional live local classifier:

```bash
python3 scripts/probes/ai_nas_edge_cloud_router_probe.py --use-dream-classifier
```

Demo cases:

- simple local task -> `route=local`
- private NAS/photo/invoice task -> `route=local`
- non-private complex market/story task -> `route=cloud` dry-run

Acceptance: `privacy_query_sent_to_cloud=false`.

## 5. Route B BPU Quality Candidate Gate

Route B is isolated model-runtime R&D. It must not replace the current
OpenClaw -> 18888 -> diffuse-resident product path, and it must not delete or
overwrite the seq16 BPU queue baseline.

Run from the Windows workspace before preparing any BPU quality compile bundle:

```powershell
& 'C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  scripts\probes\dream7b_bpu_quality_candidate_gate.py
```

Latest accepted evidence:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_candidate_gate_20260622-180021/dream7b_bpu_quality_candidate_gate.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_candidate_pack_20260622-180127/dream7b_bpu_quality_candidate_pack.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_candidate_pack_20260622-192033/dream7b_bpu_quality_candidate_pack.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_preflight_runner_20260622-180415/dream7b_bpu_quality_preflight_runner.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_preflight_runner_20260622-180725/dream7b_bpu_quality_preflight_runner.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_preflight_runner_20260622-192044/dream7b_bpu_quality_preflight_runner.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_unblock_plan_20260622-184158/dream7b_bpu_quality_capacity_unblock_plan.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_compile_admission_guard_20260622-184205/dream7b_bpu_quality_compile_admission_guard.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_operator_handoff_20260622-185400/dream7b_bpu_quality_capacity_operator_handoff.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_post_reboot_verifier_20260622-185407/dream7b_bpu_quality_capacity_post_reboot_verifier.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_unblock_plan_20260622-190943/dream7b_bpu_quality_capacity_unblock_plan.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_unblock_plan_20260622-192703/dream7b_bpu_quality_capacity_unblock_plan.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_unblock_plan_20260622-193508/dream7b_bpu_quality_capacity_unblock_plan.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_compile_admission_guard_20260622-190944/dream7b_bpu_quality_compile_admission_guard.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_compile_admission_guard_20260622-192233/dream7b_bpu_quality_compile_admission_guard.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_compile_admission_guard_20260622-192704/dream7b_bpu_quality_compile_admission_guard.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_compile_admission_guard_20260622-193509/dream7b_bpu_quality_compile_admission_guard.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_post_reboot_verifier_20260622-190941/dream7b_bpu_quality_capacity_post_reboot_verifier.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_post_reboot_verifier_20260622-192702/dream7b_bpu_quality_capacity_post_reboot_verifier.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_capacity_post_reboot_verifier_20260622-193506/dream7b_bpu_quality_capacity_post_reboot_verifier.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_reboot_resume_runner_20260622-193506/dream7b_bpu_quality_post_reboot_resume_runner.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_safe_compile_handoff_20260622-193956/dream7b_bpu_quality_safe_compile_handoff.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_logits_diagnostics_20260622-190352/dream7b_bpu_quality_logits_diagnostics.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_generation_quality_20260622-190352/dream7b_bpu_quality_generation_quality.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_same_workload_compare_20260622-190352/dream7b_bpu_quality_same_workload_compare.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_compile_validation_matrix_20260622-190401/dream7b_bpu_quality_post_compile_validation_matrix.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_compile_validation_matrix_20260622-190945/dream7b_bpu_quality_post_compile_validation_matrix.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_compile_validation_matrix_20260622-192240/dream7b_bpu_quality_post_compile_validation_matrix.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_compile_validation_matrix_20260622-192705/dream7b_bpu_quality_post_compile_validation_matrix.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_post_compile_validation_matrix_20260622-193510/dream7b_bpu_quality_post_compile_validation_matrix.json
/mnt/nas/openclaw/reports/models/ai_nas_route_a_demo_readiness_packet_20260622-182319/ai_nas_route_a_demo_readiness_packet.json
/mnt/nas/openclaw/reports/models/dream7b_route_a_quality_boundary_packet_20260622-183931/dream7b_route_a_quality_boundary_packet.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_rollback_report_20260622-183248/dream7b_bpu_quality_rollback_report.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_promotion_gate_20260622-190407/dream7b_bpu_quality_promotion_gate.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_promotion_gate_20260622-190945/dream7b_bpu_quality_promotion_gate.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_promotion_gate_20260622-192245/dream7b_bpu_quality_promotion_gate.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_promotion_gate_20260622-192705/dream7b_bpu_quality_promotion_gate.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_promotion_gate_20260622-193510/dream7b_bpu_quality_promotion_gate.json
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_goal_status_packet_20260622-194351/dream7b_ai_nas_goal_status_packet.json
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_acceptance_packet_20260622-194358/dream7b_ai_nas_acceptance_packet.json
/mnt/nas/openclaw/reports/models/dream7b_ai_nas_final_goal_audit_20260622-194358/dream7b_ai_nas_final_goal_audit.json
```

Current decision:

- Product chat stays on `OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF`.
- BPU stays as queue-batch throughput and telemetry baseline.
- Route A quality boundary is now explicit: fast-path identity/status/readiness
  is demo-ready, while generic resident generation is tracked as a latency and
  quality boundary rather than a promotion claim.
- The gate admits only prepare/verify work: compile bundle planning, parameter
  support checks, and a separate compile-capacity gate.
- This gate does not admit HBM compilation, service replacement, 18888 changes,
  or deletion of seq16 artifacts.
- The compiler and wrappers now support `--lm-head-w-bits` / `-LmHeadWBits`,
  so `lm_head` can be tested at q16 while keeping the surrounding segment q8.

Candidate order:

1. `seg27_28_lmheadq16_last_token_sentinel`: smallest q8 segment plus q16
   `lm_head` last-token sentinel.
2. `seg21_28_lateq16_quality_set`: q16 late-layer repair set for `seg21_24`,
   `seg24_26`, and `seg26_28`.
3. `seg27_28_seq128_lmheadq16_state_dict_sentinel`: first larger-window
   parameterization probe, not a full seq128 HBM set.
4. `seg27_28_seq256_lmheadq16_state_dict_sentinel`: second larger-window
   parameterization probe for seq256 feasibility, not a full seq256 HBM set.

Current preflight status:

- `seg27_28_lmheadq16_last_token_sentinel` state-dict report passed:
  segment `27:28`, tensor count `14`, `seq_len=16`, `lm_head_w_bits=16`.
- `seg21_28_lateq16_quality_set` state-dict reports passed:
  `21:24` tensor count `36`, `24:26` tensor count `24`, and `26:28`
  tensor count `26`, all with `seq_len=16` and `lm_head_w_bits=16`.
- `seg27_28_seq128_lmheadq16_state_dict_sentinel` state-dict report passed:
  segment `27:28`, tensor count `14`, `seq_len=128`, `lm_head_w_bits=16`.
- `seg27_28_seq256_lmheadq16_state_dict_sentinel` state-dict report passed:
  segment `27:28`, tensor count `14`, `seq_len=256`, `lm_head_w_bits=16`.
- Compile preflight is blocked by Windows commit headroom: current `22.95 GB`
  versus required `64.0 GB`.
- Latest capacity-unblock audit still blocks compile: current commit headroom
  is about `28.22 GB`, required `64.0 GB`, no private process above the `12 GB`
  reclaim threshold, and `C:\pagefile.sys` is allocated at `27.0 GB`.
- Recommended capacity target before the next compile preflight: raise commit
  limit to about `100.49 GB` (`43.78 GB` additional commit limit including the
  8 GB safety margin), then rerun the preflight runner.
- Capacity operator handoff is ready but not executed. C drive does not have
  enough spare room for a single enlarged pagefile; the handoff keeps the
  current `C:\pagefile.sys` at `27648 MB` and adds `F:\pagefile.sys` at
  `49152 MB`, leaving about `376.92 GB` free on F after allocation. The handoff
  requires elevated PowerShell and reboot, and the probe itself changed no
  system setting.
- Post-reboot verifier is in place and currently blocked, as expected before
  the handoff is executed: `F:\pagefile.sys` is not configured or active,
  commit headroom is still about `28.15 GB`, and no compile process is active.
  After reboot, run the verifier first, then capacity-unblock, rank-1
  preflight, compile-admission, and goal-status probes in that order.
- Post-reboot resume runner is now in place. Before reboot it reports
  `blocked_dream7b_bpu_quality_post_reboot_resume_runner`, refreshes the
  capacity/admission/matrix/promotion/goal/acceptance evidence chain, skips
  rank-1 preflight by default, and starts no compile/runtime/service. After
  reboot, rerun it with `--run-preflight` to refresh rank-1 state-dict and
  compile-preflight evidence before compile admission. Use
  `--no-run-state-dict` only for an explicit fast recheck when state-dict
  evidence is already current.
- Safe compile handoff is now in place. It currently reports
  `blocked_dream7b_bpu_quality_safe_compile_handoff` with
  `operator_may_run_compile=false`, so the rank-1 compile command stays locked
  until post-reboot capacity, rank-1 state-dict/compile-preflight, and compile
  admission all pass together.
- Final goal audit is now in place. It turns the user-facing objective into
  explicit requirements and currently reports 6 required items passing:
  live HTTP/OpenClaw/gateway, fast-path identity/status/ready, generic
  generation boundary recording, BPU queue-batch baseline preservation,
  production guardrail preservation, and the lm-head/late-segment/seq128/seq256
  candidate plan. It reports 3 blocked required items: post-reboot capacity,
  post-compile quality/latency/rollback gates, and final goal completion.
- Post-compile validation matrix is now in place and currently blocked. It
  fixes the Route B promotion checklist to four required report classes:
  logits diagnostics, three-prompt Chinese generation quality, same-workload
  comparison, and rollback. Current blockers are capacity/admission not ready
  plus missing logits, generation, same-workload, and rollback-ready evidence.
- The three validation producer probes now exist and produce explicit blocked
  reports instead of leaving missing-file gaps. Current logits evidence has
  argmax agreement `0.0`, top-1 probability `0.0`, and non-uniform top
  probabilities `false`; current generation evidence has `0` readable Chinese
  prompts and `3` failed prompts; current same-workload evidence has `0`
  processed requests and no valid baseline/candidate comparison because the
  candidate artifact is still absent.
- Compile admission guard currently admits no HBM compile commands. The rank-1
  `seg27_28_lmheadq16_last_token_sentinel` command is blocked by
  `capacity_unblock_not_ready` and `preflight_candidate_mismatch` because the
  latest preflight was the seq256 state-dict sentinel. `seg21_28_lateq16_quality_set`,
  `seg27_28_seq128_lmheadq16_state_dict_sentinel`, and
  `seg27_28_seq256_lmheadq16_state_dict_sentinel` are additionally blocked by
  `only_rank1_sentinel_allowed_first`.
- Do not run compile commands until a fresh preflight reports `verdict=preflight_ok`.
- Promotion gate currently blocks candidate promotion with:
  `capacity_not_ready`, `compile_not_admitted`, `preflight_candidate_mismatch`,
  logits threshold failures (`argmax_agreement_below_threshold`,
  `top1_probability_below_threshold`, `top_probabilities_not_non_uniform`),
  generation threshold failures (`readable_chinese_prompt_count_below_threshold`,
  `failed_prompt_count_nonzero`), same-workload failures
  (`not_same_workload`, `processed_request_count_below_threshold`,
  `baseline_missing_or_invalid`, `candidate_slower_without_complement_claim`),
  and rollback failures (`rollback_not_ready`,
  `rollback_candidate_artifact_missing`,
  `rollback_candidate_manifest_not_verified`).
- Rollback report currently blocks promotion because the candidate artifact root
  `/mnt/nas/openclaw/models/dream7b-hbm/bpu-quality-seq16-b4-lmheadq16-last-token`
  does not exist yet. It verifies that 18888 still points to
  `diffuse-resident`, production services are active, no service restart was
  performed by the probe, and seq16 baselines remain present.

Promotion requires logits argmax agreement above 80 percent, top-1 probability
above 5 percent, readable Chinese output on at least three prompts,
same-workload latency/throughput evidence, and an explicit rollback report.

## 6. Release Package

Include:

- `scripts/probes/dream7b_perf_identity_probe.py`
- `scripts/probes/dream7b_openclaw_default_latency_probe.py`
- `scripts/probes/dream7b_route_a_quality_boundary_packet.py`
- `scripts/probes/dream7b_bpu_quality_candidate_gate.py`
- `scripts/probes/dream7b_bpu_quality_candidate_pack.py`
- `scripts/probes/dream7b_bpu_quality_preflight_runner.py`
- `scripts/probes/dream7b_bpu_quality_capacity_unblock_plan.py`
- `scripts/probes/dream7b_bpu_quality_capacity_operator_handoff.py`
- `scripts/probes/dream7b_bpu_quality_capacity_post_reboot_verifier.py`
- `scripts/probes/dream7b_bpu_quality_post_reboot_resume_runner.py`
- `scripts/probes/dream7b_bpu_quality_compile_admission_guard.py`
- `scripts/probes/dream7b_bpu_quality_validation_common.py`
- `scripts/probes/dream7b_bpu_quality_logits_diagnostics.py`
- `scripts/probes/dream7b_bpu_quality_generation_quality.py`
- `scripts/probes/dream7b_bpu_quality_same_workload_compare.py`
- `scripts/probes/dream7b_bpu_quality_rollback_report.py`
- `scripts/probes/dream7b_bpu_quality_promotion_gate.py`
- `scripts/probes/dream7b_bpu_quality_post_compile_validation_matrix.py`
- `scripts/probes/dream7b_bpu_quality_safe_compile_handoff.py`
- `scripts/probes/dream7b_ai_nas_goal_status_packet.py`
- `scripts/probes/dream7b_ai_nas_acceptance_packet.py`
- `scripts/probes/dream7b_ai_nas_final_goal_audit.py`
- `scripts/probes/dream7b_ai_nas_delivery_manifest.py`
- `scripts/probes/ai_nas_route_a_demo_readiness_packet.py`
- `scripts/diffuse_resident.cpp`
- `scripts/probes/ai_nas_edge_cloud_router_probe.py`
- `scripts/probes/ai_nas_allowlisted_tool.sh`
- `configs/systemd/*.service`
- `docs/community/dream7b-s100-bpu-deploy/SKILL.md`
- latest benchmark and AI-NAS reports

Do not include private NAS contents, keys, tokens, account names, raw personal logs, or oversized generated artifacts.
