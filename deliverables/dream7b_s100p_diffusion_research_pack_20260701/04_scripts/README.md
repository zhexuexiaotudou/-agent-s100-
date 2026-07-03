# Probe Script Index

This directory contains report-producing probes and gates. Most scripts write
Markdown/JSON evidence packets and should be treated as reusable validation
patterns, even where the filename still contains `dream7b`.

## Families

| Family | Approx. Count | Role |
| --- | ---: | --- |
| `ai_nas_*` | 152 | Product/tool validation independent of Dream7B |
| `dream7b_b4_*` | 40 | B=4 true-batch/runtime analysis and admission gates |
| `dream7b_bpu_quality_*` | 16 | BPU quality, rollback, and promotion gates |
| `dream7b_true_batch_*` | 12 | true-batch compile/runtime/telemetry probes |
| `dream7b_cloud_*` | 5 | temporary x86_64 cloud compile bootstrap, gates, monitor, and parallel segment driver |
| other `dream7b_*` | 26 | gateway, fast response, product packet, and service gates |
| other | 9 | lower-level S100P/NAS/Dream helpers |

## What To Reuse

- Use `ai_nas_*` probes as the base for future product evidence.
- Use `dream7b_*_packet.py`, `*_gate.py`, and `*_audit.py` naming patterns for
  future model gates.
- Keep JSON plus Markdown output for every important decision packet.
- Keep explicit verdict fields and blocked reasons.
- Keep service and rollback checks separate from model-quality checks.
- Use `ai_nas_product_closure_gate_probe.py` as the current strict gate for the
  official Qwen2.5 plus S100 vision AI-NAS Copilot route.
- Use `ai_nas_official_ppocr_wrapper_probe.py` to prove the official S100
  PP-OCRv3 sample can run through a temporary wrapper and produce real
  prediction lines plus an annotated result image.
- Treat `dream7b_cloud_*` scripts as a historical compile workflow for the
  verified 2026-06-23 `seq128, B=1` package, not as an active prompt to rent
  more cloud time.
- Use `dream7b_s100p_diffusion_research_packet.py`,
  `dream7b_seq128_s100p_runtime_gate.py`, and
  `dream7b_seq128_logits_reference_compare.py` for the layered seq128
  S100P diffusion research path: compile evidence, board load/run evidence,
  then logits numerical evidence before any generation or product route work.

## What Not To Reuse Blindly

- Dream7B-specific ports, model aliases, paths, and HBM assumptions.
- seq16 BPU prompt-window assumptions.
- B=4/B=16 runtime conclusions unless a new model repeats equivalent tests.
- Any promotion threshold without revalidating the new workload and baseline.

## Housekeeping

Python bytecode under `__pycache__/` is cache and should not be treated as
source. Generated reports belong under `tmp/` or NAS-backed report roots, not in
this directory.
