# Baseline Progress: Audit Consistency Hardening

Date: 2026-05-30

The half-hour audit loop now checks more than connectivity. It also verifies
local and S100P-side script hygiene so the baseline tooling keeps the same
maintenance conventions as new probes are added.

## Added Checks

`baseline-audit.ps1` now verifies:

```text
PowerShell parser checks for Windows entrypoints
UTF-8 JSON parsing for tool_allowlist.json and link-check.config.json
tool_allowlist.json consistency with scripts/run_allowlisted_tool.sh
remote S100P bash -n checks for run_allowlisted_tool.sh and scripts/probes/*.sh
remote S100P python3 -m json.tool check for tool_allowlist.json
```

The allowlist consistency check requires each tool entry to have:

```text
a standard lowercase/underscore id
a local script path that exists
a matching case branch in run_allowlisted_tool.sh
a matching script path reference in run_allowlisted_tool.sh
approvedOutputPrefixes
```

## Latest Evidence

```text
manual audit: logs/baseline-audit/baseline_audit_20260530-172027.md
background loop pid: 152304
background loop first report: logs/baseline-audit/baseline_audit_20260530-172101.md
decision: continue-non-nas-readonly-only
powershellSyntaxOk: True
jsonSyntaxOk: True
allowlistConsistencyOk: True
remoteScriptValidationOk: True
```

The old background audit loop was stopped and replaced with a new one using the
same 30-minute cadence, so future automatic audits use the hardened checks.

## Tracking Impact

This does not unblock NAS-backed work. It reduces maintenance risk while the
baselines continue to grow by making local probe additions fail the audit if
the JSON registry, wrapper case branch, script file, or remote Bash syntax drift
out of sync.
