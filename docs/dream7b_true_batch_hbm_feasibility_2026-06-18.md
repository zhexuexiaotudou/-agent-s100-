# Dream7B True Batch HBM Feasibility

Date: 2026-06-18

## Decision

True batch-dimension HBM is feasible as a research experiment. Static batch-2 and batch-4 seq16 HBM artifact sets were compiled and verified, but neither currently beats the production queue-batch path.

The production service should stay on the existing raw-final segment-major queue path. `request_count=256` remains queue-level batching, not a true HBM batch dimension.

## Current B=4 Status Snapshot

As of 2026-06-19 11:28 CST, the B=4 true-batch HBM set is complete and
runtime-valid, but it is still not a production replacement:

```text
B=4 NAS root: /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4
verified segment count: 28/28
verified segment range: seg00_01 through seg27_28
latest runtime telemetry: segment-major, 1536 microbatches, 6144 requests
failed_job_count: 0
final_shape: [4, 16, 152064]
avg_bpu_loading: 76.789
avg_nonzero_bpu_loading: 89.776
amortized_wall_ms_per_request: 72.249
```

Detailed compile/runtime breakdown is in
`docs/dream7b_true_batch_b4_segment_analysis_2026-06-19.md`. The current
bottleneck evidence is that `seg27_28` remains the runtime outlier
(`20.273ms` average per B=4 run), about `2.5x` the hidden-block average
(`8.1007ms`), while group load/release accounts for about `14.66%` of the
latest telemetry wall time.

The latest same-size inner-order comparison at 512 microbatches shows that
`segment-major` is only slightly better than `microbatch-major`:

```text
segment-major, 512 microbatches:
  avg_bpu_loading: 59.160
  avg_nonzero_bpu_loading: 89.489
  amortized_wall_ms_per_request: 93.730

microbatch-major, 512 microbatches:
  avg_bpu_loading: 58.790
  avg_nonzero_bpu_loading: 89.087
  amortized_wall_ms_per_request: 94.447
```

This means changing only the group-internal loop order is not enough to reach
the queue-batch BPU loading gate. The more useful runtime work is still
reducing group load/release amortization and isolating the final logits segment
cost.

A same-size group split comparison at 512 microbatches also shows no gain from
smaller groups:

```text
segment-major, groups 0:6,6:12,12:18,18:24,24:28:
  group_count: 5
  avg_bpu_loading: 59.160
  avg_nonzero_bpu_loading: 89.489
  amortized_wall_ms_per_request: 93.730
  group_load_fraction_of_wall: 0.3409

segment-major, groups 0:4,4:8,8:12,12:16,16:20,20:24,24:28:
  group_count: 7
  avg_bpu_loading: 59.037
  avg_nonzero_bpu_loading: 89.348
  amortized_wall_ms_per_request: 93.957
  group_load_fraction_of_wall: 0.3421
```

This confirms that splitting into more groups slightly increases switching
overhead and does not improve BPU loading. For B=4, the current best observed
direction is longer queues with the memory-safe 5-group segment-major schedule,
not finer group partitioning.

A longer 3072-microbatch B=4 segment-major run confirms the amortization trend
continues, but still does not close the BPU loading gap versus queue-batch:

```text
segment-major, 5 groups, 1536 microbatches:
  processed_request_count: 6144
  avg_bpu_loading: 76.789
  avg_nonzero_bpu_loading: 89.776
  amortized_wall_ms_per_request: 72.249
  group_load_fraction_of_wall: 0.1466

segment-major, 5 groups, 3072 microbatches:
  processed_request_count: 12288
  avg_bpu_loading: 82.579
  avg_nonzero_bpu_loading: 89.680
  amortized_wall_ms_per_request: 66.976
  group_load_fraction_of_wall: 0.0798
```

This is the strongest B=4 true-batch runtime point so far. It is a useful
throughput research result, but the BPU loading remains below the existing
queue-batch service baseline (`93.166` average, `95.097` nonzero average).

## What Was Executed

- Added static `--batch-size` support to the custom Dream segment compiler:
  - local source: `F:\Project\Digua\tmp\wsl_compile_dream_full_forward.py`
  - NAS copy: `/mnt/nas/openclaw/scripts/probes/wsl_compile_dream_full_forward.py`
- Added a NAS-first compile driver:
  - local source: `F:\Project\Digua\scripts\probes\compile_dream_true_batch_segments.sh`
  - NAS copy: `/mnt/nas/openclaw/scripts/probes/compile_dream_true_batch_segments.sh`
- Verified local Python syntax with `py -3 -m py_compile`.
- Verified the NAS is writable and has enough capacity:
  - mount: `/mnt/nas/openclaw`
  - free space observed: about `1.9T`
- Created a temporary WSL build distro on F drive:
  - `F:\Project\Digua\tmp\wsl\DiguaTrueBatchBuilder`
  - arch verified as `x86_64`
