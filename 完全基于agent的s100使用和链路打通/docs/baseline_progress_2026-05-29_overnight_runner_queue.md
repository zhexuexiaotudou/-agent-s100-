# Baseline Progress: Overnight Runner Queue

Date: 2026-05-29

The current overnight runner was started before the newer acceptance, trend, manifest, and teacher-briefing probes were added to the per-iteration loop. To avoid running two samplers concurrently, this adds a queue script that waits for the current runner PID to exit, then starts the next runner with the updated script stack.

## Added

```text
scripts/queue_next_overnight_baseline_runner.sh
scripts/check_overnight_queue.sh
```

## Safety Boundary

```text
concurrent_runner: avoided
duplicate_queue: refused by default
current_pid: waits until exit
max_wait_hours: bounded
system_changes: no
service_changes: no
firewall_changes: no
control_actions: no
```

## Intended Use

```bash
scripts/queue_next_overnight_baseline_runner.sh 10 1800 18
bash scripts/check_overnight_queue.sh
```

The queued next runner will use the updated `overnight_baseline_runner.sh`, so future iterations include:

```text
baseline_acceptance
baseline_acceptance_trend
baseline_evidence_manifest
teacher_baseline_briefing
```

If a queue is already waiting, the launcher exits without starting another one
unless `OVERNIGHT_QUEUE_ALLOW_DUPLICATE=1` is explicitly set.

## Validation

```text
remote_install: /root/.openclaw/workspace/scripts
bash_syntax: pass
current_runner_pid: 278801
current_runner_status: running
current_runner_completed_iterations: 10
current_runner_failed_events: 0
queue_pid: 362168
queue_pid_file: /mnt/nas/openclaw/logs/overnight/overnight_queue_20260529-210322.pid
queue_log: /mnt/nas/openclaw/logs/overnight/overnight_queue_20260529-210322.log
queue_status_report: /mnt/nas/openclaw/reports/baseline-status/overnight_queue_status_20260529-210410.md
latest_queue_status_report: /mnt/nas/openclaw/reports/baseline-status/overnight_queue_status_20260529-211239.md
queue_status: running
queue_waiting_for_pid: 278801
duplicate_queue_attempt: refused
duplicate_queue_existing_pid: 362168
```

The SSH launcher returned after the detach fix. The queued process remains on
S100P and will start a new 10-hour, 1800-second-interval runner after the old
PID exits.
