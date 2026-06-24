# GitHub/Codex Workflow Runbook

This runbook supports B-006: issue -> branch -> PR -> Codex review workflow.

## Goal

Before opening remote issues or PRs, verify that the local repository can safely enter a scoped GitHub workflow:

- Git remote is configured and reachable.
- Current branch and upstream are known.
- Git identity is configured.
- GitHub issue seed exists.
- GitHub CLI availability is known.
- Working tree state is explicit before branch, commit, or PR creation.

## Entry Point

Run from the repository root on the Windows/Codex workstation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\probes\github_workflow_probe.ps1
```

Default output:

```text
reports/github-workflow/github_workflow_YYYYmmdd-HHmmss.md
```

## Acceptance

Local readiness is verified when the report shows:

- `Origin remote: pass`.
- `Current branch upstream: pass` or a documented warning.
- `Git identity: pass`.
- `Issue seed: pass`.
- Current dirty working tree count.
- Clear PR readiness verdict.

End-to-end B-006 is not verified until a real issue, scoped branch, pushed branch, draft PR, and Codex review evidence exist.

## Current Limitation

On the current workstation, `gh` is not installed or not on PATH. Issue and PR creation should use either:

- GitHub web UI.
- A configured GitHub connector.
- Installed and authenticated GitHub CLI.