- Converted the temporary WSL distro to WSL2 after WSL1 networking blocked `apt`.
- Installed the x86_64 compiler dependencies and SDK venv in WSL2:
  - venv: `/opt/digua/dream-true-batch-venv`
  - compiler import check: `hbdk4.compiler` and `leap_llm` OK
- Copied Dream HF inputs from NAS to a bounded local staging cache:
  - `F:\Project\Digua\tmp\true_batch_inputs\dream7b-hf`
- Compiled and linked two true-batch batch-2 segment prototypes:
  - `seg00_01`: token input path
  - `seg01_02`: hidden-state input path

## Produced Artifacts

NAS output root:

```text
/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2
```

Verified segments:

```text
seg00_01 total: 5.9G
seg01_02 total: 1.8G
combined total: 7.6G
```

Progress update at 2026-06-19 01:05 CST:

```text
verified segment count: 28
verified segment range: seg00_01 through seg27_28
NAS total size: about 56G
full remote manifest verification: all 28 OK
local segment staging: cleaned after each verified upload
F: free space: remained about 517G during the run
```

Additional verified segments compiled through the Windows-to-WSL-to-NAS
orchestrator:

```text
seg02_03
seg03_04
seg04_05
seg05_06
seg06_07
seg07_08
seg08_09
seg09_10
seg10_11
seg11_12
seg12_13
seg13_14
seg14_15
seg15_16
seg16_17
seg17_18
seg18_19
seg19_20
seg20_21
seg21_22
seg22_23
seg23_24
seg24_25
seg25_26
seg26_27
seg27_28
```

`seg27_28` contains the final norm/lm_head path and took longer than the
ordinary block-only segments. The parent PowerShell invocation was interrupted
after the `.hbm` link had started, but the WSL link process continued to
completion. The final segment was then completed manually by generating
`manifest.sha256`, running local `sha256sum -c`, uploading to NAS, and running
remote `sha256sum -c`.

Each segment contains:

```text
*.bc
*_convert.bc
*_convert_removed.bc
*.hbo
*.hbm
manifest.sha256
```

Remote verification:

```text
/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2/seg00_01/manifest.sha256: all OK
/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2/seg01_02/manifest.sha256: all OK
```

Shape evidence from compile logs:

```text
seg00_01:
func @dream_batch_segment_00_01_b2(
  tensor<2x16xsi32> _input_0,
  tensor<2x16xsi32> _input_1
) -> tensor<2x16x3584xf32> _output_0

seg01_02:
func @dream_batch_segment_01_02_b2(
  tensor<2x16x3584xf32> _input_0,
  tensor<2x16xsi32> _input_1
) -> tensor<2x16x3584xf32> _output_0
```

## Output Policy

The compile driver writes generated artifacts and logs to NAS by default:

```bash
OUTPUT_ROOT=/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b${BATCH_SIZE}
REPORT_ROOT=/mnt/nas/openclaw/reports/models/dream7b_true_batch_compile_<timestamp>
```

It also stops a batch after `STOP_AFTER_GB`, default `100`, so long runs can be split without filling a local disk.

For the current Windows + WSL2 topology, use the PowerShell orchestrator:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  F:\Project\Digua\scripts\probes\Compile-DreamTrueBatchSegments.ps1 `
  -Segments '13:14,14:15,15:16,16:17' `
  -BatchSize 2 `
  -SeqLen 16 `
  -StopAfterGB 100
```

This orchestrator compiles one segment in WSL2 local staging, links `.hbo` to
`.hbm`, writes `manifest.sha256`, uploads the segment directory to NAS through
Windows `scp.exe`, verifies `sha256sum -c` on S100P/NAS, then removes only the
verified local segment staging directory.

## Current Constraint

The current Windows host now has a usable temporary WSL2 compile environment, but WSL2 cannot directly reach the S100P/NAS link-local network. Compilation therefore uses local F-drive staging and then copies artifacts to NAS through the Windows-to-S100P SSH path.

Details:

- S100P is `aarch64`, so it cannot run the x86_64 `hbdk4_compiler` wheel natively.
- WSL1 networking timed out on `apt-get update`; WSL2 networking works.
- WSL2 cannot SSH to `192.168.127.10` and cannot mount `169.254.143.37:/OpenClawWorkspace`, while Windows can SSH to S100P.
- Local staging currently uses about `15G` for Dream HF inputs and `7.6G` for the first true-batch artifacts.

## Minimal NAS-First Compile Command

Run this on an x86_64 Linux host that can see `/mnt/nas/openclaw` and has Python 3.10:

```bash
chmod +x /mnt/nas/openclaw/scripts/probes/compile_dream_true_batch_segments.sh

