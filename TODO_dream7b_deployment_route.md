# TODO Dream7B Deployment Route

Date: 2026-06-19

Status: superseded on 2026-06-23 by the project decision that Dream7B is not
the continuing model direction for this project.

Use this file only as historical context for the Dream7B deployment phase. The
current entry points are:

- `README.md`
- `docs/project_retrospective_2026-06-23.md`
- `docs/reusable_toolchain_map_2026-06-23.md`

## Guardrails

- Do not replace `dream7b-bpu-batch-queue.service`.
- Do not overwrite `http://127.0.0.1:18888/v1`.
- Do not delete queue baseline HBM artifacts.
- Do not promote true-batch based only on compile success or shape correctness.
- Do not evaluate only `avg_nonzero_bpu_loading`.
- Do not start with full prefill+decode true-batch takeover.

## Completed In This Step

- Read-only production service audit.
- Read-only true-batch B=4 artifact audit.
- Deployment file map.
- Production baseline document.
- Cloud compile plan.
- Hybrid scheduler design.
- Unified telemetry script skeletons.
- Backend policy draft.

## Next Steps

1. Run unified queue baseline telemetry and store a normalized JSON report.
2. Run unified true-batch B=4 telemetry and store a normalized JSON report.
3. Compare queue and true-batch with `scripts/telemetry/compare_backends.py`.
4. Fill missing latency and tokens/s fields if the current probe outputs do not expose them yet.
5. Package `cloud_compile_bundle/` for repeatable cloud B=4 rebuilds.
6. Add `manifest.json`, `shape_report.json`, and root `sha256sums.txt` to the B=4 artifact root.
7. Design but do not install `dream7b-true-batch-experimental.service`.
8. Only after repeated telemetry gates pass, discuss enabling hybrid observe-only routing.

## Open Questions

- Which request trace should be used as the canonical latency workload?
- Should the experimental model alias be exposed through a separate 18889 gateway only, or kept internal until telemetry passes?
- What is the acceptable sustained queue wait ceiling for batchable decode requests?
- Should B=8 remain a cloud-only experiment until B=4 clears unified telemetry gates?
