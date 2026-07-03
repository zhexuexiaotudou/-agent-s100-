# Baseline Progress: Next Action Queue

Date: 2026-05-30

Added a read-only next-action queue so the two baseline tracks can keep moving
with less manual triage. The queue reads the latest baseline acceptance JSON,
uses the active audit decision as the route constraint, and classifies each
baseline item into a lane.

## Implementation

`refresh-baseline-local-readonly` now runs:

```text
baseline_next_action_queue_probe /root/.openclaw/workspace /root/.openclaw/workspace/reports/baseline-status continue-non-nas-readonly-only
```

The probe writes Markdown and JSON only. It does not mount NAS, write
credentials, run control actions, install runtimes, or change services.

## Latest Evidence

```text
next action queue: /root/.openclaw/workspace/reports/baseline-status/baseline_next_action_queue_20260530-202337.md
acceptance: /root/.openclaw/workspace/reports/baseline-status/baseline_acceptance_20260530-202337.md
manifest: /root/.openclaw/workspace/reports/baseline-status/baseline_evidence_manifest_20260530-202337.md
operator_review_gate: /root/.openclaw/workspace/reports/review-gates/operator_review_gate_20260530-202336.md
operator_review_gate_overall: review_packets_ready
external_input_gate: /root/.openclaw/workspace/reports/external-inputs/external_input_gate_20260530-202336.md
external_input_gate_overall: external_input_packets_ready
infrastructure_gate: /root/.openclaw/workspace/reports/infrastructure/infrastructure_gate_20260530-202335.md
infrastructure_gate_overall: infrastructure_packets_ready
manifest entry: baseline_next_action_queue true
```

Current lane counts:

```text
done: 11
collecting: 1
ready_for_operator_decision: 3
ready_for_external_input: 2
ready_for_infrastructure_action: 3
```

Safe under the current audit lane:

```text
A-010 collecting: Keep stability sampler and overnight runner collecting until 168h.
```

Ready for operator decision:

```text
A-009 review: approve one bounded named capture request before rosbag_named_capture_probe
B-009 blocked_review: review real action template and runtime allowlist before execution
B-010 blocked_confirmations: fill runtime confirmations before service/firewall preflight can pass
```

Ready for external input:

```text
B-003 blocked_external_model: provide local model files and dream7b_deployment.json
B-008 blocked_external_config: fill Home Assistant URL/token env for read-only status
```

Ready for infrastructure action:

```text
A-003 fail: restore NAS L2/IP reachability, then validate mount/write deliberately
A-006 blocked_runtime: install Docker/Podman/runc or explicitly drop A-006 from baseline v1
B-001 fail: restore NAS L2/IP reachability before relying on B-track reports
```

## Tracking Impact

The queue makes the current path explicit: continue local/S100P read-only
evidence refresh and A-010 collection, while holding NAS mount work, runtime
install, model/HA configuration, control execution, and service convergence
until their external or review prerequisites are satisfied.
It now separates incomplete review material from completed review packets that
are waiting only for an operator decision.
It also separates incomplete external-input material from packets that are ready
and waiting only for concrete model/config input.
It also separates infrastructure packets that are ready for a deliberate
infrastructure action from evidence-gathering work that can still run
automatically.