BATCH_SIZE=2 \
SEQ_LEN=16 \
SEGMENTS="0:1 1:2" \
STOP_AFTER_GB=100 \
/mnt/nas/openclaw/scripts/probes/compile_dream_true_batch_segments.sh
```

If this passes, expand gradually:

```bash
BATCH_SIZE=2 SEGMENTS="0:1 1:2 2:3 3:4" STOP_AFTER_GB=100 \
/mnt/nas/openclaw/scripts/probes/compile_dream_true_batch_segments.sh
```

Only after batch 2 passes linking/runtime shape checks should batch 4 or larger be attempted.

## Validation Gate

Do not replace or modify the current default Dream7B service until all of these pass:

- HBM link succeeds for at least one true-batch segment.
- Runtime reports input shapes such as `[2, 16]` or `[2, 16, 3584]`, not `[1, 16]` or `[16, 3584]`.
- A direct segment-chain probe validates output shape and quantization metadata.
- BPU telemetry shows improved sustained average, not only a larger instantaneous sample.
- `failed_jobs=0` remains true on a separate candidate service.

## Runtime Validation Update

Runtime chain validation was executed on S100P with:

```text
/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_runtime_chain_probe.py
```

Report:

```text
/mnt/nas/openclaw/reports/models/dream7b_true_batch_runtime_chain_20260619-011043_b2/true_batch_runtime_chain.json
```

Result:

```text
verdict: ok_dream7b_true_batch_runtime_chain
segment_count_executed: 28
final_shape: [2, 16, 152064]
total_load_ms: 68263.836
total_run_ms: 226.946
wall_ms: 94231.458
```

This proves that the batch-2 HBM artifacts are executable through S100P
`runtime.run`, with true batch shapes preserved through the chain:

```text
seg00_01 input:  [2, 16], [2, 16]
seg00_01 output: [2, 16, 3584]
seg01_02..seg26_27 input:  [2, 16, 3584], [2, 16]
seg01_02..seg26_27 output: [2, 16, 3584]
seg27_28 output: [2, 16, 152064]
```

Telemetry was collected with:

```text
/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_runtime_telemetry_probe.sh
```

Report:

```text
/mnt/nas/openclaw/reports/models/dream7b_true_batch_runtime_telemetry_20260619-011735_b2/true_batch_runtime_telemetry.json
```

Telemetry comparison report:

```text
/mnt/nas/openclaw/reports/models/dream7b_true_batch_telemetry_compare_20260619-012049/true_batch_telemetry_compare.json
```

Current comparison:

```text
true-batch avg_bpu_loading: 13.731
true-batch avg_nonzero_bpu_loading: 47.212
true-batch max_bpu_loading: 74.0

queue-batch baseline avg_bpu_loading: 93.166
queue-batch baseline avg_nonzero_bpu_loading: 95.097
queue-batch baseline max_bpu_loading: 100.0

comparison verdict: true_batch_runtime_ok_but_telemetry_not_better
telemetry_improved: false
```

Therefore, the true-batch research prototype has passed artifact and runtime
shape validation, but it has not passed the production candidate telemetry gate.
The current default queue-batch service must remain unchanged.

## Group-Major Runtime Update

The naive true-batch runtime probe loads and releases each HBM segment for each
chain. To separate load overhead from BPU execution, two additional probes were
added:

```text
/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_load_once_telemetry_probe.py
/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py
```

Full load-once of all 28 true-batch segments is not feasible on the current
S100P memory budget. Loading `seg00_01` through `seg05_06` succeeds, but loading
`seg06_07` fails with:

```text
HBRT4_STATUS_RESOURCE_EXHAUSTED
Cannot malloc bpu memory with length 226066176 bytes
ION_ALLOCATOR: Cannot allocate memory
```

This indicates a BPU memory capacity limit for holding all 28 true-batch HBM
runtimes at once.

Group-major execution was then tested with groups:

```text
0:6, 6:12, 12:18, 18:24, 24:28
```

Results:

```text
64 microbatches, B=2:
  processed_request_count: 128
  final_shape: [2, 16, 152064]
  avg_bpu_loading: 16.207
  avg_nonzero_bpu_loading: 87.046
  max_bpu_loading: 96.0
  amortized_wall_ms_per_request: 639.975

256 microbatches, B=2:
  processed_request_count: 512
  final_shape: [2, 16, 152064]
  avg_bpu_loading: 41.267
  avg_nonzero_bpu_loading: 89.377
  max_bpu_loading: 96.0
  amortized_wall_ms_per_request: 251.486

1024 microbatches, B=2:
  processed_request_count: 2048
  final_shape: [2, 16, 152064]
  avg_bpu_loading: 69.553
  avg_nonzero_bpu_loading: 89.851
  max_bpu_loading: 98.0
  amortized_wall_ms_per_request: 148.849
