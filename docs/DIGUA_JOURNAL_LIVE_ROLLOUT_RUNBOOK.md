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

## Approved Live Rollout Command

Use this only after the operator explicitly approves live rollout for the current session.

```powershell
$env:AI_NAS_OPERATOR_APPROVED_DIGUA_JOURNAL_LIVE_ROLLOUT='1'
py scripts\probes\digua_journal_live_rollout.py
```

The runner targets `sunrise@192.168.127.10` with `%USERPROFILE%\.ssh\s100p_linkcheck_ed25519` and the live OpenClaw workspace at `/mnt/nas/openclaw`.

## 2026-07-04 Live Rollout Result

- verdict: `digua_journal_live_rollout_passed`
- live DB: `/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal.sqlite3`
- journal evidence dir: `/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_evidence`
- journal export dir: `/mnt/nas/openclaw/reports/qwen25_ai_nas/digua_journal_exports`
- S100P user: `sunrise`
- S100P IPs observed: `192.168.127.10/24`, `192.168.137.10/24`
- service action: `systemctl --user restart openclaw-gateway.service`
- protected ports unchanged: `127.0.0.1:8765`, `127.0.0.1:18080`, `127.0.0.1:18888`
- `/journal`: HTTP 200
- `/api/journal/health`: OK
- privacy scan: `private_leak_count=0`
- regression: remote py_compile OK, local Journal pytest OK, disable script probe OK

The rollout synced only Journal/OpenClaw extension code, configs, static assets, migrations, and helper scripts into `/mnt/nas/openclaw`. It did not replace OpenClaw, replace Qwen, modify protected port configuration, enable cloud generation, enable screenshots or desktop capture, grant Qwen tool execution authority, or upload private NAS raw content.

## Required Outputs

- `reports/21200_journal_live_rollout_gate.json`
- `reports/21210_journal_live_e2e_gate.json`
- `reports/21220_journal_live_regression_gate.json`
- `01_final_evidence/digua_journal_live_rollout_gate_packet.json`
- `digua_journal_live_rollout_for_gptpro_<timestamp>.zip`
