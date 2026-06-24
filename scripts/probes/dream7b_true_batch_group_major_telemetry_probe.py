#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import json
import re
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from hbm_runtime import HB_HBMRuntime


def final_logits_suffix(final_logits_mode: str, index: int) -> str:
    return "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""


def final_logits_seq_len(seq_len: int, final_logits_mode: str) -> int:
    return 1 if final_logits_mode == "last-token" else seq_len


def hbm_path(
    root: Path,
    final_root: Path | None,
    index: int,
    seq_len: int,
    batch_size: int,
    w_bits: int,
    final_logits_mode: str,
) -> Path:
    base = final_root if index == 27 and final_root is not None else root
    suffix = final_logits_suffix(final_logits_mode, index)
    return base / f"seg{index:02d}_{index + 1:02d}" / f"dream7b_segment_{index}_{index + 1}_seq{seq_len}_b{batch_size}_q{w_bits}{suffix}.hbm"


def model_name(index: int, batch_size: int, final_logits_mode: str) -> str:
    suffix = final_logits_suffix(final_logits_mode, index)
    return f"dream_batch_segment_{index:02d}_{index + 1:02d}_b{batch_size}{suffix}"


def output_scale(runtime: HB_HBMRuntime, name: str) -> float | None:
    try:
        scale = np.asarray(runtime.output_quants[name]["_output_0"].scale).reshape(-1)
        return float(scale[0]) if scale.size else None
    except Exception:
        return None


def count_value(counts: dict[str, int], value: Any) -> None:
    key = str(value)
    counts[key] = counts.get(key, 0) + 1


def merge_counts(target: dict[str, int], source: dict[str, Any]) -> None:
    for key, value in source.items():
        target[str(key)] = target.get(str(key), 0) + int(value or 0)


def hidden_materialize_candidate_mode(
    *,
    index: int,
    arr: np.ndarray,
    scale: float | None,
    reusable: np.ndarray | None,
) -> str:
    if index == 27:
        return "final_logits_no_hidden_materialize"
    if reusable is not None:
        return "preallocated_reusable_copy_or_scale"
    if scale is not None:
        return "scaled_output_materialize_multiply"
    if arr.dtype == np.float32 and bool(arr.flags.c_contiguous):
        return "scale_none_float32_c_contiguous_no_copy_candidate"
    return "scale_none_materialize_copy"


def output_telemetry_fields(
    *,
    index: int,
    arr: np.ndarray,
    scale: float | None,
    reusable: np.ndarray | None,
) -> dict[str, Any]:
    return {
        "output_quant_scale": scale,
        "output_quant_scale_is_none": scale is None,
        "output_dtype": str(arr.dtype),
        "output_c_contiguous": bool(arr.flags.c_contiguous),
        "hidden_materialize_candidate_mode": hidden_materialize_candidate_mode(
            index=index,
            arr=arr,
            scale=scale,
            reusable=reusable,
        ),
    }


def parse_groups(text: str) -> list[tuple[int, int]]:
    groups: list[tuple[int, int]] = []
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"invalid group spec: {part}")
        start, end = (int(item) for item in part.split(":", 1))
        if end <= start:
            raise ValueError(f"invalid group range: {part}")
        groups.append((start, end))
    return groups


def parse_bpu_samples(text: str) -> list[float]:
    return [float(item) for item in re.findall(r"\|\s*BPU0\s+([0-9]+(?:[.][0-9]+)?)\s*\|", text)]