```

Queue-batch baseline remains stronger:

```text
queue-batch baseline avg_bpu_loading: 93.166
queue-batch baseline avg_nonzero_bpu_loading: 95.097
queue-batch baseline max_bpu_loading: 100.0
```

Conclusion: B=2 true-batch group-major execution improves significantly over
the naive per-chain load/run path, but it still does not meet the telemetry gate
for production candidate evaluation. The next useful research step is either
B=4/B=8 true-batch recompilation or a lower-level runtime submission path that
reduces inter-segment and inter-group host gaps.

## Segment-Major Runtime Update

The group-major probe was extended with an alternate inner loop:

```text
/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py --inner-order segment-major
```

This keeps the same B=2 true-batch HBM artifacts and the same memory-safe groups
(`0:6, 6:12, 12:18, 18:24, 24:28`), but runs each loaded segment across all
microbatches before moving to the next segment. The goal was to reduce host-side
runtime submission gaps inside each group.

Results:

```text
64 microbatches, B=2, segment-major:
  processed_request_count: 128
  failed_job_count: 0
  final_shape: [2, 16, 152064]
  avg_bpu_loading: 15.098
  avg_nonzero_bpu_loading: 87.467
  max_bpu_loading: 98.0
  amortized_wall_ms_per_request: 684.998

256 microbatches, B=2, segment-major:
  processed_request_count: 512
  failed_job_count: 0
  final_shape: [2, 16, 152064]
  avg_bpu_loading: 41.248
  avg_nonzero_bpu_loading: 89.816
  max_bpu_loading: 100.0
  amortized_wall_ms_per_request: 250.712

1024 microbatches, B=2, segment-major:
  processed_request_count: 2048
  failed_job_count: 0
  final_shape: [2, 16, 152064]
  avg_bpu_loading: 69.972
  avg_nonzero_bpu_loading: 90.088
  max_bpu_loading: 100.0
  amortized_wall_ms_per_request: 147.576

4096 microbatches, B=2, segment-major:
  processed_request_count: 8192
  failed_job_count: 0
  final_shape: [2, 16, 152064]
  avg_bpu_loading: 84.271
  avg_nonzero_bpu_loading: 90.202
  max_bpu_loading: 100.0
  amortized_wall_ms_per_request: 122.245
```

The 4096-microbatch run confirms that the B=2 true-batch runtime path is stable
for long queues, but it still does not beat the queue-batch baseline:

```text
segment-major B=2 avg_bpu_loading at 4096 microbatches: 84.271
segment-major B=2 avg_nonzero_bpu_loading at 4096 microbatches: 90.202

queue-batch baseline avg_bpu_loading: 93.166
queue-batch baseline avg_nonzero_bpu_loading: 95.097
```

The 4096-microbatch segment-major breakdown shows that most segments run at
about `7.5ms` per true-batch invocation, while the final logits segment remains
the outlier:

```text
group 0:6:
  load_ms: 17350.062
  segment_total_ms: 191315.442
  avg_segment_run_ms: 7.605

group 6:12:
  load_ms: 12345.477
  segment_total_ms: 189237.521
  avg_segment_run_ms: 7.528

group 12:18:
  load_ms: 12032.410
  segment_total_ms: 189407.272
  avg_segment_run_ms: 7.534

group 18:24:
  load_ms: 12279.858
  segment_total_ms: 189334.442
  avg_segment_run_ms: 7.532

group 24:28:
  load_ms: 12620.471
  segment_total_ms: 175107.865
  avg_segment_run_ms: 10.504
  slowest segment: seg27_28, avg_run_ms: 19.441
```

This points to two separate limits: group load/release cost remains visible even
in long queues, and final full-vocabulary logits generation is still much more
expensive than hidden-to-hidden segments.

Conclusion: changing the group-internal loop order from microbatch-major to
segment-major does not unlock the product telemetry target. At B=2, the
research prototype is valid and stable, but the current production service
must remain on queue-batch. Further gains require either a successful B=4/B=8
true-batch compile in a larger host-memory environment or a lower-level runtime
submission path that reduces inter-segment/inter-group gaps beyond what Python
`runtime.run` sequencing can remove.

## B=4 Compile Probe Update

A B=4 compile probe was started for `seg00_01`/`seg01_02` after the B=2
group-major results, but the host reported insufficient virtual memory and the
PowerShell invocation was interrupted before any B=4 artifact was produced.

Observed state after cleanup:

```text
local B=4 stage: tmp/true_batch_hbm_stage/seg00_01 was empty and removed
NAS B=4 root: /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4 is an empty 4K directory
WSL distro: DiguaTrueBatchBuilder recovered and is stopped
F: free space from WSL df: about 518G
B=2 NAS artifacts: still 28 verified segments
```

This failure is not an HBM/runtime shape failure and not a NAS capacity issue.
It is a host-side compile environment limit, most likely Windows commit/pagefile
pressure during B=4 graph export/compile. One unrelated Windows Anaconda
`tf2` Python process was observed with about 18GB private memory, which likely
reduces available commit headroom.

Additional host/storage snapshot after the interruption:

```text
largest observed unrelated process:
  pid: 160456
  path: F:\Program\Anaconda\envs\tf2\python.exe
  start_time: 2026-06-18 15:49:49
  private_memory: about 18.26GB
  working_set: about 10.58GB

