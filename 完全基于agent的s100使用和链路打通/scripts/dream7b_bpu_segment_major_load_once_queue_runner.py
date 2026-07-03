#!/usr/bin/env python3
import argparse
import fcntl
import gc
import json
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from hbm_runtime import HB_HBMRuntime


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
    parser = argparse.ArgumentParser(description="Dream 7B segment-major load-once queue runner.")
    parser.add_argument("queue_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--base-hbm-dir", default="/home/sunrise/.cache/openclaw/dream7b-hbm/segments6")
    parser.add_argument("--fine-hbm-dir", default="/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16")
    parser.add_argument("--max-job-count", type=int, default=12)
    parser.add_argument("--max-job-count-limit", type=int, default=12)
    parser.add_argument("--max-batch-size", type=int, default=192)
    parser.add_argument("--max-batch-size-limit", type=int, default=256)
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--bpu-lock-path", default="/run/lock/dream7b_bpu_batch_queue_runner.lock")
    parser.add_argument("--bpu-lock-timeout-sec", type=float, default=600.0)
    parser.add_argument("--forward-probe-cmd", default="", help="Accepted for queue-service compatibility; ignored.")
    return parser.parse_args()


def is_approved(path: Path, prefixes: tuple[str, ...]) -> bool:
    text = str(path)
    return any(text == prefix.rstrip("/") or text.startswith(prefix) for prefix in prefixes)


def validate_hbm_dir(path: Path, kind: str):
    allowed = {
        "base": {
            "/mnt/nas/openclaw/models/dream7b-hbm/segments6",
            "/home/sunrise/.cache/openclaw/dream7b-hbm/segments6",
        },
        "fine": {
            "/mnt/nas/openclaw/models/dream7b-hbm/fine-seq16",
            "/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16",
        },
    }[kind]
    text = str(path).rstrip("/")
    if text not in allowed:
        raise ValueError(f"Refusing {kind} HBM path outside approved Dream 7B HBM directories: {path}")


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


def write_jsonl(path: Path, rows: list[dict]):
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")


def add_timing(bucket: dict[str, float], key: str, started: float):
    bucket[key] = bucket.get(key, 0.0) + ((time.perf_counter() - started) * 1000)


def first_scale(runtime, model_name, output_name):
    quant = runtime.output_quants[model_name][output_name]
    scale = np.asarray(quant.scale).reshape(-1)
    if scale.size == 0:
        return 1.0
    return float(scale[0])


def run_loaded_segment(runtime, model_file, model_name, position_ids, input_array):
    inputs = {"_input_0": input_array, "_input_1": position_ids}
    t0 = time.perf_counter()
    output = runtime.run(inputs, model_name=model_name)
    t1 = time.perf_counter()
    output_name = runtime.output_names[model_name][0]
    arr = output[model_name][output_name]
    scale = first_scale(runtime, model_name, output_name)
    dequantized = arr.astype(np.float32) * scale
    result = {
        "model_name": model_name,
        "model_file": str(model_file),
        "output_name": output_name,
        "output_shape": list(arr.shape),
        "output_dtype": str(arr.dtype),
        "output_scale": scale,
        "run_ms": round((t1 - t0) * 1000, 3),
    }
    del output, arr
    return dequantized, result


def run_loaded_segment_raw(runtime, model_file, model_name, position_ids, input_array):
    inputs = {"_input_0": input_array, "_input_1": position_ids}
    t0 = time.perf_counter()
    output = runtime.run(inputs, model_name=model_name)
    t1 = time.perf_counter()
    output_name = runtime.output_names[model_name][0]
    arr = output[model_name][output_name]
    scale = first_scale(runtime, model_name, output_name)
    result = {
        "model_name": model_name,
        "model_file": str(model_file),
        "output_name": output_name,
        "output_shape": list(arr.shape),
        "output_dtype": str(arr.dtype),
        "output_scale": scale,
        "run_ms": round((t1 - t0) * 1000, 3),
        "raw_final_output": True,
    }
    del output
    return arr, result


