# Baseline Progress: Exec Policy Hardening

Date: 2026-05-27

## Status

| Item | Status | Evidence |
| --- | --- | --- |
| A-005 allowlisted runner | doing | `run_allowlisted_tool.sh` validates tool IDs and rejects unsafe paths. ROS2 status can be produced through the runner. |
| A-005 OpenClaw exec approvals | not verified | Gateway approvals and `tools.exec.security=allowlist` were applied, but `openclaw agent --agent main` still executed a non-allowlisted command. |
| A-005 narrow plugin path | verified path | `s100p-allowlisted-tools` loaded and the agent made real `s100p_run_probe` tool calls for ROS2, document indexing, and log diagnosis. Invalid plugin `tool_id` was rejected. |
| B-002 document index fallback | verified path | The plugin ran `index_documents` against `/root/.openclaw/workspace/documents` and wrote `/root/.openclaw/workspace/reports/document_index_20260527-034707.md`. |
| B-005 log diagnosis fallback | verified path | The plugin ran `log_diagnose` against `/root/.openclaw/workspace/logs` and wrote `/root/.openclaw/workspace/logs/probes/log_diagnosis_20260527-034730.md`. |

## Configuration Applied On Board

OpenClaw exec approvals:

```text
target: gateway
defaults: security=allowlist, ask=on-miss, askFallback=deny, autoAllowSkills=off
main allowlist: /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh
```

OpenClaw config:

```json
{
  "tools": {
    "exec": {
      "security": "allowlist",
      "ask": "on-miss",
      "safeBins": [],
      "strictInlineEval": true
    }
  }
}
```

Gateway restart succeeded and health remained OK.

## Positive Test

Allowed runner path still works:

```text
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-032127.md
nodes: none
topics: /parameter_events, /rosout
services: none
```

## Negative Test Failure

Non-allowlisted command test:

```text
command requested through agent: /usr/bin/touch /tmp/openclaw_policy_nonallowlisted_0325
board check after agent turn: MARKER_EXISTS
cleanup: MARKER_REMOVED
```

This proves A-005 is not platform-verified yet. The current system has runner-level checks and documentation-level guidance, but not a hard OpenClaw-level restriction for the tested `openclaw agent --agent main` path.

## Next Options

- Create a narrow OpenClaw plugin/native command that exposes only approved runner tool IDs.
- Disable or deny broad `system.run` for the relevant channel/session once a narrow command exists.
- Keep `TOOLS.md` guidance as an operational convention until the narrow tool exists.

## Plugin Path

A plugin was created under:

```text
openclaw-plugins/s100p-allowlisted-tools
```

It registers a planned `s100p_run_probe` tool and only accepts:

```text
openclaw_status_probe
ros2_status_probe
sandbox_status_probe
log_diagnose
index_documents
```

The first board install failed because vendored dependencies under `node_modules` confused plugin discovery. The plugin was converted to a zero-dependency package and then installed successfully.

Loaded plugin evidence:

```text
S100P Allowlisted Tools | s100p-allowlisted-tools | loaded
```

Agent tool-call evidence:

```text
toolCall name: s100p_run_probe
arguments: {"tool_id":"ros2_status_probe"}
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-033810.md
```

Invalid plugin input evidence:

```text
INVALID_TOOL_REJECT_OK
tool_id must be one of: openclaw_status_probe, ros2_status_probe
```

`tools.exec.security=deny` was then applied and the narrow plugin still worked:

```text
report: /root/.openclaw/workspace/logs/probes/ros2_status_20260527-033957.md
nodes: 0
topics: 2
services: 0
```

Broad exec negative test still failed even after `tools.exec.security=deny`:

```text
command requested through agent: /usr/bin/touch /tmp/openclaw_policy_nonallowlisted_0340
board check after agent turn: MARKER_EXISTS
cleanup: marker removed
```

Conclusion: the narrow plugin path is verified for approved probes, but A-005 remains `doing` overall because broad local command execution is still available in the tested agent path.

The same plugin path now covers the B-002/B-005 local workspace fallback:

```text
toolCall name: s100p_run_probe
arguments: {"tool_id":"index_documents"}
report: /root/.openclaw/workspace/reports/document_index_20260527-034707.md
indexed_files: 2
```

```text
toolCall name: s100p_run_probe
arguments: {"tool_id":"log_diagnose"}
report: /root/.openclaw/workspace/logs/probes/log_diagnosis_20260527-034730.md
generic error/failed: 3
connection refused: 1
exception/fatal: 1
permission denied: 1
```

These B-002/B-005 checks are intentionally scoped to `/root/.openclaw/workspace` because the NAS mount is not present yet.

The same narrow plugin path now also covers A-006 status collection:

```text
toolCall name: s100p_run_probe
arguments: {"tool_id":"sandbox_status_probe"}
report: /root/.openclaw/workspace/logs/probes/sandbox_status_20260527-040824.md
runtime_available: no
isolation_verdict: blocked
```

This is status collection only. A-006 remains unverified because the board currently has no container runtime to test isolation.