pagefile registry:
  ExistingPageFiles: \??\C:\pagefile.sys
  PagingFiles: ?:\pagefile.sys

WSL df:
  /mnt/f: 954G total, 437G used, 518G available
  /mnt/c: 285G total, 235G used, 51G available

NAS:
  /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2: 56G
  /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4: 4.0K
  /mnt/nas/openclaw: about 1.9T available
```

Exact Windows commit/pagefile usage could not be read from this restricted
session because `Get-CimInstance Win32_OperatingSystem`,
`Get-CimInstance Win32_PageFileUsage`, and `systeminfo` returned access denied.
The available evidence still points to host commit/pagefile pressure rather than
F-drive or NAS storage exhaustion.

Production service guardrail check after true-batch testing:

```text
dream7b-bpu-batch-queue.service: active
dream7b-bpu-batch-queue.service: enabled
description: Dream 7B BPU batch queue service (segment-major load-once 24x256 default)
```

No true-batch candidate service was promoted or enabled.

Do not retry large B=4 compiles until one of these is done:

```text
1. free large unrelated host-memory processes, or
2. increase Windows pagefile / commit limit, or
3. move compilation to a larger x86_64 Linux host with NAS access.
```

## B=4 Compile Preflight Guard

`scripts/probes/Compile-DreamTrueBatchSegments.ps1` now has a preflight guard
for host commit pressure:

```text
-PreflightOnly
-SkipPreflight
-MinCommitHeadroomGB 64
-WarnProcessPrivateGB 12
```

The preflight uses the Windows `GetPerformanceInfo` API instead of WMI/CIM, so
it still works in the restricted session where `Get-CimInstance` and
`systeminfo` were denied. It prints commit usage, commit limit, headroom,
available physical memory, stage/model drive free space, and the largest
private-memory processes. Unless `-SkipPreflight` is explicitly provided, the
script checks this before creating remote output directories or entering WSL
compile.

Current B=4 preflight result:

```text
command:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\probes\Compile-DreamTrueBatchSegments.ps1 -Segments '0:1' -BatchSize 4 -SeqLen 16 -PreflightOnly

preflight_commit_total_gb: 41.37
preflight_commit_limit_gb: 51.13
preflight_commit_headroom_gb: 9.76
preflight_commit_peak_gb: 65.32
preflight_physical_available_gb: 18.41
preflight_stage_free_gb: 517.43
preflight_model_drive_free_gb: 517.43
preflight_min_commit_headroom_gb: 64

largest private-memory process:
  pid: 160456
  process: python
  path: F:\Program\Anaconda\envs\tf2\python.exe
  private_memory: 18.26GB
  working_set: 10.58GB

verdict:
  Insufficient Windows commit headroom for true-batch compile:
  headroom=9.76GB required=64GB
```

This guard converts the previous host-level virtual-memory crash into an early,
non-destructive refusal. B=4 compilation should remain paused until commit
headroom is materially increased.

## B=4 Selective Weight-Load Probe

The B=4 compile path was improved after identifying that
`tmp/wsl_compile_dream_full_forward.py` loaded all safetensor weights before
filtering the requested segment. In segmented mode the compiler now defaults to
selective safetensor loading:

```text
--weight-load-mode auto       # selective for segmented/layer-limited builds
--weight-load-mode selective  # force selective loading
--weight-load-mode full       # compatibility fallback
--state-dict-report-only      # load model state only, no export/compile
```

State-dict-only probes passed for B=4:

```text
seg00_01, B=4:
  tensor_count: 13
  includes: embed_tokens + one remapped layer
  load_state_dict(strict=True): ok

seg06_07, B=4:
  tensor_count: 12
  includes: one remapped hidden layer
  load_state_dict(strict=True): ok

seg27_28, B=4:
  tensor_count: 14
  includes: one remapped layer + norm + lm_head
  load_state_dict(strict=True): ok
```

A controlled B=4 single-segment compile then succeeded for `seg06_07` by
running the generated WSL runner directly after the PowerShell wrapper hit a
transient WSL `E_ACCESSDENIED` service error:

```text
segment: seg06_07
batch_size: 4
input: tensor<4x16x3584xf32>, tensor<4x16xsi32>
output: tensor<4x16x3584xf32>
selective_state_dict_tensor_count: 12
export_module: 10.2265s
convert_mlir: 7.3631s
compile_hbo: 198.4470s
hbm_size: 226174088 bytes
local_segment_size: 1828739447 bytes
manifest: sha256sum -c OK locally and on NAS
```

NAS artifact:

```text
/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4/seg06_07
size: 1.8G
files:
  dream7b_segment_6_7_seq16_b4_q8.bc
  dream7b_segment_6_7_seq16_b4_q8_convert.bc
  dream7b_segment_6_7_seq16_b4_q8_convert_removed.bc
  dream7b_segment_6_7_seq16_b4_q8.hbo
  dream7b_segment_6_7_seq16_b4_q8.hbm
  manifest.sha256
