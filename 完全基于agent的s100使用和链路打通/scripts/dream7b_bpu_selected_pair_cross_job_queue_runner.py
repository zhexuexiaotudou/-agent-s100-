#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import shlex
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

APPROVED_LOCK_PREFIXES = (
    "/tmp/",
    "/run/lock/",
    "/mnt/nas/openclaw/reports",
    "/mnt/nas/openclaw/reports/",
    "/root/.openclaw/workspace/reports",
    "/root/.openclaw/workspace/reports/",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Drain multiple Dream 7B queue jobs in one selected-pair resident worker session."
    )
    parser.add_argument("queue_dir", help="Queue directory with pending, processing, done, and failed subdirectories.")
    parser.add_argument("output_dir", help="Output directory for cross-job queue summary.")
    parser.add_argument("--model-report-root", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--forward-probe-cmd", default="dream7b-bpu-selected-pair-forward-path-probe")
    parser.add_argument("--max-job-count", type=int, default=6)
    parser.add_argument("--max-job-count-limit", type=int, default=12)
    parser.add_argument("--max-batch-size", type=int, default=16)
    parser.add_argument("--max-batch-size-limit", type=int, default=16)
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=3600)
    parser.add_argument("--bpu-lock-path", default="/run/lock/dream7b_bpu_batch_queue_runner.lock")
    parser.add_argument("--bpu-lock-timeout-sec", type=float, default=600.0)
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


