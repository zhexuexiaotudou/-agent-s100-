#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from dream7b_research_common import iter_jsonl, now_iso, softmax_stats, tensor_stats, topk, write_json, write_text
from hbm_runtime import HB_HBMRuntime


def final_suffix(index: int, final_logits_mode: str) -> str:
    return "_last_token_logits" if index == 27 and final_logits_mode == "last-token" else ""


def hbm_path(args: argparse.Namespace, index: int) -> Path:
    end = index + 1
    lm = f"_lmheadq{args.lm_head_w_bits}" if index == 27 and args.lm_head_w_bits != args.w_bits else ""
    name = f"dream7b_segment_{index}_{end}_seq{args.seq_len}_q{args.w_bits}{lm}{final_suffix(index, args.final_logits_mode)}.hbm"
    return Path(args.hbm_root) / f"seg{index:02d}_{end:02d}" / name


def model_name(args: argparse.Namespace, index: int) -> str:
    return f"dream_segment_{index:02d}_{index+1:02d}{final_suffix(index, args.final_logits_mode)}"


def quant_metadata(runtime: HB_HBMRuntime, name: str) -> dict[str, Any]:
    meta: dict[str, Any] = {"available": False}
    try:
        quant = runtime.output_quants[name]["_output_0"]
        scale = np.asarray(getattr(quant, "scale", [])).reshape(-1)
        zero = getattr(quant, "zero_point", None)
        meta.update(
            {
                "available": True,
                "scale": scale.astype(float).tolist(),
                "scale_first": float(scale[0]) if scale.size else None,
                "zero_point": np.asarray(zero).reshape(-1).astype(float).tolist() if zero is not None else None,
                "repr": repr(quant),
            }
        )
    except Exception as exc:
        meta["error"] = f"{type(exc).__name__}:{exc}"
    return meta


def run_case(args: argparse.Namespace, case: dict[str, Any], out_root: Path) -> dict[str, Any]:
    case_id = case["case_id"]
    case_dir = out_root / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    hidden: np.ndarray | None = None
    pos = np.arange(args.seq_len, dtype=np.int32)
    rows = []
    log_lines = []
    final_raw = None
    final_dequant = None
    final_meta = None
    for index in range(args.layer_count):
        path = hbm_path(args, index)
        name = model_name(args, index)
        started = time.perf_counter()
        runtime = HB_HBMRuntime(str(path))
        load_ms = (time.perf_counter() - started) * 1000
        if index == 0:
            inputs = {"_input_0": np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len), "_input_1": pos}
        else:
            if hidden is None:
                raise RuntimeError(f"missing hidden for segment {index}")
            inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": pos}
        run_started = time.perf_counter()
        output = runtime.run(inputs, model_name=name)
        run_ms = (time.perf_counter() - run_started) * 1000
        raw = output[name]["_output_0"]
        qmeta = quant_metadata(runtime, name)
        scale = qmeta.get("scale_first")
        dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
        row = {
            "segment": index,
            "model_name": name,
            "hbm_path": str(path),
            "load_ms": round(load_ms, 3),
            "run_ms": round(run_ms, 3),
            "raw_stats": tensor_stats(raw),
            "dequant_stats": tensor_stats(dequant),
            "quant_metadata": qmeta,
        }
        rows.append(row)
        log_lines.append(f"seg={index} model={name} raw_shape={raw.shape} scale={scale} load_ms={load_ms:.3f} run_ms={run_ms:.3f}")
        if index == args.layer_count - 1:
            final_raw = raw.copy()
            final_dequant = dequant.reshape(-1).copy()
            final_meta = row
        else:
            hidden = dequant.copy()
        del output
        del runtime
        gc.collect()
    if final_raw is None or final_dequant is None or final_meta is None:
        raise RuntimeError("missing final output")
    np.save(case_dir / "raw_output.npy", final_raw)
    np.save(case_dir / "dequant_logits.npy", final_dequant)
    metadata = {
        "case_id": case_id,
        "token_count": len(case["token_ids"]),
        "final_tensor_shape": [int(x) for x in final_raw.shape],
        "final_raw_output": str(case_dir / "raw_output.npy"),
        "final_dequant_logits": str(case_dir / "dequant_logits.npy"),
        "final_segment": final_meta,
        "top5": topk(final_dequant, 5),
        "softmax": softmax_stats(final_dequant),
        "blocking_anomaly": bool(tensor_stats(final_raw)["constant"] or softmax_stats(final_dequant)["normalized_entropy"] > args.max_normalized_entropy),
    }
    write_json(case_dir / "tensor_metadata.json", metadata)
    write_text(case_dir / "runtime_log.txt", "\n".join(log_lines) + "\n")
    return {
        "case_id": case_id,
        "case_dir": str(case_dir),
        "segment_count": len(rows),
        "total_load_ms": round(sum(float(r["load_ms"]) for r in rows), 3),
        "total_run_ms": round(sum(float(r["run_ms"]) for r in rows), 3),
        "final_tensor_metadata": metadata,
    }