```

S100P single-segment runtime check:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_b4_single_segment_runtime_20260619-030323/b4_single_segment_runtime.json

verdict: ok_b4_single_segment_runtime
model_name: dream_batch_segment_06_07_b4
load_ms: 2668.244
run_ms: 9.406
output_shape: [4, 16, 3584]
```

The WSL-native batch compile helper
`scripts/probes/dream7b_true_batch_compile_segments_wsl.sh` was then added to
avoid the PowerShell wrapper's intermittent internal WSL launch failure. Using
that path, a second B=4 segment also compiled and passed remote validation:

```text
segment: seg07_08
batch_size: 4
input: tensor<4x16x3584xf32>, tensor<4x16xsi32>
output: tensor<4x16x3584xf32>
selective_state_dict_tensor_count: 12
export_module: 9.4937s
convert_mlir: 7.5327s
compile_hbo: 221.4140s
hbm_size: 226201480 bytes
local_segment_size: 1828797754 bytes
manifest: sha256sum -c OK locally and on NAS
S100P runtime.run output_shape: [4, 16, 3584]
S100P runtime.run load_ms: 2675.089
S100P runtime.run run_ms: 9.451
```

Current B=4 NAS state:

```text
/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4: 42G
verified segment count: 22
verified segments:
  seg06_07
  seg07_08
  seg08_09
  seg09_10
  seg10_11
  seg11_12
  seg12_13
  seg13_14
  seg14_15
  seg15_16
  seg16_17
  seg17_18
  seg18_19
  seg19_20
  seg20_21
  seg21_22
  seg22_23
  seg23_24
  seg24_25
  seg25_26
  seg26_27
  seg27_28
```

The next B=4 compile batch then completed four additional hidden segments:

```text
compiled batch:
  seg08_09
  seg09_10
  seg10_11
  seg11_12

local manifest: OK for all four segments
remote NAS manifest: OK for all four segments
local stage after cleanup: 256K
F: free from WSL: 518G
```

Per-segment compile summary:

```text
seg08_09:
  selective_state_dict_tensor_count: 12
  export_module: 9.2320s
  convert_mlir: 7.4085s
  compile_hbo: 216.4264s
  hbm_size: 226200456 bytes
  local_segment_size: 1828797786 bytes

seg09_10:
  selective_state_dict_tensor_count: 12
  export_module: 9.3252s
  convert_mlir: 7.2441s
  compile_hbo: 222.4658s
  hbm_size: 226199176 bytes
  local_segment_size: 1828805567 bytes

seg10_11:
  selective_state_dict_tensor_count: 12
  export_module: 9.1139s
  convert_mlir: 7.3062s
  compile_hbo: 193.8454s
  hbm_size: 226183048 bytes
  local_segment_size: 1828764398 bytes

seg11_12:
  selective_state_dict_tensor_count: 12
  export_module: 9.2181s
  convert_mlir: 7.7035s
  compile_hbo: 206.6972s
  hbm_size: 226174344 bytes
  local_segment_size: 1828733053 bytes
```

S100P runtime spot-check for the newest batch:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_b4_single_segment_runtime_20260619-030323/b4_seg11_12_single_segment_runtime.json

segment: seg11_12
verdict: ok_b4_single_segment_runtime
model_name: dream_batch_segment_11_12_b4
load_ms: 2677.851
run_ms: 9.368
output_shape: [4, 16, 3584]
```

The next B=4 compile batch completed four more hidden segments:

```text
compiled batch:
  seg12_13
  seg13_14
  seg14_15
  seg15_16

local manifest: OK for all four segments
remote NAS manifest: OK for all four segments
local stage after cleanup: 272K
F: free from WSL: 518G
```

Per-segment compile summary:

```text
seg12_13:
  selective_state_dict_tensor_count: 12
  export_module: 9.8790s
  convert_mlir: 7.2275s
  compile_hbo: 202.3340s
  hbm_size: 226189960 bytes
  local_segment_size: 1828793060 bytes

seg13_14:
  selective_state_dict_tensor_count: 12
  export_module: 9.6438s
  convert_mlir: 7.2606s
  compile_hbo: 221.1493s
  hbm_size: 226193032 bytes
  local_segment_size: 1828771928 bytes

seg14_15:
  selective_state_dict_tensor_count: 12
  export_module: 8.7646s
  convert_mlir: 7.0399s
  compile_hbo: 214.4752s
  hbm_size: 226198920 bytes
  local_segment_size: 1828796388 bytes

