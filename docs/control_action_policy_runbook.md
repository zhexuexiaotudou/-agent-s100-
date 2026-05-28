# Control Action Policy Runbook

This runbook covers the first B-009 gate: low-risk automation control must have
a whitelist, a second confirmation step, and audit evidence before any action
execution path exists.

## Scope

Allowed in this gate:

- Check whether a control action policy file exists.
- Validate policy shape.
- Count pending, approved, and executed audit records.
- Write a Markdown report.

Not allowed in this gate:

- Calling Home Assistant `/api/services`.
- Calling robot motion/control commands.
- Executing policy actions.
- Creating approvals on behalf of the user.

## Policy File

Expected board-side path:

```bash
/root/.openclaw/workspace/config/control_action_allowlist.json
```

Repository template:

```bash
config/control_action_allowlist.disabled.json
```

The template is intentionally disabled by default. It may be copied to the board
for validation, but it must not be treated as approval to execute any action.

Current board validation:

```text
/mnt/nas/openclaw/logs/probes/control_action_policy_20260528-225702.md
verdict: policy_ready_no_execution
enabled action count: 0
action_executed: no
control_endpoint_called: no
```

Minimal shape:

```json
{
  "version": 1,
  "actions": [
    {
      "id": "ha.light.turn_on.desk",
      "enabled": false,
      "mode": "manual-only",
      "target": "home_assistant",
      "domain": "light",
      "service": "turn_on",
      "entity_id": "light.desk",
      "requires_approval": true,
      "confirm_phrase": "CONFIRM ha.light.turn_on.desk",
      "risk": "low",
      "notes": "Example only. Keep disabled until reviewed."
    }
  ]
}
```

For this baseline, only `dry-run` and `manual-only` modes are accepted by the
preflight probe. Any real execution path must be added separately after the
policy is reviewed.

## Runner

```bash
scripts/run_allowlisted_tool.sh control_action_policy_probe
```

Default report:

```bash
/root/.openclaw/workspace/logs/probes/control_action_policy_<stamp>.md
```

## OpenClaw Tool

```text
s100p_run_probe tool_id=control_action_policy_probe
```

## Acceptance

B-009 is not fully verified until a real low-risk action has a reviewed
allowlist entry, a pending request, an explicit approval record, and an audit
record. This preflight only moves B-009 from no implementation to a safe
`doing` state.
