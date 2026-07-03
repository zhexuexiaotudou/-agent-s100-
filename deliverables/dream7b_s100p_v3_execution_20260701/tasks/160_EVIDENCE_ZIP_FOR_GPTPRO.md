# Task 160 — Evidence zip for GPT Pro

## Goal

Create a compact but sufficient v3 evidence package for GPT Pro review.

## Required archive

```text
dream7b_s100p_research_v3_for_gptpro_YYYYMMDD.zip
```

All zip paths must use POSIX `/`, not Windows `\`.

## Required contents

```text
README_FOR_GPT_PRO.md
GPT_PRO_REVIEW_PROMPT.md
01_final_evidence/dream7b_s100p_gate_packet_v3.json
01_final_evidence/dream7b_s100p_gate_packet_v3.md
01_final_evidence/dream7b_s100p_final_technical_report_v3.md
reports/*.json
reports/*.md
tools/*.py
cases/*.jsonl
RAW_EVIDENCE_SUBSET_MANIFEST.json
MANIFEST.json
SHA256SUMS.txt
```

## Required raw evidence subset

Include a small raw subset even if the full raw evidence is too large:

- one BPU full-chain raw final logits `.npy`
- one BPU full-chain dequant final logits `.npy`
- one GGUF last-logits `.npy`
- BPU `seg26` raw output `.npy`
- BPU `seg26` dequant output `.npy`
- isolated `seg27_28` synthetic hidden input `.npy`
- isolated `seg27_28` synthetic output `.npy`
- isolated `seg27_28` real_bpu_seg26_output input `.npy`
- isolated `seg27_28` real_bpu_seg26_output output `.npy`
- representative final segment input sweep variant inputs/outputs

## Manifest

`RAW_EVIDENCE_SUBSET_MANIFEST.json` must contain:

- relative path
- size bytes
- SHA256
- dtype
- shape
- source report
- case id / variant id
- why included

`MANIFEST.json` and `SHA256SUMS.txt` must cover every file in the zip except themselves if explicitly documented.
