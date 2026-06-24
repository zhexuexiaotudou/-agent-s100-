# Baseline Progress: Dream 7B / Local DLM Readiness

Date: 2026-05-29

This note adds a read-only readiness gate for the earlier Dream 7B / local DLM
deployment question. It avoids claiming a deployment from architecture notes
alone: the board must show both model files and a runnable local inference
runtime before any Dream 7B smoke test can be treated as ready.

## New Probe

```text
script: scripts/probes/dream7b_readiness_probe.sh
tool_id: dream7b_readiness_probe
mode: read-only
default output: /mnt/nas/openclaw/reports/models
```

The probe checks:

- S100P architecture and memory;
- local runtime candidates such as `llama-cli`, `llama-server`, `ollama`,
  `vllm`, `torch`, `transformers`, and `llama_cpp`;
- Dream/model-like files under approved NAS/workspace/user model directories;
- whether the next step can be a bounded local inference smoke test.

Safety boundary:

- no model download;
- no external API call;
- no model server start;
- no package install;
- no file deletion.

## Baseline Meaning

This supports both baseline questions:

- PC parity: it distinguishes "S100P can run OpenClaw gateway/tools" from
  "S100P can host a local 7B DLM".
- AI NAS homework: it gives a concrete gate for whether local model features are
  in scope, instead of assuming a high-end NAS-style local model stack exists.

## Board Validation

NAS-backed runner evidence:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_readiness_20260529-155315.md
verdict: blocked_no_model
memory total: 21.3 GiB
runtime summary: llama.cpp,torch-transformers
model-like files: 0
dream-named files: 0
```

OpenClaw agent evidence through `s100p_run_probe`:

```text
report: /root/.openclaw/workspace/reports/models/dream7b_readiness_20260529-160626.md
verdict: blocked_no_model
runtime summary: llama.cpp, torch-transformers
model file count: 0
memory total: 21.3 GiB
```

Latest NAS baseline roll-up:

```text
report: /mnt/nas/openclaw/reports/baseline-status/baseline_status_20260529-160424.md
OpenClaw Gateway: active-listening
NAS workspace: mounted
Dream 7B readiness: /mnt/nas/openclaw/reports/models/dream7b_readiness_20260529-155315.md
B-003 gap: mount/install Dream 7B model files or explicitly keep local DLM out of first baseline
```

If the probe returns `blocked_no_model`, `blocked_no_runtime`, or
`blocked_no_model_and_runtime`, the next action is to decide whether Dream 7B is
part of the first baseline or remains a later model-deployment track.
