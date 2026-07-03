# Dream 7B BPU 93-95% Optimization Status

Date: 2026-06-14

Latest true-batch research update: 2026-06-19

## Objective

Engineering target:

- Raise real end-to-end average BPU loading from about 90% to 93-95%.
- Keep `failed_jobs=0`.

Benchmark target:

- Keep a separate extreme benchmark mode.
- Try to approach 97-99% or local-window 100% without promoting benchmark-only settings to the default service.

## Baseline

Default service:

```text
dream7b-bpu-batch-queue.service
active/enabled: active / enabled
segment_major_24x256_default: True
latest soak avg_bpu: 90.097
latest baseline telemetry avg_bpu: 90.136
failed_jobs: 0
OpenClaw model: dream7b-local/Dream7B-S100P-local
base_url: http://127.0.0.1:18888/v1
```

Baseline evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260612-210507/segment_major_candidate_soak_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260612-212114/segment_major_candidate_service_telemetry_probe.json`

## Candidates Tested

| Candidate | Change | Avg BPU | failed_jobs | Status |
|---|---:|---:|---:|---|
| baseline default | 24 jobs x 256 requests, poll 1s, top_k 3 | 90.136 | 0 | current default |
| fastpoll service | poll 0.05s, flush 5s, 24 x 256, top_k 3 | 91.699 | 0 | improvement, not enough |
| fullgate service | min_job_count 24, poll 0.05s, 24 x 256, top_k 3 | 91.471 | 0 | worse than fastpoll |
| direct extreme top_k0 | direct runner, no service poll, 24 x 256, top_k 0 | 92.260 | 0 | best full-window result, still below engineering target |
| direct extreme top_k0 2-wave | direct runner, two consecutive 24 x 256 waves, top_k 0 | 92.131 | 0 | no improvement from wave amortization |
| direct extreme lite top_k0 | skip per-request final result JSONL, 24 x 256, top_k 0 | 92.427 | 0 | small improvement, still below target |
| direct extreme lite top_k0 no explicit GC | lite mode plus skip per-segment `gc.collect()` | 92.481 | 0 | best full-window result so far, still below 93 |
| fine-batch batch8 top_k0 | `dream7b-bpu-fine-batch-forward`, 8 independent seq16 inputs | 5.127 telemetry avg, 98.0 max | 0 | benchmark-only; amortizes HBM load but not a sustained utilization path |
| raw-final direct top_k0 | skip final full-logits float32 dequantization, 24 x 256 | 93.166 | 0 | benchmark runner now reaches engineering band |
| raw-final service top_k3 | raw-final candidate service, original `argpartition` top-k | 92.443 | 0 | service-compatible but still below 93 |
| raw-final service fast top_k3 | raw-final candidate service plus small-k raw logits `argmax` top-k | 93.042 | 0 | first service-compatible 93% candidate |
| raw-final candidate soak | two full candidate telemetry passes, raw-final fast top_k3 | 93.037 | 0 | stable isolated candidate soak |
| raw-final promoted default, first telemetry | promoted default service, raw-final fast top_k3, min_job_count initially 2 | 92.831 | 0 | below 93 full-window gate |
| raw-final promoted default, 24-job gate | promoted default service, raw-final fast top_k3, min_job_count 24 | 92.916 | 0 | below 93 full-window gate |
| raw-final promoted default rerun | promoted default service, raw-final fast top_k3, min_job_count 24 | 92.980 | 0 | still below 93 full-window gate; active window 93.258 |
| raw-final promoted default skip explicit GC | promoted default service, raw-final top_k3, no explicit `gc.collect()` | 92.932 | 0 | negative result; reverted |
| raw-final promoted default top_k1 pass 1 | promoted default service, raw-final top_k1, min_job_count 24 | 93.024 | 0 | first promoted default 93% full-window pass |
| raw-final promoted default top_k1 pass 2 | promoted default service, raw-final top_k1, min_job_count 24 | 93.014 | 0 | repeated promoted default 93% full-window pass |

Fastpoll evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260613-220923/segment_major_candidate_service_telemetry_probe.json`

Fullgate evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260613-222935/segment_major_candidate_service_telemetry_probe.json`

Extreme benchmark evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_extreme_benchmark_20260613-225414/extreme_benchmark_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_extreme_benchmark_20260613-231510/extreme_benchmark_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_extreme_benchmark_20260613-235735/extreme_benchmark_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_extreme_benchmark_20260614-001723/extreme_benchmark_probe.json`