seg15_16:
  selective_state_dict_tensor_count: 12
  export_module: 9.1729s
  convert_mlir: 7.2672s
  compile_hbo: 221.3937s
  hbm_size: 226191240 bytes
  local_segment_size: 1828766966 bytes
```

S100P runtime spot-check for this batch:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_b4_single_segment_runtime_20260619-030323/b4_seg15_16_single_segment_runtime.json

segment: seg15_16
verdict: ok_b4_single_segment_runtime
model_name: dream_batch_segment_15_16_b4
load_ms: 2683.210
run_ms: 9.508
output_shape: [4, 16, 3584]
```

The next B=4 compile batch completed four more hidden segments:

```text
compiled batch:
  seg16_17
  seg17_18
  seg18_19
  seg19_20

local manifest: OK for all four segments
remote NAS manifest: OK for all four segments
local stage after cleanup: 288K
F: free from WSL: 518G
```

Per-segment compile summary:

```text
seg16_17:
  selective_state_dict_tensor_count: 12
  export_module: 9.6357s
  convert_mlir: 7.3051s
  compile_hbo: 218.7399s
  hbm_size: 226192264 bytes
  local_segment_size: 1828765740 bytes

seg17_18:
  selective_state_dict_tensor_count: 12
  export_module: 9.6267s
  convert_mlir: 7.1401s
  compile_hbo: 218.1068s
  hbm_size: 226193032 bytes
  local_segment_size: 1828773840 bytes

seg18_19:
  selective_state_dict_tensor_count: 12
  export_module: 9.1178s
  convert_mlir: 7.1935s
  compile_hbo: 219.8321s
  hbm_size: 226212232 bytes
  local_segment_size: 1828837738 bytes

seg19_20:
  selective_state_dict_tensor_count: 12
  export_module: 9.6925s
  convert_mlir: 7.1325s
  compile_hbo: 195.8249s
  hbm_size: 226183304 bytes
  local_segment_size: 1828765990 bytes
```

S100P runtime spot-check for this batch:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_b4_single_segment_runtime_20260619-030323/b4_seg19_20_single_segment_runtime.json

segment: seg19_20
verdict: ok_b4_single_segment_runtime
model_name: dream_batch_segment_19_20_b4
load_ms: 2681.637
run_ms: 9.461
output_shape: [4, 16, 3584]
```

The next B=4 compile batch completed four more hidden segments:

```text
compiled batch:
  seg20_21
  seg21_22
  seg22_23
  seg23_24

local manifest: OK for all four segments
remote NAS manifest: OK for all four segments
local stage after cleanup: 304K
F: free from WSL: 518G
```

Per-segment compile summary:

```text
seg20_21:
  selective_state_dict_tensor_count: 12
  export_module: 9.8641s
  convert_mlir: 7.2529s
  compile_hbo: 204.0172s
  hbm_size: 226173320 bytes
  local_segment_size: 1828734983 bytes

seg21_22:
  selective_state_dict_tensor_count: 12
  export_module: 9.5932s
  convert_mlir: 7.1313s
  compile_hbo: 205.8398s
  hbm_size: 226189448 bytes
  local_segment_size: 1828794960 bytes

seg22_23:
  selective_state_dict_tensor_count: 12
  export_module: 9.4158s
  convert_mlir: 7.2280s
  compile_hbo: 206.8958s
  hbm_size: 226188424 bytes
  local_segment_size: 1828793916 bytes

seg23_24:
  selective_state_dict_tensor_count: 12
  export_module: 9.5324s
  convert_mlir: 7.0081s
  compile_hbo: 204.3553s
  hbm_size: 226179720 bytes
  local_segment_size: 1828761328 bytes
```

S100P runtime spot-check for this batch:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_b4_single_segment_runtime_20260619-030323/b4_seg23_24_single_segment_runtime.json

segment: seg23_24
verdict: ok_b4_single_segment_runtime
model_name: dream_batch_segment_23_24_b4
load_ms: 2679.150
run_ms: 9.469
output_shape: [4, 16, 3584]
```

The next B=4 compile batch completed the final four model segments:

```text
compiled batch:
  seg24_25
  seg25_26
  seg26_27
  seg27_28

local manifest: OK for all four segments
remote NAS manifest: OK for all four segments
local stage after cleanup: 320K
F: free from WSL: 518G
```

Per-segment compile summary:

```text
seg24_25:
  selective_state_dict_tensor_count: 12
  export_module: 10.1175s
  convert_mlir: 7.6070s
  compile_hbo: 218.5002s
  hbm_size: 226191752 bytes
  local_segment_size: 1828774061 bytes

seg25_26:
  selective_state_dict_tensor_count: 12
  export_module: 9.6056s
  convert_mlir: 7.2324s
  compile_hbo: 221.1050s
  hbm_size: 226199432 bytes
  local_segment_size: 1828806068 bytes

seg26_27:
  selective_state_dict_tensor_count: 12
  export_module: 10.0758s
  convert_mlir: 7.2340s
  compile_hbo: 218.4231s
  hbm_size: 226206344 bytes
  local_segment_size: 1828827462 bytes

seg27_28:
  selective_state_dict_tensor_count: 14
  export_module: 28.4610s
  convert_mlir: 23.3548s
  compile_hbo: 284.9039s
  hbm_size: 776814568 bytes
  local_segment_size: 6235525219 bytes
  output_signature: tensor<4x16x152064xf32>
```

