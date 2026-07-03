# Dream7B Two-Track OpenClaw Deployment Audit

- generated_at: `2026-06-22T19:42:52.153288+08:00`
- verdict: `ok_dream7b_two_track_deployment_audit`
- route_a: `OpenClaw -> 18888 -> diffuse-resident/GGUF`
- route_b: `18889 BPU queue / true-batch isolated experiment`

## Service State

- 18888 gateway: `active` / `enabled`
- 18888 backend: `diffuse-resident`
- OpenClaw gateway: `active` / `enabled`
- BPU queue: `active` / `enabled`
- 18889 experimental: `inactive` / ``
- queue pending/processing: `0` / `0`

## HBM Artifacts

| name | manifests | hbm files |
| --- | ---: | ---: |
| fine-seq16 | 0 | 8 |
| true-batch-seq16-b16 | 1 | 28 |
| true-batch-seq16-b16.upload | 0 | 0 |
| true-batch-seq16-b2 | 28 | 28 |
| true-batch-seq16-b32 | 1 | 28 |
| true-batch-seq16-b32.upload | 0 | 0 |
| true-batch-seq16-b4 | 28 | 28 |
| true-batch-seq16-b64 | 1 | 28 |
| true-batch-seq16-b64.upload | 0 | 0 |
| true-batch-seq16-b8 | 1 | 28 |
| true-batch-seq16-b8.upload | 0 | 0 |

## Risks

- no route-a blocker found

Warnings:
- latest local BPU promotion gate is not passing

## Decision

- Keep 18888 protected as the product default.
- Keep seq16 queue artifacts as the baseline.
- Use 18889 only for explicit background/batch/async experiments.
- Do not gray-route foreground OpenClaw replies to BPU until seq length, logits quality, Chinese generation, warm latency, stability, and rollback gates pass.
