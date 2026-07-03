# Dream7B Seq128 Cloud Compile Execution Plan

Date: 2026-06-23

## Outcome

The first cloud window completed the admitted `seq128, B=1` full segmented
compile and then the Dream compile route was paused.

Result:

- 28/28 HBM files produced for `seq128, B=1, w8`.
- Final segment uses `lm_head_w_bits=16` and `final_logits_mode=last-token`.
- Local verified package:
  `F:\Project\Digua\tmp\cloud_seq128_results\dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar`.
- SHA256:
  `c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1`.
- Closure report:
  `docs/dream7b_seq128_cloud_compile_closure_2026-06-23.md`.

This result proves compile feasibility for the segmented `seq128` package. It
does not prove S100P runtime viability or chat quality, so it is not a promotion
artifact and does not justify compiling `seq256`.

This runbook is for the temporary x86_64 Linux compile host. The goal is to
maximize useful compile throughput while avoiding the previous failure mode:
spending a long run on a shape that later turns out not to answer the chat
quality question.

## Objective

Primary objective: determine whether the Dream7B BPU route deserves a full
`seq128, B=1` compile and validation run.

Secondary objective, only if the gates pass: compile the smallest useful
`seq128` HBM candidates for S100P shape, memory, and logits validation.

`seq256` is not a first-run target. It is only admitted after `seq128` proves
that longer canvas length, q16 repair, and resource curves are all plausible.

## Cloud Host Assumptions

- x86_64 Ubuntu 22.04 or 20.04.
- Python 3.10.
- 512 GiB RAM preferred.
- 2 TiB local NVMe or ESSD data disk mounted at `/data`.
- Root or sudo access.
- GPU is optional for this compile pass.

All compiler work must run under `/data/dream7b-cloud`. Do not write HBDK
intermediates to the system disk.

## Pre-Boot Local Prep

