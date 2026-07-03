# Baseline Progress: B-009 Disabled Control Policy

Date: 2026-05-28

This note records the disabled-by-default control policy baseline for B-009. It validates the policy shape and audit gate without executing any control action.

## Verdict

| Item | Status | Evidence |
| --- | --- | --- |
| Policy template | verified | `config/control_action_allowlist.disabled.json` is valid JSON and contains one disabled example action. |
| Board policy file | verified | Template copied to `/root/.openclaw/workspace/config/control_action_allowlist.json`. |
| NAS preflight | verified | `/mnt/nas/openclaw/logs/probes/control_action_policy_20260528-225702.md` reports `policy_ready_no_execution`. |
| OpenClaw tool call | verified | `s100p_run_probe` returned `policy_ready_no_execution` with enabled action count `0`. |
| Control execution | blocked by design | `action_executed: no`, `control_endpoint_called: no`. |

## Output

```text
/mnt/nas/openclaw/logs/probes/control_action_policy_20260528-225702.md
/root/.openclaw/workspace/logs/probes/control_action_policy_20260528-225740.md
/mnt/nas/openclaw/reports/baseline-status/baseline_status_20260528-225904.md
```

## Policy Summary

```text
policy_state: disabled_template
actions: 1
enabled actions: 0
mode: manual-only
requires_approval: true
confirm_phrase: CONFIRM ha.light.turn_on.example
audit directory: /root/.openclaw/workspace/logs/control-audit
```

## Baseline Impact

- B-009 remains `doing`, but the previous `blocked_no_policy` gap is closed.
- The remaining gap is intentionally stricter: replace the disabled example with reviewed real entity/action entries, then implement request/approve/execute audit.
- No Home Assistant service endpoint or robot control endpoint was called.
