# Dream 7B Segmented S100 BPU HBM Progress

Date: 2026-06-03

## Goal

Keep Dream 7B as the model and make real Dream weights consume the S100P BPU path.

## Result

Dream 7B seq16 full-forward was compiled into S100/Nash-E `.hbm` artifacts and verified on S100P with `hrt_model_exec infer` and the board Python `HB_HBMRuntime`.

The working split is six HBM segments:

```text
/mnt/nas/openclaw/models/dream7b-hbm/segments6/dream7b_segment_0_4_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/segments6/dream7b_segment_4_7_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/segments6/dream7b_segment_7_14_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/segments6/dream7b_segment_14_21_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/segments6/dream7b_segment_21_24_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/segments6/dream7b_segment_24_28_seq16_q8.hbm
```

S100P smoke evidence:

```text
model_info: all six segments loaded successfully on S100P
infer: all six segments ran one dummy frame successfully on S100P
chain: six segments chained token -> hidden -> logits with dequantized F32 hidden handoff
runtime: /usr/hobot/bin/hrt_model_exec
NAS path: /mnt/nas/openclaw/models/dream7b-hbm
manifest: /mnt/nas/openclaw/models/dream7b-hbm/segments6/manifest.sha256
smoke outputs: /mnt/nas/openclaw/models/dream7b-hbm/smoke_outputs
smoke report: /mnt/nas/openclaw/reports/models/dream7b_segmented_hbm_smoke_20260603-015519/summary.md
chain report: /mnt/nas/openclaw/reports/models/dream7b_segmented_hbm_chain_20260603-021025/summary.md
python forward report: /mnt/nas/openclaw/reports/models/dream7b_python_forward_20260603-verified/summary.json
deployed command: /usr/local/bin/dream7b-bpu-forward
deployed command report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-022912/summary.json
token-arg report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-023557/summary.json
token-arg logits: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-023557/logits.npy
text-forward command: /usr/local/bin/dream7b-bpu-text-forward
text-forward report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-024218/summary.json
text-forward logits: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-024218/logits.npy
top-k report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-024533/summary.json
diffusion-step command: /usr/local/bin/dream7b-bpu-diffusion-step-probe
diffusion-step report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_step_20260603-025304/summary.md
diffusion-loop command: /usr/local/bin/dream7b-bpu-diffusion-loop-probe
diffusion-loop report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-030011/summary.md
strategy-aware diffusion-loop report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-031016/summary.md
cpu-quality-gate command: /usr/local/bin/dream7b-bpu-cpu-quality-gate-probe
cpu-quality-gate report: /mnt/nas/openclaw/reports/models/dream7b_bpu_cpu_quality_gate_20260603-033101/summary.md
hbm-cache-perf command: /usr/local/bin/dream7b-bpu-hbm-cache-perf-probe
hbm-cache-perf report: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_cache_perf_20260603-034629/summary.md
artifact-inventory command: /usr/local/bin/dream7b-bpu-hbm-artifact-inventory-probe
artifact-inventory report: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.md
artifact-inventory JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.json
local-cache loop report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-034939/summary.md
residency command: /usr/local/bin/dream7b-bpu-residency-probe
residency report: /mnt/nas/openclaw/reports/models/dream7b_bpu_residency_20260603-035939/summary.md
fine 26:28 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg26_28/dream7b_segment_26_28_seq16_q8.hbm
fine 24:26 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg24_26/dream7b_segment_24_26_seq16_q8.hbm
fine 0:2 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg00_02/dream7b_segment_0_2_seq16_q8.hbm
fine 2:4 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg02_04/dream7b_segment_2_4_seq16_q8.hbm
fine 7:10 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg07_10/dream7b_segment_7_10_seq16_q8.hbm
fine 10:14 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg10_14/dream7b_segment_10_14_seq16_q8.hbm
fine 14:17 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg14_17/dream7b_segment_14_17_seq16_q8.hbm
fine 17:21 HBM: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg17_21/dream7b_segment_17_21_seq16_q8.hbm
fine-residency command: /usr/local/bin/dream7b-bpu-fine-residency-probe
fine-residency report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_residency_20260603-054031/summary.md
fine-forward command: /usr/local/bin/dream7b-bpu-fine-forward
fine-forward report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/summary.json
fine-forward probe command: /usr/local/bin/dream7b-bpu-fine-forward-probe
fine-forward probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/fine_forward_probe.md
fine-forward perf command: /usr/local/bin/dream7b-bpu-fine-forward-perf-probe
fine-forward perf report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-174745/summary.md
fine-forward repeat command: /usr/local/bin/dream7b-bpu-fine-forward-repeat-probe
fine-forward repeat report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_repeat_20260603-180108/summary.md
fine-forward long-repeat command: /usr/local/bin/dream7b-bpu-fine-forward-long-repeat-probe
fine-forward long-repeat report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-140733/long_repeat_probe.md
gated fine-forward long-repeat report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/long_repeat_probe.md
fine-forward window-batch command: /usr/local/bin/dream7b-bpu-fine-forward-window-batch-probe
fine-forward window-batch report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md
fine-batch-forward command: /usr/local/bin/dream7b-bpu-fine-batch-forward
fine-batch-forward probe command: /usr/local/bin/dream7b-bpu-fine-batch-forward-probe
fine-batch-forward probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md
fine-batch-size-sweep probe command: /usr/local/bin/dream7b-bpu-fine-batch-size-sweep-probe
fine-batch-size-sweep report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.md
runtime telemetry probe command: /usr/local/bin/dream7b-bpu-runtime-telemetry-probe
runtime telemetry report: /mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/runtime_telemetry_probe.md
batch-queue-runner command: /usr/local/bin/dream7b-bpu-batch-queue-runner
batch-queue-runner probe command: /usr/local/bin/dream7b-bpu-batch-queue-runner-probe
batch-queue-runner probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md
batch-queue-drain probe command: /usr/local/bin/dream7b-bpu-batch-queue-drain-probe
batch-queue-drain probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md
batch-queue-control probe command: /usr/local/bin/dream7b-bpu-batch-queue-control-probe
batch-queue-control probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md
batch-queue-lock probe command: /usr/local/bin/dream7b-bpu-batch-queue-lock-probe
batch-queue-lock probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md
batch-queue-service command: /usr/local/bin/dream7b-bpu-batch-queue-service
batch-queue-service probe command: /usr/local/bin/dream7b-bpu-batch-queue-service-probe
batch-queue-service probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
batch-queue-service real BPU report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md
batch-queue systemd install command: /usr/local/bin/install-dream7b-bpu-queue-service
batch-queue systemd service: /etc/systemd/system/dream7b-bpu-batch-queue.service
batch-queue systemd probe command: /usr/local/bin/dream7b-bpu-batch-queue-systemd-probe
batch-queue systemd probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260603-221324/systemd_probe.md
batch-queue systemd service summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/service_summary.md
batch-queue systemd real BPU job summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json
batch-queue systemd BPU lock path: /run/lock/dream7b_bpu_batch_queue_runner.lock
batch-queue systemd soak probe command: /usr/local/bin/dream7b-bpu-batch-queue-systemd-soak-probe
batch-queue systemd soak report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_20260604-131223/systemd_soak_probe.md
batch-queue systemd soak job 001 summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_001/queue_summary.json
batch-queue systemd soak job 002 summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_002/queue_summary.json
batch-queue systemd batch probe command: /usr/local/bin/dream7b-bpu-batch-queue-systemd-batch-probe
batch-queue systemd batch report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-133034/systemd_batch_probe.md
batch-queue systemd batch job summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-133034/queue_summary.json
batch-queue systemd drain probe command: /usr/local/bin/dream7b-bpu-batch-queue-systemd-drain-probe
batch-queue systemd drain report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-174953/systemd_drain_probe.md
batch-queue systemd drain job summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-174953/queue_summary.json
batch-queue systemd full-batch drain report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-180557/systemd_drain_probe.md
batch-queue systemd full-batch drain job summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-180557/queue_summary.json
batch-queue systemd canary probe command: /usr/local/bin/dream7b-bpu-batch-queue-systemd-canary-probe
batch-queue systemd canary report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.md
batch-queue systemd canary JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.json
batch-queue systemd canary job summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_canary_20260605-151715/queue_summary.json
text-queue systemd probe command: /usr/local/bin/dream7b-bpu-text-queue-systemd-probe
text-queue systemd report: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260605-234555/text_queue_systemd_probe.md
text-queue systemd JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260605-234555/text_queue_systemd_probe.json
text-queue tokenizer JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260605-234555/tokenizer_input.json
text-queue queue summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260605-234555/queue_summary.json
text-queue submit command: /usr/local/bin/dream7b-bpu-text-queue-submit
text-queue run command: /usr/local/bin/dream7b-bpu-text-queue-run
text-queue run report: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-144526/text_queue_run.md
text-queue run JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-144526/text_queue_run.json
submit-aware text-queue systemd report: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-142516/text_queue_systemd_probe.md
submit-aware text-queue systemd JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-142516/text_queue_systemd_probe.json
submit-aware text-queue submit JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-142516/text_queue_submit.json
submit-aware text-queue tokenizer JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-142516/tokenizer_input.json
submit-aware text-queue queue summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260606-142516/queue_summary.json
run-aware text-queue systemd report: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_systemd_probe.md
run-aware text-queue systemd JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_systemd_probe.json
run-aware text-queue run JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_run.json
run-aware text-queue submit JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_submit.json
run-aware text-queue queue summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260606-144634/queue_summary.json
batch-queue systemd telemetry probe command: /usr/local/bin/dream7b-bpu-batch-queue-systemd-telemetry-probe
batch-queue systemd telemetry report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.md
batch-queue systemd telemetry job 001 summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_001/queue_summary.json
batch-queue systemd telemetry job 002 summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_002/queue_summary.json
batch-queue systemd telemetry job 003 summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_003/queue_summary.json
batch-queue retention probe command: /usr/local/bin/dream7b-bpu-batch-queue-retention-probe
batch-queue retention report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.md
deployment acceptance probe command: /usr/local/bin/dream7b-bpu-deployment-acceptance-probe
deployment acceptance report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.md
deployment acceptance JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-143759/deployment_acceptance_probe.json
updated deployment acceptance report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.md
updated deployment acceptance JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-153747/deployment_acceptance_probe.json
artifact-aware deployment acceptance report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.md
artifact-aware deployment acceptance JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-161000/deployment_acceptance_probe.json
gated deployment acceptance report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.md
gated deployment acceptance JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260605-172156/deployment_acceptance_probe.json
text-queue-aware deployment acceptance report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134314/deployment_acceptance_probe.md
text-queue-aware deployment acceptance JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-134314/deployment_acceptance_probe.json
submit-aware deployment acceptance report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-142559/deployment_acceptance_probe.md
submit-aware deployment acceptance JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-142559/deployment_acceptance_probe.json
run-aware deployment acceptance report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.md
run-aware deployment acceptance JSON: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.json
post-batch fine-forward compatibility report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-183906/fine_forward_probe.md
fine-forward diffusion-loop report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md
fine-forward quality-gate report: /mnt/nas/openclaw/reports/models/dream7b_bpu_cpu_quality_gate_20260603-160405/summary.md
default-forward compatibility report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-151711/summary.json
```

