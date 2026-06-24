#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


SEG_RE = re.compile(r"compile_seg(\d{2})_(\d{2})_b(?P<batch>\d+)_(?P<stamp>\d{8}-\d{6})[.]log$")
TIME_RE = re.compile(r"Function '([^']+)' done in ([0-9.]+) seconds[.]")
TENSOR_RE = re.compile(r"Selective state_dict tensor_count:\s*(\d+)")
FUNC_RE = re.compile(r"func @(\S+)\((.*?)\) -> (.*?) _output_0")
OP_RE = re.compile(r"^\s*([A-Za-z0-9_.:]+(?:\s+[A-Za-z0-9_.:]+)*)\s*:\s*(\d+)\s*$")


def parse_log(path: Path) -> dict[str, Any]:
    match = SEG_RE.match(path.name)
    if not match:
        raise ValueError(f"unexpected log name: {path.name}")
    start = int(match.group(1))
    end = int(match.group(2))
    text = path.read_text(encoding="utf-8", errors="replace")
    timings: dict[str, float] = {}
    for name, value in TIME_RE.findall(text):
        timings[name] = float(value)
    tensor_match = TENSOR_RE.search(text)
    func_match = FUNC_RE.search(text.replace("\n", " "))
    ops: dict[str, int] = {}
    for line in text.splitlines():
        if not line.startswith((" ", "\t")):
            continue
        op_match = OP_RE.match(line)
        if op_match:
            ops[op_match.group(1).strip()] = int(op_match.group(2))
    output_signature = func_match.group(3).strip() if func_match else None
    if start == 0:
        segment_kind = "token_embedding"
    elif start == 27:
        segment_kind = "final_logits"
    else:
        segment_kind = "hidden_block"
    return {
        "segment": f"seg{start:02d}_{end:02d}",
        "start": start,
        "end": end,
        "batch_size": int(match.group("batch")),
        "stamp": match.group("stamp"),
        "log_path": str(path),
        "log_bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
        "segment_kind": segment_kind,
        "selective_state_dict_tensor_count": int(tensor_match.group(1)) if tensor_match else None,
        "timings_s": timings,
        "pipeline_timed_s": round(sum(timings.values()), 4),
        "function_signature": func_match.group(1) if func_match else None,
        "output_signature": output_signature,
        "ops": ops,
        "op_total": sum(ops.values()),
    }


def latest_nonempty_logs(log_dir: Path, batch_size: int) -> list[dict[str, Any]]:
    by_segment: dict[str, Path] = {}
    for path in sorted(log_dir.glob(f"compile_seg??_??_b{batch_size}_*.log")):
        if path.stat().st_size <= 0:
            continue
        match = SEG_RE.match(path.name)
        if not match:
            continue
        segment = f"seg{int(match.group(1)):02d}_{int(match.group(2)):02d}"
        old = by_segment.get(segment)
        if old is None or path.stat().st_mtime > old.stat().st_mtime:
            by_segment[segment] = path
    return [parse_log(path) for _, path in sorted(by_segment.items())]