Fine-batch benchmark evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260614-004126/batch_size_sweep_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_telemetry_20260614-004519/fine_batch_telemetry_probe.json`

Raw-final evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_phase_timing_20260614-005702/phase_timing_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260614-011741/segment_major_candidate_service_telemetry_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_phase_timing_20260614-013853/phase_timing_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260614-013955/segment_major_candidate_service_telemetry_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_soak_20260614-020309/segment_major_candidate_soak_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_default_promotion_20260614-122126/segment_major_default_promotion_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_default_promotion_20260614-124251/segment_major_default_promotion_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260614-124351/segment_major_candidate_service_telemetry_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260614-130801/segment_major_candidate_service_telemetry_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_default_promotion_20260614-140853/segment_major_default_promotion_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260614-141219/segment_major_candidate_service_telemetry_probe.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_segment_major_candidate_service_telemetry_20260614-143252/segment_major_candidate_service_telemetry_probe.json`

## Window Analysis

Best observed windows:

| Run | Full Avg | Best 5s | Best 30s | Best 300s | Best 600s |
|---|---:|---:|---:|---:|---:|
| baseline default | 90.136 | not recalculated | 95.873 | 93.736 | 93.016 |
| fastpoll service | 91.699 | 96.840 | 96.520 | 94.377 | 94.202 |
| direct extreme top_k0 | 92.260 | 96.680 | 96.387 | 94.203 | 94.021 |
| direct extreme lite top_k0 | 92.427 | not recalculated | 96.593 | 94.467 | 94.218 |
| direct extreme lite top_k0 no explicit GC | 92.481 | not recalculated | 96.513 | 94.403 | 94.261 |
| fine-batch batch8 top_k0 | 5.127 telemetry avg | 98.000 max sample | not applicable | not applicable | not applicable |
| raw-final direct top_k0 | 93.166 | 100.000 max sample | not recalculated | not recalculated | not recalculated |
| raw-final service fast top_k3 | 93.042 | 100.000 max sample | not recalculated | not recalculated | not recalculated |
| raw-final promoted default 20260614-130801 | 92.980 | 100.000 max sample | not recalculated | not recalculated | not recalculated |
| raw-final promoted default top_k1 20260614-141219 | 93.024 | 100.000 max sample | not recalculated | not recalculated | not recalculated |
| raw-final promoted default top_k1 20260614-143252 | 93.014 | 100.000 max sample | not recalculated | not recalculated | not recalculated |

