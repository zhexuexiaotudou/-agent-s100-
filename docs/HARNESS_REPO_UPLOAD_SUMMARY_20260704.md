# Harness Repo Upload Summary - 2026-07-04

This note defines the harness upload scope for the Digua AI-NAS repo.

## Scope

Included:

- Stage 2.10 through Stage 5 harness gate packets, reports, traces, and final
  decision docs.
- Policy/config files for readonly shadow, signed approvals, copy routes, and
  default-service harness integration.
- Source code for copy route guarding, OpenClaw default-service middleware,
  token-budget route adapter, harness status route, and copy confirmation UI.
- Gate runners for Stage 2.10, Stage 3 readonly shadow, Stage 4 write/copy
  progression, real NAS preflight/copy canaries, aggressive progression, and
  Stage 5 default service.
- Latest GPT Pro review bundles for the new stages only; older duplicate rerun
  bundles are intentionally left unstaged.

Excluded:

- Dream7B runtime/model artifacts.
- Tokenizer-only final packages.
- Journal rollout packages.
- Older duplicate harness GPT Pro packages from repeated same-stage reruns.
- Operator approval scratch files with chat-derived approval text.

## Current Final Verdict

Stage 5 passed with:

```text
harness_default_service_integrated_limited_copy_enabled
```

The final package is:

```text
evidence_for_gptpro/digua_ai_nas_harness_default_service_for_gptpro_20260704-143537.zip
SHA256: 38bc412b3cf0bbf1a159bdc75413a680f9cc2f3c5ec14d9878a8fb962e0c2fbf
```

## Safety Boundary

The default service supports bounded copy only after policy approval, typed
confirmation, signed approval token, source rehash, target absence, and
allowlisted dispatcher execution.

The following remain unavailable:

```text
delete, move, rename, chmod, chown, overwrite, recursive,
recursive_delete, arbitrary_shell, Qwen autonomous execution,
private raw cloud egress
```

## Verification Used Before Upload

- `py -3 gates/stage5_default_service_gates.py --readonly-runs 500 --copy-runs 100 --token-runs 50 --concurrency 4`
- `Get-FileHash -Algorithm SHA256 evidence_for_gptpro/digua_ai_nas_harness_default_service_for_gptpro_20260704-143537.zip`
- S100P live service checks:
  - `openclaw-gateway.service`: active
  - `qwen25-local-openai-gateway.service`: active
  - `curl http://127.0.0.1:8765/api/harness/status`: ok
  - `curl http://127.0.0.1:18080/health`: ok