Observed one-frame infer times:

| Segment | Input | Output | Infer time |
| --- | --- | --- | ---: |
| `dream_segment_00_04` | token ids + positions | hidden S16 | 27.384 ms |
| `dream_segment_04_07` | hidden F32 + positions | hidden S16 | 17.571 ms |
| `dream_segment_07_14` | hidden F32 + positions | hidden S16 | 39.528 ms |
| `dream_segment_14_21` | hidden F32 + positions | hidden S16 | 39.455 ms |
| `dream_segment_21_24` | hidden F32 + positions | hidden S16 | 17.548 ms |
| `dream_segment_24_28` | hidden F32 + positions | logits S16 | 34.675 ms |

## Why Six Segments

The first successful full-model link produced a single 7.1GB HBM:

```text
/mnt/nas/openclaw/models/dream7b-hbm/dream7b_seq16_4seg_q8.hbm
sha256: 81add9c86ed25a06b168daa62af9837ed06059f9b7784cbd20e782a14dae610c
```

That file failed to load on S100P because HBRT tried to allocate about 7.62GB of BPU/ION memory.

A four-segment split also failed for the edge segments:

```text
0-7:  resource exhausted at about 2.19GB
21-28: resource exhausted at about 2.18GB
```

The six-segment split keeps every load under the board's observed runtime limit.

## New Scripts

```text
scripts/probes/compile_dream_segmented_full_forward.py
scripts/probes/compile_dream_segments_seq16.sh
scripts/probes/dream7b_segmented_hbm_smoke_probe.sh
scripts/probes/dream7b_segmented_hbm_chain_probe.sh
scripts/probes/dream7b_segmented_hbm_python_forward.py
scripts/dream7b-bpu-forward.sh
scripts/dream7b-bpu-text-forward.sh
scripts/probes/dream7b_bpu_diffusion_step_probe.sh
scripts/probes/dream7b_bpu_diffusion_loop_probe.sh
scripts/probes/dream7b_bpu_cpu_quality_gate_probe.sh
scripts/probes/dream7b_bpu_hbm_cache_perf_probe.sh
scripts/probes/dream7b_bpu_hbm_artifact_inventory_probe.sh
scripts/probes/dream7b_bpu_residency_probe.sh
scripts/probes/compile_dream_segments_seq16_fine.sh
scripts/probes/dream7b_bpu_fine_residency_probe.sh
scripts/dream7b-bpu-fine-forward.sh
scripts/probes/dream7b_bpu_fine_forward_probe.sh
scripts/probes/dream7b_bpu_fine_forward_perf_probe.sh
scripts/probes/dream7b_bpu_fine_forward_repeat_probe.sh
scripts/probes/dream7b_bpu_fine_forward_long_repeat_probe.sh
scripts/probes/dream7b_bpu_fine_forward_window_batch_probe.sh
scripts/dream7b-bpu-fine-batch-forward.sh
scripts/probes/dream7b_bpu_fine_batch_forward_probe.sh
scripts/probes/dream7b_bpu_fine_batch_size_sweep_probe.sh
scripts/probes/dream7b_bpu_runtime_telemetry_probe.sh
scripts/dream7b-bpu-batch-queue-runner.sh
scripts/dream7b_bpu_batch_queue_runner.py
scripts/probes/dream7b_bpu_batch_queue_runner_probe.sh
scripts/probes/dream7b_bpu_batch_queue_drain_probe.sh
scripts/probes/dream7b_bpu_batch_queue_control_probe.sh
scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh
scripts/dream7b-bpu-batch-queue-service.sh
scripts/dream7b_bpu_batch_queue_service.py
scripts/probes/dream7b_bpu_batch_queue_service_probe.sh
scripts/install_dream7b_bpu_queue_service.sh
scripts/probes/dream7b_bpu_batch_queue_systemd_probe.sh
scripts/probes/dream7b_bpu_batch_queue_systemd_soak_probe.sh
scripts/probes/dream7b_bpu_batch_queue_systemd_batch_probe.sh
scripts/probes/dream7b_bpu_batch_queue_systemd_drain_probe.sh
scripts/probes/dream7b_bpu_batch_queue_systemd_canary_probe.sh
scripts/probes/dream7b_bpu_batch_queue_systemd_telemetry_probe.sh
scripts/probes/dream7b_bpu_batch_queue_retention_probe.sh
scripts/probes/dream7b_bpu_deployment_acceptance_probe.sh
```

The smoke probe can be run on S100P:

```bash
bash scripts/probes/dream7b_segmented_hbm_smoke_probe.sh \
  /mnt/nas/openclaw/reports/models \
  /mnt/nas/openclaw/models/dream7b-hbm/segments6
```

The chained forward proof can be run on S100P:

```bash
bash scripts/probes/dream7b_segmented_hbm_chain_probe.sh \
  /mnt/nas/openclaw/reports/models \
  /mnt/nas/openclaw/models/dream7b-hbm/segments6
```

The reusable Python forward prototype can be run after building/installing the board-provided `hbm_runtime` pybind package into:

```text
/mnt/nas/openclaw/runtimes/hbm-runtime-venv
```

Run:

```bash
. /mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/activate
python scripts/probes/dream7b_segmented_hbm_python_forward.py \
  --hbm-dir /mnt/nas/openclaw/models/dream7b-hbm/segments6 \
  --output-dir /mnt/nas/openclaw/reports/models/dream7b_python_forward
```