def topk_raw_mutating(last, top_k: int, scale: float):
    if top_k <= 0:
        return []
    selected = []
    if np.issubdtype(last.dtype, np.integer):
        fill_value = np.iinfo(last.dtype).min
    else:
        fill_value = -np.inf
    for _ in range(min(top_k, int(last.shape[0]))):
        index = int(np.argmax(last))
        value = last[index].item()
        selected.append({"token_id": index, "score": float(value) * scale})
        last[index] = fill_value
    return selected


def segment_specs(base_hbm_dir: Path, fine_hbm_dir: Path):
    return [
        ("seg00_02", "fine", fine_hbm_dir / "seg00_02/dream7b_segment_0_2_seq16_q8.hbm", "dream_segment_00_02"),
        ("seg02_04", "fine", fine_hbm_dir / "seg02_04/dream7b_segment_2_4_seq16_q8.hbm", "dream_segment_02_04"),
        ("seg04_07", "base", base_hbm_dir / "dream7b_segment_4_7_seq16_q8.hbm", "dream_segment_04_07"),
        ("seg07_10", "fine", fine_hbm_dir / "seg07_10/dream7b_segment_7_10_seq16_q8.hbm", "dream_segment_07_10"),
        ("seg10_14", "fine", fine_hbm_dir / "seg10_14/dream7b_segment_10_14_seq16_q8.hbm", "dream_segment_10_14"),
        ("seg14_17", "fine", fine_hbm_dir / "seg14_17/dream7b_segment_14_17_seq16_q8.hbm", "dream_segment_14_17"),
        ("seg17_21", "fine", fine_hbm_dir / "seg17_21/dream7b_segment_17_21_seq16_q8.hbm", "dream_segment_17_21"),
        ("seg21_24", "base", base_hbm_dir / "dream7b_segment_21_24_seq16_q8.hbm", "dream_segment_21_24"),
        ("seg24_26", "fine", fine_hbm_dir / "seg24_26/dream7b_segment_24_26_seq16_q8.hbm", "dream_segment_24_26"),
        ("seg26_28", "fine", fine_hbm_dir / "seg26_28/dream7b_segment_26_28_seq16_q8.hbm", "dream_segment_26_28"),
    ]