def load_telemetry(paths: list[Path]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_file"] = str(path)
        payloads.append(payload)
    return payloads


def flatten_segment_runtime(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("group_rows", []):
        group_label = f"{group.get('group_start')}:{group.get('group_end')}"
        for segment in group.get("segment_rows", []):
            rows.append(
                {
                    "group": group_label,
                    "index": segment.get("index"),
                    "model_name": segment.get("model_name"),
                    "avg_run_ms": segment.get("avg_run_ms"),
                    "total_run_ms": segment.get("total_run_ms"),
                    "completed_microbatch_count": segment.get("completed_microbatch_count"),
                }
            )
    return rows


def telemetry_timing_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("timing_summary") or {}) if isinstance(payload.get("timing_summary"), dict) else {}
    rows = flatten_segment_runtime(payload)
    total_group_load_ms = round(sum(float(group.get("group_load_ms") or 0.0) for group in payload.get("group_rows", [])), 3)
    total_group_item_ms = round(sum(float(group.get("total_item_ms") or 0.0) for group in payload.get("group_rows", [])), 3)
    total_segment_run_ms = round(sum(float(row.get("total_run_ms") or 0.0) for row in rows), 3)
    wall_ms = payload.get("wall_ms")
    hidden = [
        float(row["avg_run_ms"])
        for row in rows
        if isinstance(row.get("index"), int)
        and 1 <= int(row["index"]) <= 26
        and isinstance(row.get("avg_run_ms"), (int, float))
    ]
    token = [
        float(row["avg_run_ms"])
        for row in rows
        if row.get("index") == 0 and isinstance(row.get("avg_run_ms"), (int, float))
    ]
    final = [
        float(row["avg_run_ms"])
        for row in rows
        if row.get("index") == 27 and isinstance(row.get("avg_run_ms"), (int, float))
    ]
    hidden_avg = mean(hidden)
    final_avg = mean(final)
    measured_run_ms = total_segment_run_ms if rows else total_group_item_ms
    computed = {
        "total_group_load_ms": total_group_load_ms if total_group_load_ms else None,
        "total_group_item_ms": total_group_item_ms if total_group_item_ms else None,
        "total_segment_run_ms": total_segment_run_ms if rows else None,
        "estimated_host_gap_ms": round(float(wall_ms) - total_group_load_ms - total_segment_run_ms, 3)
        if rows and isinstance(wall_ms, (int, float))
        else round(float(wall_ms) - total_group_load_ms - total_group_item_ms, 3)
        if total_group_item_ms and isinstance(wall_ms, (int, float))
        else None,
        "group_load_fraction_of_wall": round(total_group_load_ms / float(wall_ms), 4)
        if isinstance(wall_ms, (int, float)) and wall_ms > 0
        else None,
        "measured_run_fraction_of_wall": round(measured_run_ms / float(wall_ms), 4)
        if measured_run_ms and isinstance(wall_ms, (int, float)) and wall_ms > 0
        else None,
        "token_avg_run_ms": mean(token),
        "hidden_avg_run_ms": hidden_avg,
        "final_logits_avg_run_ms": final_avg,
        "final_vs_hidden_avg_run_ratio": round(final_avg / hidden_avg, 3) if final_avg and hidden_avg else None,
    }
    for key, value in computed.items():
        if summary.get(key) is None and value is not None:
            summary[key] = value
    return summary


def mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))
    return round(ordered[index], 4)


def md_value(value: Any) -> str:
    return "" if value is None else str(value)