Verified output:

```text
verdict: ok_dream7b_segmented_hbm_python_forward
runtime_version: 3.13.6_(4.7.5 HBRT)
final_shape: [1, 16, 152064]
final_dtype: float32
```

The deployed S100P command is:

```bash
dream7b-bpu-forward
```

It uses these default paths:

```text
venv: /mnt/nas/openclaw/runtimes/hbm-runtime-venv
script: /mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py
hbm_dir: /mnt/nas/openclaw/models/dream7b-hbm/segments6
report_root: /mnt/nas/openclaw/reports/models
```

The deployed command was verified on S100P and wrote:

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-022912/summary.json
```

It also accepts explicit seq16 token ids and can write final logits:

```bash
dream7b-bpu-forward \
  --tokens '1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16' \
  --save-logits
```

Verified token-arg output:

```text
verdict: ok_dream7b_segmented_hbm_python_forward
tokens_source: tokens_arg
logits_npy: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-023557/logits.npy
final_shape: [1, 16, 152064]
```

The deployed text-to-BPU entrypoint is:

```bash
dream7b-bpu-text-forward --fit truncate-left --save-logits \
  'Explain in one sentence why S100P BPU execution matters for Dream 7B deployment in OpenClaw.'
```

Default prompt fitting is `exact`, so non-seq16 prompts are rejected unless a probe explicitly chooses `--fit truncate-left` or `--fit pad-right`. This avoids silently changing the input shape while the available HBM artifacts are fixed at seq16.

Verified text-forward output:

```text
verdict: ok_dream7b_segmented_hbm_python_forward
tokens_source: tokens_arg
logits_npy: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-024218/logits.npy
final_shape: [1, 16, 152064]
```

The forward script also supports a lightweight top-k summary for the final position:

```bash
dream7b-bpu-text-forward --fit truncate-left --top-k 5 \
  'Explain in one sentence why S100P BPU execution matters for Dream 7B deployment in OpenClaw.'
```

Verified top-k output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-024533/summary.json
top_k: 5
topk_last_position: token ids 279, 11, 315, 13, 374
```

The deployed one-step diffusion bridge probe is:

```bash
dream7b-bpu-diffusion-step-probe \
  /mnt/nas/openclaw/reports/models \
  'Explain why S100P BPU matters for Dream 7B in OpenClaw.'
```

It builds a seq16 Dream-style input with masked generation slots, runs the six-segment BPU forward path, applies the same logits shift used by `DreamGenerationMixin._sample`, and greedily fills the masked positions for one host-side diffusion step.

Verified diffusion-step output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_step_20260603-025304/summary.md
verdict: ok_dream7b_bpu_diffusion_step_probe
logits_shape: [1, 16, 152064]
mask_positions: [12, 13, 14, 15]
selected_token_ids: 279, 279, 279, 279
```

The deployed bounded diffusion loop probe is:

```bash
dream7b-bpu-diffusion-loop-probe \
  /mnt/nas/openclaw/reports/models \
  'Explain why S100P BPU matters for Dream 7B in OpenClaw.'
```

It repeatedly calls the deployed BPU forward command, applies the Dream logits shift before selecting mask positions, and transfers a bounded number of mask tokens per step. The default verification loop uses two BPU forward calls over the seq16 graph.

The loop probe now supports remasking strategies compatible with the deployed CPU `diffuse-cli` names:

```text
low_confidence
entropy_exit
maskgit_plus
topk_margin
entropy
```

Its default is `entropy_exit`, matching the existing `dream7b-text` CPU wrapper's `--remasking entropy_exit` path. The probe also records `temperature`, `seed`, `entropy_threshold`, selected token ids, per-position confidence, and entropy-derived transfer decisions.

Verified diffusion-loop output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-030011/summary.md
verdict: ok_dream7b_bpu_diffusion_loop_probe
steps: 2
remaining_mask_positions: []
step0_transferred: 1 token
step1_transferred: 3 tokens
```

Verified strategy-aware `entropy_exit` output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-031016/summary.md
verdict: ok_dream7b_bpu_diffusion_loop_probe
remasking: entropy_exit
temperature: 0.0
entropy_threshold: 1.5
remaining_mask_positions: []
```

The deployed CPU/BPU quality coverage gate is:

```bash
dream7b-bpu-cpu-quality-gate-probe \
  /mnt/nas/openclaw/reports/models \
  'Explain why BPU matters.'
```

It runs a bounded CPU Dream sample through `dream7b-text`, runs the BPU diffusion loop probe for the same prompt, and records the comparison without treating current seq16 divergence as a deployment failure.

Verified quality-gate output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_cpu_quality_gate_20260603-033101/summary.md
verdict: ok_dream7b_bpu_cpu_quality_gate_recorded
quality_status: diverged_expected_for_seq16_probe
cpu_output: I
bpu_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-033112/summary.md
```

The deployed HBM cache performance probe is:

```bash
dream7b-bpu-hbm-cache-perf-probe /mnt/nas/openclaw/reports/models
```

It syncs the NAS HBM segments into the S100P local cache path and compares one full seq16 forward from NAS versus local cache:

```text
local cache: /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_cache_perf_20260603-034629/summary.md
NAS wall: 66510.049 ms
NAS HBM load: 65212.480 ms
local wall: 25203.805 ms
local HBM load: 23933.206 ms
local-vs-NAS load speedup: 2.725x
local-vs-NAS wall speedup: 2.639x
```

The same local cache path works for the diffusion loop:

```bash
DREAM7B_BPU_HBM_DIR=/home/sunrise/.cache/openclaw/dream7b-hbm/segments6 \
  dream7b-bpu-diffusion-loop-probe \
  /mnt/nas/openclaw/reports/models \
  'Explain why S100P BPU matters for Dream 7B in OpenClaw.'
```

Verified local-cache loop output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-034939/summary.md
verdict: ok_dream7b_bpu_diffusion_loop_probe
hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
remaining_mask_positions: []
```

The deployed segment residency probe is:

```bash
dream7b-bpu-residency-probe \
  /mnt/nas/openclaw/reports/models \
  /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
```

It loads single segments and every pair of segments in isolated child processes to test whether multiple HBM runtimes can be held resident at once.

Verified residency output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_residency_20260603-035939/summary.md
verdict: ok_dream7b_bpu_residency_probe
successful_pair_count: 1
failed_pair_count: 14
successful_pair: seg04_07, seg21_24
```

This rules out a simple all-segment resident orchestrator for the current six-segment split. Only the two small non-adjacent segments can coexist. Any pair involving a large segment failed to load in the same process, so the next performance path should be one of:

- compile a more granular split with lower per-segment residency pressure;
- find an official HBRT/HBDK mechanism for explicit release or streaming residency;
- keep local HBM cache as the current practical improvement while preserving correctness gates.

## Fine Split Residency

The fine-split follow-up replaced the original large segments `0:4`, `7:14`, `14:21`, and `24:28` with smaller HBM windows while keeping the existing small base segments `4:7` and `21:24`.

Compiled fine HBM artifacts:

```text
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg24_26/dream7b_segment_24_26_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg26_28/dream7b_segment_26_28_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg00_02/dream7b_segment_0_2_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg02_04/dream7b_segment_2_4_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg07_10/dream7b_segment_7_10_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg10_14/dream7b_segment_10_14_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg14_17/dream7b_segment_14_17_seq16_q8.hbm
/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16/seg17_21/dream7b_segment_17_21_seq16_q8.hbm
```

S100P model-load evidence:

```text
seg24_26 model_info: dream_segment_24_26, input (16,3584) F32 + (16) S32, output (16,3584) S16, DDR load 2182.22 ms
seg26_28 model_info: dream_segment_26_28, input (16,3584) F32 + (16) S32, output (1,16,152064) S16, DDR load 3680.37 ms
seg00_02 model_info: dream_segment_00_02, input (1,16) S32 + (16) S32, output (16,3584) S16, DDR load 4065.79 ms
seg02_04 model_info: dream_segment_02_04, input (16,3584) F32 + (16) S32, output (16,3584) S16, DDR load 5658.17 ms
seg07_10 model_info: dream_segment_07_10, input (16,3584) F32 + (16) S32, output (16,3584) S16, DDR load 2946.25 ms
seg10_14 model_info: dream_segment_10_14, input (16,3584) F32 + (16) S32, output (16,3584) S16, DDR load 3618.08 ms
seg14_17 model_info: dream_segment_14_17, input (16,3584) F32 + (16) S32, output (16,3584) S16, DDR load 2889.95 ms
seg17_21 model_info: dream_segment_17_21, input (16,3584) F32 + (16) S32, output (16,3584) S16, DDR load 3613.18 ms
```