def main():
    args = parse_args()
    if args.max_job_count_limit < 1 or args.max_job_count_limit > 24:
        raise ValueError("--max-job-count-limit must be from 1 to 24")
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
    base_hbm_dir = Path(args.base_hbm_dir)
    fine_hbm_dir = Path(args.fine_hbm_dir)
    bpu_lock_path = Path(args.bpu_lock_path)
    if not is_approved(queue_dir, APPROVED_QUEUE_PREFIXES):
        raise ValueError(f"Refusing queue path outside approved queue directories: {queue_dir}")
    if not is_approved(output_dir, APPROVED_OUTPUT_PREFIXES):
        raise ValueError(f"Refusing output path outside approved report directories: {output_dir}")
    validate_hbm_dir(base_hbm_dir, "base")
    validate_hbm_dir(fine_hbm_dir, "fine")
    if not is_approved(bpu_lock_path, APPROVED_LOCK_PREFIXES):
        raise ValueError(f"Refusing lock path outside approved lock directories: {bpu_lock_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    queue_paths = ensure_queue_dirs(queue_dir)
    warnings = []
    errors = []
    skipped_requests = []
    results = []
    segment_results = []
    final_shape_counts = {}
    topk_sample = []
    phase_timing_enabled = os.environ.get("DREAM7B_BPU_SEGMENT_MAJOR_PHASE_TIMING", "") == "1"
    raw_final_enabled = os.environ.get("DREAM7B_BPU_SEGMENT_MAJOR_RAW_FINAL", "") == "1"
    skip_explicit_gc = os.environ.get("DREAM7B_BPU_SEGMENT_MAJOR_SKIP_EXPLICIT_GC", "") == "1"
    phase_timing_totals: dict[str, float] = {}
    lock_file = None
    lock_wait_ms = None
    total_load_ms = 0.0
    total_run_ms = 0.0
    wall_ms = 0.0
    peak_live_bytes = 0
    processed_count = 0
    job_rows = []
    processing_jobs = []
    deadline = time.monotonic() + args.timeout_sec

    def check_deadline():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"segment-major queue runner timed out after {args.timeout_sec} seconds")

    try:
        pending_jobs = sorted(path for path in queue_paths["pending"].glob("*.jsonl") if path.is_file())
        selected_pending_jobs = pending_jobs[: args.max_job_count]
        if not selected_pending_jobs:
            raise ValueError("need at least 1 pending job")
        if len(selected_pending_jobs) == 1:
            warnings.append("single-job fallback path used; segment-major load amortization is limited")
        processing_jobs = [move_job(path, queue_paths["processing"]) for path in selected_pending_jobs]
        for job_index, job_path in enumerate(processing_jobs):
            rows, skipped = read_job(job_path, args.seq_len)
            if len(rows) > args.max_batch_size:
                raise ValueError(f"{job_path}: expected at most {args.max_batch_size} runnable requests, got {len(rows)}")
            skipped_requests.extend(skipped)
            job_rows.append({"job_path": job_path, "rows": rows})

        records = []
        for job_index, job in enumerate(job_rows):
            for batch_index, row in enumerate(job["rows"]):
                records.append(
                    {
                        "request_id": row["request_id"],
                        "job_index": job_index,
                        "batch_index": batch_index,
                        "state": np.asarray(row["tokens"], dtype=np.int32).reshape(1, args.seq_len),
                    }
                )
        processed_count = len(records)
        if not records:
            raise ValueError("no runnable requests after filtering")

        specs = segment_specs(base_hbm_dir, fine_hbm_dir)
        missing = [str(item[2]) for item in specs if not item[2].exists()]
        if missing:
            raise FileNotFoundError("missing HBM files: " + ", ".join(missing))

        started = time.monotonic()
        lock_file, lock_wait_ms = acquire_lock(bpu_lock_path, args.bpu_lock_timeout_sec)
        position_ids = np.arange(args.seq_len, dtype=np.int32)
        vocab_size = 152064
        for segment_index, (segment_id, source, model_file, model_name) in enumerate(specs):
            check_deadline()
            segment_phase_timing: dict[str, float] = {}
            load_start = time.perf_counter()
            runtime = HB_HBMRuntime(str(model_file))
            load_end = time.perf_counter()
            load_ms = round((load_end - load_start) * 1000, 3)
            total_load_ms += load_ms
            segment_run_ms = 0.0
            segment_started = time.perf_counter()
            try:
                for record in records:
                    check_deadline()
                    call_started = time.perf_counter()
                    if raw_final_enabled and segment_index == len(specs) - 1:
                        output, result = run_loaded_segment_raw(runtime, model_file, model_name, position_ids, record["state"])
                    else:
                        output, result = run_loaded_segment(runtime, model_file, model_name, position_ids, record["state"])
                    if phase_timing_enabled:
                        add_timing(segment_phase_timing, "run_loaded_segment_call_ms", call_started)
                    segment_run_ms += float(result["run_ms"])
                    total_run_ms += float(result["run_ms"])
                    if segment_index == len(specs) - 1:
                        final_started = time.perf_counter()
                        shape = list(output.shape)
                        if phase_timing_enabled:
                            add_timing(segment_phase_timing, "final_shape_ms", final_started)
                        shape_count_started = time.perf_counter()
                        final_shape_counts[str(shape)] = final_shape_counts.get(str(shape), 0) + 1
                        if phase_timing_enabled:
                            add_timing(segment_phase_timing, "final_shape_count_ms", shape_count_started)
                        topk = []
                        shape_check_started = time.perf_counter()
                        if shape != [1, args.seq_len, vocab_size]:
                            errors.append(f"unexpected final shape for {record['request_id']}: {shape}")
                        if phase_timing_enabled:
                            add_timing(segment_phase_timing, "final_shape_check_ms", shape_check_started)
                        if args.top_k > 0:
                            topk_started = time.perf_counter()
                            last = output[0, -1]
                            scale = float(result.get("output_scale") or 1.0)
                            if raw_final_enabled:
                                topk = topk_raw_mutating(last, args.top_k, scale)
                            else:
                                k = min(args.top_k, int(last.shape[0]))
                                indices = np.argpartition(last, -k)[-k:]
                                indices = indices[np.argsort(last[indices])[::-1]]
                                topk = [{"token_id": int(idx), "score": float(last[idx])} for idx in indices]
                            if phase_timing_enabled:
                                add_timing(segment_phase_timing, "topk_ms", topk_started)
                            if len(topk_sample) < 8:
                                topk_sample_started = time.perf_counter()
                                topk_sample.append(
                                    {
                                        "request_id": record["request_id"],
                                        "job_index": record["job_index"],
                                        "batch_index": record["batch_index"],
                                        "topk_last_position": topk,
                                    }
                                )
                                if phase_timing_enabled:
                                    add_timing(segment_phase_timing, "topk_sample_append_ms", topk_sample_started)
                        results_started = time.perf_counter()
                        results.append(
                            {
                                "request_id": record["request_id"],
                                "job_index": record["job_index"],
                                "batch_index": record["batch_index"],
                                "final_shape": shape,
                                "topk_last_position": topk,
                            }
                        )
                        if phase_timing_enabled:
                            add_timing(segment_phase_timing, "results_append_ms", results_started)
                        clear_started = time.perf_counter()
                        record["state"] = None
                        del output
                        if phase_timing_enabled:
                            add_timing(segment_phase_timing, "final_state_clear_ms", clear_started)
                    else:
                        assign_started = time.perf_counter()
                        record["state"] = output
                        if phase_timing_enabled:
                            add_timing(segment_phase_timing, "state_assign_ms", assign_started)
                    segment_result_started = time.perf_counter()
                    segment_results.append(
                        {
                            "segment_index": segment_index,
                            "segment": segment_id,
                            "source": source,
                            "job_index": record["job_index"],
                            "batch_index": record["batch_index"],
                            "load_ms": load_ms if record["job_index"] == 0 and record["batch_index"] == 0 else 0.0,
                            "run_ms": result["run_ms"],
                            "output_shape": result["output_shape"],
                        }
                    )
                    if phase_timing_enabled:
                        add_timing(segment_phase_timing, "segment_results_append_ms", segment_result_started)
                live_started = time.perf_counter()
                live_bytes = sum(
                    int(record["state"].nbytes)
                    for record in records
                    if isinstance(record.get("state"), np.ndarray)
                )
                peak_live_bytes = max(peak_live_bytes, live_bytes)
                if phase_timing_enabled:
                    add_timing(segment_phase_timing, "live_bytes_scan_ms", live_started)
            finally:
                del runtime
                if skip_explicit_gc:
                    if phase_timing_enabled:
                        segment_phase_timing["gc_collect_skipped_count"] = segment_phase_timing.get("gc_collect_skipped_count", 0.0) + 1.0
                else:
                    gc_started = time.perf_counter()
                    gc.collect()
                    if phase_timing_enabled:
                        add_timing(segment_phase_timing, "gc_collect_ms", gc_started)
            if phase_timing_enabled:
                segment_phase_timing = {key: round(value, 3) for key, value in sorted(segment_phase_timing.items())}
                for key, value in segment_phase_timing.items():
                    phase_timing_totals[key] = phase_timing_totals.get(key, 0.0) + value
            progress = {
                "segment_index": segment_index,
                "segment": segment_id,
                "load_ms": load_ms,
                "segment_run_ms": round(segment_run_ms, 3),
                "segment_wall_ms": round((time.perf_counter() - segment_started) * 1000, 3),
                "processed_forward_count": processed_count,
                "peak_live_bytes": peak_live_bytes,
            }
            if phase_timing_enabled:
                progress["phase_timing_ms"] = segment_phase_timing
            (output_dir / f"segment_{segment_index:02d}_progress.json").write_text(
                json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        wall_ms = round((time.monotonic() - started) * 1000, 3)
        for job_path in processing_jobs:
            move_job(job_path, queue_paths["failed"] if errors else queue_paths["done"])
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        for job_path in processing_jobs:
            if job_path.exists():
                move_job(job_path, queue_paths["failed"])
    finally:
        release_lock(lock_file)

    durable_dir = output_dir / "durable_state"
    durable_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(durable_dir / "results.jsonl", results)
    write_jsonl(durable_dir / "skipped_requests.jsonl", skipped_requests)

    load_to_run_ratio = round(total_load_ms / total_run_ms, 6) if total_run_ms else None
    load_event_count = len(segment_specs(base_hbm_dir, fine_hbm_dir))
    job_major_equivalent_load_event_count = 2 + (load_event_count - 2) * len(job_rows) if job_rows else None
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_bpu_segment_major_load_once_queue_runner" if not errors else "failed_dream7b_bpu_segment_major_load_once_queue_runner",
        "queue_dir": str(queue_dir),
        "output_dir": str(output_dir),
        "base_hbm_dir": str(base_hbm_dir),
        "fine_hbm_dir": str(fine_hbm_dir),
        "max_job_count": args.max_job_count,
        "max_batch_size": args.max_batch_size,
        "max_batch_size_limit": args.max_batch_size_limit,
        "processed_job_count": len(job_rows) if not errors else 0,
        "processed_request_count": len(results),
        "failed_job_count": len(processing_jobs) if errors else 0,
        "skipped_request_count": len(skipped_requests),
        "segment_major_load_once": True,
        "job_major_baseline_replaced": False,
        "bpu_lock": {"path": str(bpu_lock_path), "wait_ms": lock_wait_ms},
        "load_event_count": load_event_count,
        "job_major_equivalent_load_event_count": job_major_equivalent_load_event_count,
        "load_event_reduction_ratio": (
            round(1.0 - (load_event_count / job_major_equivalent_load_event_count), 6)
            if job_major_equivalent_load_event_count
            else None
        ),
        "total_load_ms": round(total_load_ms, 3),
        "run_ms": round(total_run_ms, 3),
        "wall_ms": wall_ms,
        "load_to_run_ratio": load_to_run_ratio,
        "amortized_wall_ms_per_processed_request": round(wall_ms / len(results), 3) if results else None,
        "amortized_total_load_ms_per_processed_request": round(total_load_ms / len(results), 3) if results else None,
        "amortized_run_ms_per_processed_request": round(total_run_ms / len(results), 3) if results else None,
        "peak_live_bytes": peak_live_bytes,
        "peak_live_mib": round(peak_live_bytes / (1024 * 1024), 3),
        "final_shape_counts": final_shape_counts,
        "topk_sample": topk_sample,
        "phase_timing_enabled": phase_timing_enabled,
        "raw_final_enabled": raw_final_enabled,
        "skip_explicit_gc": skip_explicit_gc,
        "phase_timing_totals_ms": {key: round(value, 3) for key, value in sorted(phase_timing_totals.items())},
        "durable_state": {
            "results_jsonl": str(durable_dir / "results.jsonl"),
            "skipped_requests_jsonl": str(durable_dir / "skipped_requests.jsonl"),
        },
        "warnings": warnings,
        "errors": errors,
    }
    summary_json = output_dir / "segment_major_queue_summary.json"
    summary_md = output_dir / "segment_major_queue_summary.md"
    summary_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream 7B Segment-Major Load-Once Queue Runner",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- processed_job_count: {payload['processed_job_count']}",
        f"- processed_request_count: {payload['processed_request_count']}",
        f"- failed_job_count: {payload['failed_job_count']}",
        f"- load_to_run_ratio: {payload['load_to_run_ratio']}",
        f"- avg load/run target gate: 0.15",
        f"- amortized_wall_ms_per_processed_request: {payload['amortized_wall_ms_per_processed_request']}",
        f"- peak_live_mib: {payload['peak_live_mib']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_md)
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    main()
