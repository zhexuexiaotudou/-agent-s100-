# Baseline Progress: B-003 Dream 7B Config Template Local Refresh

Date: 2026-05-30

The active audit lane is still `continue-non-nas-readonly-only`, so this pass
only added a B-003 deployment configuration template artifact. It did not write
the runtime config, download model files, start a model server, or run
inference.

## Implementation

```text
script: scripts/probes/dream7b_config_template_probe.sh
allowlist id: dream7b_config_template_probe
windows action: refresh-baseline-local-readonly
output: /root/.openclaw/workspace/reports/models
runtime target not written: /root/.openclaw/workspace/config/dream7b_deployment.json
```

The template records the expected bounded smoke-test configuration shape:

```text
model.path: /root/.openclaw/workspace/models/dream7b
model.runtime: auto
smoke_test.prompt: Respond with exactly: OK
smoke_test.max_new_tokens: 16
smoke_test.timeout_seconds: 120
approved model roots: /mnt/nas/openclaw/models, /root/.openclaw/workspace/models, /home/sunrise/models
```

## Latest Evidence

```text
config template: /root/.openclaw/workspace/reports/models/dream7b_config_template_20260530-163050.md
readiness: /root/.openclaw/workspace/reports/models/dream7b_readiness_20260530-163050.md
baseline status: /root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-163051.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-163051.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-163051.md
manifest entry: dream7b_config_template true sha256=7cf73c7e864136eb
```

The template probe reported:

```text
runtime_config: missing
local_model_dir: missing
nas_model_dir: skipped_not_real_nas_mount:autofs
```

## Tracking Impact

B-003 remains `blocked_external_model`. The missing step is now precise:
install or mount model files in an approved model root, deliberately create
`/root/.openclaw/workspace/config/dream7b_deployment.json` from the template,
then run `dream7b_smoke_probe`. This change does not claim Dream 7B deployment
and does not authorize a persistent model service.