def summarize_group_rows(group_rows: list[dict[str, Any]], wall_ms: float) -> dict[str, Any]:
    total_hbm_prewarm_ms = sum(float(group.get("hbm_prewarm_ms") or 0.0) for group in group_rows)
    total_hbm_prewarm_bytes = sum(int(group.get("hbm_prewarm_bytes") or 0) for group in group_rows)
    total_group_load_ms = sum(float(group.get("group_load_ms") or 0.0) for group in group_rows)
    total_group_item_ms = sum(float(group.get("total_item_ms") or 0.0) for group in group_rows)
    total_group_release_ms = sum(float(group.get("group_release_ms") or 0.0) for group in group_rows)
    total_group_input_prepare_ms = sum(float(group.get("input_prepare_ms") or 0.0) for group in group_rows)
    total_group_output_postprocess_ms = sum(float(group.get("output_postprocess_ms") or 0.0) for group in group_rows)
    total_group_hidden_materialize_ms = sum(float(group.get("hidden_materialize_ms") or 0.0) for group in group_rows)
    total_group_hidden_materialize_count = sum(int(group.get("hidden_materialize_count") or 0) for group in group_rows)
    total_group_reused_hidden_buffer_count = sum(int(group.get("reused_hidden_buffer_count") or 0) for group in group_rows)
    total_group_output_quant_scale_none_count = sum(
        int(group.get("output_quant_scale_none_count") or 0) for group in group_rows
    )
    total_group_output_c_contiguous_count = sum(
        int(group.get("output_c_contiguous_count") or 0) for group in group_rows
    )
    group_output_dtype_counts: dict[str, int] = {}
    group_hidden_candidate_mode_counts: dict[str, int] = {}
    for group in group_rows:
        merge_counts(group_output_dtype_counts, group.get("output_dtype_counts") or {})
        merge_counts(
            group_hidden_candidate_mode_counts,
            group.get("hidden_materialize_candidate_mode_counts") or {},
        )
    segment_rows: list[dict[str, Any]] = []
    for group in group_rows:
        segment_rows.extend(group.get("segment_rows") or [])
    total_segment_run_ms = sum(float(row.get("total_run_ms") or 0.0) for row in segment_rows)
    total_segment_total_ms = sum(float(row.get("segment_total_ms") or 0.0) for row in segment_rows)
    total_segment_hidden_materialize_ms = sum(float(row.get("hidden_materialize_ms") or 0.0) for row in segment_rows)
    total_segment_input_prepare_ms = sum(float(row.get("input_prepare_ms") or 0.0) for row in segment_rows)
    total_segment_output_postprocess_ms = sum(float(row.get("output_postprocess_ms") or 0.0) for row in segment_rows)
    total_inter_segment_first_run_gap_ms = sum(
        float(row.get("inter_segment_first_run_gap_ms") or 0.0) for row in segment_rows
    )
    total_intra_segment_run_gap_ms = sum(float(row.get("intra_segment_run_gap_ms") or 0.0) for row in segment_rows)
    total_segment_hidden_materialize_count = sum(int(row.get("hidden_materialize_count") or 0) for row in segment_rows)
    total_segment_reused_hidden_buffer_count = sum(int(row.get("reused_hidden_buffer_count") or 0) for row in segment_rows)
    total_segment_output_quant_scale_none_count = sum(
        int(row.get("output_quant_scale_none_count") or 0) for row in segment_rows
    )
    total_segment_output_c_contiguous_count = sum(
        int(row.get("output_c_contiguous_count") or 0) for row in segment_rows
    )
    segment_output_dtype_counts: dict[str, int] = {}
    segment_hidden_candidate_mode_counts: dict[str, int] = {}
    for row in segment_rows:
        merge_counts(segment_output_dtype_counts, row.get("output_dtype_counts") or {})
        merge_counts(
            segment_hidden_candidate_mode_counts,
            row.get("hidden_materialize_candidate_mode_counts") or {},
        )
    total_hidden_materialize_ms = total_segment_hidden_materialize_ms or total_group_hidden_materialize_ms
    total_input_prepare_ms = total_segment_input_prepare_ms or total_group_input_prepare_ms
    total_output_postprocess_ms = total_segment_output_postprocess_ms or total_group_output_postprocess_ms
    total_hidden_materialize_count = total_segment_hidden_materialize_count or total_group_hidden_materialize_count
    total_reused_hidden_buffer_count = (
        total_segment_reused_hidden_buffer_count or total_group_reused_hidden_buffer_count
    )
    output_quant_scale_none_count = (
        total_segment_output_quant_scale_none_count
        if segment_rows
        else total_group_output_quant_scale_none_count
    )
    output_c_contiguous_count = (
        total_segment_output_c_contiguous_count
        if segment_rows
        else total_group_output_c_contiguous_count
    )
    output_dtype_counts = segment_output_dtype_counts if segment_rows else group_output_dtype_counts
    hidden_candidate_mode_counts = (
        segment_hidden_candidate_mode_counts
        if segment_rows
        else group_hidden_candidate_mode_counts
    )
    output_dtype_by_segment = [
        {"index": row.get("index"), "output_dtype": row.get("output_dtype")}
        for row in segment_rows
        if row.get("output_dtype") is not None
    ]
    output_c_contiguous_by_segment = [
        {"index": row.get("index"), "output_c_contiguous": row.get("output_c_contiguous")}
        for row in segment_rows
        if row.get("output_c_contiguous") is not None
    ]
    hidden_materialize_candidate_mode_by_segment = [
        {
            "index": row.get("index"),
            "hidden_materialize_candidate_mode": row.get(
                "hidden_materialize_candidate_mode"
            ),
        }
        for row in segment_rows
        if row.get("hidden_materialize_candidate_mode") is not None
    ]
    total_segment_overhead_ms = max(0.0, total_segment_total_ms - total_segment_run_ms)
    measured_active_ms = total_segment_total_ms if segment_rows else total_group_item_ms
    measured_run_ms = total_segment_run_ms if segment_rows else total_group_item_ms
    accounted_ms = total_hbm_prewarm_ms + total_group_load_ms + measured_active_ms + total_group_release_ms
    hidden_avg_run_ms = [
        float(row["avg_run_ms"])
        for row in segment_rows
        if isinstance(row.get("index"), int)
        and 1 <= int(row["index"]) <= 26
        and isinstance(row.get("avg_run_ms"), (int, float))
    ]
    token_avg_run_ms = [
        float(row["avg_run_ms"])
        for row in segment_rows
        if row.get("index") == 0 and isinstance(row.get("avg_run_ms"), (int, float))
    ]
    final_avg_run_ms = [
        float(row["avg_run_ms"])
        for row in segment_rows
        if row.get("index") == 27 and isinstance(row.get("avg_run_ms"), (int, float))
    ]
    hidden_avg = round(statistics.fmean(hidden_avg_run_ms), 3) if hidden_avg_run_ms else None
    final_avg = round(statistics.fmean(final_avg_run_ms), 3) if final_avg_run_ms else None
    return {
        "total_group_load_ms": round(total_group_load_ms, 3),
        "total_hbm_prewarm_ms": round(total_hbm_prewarm_ms, 3) if total_hbm_prewarm_ms else None,
        "total_hbm_prewarm_bytes": total_hbm_prewarm_bytes,
        "total_hbm_prewarm_mib": round(total_hbm_prewarm_bytes / 1024 / 1024, 3) if total_hbm_prewarm_bytes else None,
        "total_group_item_ms": round(total_group_item_ms, 3) if total_group_item_ms else None,
        "total_segment_run_ms": round(total_segment_run_ms, 3) if segment_rows else None,
        "total_segment_total_ms": round(total_segment_total_ms, 3) if segment_rows else None,
        "total_segment_overhead_ms": round(total_segment_overhead_ms, 3) if segment_rows else None,
        "total_group_release_ms": round(total_group_release_ms, 3) if total_group_release_ms else None,
        "total_input_prepare_ms": round(total_input_prepare_ms, 3) if total_input_prepare_ms else None,
        "total_output_postprocess_ms": round(total_output_postprocess_ms, 3) if total_output_postprocess_ms else None,
        "total_hidden_materialize_ms": round(total_hidden_materialize_ms, 3) if total_hidden_materialize_ms else None,
        "total_inter_segment_first_run_gap_ms": (
            round(total_inter_segment_first_run_gap_ms, 3) if total_inter_segment_first_run_gap_ms else None
        ),
        "total_intra_segment_run_gap_ms": round(total_intra_segment_run_gap_ms, 3) if total_intra_segment_run_gap_ms else None,
        "hidden_materialize_count": total_hidden_materialize_count,
        "hidden_materialize_ms_per_item": (
            round(total_hidden_materialize_ms / total_hidden_materialize_count, 6)
            if total_hidden_materialize_count
            else None
        ),
        "reused_hidden_buffer_count": total_reused_hidden_buffer_count,
        "output_quant_scale_none_count": output_quant_scale_none_count,
        "output_dtype_counts": output_dtype_counts,
        "output_dtype_by_segment": output_dtype_by_segment,
        "output_c_contiguous_count": output_c_contiguous_count,
        "output_c_contiguous_by_segment": output_c_contiguous_by_segment,
        "hidden_materialize_candidate_mode_counts": hidden_candidate_mode_counts,
        "hidden_materialize_candidate_mode_by_segment": hidden_materialize_candidate_mode_by_segment,
        "measured_active_ms": round(measured_active_ms, 3) if measured_active_ms else None,
        "estimated_host_gap_ms": round(wall_ms - total_hbm_prewarm_ms - total_group_load_ms - measured_active_ms, 3) if measured_active_ms else None,
        "estimated_unaccounted_gap_ms": round(wall_ms - accounted_ms, 3) if measured_active_ms else None,
        "hbm_prewarm_fraction_of_wall": round(total_hbm_prewarm_ms / wall_ms, 4) if wall_ms > 0 and total_hbm_prewarm_ms else None,
        "group_load_fraction_of_wall": round(total_group_load_ms / wall_ms, 4) if wall_ms > 0 else None,
        "measured_run_fraction_of_wall": round(measured_run_ms / wall_ms, 4) if wall_ms > 0 and measured_run_ms else None,
        "measured_active_fraction_of_wall": round(measured_active_ms / wall_ms, 4) if wall_ms > 0 and measured_active_ms else None,
        "segment_overhead_fraction_of_wall": round(total_segment_overhead_ms / wall_ms, 4) if wall_ms > 0 and total_segment_overhead_ms else None,
        "group_release_fraction_of_wall": round(total_group_release_ms / wall_ms, 4) if wall_ms > 0 and total_group_release_ms else None,
        "input_prepare_fraction_of_wall": round(total_input_prepare_ms / wall_ms, 4) if wall_ms > 0 and total_input_prepare_ms else None,
        "output_postprocess_fraction_of_wall": round(total_output_postprocess_ms / wall_ms, 4) if wall_ms > 0 and total_output_postprocess_ms else None,
        "inter_segment_first_run_gap_fraction_of_wall": (
            round(total_inter_segment_first_run_gap_ms / wall_ms, 4)
            if wall_ms > 0 and total_inter_segment_first_run_gap_ms
            else None
        ),
        "intra_segment_run_gap_fraction_of_wall": (
            round(total_intra_segment_run_gap_ms / wall_ms, 4)
            if wall_ms > 0 and total_intra_segment_run_gap_ms
            else None
        ),
        "unaccounted_gap_fraction_of_wall": round((wall_ms - accounted_ms) / wall_ms, 4) if wall_ms > 0 and measured_active_ms else None,
        "token_avg_run_ms": round(statistics.fmean(token_avg_run_ms), 3) if token_avg_run_ms else None,
        "hidden_avg_run_ms": hidden_avg,
        "final_logits_avg_run_ms": final_avg,
        "final_vs_hidden_avg_run_ratio": round(final_avg / hidden_avg, 3) if final_avg and hidden_avg else None,
    }


