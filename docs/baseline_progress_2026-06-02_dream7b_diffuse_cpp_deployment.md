# Baseline Progress: Dream 7B diffuse-cpp Deployment

Date: 2026-06-02

This pass turns the existing Dream 7B assets on the NAS into a reproducible
S100P deployment gate. It does not claim BPU acceleration: the validated runtime
path is local CPU inference through `diffuse-cpp`, with model files stored on the
NAS and mounted by S100P over NFS.

## Deployment State

```text
model: /mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf
model sha256: c93a1386030efa2eff137ced99a33c2b4d9d8867e281bc1c45eaa6ef0864cbd4
runtime: /mnt/nas/openclaw/runtimes/diffuse-cpp/build/diffuse-cli
text wrapper: /usr/local/bin/dream7b-text
token wrapper: /usr/local/bin/dream7b-cli
default config: /root/.openclaw/workspace/config/dream7b_deployment.json
NAS config copy: /mnt/nas/openclaw/models/dream7b/dream7b_deployment.json
```

The model checksum was verified on S100P:

```text
/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf: OK
```

## Script Update

`scripts/probes/dream7b_smoke_probe.sh` now supports the deployed
`diffuse-cpp` path in addition to the earlier `llama-cli` and `transformers`
paths.

The probe also accepts the fixed NAS model deployment config:

```text
/mnt/nas/openclaw/models/dream7b/dream7b_deployment.json
```

`scripts/run_allowlisted_tool.sh` and `scripts/tool_allowlist.json` keep this as
a single explicit approved config path instead of allowing arbitrary NAS config
files.

## Current Smoke Evidence

Command:

```bash
sudo -n bash /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh \
  dream7b_smoke_probe \
  /mnt/nas/openclaw/reports/models
```

Report:

```text
/mnt/nas/openclaw/reports/models/dream7b_smoke_20260602-141525.md
```

Result:

```text
verdict: ok_smoke
runtime: diffuse-cpp
elapsed_seconds: 22.99
output: The capital of France is Paris.
```

The smoke test is bounded local inference. It did not download models and did
not start a persistent model server.

## Maintenance Meaning

Dream 7B is now deployable on the S100P as a local CLI/text inference path:

```bash
dream7b-text "What is the capital of France?"
```

For project automation, the safer entry remains the allowlisted smoke probe
until a separate prompt-bounded Dream text tool is deliberately added.

This does not use the S100P 128 TOPS BPU. Using BPU would still require a
Dream-compatible `.hbm` compilation path from the S100 LLM toolchain or a custom
model adapter.