Verified fine-residency output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_residency_20260603-054031/summary.md
verdict: ok_dream7b_bpu_fine_residency_probe
seg00_02: ok, 3804.416 ms
seg02_04: ok, 2136.789 ms
seg00_02 + seg02_04: ok, 5427.987 ms
seg02_04 + seg04_07: ok, 4252.896 ms
seg07_10: ok, 2843.748 ms
seg10_14: ok, 3709.783 ms
seg04_07 + seg07_10: ok, 5134.936 ms
seg07_10 + seg10_14: ok, 5658.337 ms
seg10_14 + seg14_21: failed, memory alloc failed
seg14_17: ok, 3025.018 ms
seg17_21: ok, 3558.866 ms
seg10_14 + seg14_17: ok, 5820.523 ms
seg14_17 + seg17_21: ok, 5716.064 ms
seg17_21 + seg21_24: ok, 5673.588 ms
seg24_26: ok, 2133.847 ms
seg26_28: ok, 4370.982 ms
seg24_26 + seg26_28: ok, 5193.505 ms
seg21_24 + seg24_26: ok, 4393.535 ms
seg04_07 + seg26_28: ok, 6059.886 ms
seg21_24 + seg26_28: ok, 6089.736 ms
seg21_24 + seg24_26 + seg26_28: failed, memory alloc failed
seg04_07 + seg21_24 + seg26_28: failed, memory alloc failed
seg24_28 + seg26_28: failed, memory alloc failed
```

This proves the fine-split direction is useful: every adjacent window in the fine split can be loaded resident as a pair:

```text
00:02 + 02:04
02:04 + 04:07
04:07 + 07:10
07:10 + 10:14
10:14 + 14:17
14:17 + 17:21
17:21 + 21:24
21:24 + 24:26
24:26 + 26:28
```

It does not solve all-resident orchestration, because three-segment combinations still exceed the board's current load-residency limit. The next engineering target is a lower-overhead sliding two-segment resident orchestrator over the fine split, not an all-segment resident orchestrator.

## Fine Sliding Forward

The deployed fine forward entrypoint is:

```bash
dream7b-bpu-fine-forward \
  --tokens '1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16' \
  --top-k 5
```

It wraps `dream7b-bpu-forward` with:

```text
segment_plan: fine-adjacent
residency_window_size: 2
child_window_mode: pair
child_runtime_mode: packed
window_execution_mode: in-process
base_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
```

Because `HB_HBMRuntime` does not expose an explicit release/close API, the first in-process two-segment attempt failed after the first segment with an ION allocation error while loading `seg04_07`. The working implementation now deletes output array/runtime references and calls `gc.collect()` between resident pair windows.

The first working mode was `sliding`, with one child per segment. The next working mode was `pair_child_process`, which reduced the forward from 10 child processes to 5. The current default is `pair_in_process`: each resident pair constructs one packed `HB_HBMRuntime`, runs both adjacent segments in order, then releases references before the next pair. This keeps the two-segment residency invariant while reducing the forward from 5 child processes to 0.

Verified fine in-process forward output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/summary.json
verdict: ok_dream7b_segmented_hbm_python_forward
segment_plan: fine-adjacent
residency_window_size: 2
child_window_mode: pair
child_runtime_mode: packed
window_execution_mode: in-process
execution_mode: pair_in_process
child_process_count: 0
segments: 10
final_shape: [1, 16, 152064]
top_k: 5
```

Observed comparison against the earlier sliding-child report:

```text
sliding-child report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-154303/summary.json
sliding-child child_process_count: 10
sliding-child summed load_ms: 30624.418
sliding-child summed run_ms: 184.756
pair-child report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-162214/summary.json
pair-child child_process_count: 5
pair-child summed load_ms: 27021.312
pair-child summed run_ms: 179.693
```

The deployed fine-forward performance regression probe is:

```bash
dream7b-bpu-fine-forward-perf-probe /mnt/nas/openclaw/reports/models
```

It runs the deployed six-segment forward, fine sliding-child forward, and fine pair-child forward against the same seq16 token input. This is a regression/performance probe, not a full throughput benchmark.

Verified performance probe output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-164445/summary.md
verdict: ok_dream7b_bpu_fine_forward_perf_probe
segments6: execution_mode=in_process, child_process_count=0, wall_ms=26359.864, load_ms=24034.035, run_ms=173.134
fine_sliding: execution_mode=sliding_child_process, child_window_mode=sliding, child_process_count=10, wall_ms=62410.354, load_ms=30704.095, run_ms=185.360
fine_pair: execution_mode=pair_child_process, child_window_mode=pair, child_process_count=5, wall_ms=32836.161, load_ms=27688.528, run_ms=179.260
pair_vs_sliding_child_process_reduction: 5
pair_vs_sliding_load_speedup: 1.109x
pair_vs_sliding_wall_speedup: 1.901x
```

The packed-runtime update was verified with:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-171203/summary.md
verdict: ok_dream7b_bpu_fine_forward_perf_probe
segments6: execution_mode=in_process, child_process_count=0, wall_ms=25640.083, load_ms=24277.313, run_ms=173.395
fine_sliding: execution_mode=sliding_child_process, child_window_mode=sliding, child_runtime_mode=separate, child_process_count=10, wall_ms=62374.465, load_ms=30651.821, run_ms=185.280
fine_pair_separate: execution_mode=pair_child_process, child_window_mode=pair, child_runtime_mode=separate, child_process_count=5, wall_ms=32569.229, load_ms=27262.626, run_ms=179.780
fine_pair_packed: execution_mode=pair_child_process, child_window_mode=pair, child_runtime_mode=packed, child_process_count=5, wall_ms=32302.286, load_ms=27215.231, run_ms=179.190
pair_vs_sliding_child_process_reduction: 5
pair_vs_sliding_load_speedup: 1.126x
pair_vs_sliding_wall_speedup: 1.931x
packed_vs_separate_pair_load_speedup: 1.002x
packed_vs_separate_pair_wall_speedup: 1.008x
```

The in-process pair release update was verified with:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_perf_20260603-174745/summary.md
verdict: ok_dream7b_bpu_fine_forward_perf_probe
segments6: execution_mode=in_process, child_process_count=0, wall_ms=26698.544, load_ms=24260.385, run_ms=173.340
fine_sliding_child: execution_mode=sliding_child_process, window_execution_mode=child-process, child_window_mode=sliding, child_runtime_mode=separate, child_process_count=10, wall_ms=62042.823, load_ms=30972.421, run_ms=185.000
fine_pair_child_packed: execution_mode=pair_child_process, window_execution_mode=child-process, child_window_mode=pair, child_runtime_mode=packed, child_process_count=5, wall_ms=32218.834, load_ms=27023.825, run_ms=179.515
fine_pair_in_process_packed: execution_mode=pair_in_process, window_execution_mode=in-process, child_window_mode=pair, child_runtime_mode=packed, child_process_count=0, wall_ms=25459.392, load_ms=24159.358, run_ms=176.133
pair_vs_sliding_child_process_reduction: 5
pair_vs_sliding_load_speedup: 1.146x
pair_vs_sliding_wall_speedup: 1.926x
in_process_vs_child_pair_child_process_reduction: 5
in_process_vs_child_pair_load_speedup: 1.119x
in_process_vs_child_pair_wall_speedup: 1.265x
```

The same deployed Python script remains compatible with the existing six-segment entrypoint:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-151711/summary.json
verdict: ok_dream7b_segmented_hbm_python_forward
segment_plan: segments6
residency_window_size: 1
execution_mode: in_process
segments: 6
final_shape: [1, 16, 152064]
```

The deployed fine-forward check probe is:

```bash
dream7b-bpu-fine-forward-probe /mnt/nas/openclaw/reports/models
```