def group_hbm_paths(
    root: Path,
    final_root: Path | None,
    start: int,
    end: int,
    seq_len: int,
    batch_size: int,
    w_bits: int,
    final_logits_mode: str,
) -> list[Path]:
    return [
        hbm_path(root, final_root, index, seq_len, batch_size, w_bits, final_logits_mode)
        for index in range(start, end)
    ]


def prewarm_hbm_files(paths: list[Path], chunk_bytes: int) -> dict[str, Any]:
    started = time.perf_counter()
    total_bytes = 0
    files: list[dict[str, Any]] = []
    for path in paths:
        file_started = time.perf_counter()
        file_bytes = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_bytes)
                if not chunk:
                    break
                file_bytes += len(chunk)
        total_bytes += file_bytes
        files.append(
            {
                "hbm_path": str(path),
                "bytes": file_bytes,
                "mib": round(file_bytes / 1024 / 1024, 3),
                "prewarm_ms": round((time.perf_counter() - file_started) * 1000, 3),
            }
        )
    return {
        "hbm_prewarm_ms": round((time.perf_counter() - started) * 1000, 3),
        "hbm_prewarm_bytes": total_bytes,
        "hbm_prewarm_mib": round(total_bytes / 1024 / 1024, 3),
        "hbm_prewarm_files": files,
    }


