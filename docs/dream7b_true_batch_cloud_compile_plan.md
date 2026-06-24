# Dream7B True-Batch Cloud Compile Plan

Date: 2026-06-19

This plan describes a cloud compile workflow. It does not change the production
service and does not promote true-batch as default.

## Goal

First cloud objective:

```text
B=4, seq16, 28 one-layer segments
```

Do not start by compiling B=8 or seq32. Only after B=4 seq16 is complete,
shape-validated, hash-verified, and telemetry-tested should larger batch sizes
or longer sequence lengths be considered.

## Host Selection

Required:

- x86_64 Linux host
- Ubuntu 20.04 or 22.04
- Python 3.10
- at least 128 GB RAM
- preferred 256 GB RAM
- at least 300 GB local SSD/NVMe
- preferred 500 GB local SSD/NVMe

GPU model is secondary for this compiler path. RTX 3090/4090/A10/A40 class
machines are acceptable if they provide enough system RAM and local disk.

## Cloud Bundle Layout

Recommended bundle:

```text
cloud_compile_bundle/
  README.md
  scripts/
    compile_dream_true_batch_segments.sh
    dream7b_true_batch_compile_segments_wsl.sh
    validate_shapes.py
    generate_hashes.sh
    collect_compile_logs.sh
    check_environment.sh
  compiler/
    wsl_compile_dream_full_forward.py
  oellm_build/
    requirements.txt
    hbdk4_compiler-*.whl
    leap_llm-*.whl
  templates/
    manifest.template.json
  models/
    README.md
```

Model inputs should be staged separately under:

```text
models/dream7b-hf/
```

Do not store the model or compiler outputs on the small system disk.

## Environment Check

The environment check should record:

- hostname
- kernel
- CPU model and core count
- total RAM and available RAM
- local disk free space
- Python version
- compiler wheel filenames
- `hbdk4.compiler` import result
- `leap_llm` import result
- model file presence
- source script hash

## Compile Order

Recommended staged order:

1. State-dict-only preflight:
   - `seg00_01`
   - one hidden segment such as `seg05_06`
   - final segment `seg27_28`
2. Compile sentinel segments:
   - `0:1`
   - `5:6`
   - `27:28`
3. Compile capacity groups:
   - `0:6`
   - `24:28`
4. Compile all 28 segments only after sentinel and capacity checks pass.

For the first cloud B=4 pass, use:

```bash
BATCH_SIZE=4
SEQ_LEN=16
W_BITS=8
MARCH=nash-e
```

## Target Artifact Layout

Target root:

```text
/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4
```

Required structure:

```text
true-batch-seq16-b4/
  manifest.json
  shape_report.json
  sha256sums.txt
  validate_shapes.py
  compile_logs/
  seg00_01/
    dream7b_segment_0_1_seq16_b4_q8.bc
    dream7b_segment_0_1_seq16_b4_q8_convert.bc
    dream7b_segment_0_1_seq16_b4_q8_convert_removed.bc
    dream7b_segment_0_1_seq16_b4_q8.hbo
    dream7b_segment_0_1_seq16_b4_q8.hbm
    manifest.sha256
  ...
  seg27_28/
```

## Manifest Fields

`manifest.json` must record:

- model name
- source model path or model hash set
- batch size
- sequence length
- segment count
- expected final output shape `[4, 16, 152064]`
- compiler version
- `leap_llm` version if available
- build host
- build time
- source commit or source bundle hash
- compile command
- artifact hashes
- per-segment HBM size
- per-segment compile status
- per-segment shape signature

## Validation Gates

Artifact gates:

- 28 segments exist.
- Every segment has `.bc`, `_convert.bc`, `_convert_removed.bc`, `.hbo`, `.hbm`, and `manifest.sha256`.
- Root `sha256sums.txt` verifies all artifacts.
- `manifest.json` and `shape_report.json` are complete.

Runtime gates on S100P:

- Single segment `seg00_01` returns `[4, 16, 3584]`.
- Single hidden segment returns `[4, 16, 3584]`.
- Final segment returns `[4, 16, 152064]`.
- Full chain returns `[4, 16, 152064]`.
- Long group-major telemetry reports `failed_job_count=0`.

Promotion gates are separate and stricter; successful cloud compilation alone
does not make true-batch deployable.