def move_job(source: Path, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        target = target_dir / f"{source.stem}_{int(time.time() * 1000)}{source.suffix}"
    source.replace(target)
    return target


def acquire_lock(path: Path, timeout_sec: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.open("a+", encoding="utf-8")
    started = time.monotonic()
    while True:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            wait_ms = round((time.monotonic() - started) * 1000, 3)
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps({"acquired_at_epoch_ms": int(time.time() * 1000)}) + "\n")
            lock_file.flush()
            return lock_file, wait_ms
        except BlockingIOError:
            elapsed = time.monotonic() - started
            if elapsed >= timeout_sec:
                lock_file.close()
                raise TimeoutError(f"timed out waiting for BPU lock: {path}")
            time.sleep(min(0.25, max(0.0, timeout_sec - elapsed)))


def release_lock(lock_file):
    if lock_file is None:
        return
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    lock_file.close()


def read_job(path: Path, seq_len: int):
    rows = []
    request_ids = set()
    now_epoch_ms = int(time.time() * 1000)
    skipped = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        item = json.loads(raw)
        request_id = item.get("request_id")
        tokens = item.get("tokens")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError(f"{path}: line {line_number}: request_id must be a non-empty string")
        if request_id in request_ids:
            raise ValueError(f"{path}: line {line_number}: duplicate request_id: {request_id}")
        if not isinstance(tokens, list) or len(tokens) != seq_len:
            raise ValueError(f"{path}: line {line_number}: expected {seq_len} token ids")
        request_ids.add(request_id)
        if item.get("cancelled") is True:
            skipped.append({"request_id": request_id, "line_number": line_number, "reason": "cancelled"})
            continue
        not_after_epoch_ms = item.get("not_after_epoch_ms")
        if not_after_epoch_ms is not None and int(not_after_epoch_ms) < now_epoch_ms:
            skipped.append({"request_id": request_id, "line_number": line_number, "reason": "expired"})
            continue
        rows.append(
            {
                "request_id": request_id,
                "line_number": line_number,
                "tokens": [int(token) for token in tokens],
            }
        )
    if not rows:
        raise ValueError(f"{path}: no runnable requests")
    return rows, skipped


def latest_triplet_json(model_report_root: Path):
    paths = sorted(
        model_report_root.glob("dream7b_bpu_single_segment_triplet_residency_*/single_segment_triplet_residency_probe.json"),
        key=lambda item: item.stat().st_mtime,
    )
    if not paths:
        raise FileNotFoundError("missing dream7b_bpu_single_segment_triplet_residency report")
    return paths[-1]


def write_jsonl(path: Path, rows: list[dict]):
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")


def find_forward_json(stdout_text: str):
    for raw in reversed(stdout_text.splitlines()):
        line = raw.strip()
        if line.endswith("selected_pair_forward_path_probe.md"):
            return Path(line).with_suffix(".json")
    return None


def main():
    args = parse_args()
    if args.max_job_count_limit < 1 or args.max_job_count_limit > 32:
        raise ValueError("--max-job-count-limit must be from 1 to 32")
    if args.max_job_count < 1 or args.max_job_count > args.max_job_count_limit:
        raise ValueError(f"--max-job-count must be from 1 to {args.max_job_count_limit}")
    if args.max_batch_size_limit < 1 or args.max_batch_size_limit > 256:
        raise ValueError("--max-batch-size-limit must be from 1 to 256")
    if args.max_batch_size < 1 or args.max_batch_size > args.max_batch_size_limit:
        raise ValueError(f"--max-batch-size must be from 1 to {args.max_batch_size_limit}")
    if args.seq_len != 16:
        raise ValueError("--seq-len must remain 16 for the current Dream 7B HBM artifacts")
    if args.top_k < 0:
        raise ValueError("--top-k must be non-negative")
    queue_dir = Path(args.queue_dir)
    output_dir = Path(args.output_dir)
    model_report_root = Path(args.model_report_root)
    bpu_lock_path = Path(args.bpu_lock_path)
    if not is_approved(queue_dir, APPROVED_QUEUE_PREFIXES):
        raise ValueError(f"Refusing queue path outside approved queue directories: {queue_dir}")
    if not is_approved(output_dir, APPROVED_OUTPUT_PREFIXES):
        raise ValueError(f"Refusing output path outside approved report directories: {output_dir}")
    if not is_approved(model_report_root, APPROVED_OUTPUT_PREFIXES):
        raise ValueError(f"Refusing model report root outside approved report directories: {model_report_root}")
    if not is_approved(bpu_lock_path, APPROVED_LOCK_PREFIXES):
        raise ValueError(f"Refusing lock path outside approved lock directories: {bpu_lock_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    queue_paths = ensure_queue_dirs(queue_dir)
    warnings = []
    pending_jobs = sorted(path for path in queue_paths["pending"].glob("*.jsonl") if path.is_file())
    selected_pending_jobs = pending_jobs[: args.max_job_count]
    if len(selected_pending_jobs) < 1:
        raise ValueError(f"need at least 1 pending job for selected-pair queue execution, got {len(selected_pending_jobs)}")
    if len(selected_pending_jobs) == 1:
        warnings.append("single-job fallback path used; no cross-job load amortization available for this run")

    processing_jobs = [move_job(path, queue_paths["processing"]) for path in selected_pending_jobs]
    errors = []
    skipped_requests = []
    job_rows = []
    padded_forward_count = 0
    padding_request_count = 0
    try:
        for job_path in processing_jobs:
            rows, skipped = read_job(job_path, args.seq_len)
            if len(rows) > args.max_batch_size:
                raise ValueError(f"{job_path}: expected at most {args.max_batch_size} runnable requests, got {len(rows)}")
            job_rows.append({"job_path": job_path, "rows": rows})
            skipped_requests.extend(skipped)

        max_rows_per_job = max(len(job["rows"]) for job in job_rows)
        tokens_batches_by_job = []
        padded_forward_count = 0
        padding_request_count = 0
        for job in job_rows:
            tokens_batch = [row["tokens"] for row in job["rows"]]
            if len(tokens_batch) < max_rows_per_job:
                padding_request_count += max_rows_per_job - len(tokens_batch)
                pad_tokens = tokens_batch[-1]
                tokens_batch = tokens_batch + [pad_tokens for _ in range(max_rows_per_job - len(tokens_batch))]
            padded_forward_count += len(tokens_batch)
            tokens_batches_by_job.append(tokens_batch)
        if padding_request_count:
            warnings.append(f"padded {padding_request_count} internal forward rows to keep cross-job batch shapes aligned")
        tokens_batches_path = output_dir / "tokens_batches_by_job.json"
        tokens_batches_path.write_text(json.dumps(tokens_batches_by_job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        triplet_json = latest_triplet_json(model_report_root)
        forward_report_root = output_dir / "selected_pair_forward_reports"
        forward_report_root.mkdir(parents=True, exist_ok=True)

        lock_file = None
        lock_wait_ms = None
        started = time.monotonic()
        try:
            lock_file, lock_wait_ms = acquire_lock(bpu_lock_path, args.bpu_lock_timeout_sec)
            cmd = shlex.split(args.forward_probe_cmd) + [str(forward_report_root)]
            env = {
                "DREAM7B_BPU_SELECTED_PAIR_ONLY": "1",
                "DREAM7B_BPU_SELECTED_PAIR_TRIPLET_JSON": str(triplet_json),
                "DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT": str(len(job_rows)),
                "DREAM7B_BPU_SELECTED_PAIR_JOB_COUNT_LIMIT": str(args.max_job_count_limit),
                "DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT": str(args.max_batch_size),
                "DREAM7B_BPU_SELECTED_PAIR_BATCH_COUNT_LIMIT": str(args.max_batch_size_limit),
                "DREAM7B_BPU_SELECTED_PAIR_TOP_K": str(args.top_k),
                "DREAM7B_BPU_SELECTED_PAIR_TIMEOUT_SEC": str(args.timeout_sec),
                "DREAM7B_BPU_SELECTED_PAIR_TOKENS_BATCHES_BY_JOB_JSON": str(tokens_batches_path),
            }
            full_env = {**dict(os.environ), **env}
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=args.timeout_sec, env=full_env)
        finally:
            release_lock(lock_file)
        wall_ms = round((time.monotonic() - started) * 1000, 3)
        (output_dir / "selected_pair_forward.stdout").write_text(proc.stdout, encoding="utf-8")
        (output_dir / "selected_pair_forward.stderr").write_text(proc.stderr, encoding="utf-8")
        forward_json = find_forward_json(proc.stdout)
        if proc.returncode != 0:
            errors.append(f"selected-pair forward path returned {proc.returncode}")
        if forward_json is None or not forward_json.is_file():
            errors.append("could not locate selected-pair forward JSON from stdout")
            forward_payload = {}
            selected_summary = {}
        else:
            forward_payload = json.loads(forward_json.read_text(encoding="utf-8"))
            selected_summary_path = Path(forward_payload.get("selected_summary_json") or "")
            selected_summary = (
                json.loads(selected_summary_path.read_text(encoding="utf-8"))
                if selected_summary_path.is_file()
                else {}
            )
        if forward_payload.get("verdict") != "ok_dream7b_bpu_selected_pair_forward_path_probe":
            errors.append(f"unexpected forward verdict: {forward_payload.get('verdict')}")
        expected_processed_forward_count = padded_forward_count
        if selected_summary.get("processed_forward_count") != expected_processed_forward_count:
            errors.append(f"unexpected processed_forward_count: {selected_summary.get('processed_forward_count')}")

        results = []
        final_shapes_by_job = selected_summary.get("final_shapes_by_job") or []
        topk_by_job = selected_summary.get("topk_last_position_by_job") or []
        for job_index, job in enumerate(job_rows):
            final_shapes = final_shapes_by_job[job_index] if job_index < len(final_shapes_by_job) else []
            topk_rows = topk_by_job[job_index] if job_index < len(topk_by_job) else []
            for batch_index, row in enumerate(job["rows"]):
                results.append(
                    {
                        "request_id": row["request_id"],
                        "job_index": job_index,
                        "batch_index": batch_index,
                        "final_shape": final_shapes[batch_index] if batch_index < len(final_shapes) else None,
                        "topk_last_position": topk_rows[batch_index] if batch_index < len(topk_rows) else [],
                    }
                )
        for result in results:
            if result["final_shape"] != [1, args.seq_len, 152064]:
                errors.append(f"unexpected final_shape for {result['request_id']}: {result['final_shape']}")
        for job_path in processing_jobs:
            move_job(job_path, queue_paths["failed"] if errors else queue_paths["done"])
    except Exception as exc:
        errors.append(str(exc))
        for job_path in processing_jobs:
            if job_path.exists():
                move_job(job_path, queue_paths["failed"])
        wall_ms = 0.0
        lock_wait_ms = None
        env = {}
        cmd = []
        forward_json = None
        forward_payload = {}
        selected_summary = {}
        results = []

    durable_dir = output_dir / "durable_state"
    durable_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(durable_dir / "results.jsonl", results)
    write_jsonl(durable_dir / "skipped_requests.jsonl", skipped_requests)

    processed_count = len(results)
    selected_total_load_ms = float(selected_summary.get("selected_total_load_ms") or 0.0)
    run_ms = float(selected_summary.get("run_ms") or 0.0)
    selected_wall_ms = float(selected_summary.get("wall_ms") or 0.0)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_bpu_selected_pair_cross_job_queue_runner" if not errors else "failed_dream7b_bpu_selected_pair_cross_job_queue_runner",
        "queue_dir": str(queue_dir),
        "output_dir": str(output_dir),
        "model_report_root": str(model_report_root),
        "forward_probe_command": shlex.split(args.forward_probe_cmd),
        "selected_pair_forward_json": str(forward_json) if forward_json else None,
        "max_job_count": args.max_job_count,
        "max_batch_size": args.max_batch_size,
        "max_batch_size_limit": args.max_batch_size_limit,
        "processed_job_count": len(job_rows) if not errors else 0,
        "processed_request_count": processed_count,
        "padded_forward_count": padded_forward_count if not errors else 0,
        "padding_request_count": padding_request_count if not errors else 0,
        "failed_job_count": len(processing_jobs) if errors else 0,
        "bpu_lock": {"path": str(bpu_lock_path), "wait_ms": lock_wait_ms},
        "tokens_batches_by_job_json": str(output_dir / "tokens_batches_by_job.json"),
        "selected_pair": selected_summary.get("selected_pair"),
        "selected_segments": selected_summary.get("selected_segments"),
        "selected_pair_covers_all_segments": selected_summary.get("selected_pair_covers_all_segments"),
        "selected_worker_count": selected_summary.get("selected_worker_count"),
        "selected_resident_load_ms": selected_summary.get("selected_resident_load_ms"),
        "selected_total_load_ms": round(selected_total_load_ms, 3),
        "run_ms": round(run_ms, 3),
        "wall_ms": round(selected_wall_ms or wall_ms, 3),
        "load_to_run_ratio": round(selected_total_load_ms / run_ms, 6) if run_ms else None,
        "amortized_wall_ms_per_processed_request": round((selected_wall_ms or wall_ms) / processed_count, 3) if processed_count else None,
        "amortized_total_load_ms_per_processed_request": round(selected_total_load_ms / processed_count, 3) if processed_count else None,
        "amortized_run_ms_per_processed_request": round(run_ms / processed_count, 3) if processed_count else None,
        "durable_state": {
            "results_jsonl": str(durable_dir / "results.jsonl"),
            "skipped_requests_jsonl": str(durable_dir / "skipped_requests.jsonl"),
        },
        "results": results,
        "warnings": warnings,
        "errors": errors,
    }
    summary_json = output_dir / "cross_job_queue_summary.json"
    summary_md = output_dir / "cross_job_queue_summary.md"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B Selected-Pair Cross-Job Queue Runner",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- processed_job_count: {payload['processed_job_count']}",
        f"- processed_request_count: {payload['processed_request_count']}",
        f"- failed_job_count: {payload['failed_job_count']}",
        f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
        f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
        f"- selected_pair: {payload['selected_pair']}",
        f"- selected_segments: {payload['selected_segments']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_md)
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    main()