def build_payload(
    log_rows: list[dict[str, Any]],
    telemetry: list[dict[str, Any]],
    queue_baseline_avg_bpu: float | None,
    queue_baseline_avg_nonzero_bpu: float | None,
) -> dict[str, Any]:
    hidden = [row for row in log_rows if row["segment_kind"] == "hidden_block"]
    export_values = [row["timings_s"].get("export_module") for row in log_rows if row["timings_s"].get("export_module") is not None]
    convert_values = [row["timings_s"].get("convert_mlir") for row in log_rows if row["timings_s"].get("convert_mlir") is not None]
    compile_values = [row["timings_s"].get("compile_hbo") for row in log_rows if row["timings_s"].get("compile_hbo") is not None]
    slow_compile = sorted(log_rows, key=lambda row: row["timings_s"].get("compile_hbo", 0.0), reverse=True)[:6]
    slow_pipeline = sorted(log_rows, key=lambda row: row["pipeline_timed_s"], reverse=True)[:6]

    telemetry_summaries: list[dict[str, Any]] = []
    runtime_rows: list[dict[str, Any]] = []
    for item in telemetry:
        rows = flatten_segment_runtime(item)
        runtime_rows.extend(rows)
        timing = telemetry_timing_summary(item)
        groups = [
            f"{group.get('start')}:{group.get('end')}"
            for group in item.get("groups", [])
            if group.get("start") is not None and group.get("end") is not None
        ]
        telemetry_summaries.append(
            {
                "file": item.get("_file"),
                "verdict": item.get("verdict"),
                "batch_size": item.get("batch_size"),
                "microbatch_count": item.get("microbatch_count"),
                "inner_order": item.get("inner_order"),
                "group_count": len(groups),
                "group_spec": ",".join(groups),
                "processed_request_count": item.get("processed_request_count"),
                "avg_bpu_loading": item.get("avg_bpu_loading"),
                "avg_nonzero_bpu_loading": item.get("avg_nonzero_bpu_loading"),
                "amortized_wall_ms_per_request": item.get("amortized_wall_ms_per_request"),
                "final_shape": item.get("final_shape"),
                "group_load_fraction_of_wall": timing.get("group_load_fraction_of_wall"),
                "hidden_avg_run_ms": timing.get("hidden_avg_run_ms"),
                "final_logits_avg_run_ms": timing.get("final_logits_avg_run_ms"),
                "final_vs_hidden_avg_run_ratio": timing.get("final_vs_hidden_avg_run_ratio"),
                "estimated_host_gap_ms": timing.get("estimated_host_gap_ms"),
                "measured_run_fraction_of_wall": timing.get("measured_run_fraction_of_wall"),
            }
        )
    slow_runtime = sorted(
        [row for row in runtime_rows if isinstance(row.get("avg_run_ms"), (int, float))],
        key=lambda row: float(row["avg_run_ms"]),
        reverse=True,
    )[:8]
    latest_telemetry = telemetry[-1] if telemetry else None
    latest_timing = telemetry_timing_summary(latest_telemetry) if latest_telemetry else {}
    latest_avg_bpu = latest_telemetry.get("avg_bpu_loading") if latest_telemetry else None
    latest_nonzero_bpu = latest_telemetry.get("avg_nonzero_bpu_loading") if latest_telemetry else None
    avg_bpu_gap = (
        round(float(latest_avg_bpu) - queue_baseline_avg_bpu, 3)
        if isinstance(latest_avg_bpu, (int, float)) and queue_baseline_avg_bpu is not None
        else None
    )
    nonzero_bpu_gap = (
        round(float(latest_nonzero_bpu) - queue_baseline_avg_nonzero_bpu, 3)
        if isinstance(latest_nonzero_bpu, (int, float)) and queue_baseline_avg_nonzero_bpu is not None
        else None
    )

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "segment_count": len(log_rows),
        "segments": log_rows,
        "compile_summary": {
            "export_module_mean_s": mean([float(v) for v in export_values]),
            "convert_mlir_mean_s": mean([float(v) for v in convert_values]),
            "compile_hbo_mean_s": mean([float(v) for v in compile_values]),
            "compile_hbo_p95_s": p95([float(v) for v in compile_values]),
            "hidden_compile_hbo_mean_s": mean([float(row["timings_s"]["compile_hbo"]) for row in hidden if "compile_hbo" in row["timings_s"]]),
            "total_timed_pipeline_s": round(sum(float(row["pipeline_timed_s"]) for row in log_rows), 4),
            "slowest_compile_hbo": slow_compile,
            "slowest_pipeline": slow_pipeline,
        },
        "telemetry_reports": telemetry_summaries,
        "slowest_runtime_segments": slow_runtime,
        "runtime_summary": {
            "latest_telemetry_file": latest_telemetry.get("_file") if latest_telemetry else None,
            "queue_baseline_avg_bpu_loading": queue_baseline_avg_bpu,
            "queue_baseline_avg_nonzero_bpu_loading": queue_baseline_avg_nonzero_bpu,
            "avg_bpu_gap_vs_queue": avg_bpu_gap,
            "avg_nonzero_bpu_gap_vs_queue": nonzero_bpu_gap,
            "token_avg_run_ms": latest_timing.get("token_avg_run_ms"),
            "hidden_avg_run_ms": latest_timing.get("hidden_avg_run_ms"),
            "final_logits_avg_run_ms": latest_timing.get("final_logits_avg_run_ms"),
            "final_vs_hidden_avg_run_ratio": latest_timing.get("final_vs_hidden_avg_run_ratio"),
            "total_group_load_ms": latest_timing.get("total_group_load_ms"),
            "total_segment_run_ms": latest_timing.get("total_segment_run_ms"),
            "estimated_host_gap_ms": latest_timing.get("estimated_host_gap_ms"),
            "group_load_fraction_of_wall": latest_timing.get("group_load_fraction_of_wall"),
        },
    }


