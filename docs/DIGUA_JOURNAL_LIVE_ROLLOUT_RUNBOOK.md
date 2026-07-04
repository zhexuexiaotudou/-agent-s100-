# Digua Journal Live Rollout Runbook

This runbook covers the approval boundary for enabling Digua Journal on the live S100P/OpenClaw default service.

## Approval Gate

Live rollout must not start unless one of these is true:

- `AI_NAS_OPERATOR_APPROVED_DIGUA_JOURNAL_LIVE_ROLLOUT=1`
- `operator_approval/digua_journal_live_rollout_approved.json` exists

Without approval, the rollout runner writes blocked reports and does not SSH into S100P, reload OpenClaw, change ports, run migrations on the live NAS path, or mutate live services.

## Protected Boundaries

- Do not modify ports `8765`, `18080`, `18888`, or `18889`.
- Do not replace OpenClaw.
- Do not replace Qwen.
- Do not enable cloud generation.
- Do not enable screenshot capture, desktop visual capture, keyboard tracking, or mouse tracking.
- Do not grant Qwen tool execution authority.
- Do not execute delete, move, rename, or chmod on NAS content.
- Do not upload private NAS raw content.

## Current Blocked Command

```powershell
py scripts\probes\digua_journal_live_rollout.py --allow-blocked-output
```

Expected blocked verdict:

```text
blocked_by_no_operator_approval
```

## Required Outputs

- `reports/21200_journal_live_rollout_gate.json`
- `reports/21210_journal_live_e2e_gate.json`
- `reports/21220_journal_live_regression_gate.json`
- `01_final_evidence/digua_journal_live_rollout_gate_packet.json`
- `digua_journal_live_rollout_for_gptpro_<timestamp>.zip`
