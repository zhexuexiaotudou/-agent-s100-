# Baseline Progress: Teacher Briefing Probe

Date: 2026-05-29

This adds a read-only report generator for the teacher-facing version of the two baseline questions:

1. Whether S100P can reproduce the useful parts of PC OpenClaw.
2. How much of high-end AI NAS / OpenClaw NAS behavior S100P + NAS has reproduced.

## Added

```text
script: scripts/probes/teacher_baseline_briefing_probe.sh
tool_id: teacher_baseline_briefing_probe
output: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_*.md
json: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_*.json
```

## Safety Boundary

```text
mode: read-only
system_changes: no
service_changes: no
firewall_changes: no
control_actions: no
model_inference: no
```

## Baseline Value

The probe turns the latest NAS-backed evidence into a concise Chinese briefing. It keeps the important boundaries explicit: A-010 is still collecting, Dream 7B is not deployed until model files plus smoke pass, Home Assistant needs URL/token, B-009 needs reviewed actions, and B-010 remains preflight-only.

## Board Validation

Allowlist runner evidence:

```text
report: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_20260529-200427.md
json: /mnt/nas/openclaw/reports/teacher/teacher_baseline_briefing_20260529-200427.json
A-010: 80 snapshots, 25.66h, collecting
allowlisted_tools: 28
Dream 7B: readiness=blocked_no_model; smoke=blocked_no_config
```

OpenClaw agent evidence through `s100p_run_probe`:

```text
tool_id: teacher_baseline_briefing_probe
report: /root/.openclaw/workspace/reports/teacher/teacher_baseline_briefing_20260529-200724.md
A-010: 80 snapshots, 25.66h, collecting
```

The generated briefing directly answers the supervisor's two questions and is safe to regenerate whenever the NAS evidence updates.