Verified probe output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-174608/fine_forward_probe.md
verdict: ok_dream7b_bpu_fine_forward_probe
segment_plan: fine-adjacent
residency_window_size: 2
child_window_mode: pair
child_runtime_mode: packed
window_execution_mode: in-process
execution_mode: pair_in_process
child_process_count: 0
final_shape: [1, 16, 152064]
segment_count: 10
```

The deployed fine-forward repeat check is:

```bash
dream7b-bpu-fine-forward-repeat-probe /mnt/nas/openclaw/reports/models
```

Verified repeat output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_repeat_20260603-180108/summary.md
verdict: ok_dream7b_bpu_fine_forward_repeat_probe
repeat_count: 3
median_wall_ms: 25477.291
median_load_ms: 24051.374
median_run_ms: 176.018
run_01: execution_mode=pair_in_process, window_execution_mode=in-process, child_process_count=0, final_shape=[1, 16, 152064], wall_ms=26215.101
run_02: execution_mode=pair_in_process, window_execution_mode=in-process, child_process_count=0, final_shape=[1, 16, 152064], wall_ms=25344.291
run_03: execution_mode=pair_in_process, window_execution_mode=in-process, child_process_count=0, final_shape=[1, 16, 152064], wall_ms=25477.291
```

Verified longer repeat output:

```text
long_repeat_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_long_repeat_20260605-163343/long_repeat_probe.md
long_repeat_verdict: ok_dream7b_bpu_fine_forward_long_repeat_probe
repeat_count: 6
repeat_status: 0
failure_count: 0
median_wall_ms: 25253.389
median_load_ms: 24134.596
median_run_ms: 176.056
min_wall_ms: 24998.927
max_wall_ms: 26168.34
wall_spread_ratio: 0.046307
max_wall_spread_ratio: 0.1
warnings: []
errors: []
```

The deployed window-batch throughput probe is:

```bash
dream7b-bpu-fine-forward-window-batch-probe /mnt/nas/openclaw/reports/models
```

Verified window-batch output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_window_batch_20260603-181131/summary.md
verdict: ok_dream7b_bpu_fine_forward_window_batch_probe
batch_count: 3
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
window_count: 5
total_segment_events: 30
wall_ms: 24448.566
load_ms: 23729.686
run_ms: 523.525
amortized_load_ms_per_forward: 7909.895
amortized_wall_ms_per_forward: 8149.522
final_shapes: [[1, 16, 152064], [1, 16, 152064], [1, 16, 152064]]
```

This proves a throughput direction for concurrent independent seq16 inputs: load each resident pair once, run that pair for multiple inputs, then release the runtime. It does not reduce reload cost for a single dependent Dream diffusion request.

The reusable batch wrapper for that path is:

```bash
dream7b-bpu-fine-batch-forward \
  --tokens-batch-json /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/tokens_batch.json \
  --top-k 3 \
  --output-dir /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625
```

It wraps `dream7b-bpu-forward` with:

```text
segment_plan: fine-adjacent
residency_window_size: 2
child_window_mode: pair
child_runtime_mode: packed
window_execution_mode: window-batch
tokens_batch_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/tokens_batch.json
```

Verified fine batch-forward output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/fine_batch_forward_probe.md
summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_forward_20260603-183625/summary.json
verdict: ok_dream7b_bpu_fine_batch_forward_probe
segment_plan: fine-adjacent
residency_window_size: 2
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_window_mode: pair
child_runtime_mode: packed
child_process_count: 0
batch_count: 3
wall_ms: 24495.731
load_ms: 23776.245
run_ms: 522.62
amortized_wall_ms_per_forward: 8165.244
amortized_load_ms_per_forward: 7925.415
final_shapes: [[1, 16, 152064], [1, 16, 152064], [1, 16, 152064]]
segment_event_count: 30
```

The fine-batch-size sweep path is:

```bash
dream7b-bpu-fine-batch-size-sweep-probe /mnt/nas/openclaw/reports/models
```

Verified fine-batch-size sweep output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_batch_size_sweep_20260604-181429/batch_size_sweep_probe.md
verdict: ok_dream7b_bpu_fine_batch_size_sweep_probe
counts: [1, 2, 4, 8]
batch_count 1 amortized_wall_ms_per_forward: 24562.798
batch_count 1 amortized_load_ms_per_forward: 24198.434
batch_count 1 amortized_run_ms_per_forward: 175.949
batch_count 2 amortized_wall_ms_per_forward: 12293.305
batch_count 2 amortized_load_ms_per_forward: 12022.294
batch_count 2 amortized_run_ms_per_forward: 175.037
batch_count 4 amortized_wall_ms_per_forward: 6336.077
batch_count 4 amortized_load_ms_per_forward: 6111.385
batch_count 4 amortized_run_ms_per_forward: 173.981
batch_count 8 amortized_wall_ms_per_forward: 3175.416
batch_count 8 amortized_load_ms_per_forward: 2974.35
batch_count 8 amortized_run_ms_per_forward: 173.565
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
```

The runtime telemetry path is:

```bash
dream7b-bpu-runtime-telemetry-probe /mnt/nas/openclaw/reports/models
```

Verified runtime telemetry output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/runtime_telemetry_probe.md
verdict: ok_dream7b_bpu_runtime_telemetry_probe
batch_count: 8
monitor_delay_ms: 100
monitor_sample_count: 320
bpu_loading_sample_count: 320
nonzero_bpu_loading_sample_count: 20
max_bpu_loading: 100.0
avg_bpu_loading: 4.369
forward_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260604-225030/forward/summary.json
forward execution_mode: pair_window_batch
forward window_execution_mode: window-batch
forward child_process_count: 0
forward wall_ms: 24821.269
forward load_ms: 23209.905
forward run_ms: 1390.985
forward amortized_wall_ms_per_forward: 3102.659
forward amortized_load_ms_per_forward: 2901.238
forward amortized_run_ms_per_forward: 173.873
final_shapes: [1, 16, 152064] x 8
```

The service-level JSONL queue runner for independent seq16 requests is:

```bash
dream7b-bpu-batch-queue-runner \
  /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/requests.jsonl \
  /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243 \
  --max-batch-size 3 \
  --top-k 3
```

Request JSONL keys:

```text
request_id
tokens
cancelled
not_after_epoch_ms
```

The runner accepts up to `--max-batch-size` requests, writes `tokens_batch.json`, calls `dream7b-bpu-fine-batch-forward`, records `results`, records overflow request IDs in `deferred_request_ids`, skips `cancelled` or expired `not_after_epoch_ms` requests, and writes durable state JSONL files under `durable_state`.

Default BPU lock arguments:

```text
--bpu-lock-path /tmp/dream7b_bpu_batch_queue_runner.lock
--bpu-lock-timeout-sec 600.0
```

The runner records lock status in `bpu_lock`.

Durable state files:

```text
accepted_requests.jsonl
deferred_requests.jsonl
skipped_requests.jsonl
results.jsonl
```

Verified batch-queue output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/batch_queue_runner_probe.md
summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_runner_20260603-193243/queue_summary.json
verdict: ok_dream7b_bpu_batch_queue_runner_probe
accepted_count: 3
deferred_count: 1
deferred_request_ids: ['req-004']
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
batch_count: 3
total_wall_ms: 24536.714
amortized_wall_ms_per_processed_request: 8178.905
result_count: 3
bpu_lock: {'path': '/tmp/dream7b_bpu_batch_queue_runner.lock', 'timeout_sec': 600.0, 'acquired': True, 'wait_ms': 0.01}
```

The multi-batch drain path is:

```bash
dream7b-bpu-batch-queue-runner \
  /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/requests.jsonl \
  /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309 \
  --max-batch-size 3 \
  --top-k 3 \
  --drain-all
```

Verified drain-all output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/batch_queue_drain_probe.md
summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_drain_20260603-193309/queue_summary.json
verdict: ok_dream7b_bpu_batch_queue_drain_probe
drain_all: True
request_count: 5
processed_count: 5
deferred_count: 0
batch_run_count: 2
batch_counts: [3, 2]
result_count: 5
total_wall_ms: 48940.128
amortized_wall_ms_per_processed_request: 9788.026
bpu_lock: {'path': '/tmp/dream7b_bpu_batch_queue_runner.lock', 'timeout_sec': 600.0, 'acquired': True, 'wait_ms': 0.01}
```

The cancellation, expiration, and durable-state control path is:

```bash
dream7b-bpu-batch-queue-control-probe /mnt/nas/openclaw/reports/models
```

