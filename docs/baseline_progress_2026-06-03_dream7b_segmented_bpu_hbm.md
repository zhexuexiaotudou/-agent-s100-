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

## Current Boundary

This is real BPU execution for real Dream 7B weights, including a complete seq16 forward chain from prompt text or token ids to logits. The Python prototype uses `HB_HBMRuntime`, dequantizes each S16 segment output back to F32, and explicitly releases each HBM before loading the next one to stay inside S100P BPU/ION memory limits. It is not yet a complete text-generation service.

Remaining engineering work:

- turn the verified Python forward prototype into the production host-side segment orchestrator;
- reduce or remove S16->F32 dump handoff overhead between segments;
- connect Dream diffusion sampling to the segmented BPU forward path;
- add quality checks against the existing CPU Dream output path;
- benchmark with production prompt/token settings, not only dummy seq16 smoke input.

## Review

The path still uses Dream 7B, not a substitute model. The current route is now:

```text
Dream HF weights -> WSL1 AVX build host -> segmented S100 HBM -> NAS storage -> S100P tokenizer/runtime -> deployed S100P commands
```

The earlier official cached prefill/decode skeleton remains unsuitable for Dream in the short term because Dream is diffusion-based and the direct official skeleton conversion crashed on real Dream graphs.