Run locally before the cloud host is started or immediately after the IP is
known:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\probes\dream7b_cloud_make_bundle.ps1
```

This creates a bundle containing the cloud bootstrap script, gate runner,
resource monitor, Dream compile scripts, and the current compiler Python source.

## Boot-Time Sequence

After the cloud instance is reachable:

1. SSH in and confirm the data disk device with `lsblk`.
2. If the 2 TiB disk is blank, run bootstrap with explicit format approval:

```bash
DATA_DISK=/dev/vdb FORMAT_DATA_DISK=1 bash dream7b_cloud_bootstrap.sh
```

If the disk is already mounted at `/data`, run without formatting:

```bash
bash dream7b_cloud_bootstrap.sh
```

3. Upload or download the S100 LLM SDK and Dream7B HF model into:

```text
/data/dream7b-cloud/input/s100_llm_sdk/
/data/dream7b-cloud/input/dream7b-hf/
```

4. Start resource monitoring before any expensive command:

```bash
tmux new -s monitor -d 'INTERVAL_SECONDS=30 bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_resource_monitor.sh /data/dream7b-cloud/reports/resource_monitor'
```

## Gate Policy

Each gate has one of three states:

- `pass`: continue.
- `recoverable`: fix the local problem and rerun the same gate.
- `hard_fail`: save evidence and stop the current Dream-BPU compile route.

Do not treat one compiler crash as a hard fail until the error is classified.
The aim is to make Dream compile if it is realistically possible, not to stop
at the first inconvenience.

## Gate Order

### Gate 0: Host And Input Check

Command:

```bash
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh env
```

Pass:

- `uname -m` is `x86_64`.
- Python 3.10 exists.
- `/data` has at least 1.8 TiB total capacity.
- Dream model files and SDK paths exist.

Recoverable:

- Missing model or SDK files.
- Data disk not mounted but visible and blank.

Hard fail:

- Host is not x86_64.
- RAM or disk is materially below the rented specification.

### Gate 1: HBDK Import

Command:

```bash
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh hbdk-import
```

Pass:

- `hbdk4` and `leap_llm` import in the Python 3.10 venv.

Recoverable:

- Python package dependency mismatch.
- SDK path layout differs from expected.

Hard fail:

- Compiler wheel is incompatible with the host architecture.

### Gate 2: State-Dict Parameterization

Commands:

```bash
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh state-seq16-last
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh state-seq128-last
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh state-seq256-last
```

Pass:

- The compiler script can construct the selected state dict for seq16,
  seq128, and seq256 last-token lm_head q16 sentinel scopes.

Recoverable:

- Script path or model path mismatch.
- Missing optional final-logits flag support.

Hard fail:

- Weight mapping is structurally incompatible with longer sequence scopes.

### Gate 3: Seq128 Single-Segment Compile

Start with the most diagnostic segment:

```bash
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh compile-seq128-last
```

Then only if it passes:

```bash
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh compile-seq128-hidden
bash /data/dream7b-cloud/bundle/scripts/probes/dream7b_cloud_gate_runner.sh compile-seq128-embed
```

Pass:

- HBM is produced.
- No silent CPU fallback is observed in logs.
- Peak RAM and temporary disk curves stay within the host budget.

Recoverable:

- Failure isolated to final logits/lm_head. Try trunk/head split before
  abandoning the route.
- Disk pressure from `.bc` intermediates. Clean completed non-keeper
  intermediates only after hashes and logs are saved.

Hard fail:

- Representative hidden block at L128 cannot compile.
- Compiler inserts unsupported fallback that invalidates S100P runtime value.
- A single segment consumes nearly all 512 GiB RAM or shows non-linear disk
  growth that makes full seq128 implausible.

### Gate 4: Seq128 Full Compile Admission

Full `seq128, B=1` is admitted only when:

- Gate 0-3 pass.
- Resource monitor confirms enough headroom.
- The next target and output path are written into a decision report.
- The existing seq16 baseline is not overwritten or deleted.

## Resource Use Strategy

- Keep all temp files under `/data/dream7b-cloud/tmp`.
- Set `TMPDIR=/data/dream7b-cloud/tmp`.
- Start one HBDK compile at a time until peak RSS is known.
- Parallelize only safe work: download, checksum, compression, log parsing.
- Use `pigz`/`zstd` for packaging logs and non-HBM artifacts.
- Run long commands inside `tmux`.
- Record `/usr/bin/time -v` for every compile command.

## Likely Problems And Responses

### Missing SDK Or Model Files

Response: do not improvise paths. Download or upload into the expected input
directories, then rerun Gate 0.

### Python/HBDK Dependency Conflict

Response: recreate only the venv under `/data/dream7b-cloud/venvs/oellm`.
Do not reinstall the operating system. Preserve `pip freeze` and error logs.

### Data Disk Not Mounted

Response: inspect `lsblk`. Format only an unmounted blank data disk with
explicit `FORMAT_DATA_DISK=1`; never format a mounted or root disk.

### Compiler OOM Or Virtual Memory Failure

Response: classify whether this is a real host limit or accidental concurrency.
Reduce concurrent work to one compile, verify swap status, and retry the same
single segment once. If the same segment still needs near-host-limit memory,
stop before full seq128.

### `.bc` Intermediates Fill Disk

Response: first hash and record artifact sizes. Clean only known rebuildable
intermediates after the report points to the corresponding logs. Keep `.hbm`,
`.hbo`, manifests, and compile logs.

### Lm Head Is The Bottleneck

Response: do not jump to full seq256. Try q16 final norm/lm_head sentinel,
then trunk/head split as a diagnostic path. Continue only if logits repair is
measurable.

### Seq128 Compiles But S100P Load Fails

Response: preserve cloud artifacts and switch to board-side memory/common-buffer
triage. Do not compile seq256 until S100P can load at least one seq128
representative segment.

## Evidence To Preserve

Every run should leave:

- `resource_trace.jsonl`
- `gate_runner.log`
- each gate `*.json`
- each compile `*.stdout.log` and `*.time.log`
- artifact `sha256sum`
- HBM/HBO sizes
- explicit `continue`, `recover`, or `stop` decision

## Final First-Run Decision

At the end of the first cloud window, produce one of:

- `continue_seq128_full`: single-segment compile and resource curves justify a
  full seq128 run.
- `recover_then_retry`: a fixable environment or script issue blocked progress.
- `stop_dream_bpu_compile_route`: evidence shows the current skeleton route is
  not worth further seq128/seq256 spending.

Actual first-run decision:

```text
continue_seq128_full -> completed
then pause_dream_compile_route
```

The route is paused because the useful compile-feasibility question has been
answered, while the remaining risks are board-side runtime and model-quality
risks. Those should not be attacked by more cloud compilation.