def load_group(
    root: Path,
    final_root: Path | None,
    start: int,
    end: int,
    seq_len: int,
    batch_size: int,
    w_bits: int,
    final_logits_mode: str,
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for index in range(start, end):
        path = hbm_path(root, final_root, index, seq_len, batch_size, w_bits, final_logits_mode)
        name = model_name(index, batch_size, final_logits_mode)
        hbm_size_bytes = path.stat().st_size if path.exists() else None
        t0 = time.perf_counter()
        runtime = HB_HBMRuntime(str(path))
        load_ms = (time.perf_counter() - t0) * 1000
        loaded.append(
            {
                "index": index,
                "runtime": runtime,
                "model_name": name,
                "hbm_path": str(path),
                "hbm_size_bytes": hbm_size_bytes,
                "hbm_size_mib": round(hbm_size_bytes / 1024 / 1024, 3) if hbm_size_bytes is not None else None,
                "load_ms": round(load_ms, 3),
                "output_quant_scale": output_scale(runtime, name),
            }
        )
    return loaded


def loaded_segment_summary(loaded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": int(item["index"]),
            "model_name": str(item["model_name"]),
            "hbm_path": str(item["hbm_path"]),
            "hbm_size_bytes": item.get("hbm_size_bytes"),
            "hbm_size_mib": item.get("hbm_size_mib"),
            "load_ms": item.get("load_ms"),
            "output_quant_scale": item.get("output_quant_scale"),
        }
        for item in loaded
    ]


def materialize_hidden(
    arr: np.ndarray,
    scale: float | None,
    reusable: np.ndarray | None = None,
) -> tuple[np.ndarray, float, bool]:
    start = time.perf_counter()
    if reusable is not None:
        if scale is None:
            np.copyto(reusable, arr, casting="unsafe")
        else:
            np.multiply(arr, float(scale), out=reusable, casting="unsafe")
        return reusable, (time.perf_counter() - start) * 1000, True
    if scale is None:
        result = arr.astype(np.float32, copy=True)
    else:
        result = arr.astype(np.float32, copy=False) * float(scale)
    return result, (time.perf_counter() - start) * 1000, False


def run_group_for_item(
    loaded: list[dict[str, Any]],
    tokens: np.ndarray,
    hidden: np.ndarray | None,
    hidden_buffer: np.ndarray | None,
    position_ids: np.ndarray,
    batch_size: int,
    seq_len: int,
    hidden_size: int,
    vocab_size: int,
    final_logits_mode: str,
) -> tuple[np.ndarray | None, dict[str, Any], list[str]]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    current_hidden = hidden
    final_logits_shape: list[int] | None = None
    input_prepare_times: list[float] = []
    output_postprocess_times: list[float] = []
    materialize_times: list[float] = []
    reused_buffer_count = 0
    output_quant_scale_none_count = 0
    output_c_contiguous_count = 0
    output_dtype_counts: dict[str, int] = {}
    hidden_materialize_candidate_mode_counts: dict[str, int] = {}
    t0 = time.perf_counter()
    for item in loaded:
        index = int(item["index"])
        runtime: HB_HBMRuntime = item["runtime"]
        name = str(item["model_name"])
        prepare_start = time.perf_counter()
        if index == 0:
            inputs = {"_input_0": tokens, "_input_1": position_ids}
        else:
            if current_hidden is None:
                raise RuntimeError(f"missing hidden before segment {index}")
            inputs = {"_input_0": current_hidden.astype(np.float32, copy=False), "_input_1": position_ids}
        run_start = time.perf_counter()
        input_prepare_ms = (run_start - prepare_start) * 1000
        input_prepare_times.append(input_prepare_ms)
        out = runtime.run(inputs, model_name=name)
        run_ms = (time.perf_counter() - run_start) * 1000
        postprocess_start = time.perf_counter()
        arr = out[name]["_output_0"]
        actual_shape = [int(dim) for dim in arr.shape]
        expected_shape = [batch_size, final_logits_seq_len(seq_len, final_logits_mode), vocab_size] if index == 27 else [batch_size, seq_len, hidden_size]
        if actual_shape != expected_shape:
            errors.append(f"shape_mismatch:{name}:expected={expected_shape}:actual={actual_shape}")
        scale = item["output_quant_scale"]
        telemetry = output_telemetry_fields(
            index=index,
            arr=arr,
            scale=scale,
            reusable=hidden_buffer if index != 27 else None,
        )
        output_quant_scale_none_count += 1 if telemetry["output_quant_scale_is_none"] else 0
        output_c_contiguous_count += 1 if telemetry["output_c_contiguous"] else 0
        count_value(output_dtype_counts, telemetry["output_dtype"])
        count_value(hidden_materialize_candidate_mode_counts, telemetry["hidden_materialize_candidate_mode"])
        if index == 27:
            final_logits_shape = actual_shape
            current_hidden = None
            materialize_ms = 0.0
            reused_buffer = False
        else:
            current_hidden, materialize_ms, reused_buffer = materialize_hidden(arr, scale, hidden_buffer)
            materialize_times.append(materialize_ms)
            reused_buffer_count += 1 if reused_buffer else 0
        del out
        output_postprocess_ms = (time.perf_counter() - postprocess_start) * 1000
        output_postprocess_times.append(output_postprocess_ms)
        rows.append(
            {
                "index": index,
                "model_name": name,
                "input_prepare_ms": round(input_prepare_ms, 3),
                "run_ms": round(run_ms, 3),
                "output_postprocess_ms": round(output_postprocess_ms, 3),
                "hidden_materialize_ms": round(materialize_ms, 3) if index != 27 else None,
                "reused_hidden_buffer": reused_buffer if index != 27 else None,
                "output_shape": actual_shape,
                **telemetry,
            }
        )
    return current_hidden, {
        "group_item_ms": round((time.perf_counter() - t0) * 1000, 3),
        "segments": rows,
        "final_logits_shape": final_logits_shape,
        "input_prepare_ms": round(sum(input_prepare_times), 3),
        "output_postprocess_ms": round(sum(output_postprocess_times), 3),
        "hidden_materialize_ms": round(sum(materialize_times), 3),
        "hidden_materialize_count": len(materialize_times),
        "reused_hidden_buffer_count": reused_buffer_count,
        "output_quant_scale_none_count": output_quant_scale_none_count,
        "output_dtype_counts": output_dtype_counts,
        "output_c_contiguous_count": output_c_contiguous_count,
        "hidden_materialize_candidate_mode_counts": hidden_materialize_candidate_mode_counts,
    }, errors


