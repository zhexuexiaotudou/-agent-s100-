#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


APPROVED_QUEUE_PREFIXES = (
    "/tmp/",
    "/mnt/nas/openclaw/queues",
    "/mnt/nas/openclaw/queues/",
    "/mnt/nas/openclaw/reports",
    "/mnt/nas/openclaw/reports/",
    "/root/.openclaw/workspace/queues",
    "/root/.openclaw/workspace/queues/",
    "/root/.openclaw/workspace/reports",
    "/root/.openclaw/workspace/reports/",
)

APPROVED_OUTPUT_PREFIXES = (
    "/tmp/",
    "/mnt/nas/openclaw/reports",
    "/mnt/nas/openclaw/reports/",
    "/root/.openclaw/workspace/reports",
    "/root/.openclaw/workspace/reports/",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Directory-backed service loop for Dream 7B BPU batch queue requests.")
    parser.add_argument("queue_dir", help="Queue directory containing pending, processing, done, and failed subdirectories.")
    parser.add_argument("output_dir", help="Output directory for service summary and per-job runner reports.")
    parser.add_argument("--runner-cmd", default="dream7b-bpu-batch-queue-runner")
    parser.add_argument("--max-batch-size", type=int, default=4)
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--forward-cmd", default="dream7b-bpu-fine-batch-forward")
    parser.add_argument("--bpu-lock-path", default="/tmp/dream7b_bpu_batch_queue_runner.lock")
    parser.add_argument("--bpu-lock-timeout-sec", type=float, default=600.0)
    parser.add_argument("--poll-interval-sec", type=float, default=1.0)
    parser.add_argument("--max-iterations", type=int, default=0, help="0 means run until stopped.")
    parser.add_argument("--once", action="store_true", help="Run one polling iteration and exit.")
    parser.add_argument("--drain-all", action="store_true", help="Pass --drain-all to each runner invocation.")
    return parser.parse_args()


def is_approved_path(path: Path, prefixes: tuple[str, ...]) -> bool:
    text = str(path)
    return any(text == prefix.rstrip("/") or text.startswith(prefix) for prefix in prefixes)


def ensure_queue_dirs(queue_dir: Path):
    paths = {
        "pending": queue_dir / "pending",
        "processing": queue_dir / "processing",
        "done": queue_dir / "done",
        "failed": queue_dir / "failed",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def next_pending_job(pending_dir: Path):
    jobs = sorted(path for path in pending_dir.glob("*.jsonl") if path.is_file())
    return jobs[0] if jobs else None


def move_job(source: Path, target_dir: Path, suffix: str):
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source.stem}{suffix}"
    if target.exists():
        target = target_dir / f"{source.stem}_{int(time.time() * 1000)}{suffix}"
    source.replace(target)
    return target


def run_job(args, job_path: Path, output_dir: Path, job_index: int):
    job_output_dir = output_dir / "jobs" / job_path.stem
    job_output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        args.runner_cmd,
        str(job_path),
        str(job_output_dir),
        "--max-batch-size",
        str(args.max_batch_size),
        "--seq-len",
        str(args.seq_len),
        "--top-k",
        str(args.top_k),
        "--forward-cmd",
        args.forward_cmd,
        "--bpu-lock-path",
        args.bpu_lock_path,
        "--bpu-lock-timeout-sec",
        str(args.bpu_lock_timeout_sec),
    ]
    if args.drain_all:
        cmd.append("--drain-all")
    started = time.monotonic()
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=900)
    wall_ms = round((time.monotonic() - started) * 1000, 3)
    (job_output_dir / "runner.stdout").write_text(proc.stdout, encoding="utf-8")
    (job_output_dir / "runner.stderr").write_text(proc.stderr, encoding="utf-8")
    summary_path = job_output_dir / "queue_summary.json"
    runner_summary = None
    if summary_path.is_file():
        runner_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "job_index": job_index,
        "request_jsonl": str(job_path),
        "output_dir": str(job_output_dir),
        "runner_command": cmd,
        "returncode": proc.returncode,
        "wall_ms": wall_ms,
        "queue_summary": str(summary_path) if summary_path.is_file() else None,
        "runner_verdict": runner_summary.get("verdict") if isinstance(runner_summary, dict) else None,
        "processed_count": runner_summary.get("processed_count") if isinstance(runner_summary, dict) else None,
        "deferred_count": runner_summary.get("deferred_count") if isinstance(runner_summary, dict) else None,
        "skipped_count": runner_summary.get("skipped_count") if isinstance(runner_summary, dict) else None,
        "bpu_lock": runner_summary.get("bpu_lock") if isinstance(runner_summary, dict) else None,
    }


