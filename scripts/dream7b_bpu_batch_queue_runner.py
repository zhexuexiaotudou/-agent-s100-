#!/usr/bin/env python3
import argparse
import fcntl
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


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
    parser = argparse.ArgumentParser(description="Batch independent Dream 7B seq16 token requests through S100 BPU.")
    parser.add_argument("request_jsonl", help="JSONL queue. Each line must contain request_id and tokens.")
    parser.add_argument("output_dir", help="Output directory for queue summary and the BPU forward run.")
    parser.add_argument("--max-batch-size", type=int, default=4)
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--forward-cmd", default="dream7b-bpu-fine-batch-forward")
    parser.add_argument("--drain-all", action="store_true", help="Process all requests in multiple batches instead of deferring overflow.")
    parser.add_argument("--bpu-lock-path", default="/tmp/dream7b_bpu_batch_queue_runner.lock")
    parser.add_argument("--bpu-lock-timeout-sec", type=float, default=600.0)
    return parser.parse_args()


def is_approved_output_dir(path: Path) -> bool:
    text = str(path)
    return any(text == prefix.rstrip("/") or text.startswith(prefix) for prefix in APPROVED_OUTPUT_PREFIXES)


def is_approved_lock_path(path: Path) -> bool:
    text = str(path)
    return any(text == prefix.rstrip("/") or text.startswith(prefix) for prefix in APPROVED_LOCK_PREFIXES)


