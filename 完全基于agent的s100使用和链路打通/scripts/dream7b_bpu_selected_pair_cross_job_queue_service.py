#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


APPROVED_QUEUE_PREFIXES = (
    "/tmp/",
    "/mnt/nas/openclaw/queues",
    "/mnt/nas/openclaw/queues/",
    "/root/.openclaw/workspace/queues",
    "/root/.openclaw/workspace/queues/",
)

APPROVED_OUTPUT_PREFIXES = (
    "/tmp/",
    "/mnt/nas/openclaw/reports",
    "/mnt/nas/openclaw/reports/",
    "/root/.openclaw/workspace/reports",
    "/root/.openclaw/workspace/reports/",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Service loop for Dream 7B selected-pair cross-job queue candidate.")
    parser.add_argument("queue_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--runner-cmd", default="python3 scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py")
    parser.add_argument("--forward-probe-cmd", default="bash scripts/probes/dream7b_bpu_selected_pair_forward_path_probe.sh")
    parser.add_argument("--expected-runner-verdict", default="ok_dream7b_bpu_selected_pair_cross_job_queue_runner")
    parser.add_argument("--summary-stem", default="cross_job_queue")
    parser.add_argument("--min-job-count", type=int, default=2)
    parser.add_argument("--max-job-count", type=int, default=6)
    parser.add_argument("--max-job-count-limit", type=int, default=12)
    parser.add_argument("--max-batch-size", type=int, default=16)
    parser.add_argument("--max-batch-size-limit", type=int, default=16)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=3600)
    parser.add_argument("--bpu-lock-path", default="/run/lock/dream7b_bpu_batch_queue_runner.lock")
    parser.add_argument("--poll-interval-sec", type=float, default=1.0)
    parser.add_argument("--single-job-flush-timeout-sec", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def is_approved(path: Path, prefixes: tuple[str, ...]) -> bool:
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


def pending_count(pending_dir: Path):
    return len([path for path in pending_dir.glob("*.jsonl") if path.is_file()])


def pending_jobs(pending_dir: Path):
    return sorted(path for path in pending_dir.glob("*.jsonl") if path.is_file())


def oldest_pending_age_sec(jobs: list[Path]):
    if not jobs:
        return None
    oldest_mtime = min(path.stat().st_mtime for path in jobs)
    return max(0.0, time.time() - oldest_mtime)


def write_summary(output_dir: Path, payload: dict):
    summary_json = output_dir / "cross_job_queue_service_summary.json"
    summary_md = output_dir / "cross_job_queue_service_summary.md"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B Selected-Pair Cross-Job Queue Service",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- queue_dir: {payload['queue_dir']}",
        f"- output_dir: {payload['output_dir']}",
        f"- processed_run_count: {payload['processed_run_count']}",
        f"- failed_run_count: {payload['failed_run_count']}",
        f"- last_runner_summary_json: {payload.get('last_runner_summary_json')}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["errors"]) if payload["errors"] else lines.append("- none")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_md


def build_payload(args, queue_dir: Path, output_dir: Path, queue_paths: dict, runs: list[dict], errors: list):
    failed_run_count = sum(
        1 for item in runs if item.get("returncode") != 0 or item.get("runner_verdict") != args.expected_runner_verdict
    )
    last_summary = runs[-1].get("runner_summary_json") if runs else None
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_bpu_selected_pair_cross_job_queue_service" if not errors else "failed_dream7b_bpu_selected_pair_cross_job_queue_service",
        "queue_dir": str(queue_dir),
        "output_dir": str(output_dir),
        "queue_paths": {name: str(path) for name, path in queue_paths.items()},
        "runner_command": args.runner_cmd,
        "forward_probe_command": args.forward_probe_cmd,
        "expected_runner_verdict": args.expected_runner_verdict,
        "summary_stem": args.summary_stem,
        "min_job_count": args.min_job_count,
        "max_job_count": args.max_job_count,
        "max_job_count_limit": args.max_job_count_limit,
        "max_batch_size": args.max_batch_size,
        "max_batch_size_limit": args.max_batch_size_limit,
        "top_k": args.top_k,
        "timeout_sec": args.timeout_sec,
        "bpu_lock_path": args.bpu_lock_path,
        "poll_interval_sec": args.poll_interval_sec,
        "single_job_flush_timeout_sec": args.single_job_flush_timeout_sec,
        "once": bool(args.once),
        "processed_run_count": len(runs) - failed_run_count,
        "failed_run_count": failed_run_count,
        "last_runner_summary_json": last_summary,
        "runs": runs,
        "errors": errors,
    }