def write_summary(output_dir: Path, payload: dict):
    summary_json = output_dir / "service_summary.json"
    summary_md = output_dir / "service_summary.md"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B BPU Batch Queue Service",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- queue_dir: {payload['queue_dir']}",
        f"- output_dir: {payload['output_dir']}",
        f"- runner_command: {payload['runner_command']}",
        f"- processed_job_count: {payload['processed_job_count']}",
        f"- failed_job_count: {payload['failed_job_count']}",
        f"- iteration_count: {payload['iteration_count']}",
        "",
        "## Jobs",
        "",
        "| job_index | request_jsonl | runner_verdict | processed_count | deferred_count | skipped_count | bpu_lock_wait_ms |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for job in payload["jobs"]:
        lock = job.get("bpu_lock") or {}
        lines.append(
            f"| {job['job_index']} | {job['request_jsonl']} | {job.get('runner_verdict')} | {job.get('processed_count')} | {job.get('deferred_count')} | {job.get('skipped_count')} | {lock.get('wait_ms')} |"
        )
    if not payload["jobs"]:
        lines.append("| | none | | | | | |")
    lines.extend(["", "## Errors", ""])
    if payload["errors"]:
        lines.extend(f"- {item}" for item in payload["errors"])
    else:
        lines.append("- none")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_md


def build_summary_payload(args, queue_dir: Path, output_dir: Path, queue_paths: dict, jobs: list, errors: list, iteration_count: int):
    failed_job_count = sum(1 for job in jobs if job["returncode"] != 0 or job.get("runner_verdict") != "ok_dream7b_bpu_batch_queue_runner")
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_bpu_batch_queue_service" if not errors else "failed_dream7b_bpu_batch_queue_service",
        "queue_dir": str(queue_dir),
        "output_dir": str(output_dir),
        "runner_command": args.runner_cmd,
        "max_batch_size": args.max_batch_size,
        "seq_len": args.seq_len,
        "top_k": args.top_k,
        "forward_command": args.forward_cmd,
        "drain_all": bool(args.drain_all),
        "bpu_lock_path": args.bpu_lock_path,
        "bpu_lock_timeout_sec": args.bpu_lock_timeout_sec,
        "poll_interval_sec": args.poll_interval_sec,
        "max_iterations": args.max_iterations,
        "once": bool(args.once),
        "iteration_count": iteration_count,
        "processed_job_count": len(jobs) - failed_job_count,
        "failed_job_count": failed_job_count,
        "queue_paths": {name: str(path) for name, path in queue_paths.items()},
        "jobs": jobs,
        "errors": errors,
    }


def main():
    args = parse_args()
    if args.max_batch_size <= 0:
        raise ValueError("--max-batch-size must be positive")
    if args.seq_len <= 0:
        raise ValueError("--seq-len must be positive")
    if args.poll_interval_sec < 0:
        raise ValueError("--poll-interval-sec must be non-negative")
    if args.max_iterations < 0:
        raise ValueError("--max-iterations must be non-negative")
    queue_dir = Path(args.queue_dir)
    output_dir = Path(args.output_dir)
    if not is_approved_path(queue_dir, APPROVED_QUEUE_PREFIXES):
        raise ValueError(f"Refusing queue path outside approved queue directories: {queue_dir}")
    if not is_approved_path(output_dir, APPROVED_OUTPUT_PREFIXES):
        raise ValueError(f"Refusing output path outside approved report directories: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    queue_paths = ensure_queue_dirs(queue_dir)
    jobs = []
    errors = []
    iteration_count = 0
    max_iterations = 1 if args.once else args.max_iterations
    while True:
        iteration_count += 1
        pending = next_pending_job(queue_paths["pending"])
        if pending is not None:
            processing = move_job(pending, queue_paths["processing"], ".jsonl")
            try:
                job = run_job(args, processing, output_dir, len(jobs))
                jobs.append(job)
                if job["returncode"] == 0 and job.get("runner_verdict") == "ok_dream7b_bpu_batch_queue_runner":
                    move_job(processing, queue_paths["done"], ".jsonl")
                else:
                    errors.append(f"job failed: {processing}: returncode={job['returncode']} runner_verdict={job.get('runner_verdict')}")
                    move_job(processing, queue_paths["failed"], ".jsonl")
            except Exception as exc:
                errors.append(f"job exception: {processing}: {exc}")
                if processing.exists():
                    move_job(processing, queue_paths["failed"], ".jsonl")
        payload = build_summary_payload(args, queue_dir, output_dir, queue_paths, jobs, errors, iteration_count)
        summary_md = write_summary(output_dir, payload)
        if max_iterations and iteration_count >= max_iterations:
            break
        if pending is None:
            time.sleep(args.poll_interval_sec)

    print(summary_md)
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