def run_cases_segment_major(args: argparse.Namespace, cases: list[dict[str, Any]], out_root: Path) -> list[dict[str, Any]]:
    states: dict[str, np.ndarray | None] = {case["case_id"]: None for case in cases}
    segment_rows: dict[str, list[dict[str, Any]]] = {case["case_id"]: [] for case in cases}
    final_metadata: dict[str, dict[str, Any]] = {}
    pos = np.arange(args.seq_len, dtype=np.int32)
    for index in range(args.layer_count):
        path = hbm_path(args, index)
        name = model_name(args, index)
        load_started = time.perf_counter()
        runtime = HB_HBMRuntime(str(path))
        load_ms = (time.perf_counter() - load_started) * 1000
        qmeta = quant_metadata(runtime, name)
        scale = qmeta.get("scale_first")
        for case in cases:
            case_id = case["case_id"]
            case_dir = out_root / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            if index == 0:
                inputs = {"_input_0": np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len), "_input_1": pos}
            else:
                hidden = states[case_id]
                if hidden is None:
                    raise RuntimeError(f"missing hidden for {case_id} segment {index}")
                inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": pos}
            run_started = time.perf_counter()
            output = runtime.run(inputs, model_name=name)
            run_ms = (time.perf_counter() - run_started) * 1000
            raw = output[name]["_output_0"]
            dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
            row = {
                "segment": index,
                "model_name": name,
                "hbm_path": str(path),
                "load_ms": round(load_ms, 3),
                "run_ms": round(run_ms, 3),
                "raw_stats": tensor_stats(raw),
                "dequant_stats": tensor_stats(dequant),
                "quant_metadata": qmeta,
            }
            segment_rows[case_id].append(row)
            if index == args.layer_count - 1:
                np.save(case_dir / "raw_output.npy", raw)
                np.save(case_dir / "dequant_logits.npy", dequant.reshape(-1))
                meta = {
                    "case_id": case_id,
                    "token_count": len(case["token_ids"]),
                    "final_tensor_shape": [int(x) for x in raw.shape],
                    "final_raw_output": str(case_dir / "raw_output.npy"),
                    "final_dequant_logits": str(case_dir / "dequant_logits.npy"),
                    "final_segment": row,
                    "top5": topk(dequant.reshape(-1), 5),
                    "softmax": softmax_stats(dequant.reshape(-1)),
                    "blocking_anomaly": bool(tensor_stats(raw)["constant"] or softmax_stats(dequant.reshape(-1))["normalized_entropy"] > args.max_normalized_entropy),
                }
                write_json(case_dir / "tensor_metadata.json", meta)
                write_text(case_dir / "runtime_log.txt", "\n".join(f"seg={r['segment']} model={r['model_name']} scale={r['quant_metadata'].get('scale_first')} load_ms={r['load_ms']} run_ms={r['run_ms']}" for r in segment_rows[case_id]) + "\n")
                final_metadata[case_id] = meta
            else:
                states[case_id] = dequant.copy()
            del output
        del runtime
        gc.collect()
    rows = []
    for case in cases:
        case_id = case["case_id"]
        rows.append(
            {
                "case_id": case_id,
                "case_dir": str(out_root / case_id),
                "segment_count": len(segment_rows[case_id]),
                "total_load_ms": round(sum(float(r["load_ms"]) for r in segment_rows[case_id]), 3),
                "total_run_ms": round(sum(float(r["run_ms"]) for r in segment_rows[case_id]), 3),
                "final_tensor_metadata": final_metadata[case_id],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S100P seq128 HBM chain and dump raw/dequant final logits.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--layer-count", type=int, default=28)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", default="last-token")
    parser.add_argument("--max-normalized-entropy", type=float, default=0.95)
    parser.add_argument("--execution-order", choices=["segment-major", "case-major"], default="segment-major")
    args = parser.parse_args()
    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    errors = []
    cases = list(iter_jsonl(Path(args.cases)))
    if args.execution_order == "segment-major":
        try:
            rows = run_cases_segment_major(args, cases, out_root)
            for row in rows:
                print(row["case_id"], row["final_tensor_metadata"]["softmax"], flush=True)
        except Exception as exc:
            errors.append(f"segment_major:{type(exc).__name__}:{exc}")
    else:
        for case in cases:
            try:
                row = run_case(args, case, out_root)
                rows.append(row)
                print(row["case_id"], row["final_tensor_metadata"]["softmax"], flush=True)
            except Exception as exc:
                errors.append(f"{case['case_id']}:{type(exc).__name__}:{exc}")
                break
    anomalies = [r["case_id"] for r in rows if r["final_tensor_metadata"].get("blocking_anomaly")]
    payload = {
        "created_at": now_iso(),
        "verdict": "blocked_s100p_dump_logits_anomaly" if anomalies else ("ok_s100p_dump_logits" if not errors else "failed_s100p_dump_logits"),
        "runtime_version": getattr(HB_HBMRuntime, "version", None),
        "hbm_root": args.hbm_root,
        "case_count": len(rows),
        "blocking_anomaly_cases": anomalies,
        "errors": errors,
        "cases": rows,
    }
    write_json(Path(args.report_json), payload)
    lines = ["# S100P BPU Dump Logits", "", f"- verdict: `{payload['verdict']}`", f"- case_count: `{len(rows)}`", "", "| case | raw constant | entropy | top1 prob | top1 |", "| --- | --- | ---: | ---: | ---: |"]
    for row in rows:
        meta = row["final_tensor_metadata"]
        stats = meta["final_segment"]["raw_stats"]
        soft = meta["softmax"]
        top = meta["top5"][0]["token"] if meta["top5"] else None
        lines.append(f"| `{row['case_id']}` | {stats['constant']} | {soft['normalized_entropy']:.6f} | {soft['top1_probability']:.8f} | {top} |")
    lines.extend(["", "## Errors", ""])
    lines.extend(f"- `{e}`" for e in errors) if errors else lines.append("- none")
    write_text(Path(args.report_md), "\n".join(lines) + "\n")
    print(args.report_json)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
