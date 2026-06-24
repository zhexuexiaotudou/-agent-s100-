# Dream7B Seq128 Cloud Compile Closure 2026-06-23

## Decision

The 512 GiB x86_64 cloud compile window produced a complete `seq128, B=1`
Dream7B HBM package for S100 `nash-e`, but this does not reopen Dream7B as the
project model path.

Current decision:

- Keep the `seq128` result as a preserved research artifact.
- Do not compile `seq256`.
- Do not rent more cloud compile capacity for Dream7B until the project
  explicitly reopens this route.
- Do not promote the artifact to OpenClaw foreground chat. It has not been
  loaded, run, or quality-validated on S100P.

This run answers the compile-feasibility question only: `seq128` can be compiled
with the current segmented Dream7B skeleton after targeted compiler-script
repairs. It does not answer runtime latency, HBM residency, logits quality,
Chinese generation quality, or product suitability.

## Preserved Artifacts

Local preserved package:

```text
F:\Project\Digua\tmp\cloud_seq128_results\dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar
F:\Project\Digua\tmp\cloud_seq128_results\dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar.sha256
F:\Project\Digua\tmp\cloud_seq128_results\seq128_b1_lmheadq16_lasttoken_summary.json
F:\Project\Digua\tmp\cloud_seq128_results\seq128_b1_lmheadq16_lasttoken_hbm_manifest.tsv
```

Integrity:

```text
sha256 c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1
tar_bytes 8567367680
```

The SHA256 was verified locally after download. The 8 GiB tar package is kept
under `tmp/` and must not be committed to the repo. The repo records its path,
size, and hash only.

Cloud artifact source before shutdown:

```text
/data/dream7b-cloud/artifacts/dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar
/data/dream7b-cloud/artifacts/dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar.sha256
/data/dream7b-cloud/artifacts/seq128_b1_lmheadq16_lasttoken_summary.json
/data/dream7b-cloud/artifacts/seq128_b1_lmheadq16_lasttoken_hbm_manifest.tsv
```

Cloud VM status at shutdown decision: no active Dream compile, HBDK, tar,
sha256, or transfer process remained.

## Artifact Summary

Compile shape:

```text
model Dream7B
target S100 nash-e
seq_len 128
batch_size 1
w_bits 8
final_segment 27:28 lm_head_w_bits=16 final_logits_mode=last-token
segment_count 28
hbm_count 28
hbo_count 28
missing_or_bad []
```

Size summary:

| Group | Size |
| --- | ---: |
| Total HBM bytes | 8,567,319,904 |
| Total HBM GiB | 7.979 |
| HBM-only tar bytes | 8,567,367,680 |
| Embedding segment `0:1` | 0.728 GiB |
| Hidden segments `1:27` total | 5.500 GiB |
| Final segment `27:28` | 1.751 GiB |

The final segment is the largest HBM file because it carries the q16 lm_head
last-token logits path.

## Gate Results

Completed gates:

| Gate | Result |
| --- | --- |
| Host/input check | pass |
| `hbdk4` / `leap_llm` import | pass |
| State-dict preflight `seq16`, `seq128`, `seq256` | pass |
| `seq128` final segment `27:28` | pass after q16 compiler hotfix |
| `seq128` hidden segment `5:6` | pass |
| `seq128` embedding segment `0:1` | pass |
| Full `seq128, B=1` segmented compile | pass, 28/28 HBM |
| Local package download and SHA256 verification | pass |

The first final-segment compile failed because `leap_llm.nn.modules.linear`
did not handle `FakeQuantLinear` with `w_bits=16`. The cloud venv was hotfixed
to add the q16 branch. This was a cloud SDK-site-package repair, not a repo
source change.

## Repo Script Changes That Matter

The cloud compile flow depends on these repo-side script repairs:

- `scripts/probes/compile_dream_true_batch_segments.sh`
  - accepts `FINAL_LOGITS_MODE`;
  - passes `--final-logits-mode`;
  - names `BATCH_SIZE=1` artifacts without `_b1`, matching the compiler output;
  - supports `SKIP_PIP_INSTALL=1` for parallel segment workers.
- `scripts/probes/dream7b_cloud_gate_runner.sh`
  - runs `compile-seq128-last` with `FINAL_LOGITS_MODE=last-token`.
- `scripts/probes/dream7b_cloud_parallel_segments.sh`
  - parallelizes independent one-layer segment compiles after sentinel gates
    pass.

These scripts are useful as a record of the working compile path. They are not
a product deployment route by themselves.

## Interpretation

The earlier `seq16` problem was real: a 16-token fixed BPU window forces normal
chat prompts into prompt-tail truncation and leaves only a tiny mask window for
answers. The `seq128` compile proves that a longer fixed-window HBM package can
be built on a large x86_64 compile host.

However, this does not prove Dream7B is usable for the project:

- `seq128` has not been loaded on S100P.
- No S100P runtime chain has consumed these 28 HBM files.
- No BF16/CPU reference comparison was rerun against the `seq128` artifacts.
- No Chinese or generic chat quality gate has passed.
- No OpenClaw route points to this package.

So the correct conclusion is narrower than "Dream is fixed": the compile
blocker was reduced, but the deployment and product-quality blockers remain.

## Stop Boundary

Dream compile work is paused here.

Do not spend more cloud compile time on:

- `seq256`;
- alternative batch sizes for long-seq Dream;
- repeated full `seq128` builds;
- foreground OpenClaw promotion work based only on this compile result.

If the Dream route is ever reopened, the next step should be board-side use of
the existing package, not another cloud compile:

1. copy the verified tar to NAS/S100P;
2. extract into an isolated directory, not over the seq16 baseline;
3. run single-segment load checks for `0:1`, `5:6`, and `27:28`;
4. only then consider a full segmented runtime and quality gate.

Until then, the project should continue treating Dream7B as historical
engineering evidence and carry the reusable S100P/NAS/OpenClaw/probe toolchain
forward to the current AI-NAS direction.
