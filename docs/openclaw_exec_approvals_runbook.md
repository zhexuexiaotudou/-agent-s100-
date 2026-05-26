# OpenClaw Exec Approvals Runbook

This runbook hardens A-005 by using OpenClaw exec approvals in addition to the repository allowlist runner.

## Goal

The `main` agent should not be able to run arbitrary local shell commands for S100P baseline workflows. It should only invoke:

```text
/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh
```

That runner then performs second-level validation of tool IDs and paths.

## Target Approval Policy

```json
{
  "version": 1,
  "defaults": {
    "security": "allowlist",
    "ask": "on-miss",
    "askFallback": "deny",
    "autoAllowSkills": false
  },
  "agents": {
    "main": {
      "security": "allowlist",
      "ask": "on-miss",
      "askFallback": "deny",
      "autoAllowSkills": false,
      "allowlist": [
        {
          "pattern": "/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh"
        }
      ]
    }
  }
}
```

## Apply

On the S100P:

```bash
PATH=/root/.local/lib/node-v24.16.0-linux-arm64/bin:/root/.npm-global/bin:$PATH \
openclaw approvals set --stdin <<'JSON'
{
  "version": 1,
  "defaults": {
    "security": "allowlist",
    "ask": "on-miss",
    "askFallback": "deny",
    "autoAllowSkills": false
  },
  "agents": {
    "main": {
      "security": "allowlist",
      "ask": "on-miss",
      "askFallback": "deny",
      "autoAllowSkills": false,
      "allowlist": [
        {
          "pattern": "/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh"
        }
      ]
    }
  }
}
JSON
```

## Verify

```bash
PATH=/root/.local/lib/node-v24.16.0-linux-arm64/bin:/root/.npm-global/bin:$PATH \
openclaw approvals get
```

Expected:

- `Exists` is `yes`.
- `Defaults` include `security=allowlist`.
- Agent `main` has one allowlist entry for `/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh`.

Then verify the approved runner still works:

```bash
/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh ros2_status_probe /root/.openclaw/workspace/logs/probes
```

Verify an unsafe runner argument is still rejected:

```bash
! /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh ros2_status_probe /root
```

## Residual Risk

This policy constrains OpenClaw's exec approval layer for the `main` agent. The allowlisted runner remains the real argument-level guard. Do not add `/usr/bin/bash`, `/bin/sh`, `node`, or broad wildcard paths to the OpenClaw approval allowlist, because that would re-open arbitrary command execution.

## 2026-05-27 Validation Finding

The approval policy and global exec settings were applied on the S100P:

```text
approvals target: gateway
defaults: security=allowlist, ask=on-miss, askFallback=deny, autoAllowSkills=off
main allowlist: /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh
tools.exec.security: allowlist
tools.exec.ask: on-miss
tools.exec.safeBins: []
tools.exec.strictInlineEval: true
gateway restart: ok
```

Allowed command still works:

```text
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-032127.md
nodes: none
topics: /parameter_events, /rosout
services: none
```

However, the OpenClaw agent CLI path still executed a non-allowlisted command:

```text
test command: /usr/bin/touch /tmp/openclaw_policy_nonallowlisted_0325
agent result: reported executed
board check: MARKER_EXISTS
cleanup: MARKER_REMOVED
```

Conclusion: A-005 must remain `doing`. The current setup improves the documented command path and runner-level checks, but does not prove platform-level command restriction for `openclaw agent --agent main`.

Next hardening options:

- Find or implement a narrower OpenClaw tool surface that exposes only `run_allowlisted_tool.sh`.
- Disable or deny `system.run` entirely and replace ROS2 status with a native/plugin command.
- Treat current `TOOLS.md` guidance as an operator convention only, not as a hard security boundary.

## Follow-up: `tools.exec.security=deny`

`tools.exec.security` was changed from `allowlist` to `deny`, and the gateway was restarted. The narrow plugin path still worked, but broad local command execution was still not blocked in the tested CLI agent path:

```text
test command: /usr/bin/touch /tmp/openclaw_policy_nonallowlisted_0340
board check: MARKER_EXISTS
cleanup: marker removed
```

This reinforces that A-005 cannot rely on OpenClaw's current exec policy alone. The verified usable path is the custom `s100p_run_probe` plugin plus the repository runner validation.