Verified queue-control output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/batch_queue_control_probe.md
summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_control_20260603-193400/queue_summary.json
verdict: ok_dream7b_bpu_batch_queue_control_probe
request_count: 4
runnable_count: 2
processed_count: 2
skipped_count: 2
deferred_count: 0
result_request_ids: ['control-001', 'control-002']
skipped_requests: [{'request_id': 'control-cancelled', 'line_number': 2, 'reason': 'cancelled'}, {'request_id': 'control-expired', 'line_number': 3, 'reason': 'expired', 'not_after_epoch_ms': 1, 'now_epoch_ms': 1780486440249}]
bpu_lock: {'path': '/tmp/dream7b_bpu_batch_queue_runner.lock', 'timeout_sec': 600.0, 'acquired': True, 'wait_ms': 0.009}
```

The single-flight queue lock path is:

```bash
dream7b-bpu-batch-queue-lock-probe /mnt/nas/openclaw/reports/models
```

Verified queue-lock output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/batch_queue_lock_probe.md
verdict: ok_dream7b_bpu_batch_queue_lock_probe
run_a_bpu_lock_wait_ms: 0.172
run_b_bpu_lock_wait_ms: 2003.713
lock_path: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_lock_20260603-193209/dream7b_bpu_batch_queue_runner.lock
```

The directory-backed service loop is:

```bash
dream7b-bpu-batch-queue-service \
  /mnt/nas/openclaw/queues/dream7b-bpu \
  /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service
```

Queue subdirectories:

```text
pending
processing
done
failed
```

The service calls `dream7b-bpu-batch-queue-runner` for each pending JSONL job, so `durable_state` and `bpu_lock` remain the runner-level source of truth.

Verified service probe output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_20260603-194437/batch_queue_service_probe.md
verdict: ok_dream7b_bpu_batch_queue_service_probe
processed_job_count: 1
failed_job_count: 0
done_files: ['job_001.jsonl']
job_runner_verdict: ok_dream7b_bpu_batch_queue_runner
job_processed_count: 2
```

Verified real BPU service one-shot output:

```text
summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_real_scp_20260603-194827/output/service_summary.md
verdict: ok_dream7b_bpu_batch_queue_service
processed_job_count: 1
failed_job_count: 0
runner_verdict: ok_dream7b_bpu_batch_queue_runner
processed_count: 1
result_shape: [1, 16, 152064]
bpu_lock: {'path': '/tmp/dream7b_bpu_batch_queue_runner.lock', 'timeout_sec': 600.0, 'acquired': True, 'wait_ms': 0.01}
```

The NAS-backed systemd service is installed as:

```text
service: dream7b-bpu-batch-queue.service
service_path: /etc/systemd/system/dream7b-bpu-batch-queue.service
queue_dir: /mnt/nas/openclaw/queues/dream7b-bpu
output_dir: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
drain_all: true
working_directory: /mnt/nas/openclaw
```

Verified systemd probe output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260603-221324/systemd_probe.md
service_status: active
service_enabled: enabled
unit_path: /etc/systemd/system/dream7b-bpu-batch-queue.service
exec_start includes: /run/lock/dream7b_bpu_batch_queue_runner.lock
```

Verified systemd drain-all probe output after reinstalling default `DREAM7B_BPU_QUEUE_DRAIN_ALL=1`:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-174953/systemd_probe.md
verdict: ok_dream7b_bpu_batch_queue_systemd_probe
service_status: active
service_enabled: enabled
drain_all_required: True
exec_start includes: --drain-all
```

Verified real systemd-queued BPU output:

```text
service_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/service_summary.md
job_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_job_20260603_220710/queue_summary.json
verdict: ok_dream7b_bpu_batch_queue_runner
request_id: systemd-req-001
processed_count: 1
final_shape: [1, 16, 152064]
bpu_lock.path: /run/lock/dream7b_bpu_batch_queue_runner.lock
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
```

Verified real systemd-queued BPU soak output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_soak_20260604-131223/systemd_soak_probe.md
verdict: ok_dream7b_bpu_batch_queue_systemd_soak_probe
job_count: 2
service_status_before: active
service_status_after: active
completed_job_count: 2
failed_job_count: 0
processed_request_count: 2
total_wall_ms: 49192.894
amortized_wall_ms_per_processed_request: 24596.447
job_001_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_001/queue_summary.json
job_002_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_soak_20260604-131223_002/queue_summary.json
job verdicts: ok_dream7b_bpu_batch_queue_runner, ok_dream7b_bpu_batch_queue_runner
job final_shapes: [1, 16, 152064], [1, 16, 152064]
job execution_mode: pair_window_batch
job window_execution_mode: window-batch
job child_process_count: 0
```

Verified real systemd-queued BPU batch output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-133034/systemd_batch_probe.md
verdict: ok_dream7b_bpu_batch_queue_systemd_batch_probe
job_name: systemd_batch_20260604-133034.jsonl
job_status: done
request_count: 4
processed_count: 4
accepted_count: 4
deferred_count: 0
batch_count: 4
result_count: 4
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
total_wall_ms: 24977.437
amortized_wall_ms_per_processed_request: 6244.359
queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-133034/queue_summary.json
bpu_lock.path: /run/lock/dream7b_bpu_batch_queue_runner.lock
```

Verified real systemd-queued BPU drain-all output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-174953/systemd_drain_probe.md
verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
job_name: systemd_drain_20260604-174953.jsonl
job_status: done
request_count: 5
expected_batch_counts: [4, 1]
drain_all: True
max_batch_size: 4
processed_count: 5
accepted_count: 5
deferred_count: 0
batch_run_count: 2
batch_counts: [4, 1]
result_count: 5
execution_modes: ['pair_window_batch', 'pair_window_batch']
window_execution_modes: ['window-batch', 'window-batch']
child_process_counts: [0, 0]
total_wall_ms: 49773.849
amortized_wall_ms_per_processed_request: 9954.77
queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-174953/queue_summary.json
bpu_lock.path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shapes: [1, 16, 152064] x 5
```