S100P runtime spot-check for the final segment:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_b4_single_segment_runtime_20260619-030323/b4_seg27_28_final_segment_runtime.json

segment: seg27_28
verdict: ok_b4_final_segment_runtime
model_name: dream_batch_segment_27_28_b4
load_ms: 7360.343
run_ms: 21.450
output_shape: [4, 16, 152064]
```

B=4 completion update at 2026-06-19 06:41 CST:

```text
NAS output root:
  /mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4

verified segment count: 28
verified segment range: seg00_01 through seg27_28
NAS total size: about 56G
remote manifest verification: all 28 OK

last missing segments completed and verified:
  seg03_04
  seg04_05
  seg05_06
```

The final missing compile batch used selective state loading and produced:

```text
seg03_04:
  selective_state_dict_tensor_count: 12
  export_module: 9.1248s
  convert_mlir: 7.2993s
  compile_hbo: 212.9856s
  hbm_size: 226194056 bytes
  local_segment_size: 1828774278 bytes

seg04_05:
  selective_state_dict_tensor_count: 12
  export_module: 9.4581s
  convert_mlir: 7.1398s
  compile_hbo: 218.6603s
  hbm_size: 226201224 bytes
  local_segment_size: 1828802150 bytes

seg05_06:
  selective_state_dict_tensor_count: 12
  export_module: 9.5836s
  convert_mlir: 7.3102s
  compile_hbo: 222.2432s
  hbm_size: 226202504 bytes
  local_segment_size: 1828804872 bytes
```

Additional B=4 hidden-segment runtime spot-check:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_single_segment_runtime_20260619-063657_seg05_b4/true_batch_single_segment_runtime.json

segment: seg05_06
verdict: ok_dream7b_true_batch_single_segment_runtime
model_name: dream_batch_segment_05_06_b4
input_shape: [4, 16, 3584], [4, 16]
output_shape: [4, 16, 3584]
load_ms: 2680.477
run_ms: 9.249
```

B=4 full runtime chain validation:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_runtime_chain_20260619-063711_b4/true_batch_runtime_chain.json

verdict: ok_dream7b_true_batch_runtime_chain
segment_count_executed: 28
final_shape: [4, 16, 152064]
total_load_ms: 65752.126
total_run_ms: 254.454
wall_ms: 66392.761
```

B=4 telemetry comparison:

```text
telemetry report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_runtime_telemetry_20260619-063852_b4/true_batch_runtime_telemetry.json

comparison report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_telemetry_compare_20260619-064106/true_batch_telemetry_compare.json

verdict: true_batch_runtime_ok_but_telemetry_not_better
B=4 avg_bpu_loading: 15.495
B=4 avg_nonzero_bpu_loading: 48.767
B=4 max_bpu_loading: 80.0
queue baseline avg_bpu_loading: 93.166
queue baseline avg_nonzero_bpu_loading: 95.097
queue baseline max_bpu_loading: 100.0
```

Comparable B=4 segment-major long telemetry:

```text
report:
  /mnt/nas/openclaw/reports/models/dream7b_true_batch_group_major_telemetry_20260619-105833_segment_major_mb1536_b4/true_batch_group_major_telemetry.json

verdict: ok_dream7b_true_batch_group_major_telemetry
inner_order: segment-major
microbatch_count: 1536
batch_size: 4
processed_request_count: 6144
failed_job_count: 0
final_shape: [4, 16, 152064]
wall_ms: 443896.647
amortized_wall_ms_per_request: 72.249
avg_bpu_loading: 76.789
avg_nonzero_bpu_loading: 89.776
max_bpu_loading: 100.0
```

The long B=4 segment-major probe shows real throughput potential versus the
queue baseline (`72.249 ms/request` versus `179.62 ms/request`), but sustained
BPU loading is still lower (`76.789` average and `89.776` nonzero average
versus the queue baseline `93.166` and `95.097`). Conclusion: B=4 true
batch-dimension HBM is now a complete, executable research artifact with a
positive throughput signal, but it has not passed the production BPU gate and
is not ready to replace the default service.

Operational note: the PowerShell wrapper can still encounter transient WSL
`E_ACCESSDENIED` errors when it invokes WSL internally. It now retries `exit=-1`
once and treats post-sync local cleanup as best-effort, but direct WSL runner
execution remains the fallback when WSL service access fails inside the wrapper.

The production service remains unchanged.
