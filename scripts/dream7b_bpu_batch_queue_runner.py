#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


APPROVED_OUTPUT_PREFIXES = (
    "/tmp/",
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
    return parser.parse_args()


def is_approved_output_dir(path: Path) -> bool:
    text = str(path)
    return any(text == prefix.rstrip("/") or text.startswith(prefix) for prefix in APPROVED_OUTPUT_PREFIXES)


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
        if not isinstance(request_id, str) or not request_id:
            raise ValueError(f"line {line_number}: request_id must be a non-empty string")
        if request_id in request_ids:
            raise ValueError(f"line {line_number}: duplicate request_id: {request_id}")
        if not isinstance(tokens, list):
            raise ValueError(f"line {line_number}: tokens must be a JSON list")
        if len(tokens) != seq_len:
            raise ValueError(f"line {line_number}: expected {seq_len} token ids, got {len(tokens)}")
        request_ids.add(request_id)
        rows.append(
            {
                "request_id": request_id,
                "tokens": [int(token) for token in tokens],
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


def main():
    args = parse_args()
    if args.max_batch_size <= 0:
        raise ValueError("--max-batch-size must be positive")
    if args.seq_len <= 0:
        raise ValueError("--seq-len must be positive")
    request_jsonl = Path(args.request_jsonl)
    output_dir = Path(args.output_dir)
    if not request_jsonl.is_file():
        raise FileNotFoundError(request_jsonl)
    if not is_approved_output_dir(output_dir):
        raise ValueError(f"Refusing output path outside approved report directories: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    requests = read_requests(request_jsonl, args.seq_len)
    accepted = requests[: args.max_batch_size]
    deferred = requests[args.max_batch_size :]
    tokens_batch_json = output_dir / "tokens_batch.json"
    tokens_batch_json.write_text(json.dumps([item["tokens"] for item in accepted], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    forward_dir = output_dir / "forward"
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
    (output_dir / "forward.stdout").write_text(proc.stdout, encoding="utf-8")
    (output_dir / "forward.stderr").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"forward command failed with exit code {proc.returncode}: {output_dir / 'forward.stderr'}")

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
                "batch_index": batch_index,
                "final_shape": final_shape,
                "topk_last_position": indexed_topk.get(batch_index, []),
            }
        )

    errors = []
    if forward_summary.get("verdict") != "ok_dream7b_segmented_hbm_python_forward":
        errors.append(f"unexpected forward verdict: {forward_summary.get('verdict')}")
    if forward_summary.get("execution_mode") != "pair_window_batch":
        errors.append(f"unexpected execution_mode: {forward_summary.get('execution_mode')}")
    if forward_summary.get("batch_count") != len(accepted):
        errors.append(f"unexpected batch_count: {forward_summary.get('batch_count')}")
    for result in results:
        if result["final_shape"] != [1, args.seq_len, 152064]:
            errors.append(f"unexpected final_shape for {result['request_id']}: {result['final_shape']}")

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_bpu_batch_queue_runner" if not errors else "failed_dream7b_bpu_batch_queue_runner",
        "request_jsonl": str(request_jsonl),
        "output_dir": str(output_dir),
        "forward_command": args.forward_cmd,
        "forward_summary": str(forward_summary_path),
        "tokens_batch_json": str(tokens_batch_json),
        "max_batch_size": args.max_batch_size,
        "accepted_count": len(accepted),
        "deferred_count": len(deferred),
        "deferred_request_ids": [item["request_id"] for item in deferred],
        "results": results,
        "forward_metrics": {
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
        f"- forward_summary: {payload['forward_summary']}",
        f"- max_batch_size: {payload['max_batch_size']}",
        f"- accepted_count: {payload['accepted_count']}",
        f"- deferred_count: {payload['deferred_count']}",
        f"- execution_mode: {payload['forward_metrics']['execution_mode']}",
        f"- window_execution_mode: {payload['forward_metrics']['window_execution_mode']}",
        f"- child_process_count: {payload['forward_metrics']['child_process_count']}",
        f"- wall_ms: {payload['forward_metrics']['wall_ms']}",
        f"- amortized_wall_ms_per_forward: {payload['forward_metrics']['amortized_wall_ms_per_forward']}",
        "",
        "## Results",
        "",
        "| request_id | batch_index | final_shape |",
        "| --- | ---: | --- |",
    ]
    for result in results:
        lines.append(f"| {result['request_id']} | {result['batch_index']} | {result['final_shape']} |")
    lines.extend(["", "## Deferred", ""])
    if deferred:
        lines.extend(f"- {item['request_id']}" for item in deferred)
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