def run_group_segment_major(
    loaded: list[dict[str, Any]],
    token_batches: list[np.ndarray],
    hidden_batches: list[np.ndarray | None],
    hidden_buffers: list[np.ndarray] | None,
    position_ids: np.ndarray,
    batch_size: int,
    seq_len: int,
    hidden_size: int,
    vocab_size: int,
    final_logits_mode: str,
) -> tuple[list[int] | None, list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    segment_rows: list[dict[str, Any]] = []
    final_shape: list[int] | None = None
    microbatch_count = len(token_batches)
    previous_segment_complete: float | None = None

    for item in loaded:
        index = int(item["index"])
        runtime: HB_HBMRuntime = item["runtime"]
        name = str(item["model_name"])
        expected_shape = [batch_size, final_logits_seq_len(seq_len, final_logits_mode), vocab_size] if index == 27 else [batch_size, seq_len, hidden_size]
        run_times: list[float] = []
        input_prepare_times: list[float] = []
        output_postprocess_times: list[float] = []
        materialize_times: list[float] = []
        reused_buffer_count = 0
        output_quant_scale_none_count = 0
        output_c_contiguous_count = 0
        output_dtype_counts: dict[str, int] = {}
        hidden_materialize_candidate_mode_counts: dict[str, int] = {}
        output_dtype: str | None = None
        output_c_contiguous: bool | None = None
        hidden_candidate_mode: str | None = None
        preview: list[dict[str, Any]] = []
        inter_segment_first_run_gap_ms: float | None = None
        intra_segment_run_gap_ms = 0.0
        previous_item_complete: float | None = None
        segment_start = time.perf_counter()
        for item_index in range(microbatch_count):
            prepare_start = time.perf_counter()
            if index == 0:
                inputs = {"_input_0": token_batches[item_index], "_input_1": position_ids}
            else:
                hidden = hidden_batches[item_index]
                if hidden is None:
                    errors.append(f"missing_hidden:microbatch={item_index}:segment={index}")
                    break
                inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": position_ids}

            run_start = time.perf_counter()
            input_prepare_ms = (run_start - prepare_start) * 1000
            input_prepare_times.append(input_prepare_ms)
            if item_index == 0 and previous_segment_complete is not None:
                inter_segment_first_run_gap_ms = (run_start - previous_segment_complete) * 1000
            elif item_index > 0 and previous_item_complete is not None:
                intra_segment_run_gap_ms += (run_start - previous_item_complete) * 1000
            out = runtime.run(inputs, model_name=name)
            run_ms = (time.perf_counter() - run_start) * 1000
            postprocess_start = time.perf_counter()
            arr = out[name]["_output_0"]
            actual_shape = [int(dim) for dim in arr.shape]
            if actual_shape != expected_shape:
                errors.append(f"shape_mismatch:{name}:expected={expected_shape}:actual={actual_shape}")
            scale = item["output_quant_scale"]
            reusable = (
                hidden_buffers[item_index]
                if index != 27 and hidden_buffers is not None
                else None
            )
            telemetry = output_telemetry_fields(
                index=index,
                arr=arr,
                scale=scale,
                reusable=reusable,
            )
            output_quant_scale_none_count += 1 if telemetry["output_quant_scale_is_none"] else 0
            output_c_contiguous_count += 1 if telemetry["output_c_contiguous"] else 0
            output_dtype = telemetry["output_dtype"]
            output_c_contiguous = telemetry["output_c_contiguous"]
            hidden_candidate_mode = telemetry["hidden_materialize_candidate_mode"]
            count_value(output_dtype_counts, output_dtype)
            count_value(hidden_materialize_candidate_mode_counts, hidden_candidate_mode)
            if index == 27:
                final_shape = actual_shape
                hidden_batches[item_index] = None
                materialize_ms = 0.0
                reused_buffer = False
            else:
                hidden, materialize_ms, reused_buffer = materialize_hidden(arr, scale, reusable)
                hidden_batches[item_index] = hidden
                materialize_times.append(materialize_ms)
                reused_buffer_count += 1 if reused_buffer else 0
            output_postprocess_ms = (time.perf_counter() - postprocess_start) * 1000
            output_postprocess_times.append(output_postprocess_ms)
            run_times.append(run_ms)
            if item_index < 2 or item_index >= microbatch_count - 2:
                preview.append(
                    {
                        "microbatch_index": item_index,
                        "input_prepare_ms": round(input_prepare_ms, 3),
                        "run_ms": round(run_ms, 3),
                        "output_postprocess_ms": round(output_postprocess_ms, 3),
                        "hidden_materialize_ms": round(materialize_ms, 3) if index != 27 else None,
                        "reused_hidden_buffer": reused_buffer if index != 27 else None,
                        "output_shape": actual_shape,
                        **telemetry,
                    }
                )
            del out
            previous_item_complete = time.perf_counter()
            if errors:
                break
        segment_complete = time.perf_counter()

        segment_rows.append(
            {
                "index": index,
                "model_name": name,
                "segment_total_ms": round((time.perf_counter() - segment_start) * 1000, 3),
                "avg_run_ms": round(statistics.fmean(run_times), 3) if run_times else None,
                "total_run_ms": round(sum(run_times), 3),
                "input_prepare_ms": round(sum(input_prepare_times), 3),
                "avg_input_prepare_ms": round(statistics.fmean(input_prepare_times), 6) if input_prepare_times else None,
                "output_postprocess_ms": round(sum(output_postprocess_times), 3),
                "avg_output_postprocess_ms": round(statistics.fmean(output_postprocess_times), 6) if output_postprocess_times else None,
                "hidden_materialize_ms": round(sum(materialize_times), 3),
                "hidden_materialize_count": len(materialize_times),
                "reused_hidden_buffer_count": reused_buffer_count,
                "output_quant_scale": item.get("output_quant_scale"),
                "output_quant_scale_is_none": item.get("output_quant_scale") is None,
                "output_quant_scale_none_count": output_quant_scale_none_count,
                "output_dtype": output_dtype,
                "output_dtype_counts": output_dtype_counts,
                "output_c_contiguous": output_c_contiguous,
                "output_c_contiguous_count": output_c_contiguous_count,
                "hidden_materialize_candidate_mode": hidden_candidate_mode,
                "hidden_materialize_candidate_mode_counts": hidden_materialize_candidate_mode_counts,
                "inter_segment_first_run_gap_ms": (
                    round(inter_segment_first_run_gap_ms, 3) if inter_segment_first_run_gap_ms is not None else None
                ),
                "intra_segment_run_gap_ms": round(intra_segment_run_gap_ms, 3) if intra_segment_run_gap_ms else None,
                "completed_microbatch_count": len(run_times),
                "preview": preview,
            }
        )
        previous_segment_complete = segment_complete
        if errors:
            break

    return final_shape, segment_rows, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b2")
    parser.add_argument("--final-hbm-root", default="", help="Optional alternate root for seg27_28 only.")
    parser.add_argument("--report-root", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--groups", default="0:6,6:12,12:18,18:24,24:28")
    parser.add_argument("--microbatch-count", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--seq-len", type=int, default=16)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--monitor-delay-ms", type=int, default=100)
    parser.add_argument("--monitor-samples", type=int, default=5000)
    parser.add_argument("--inner-order", choices=["microbatch-major", "segment-major"], default="microbatch-major")
    parser.add_argument("--preallocate-hidden", action="store_true")
    parser.add_argument("--prewarm-hbm", action="store_true", help="Read each group HBM file before HB_HBMRuntime load.")
    parser.add_argument("--prewarm-chunk-mib", type=int, default=32)
    parser.add_argument("--release-gc-mode", choices=["collect", "skip"], default="collect")
    parser.add_argument("--final-logits-mode", choices=["full", "last-token"], default="full")
    args = parser.parse_args()

    hbm_root = Path(args.hbm_root)
    final_hbm_root = Path(args.final_hbm_root) if args.final_hbm_root else None
    report_root = Path(args.report_root)
    groups = parse_groups(args.groups)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    order_tag = args.inner_order.replace("-", "_")
    run_dir = report_root / f"dream7b_true_batch_group_major_telemetry_{stamp}_{order_tag}_mb{args.microbatch_count}_b{args.batch_size}"
    run_dir.mkdir(parents=True, exist_ok=False)
    monitor_stdout = run_dir / "hrt_ucp_monitor.stdout"
    monitor_stderr = run_dir / "hrt_ucp_monitor.stderr"

    errors: list[str] = []
    group_rows: list[dict[str, Any]] = []
    position_ids = np.tile(np.arange(args.seq_len, dtype=np.int32), (args.batch_size, 1))
    token_batches = [
        np.full((args.batch_size, args.seq_len), fill_value=(1000 + i) % 120000, dtype=np.int32)
        for i in range(args.microbatch_count)
    ]
    hidden_batches: list[np.ndarray | None] = [None] * args.microbatch_count
    hidden_buffers: list[np.ndarray] | None = None
    if args.preallocate_hidden:
        hidden_buffers = [
            np.empty((args.batch_size, args.seq_len, args.hidden_size), dtype=np.float32)
            for _ in range(args.microbatch_count)
        ]
    final_shape: list[int] | None = None

    monitor_proc: subprocess.Popen[str] | None = None
    started = time.perf_counter()
    try:
        with monitor_stdout.open("w", encoding="utf-8") as stdout, monitor_stderr.open("w", encoding="utf-8") as stderr:
            monitor_proc = subprocess.Popen(
                ["hrt_ucp_monitor", "-b", "-e", "bpu", "-d", str(args.monitor_delay_ms), "-n", str(args.monitor_samples)],
                stdout=stdout,
                stderr=stderr,
                text=True,
            )
            time.sleep(max(0.2, args.monitor_delay_ms / 1000.0 * 2))
            for group_start, group_end in groups:
                group_loop_start = time.perf_counter()
                prewarm_row: dict[str, Any] = {}
                if args.prewarm_hbm:
                    prewarm_row = prewarm_hbm_files(
                        group_hbm_paths(
                            hbm_root,
                            final_hbm_root,
                            group_start,
                            group_end,
                            args.seq_len,
                            args.batch_size,
                            args.w_bits,
                            args.final_logits_mode,
                        ),
                        max(1, args.prewarm_chunk_mib) * 1024 * 1024,
                    )
                load_start = time.perf_counter()
                loaded = load_group(
                    hbm_root,
                    final_hbm_root,
                    group_start,
                    group_end,
                    args.seq_len,
                    args.batch_size,
                    args.w_bits,
                    args.final_logits_mode,
                )
                group_load_ms = (time.perf_counter() - load_start) * 1000
                if args.inner_order == "microbatch-major":
                    item_times: list[float] = []
                    hidden_materialize_ms = 0.0
                    hidden_materialize_count = 0
                    reused_hidden_buffer_count = 0
                    output_quant_scale_none_count = 0
                    output_c_contiguous_count = 0
                    output_dtype_counts: dict[str, int] = {}
                    hidden_materialize_candidate_mode_counts: dict[str, int] = {}
                    input_prepare_ms = 0.0
                    output_postprocess_ms = 0.0
                    preview: list[dict[str, Any]] = []
                    for item_index in range(args.microbatch_count):
                        hidden, item_row, item_errors = run_group_for_item(
                            loaded,
                            token_batches[item_index],
                            hidden_batches[item_index],
                            hidden_buffers[item_index] if hidden_buffers is not None else None,
                            position_ids,
                            args.batch_size,
                            args.seq_len,
                            args.hidden_size,
                            args.vocab_size,
                            args.final_logits_mode,
                        )
                        if hidden is not None:
                            hidden_batches[item_index] = hidden
                        if item_row.get("final_logits_shape") is not None:
                            final_shape = item_row["final_logits_shape"]
                        item_times.append(float(item_row["group_item_ms"]))
                        input_prepare_ms += float(item_row.get("input_prepare_ms") or 0.0)
                        output_postprocess_ms += float(item_row.get("output_postprocess_ms") or 0.0)
                        hidden_materialize_ms += float(item_row.get("hidden_materialize_ms") or 0.0)
                        hidden_materialize_count += int(item_row.get("hidden_materialize_count") or 0)
                        reused_hidden_buffer_count += int(item_row.get("reused_hidden_buffer_count") or 0)
                        output_quant_scale_none_count += int(
                            item_row.get("output_quant_scale_none_count") or 0
                        )
                        output_c_contiguous_count += int(
                            item_row.get("output_c_contiguous_count") or 0
                        )
                        merge_counts(
                            output_dtype_counts,
                            item_row.get("output_dtype_counts") or {},
                        )
                        merge_counts(
                            hidden_materialize_candidate_mode_counts,
                            item_row.get("hidden_materialize_candidate_mode_counts")
                            or {},
                        )
                        if item_index < 2 or item_index >= args.microbatch_count - 2:
                            preview.append({"microbatch_index": item_index, **item_row})
                        errors.extend(item_errors)
                        if item_errors:
                            break
                    group_rows.append(
                        {
                            "group_start": group_start,
                            "group_end": group_end,
                            **prewarm_row,
                            "group_load_ms": round(group_load_ms, 3),
                            "loaded_count": len(loaded),
                            "loaded_segments": loaded_segment_summary(loaded),
                            "avg_item_ms": round(statistics.fmean(item_times), 3) if item_times else None,
                            "total_item_ms": round(sum(item_times), 3),
                            "input_prepare_ms": round(input_prepare_ms, 3),
                            "output_postprocess_ms": round(output_postprocess_ms, 3),
                            "hidden_materialize_ms": round(hidden_materialize_ms, 3),
                            "hidden_materialize_count": hidden_materialize_count,
                            "reused_hidden_buffer_count": reused_hidden_buffer_count,
                            "output_quant_scale_none_count": output_quant_scale_none_count,
                            "output_dtype_counts": output_dtype_counts,
                            "output_c_contiguous_count": output_c_contiguous_count,
                            "hidden_materialize_candidate_mode_counts": hidden_materialize_candidate_mode_counts,
                            "preview": preview,
                        }
                    )
                else:
                    group_final_shape, segment_rows, segment_errors = run_group_segment_major(
                        loaded,
                        token_batches,
                        hidden_batches,
                        hidden_buffers,
                        position_ids,
                        args.batch_size,
                        args.seq_len,
                        args.hidden_size,
                        args.vocab_size,
                        args.final_logits_mode,
                    )
                    if group_final_shape is not None:
                        final_shape = group_final_shape
                    errors.extend(segment_errors)
                    group_rows.append(
                        {
                            "group_start": group_start,
                            "group_end": group_end,
                            **prewarm_row,
                            "group_load_ms": round(group_load_ms, 3),
                            "loaded_count": len(loaded),
                            "loaded_segments": loaded_segment_summary(loaded),
                            "segment_rows": segment_rows,
                        }
                    )
                release_start = time.perf_counter()
                del loaded
                if args.release_gc_mode == "collect":
                    gc.collect()
                group_release_ms = (time.perf_counter() - release_start) * 1000
                group_loop_ms = (time.perf_counter() - group_loop_start) * 1000
                group_rows[-1]["group_release_ms"] = round(group_release_ms, 3)
                group_rows[-1]["release_gc_mode"] = args.release_gc_mode
                group_rows[-1]["group_loop_ms"] = round(group_loop_ms, 3)
                if errors:
                    break
    except Exception as exc:
        errors.append(f"exception:{type(exc).__name__}:{exc}")
    finally:
        if monitor_proc is not None and monitor_proc.poll() is None:
            monitor_proc.terminate()
            try:
                monitor_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                monitor_proc.kill()
                monitor_proc.wait(timeout=5)

    wall_ms = (time.perf_counter() - started) * 1000
    monitor_text = monitor_stdout.read_text(encoding="utf-8", errors="replace") if monitor_stdout.exists() else ""
    samples = parse_bpu_samples(monitor_text)
    nonzero = [item for item in samples if item > 0.0]
    if not samples:
        errors.append("no_bpu_monitor_samples")
    expected_final_shape = [args.batch_size, final_logits_seq_len(args.seq_len, args.final_logits_mode), args.vocab_size]
    if final_shape != expected_final_shape and not errors:
        errors.append(f"final_shape={final_shape}")

    processed_microbatches = args.microbatch_count if final_shape == expected_final_shape else 0
    timing_summary = summarize_group_rows(group_rows, wall_ms)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ok_dream7b_true_batch_group_major_telemetry" if not errors else "failed_dream7b_true_batch_group_major_telemetry",
        "runtime_version": getattr(HB_HBMRuntime, "version", None),
        "hbm_root": str(hbm_root),
        "final_hbm_root": str(final_hbm_root) if final_hbm_root is not None else None,
        "groups": [{"start": start, "end": end} for start, end in groups],
        "inner_order": args.inner_order,
        "preallocate_hidden": args.preallocate_hidden,
        "prewarm_hbm": args.prewarm_hbm,
        "prewarm_chunk_mib": args.prewarm_chunk_mib,
        "release_gc_mode": args.release_gc_mode,
        "final_logits_mode": args.final_logits_mode,
        "microbatch_count": args.microbatch_count,
        "batch_size": args.batch_size,
        "processed_request_count": processed_microbatches * args.batch_size,
        "failed_job_count": 0 if not errors else 1,
        "expected_final_shape": expected_final_shape,
        "final_shape": final_shape,
        "wall_ms": round(wall_ms, 3),
        "amortized_wall_ms_per_request": round(wall_ms / max(1, processed_microbatches * args.batch_size), 3),
        "bpu_loading_sample_count": len(samples),
        "nonzero_bpu_loading_sample_count": len(nonzero),
        "avg_bpu_loading": round(statistics.fmean(samples), 3) if samples else 0.0,
        "avg_nonzero_bpu_loading": round(statistics.fmean(nonzero), 3) if nonzero else 0.0,
        "max_bpu_loading": max(samples) if samples else 0.0,
        "group_rows": group_rows,
        "timing_summary": timing_summary,
        "errors": errors,
    }
    report_json = run_dir / "true_batch_group_major_telemetry.json"
    report_md = run_dir / "true_batch_group_major_telemetry.md"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Dream7B True Batch Group-Major Telemetry",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- hbm_root: {payload['hbm_root']}",
        f"- final_hbm_root: {payload['final_hbm_root']}",
        f"- inner_order: {payload['inner_order']}",
        f"- preallocate_hidden: {payload['preallocate_hidden']}",
        f"- prewarm_hbm: {payload['prewarm_hbm']}",
        f"- prewarm_chunk_mib: {payload['prewarm_chunk_mib']}",
        f"- release_gc_mode: {payload['release_gc_mode']}",
        f"- final_logits_mode: {payload['final_logits_mode']}",
        f"- microbatch_count: {payload['microbatch_count']}",
        f"- processed_request_count: {payload['processed_request_count']}",
        f"- expected_final_shape: {payload['expected_final_shape']}",
        f"- final_shape: {payload['final_shape']}",
        f"- wall_ms: {payload['wall_ms']}",
        f"- amortized_wall_ms_per_request: {payload['amortized_wall_ms_per_request']}",
        f"- avg_bpu_loading: {payload['avg_bpu_loading']}",
        f"- avg_nonzero_bpu_loading: {payload['avg_nonzero_bpu_loading']}",
        f"- max_bpu_loading: {payload['max_bpu_loading']}",
        f"- total_group_load_ms: {timing_summary['total_group_load_ms']}",
        f"- total_hbm_prewarm_ms: {timing_summary['total_hbm_prewarm_ms']}",
        f"- total_hbm_prewarm_mib: {timing_summary['total_hbm_prewarm_mib']}",
        f"- total_segment_run_ms: {timing_summary['total_segment_run_ms']}",
        f"- total_segment_total_ms: {timing_summary['total_segment_total_ms']}",
        f"- total_segment_overhead_ms: {timing_summary['total_segment_overhead_ms']}",
        f"- total_group_release_ms: {timing_summary['total_group_release_ms']}",
        f"- total_input_prepare_ms: {timing_summary['total_input_prepare_ms']}",
        f"- input_prepare_fraction_of_wall: {timing_summary['input_prepare_fraction_of_wall']}",
        f"- total_output_postprocess_ms: {timing_summary['total_output_postprocess_ms']}",
        f"- output_postprocess_fraction_of_wall: {timing_summary['output_postprocess_fraction_of_wall']}",
        f"- total_hidden_materialize_ms: {timing_summary['total_hidden_materialize_ms']}",
        f"- hidden_materialize_ms_per_item: {timing_summary['hidden_materialize_ms_per_item']}",
        f"- reused_hidden_buffer_count: {timing_summary['reused_hidden_buffer_count']}",
        f"- output_quant_scale_none_count: {timing_summary['output_quant_scale_none_count']}",
        f"- output_dtype_counts: {timing_summary['output_dtype_counts']}",
        f"- output_c_contiguous_count: {timing_summary['output_c_contiguous_count']}",
        f"- hidden_materialize_candidate_mode_counts: {timing_summary['hidden_materialize_candidate_mode_counts']}",
        f"- estimated_host_gap_ms: {timing_summary['estimated_host_gap_ms']}",
        f"- estimated_unaccounted_gap_ms: {timing_summary['estimated_unaccounted_gap_ms']}",
        f"- final_vs_hidden_avg_run_ratio: {timing_summary['final_vs_hidden_avg_run_ratio']}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_json, flush=True)
    print(report_md, flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