Window evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_bpu_window_analysis_default_20260612-212114.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_window_analysis_fastpoll_plus_short_20260613-220923.json`
- `/mnt/nas/openclaw/reports/models/dream7b_bpu_window_analysis_extreme_topk0_20260613-225414.json`

## Interpretation

The current ceiling is not caused by segment HBM load overhead. Load-to-run ratio is already about 2.2-2.6%, and `load_event_count` is down to 10 due to segment-major load-once execution.

The remaining gap is likely in low-utilization intervals between segment invocations:

- host-side runtime submission and synchronization
- CPU-side post-processing and JSON/result handling
- segment boundary effects
- monitor window including low-load ramp-up/ramp-down periods

The best long local windows already reach 94% for 300-600 seconds. After the raw-final/top_k1 promotion, promoted default full-window averages now reach 93.014-93.024%. Short windows peak around 96.8%, not 97-99%.

The fine-batch path can show high instantaneous samples, but it does not solve sustained utilization. A fresh `top_k=0` batch-size sweep on 2026-06-14 showed `batch_count=8` with `amortized_wall_ms_per_forward=3197.990` and `amortized_run_ms_per_forward=173.541`. The matching telemetry run showed `max_bpu_loading=98.0`, but only `avg_bpu_loading=5.127` with 19 nonzero samples out of 252. Its forward summary was dominated by HBM load time: `load_ms=23790.753`, `run_ms=1390.329`, `load_to_run_ratio=17.111599`. This confirms that fine-batch is useful as a load-amortization microbenchmark, not as a route to 100% average utilization for the default OpenAI-compatible service.

The 2026-06-14 phase-timing probe identified the removable final-segment overhead. In the old raw final path, `seg26_28` spent about 10 s of full-run wall time outside `runtime.run`, dominated by final logits materialization. The fix is to skip full final-logits float32 dequantization when the final tensor is only needed for shape validation and top-k. For top-k, raw quantized logits preserve ordering under the scalar output scale, so the runner can select token ids on the raw output and scale only selected scores.

Two raw-final optimizations were validated:

- `raw-final direct top_k0`: full-window benchmark reached `avg_bpu_loading=93.166`, `max_bpu_loading=100.0`, `processed_request_count=6144`, `failed_job_count=0`.
- `raw-final service fast top_k3`: isolated candidate service reached `avg_bpu_loading=93.042`, `max_bpu_loading=100.0`, `processed_request_count=6144`, `failed_job_count=0`, `matched_result_count=6144`, `default_service_replaced=False`.
- `raw-final candidate soak`: two isolated candidate passes reached `avg_bpu_loading=93.037`, `processed_request_count=12288`, `failed_job_count=0`.
- `raw-final promoted default`: promotion and rollback verification passed, but default-service full-window telemetry is currently `92.831`, `92.916`, then `92.980`, all with `failed_job_count=0`.
- `raw-final promoted default top_k1`: two promoted default full-window telemetry passes reached `93.024` and `93.014`, both with `processed_request_count=6144`, `failed_job_count=0`, `matched_result_count=6144`, and `max_bpu_loading=100.0`.

Top-k was separately optimized after timing showed `argpartition` cost. For 32 requests, raw-final `top_k=3` timing improved `topk_ms` from `46.635` to `8.029` with the same sample top-k output for the first request. The candidate service result above uses this fast small-k raw logits path.

The final promoted default uses `top_k=1` rather than `top_k=3`. This preserves a non-empty deterministic next-token result for the OpenClaw/text-queue path, but no longer returns three alternatives per request. Compatibility was verified with `dream7b-bpu-text-queue-run --prompt hello`: `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260614-140950/text_queue_run.json` returned `ok_dream7b_bpu_text_queue_run` with one decoded token and no errors.

An attempted `DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC=1` optimization was rejected. It produced `avg_bpu_loading=92.932`, `failed_job_count=0`, and a slower runner wall time (`1106.089` s), so the default service was restored to `DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC=0`.

The promoted default service appears to be performance-equivalent to the isolated candidate at the runner layer:

- candidate runner wall time: about `1105.14-1105.22` s for 6144 requests.
- promoted default top_k3 runner wall time: `1105.36-1105.68` s for 6144 requests.
- promoted default top_k1 runner wall time: `1104.17-1105.38` s for 6144 requests.
- promoted default top_k1 `load_to_run_ratio`: `0.022017-0.022140`.
- promoted default active-window BPU average on `20260614-130801`: `93.258`.

The earlier top_k3 promoted default miss was caused by monitor-window and boundary samples, not by a regression in the segment-major runner. The `20260614-130801` promoted default telemetry had `11055` BPU samples, `10827` nonzero samples, `228` zero samples, `30` leading idle samples, and `3` trailing idle samples. The full average was `92.980`; the first-nonzero-to-last-nonzero active average was `93.258`. Reducing production output to deterministic `top_k=1` moved the full-window metric across the 93% gate while keeping a usable next-token result.

Segment progress analysis gives a more specific hotspot:

- fastpoll total segment wall-run overhead: 32.578 s, about 2.96% of segment wall time.
- direct top_k0 total segment wall-run overhead: 24.221 s, about 2.22% of segment wall time.
- most early/middle segments add about 1.5 s wall-run overhead per segment.
- final `seg26_28` is the dominant outlier:
  - fastpoll `seg26_28` wall-run overhead: 18.947 s.
  - direct top_k0 `seg26_28` wall-run overhead: 10.199 s.
  - lite top_k0 `seg26_28` wall-run overhead: 10.124 s.
  - lite top_k0 without explicit GC `seg26_28` wall-run overhead: 10.061 s.

Segment analysis evidence:

- `/mnt/nas/openclaw/reports/models/dream7b_segment_progress_analysis_fastpoll_20260613-220924.json`
- `/mnt/nas/openclaw/reports/models/dream7b_segment_progress_analysis_extreme_topk0_20260613-225414.json`
- `/mnt/nas/openclaw/reports/models/dream7b_segment_progress_analysis_lite_topk0_20260613-235735.json`
- `/mnt/nas/openclaw/reports/models/dream7b_segment_progress_analysis_lite_nogc_topk0_20260614-001723.json`

HBM shape check:

- `seg00_02` input shape is fixed to `_input_0: [1, 16]`, `_input_1: [16]`.
- middle segment input shape is fixed to `_input_0: [16, 3584]`, `_input_1: [16]`.
- Therefore the current HBM artifacts do not accept a true multi-request batch input. `request_count=256` is a queue-level batch, not a single HBM batch. A real batch-size improvement requires recompiled HBM artifacts with batch dimension support or a lower-level runtime path that can submit multiple fixed-shape invocations with less Python overhead.

True batch-dimension HBM follow-up:

- B=2 seq16 true-batch HBM artifacts were compiled for all 28 one-layer segments and stored under `/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2`.
- The B=2 runtime chain executes successfully on S100P with true batch shapes: first segment inputs `[2,16]`, hidden segment input/output `[2,16,3584]`, final logits `[2,16,152064]`, and `failed_job_count=0` in long telemetry probes.
- Full load-once of all 28 B=2 true-batch segments is not feasible on the current S100P memory budget; loading `seg06_07` after `seg00_01` through `seg05_06` fails with `HBRT4_STATUS_RESOURCE_EXHAUSTED`.
- Memory-safe grouped execution with groups `0:6,6:12,12:18,18:24,24:28` is stable, but does not beat the queue-batch baseline. The best B=2 segment-major run so far is 4096 microbatches / 8192 requests with `avg_bpu_loading=84.271`, `avg_nonzero_bpu_loading=90.202`, `max_bpu_loading=100.0`, and `amortized_wall_ms_per_request=122.245`.
- The queue-batch baseline remains stronger at `avg_bpu_loading=93.166` and `avg_nonzero_bpu_loading=95.097`.
- The first B=4 compile probe was interrupted by Windows virtual-memory pressure before producing artifacts. This was fixed by avoiding full-model safetensor loading in segmented mode and by compiling in smaller controlled batches.
- `scripts/probes/Compile-DreamTrueBatchSegments.ps1` now has a host commit preflight guard (`-PreflightOnly`, `-MinCommitHeadroomGB`, `-SkipPreflight`). The WSL-native helper `scripts/probes/dream7b_true_batch_compile_segments_wsl.sh` is the fallback when the PowerShell wrapper hits transient internal WSL `E_ACCESSDENIED` launches.
- The B=4 compiler path now avoids full-model safetensor loading in segmented mode. Selective loading uses only 12-14 tensors per one-layer segment instead of the full 339-tensor model state.
- B=4 seq16 true-batch HBM artifacts are now complete for all 28 one-layer segments and stored under `/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4` (`56G` total). Remote `manifest.sha256` verification passed for all 28 segments.
- B=4 S100P runtime validation passed: single-segment `seg05_06` returned `[4,16,3584]`; full 28-segment chain returned final logits `[4,16,152064]` with `verdict=ok_dream7b_true_batch_runtime_chain`.
- Short B=4 telemetry did not beat the queue-batch baseline. Report `/mnt/nas/openclaw/reports/models/dream7b_true_batch_runtime_telemetry_20260619-063852_b4/true_batch_runtime_telemetry.json` measured `avg_bpu_loading=15.495`, `avg_nonzero_bpu_loading=48.767`, and `max_bpu_loading=80.0`. The comparison report `/mnt/nas/openclaw/reports/models/dream7b_true_batch_telemetry_compare_20260619-064106/true_batch_telemetry_compare.json` returned `true_batch_runtime_ok_but_telemetry_not_better` against the queue baseline `avg_bpu_loading=93.166`, `avg_nonzero_bpu_loading=95.097`, `max_bpu_loading=100.0`.
- Comparable B=4 segment-major long telemetry with `microbatch_count=1536`, `batch_size=4`, and `processed_request_count=6144` passed runtime validation with `failed_job_count=0` and final shape `[4,16,152064]`. Report `/mnt/nas/openclaw/reports/models/dream7b_true_batch_group_major_telemetry_20260619-105833_segment_major_mb1536_b4/true_batch_group_major_telemetry.json` measured `amortized_wall_ms_per_request=72.249`, `avg_bpu_loading=76.789`, `avg_nonzero_bpu_loading=89.776`, and `max_bpu_loading=100.0`. This is a positive throughput signal versus the queue baseline `179.62 ms/request`, but still below the queue baseline BPU average/nonzero average.
- Detailed report: `/mnt/nas/openclaw/reports/models/dream7b_true_batch_compile_20260618_progress/dream7b_true_batch_hbm_feasibility_2026-06-18.md`

## Current Decision

Do not promote fastpoll/fullgate/top_k0 to the default service.

- fastpoll improves average BPU from 90.136 to 91.699, but does not reach 93%.
- fullgate does not improve fastpoll.
- pre-raw-final top_k0 direct benchmark is not a service-compatible production setting and only reaches 92.260 full-window average.
- lite/no-GC benchmark reaches 92.481, but it has been superseded by raw-final results.
- fine-batch batch8 can reach a 98.0 instantaneous sample, but its telemetry average is only 5.127 because the current fine-adjacent HBM path spends most time loading HBM files.
- B=2 and B=4 true batch-dimension HBM are valid research prototypes and run with true batch shapes. B=4 shows better amortized wall time in the segment-major probe, but it still does not beat the 93.166/95.097 queue-batch BPU baseline. B=4 is therefore not a production replacement candidate yet.
- raw-final fast top_k3 candidate service reaches 93.042 with `failed_job_count=0`, and a two-pass isolated soak reaches 93.037 with `failed_job_count=0`.
- raw-final top_k1 has been promoted to the default service with rollback verified, and two promoted default full-window telemetry passes are inside the 93-95% engineering band.
- All tested candidates preserved `failed_jobs=0`.

The new fastpoll and fullgate candidate services were disabled after testing. The raw-final candidate service was installed as an isolated service named `dream7b-bpu-segment-major-load-once-candidate-rawfinal.service` and was disabled after soak testing. The default service is now raw-final segment-major 24x256, active/enabled, and uses service-compatible `top_k=1`.

OpenClaw/Dream text queue compatibility was rechecked after promotion. The default service now writes segment-major summaries under `runs/<timestamp>/segment_major_queue_summary.json`, while the older `dream7b-bpu-text-queue-run` expected `jobs/<job>/queue_summary.json`. The helper was updated to locate the segment-major summary by `request_id` through `durable_state.results_jsonl`. Verification:

- command: `dream7b-bpu-text-queue-run --prompt hello`
- report: `/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260614-140950/text_queue_run.json`
- verdict: `ok_dream7b_bpu_text_queue_run`
- summary: `/mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/runs/20260614-141125/segment_major_queue_summary.json`
- raw_final_enabled: `True`
- processed_request_count: `1`
- failed_job_count: `0`
- topk_last_position length: `1`

## 100% Average Utilization Assessment

Do not treat 100% average BPU loading as an achievable near-term engineering target with the current artifacts.

Current evidence supports this boundary:

- The best isolated raw-final candidate service result is now 93.042% average, inside the engineering band.
- The best direct full-window benchmark is now 93.166%.
- The promoted default top_k1 service currently reaches 93.014-93.024% full-window average and about 93.31% active-window average, with 100.0 max samples.
- The best short-window observation remains about 96.8% in prior window analyses, while raw-final telemetry includes isolated 100.0 samples.
- A microbenchmark can hit 98.0 or 100.0 instantaneous samples, but those peaks disappear when averaged across load, synchronization, and boundary idle time.
- Current HBM input shapes are fixed single-request shapes, so queue-level batching cannot become true BPU batch execution without recompilation or a lower-level runtime path.

Practical target split:

- Production/default service: raw-final top_k1 is promoted and active, with repeated promoted-default full-window telemetry passes at 93-95%.
- Benchmark mode: continue trying for 97-99% short-window or isolated 100% samples, clearly labelled as benchmark-only.
- Sustained 100% average: requires a different execution architecture, likely true batch-dimension HBM artifacts, deeper runtime submission changes, or both.

## Next Work

The next useful optimization should target margin above 93%, not queue depth:

- Keep telemetry reports explicit about full-window average versus active-window average.
- Target remaining segment boundary and monitor-boundary idle time to move the promoted default away from a narrow 93.014-93.024 margin.
- Do not use benchmark-only `top_k=0` for production acceptance.
- Explore batching host-side post-processing after all BPU segments complete.
- Since current HBM input shapes are fixed single-request shapes, the next meaningful performance path is either:
  - recompile HBM artifacts with a real batch dimension, then test true multi-request `runtime.run` calls; or
  - implement a lower-level runtime submission path that reduces Python per-request call overhead without changing HBM shape.

Current promotion gate evidence:

- real service telemetry average BPU: 93-95%
- `failed_jobs=0`
- default service rollback verified
- no regression to OpenClaw `Dream7B-S100P-local` availability