def main():
    args = parse_args()
    if args.min_job_count < 2:
        raise ValueError("--min-job-count must be at least 2")
    if args.max_job_count_limit < 1 or args.max_job_count_limit > 32:
        raise ValueError("--max-job-count-limit must be from 1 to 32")
    if args.max_job_count < args.min_job_count or args.max_job_count > args.max_job_count_limit:
        raise ValueError(f"--max-job-count must be between --min-job-count and {args.max_job_count_limit}")
    if args.max_batch_size_limit < 1 or args.max_batch_size_limit > 256:
        raise ValueError("--max-batch-size-limit must be from 1 to 256")
    if args.max_batch_size < 1 or args.max_batch_size > args.max_batch_size_limit:
        raise ValueError(f"--max-batch-size must be from 1 to {args.max_batch_size_limit}")
    if args.poll_interval_sec < 0:
        raise ValueError("--poll-interval-sec must be non-negative")
    if args.single_job_flush_timeout_sec < 0:
        raise ValueError("--single-job-flush-timeout-sec must be non-negative")

    queue_dir = Path(args.queue_dir)
    output_dir = Path(args.output_dir)
    if not is_approved(queue_dir, APPROVED_QUEUE_PREFIXES):
        raise ValueError(f"Refusing queue path outside approved queue directories: {queue_dir}")
    if not is_approved(output_dir, APPROVED_OUTPUT_PREFIXES):
        raise ValueError(f"Refusing output path outside approved report directories: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    queue_paths = ensure_queue_dirs(queue_dir)
    runs = []
    errors = []
    while True:
        current_pending_jobs = pending_jobs(queue_paths["pending"])
        current_pending_count = len(current_pending_jobs)
        oldest_age_sec = oldest_pending_age_sec(current_pending_jobs)
        run_reason = None
        run_job_count = None
        if current_pending_count >= args.min_job_count:
            run_reason = "min_job_count_reached"
            run_job_count = args.max_job_count
        elif (
            0 < current_pending_count < args.min_job_count
            and oldest_age_sec is not None
            and oldest_age_sec >= args.single_job_flush_timeout_sec
        ):
            run_reason = "partial_batch_flush_timeout"
            run_job_count = current_pending_count
        if run_reason is not None and run_job_count is not None:
            run_dir = output_dir / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
            run_dir.mkdir(parents=True, exist_ok=True)
            cmd = args.runner_cmd.split() + [
                str(queue_dir),
                str(run_dir),
                "--max-job-count",
                str(run_job_count),
                "--max-job-count-limit",
                str(args.max_job_count_limit),
                "--max-batch-size",
                str(args.max_batch_size),
                "--max-batch-size-limit",
                str(args.max_batch_size_limit),
                "--top-k",
                str(args.top_k),
                "--timeout-sec",
                str(args.timeout_sec),
                "--bpu-lock-path",
                args.bpu_lock_path,
                "--forward-probe-cmd",
                args.forward_probe_cmd,
            ]
            started = time.monotonic()
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=args.timeout_sec + 60)
            wall_ms = round((time.monotonic() - started) * 1000, 3)
            (run_dir / "runner.stdout").write_text(proc.stdout, encoding="utf-8")
            (run_dir / "runner.stderr").write_text(proc.stderr, encoding="utf-8")
            summary_path = run_dir / f"{args.summary_stem}_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
            row = {
                "run_index": len(runs),
                "run_dir": str(run_dir),
                "returncode": proc.returncode,
                "wall_ms": wall_ms,
                "runner_summary_json": str(summary_path) if summary_path.is_file() else None,
                "runner_verdict": summary.get("verdict"),
                "run_reason": run_reason,
                "pending_count_at_start": current_pending_count,
                "oldest_pending_age_sec": round(oldest_age_sec, 3) if oldest_age_sec is not None else None,
                "effective_max_job_count": run_job_count,
                "processed_request_count": summary.get("processed_request_count"),
                "load_to_run_ratio": summary.get("load_to_run_ratio"),
                "amortized_wall_ms_per_processed_request": summary.get("amortized_wall_ms_per_processed_request"),
            }
            runs.append(row)
            if row["returncode"] != 0 or row["runner_verdict"] != args.expected_runner_verdict:
                errors.append(f"runner failed: {row}")
        payload = build_payload(args, queue_dir, output_dir, queue_paths, runs, errors)
        summary_md = write_summary(output_dir, payload)
        if args.once:
            break
        time.sleep(args.poll_interval_sec)
    print(summary_md)
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    main()
