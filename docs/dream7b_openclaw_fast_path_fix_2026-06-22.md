# Dream7B OpenClaw Fast Path Fix 2026-06-22

## Decision

Keep the chat-facing default as:

`OpenClaw -> dream7b-local-openai-gateway:18888 -> diffuse-resident -> Dream7B GGUF`

Do not promote the current BPU seq16 single-request path as the chat default. The
BPU path remains the queue-batch throughput and telemetry baseline.

## Fix Applied

- Restored transparent gateway fast paths for model identity and local S100P
  status prompts in `dream7b_local_openai_gateway.py`.
- Enabled `DREAM7B_OPENAI_QUICK_RESPONSE=1` in
  `configs/systemd/dream7b-local-openai-gateway.service`.
- Synced both files to S100P and restarted
  `dream7b-local-openai-gateway.service`.

Remote hashes after deploy:

```text
d85fcb7031c48ba2616e1955f4c158cf9e54b5c4203c4b5632c525379fd60bf8  /root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py
833a44e1b5a19addf7f20dcc927f0d20099542cac348820fdddf4f67bb5d5209  /root/.config/systemd/user/dream7b-local-openai-gateway.service
```

## Live Verification

Health:

```text
http://127.0.0.1:18789/health -> {"ok":true,"status":"live"}
openclaw-gateway.service -> active
dream7b-local-openai-gateway.service -> active
```

Current NAS-backed reports:

```text
/mnt/nas/openclaw/reports/models/dream7b_fast_path_regression_20260622-174547/dream7b_fast_path_regression.json
/mnt/nas/openclaw/reports/models/dream7b_first_response_slo_tier_guard_20260622-174823/dream7b_first_response_slo_tier_guard.json
/mnt/nas/openclaw/reports/models/openclaw_entry_demo_20260622-174732/openclaw_entry_demo.json
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
LATEST:/mnt/nas/openclaw/reports/models/dream7b_ai_nas_delivery_manifest_*/dream7b_ai_nas_delivery_manifest.json
```

Direct 18888 probes:

| Case | Elapsed | Path | Backend | Result |
| --- | ---: | --- | --- | --- |
| Ready probe | 2.663 ms | `gateway_fast_ready` | not invoked | `Ready` |
| English identity | 2.626 ms | `gateway_fast_identity` | not invoked | Dream7B-S100P-local identity fact |
| Chinese identity | 2.843 ms | `gateway_fast_identity` | not invoked | Dream7B-S100P-local identity fact |
| Chinese local status | 2.935 ms | `gateway_fast_local_status` | not invoked | local S100P status fact |
| Generic math | 8201.547 ms | `gateway_diffuse_resident` | invoked | `1` |

First-response SLO tier guard:

```text
verdict: ok_dream7b_first_response_slo_tier_guard
fast_path_max_first_content_ms: 2.935
sse_first_progress_p50_ms: 278.387
explicit_first_content_p50_ms: 20771.222
quickpath_first_content_p50_ms: 2.554
```

OpenClaw entry layer:

```text
verdict: ok_openclaw_entry_demo_probe
nas_mounted: true
nas_writable: true
openclaw_status_probe.status: ok
root user openclaw-gateway capture: ok
port_18789 capture: ok
```

The fix solves the user-facing slow/low-quality regression for deterministic
identity, local-status, and readiness prompts by routing them to explicit
transparent gateway facts. It does not claim that Dream diffusion generation is
now a fast or high-quality general chat model.

Goal status packet:

```text
verdict: ready_route_a_blocked_route_b_goal_status
goal_complete: false
route_a_status: ready_for_demo
route_b_status: candidate_preflight_done_capacity_blocked
route_b_errors: capacity_unblock_not_ready, capacity_post_reboot_verifier_not_ready, safe_compile_handoff_not_ready, post_compile_validation_matrix_not_ready, rollback_report_not_ready, promotion_gate_not_ready
compile_started: false
service_restarted: false
latest_route_b_inputs: resolved through LATEST:/mnt/nas/openclaw/reports/models/... path specs
```

Route A quality boundary packet:

```text
verdict: ok_dream7b_route_a_quality_boundary_packet
fast_path_max_first_content_ms: 2.713
generic_generation_boundary.elapsed_ms: 6688.118
generic_generation_boundary.promotion_claim: false
```

Route A demo-readiness packet:

```text
verdict: ok_ai_nas_route_a_demo_readiness_packet
ready: true
tool_count: 7
before_ready: true
after_ready: true
privacy_query_sent_to_cloud: false
```

Acceptance packet:

```text
verdict: partial_dream7b_ai_nas_acceptance_packet_route_a_ready_route_b_blocked
full_goal_complete: false
demo_delivery_ready: true
route_a_demo_ready: true
route_b_isolated: true
route_b_promotion_ready: false
generic_generation_elapsed_ms: 6688.118
generic_generation_promotion_claim: false
operator_may_run_compile: false
```

Final goal audit:

```text
verdict: partial_dream7b_ai_nas_final_goal_audit_route_a_ready_route_b_blocked
all_complete: false
demo_delivery_ready: true
required_pass_count: 6
required_blocked_count: 3
required_fail_count: 0
blocked_requirement_ids: route_b_capacity_ready_after_reboot, route_b_post_compile_quality_latency_rollback_gates, final_goal_complete
candidate_plan: lm_head rank-1, late-segment q16, seq128 sentinel, seq256 sentinel
safe_compile_handoff_enforced: pass
rank1_preflight_matches_candidate: false
latest_preflight_selected_candidate_ids: seg27_28_seq256_lmheadq16_state_dict_sentinel
```

Delivery manifest:

```text
verdict: partial_dream7b_ai_nas_delivery_manifest_route_a_ready_route_b_blocked
delivery_manifest_ready: true
missing_release_file_count: 0
release_file_count: 35
demo_delivery_ready: true
full_goal_complete: false
```

## Remaining Boundary

Generic Dream7B GGUF resident generation still takes seconds and can return
short or wrong text. This is the remaining model/runtime quality boundary, not
an OpenClaw process-start problem.

The current BPU seq16 single-request path is still structurally blocked for
production chat because the 16-token window forces prompt truncation and only a
small mask region remains. Use it for throughput/logits telemetry until a
separate larger-window or higher-precision BPU experiment clears quality gates.

## Route Plan

### Route A: Product Experience

Goal: make the AI-NAS/OpenClaw demo reliable.

- Keep fast paths for identity, S100P status, ready/heartbeat, and bounded
  operational status prompts.
- Keep NAS tools, file search, duplicate report, folder RAG, OCR, and edge/cloud
  routing as the primary product value.
- Use `scripts/probes/ai_nas_route_a_demo_readiness_packet.py` to rerun the
  fixed dispatcher demo set and preserve one NAS-backed rollup.
- Use `scripts/probes/dream7b_route_a_quality_boundary_packet.py` to prove the
  fixed fast-path prompts remain under the interactive SLO and to record generic
  resident generation as a boundary, not a quality-promotion claim.
- Track generic resident generation separately with an honest latency and
  quality boundary.

Acceptance:

- 18789 and 18888 health checks are live.
- Fast identity/status/ready prompts return under 100 ms with backend not invoked.
- All NAS actions write Markdown/JSON reports and preserve source files.

### Route B: Model Runtime R&D

Goal: make a BPU-backed text path that can eventually improve quality and/or
latency without destabilizing Route A.

- Keep `dream7b-bpu-batch-queue.service` as the production BPU baseline.
- Do not delete seq16 queue HBM artifacts and do not overwrite 18888.
- Run `scripts/probes/dream7b_bpu_quality_candidate_gate.py` before preparing
  any BPU quality compile bundle.
- Use `scripts/probes/dream7b_bpu_quality_candidate_pack.py` for the concrete
  candidate order and preflight commands.
- The compiler and wrappers support `--lm-head-w-bits` / `-LmHeadWBits`, which
  enables a q16 `lm_head` sentinel while keeping surrounding segment weights q8.
- Next candidates are ordered as:
  1. `seg27_28_lmheadq16_last_token_sentinel`;
  2. `seg21_28_lateq16_quality_set`;
  3. `seg27_28_seq128_lmheadq16_state_dict_sentinel`;
  4. `seg27_28_seq256_lmheadq16_state_dict_sentinel`.
- The current gate admits prepare/verify work only. It does not admit HBM
  compilation, service replacement, 18888 changes, or seq16 deletion.
- Latest preflight result: the `seg27_28_lmheadq16_last_token_sentinel`
  state-dict report passed, but compile preflight is blocked by Windows commit
  headroom (`22.95 GB` available versus `64.0 GB` required).
- Remaining state-dict preflights also passed: `seg21_28_lateq16_quality_set`
  covers `21:24`, `24:26`, and `26:28` at `seq_len=16`, and
  `seg27_28_seq128_lmheadq16_state_dict_sentinel` covers the larger-window
  `seq_len=128` parameterization. The new
  `seg27_28_seq256_lmheadq16_state_dict_sentinel` also passed state-dict
  preflight for segment `27:28`, tensor count `14`, `seq_len=256`, and
  `lm_head_w_bits=16`.
