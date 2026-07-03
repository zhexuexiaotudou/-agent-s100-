#!/usr/bin/env python3
"""Dream7B/S100P v14 seg00_01 exact HRT dump and position audit.

Offline boundary-only probes. No generation and no product route interaction.
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

from run_v12r_remote_reconstruction import (
    CASE_IDS,
    hbm_path,
    iter_jsonl,
    model_name,
    quant_metadata,
    sha256_file,
    stats,
    write_json,
)


POSITION_VARIANTS = {
    "canonical_0_to_127": lambda n: np.arange(n, dtype=np.int32),
    "all_zero_positions": lambda n: np.zeros(n, dtype=np.int32),
    "all_one_positions": lambda n: np.ones(n, dtype=np.int32),
    "one_indexed_1_to_128": lambda n: np.arange(1, n + 1, dtype=np.int32),
    "reverse_127_to_0": lambda n: np.arange(n - 1, -1, -1, dtype=np.int32),
    "doubled_positions": lambda n: (np.arange(n, dtype=np.int32) * 2),
    "random_permutation_positions": lambda n: np.random.default_rng(20260703).permutation(n).astype(np.int32),
}


def write_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "sha256": sha256_file(path), "stats": stats(arr)}


def copy_bin(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"path": str(dst), "sha256": sha256_file(dst), "size_bytes": dst.stat().st_size}


def find_one(root: Path, contains: list[str], size: int | None = None) -> Path | None:
    matches = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        s = str(p)
        if all(x in s for x in contains) and (size is None or p.stat().st_size == size):
            matches.append(p)
    return sorted(matches, key=lambda x: str(x))[0] if matches else None


def run_hrt_dump(args: argparse.Namespace, case: dict[str, Any], case_dir: Path) -> dict[str, Any]:
    hbm = hbm_path(Path(args.hbm_root), 0, args.seq_len, args.w_bits, args.lm_head_w_bits, args.final_logits_mode)
    name = model_name(0, args.final_logits_mode)
    input_dir = case_dir / "hrt_inputs"
    dump_dir = case_dir / "hrt_dump_raw"
    input_dir.mkdir(parents=True, exist_ok=True)
    if dump_dir.exists():
        shutil.rmtree(dump_dir)
    dump_dir.mkdir(parents=True)
    token_ids = np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len)
    positions = np.arange(args.seq_len, dtype=np.int32)
    np.save(input_dir / "input_0_tokens.npy", token_ids)
    np.save(input_dir / "input_1_positions.npy", positions)
    cmd = [
        "hrt_model_exec",
        "infer",
        "--model_file",
        str(hbm),
        "--model_name",
        name,
        "--input_file",
        f"{input_dir / 'input_0_tokens.npy'},{input_dir / 'input_1_positions.npy'}",
        "--frame_count",
        "1",
        "--dump_intermediate",
        "1",
        "--enable_dump",
        "true",
        "--dump_path",
        str(dump_dir),
        "--dump_format",
        "bin",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=args.hrt_timeout_seconds)
    log_text = "COMMAND: " + " ".join(cmd) + "\n\nSTDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr
    (case_dir / "hrt_dump_command.log").write_text(log_text, encoding="utf-8")
    token_info = write_array(case_dir / "input_0_tokens.npy", token_ids)
    pos_info = write_array(case_dir / "input_1_positions.npy", positions)

    gather_bin = find_one(dump_dir, ["GatherND", "output"], size=args.seq_len * args.hidden_size)
    gather_in_bin = find_one(dump_dir, ["GatherND", "input"], size=args.seq_len * 4)
    add_in_bin = find_one(dump_dir, ["add_id", "input"], size=args.seq_len * args.hidden_size)
    add_out_bin = find_one(dump_dir, ["add_id", "output"], size=args.seq_len * args.hidden_size * 2)
    model_out_bin = find_one(dump_dir, ["model_infer_output"], size=args.seq_len * args.hidden_size * 2)
    mul_in_bin = find_one(dump_dir, ["mul_id", "input"], size=args.seq_len * 4)
    copied: dict[str, Any] = {}
    if gather_bin:
        copied["gathernd_output_raw_bin"] = copy_bin(gather_bin, case_dir / "gathernd_output_raw.bin")
        gather_i8 = np.fromfile(gather_bin, dtype=np.int8).reshape(args.seq_len, args.hidden_size)
        copied["gathernd_output_interpreted"] = write_array(case_dir / "gathernd_output_interpreted.npy", gather_i8.astype(np.float32))
    if gather_in_bin:
        copied["gathernd_input_indices"] = write_array(case_dir / "gathernd_input_indices.npy", np.fromfile(gather_in_bin, dtype=np.int32).reshape(1, args.seq_len))
    if mul_in_bin:
        copied["mul_input"] = write_array(case_dir / "mul_input.npy", np.fromfile(mul_in_bin, dtype=np.int32))
    if add_in_bin:
        copied["add_input_embedding_raw_bin"] = copy_bin(add_in_bin, case_dir / "add_input_embedding_raw.bin")
        copied["add_input_embedding"] = write_array(case_dir / "add_input_embedding.npy", np.fromfile(add_in_bin, dtype=np.int8).reshape(args.seq_len, args.hidden_size).astype(np.float32))
    if add_out_bin:
        copied["add_output_raw_bin"] = copy_bin(add_out_bin, case_dir / "add_output_raw.bin")
        add_raw = np.fromfile(add_out_bin, dtype=np.int16).reshape(args.seq_len, args.hidden_size)
        copied["add_output_raw"] = write_array(case_dir / "add_output_raw.npy", add_raw)
        copied["add_output_dequant"] = write_array(case_dir / "add_output_dequant.npy", add_raw.astype(np.float32) * args.output_scale)
    if model_out_bin:
        copied["model_infer_output_raw_bin"] = copy_bin(model_out_bin, case_dir / "model_infer_output_raw.bin")
    limitations = []
    if not find_one(dump_dir, ["mul_id", "output"]):
        limitations.append("mul_output was not dumped by hrt_model_exec; only hbir.mul input was visible.")
    if not find_one(dump_dir, ["add_id", "input"], size=args.seq_len * args.hidden_size * 2):
        limitations.append("separate add_input_position tensor was not dumped; only add input-0 and add output were visible.")
    return {
        "case_id": case["case_id"],
        "command": cmd,
        "returncode": proc.returncode,
        "log_path": str(case_dir / "hrt_dump_command.log"),
        "input_0_tokens": token_info,
        "input_1_positions": pos_info,
        "dumped_artifacts": copied,
        "limitations": limitations,
        "raw_dump_file_listing": [{"path": str(p), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)} for p in sorted(dump_dir.rglob("*")) if p.is_file()],
    }


def run_position_variants(args: argparse.Namespace, case: dict[str, Any], case_dir: Path) -> dict[str, Any]:
    from hbm_runtime import HB_HBMRuntime

    hbm = hbm_path(Path(args.hbm_root), 0, args.seq_len, args.w_bits, args.lm_head_w_bits, args.final_logits_mode)
    name = model_name(0, args.final_logits_mode)
    runtime = HB_HBMRuntime(str(hbm))
    token_ids = np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len)
    qmeta = quant_metadata(runtime, name)
    scale = float(qmeta.get("scale_first") or args.output_scale)
    rows = []
    zero_deq = None
    for vname, make_pos in POSITION_VARIANTS.items():
        positions = make_pos(args.seq_len)
        out = runtime.run({"_input_0": token_ids, "_input_1": positions}, model_name=name)
        raw = out[name]["_output_0"]
        deq = raw.astype(np.float32) * scale
        vdir = case_dir / "position_variants" / vname
        raw_info = write_array(vdir / "raw_output.npy", raw)
        deq_info = write_array(vdir / "dequant_output.npy", deq)
        pos_info = write_array(vdir / "positions.npy", positions)
        if vname == "all_zero_positions":
            zero_deq = deq.copy()
        rows.append({"variant": vname, "positions": pos_info, "raw_output": raw_info, "dequant_output": deq_info})
    if zero_deq is not None:
        for row in rows:
            deq = np.load(case_dir / "position_variants" / row["variant"] / "dequant_output.npy")
            delta = deq - zero_deq
            row["delta_vs_all_zero_positions"] = write_array(case_dir / "position_variants" / row["variant"] / "delta_vs_all_zero_positions.npy", delta)
            row["delta_norm"] = float(np.linalg.norm(delta.reshape(-1)))
            row["delta_abs_max"] = float(np.max(np.abs(delta)))
            row["delta_std"] = float(np.std(delta))
    del runtime
    return {"quant_metadata": qmeta, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--hidden-size", type=int, default=3584)
    ap.add_argument("--w-bits", type=int, default=8)
    ap.add_argument("--lm-head-w-bits", type=int, default=16)
    ap.add_argument("--final-logits-mode", default="last-token")
    ap.add_argument("--output-scale", type=float, default=6.062494503566995e-05)
    ap.add_argument("--hrt-timeout-seconds", type=int, default=300)
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--report-md", required=True)
    args = ap.parse_args()

    started = time.time()
    out_root = Path(args.output_root)
    report = {
        "schema_version": "dream7b_s100p_v14_seg00_exact_graph_and_position",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "rows": [],
        "errors": [],
        "safety": {"generation_quality_run": False, "product_routes_18888_18889_touched": False, "dream7b_frontend_openclaw_traffic_touched": False},
    }
    try:
        cases = [c for c in iter_jsonl(Path(args.cases)) if c.get("case_id") in CASE_IDS]
        for case in cases:
            cid = case["case_id"]
            case_dir = out_root / "evidence" / "seg00_01_exact_graph_v14" / cid
            try:
                dump = run_hrt_dump(args, case, case_dir)
                pos = run_position_variants(args, case, case_dir)
                meta = {"case_id": cid, "hrt_dump": dump, "position_audit": pos}
                write_json(case_dir / "metadata.json", meta)
                report["rows"].append(meta)
            except Exception as exc:
                err = {"case_id": cid, "type": type(exc).__name__, "message": str(exc)}
                report["errors"].append(err)
                print(f"[v14] ERROR {err}", flush=True)
            write_json(Path(args.report_json), report)
        report["status"] = "pass" if len(report["rows"]) == len(cases) and not report["errors"] else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(Path(args.report_json), report)
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(
        "\n".join([
            "# v14 seg00_01 Exact Graph and Position Remote",
            "",
            f"- status: `{report.get('status')}`",
            f"- rows: `{len(report.get('rows', []))}`",
            f"- errors: `{len(report.get('errors', []))}`",
            "- generation_quality_run: `False`",
            "- product_routes_18888_18889_touched: `False`",
        ]) + "\n",
        encoding="utf-8",
    )
    print(args.report_json, flush=True)
    return 0 if report.get("rows") else 2


if __name__ == "__main__":
    raise SystemExit(main())