def write_markdown(payload: dict[str, Any], out_path: Path) -> None:
    compile_summary = payload["compile_summary"]
    lines = [
        "# Dream7B B=4 True-Batch Segment Analysis",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- parsed_segment_count: {payload['segment_count']}",
        f"- total_timed_compile_pipeline_s: {compile_summary['total_timed_pipeline_s']}",
        f"- compile_hbo_mean_s: {compile_summary['compile_hbo_mean_s']}",
        f"- compile_hbo_p95_s: {compile_summary['compile_hbo_p95_s']}",
        f"- hidden_compile_hbo_mean_s: {compile_summary['hidden_compile_hbo_mean_s']}",
        "",
        "## Compile Bottlenecks",
        "",
        "| rank | segment | kind | export_s | convert_s | compile_hbo_s | timed_pipeline_s | output |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for rank, row in enumerate(compile_summary["slowest_pipeline"], start=1):
        timings = row["timings_s"]
        lines.append(
            "| {rank} | {segment} | {kind} | {export:.4f} | {convert:.4f} | {compile:.4f} | {pipeline:.4f} | {output} |".format(
                rank=rank,
                segment=row["segment"],
                kind=row["segment_kind"],
                export=float(timings.get("export_module", 0.0)),
                convert=float(timings.get("convert_mlir", 0.0)),
                compile=float(timings.get("compile_hbo", 0.0)),
                pipeline=float(row["pipeline_timed_s"]),
                output=row.get("output_signature") or "",
            )
        )
    lines.extend(["", "## Runtime Telemetry", ""])
    runtime_summary = payload["runtime_summary"]
    if payload["telemetry_reports"]:
        lines.extend(
            [
                "| file | inner_order | groups | microbatches | avg_bpu | avg_nonzero_bpu | wall_ms_per_request | final_shape |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for item in payload["telemetry_reports"]:
            lines.append(
                "| {file} | {inner} | {groups} | {mb} | {avg} | {nonzero} | {wall} | {shape} |".format(
                    file=item.get("file"),
                    inner=item.get("inner_order"),
                    groups=item.get("group_count"),
                    mb=item.get("microbatch_count"),
                    avg=md_value(item.get("avg_bpu_loading")),
                    nonzero=md_value(item.get("avg_nonzero_bpu_loading")),
                    wall=md_value(item.get("amortized_wall_ms_per_request")),
                    shape=md_value(item.get("final_shape")),
                )
            )
        lines.extend(
            [
                "",
                "## Runtime Scaling",
                "",
                "| inner_order | groups | microbatches | load_fraction_wall | hidden_avg_ms | final_avg_ms | final_hidden_ratio |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for item in sorted(
            payload["telemetry_reports"],
            key=lambda row: (int(row.get("microbatch_count") or 0), str(row.get("inner_order")), int(row.get("group_count") or 0)),
        ):
            lines.append(
                "| {inner} | {groups} | {mb} | {load} | {hidden} | {final} | {ratio} |".format(
                    inner=item.get("inner_order"),
                    groups=item.get("group_count"),
                    mb=item.get("microbatch_count"),
                    load=md_value(item.get("group_load_fraction_of_wall")),
                    hidden=md_value(item.get("hidden_avg_run_ms")),
                    final=md_value(item.get("final_logits_avg_run_ms")),
                    ratio=md_value(item.get("final_vs_hidden_avg_run_ratio")),
                )
            )
        lines.extend(
            [
                "",
                "## Order Comparison",
                "",
                "| inner_order | groups | microbatches | avg_bpu | nonzero_bpu | ms_per_request | load_fraction | measured_run_fraction | estimated_host_gap_ms |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for item in sorted(
            payload["telemetry_reports"],
            key=lambda row: (int(row.get("microbatch_count") or 0), str(row.get("inner_order")), int(row.get("group_count") or 0)),
        ):
            lines.append(
                "| {inner} | {groups} | {mb} | {avg} | {nonzero} | {wall} | {load} | {run_frac} | {gap} |".format(
                    inner=item.get("inner_order"),
                    groups=item.get("group_count"),
                    mb=item.get("microbatch_count"),
                    avg=item.get("avg_bpu_loading"),
                    nonzero=item.get("avg_nonzero_bpu_loading"),
                    wall=item.get("amortized_wall_ms_per_request"),
                    load=md_value(item.get("group_load_fraction_of_wall")),
                    run_frac=md_value(item.get("measured_run_fraction_of_wall")),
                    gap=md_value(item.get("estimated_host_gap_ms")),
                )
            )
        if payload["slowest_runtime_segments"]:
            lines.extend(["", "## Slowest Runtime Segments", ""])
            lines.extend(["| rank | group | index | avg_run_ms | completed_microbatches |", "| ---: | --- | ---: | ---: | ---: |"])
            for rank, row in enumerate(payload["slowest_runtime_segments"], start=1):
                lines.append(
                    f"| {rank} | {row.get('group')} | {row.get('index')} | {row.get('avg_run_ms')} | {row.get('completed_microbatch_count')} |"
                )
        lines.extend(
            [
                "",
                "## Runtime Summary",
                "",
                f"- avg_bpu_gap_vs_queue_points: {runtime_summary['avg_bpu_gap_vs_queue']}",
                f"- avg_nonzero_bpu_gap_vs_queue_points: {runtime_summary['avg_nonzero_bpu_gap_vs_queue']}",
                f"- token_avg_run_ms: {runtime_summary['token_avg_run_ms']}",
                f"- hidden_avg_run_ms: {runtime_summary['hidden_avg_run_ms']}",
                f"- final_logits_avg_run_ms: {runtime_summary['final_logits_avg_run_ms']}",
                f"- final_vs_hidden_avg_run_ratio: {runtime_summary['final_vs_hidden_avg_run_ratio']}",
                f"- total_group_load_ms: {runtime_summary['total_group_load_ms']}",
                f"- total_segment_run_ms: {runtime_summary['total_segment_run_ms']}",
                f"- group_load_fraction_of_wall: {runtime_summary['group_load_fraction_of_wall']}",
            ]
        )
    else:
        lines.append("- no runtime telemetry JSON was supplied")

    lines.extend(["", "## Interpretation", ""])
    lines.append(
        "- Compile side: hidden segments are tightly clustered; the first token/embedding segment and final logits segment are the main outliers."
    )
    if payload["telemetry_reports"]:
        lines.append(
            "- Runtime side: B=4 segment-major execution is valid and stable, but it remains below the queue-batch BPU loading gate."
        )
        lines.append(
            "- Inner-order comparison: at 512 microbatches, segment-major is only slightly better than microbatch-major, so loop order alone is not the missing production lever."
        )
        lines.append(
            "- Group-size comparison: at 512 microbatches, splitting into more groups slightly increases load fraction and does not improve BPU loading."
        )
        lines.append(
            "- Long-queue scaling: increasing from 1536 to 3072 microbatches improves average BPU loading and lowers per-request wall time, but still does not reach the queue-batch BPU gate."
        )
        lines.append(
            "- Segment breakdown: final logits is still the run-time outlier; tune scheduling around it separately from the hidden-block average."
        )
        lines.append(
            "- Gap accounting: segment-major measured-run fraction comes from per-segment run totals; microbatch-major uses group item totals, so compare host gap directionally rather than as identical instrumentation."
        )
    else:
        lines.append(
            "- Runtime side: supply B=4 group-major telemetry JSON to quantify whether the final logits segment remains the run-time outlier."
        )
    lines.append(
        "- Scheduling implication: group sizing can reduce load/release amortization, but it cannot remove the final logits cost."
    )
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-dir", default="tmp/true_batch_hbm_stage/logs")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--telemetry-json", action="append", default=[])
    parser.add_argument("--queue-baseline-avg-bpu", type=float, default=93.166)
    parser.add_argument("--queue-baseline-avg-nonzero-bpu", type=float, default=95.097)
    parser.add_argument("--out-json", default="tmp/true_batch_hbm_stage/b4_segment_analysis.json")
    parser.add_argument("--out-md", default="docs/dream7b_true_batch_b4_segment_analysis_2026-06-19.md")
    args = parser.parse_args()

    logs = latest_nonempty_logs(Path(args.log_dir), args.batch_size)
    telemetry = load_telemetry([Path(item) for item in args.telemetry_json])
    payload = build_payload(logs, telemetry, args.queue_baseline_avg_bpu, args.queue_baseline_avg_nonzero_bpu)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, out_md)
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
