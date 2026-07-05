#!/usr/bin/env python3
"""Dream7B/S100P v18 seg00_01 position-derived path probe.

Runs only the offline seg00_01 HBM and optional HRT intermediate dumps. It does
not call generation APIs, product routes, or OpenClaw foreground traffic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def stats(x: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(x)
    if arr.size == 0:
        return {"shape": list(arr.shape), "dtype": str(arr.dtype), "size": 0}
    finite = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    return {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "size": int(arr.size),
        "min": float(np.min(finite)) if finite.size else None,
        "max": float(np.max(finite)) if finite.size else None,
        "mean": float(np.mean(finite)) if finite.size else None,
        "std": float(np.std(finite)) if finite.size else None,
        "abs_max": float(np.max(np.abs(finite))) if finite.size else None,
        "nonzero_count": int(np.count_nonzero(arr)),
        "allzero": bool(np.count_nonzero(arr) == 0),
        "constant": bool(arr.size > 0 and np.all(arr == arr.flat[0])),
        "nan_count": int(np.isnan(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
        "inf_count": int(np.isinf(arr).sum()) if np.issubdtype(arr.dtype, np.floating) else 0,
    }


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "sha256": sha256_file(path), "stats": stats(arr)}


def quant_metadata(runtime: Any, model_name: str) -> dict[str, Any]:
    try:
        qp = runtime.output_quants[model_name]["_output_0"]
        scale = np.asarray(getattr(qp, "scale", [])).reshape(-1)
        zero = getattr(qp, "zero_point", None)
        return {
            "available": True,
            "scale": scale.astype(float).tolist(),
            "scale_first": float(scale[0]) if scale.size else None,
            "zero_point": np.asarray(zero).reshape(-1).astype(float).tolist() if zero is not None else None,
            "repr": repr(qp),
        }
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}:{exc}"}


def position_variants(n: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(20260704)
    variants: dict[str, np.ndarray] = {
        "all_zero": np.zeros(n, dtype=np.int32),
        "all_one": np.ones(n, dtype=np.int32),
        "canonical": np.arange(n, dtype=np.int32),
        "reversed": np.arange(n - 1, -1, -1, dtype=np.int32),
        "random_permutation": rng.permutation(n).astype(np.int32),
    }
    for k in [0, 1, 2, 4, 8, 16, 32, 64, 127]:
        variants[f"constant_{k}"] = np.full(n, k, dtype=np.int32)
    for idx in [0, 1, 2, 64, 127]:
        for val in [1, 2, 64, 127]:
            arr = np.zeros(n, dtype=np.int32)
            arr[idx] = val
            variants[f"single_spike_index_{idx:03d}_value_{val:03d}"] = arr
    return variants


def run_command(cmd: list[str], log_path: Path, timeout: int = 240, env: dict[str, str] | None = None) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    started = time.time()
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=merged_env)
        log_path.write_text(
            "COMMAND: " + " ".join(cmd) + "\n"
            + "ENV_OVERRIDES: " + json.dumps(env or {}, ensure_ascii=False) + "\n\n"
            + "STDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr,
            encoding="utf-8",
            errors="ignore",
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout_len": len(proc.stdout),
            "stderr_len": len(proc.stderr),
            "log_path": str(log_path),
            "log_sha256": sha256_file(log_path),
        }
    except Exception as exc:
        log_path.write_text(f"COMMAND: {' '.join(cmd)}\nEXCEPTION: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        return {"cmd": cmd, "exception": type(exc).__name__, "message": str(exc), "elapsed_seconds": round(time.time() - started, 3), "log_path": str(log_path)}


def file_listing(root: Path) -> list[dict[str, Any]]:
    rows = []
    if not root.exists():
        return rows
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rows.append({"path": str(p), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    return rows


def run_hrt_add_input0_dump(args: argparse.Namespace, case: dict[str, Any], case_dir: Path) -> dict[str, Any]:
    input_dir = case_dir / "hrt_inputs"
    dump_dir = case_dir / "hrt_all_zero_dump_npy"
    if dump_dir.exists():
        shutil.rmtree(dump_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    dump_dir.mkdir(parents=True, exist_ok=True)
    np.save(input_dir / "input_0_tokens.npy", np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len))
    np.save(input_dir / "input_1_positions_all_zero.npy", np.zeros(args.seq_len, dtype=np.int32))
    cmd = [
        "hrt_model_exec",
        "infer",
        "--model_file",
        str(Path(args.hbm)),
        "--model_name",
        args.model_name,
        "--input_file",
        f"{input_dir / 'input_0_tokens.npy'},{input_dir / 'input_1_positions_all_zero.npy'}",
        "--frame_count",
        "1",
        "--dump_intermediate",
        "1",
        "--enable_dump",
        "true",
        "--dump_path",
        str(dump_dir),
        "--dump_format",
        "npy",
    ]
    row = run_command(cmd, case_dir / "hrt_all_zero_dump_npy.log", timeout=args.hrt_timeout, env={"HBRT_LOG_LEVEL": "debug", "DNN_LOG_LEVEL": "6", "UCPT_LOG_LEVEL": "6"})
    names = file_listing(dump_dir)
    row["dump_file_listing"] = names
    row["gathernd_or_add_input0_files"] = [x for x in names if "GatherND" in x["path"] or "qnt.const_fake_quant" in x["path"] or "hbir.add_id_137_bpu_segment_3-input-0" in x["path"]]
    row["add_input1_files"] = [x for x in names if "input-1" in x["path"] or "input_1" in x["path"]]
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken/seg00_01/dream7b_segment_0_1_seq128_q8.hbm")
    ap.add_argument("--model-name", default="dream_segment_00_01")
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--fallback-output-scale", type=float, default=6.062494503566995e-05)
    ap.add_argument("--hrt-timeout", type=int, default=300)
    ap.add_argument("--skip-hrt-dump", action="store_true")
    args = ap.parse_args()

    from hbm_runtime import HB_HBMRuntime

    started = time.time()
    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v18_position_path_recovery_remote",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": dict(SAFETY),
        "rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(out_root / "position_path_recovery_report.json", report)
    try:
        runtime = HB_HBMRuntime(str(Path(args.hbm)))
        qmeta = quant_metadata(runtime, args.model_name)
        scale = float(qmeta.get("scale_first") or args.fallback_output_scale)
        report["quant_metadata"] = qmeta
        report["dequant_domain"] = {"tensor": "seg00_01 add/model output", "scale": scale, "zero_point_assumed": 0}
        cases = [c for c in read_jsonl(Path(args.cases)) if c.get("case_id") in CASE_IDS]
        variants = position_variants(args.seq_len)
        report["variant_names"] = list(variants.keys())
        for case in cases:
            cid = case["case_id"]
            case_dir = out_root / cid
            token_ids = np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len)
            save_array(case_dir / "input_0_tokens.npy", token_ids)
            hrt_row = None if args.skip_hrt_dump else run_hrt_add_input0_dump(args, case, case_dir)
            zero_deq = None
            variant_rows = []
            for name, positions in variants.items():
                vdir = case_dir / "position_variants" / name
                output = runtime.run({"_input_0": token_ids, "_input_1": positions}, model_name=args.model_name)
                raw = output[args.model_name]["_output_0"]
                deq = raw.astype(np.float32, copy=False) * scale
                if name == "all_zero":
                    zero_deq = deq.copy()
                row = {
                    "case_id": cid,
                    "variant": name,
                    "positions": save_array(vdir / "positions.npy", positions),
                    "add_output_raw": save_array(vdir / "add_output_raw.npy", raw),
                    "add_output_dequant": save_array(vdir / "add_output_dequant.npy", deq),
                }
                variant_rows.append(row)
                write_json(vdir / "metadata.json", row)
            if zero_deq is not None:
                for row in variant_rows:
                    deq = np.load(row["add_output_dequant"]["path"])
                    delta = deq - zero_deq
                    vdir = case_dir / "position_variants" / row["variant"]
                    row["delta_vs_all_zero"] = save_array(vdir / "delta_vs_all_zero.npy", delta)
                    row["delta_norm"] = float(np.linalg.norm(delta.reshape(-1)))
                    row["delta_abs_max"] = float(np.max(np.abs(delta)))
                    write_json(vdir / "metadata.json", row)
            case_meta = {
                "case_id": cid,
                "token_ids_sha256": case.get("token_ids_sha256"),
                "hrt_add_input0_dump": hrt_row,
                "variants": variant_rows,
            }
            write_json(case_dir / "metadata.json", case_meta)
            report["rows"].append({"case_id": cid, "variant_count": len(variant_rows), "hrt_add_input0_dump": hrt_row})
            report["status"] = "running"
            write_json(out_root / "position_path_recovery_report.json", report)
        report["status"] = "pass" if len(report["rows"]) == len(CASE_IDS) else "partial"
        del runtime
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(out_root / "position_path_recovery_report.json", report)
    (out_root / "position_path_recovery_report.md").write_text(
        "# v18 Position Path Recovery Remote\n\n"
        f"- status: `{report.get('status')}`\n"
        f"- rows: `{len(report.get('rows', []))}`\n"
        f"- errors: `{len(report.get('errors', []))}`\n"
        "- generation_quality_run: `False`\n"
        "- product_routes_18888_18889_touched: `False`\n",
        encoding="utf-8",
    )
    print(out_root / "position_path_recovery_report.json", flush=True)
    return 0 if report.get("rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
