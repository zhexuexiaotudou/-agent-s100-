# Documentation Audit Runbook

Last updated: 2026-06-03

## Purpose

Use this runbook after every task. It prevents drift between code, configuration, evidence reports, README, and project Markdown documents.

## Rule

Never guess identifiers. If a command name, JSON key, environment variable, file path, model name, report field, or service name is needed, read the source file or report first and copy the exact spelling.

## Required Files

```text
README.md
docs/project_reference.md
docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md
docs/documentation_audit_runbook.md
scripts/probes/project_docs_consistency_probe.sh
```

## Standard Check

Run from the repository root:

```bash
bash scripts/probes/project_docs_consistency_probe.sh /tmp/project_docs_consistency
```

The probe writes:

```text
summary.json
summary.md
```

Approved output roots:

```text
/tmp/
/mnt/nas/openclaw/reports/
/root/.openclaw/workspace/reports/
```

## Manual Check

After the probe, inspect the changed files and answer these questions:

```text
Did README.md point to docs/project_reference.md?
Did docs/project_reference.md record new command interfaces, config keys, decisions, development log, requirements, and TODOs?
Did docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md record new Dream 7B BPU evidence when Dream 7B changed?
Were all identifiers copied from source files, config files, report files, or command output?
Did the final response mention whether the documentation check ran?
```

## Evidence Sources

Use these files before changing documentation:

```text
scripts/dream7b-bpu-forward.sh
scripts/dream7b-bpu-fine-forward.sh
scripts/dream7b-bpu-fine-batch-forward.sh
scripts/dream7b-bpu-batch-queue-runner.sh
scripts/dream7b_bpu_batch_queue_runner.py
scripts/dream7b-bpu-batch-queue-service.sh
scripts/dream7b_bpu_batch_queue_service.py
scripts/dream7b-bpu-text-forward.sh
scripts/probes/dream7b_segmented_hbm_python_forward.py
scripts/probes/dream7b_bpu_diffusion_loop_probe.sh
scripts/probes/dream7b_bpu_fine_batch_forward_probe.sh
scripts/probes/dream7b_bpu_batch_queue_runner_probe.sh
scripts/probes/dream7b_bpu_batch_queue_drain_probe.sh
scripts/probes/dream7b_bpu_batch_queue_control_probe.sh
scripts/probes/dream7b_bpu_batch_queue_lock_probe.sh
scripts/probes/dream7b_bpu_batch_queue_service_probe.sh
scripts/startup_link_check/link-check.config.json
scripts/tool_allowlist.json
docs/baseline_progress_2026-06-03_dream7b_segmented_bpu_hbm.md
```

## Failure Handling

If the probe fails:

- do not claim the task is complete;
- read the failing source path from `summary.md`;
- fix the missing document reference or incorrect identifier;
- rerun the probe.

If the probe cannot run:

- record the command attempted;
- record the error;
- do a manual review of `README.md`, `docs/project_reference.md`, and changed files;
- state in the final response that automated documentation verification did not run.