def acquire_bpu_lock(path: Path, timeout_sec: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.open("a+", encoding="utf-8")
    started = time.monotonic()
    while True:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            wait_ms = round((time.monotonic() - started) * 1000, 3)
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(json.dumps({"acquired_at_epoch_ms": int(time.time() * 1000)}, ensure_ascii=False) + "\n")
            lock_file.flush()
            return lock_file, wait_ms
        except BlockingIOError:
            elapsed = time.monotonic() - started
            if elapsed >= timeout_sec:
                lock_file.close()
                raise TimeoutError(f"timed out waiting for BPU lock: {path}")
            time.sleep(min(0.25, max(0.0, timeout_sec - elapsed)))


def release_bpu_lock(lock_file):
    if lock_file is None:
        return
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    lock_file.close()


def read_requests(path: Path, seq_len: int):
    rows = []
    request_ids = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(item, dict):
            raise ValueError(f"line {line_number}: request must be a JSON object")
        if "request_id" not in item:
            raise ValueError(f"line {line_number}: missing request_id")
        if "tokens" not in item:
            raise ValueError(f"line {line_number}: missing tokens")
        request_id = item["request_id"]
        tokens = item["tokens"]
        cancelled = item.get("cancelled", False)
        not_after_epoch_ms = item.get("not_after_epoch_ms", None)
        if not isinstance(request_id, str) or not request_id:
            raise ValueError(f"line {line_number}: request_id must be a non-empty string")
        if request_id in request_ids:
            raise ValueError(f"line {line_number}: duplicate request_id: {request_id}")
        if not isinstance(tokens, list):
            raise ValueError(f"line {line_number}: tokens must be a JSON list")
        if len(tokens) != seq_len:
            raise ValueError(f"line {line_number}: expected {seq_len} token ids, got {len(tokens)}")
        if not isinstance(cancelled, bool):
            raise ValueError(f"line {line_number}: cancelled must be a JSON boolean")
        if not_after_epoch_ms is not None and not isinstance(not_after_epoch_ms, int):
            raise ValueError(f"line {line_number}: not_after_epoch_ms must be an integer")
        request_ids.add(request_id)
        rows.append(
            {
                "request_id": request_id,
                "tokens": [int(token) for token in tokens],
                "cancelled": cancelled,
                "not_after_epoch_ms": not_after_epoch_ms,
                "line_number": line_number,
            }
        )
    if not rows:
        raise ValueError("request_jsonl contained no requests")
    return rows


def topk_by_batch(forward_summary: dict) -> dict[int, list]:
    indexed = {}
    for item in forward_summary.get("topk_last_position_by_batch", []):
        indexed[int(item["batch_index"])] = item.get("topk_last_position", [])
    return indexed


def split_runnable_requests(requests: list[dict], now_epoch_ms: int):
    runnable = []
    skipped = []
    for item in requests:
        if item.get("cancelled") is True:
            skipped.append(
                {
                    "request_id": item["request_id"],
                    "line_number": item["line_number"],
                    "reason": "cancelled",
                }
            )
            continue
        not_after_epoch_ms = item.get("not_after_epoch_ms")
        if not_after_epoch_ms is not None and not_after_epoch_ms < now_epoch_ms:
            skipped.append(
                {
                    "request_id": item["request_id"],
                    "line_number": item["line_number"],
                    "reason": "expired",
                    "not_after_epoch_ms": not_after_epoch_ms,
                    "now_epoch_ms": now_epoch_ms,
                }
            )
            continue
        runnable.append(item)
    return runnable, skipped


def write_jsonl(path: Path, rows: list[dict]):
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")


def run_forward_batch(args, output_dir: Path, accepted: list[dict], batch_run_index: int):
    batch_dir = output_dir / f"batch_{batch_run_index:03d}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    tokens_batch_json = batch_dir / "tokens_batch.json"
    tokens_batch_json.write_text(json.dumps([item["tokens"] for item in accepted], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    forward_dir = batch_dir / "forward"
    cmd = [
        args.forward_cmd,
        "--tokens-batch-json",
        str(tokens_batch_json),
        "--top-k",
        str(args.top_k),
        "--output-dir",
        str(forward_dir),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=240)
    (batch_dir / "forward.stdout").write_text(proc.stdout, encoding="utf-8")
    (batch_dir / "forward.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"forward command failed with exit code {proc.returncode}: {batch_dir / 'forward.stderr'}")

    forward_summary_path = forward_dir / "summary.json"
    forward_summary = json.loads(forward_summary_path.read_text(encoding="utf-8"))
    indexed_topk = topk_by_batch(forward_summary)
    final_shapes = forward_summary.get("final_shapes", [])
    results = []
    for batch_index, item in enumerate(accepted):
        final_shape = final_shapes[batch_index] if batch_index < len(final_shapes) else None
        results.append(
            {
                "request_id": item["request_id"],
                "line_number": item["line_number"],
                "batch_run_index": batch_run_index,
                "batch_index": batch_index,
                "global_batch_index": None,
                "final_shape": final_shape,
                "topk_last_position": indexed_topk.get(batch_index, []),
            }
        )

    return {
        "batch_run_index": batch_run_index,
        "request_ids": [item["request_id"] for item in accepted],
        "tokens_batch_json": str(tokens_batch_json),
        "forward_summary": str(forward_summary_path),
        "metrics": {
            "execution_mode": forward_summary.get("execution_mode"),
            "window_execution_mode": forward_summary.get("window_execution_mode"),
            "child_process_count": forward_summary.get("child_process_count"),
            "batch_count": forward_summary.get("batch_count"),
            "wall_ms": forward_summary.get("wall_ms"),
            "load_ms": forward_summary.get("load_ms"),
            "run_ms": forward_summary.get("run_ms"),
            "amortized_wall_ms_per_forward": forward_summary.get("amortized_wall_ms_per_forward"),
            "amortized_load_ms_per_forward": forward_summary.get("amortized_load_ms_per_forward"),
        },
        "forward_summary_payload": forward_summary,
        "results": results,
    }


def main():
    args = parse_args()
    if args.max_batch_size <= 0:
        raise ValueError("--max-batch-size must be positive")
    if args.seq_len <= 0:
        raise ValueError("--seq-len must be positive")
    if args.bpu_lock_timeout_sec < 0:
        raise ValueError("--bpu-lock-timeout-sec must be non-negative")
    request_jsonl = Path(args.request_jsonl)
    output_dir = Path(args.output_dir)
    bpu_lock_path = Path(args.bpu_lock_path)
    if not request_jsonl.is_file():
        raise FileNotFoundError(request_jsonl)
    if not is_approved_output_dir(output_dir):
        raise ValueError(f"Refusing output path outside approved report directories: {output_dir}")
    if not is_approved_lock_path(bpu_lock_path):
        raise ValueError(f"Refusing lock path outside approved lock directories: {bpu_lock_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    requests = read_requests(request_jsonl, args.seq_len)
    now_epoch_ms = int(time.time() * 1000)
    runnable_requests, skipped_requests = split_runnable_requests(requests, now_epoch_ms)
    if args.drain_all:
        request_batches = [runnable_requests[index:index + args.max_batch_size] for index in range(0, len(runnable_requests), args.max_batch_size)]
        deferred = []
    else:
        request_batches = [runnable_requests[: args.max_batch_size]]
        deferred = runnable_requests[args.max_batch_size :]
    batch_runs = []
    results = []
    lock_file = None
    lock_wait_ms = None
    lock_acquired = False
    try:
        if any(request_batches):
            lock_file, lock_wait_ms = acquire_bpu_lock(bpu_lock_path, args.bpu_lock_timeout_sec)
            lock_acquired = True
        for batch_run_index, accepted in enumerate(request_batches):
            if not accepted:
                continue
            batch_run = run_forward_batch(args, output_dir, accepted, batch_run_index)
            batch_runs.append(batch_run)
            results.extend(batch_run["results"])
    finally:
        release_bpu_lock(lock_file)

    for global_batch_index, result in enumerate(results):
        result["global_batch_index"] = global_batch_index

    errors = []
    for batch_run in batch_runs:
        forward_summary = batch_run["forward_summary_payload"]
        metrics = batch_run["metrics"]
        if forward_summary.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
            errors.append(f"unexpected forward verdict in batch {batch_run['batch_run_index']}: {forward_summary.get('verdict')}")
        if metrics.get("execution_mode") != "pair_window_batch":
            errors.append(f"unexpected execution_mode in batch {batch_run['batch_run_index']}: {metrics.get('execution_mode')}")
        if metrics.get("batch_count") != len(batch_run["request_ids"]):
            errors.append(f"unexpected batch_count in batch {batch_run['batch_run_index']}: {metrics.get('batch_count')}")
    for result in results:
        if result["final_shape"] != [1, args.seq_len, 152064]:
            errors.append(f"unexpected final_shape for {result['request_id']}: {result['final_shape']}")
    compact_batch_runs = []
    for batch_run in batch_runs:
        compact_batch_runs.append(
            {
                "batch_run_index": batch_run["batch_run_index"],
                "request_ids": batch_run["request_ids"],
                "tokens_batch_json": batch_run["tokens_batch_json"],
                "forward_summary": batch_run["forward_summary"],
                "metrics": batch_run["metrics"],
            }
        )
    total_wall_ms = round(sum(float(item["metrics"].get("wall_ms") or 0.0) for item in batch_runs), 3)
    total_load_ms = round(sum(float(item["metrics"].get("load_ms") or 0.0) for item in batch_runs), 3)
    total_run_ms = round(sum(float(item["metrics"].get("run_ms") or 0.0) for item in batch_runs), 3)
    processed_count = len(results)
    durable_dir = output_dir / "durable_state"
    durable_dir.mkdir(parents=True, exist_ok=True)
    accepted_rows = [
        {
            "request_id": result["request_id"],
            "batch_run_index": result["batch_run_index"],
            "batch_index": result["batch_index"],
            "global_batch_index": result["global_batch_index"],
        }
        for result in results
    ]
    deferred_rows = [
        {
            "request_id": item["request_id"],
            "line_number": item["line_number"],
            "reason": "deferred",
        }
        for item in deferred
    ]
    result_rows = [
        {
            "request_id": result["request_id"],
            "batch_run_index": result["batch_run_index"],
            "batch_index": result["batch_index"],
            "global_batch_index": result["global_batch_index"],
            "final_shape": result["final_shape"],
            "topk_last_position": result["topk_last_position"],
        }
        for result in results
    ]
    write_jsonl(durable_dir / "accepted_requests.jsonl", accepted_rows)
    write_jsonl(durable_dir / "deferred_requests.jsonl", deferred_rows)
    write_jsonl(durable_dir / "skipped_requests.jsonl", skipped_requests)
    write_jsonl(durable_dir / "results.jsonl", result_rows)

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_bpu_batch_queue_runner" if not errors else "failed_dream7b_bpu_batch_queue_runner",
        "request_jsonl": str(request_jsonl),
        "output_dir": str(output_dir),
        "forward_command": args.forward_cmd,
        "drain_all": bool(args.drain_all),
        "max_batch_size": args.max_batch_size,
        "bpu_lock": {
            "path": str(bpu_lock_path),
            "timeout_sec": args.bpu_lock_timeout_sec,
            "acquired": lock_acquired,
            "wait_ms": lock_wait_ms,
        },
        "request_count": len(requests),
        "runnable_count": len(runnable_requests),
        "processed_count": processed_count,
        "accepted_count": processed_count,
        "deferred_count": len(deferred),
        "deferred_request_ids": [item["request_id"] for item in deferred],
        "skipped_count": len(skipped_requests),
        "skipped_requests": skipped_requests,
        "batch_run_count": len(compact_batch_runs),
        "batch_runs": compact_batch_runs,
        "durable_state": {
            "accepted_requests_jsonl": str(durable_dir / "accepted_requests.jsonl"),
            "deferred_requests_jsonl": str(durable_dir / "deferred_requests.jsonl"),
            "skipped_requests_jsonl": str(durable_dir / "skipped_requests.jsonl"),
            "results_jsonl": str(durable_dir / "results.jsonl"),
        },
        "results": results,
        "forward_metrics": {
            "total_wall_ms": total_wall_ms,
            "total_load_ms": total_load_ms,
            "total_run_ms": total_run_ms,
            "amortized_wall_ms_per_processed_request": round(total_wall_ms / processed_count, 3) if processed_count else 0.0,
        },
        "errors": errors,
    }
    summary_json = output_dir / "queue_summary.json"
    summary_md = output_dir / "queue_summary.md"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B BPU Batch Queue Runner",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- request_jsonl: {payload['request_jsonl']}",
        f"- forward_command: {payload['forward_command']}",
        f"- drain_all: {payload['drain_all']}",
        f"- max_batch_size: {payload['max_batch_size']}",
        f"- bpu_lock_path: {payload['bpu_lock']['path']}",
        f"- bpu_lock_acquired: {payload['bpu_lock']['acquired']}",
        f"- bpu_lock_wait_ms: {payload['bpu_lock']['wait_ms']}",
        f"- request_count: {payload['request_count']}",
        f"- runnable_count: {payload['runnable_count']}",
        f"- processed_count: {payload['processed_count']}",
        f"- accepted_count: {payload['accepted_count']}",
        f"- deferred_count: {payload['deferred_count']}",
        f"- skipped_count: {payload['skipped_count']}",
        f"- batch_run_count: {payload['batch_run_count']}",
        f"- total_wall_ms: {payload['forward_metrics']['total_wall_ms']}",
        f"- amortized_wall_ms_per_processed_request: {payload['forward_metrics']['amortized_wall_ms_per_processed_request']}",
        "",
        "## Batch Runs",
        "",
        "| batch_run_index | request_ids | forward_summary | wall_ms |",
        "| ---: | --- | --- | ---: |",
    ]
    for batch_run in compact_batch_runs:
        lines.append(
            f"| {batch_run['batch_run_index']} | {batch_run['request_ids']} | {batch_run['forward_summary']} | {batch_run['metrics'].get('wall_ms')} |"
        )
    lines.extend([
        "",
        "## Results",
        "",
        "| request_id | batch_run_index | batch_index | global_batch_index | final_shape |",
        "| --- | ---: | ---: | ---: | --- |",
    ])
    for result in results:
        lines.append(
            f"| {result['request_id']} | {result['batch_run_index']} | {result['batch_index']} | {result['global_batch_index']} | {result['final_shape']} |"
        )
    lines.extend(["", "## Deferred", ""])
    if deferred:
        lines.extend(f"- {item['request_id']}" for item in deferred)
    else:
        lines.append("- none")
    lines.extend(["", "## Skipped", ""])
    if skipped_requests:
        lines.extend(f"- {item['request_id']}: {item['reason']}" for item in skipped_requests)
    else:
        lines.append("- none")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_md)
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