- Compile admission is candidate-aware: the latest seq256 state-dict preflight
  does not satisfy the rank-1 compile gate. Rank-1 is blocked by both
  `capacity_unblock_not_ready` and `preflight_candidate_mismatch` until a fresh
  rank-1 preflight is rerun after the pagefile handoff.
- Latest capacity-unblock audit still blocks compile: current commit headroom
  is about `28.22 GB` versus the `64.0 GB` guard, no private process exceeds the
  `12 GB` reclaim threshold, and the pagefile is allocated at `27.0 GB`.
  Increase commit limit to about `100.49 GB` and rerun preflight before any HBM
  compile.
- Capacity operator handoff is prepared but not executed: keep
  `C:\pagefile.sys=27648 MB`, add `F:\pagefile.sys=49152 MB`, then reboot and
  run post-reboot verifier, capacity, rank-1 preflight, compile admission, and
  goal status probes. The handoff and verifier probes made no system-setting
  change. Current verifier status is blocked because `F:\pagefile.sys` is not
  configured or active and commit headroom is still below the 64 GB guard.
- Compile admission guard currently admits no HBM compile commands. Rank-1
  `seg27_28_lmheadq16_last_token_sentinel` is blocked by capacity; later
  candidates are also blocked until the rank-1 sentinel has passed first.
- `scripts/probes/dream7b_bpu_quality_promotion_gate.py` now blocks promotion
  until capacity, compile admission, logits diagnostics, three-prompt Chinese
  quality, same-workload comparison, and rollback evidence all pass.
- `scripts/probes/dream7b_bpu_quality_post_compile_validation_matrix.py` now
  fixes the exact post-compile checklist: logits diagnostics must meet
  argmax/top-1/non-uniform thresholds, Chinese generation must pass three
  prompts with zero failures, same-workload comparison must cover at least
  12288 processed requests, and rollback must prove production isolation.
- `scripts/probes/dream7b_bpu_quality_logits_diagnostics.py`,
  `scripts/probes/dream7b_bpu_quality_generation_quality.py`, and
  `scripts/probes/dream7b_bpu_quality_same_workload_compare.py` now produce
  explicit blocked reports while the candidate artifact is absent, so Route B
  no longer has missing-file gaps in the promotion evidence chain.
- `scripts/probes/dream7b_bpu_quality_rollback_report.py` now verifies the
  rollback boundary without restarting services or touching production: 18888
  still points to `diffuse-resident`, seq16 baselines remain present, and the
  current rank-1 candidate artifact is still missing because compile has not
  been admitted.
- `scripts/probes/dream7b_bpu_quality_post_reboot_resume_runner.py` now gives a
  single post-reboot continuation entry point. By default it refreshes
  verifier/capacity/admission/matrix/promotion/goal/acceptance evidence without
  compile or service changes; after pagefile handoff and reboot, rerun it with
  `--run-preflight` to refresh rank-1 state-dict and compile-preflight before
  compile admission. Use `--no-run-state-dict` only when the state-dict evidence
  is already current and an explicit fast recheck is intended.
- `scripts/probes/dream7b_bpu_quality_safe_compile_handoff.py` now gives the
  final no-execute compile handoff: it emits `operator_may_run_compile=true`
  only when post-reboot capacity, rank-1 state-dict/compile-preflight, and
  compile admission all pass together. Current status is blocked, so no rank-1
  compile command is runnable yet.
- `scripts/probes/dream7b_ai_nas_acceptance_packet.py` now aggregates the
  final delivery evidence and keeps the distinction explicit: Route A is
  demo-deliverable today, Route B remains isolated and blocked, and full goal
  completion is still false.
- `scripts/probes/dream7b_ai_nas_goal_status_packet.py` now resolves changing
  Route B evidence through `LATEST:` path specs, so capacity/admission/matrix
  and promotion status follow the newest NAS reports.
- `scripts/probes/dream7b_ai_nas_final_goal_audit.py` now maps the final
  objective to explicit requirement rows, so completion requires every required
  item to pass instead of relying on a broad summary verdict.
- Promote nothing until live generation quality, logits diagnostics, same-workload
  latency, and rollback evidence all pass.

Acceptance:

- BPU candidate output is readable Chinese on multiple prompts.
- Logits diagnostics recover non-uniform top probabilities and argmax agreement.
- Same-workload latency/throughput beats or complements the current baseline.
- Route A remains unchanged during experiments.
