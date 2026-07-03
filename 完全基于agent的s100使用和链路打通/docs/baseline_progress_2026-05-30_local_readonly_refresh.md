# Baseline Progress: Local Read-Only Refresh While NAS Is Down

Date: 2026-05-30

The half-hour audit gate still reports:

```text
decision: continue-non-nas-readonly-only
NAS target: 169.254.110.209 unreachable
S100P SSH: ok
OpenClaw gateway: ok
```

## Added Entrypoint

`scripts/windows/s100p-task.ps1` now has a bounded action:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\s100p-task.ps1 `
  -Action refresh-baseline-local-readonly `
  -TimeoutSeconds 540
```

It runs only read-only allowlisted reporting against:

```text
/root/.openclaw/workspace
```

This is a local fallback path. It must not be treated as NAS-backed evidence.

## Generated Reports

```text
/root/.openclaw/workspace/logs/probes/security_audit_20260530-163039.md
/root/.openclaw/workspace/logs/probes/service_policy_20260530-163049.md
/root/.openclaw/workspace/logs/probes/service_hardening_plan_20260530-163049.md
/root/.openclaw/workspace/reports/security/service_convergence_decision_20260530-163049.md
/root/.openclaw/workspace/reports/security/service_confirmation_template_20260530-163050.md
/root/.openclaw/workspace/reports/security/service_execution_preflight_20260530-163050.md
/root/.openclaw/workspace/logs/probes/sandbox_status_20260530-163050.md
/root/.openclaw/workspace/logs/probes/sandbox_isolation_smoke_20260530-163050.md
/root/.openclaw/workspace/reports/models/dream7b_readiness_20260530-163050.md
/root/.openclaw/workspace/reports/models/dream7b_config_template_20260530-163050.md
/root/.openclaw/workspace/reports/home-assistant/home_assistant_config_template_20260530-163050.md
/root/.openclaw/workspace/logs/probes/home_assistant_status_20260530-163050.md
/root/.openclaw/workspace/reports/control/control_action_template_20260530-163050.md
/root/.openclaw/workspace/logs/probes/control_action_policy_20260530-163050.md
/root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-163051.md
/root/.openclaw/workspace/reports/baseline-status/baseline_gap_decision_20260530-163051.md
/root/.openclaw/workspace/reports/teacher/teacher_baseline_briefing_20260530-163051.md
/root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-163051.md
/root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_trend_20260530-163051.md
/root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-163051.md
```

Latest B-002 local fallback refresh:

```text
/root/.openclaw/workspace/reports/document_index_20260530-163624.md
/root/.openclaw/workspace/reports/daily-summary/document_daily_summary_20260530-163624.md
/root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-163636.md
/root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-163637.md
/root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-163637.md
```

Latest A-003/B-001 local link-blocker refresh:

```text
/root/.openclaw/workspace/logs/probes/nas_link_blocker_20260530-164450.md
/root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-164504.md
/root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-164505.md
/root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-164505.md
verdict: blocked_l2_no_neighbor
target: 169.254.110.209 via eth0
ping: fail
neighbor: INCOMPLETE after ping, FAILED before ping
mount: autofs_not_reached
```

Latest A-010 local stability refresh:

```text
/root/.openclaw/workspace/logs/probes/stability_snapshot_20260530-164956.md
/root/.openclaw/workspace/reports/stability/stability_summary_20260530-165005.md
/root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-165019.md
/root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-165019.md
/root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-165019.md
snapshot count: 82
elapsed hours: 83.62
verdict: collecting
latest NAS workspace: autofs_not_reached
latest NAS fstype: autofs
```

Latest A-009 local named-capture request refresh:

```text
/root/.openclaw/workspace/reports/rosbag/rosbag_named_capture_request_20260530-165826.md
/root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-165839.md
/root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-165839.md
/root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-165839.md
approved topics detected: /rosout /parameter_events
command-like topics excluded: none_detected
acceptance: A-009 review, named=missing
```

Latest B-005/B-007 local report refresh:

```text
/root/.openclaw/workspace/logs/probes/log_diagnosis_20260530-170419.md
/root/.openclaw/workspace/reports/experiments/experiment_report_20260530-170419.md
/root/.openclaw/workspace/reports/baseline-status/baseline_status_20260530-170420.md
/root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-170420.md
/root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-170420.md
manifest entries: log_diagnosis true sha256=89dd45b7ea77b089; experiment_report true sha256=a0ecfec1576075df
```

## Semantics Fixed

`baseline_status_probe` now distinguishes a real NAS mount from autofs:

```text
NAS workspace: autofs_not_reached
Artifact scope: local workspace fallback; NAS not verified
```

`teacher_baseline_briefing_probe` now labels local fallback reports as local
fallback rather than NAS-backed evidence.

The refresh order now writes teacher briefing before acceptance/trend/manifest,
so the final manifest can hash the same-round briefing and acceptance evidence.

`sandbox_status_probe` and `sandbox_isolation_smoke_probe` are now part of the
local read-only refresh. A-006 is derived from the latest sandbox status and
smoke reports instead of being hard-coded as blocked.

`security_audit_probe` now uses the same mount classification and records the
current NAS mount line as:

```text
NAS workspace mount: warn, autofs_not_reached, fstype=autofs
```

`service_confirmation_template_probe` is now part of the local read-only
refresh. It writes a report/JSON template artifact for B-010 confirmations, but
does not write the runtime config or approve service/firewall execution.

`control_action_template_probe` is now part of the local read-only refresh. It
writes a report/JSON template artifact for B-009 reviewed actions and audit
records, but does not write the runtime allowlist or call any device API.

`home_assistant_config_template_probe` is now part of the local read-only
refresh. It writes a report/JSON template artifact for B-008 runtime
configuration shape, but does not write `/root/.openclaw/workspace/config/home_assistant.env`,
does not print a token, and does not call Home Assistant.

`dream7b_config_template_probe` is now part of the local read-only refresh. It
writes a report/JSON template artifact for B-003 deployment configuration
shape, but does not write `/root/.openclaw/workspace/config/dream7b_deployment.json`,
does not download model files, does not start a model server, and does not run
inference.

When `/root/.openclaw/workspace/documents` exists, `index_documents` and
`document_daily_summary_probe` are now part of the local read-only refresh for
B-002. They generate deterministic file metadata reports only; no external
model is used.

`nas_link_blocker_probe` is now part of the local read-only refresh for
A-003/B-001. It records the known NAS target route, eth0 address, mount fstype,
one ping, and neighbor state. It does not log in, mount, unmount, scan the
network, or use credentials.

`stability_snapshot_probe` and `stability_summary_probe` are now part of the
local read-only refresh for A-010. The snapshot probe now classifies autofs as
`autofs_not_reached` and skips `df /mnt/nas/openclaw` unless the NAS workspace
is a real NFS/CIFS mount.

`rosbag_named_capture_request_probe` is now part of the local read-only refresh
for A-009. It writes a request/approval template and current topic signals, but
does not start `ros2 bag record`, create a dataset directory, delete bags, or
send robot commands.

`log_diagnose` and `experiment_report_probe` are now part of the local
read-only refresh for B-005/B-007. They refresh local fallback diagnosis and
experiment summary artifacts before the baseline status, acceptance, and
manifest reports are generated.

## Current Acceptance Gate

```text
overall: not_ready
pass: 12
fail: 2
collecting: 1
blocked_runtime: 1
blocked_external_model: 1
blocked_external_config: 1
blocked_review: 1
blocked_confirmations: 1
```

Explicit not-ready items:

```text
A-003: fail, NAS workspace mounted = autofs_not_reached
A-006: blocked_runtime
A-010: collecting, 36.93h / 168h
B-001: fail, NAS workspace directory spec waits for NAS restore
B-002: pass, local document index and daily summary present
B-003: blocked_external_model, template present, no model files/config
B-008: blocked_external_config, template present, status=blocked_no_config
B-009: blocked_review
B-010: blocked_confirmations
```

## Tracking Impact

The two baseline tracks are still moving in the allowed non-NAS read-only lane:

- Baseline A: OpenClaw gateway, allowlisted tool execution, local evidence
  refresh, and acceptance reporting continue. A-003 now has same-round targeted
  link-blocker evidence proving the current issue is below the mount/credential
  layer. A-010 local stability evidence now continues collecting even while
  NAS-backed summaries are held. A-009 is no longer overstated as complete in
  the acceptance gate: it is `review` until a real approved named capture exists.
  B-005 and B-007 now point at same-round local reports rather than stale
  2026-05-27 artifacts.
- Baseline B: Dream 7B readiness and teacher-facing reporting continue as local
  fallback evidence. B-002 now refreshes deterministic local document index and
  daily summary when local documents exist. B-003 has a local fallback
  deployment config template, but no runtime config or model files were written.
  B-008 also has a local fallback configuration template and read-only status
  preflight, but no real Home Assistant read is attempted until runtime
  URL/token config is deliberately created.
- NAS-backed claims remain held until the NAS direct link becomes a real
  NFS/CIFS mount again.
