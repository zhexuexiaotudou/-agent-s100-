#!/usr/bin/env python3
"""Dream7B/S100P v16 remote seg00_01 introspection and position probes.

Runs on the S100P/NAS research host. It is read-only with respect to model
artifacts and does not call generation or product routes.
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
}
PATTERNS = [
    "scale",
    "zero_point",
    "zero-point",
    "qnt",
    "quant",
    "const_fake_quant",
    "hbir.mul",
    "hbir.add",
    "GatherND",
    "_input_0",
    "_input_1",
    "_output_0",
    "dream_segment_00_01",
]


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
        line = line.strip()
        if line:
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


def run_command(cmd: list[str], log_path: Path, timeout: int = 60, env: dict[str, str] | None = None) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=merged_env)
        result = {
            "cmd": cmd,
            "returncode": proc.returncode,
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout_path": str(log_path),
            "stderr_path": str(log_path),
        }
        log_path.write_text(
            "COMMAND: " + " ".join(cmd) + "\n"
            + "ENV_OVERRIDES: " + json.dumps(env or {}, ensure_ascii=False) + "\n\n"
            + "STDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr,
            encoding="utf-8",
            errors="ignore",
        )
        result["stdout_len"] = len(proc.stdout)
        result["stderr_len"] = len(proc.stderr)
        return result
    except Exception as exc:
        log_path.write_text(
            "COMMAND: " + " ".join(cmd) + "\n"
            + "ENV_OVERRIDES: " + json.dumps(env or {}, ensure_ascii=False) + "\n\n"
            + f"EXCEPTION: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
            errors="ignore",
        )
        return {"cmd": cmd, "exception": type(exc).__name__, "message": str(exc), "elapsed_seconds": round(time.time() - started, 3), "log_path": str(log_path)}


def enumerate_tools(out_dir: Path) -> dict[str, Any]:
    tools = [
        "hrt_model_exec",
        "hb_model_info",
        "hb_mapper",
        "hbdk-cc",
        "hbdk-cc-4",
        "hbdk3",
        "hbdk4",
        "hbm-info",
        "hbm_model_info",
        "strings",
        "readelf",
        "file",
        "python3",
    ]
    rows = []
    for tool in tools:
        path = shutil.which(tool)
        row = {"tool": tool, "path": path}
        if path:
            row["version_probe"] = run_command([tool, "--help"], out_dir / "tool_help" / f"{tool.replace('/', '_')}.help.log", timeout=15)
        rows.append(row)
    compgen = run_command(["bash", "-lc", "compgen -c | grep -E '^(hrt|hb_|hbdk|hbm|hb_mapper)' | sort -u"], out_dir / "tool_compgen.log", timeout=20)
    return {"tools": rows, "compgen": compgen}


def run_hbm_introspection(args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    hbm = Path(args.hbm)
    model_name = args.model_name
    commands = []
    commands.append(run_command(["sha256sum", str(hbm)], out_dir / "hbm_sha256.log", timeout=60))
    commands.append(run_command(["file", str(hbm)], out_dir / "hbm_file.log", timeout=60))
    commands.append(run_command(["readelf", "-h", str(hbm)], out_dir / "hbm_readelf_h.log", timeout=60))
    commands.append(run_command(["hrt_model_exec", "model_info", "--model_file", str(hbm)], out_dir / "hrt_model_exec_model_info.log", timeout=args.command_timeout))
    commands.append(run_command(["hb_model_info", "--model_file", str(hbm)], out_dir / "hb_model_info_model_file.log", timeout=args.command_timeout))
    commands.append(run_command(["hb_model_info", str(hbm)], out_dir / "hb_model_info_positional.log", timeout=args.command_timeout))
    pattern = "|".join(PATTERNS)
    commands.append(
        run_command(
            ["bash", "-lc", f"strings -a {sh_quote(str(hbm))} | grep -Ei {sh_quote(pattern)} | head -2000"],
            out_dir / "hbm_strings_filtered.log",
            timeout=args.command_timeout,
        )
    )
    commands.append(
        run_command(
            ["bash", "-lc", f"strings -a {sh_quote(str(hbm))} | grep -Ei 'hbir|GatherND|qnt|scale|zero|input|output' | head -5000"],
            out_dir / "hbm_strings_broad.log",
            timeout=args.command_timeout,
        )
    )
    sample_case = next(c for c in read_jsonl(Path(args.cases)) if c.get("case_id") == "zeros")
    input_dir = out_dir / "hrt_inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    np.save(input_dir / "input_0_tokens.npy", np.asarray(sample_case["token_ids"], dtype=np.int32).reshape(1, args.seq_len))
    np.save(input_dir / "input_1_positions.npy", np.arange(args.seq_len, dtype=np.int32))
    dump_rows = []
    for fmt in ["bin", "txt", "npy"]:
        dump_dir = out_dir / f"hrt_dump_{fmt}"
        if dump_dir.exists():
            shutil.rmtree(dump_dir)
        dump_dir.mkdir(parents=True)
        cmd = [
            "hrt_model_exec",
            "infer",
            "--model_file",
            str(hbm),
            "--model_name",
            model_name,
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
            fmt,
        ]
        env = {"HBRT_LOG_LEVEL": "debug", "DNN_LOG_LEVEL": "6", "UCPT_LOG_LEVEL": "6"}
        row = run_command(cmd, out_dir / f"hrt_dump_{fmt}.log", timeout=args.hrt_timeout, env=env)
        row["dump_file_listing"] = file_listing(dump_dir)
        dump_rows.append(row)
    recovered = summarize_dump_files(out_dir)
    return {
        "hbm_path": str(hbm),
        "hbm_exists": hbm.exists(),
        "hbm_size_bytes": hbm.stat().st_size if hbm.exists() else None,
        "hbm_sha256": sha256_file(hbm) if hbm.exists() else None,
        "model_name": model_name,
        "commands": commands,
        "hrt_dump_rows": dump_rows,
        "recovered_tensor_visibility": recovered,
    }


def sh_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def file_listing(root: Path) -> list[dict[str, Any]]:
    rows = []
    if not root.exists():
        return rows
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rows.append({"path": str(p), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    return rows


def summarize_dump_files(root: Path) -> dict[str, Any]:
    names = [str(p) for p in root.rglob("*") if p.is_file()]
    return {
        "mul_input": [n for n in names if "hbir.mul" in n and "input" in n],
        "mul_output": [n for n in names if "hbir.mul" in n and "output" in n],
        "add_input0": [n for n in names if "hbir.add" in n and "input-0" in n],
        "add_input1": [n for n in names if "hbir.add" in n and ("input-1" in n or "input_1" in n)],
        "add_output": [n for n in names if "hbir.add" in n and "output" in n],
        "gathernd_output": [n for n in names if "GatherND" in n and "output" in n],
    }


def position_variants(n: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(20260703)
    variants: dict[str, np.ndarray] = {
        "all_zero_positions": np.zeros(n, dtype=np.int32),
        "all_one_positions": np.ones(n, dtype=np.int32),
        "canonical_0_to_127": np.arange(n, dtype=np.int32),
        "one_indexed_1_to_128": np.arange(1, n + 1, dtype=np.int32),
        "reverse_127_to_0": np.arange(n - 1, -1, -1, dtype=np.int32),
        "doubled_positions": np.arange(n, dtype=np.int32) * 2,
        "random_permutation_positions": rng.permutation(n).astype(np.int32),
    }
    for k in [0, 1, 2, 4, 8, 16, 32, 64, 127]:
        variants[f"constant_{k}_positions"] = np.full(n, k, dtype=np.int32)
    for idx in [0, 1, 2, 4, 8, 16, 32, 64, 127]:
        arr = np.zeros(n, dtype=np.int32)
        arr[idx] = 127
        variants[f"sparse_index_{idx:03d}_value_127"] = arr
    return variants


def quant_metadata(runtime: Any, name: str) -> dict[str, Any]:
    try:
        qp = runtime.output_quants[name]["_output_0"]
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


def run_position_probe(args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    from hbm_runtime import HB_HBMRuntime

    cases = [c for c in read_jsonl(Path(args.cases)) if c.get("case_id") in CASE_IDS]
    runtime = HB_HBMRuntime(str(Path(args.hbm)))
    qmeta = quant_metadata(runtime, args.model_name)
    scale = float(qmeta.get("scale_first") or args.output_scale)
    rows = []
    for case in cases:
        cid = case["case_id"]
        case_dir = out_dir / cid
        token_ids = np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len)
        save_array(case_dir / "input_0_tokens.npy", token_ids)
        zero_deq = None
        variant_rows = []
        for name, positions in position_variants(args.seq_len).items():
            vdir = case_dir / "position_variants" / name
            out = runtime.run({"_input_0": token_ids, "_input_1": positions}, model_name=args.model_name)
            raw = out[args.model_name]["_output_0"]
            deq = raw.astype(np.float32) * scale
            save_array(vdir / "positions.npy", positions)
            save_array(vdir / "raw_output.npy", raw)
            save_array(vdir / "dequant_output.npy", deq)
            if name == "all_zero_positions":
                zero_deq = deq.copy()
            variant_rows.append({"variant": name, "positions_stats": stats(positions), "raw_stats": stats(raw), "dequant_stats": stats(deq)})
        if zero_deq is not None:
            for row in variant_rows:
                deq = np.load(case_dir / "position_variants" / row["variant"] / "dequant_output.npy")
                delta = deq - zero_deq
                save_array(case_dir / "position_variants" / row["variant"] / "delta_vs_all_zero_positions.npy", delta)
                row["delta_stats"] = stats(delta)
                row["delta_norm"] = float(np.linalg.norm(delta.reshape(-1)))
                row["delta_abs_max"] = float(np.max(np.abs(delta)))
        write_json(case_dir / "metadata.json", {"case_id": cid, "quant_metadata": qmeta, "variants": variant_rows})
        rows.append({"case_id": cid, "variant_count": len(variant_rows), "variants": variant_rows})
    del runtime
    return {"quant_metadata": qmeta, "case_rows": rows, "variant_names": list(position_variants(args.seq_len).keys())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--hbm", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken/seg00_01/dream7b_segment_0_1_seq128_q8.hbm")
    ap.add_argument("--model-name", default="dream_segment_00_01")
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--hidden-size", type=int, default=3584)
    ap.add_argument("--output-scale", type=float, default=6.062494503566995e-05)
    ap.add_argument("--command-timeout", type=int, default=120)
    ap.add_argument("--hrt-timeout", type=int, default=300)
    args = ap.parse_args()

    started = time.time()
    root = Path(args.output_root)
    report = {
        "schema_version": "dream7b_s100p_v16_remote_seg00_introspection_position",
        "created_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": dict(SAFETY),
        "status": "started",
        "errors": [],
    }
    write_json(root / "v16_remote_collection_report.json", report)
    try:
        report["tool_enumeration"] = enumerate_tools(root / "evidence" / "hbm_introspection_v16")
        write_json(root / "v16_remote_collection_report.json", report)
        report["hbm_introspection"] = run_hbm_introspection(args, root / "evidence" / "hbm_introspection_v16")
        write_json(root / "v16_remote_collection_report.json", report)
        report["position_probe"] = run_position_probe(args, root / "evidence" / "position_finite_difference_v16")
        report["status"] = "pass"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(root / "v16_remote_collection_report.json", report)
    (root / "v16_remote_collection_report.md").write_text(
        "# v16 Remote seg00_01 Collection\n\n"
        f"- status: `{report.get('status')}`\n"
        f"- errors: `{len(report.get('errors', []))}`\n"
        f"- elapsed_total_seconds: `{report.get('elapsed_total_seconds')}`\n"
        "- generation_quality_run: `False`\n"
        "- product_routes_18888_18889_touched: `False`\n"
        "- dream7b_frontend_openclaw_traffic_touched: `False`\n",
        encoding="utf-8",
    )
    print(root / "v16_remote_collection_report.json", flush=True)
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
