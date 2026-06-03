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
fine-forward report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-154303/summary.json
fine-forward probe command: /usr/local/bin/dream7b-bpu-fine-forward-probe
fine-forward probe report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-154831/fine_forward_probe.md
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
scripts/probes/dream7b_bpu_residency_probe.sh
scripts/probes/compile_dream_segments_seq16_fine.sh
scripts/probes/dream7b_bpu_fine_residency_probe.sh
scripts/dream7b-bpu-fine-forward.sh
scripts/probes/dream7b_bpu_fine_forward_probe.sh
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
base_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/segments6
fine_hbm_dir: /home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16
```

Because `HB_HBMRuntime` does not expose an explicit release/close API, the first in-process two-segment attempt failed after the first segment with an ION allocation error while loading `seg04_07`. The working implementation uses a child process per adjacent window: each child loads the current segment plus the next segment, runs the current segment with both resident, writes the dequantized output to `.npy`, and exits so the process boundary releases BPU/ION allocations.

Verified fine sliding-forward output:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_forward_20260603-154303/summary.json
verdict: ok_dream7b_segmented_hbm_python_forward
segment_plan: fine-adjacent
residency_window_size: 2
execution_mode: window_child_process
segments: 10
final_shape: [1, 16, 152064]
top_k: 5
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
report: /mnt/nas/openclaw/reports/models/dream7b_bpu_fine_forward_20260603-154831/fine_forward_probe.md
verdict: ok_dream7b_bpu_fine_forward_probe
segment_plan: fine-adjacent
residency_window_size: 2
execution_mode: window_child_process
final_shape: [1, 16, 152064]
segment_count: 10
```

## Current Boundary

This is real BPU execution for real Dream 7B weights, including a complete seq16 forward chain from prompt text or token ids to logits plus verified one-step and strategy-aware bounded multi-step Dream diffusion bridges over masked positions. The path now also has a CPU/BPU quality coverage gate that records current divergence against the existing CPU Dream text path, an HBM cache performance gate that quantifies NAS versus S100P-local HBM load cost, a residency gate proving that the current six-segment split cannot be made all-resident, a fine-residency gate proving that every adjacent two-segment window can be resident, and a deployed fine sliding-forward command that runs the 10-segment fine plan to logits. It is not yet a complete text-generation service.

Remaining engineering work:

- reduce the child-process and per-window HBM reload overhead in `dream7b-bpu-fine-forward`;
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