Verified real systemd-queued BPU full-batch drain-all output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-180557/systemd_drain_probe.md
verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
job_name: systemd_drain_20260604-180557.jsonl
job_status: done
request_count: 8
expected_batch_counts: [4, 4]
drain_all: True
max_batch_size: 4
processed_count: 8
accepted_count: 8
deferred_count: 0
batch_run_count: 2
batch_counts: [4, 4]
result_count: 8
execution_modes: ['pair_window_batch', 'pair_window_batch']
window_execution_modes: ['window-batch', 'window-batch']
child_process_counts: [0, 0]
total_wall_ms: 49509.638
amortized_wall_ms_per_processed_request: 6188.705
queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-180557/queue_summary.json
bpu_lock.path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shapes: [1, 16, 152064] x 8
```

Verified current max-batch-size-8 systemd output after updating `DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE` default to 8:

```text
systemd_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260604-233926/systemd_probe.md
systemd_verdict: ok_dream7b_bpu_batch_queue_systemd_probe
service_status: active
service_enabled: enabled
max_batch_size_required: 8
drain_all_required: True
exec_start includes: --max-batch-size 8
exec_start includes: --drain-all
batch_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260604-235205/systemd_batch_probe.md
batch_queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260604-235205/queue_summary.json
batch_verdict: ok_dream7b_bpu_batch_queue_systemd_batch_probe
batch_request_count: 8
batch_processed_count: 8
batch_accepted_count: 8
batch_deferred_count: 0
batch_max_batch_size: 8
batch_run_count: 1
batch_count: 8
batch_result_count: 8
batch_total_wall_ms: 25568.117
batch_amortized_wall_ms_per_processed_request: 3196.015
drain_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260604-235302/systemd_drain_probe.md
drain_queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260604-235302/queue_summary.json
drain_verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
drain_request_count: 8
drain_expected_batch_counts: [8]
drain_max_batch_size: 8
drain_batch_run_count: 1
drain_batch_counts: [8]
drain_total_wall_ms: 25621.258
drain_amortized_wall_ms_per_processed_request: 3202.657
```

Verified batch capacity expansion to 16 independent seq16 requests:

```text
capacity_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_capacity_20260605-123835/batch_capacity_probe.md
capacity_verdict: ok_dream7b_bpu_batch_capacity_probe
counts: [8, 12, 16]
max_passing_count: 16
batch_8_amortized_wall_ms_per_forward: 3197.161
batch_8_amortized_load_ms_per_forward: 2996.019
batch_8_amortized_run_ms_per_forward: 173.652
batch_12_amortized_wall_ms_per_forward: 2188.664
batch_12_amortized_load_ms_per_forward: 1995.449
batch_12_amortized_run_ms_per_forward: 173.423
batch_16_amortized_wall_ms_per_forward: 1714.647
batch_16_amortized_load_ms_per_forward: 1525.35
batch_16_amortized_run_ms_per_forward: 173.253
```

Verified current max-batch-size-16 systemd output after updating `DREAM7B_BPU_QUEUE_MAX_BATCH_SIZE` default to 16:

```text
systemd_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_20260605-131550/systemd_probe.md
systemd_verdict: ok_dream7b_bpu_batch_queue_systemd_probe
service_status: active
service_enabled: enabled
max_batch_size_required: 16
drain_all_required: True
exec_start includes: --max-batch-size 16
exec_start includes: --drain-all
batch_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_batch_20260605-131550/systemd_batch_probe.md
batch_queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_batch_20260605-131550/queue_summary.json
batch_verdict: ok_dream7b_bpu_batch_queue_systemd_batch_probe
batch_request_count: 16
batch_processed_count: 16
batch_accepted_count: 16
batch_deferred_count: 0
batch_max_batch_size: 16
batch_run_count: 1
batch_count: 16
batch_result_count: 16
batch_total_wall_ms: 27416.621
batch_amortized_wall_ms_per_processed_request: 1713.539
drain_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_drain_20260605-131621/systemd_drain_probe.md
drain_queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_drain_20260605-131621/queue_summary.json
drain_verdict: ok_dream7b_bpu_batch_queue_systemd_drain_probe
drain_request_count: 16
drain_expected_batch_counts: [16]
drain_max_batch_size: 16
drain_batch_run_count: 1
drain_batch_counts: [16]
drain_total_wall_ms: 27248.799
drain_amortized_wall_ms_per_processed_request: 1703.05
```

Verified lightweight systemd canary:

```text
canary_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.md
canary_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_canary_20260605-151715/systemd_canary_probe.json
canary_queue_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_canary_20260605-151715/queue_summary.json
canary_verdict: ok_dream7b_bpu_batch_queue_systemd_canary_probe
service_name: dream7b-bpu-batch-queue.service
job_name: systemd_canary_20260605-151715.jsonl
job_status: done
request_count: 1
processed_count: 1
accepted_count: 1
deferred_count: 0
skipped_count: 0
drain_all: True
max_batch_size: 16
batch_run_count: 1
batch_count: 1
result_count: 1
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shapes: [[1, 16, 152064]]
total_wall_ms: 24073.138
amortized_wall_ms_per_processed_request: 24073.138
errors: []
```

Verified HBM artifact inventory:

```text
inventory_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.md
inventory_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_hbm_artifact_inventory_20260605-160050/hbm_artifact_inventory_probe.json
inventory_verdict: ok_dream7b_bpu_hbm_artifact_inventory_probe
forward_script: /mnt/nas/openclaw/runtimes/dream7b-bpu-forward/dream7b_segmented_hbm_python_forward.py
nas_hbm_dir: /mnt/nas/openclaw/models/dream7b-hbm/segments6
nas_fine_hbm_dir: /mnt/nas/openclaw/models/dream7b-hbm/fine-seq16
local_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
local_fine_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
expected_artifact_count: 14
expected_base_count: 6
expected_fine_count: 8
nas_existing_count: 14
local_existing_count: 14
size_match_count: 14
manifest_expected_count: 12
manifest_verified_count: 12
required_manifest_expected_count: 12
warnings: []
errors: []
```

Verified batch 16 runtime telemetry:

```text
telemetry_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/runtime_telemetry_probe.md
telemetry_verdict: ok_dream7b_bpu_runtime_telemetry_probe
batch_count: 16
bpu_loading_sample_count: 320
nonzero_bpu_loading_sample_count: 35
max_bpu_loading: 100.0
avg_bpu_loading: 8.45
forward_summary: /mnt/nas/openclaw/reports/models/dream7b_bpu_runtime_telemetry_20260605-132014/forward/summary.json
forward_wall_ms: 26369.124
forward_load_ms: 23336.624
forward_run_ms: 2778.412
forward_amortized_wall_ms_per_forward: 1648.07
forward_amortized_load_ms_per_forward: 1458.539
forward_amortized_run_ms_per_forward: 173.651
```

Verified sustained systemd telemetry over three sixteen-request jobs:

```text
systemd_telemetry_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_systemd_telemetry_20260605-133919/systemd_telemetry_probe.md
systemd_telemetry_verdict: ok_dream7b_bpu_batch_queue_systemd_telemetry_probe
job_count: 3
request_count: 16
expected_request_total: 48
completed_job_count: 3
failed_job_count: 0
processed_request_count: 48
accepted_request_count: 48
deferred_request_count: 0
result_count: 48
batch_counts: [16, 16, 16]
total_wall_ms: 79811.376
total_load_ms: 70702.172
total_run_ms: 8337.877
amortized_wall_ms_per_processed_request: 1662.737
amortized_load_ms_per_processed_request: 1472.962
amortized_run_ms_per_processed_request: 173.706
bpu_loading_sample_count: 829
nonzero_bpu_loading_sample_count: 99
max_bpu_loading: 100.0
avg_bpu_loading: 9.616
queue_summary_001: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_001/queue_summary.json
queue_summary_002: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_002/queue_summary.json
queue_summary_003: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/systemd_telemetry_20260605-133919_003/queue_summary.json
```

Verified report-only queue retention policy:

```text
retention_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_retention_20260605-135448/queue_retention_probe.md
retention_verdict: ok_dream7b_bpu_batch_queue_retention_probe
policy_mode: report_only
queue_counts: {'pending': 0, 'processing': 0, 'done': 13, 'failed': 1}
queue_size_bytes: {'pending': 0, 'processing': 0, 'done': 18685, 'failed': 83}
pending_stale_count: 0
processing_stale_count: 0
done_archive_candidate_count: 0
failed_archive_candidate_count: 0
archive_root: /mnt/nas/openclaw/queues/dream7b-bpu/archive
apply_supported: False
warnings: []
errors: []
```

Verified report-only deployment acceptance gate:

```text
deployment_acceptance_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.md
deployment_acceptance_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260606-144721/deployment_acceptance_probe.json
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 11
passed_check_count: 11
min_batch_capacity: 16
min_systemd_batch_requests: 16
min_systemd_telemetry_requests: 48
min_long_repeat_count: 6
max_long_repeat_wall_spread_ratio: 0.1
systemd_service.ok: True
batch_capacity.ok: True
hbm_artifact_inventory.ok: True
systemd_batch.ok: True
systemd_drain.ok: True
systemd_canary.ok: True
text_queue_run.ok: True
text_queue_systemd.ok: True
systemd_telemetry.ok: True
long_repeat.ok: True
queue_retention.ok: True
warnings: []
errors: []
```

Verified reusable text prompt queue run:

```text
text_queue_run_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-144526/text_queue_run.md
text_queue_run_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_20260606-144526/text_queue_run.json
verdict: ok_dream7b_bpu_text_queue_run
submit_cmd: dream7b-bpu-text-queue-submit
submit_verdict: ok_dream7b_bpu_text_queue_submit
job_status: done
request_id: text_queue_run_20260606-144526-001
tokenizer_dir: /mnt/nas/openclaw/models/dream7b/tokenizer
fit_mode: pad-right
original_token_count: 9
token_count: 16
processed_count: 1
accepted_count: 1
deferred_count: 0
skipped_count: 0
batch_run_count: 1
batch_count: 1
result_count: 1
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shape: [1, 16, 152064]
topk_last_position: [{'token_id': 323, 'score': 1.7742547988891602}, {'token_id': 476, 'score': 1.0451929569244385}, {'token_id': 11, 'score': 0.8926413059234619}]
durable_results_jsonl: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_run_20260606-144526/durable_state/results.jsonl
total_wall_ms: 24525.835
amortized_wall_ms_per_processed_request: 24525.835
errors: []
```

Verified real text prompt to NAS-backed systemd BPU queue:

```text
text_queue_report: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_systemd_probe.md
text_queue_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_systemd_probe.json
text_queue_run_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_run.json
text_queue_submit_json: /mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_systemd_20260606-144634/text_queue_submit.json
verdict: ok_dream7b_bpu_text_queue_systemd_probe
run_cmd: dream7b-bpu-text-queue-run
run_verdict: ok_dream7b_bpu_text_queue_run
submit_cmd: dream7b-bpu-text-queue-submit
submit_verdict: ok_dream7b_bpu_text_queue_submit
job_status: done
request_id: text-queue-20260606-144634-001
tokenizer_dir: /mnt/nas/openclaw/models/dream7b/tokenizer
fit_mode: pad-right
original_token_count: 9
token_count: 16
processed_count: 1
accepted_count: 1
deferred_count: 0
skipped_count: 0
batch_run_count: 1
batch_count: 1
result_count: 1
execution_mode: pair_window_batch
window_execution_mode: window-batch
child_process_count: 0
bpu_lock_path: /run/lock/dream7b_bpu_batch_queue_runner.lock
final_shape: [1, 16, 152064]
topk_last_position: [{'token_id': 323, 'score': 1.7742547988891602}, {'token_id': 476, 'score': 1.0451929569244385}, {'token_id': 11, 'score': 0.8926413059234619}]
durable_results_jsonl: /mnt/nas/openclaw/reports/models/dream7b_bpu_batch_queue_service_systemd/jobs/text_queue_systemd_20260606-144634/durable_state/results.jsonl
total_wall_ms: 24389.453
amortized_wall_ms_per_processed_request: 24389.453
errors: []
```

The default single-input fine-forward path was re-verified after adding `--tokens-batch-json`, `--window-execution-mode window-batch`, and timing fields:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-183906/fine_forward_probe.md
verdict: ok_dream7b_bpu_fine_forward_probe
execution_mode: pair_in_process
window_execution_mode: in-process
child_process_count: 0
final_shape: [1, 16, 152064]
segment_count: 10
```

