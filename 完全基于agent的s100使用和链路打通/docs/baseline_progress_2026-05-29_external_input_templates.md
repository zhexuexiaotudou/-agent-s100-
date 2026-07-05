# External Input Templates For Remaining Baseline Gates

Date: 2026-05-29

This adds concrete handoff templates for the remaining baseline gates that cannot be completed without external inputs. No service, firewall, control, or model-server changes are executed by these templates.

## B-003 Dream 7B

- Added `config/dream7b_deployment.example.json`.
- Added `scripts/probes/dream7b_smoke_probe.sh`.
- The smoke probe requires an explicit `dream7b_deployment.json` and a model path under an approved local model directory.
- If the config or model is missing, it writes a blocked report instead of downloading model files.
- If the model exists, it runs one bounded local smoke test with a short timeout and writes Markdown plus JSON evidence.

Board validation through the allowlist runner:

```text
report: /mnt/nas/openclaw/reports/models/dream7b_smoke_20260529-195131.md
verdict: blocked_no_config
runtime: not_attempted
meaning: the smoke gate is installed; model config is still absent
```

OpenClaw agent validation through `s100p_run_probe` after Gateway restart:

```text
report: /root/.openclaw/workspace/reports/models/dream7b_smoke_20260529-195337.md
verdict: blocked_no_config
runtime: not_attempted
meaning: the plugin path can trigger the Dream 7B smoke gate; no model inference was attempted
```

## B-008 Home Assistant

- Added `config/home_assistant_env_example.txt`.
- The existing HA probe remains read-only and only calls `GET /api/` and `GET /api/states`.
- Real URL/token are still external inputs and should not be committed.

## B-009 Control Actions

- The current disabled allowlist template remains the gate.
- No action is enabled, approved, or executed by default.
- Real entity IDs and approval phrases are still external inputs.

## B-010 Service Convergence

- The current disabled service confirmation template remains the gate.
- Service/firewall execution remains blocked until each confirmation is deliberately set in the runtime config.

## Baseline Meaning

These templates convert the remaining blockers from vague requirements into deterministic gates:

1. Place the required private input in the documented runtime path.
2. Run the read-only or bounded probe.
3. Use the generated report as the acceptance evidence.