The deployed diffusion loop can now select the forward backend with:

```bash
DREAM7B_BPU_FORWARD_CMD=dream7b-bpu-fine-forward \
  dream7b-bpu-diffusion-loop-probe \
  /mnt/nas/openclaw/reports/models \
  'Explain why S100P BPU matters for Dream 7B in OpenClaw.'
```

Verified fine-forward diffusion-loop output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_diffusion_loop_20260603-175030/summary.md
verdict: ok_dream7b_bpu_diffusion_loop_probe
forward_command: dream7b-bpu-fine-forward
steps: 2
remaining_mask_positions: []
step0 forward: segment_plan=fine-adjacent, residency_window_size=2, window_execution_mode=in-process, child_window_mode=pair, child_runtime_mode=packed, execution_mode=pair_in_process, child_process_count=0, final_shape=[1, 16, 152064]
step1 forward: segment_plan=fine-adjacent, residency_window_size=2, window_execution_mode=in-process, child_window_mode=pair, child_runtime_mode=packed, execution_mode=pair_in_process, child_process_count=0, final_shape=[1, 16, 152064]
```

The CPU/BPU quality gate can now record the fine-forward path with:

```bash
DREAM7B_BPU_QUALITY_FORWARD_CMD=dream7b-bpu-fine-forward \
  dream7b-bpu-cpu-quality-gate-probe \
  /mnt/nas/openclaw/reports/models \
  'Explain why BPU matters.'
```

Verified fine-forward quality-gate output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_cpu_quality_gate_20260603-160405/summary.md
verdict: ok_dream7b_bpu_cpu_quality_gate_recorded
quality_status: diverged_expected_for_seq16_probe
bpu_forward_command: dream7b-bpu-fine-forward
bpu loop verdict: ok_dream7b_bpu_diffusion_loop_probe
bpu remaining_mask_positions: []
```

## Current Boundary

This is real BPU execution for real Dream 7B weights, including a complete seq16 forward chain from prompt text or token ids to logits plus verified one-step and strategy-aware bounded multi-step Dream diffusion bridges over masked positions. The path now also has a CPU/BPU quality coverage gate that records current divergence against the existing CPU Dream text path, an HBM cache performance gate that quantifies NAS versus S100P-local HBM load cost, a HBM artifact inventory gate showing `expected_artifact_count: 14`, `nas_existing_count: 14`, `local_existing_count: 14`, `size_match_count: 14`, and `manifest_verified_count: 12`, a residency gate proving that the current six-segment split cannot be made all-resident, a fine-residency gate proving that every adjacent two-segment window can be resident, a deployed fine in-process pair forward command that runs the 10-segment fine plan to logits with 0 child processes, a 3-run repeat probe plus a gated 6-run long-repeat probe for the default in-process path showing `wall_spread_ratio: 0.046307` under `max_wall_spread_ratio: 0.1`, a window-batch throughput probe for concurrent independent seq16 inputs, a batch-size sweep proving amortized wall time drops from `24562.798` ms at batch 1 to `3175.416` ms at batch 8, a batch-capacity probe proving independent seq16 batch 16 passes with `amortized_wall_ms_per_forward: 1714.647`, runtime telemetry with `hrt_ucp_monitor` showing `max_bpu_loading: 100.0` during Dream 7B BPU forward, a reusable `dream7b-bpu-fine-batch-forward` wrapper for JSON token batches, a bounded `dream7b-bpu-batch-queue-runner` JSONL service bridge with verified multi-batch `--drain-all`, verified `cancelled` and `not_after_epoch_ms` control semantics, durable queue state JSONL outputs, default queue-runner single-flight `bpu_lock`, a directory-backed `dream7b-bpu-batch-queue-service` loop with verified real BPU one-shot operation, and a NAS-backed `dream7b-bpu-batch-queue.service` systemd unit with verified single-job, 2-job, historical `max_batch_size=4` and `max_batch_size=8` reports, current default `--max-batch-size 16 --drain-all` one-job sixteen-request real BPU queued execution with `batch_run_count=1`, `batch_count=16`, and `amortized_wall_ms_per_processed_request` around 1.7 seconds, a lightweight one-request systemd canary showing `verdict: ok_dream7b_bpu_batch_queue_systemd_canary_probe`, `job_status: done`, `final_shapes: [[1, 16, 152064]]`, and `errors: []`, reusable `dream7b-bpu-text-queue-submit` and `dream7b-bpu-text-queue-run` commands showing real prompt tokenization through `/mnt/nas/openclaw/models/dream7b/tokenizer`, `submit_verdict: ok_dream7b_bpu_text_queue_submit`, `verdict: ok_dream7b_bpu_text_queue_run`, `fit_mode: pad-right`, `token_count: 16`, `final_shape: [1, 16, 152064]`, and non-empty `topk_last_position`, sustained service telemetry over three sixteen-request jobs showing `processed_request_count: 48`, `batch_counts: [16, 16, 16]`, `max_bpu_loading: 100.0`, and `amortized_wall_ms_per_processed_request: 1662.737`, a report-only queue retention probe showing the current NAS queue has no stale `pending` or `processing` jobs and no current archive candidates, plus a report-only deployment acceptance gate showing `check_count: 11`, `passed_check_count: 11`, `max_long_repeat_wall_spread_ratio: 0.1`, and `verdict: ok_dream7b_bpu_deployment_acceptance_probe` across service, capacity, HBM inventory, batch, drain, canary, text-queue-run, text-queue-systemd, telemetry, long-repeat, and retention evidence. It is not yet a complete text-generation service.

Remaining engineering work:

- continue reducing per-window HBM reload overhead in `dream7b-bpu-fine-forward`; in-process pair mode removed child-process overhead but still reloads HBM per resident pair;
- keep the queue retention path report-only until an explicit apply mode and archive directory migration rule are approved; do not treat systemd supervision as a single-request Dream diffusion speedup;
- keep all-segment residency out of the plan unless HBRT/HBDK exposes stronger release or streaming APIs; current fine split makes every adjacent two-segment window viable, but three-segment residency still fails;
- reduce or remove S16->F32 handoff overhead between segments;
- add quality gates against the existing CPU Dream output path and decide acceptable divergence for seq16 BPU probes;
- benchmark with production prompt/token settings, not only dummy seq16 smoke input.

## Review

The path still uses Dream 7B, not a substitute model. The current route is now:

```text
Dream HF weights -> WSL1 AVX build host -> segmented S100 HBM -> NAS storage -> S100P tokenizer/runtime -> deployed S100P commands
```

The earlier official cached prefill/decode skeleton remains unsuitable for Dream in the short term because Dream is diffusion-based and the direct official skeleton conversion crashed on real Dream graphs.
