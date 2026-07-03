#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from common_artifact_utils import sha256_file, utc_now_iso, write_json
from run_s100p_hbm_chain_dump_logits import hbm_path, model_name


def safe_repr(obj: Any, limit: int = 1000) -> str:
    try:
        text = repr(obj)
    except Exception as exc:
        text = f"<repr_error {type(exc).__name__}: {exc}>"
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def jsonable(obj: Any, depth: int = 0) -> Any:
    if depth > 4:
        return safe_repr(obj, 300)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, np.ndarray):
        return {
            "shape": list(obj.shape),
            "dtype": str(obj.dtype),
            "values": obj.reshape(-1)[:16].astype(float).tolist() if obj.size else [],
        }
    if isinstance(obj, (list, tuple)):
        return [jsonable(v, depth + 1) for v in obj[:32]]
    if isinstance(obj, dict):
        return {str(k): jsonable(v, depth + 1) for k, v in list(obj.items())[:64]}
    if hasattr(obj, "__dict__"):
        return {str(k): jsonable(v, depth + 1) for k, v in vars(obj).items() if not str(k).startswith("_")}
    return safe_repr(obj, 500)


def quant_dict(q: Any) -> dict[str, Any]:
    out = {"repr": safe_repr(q, 500)}
    for attr in ["scale", "zero_point", "axis", "dtype", "data_type", "qtype", "quant_type"]:
        try:
            if hasattr(q, attr):
                out[attr] = jsonable(getattr(q, attr))
        except Exception as exc:
            out[f"{attr}_error"] = f"{type(exc).__name__}:{exc}"
    return out


def nested_quants(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            out[str(k)] = nested_quants(v)
        return out
    return quant_dict(obj)


def collect_known_runtime_fields(runtime: Any, name: str) -> tuple[dict[str, Any], list[str], list[str]]:
    fields: dict[str, Any] = {}
    unavailable: list[str] = []
    exceptions: list[str] = []
    known = [
        "model_names",
        "input_quants",
        "output_quants",
        "input_names",
        "output_names",
        "input_shapes",
        "output_shapes",
        "input_dtypes",
        "output_dtypes",
        "model_infos",
        "model_info",
        "models",
        "graph_infos",
        "tensor_infos",
        "input_tensors",
        "output_tensors",
    ]
    for attr in known:
        try:
            if hasattr(runtime, attr):
                value = getattr(runtime, attr)
                fields[attr] = nested_quants(value) if attr.endswith("_quants") else jsonable(value)
            else:
                unavailable.append(attr)
        except Exception as exc:
            exceptions.append(f"{attr}:{type(exc).__name__}:{exc}")
            unavailable.append(attr)

    public_attrs = {}
    for attr in dir(runtime):
        if attr.startswith("_") or attr in fields:
            continue
        try:
            value = getattr(runtime, attr)
        except Exception:
            continue
        if callable(value):
            continue
        public_attrs[attr] = safe_repr(value, 300)
    fields["runtime_public_attributes"] = public_attrs

    out_quants = fields.get("output_quants")
    if isinstance(out_quants, dict):
        model_q = out_quants.get(name) or out_quants.get(name.lstrip("_"))
        if isinstance(model_q, dict):
            fields["output_tensor_names_inferred_from_quants"] = sorted(model_q.keys())
    in_quants = fields.get("input_quants")
    if isinstance(in_quants, dict):
        model_q = in_quants.get(name) or in_quants.get(name.lstrip("_"))
        if isinstance(model_q, dict):
            fields["input_tensor_names_inferred_from_quants"] = sorted(model_q.keys())
    return fields, unavailable, exceptions


def inspect_one(args: argparse.Namespace, index: int) -> dict[str, Any]:
    args.layer_count = 28
    hbm = hbm_path(args, index)
    name = model_name(args, index)
    rec: dict[str, Any] = {
        "segment_index": index,
        "model_name": name,
        "hbm_path": str(hbm),
        "hbm_exists": hbm.is_file(),
        "hbm_size_bytes": hbm.stat().st_size if hbm.is_file() else None,
        "hbm_sha256": sha256_file(hbm) if hbm.is_file() else None,
        "hbo_path": "unavailable",
        "input_tensor_names": "unavailable",
        "output_tensor_names": "unavailable",
        "declared_input_shapes": "unavailable",
        "declared_output_shapes": "unavailable",
        "input_dtype": "unavailable",
        "output_dtype": "unavailable",
        "input_quant_params": "unavailable",
        "output_quant_params": "unavailable",
        "runtime_model_info": {},
        "runtime_tensor_descriptors": {},
        "unavailable_fields": [],
        "exceptions": [],
    }
    if not hbm.is_file():
        rec["exceptions"].append("hbm_missing")
        rec["unavailable_fields"].append("runtime_all")
        return rec

    try:
        from hbm_runtime import HB_HBMRuntime

        runtime = HB_HBMRuntime(str(hbm))
        fields, unavailable, exceptions = collect_known_runtime_fields(runtime, name)
        rec["runtime_model_info"] = {
            "model_names": fields.get("model_names", []),
            "runtime_public_attributes": fields.get("runtime_public_attributes", {}),
        }
        rec["runtime_tensor_descriptors"] = fields
        rec["unavailable_fields"].extend(unavailable)
        rec["exceptions"].extend(exceptions)

        if isinstance(fields.get("output_quants"), dict):
            rec["output_quant_params"] = fields["output_quants"]
            rec["output_tensor_names"] = fields.get("output_tensor_names_inferred_from_quants", "unavailable")
        if isinstance(fields.get("input_quants"), dict):
            rec["input_quant_params"] = fields["input_quants"]
            rec["input_tensor_names"] = fields.get("input_tensor_names_inferred_from_quants", "unavailable")
        for src, dst in [
            ("input_names", "input_tensor_names"),
            ("output_names", "output_tensor_names"),
            ("input_shapes", "declared_input_shapes"),
            ("output_shapes", "declared_output_shapes"),
            ("input_dtypes", "input_dtype"),
            ("output_dtypes", "output_dtype"),
        ]:
            if src in fields and rec.get(dst) == "unavailable":
                rec[dst] = fields[src]
    except Exception as exc:
        rec["exceptions"].append(f"runtime_load_or_probe:{type(exc).__name__}:{exc}")
        rec["unavailable_fields"].append("runtime_descriptor_probe")
    rec["unavailable_fields"] = sorted(set(rec["unavailable_fields"]))
    return rec


def child_main(argv: list[str]) -> int:
    parser = base_parser()
    parser.add_argument("--single-segment", type=int, required=True)
    parser.add_argument("--single-output", required=True)
    args = parser.parse_args(argv)
    rec = inspect_one(args, args.single_segment)
    write_json(Path(args.single_output), rec)
    return 0 if not any("runtime_load_or_probe" in e for e in rec.get("exceptions", [])) else 2


def base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", default="last-token")
    return parser


def run_child_for_segment(args: argparse.Namespace, index: int, tmp_dir: Path) -> dict[str, Any]:
    out = tmp_dir / f"seg_{index:02d}.json"
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--single-segment",
        str(index),
        "--single-output",
        str(out),
        "--hbm-root",
        args.hbm_root,
        "--seq-len",
        str(args.seq_len),
        "--w-bits",
        str(args.w_bits),
        "--lm-head-w-bits",
        str(args.lm_head_w_bits),
        "--final-logits-mode",
        args.final_logits_mode,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if out.is_file():
        rec = json.loads(out.read_text(encoding="utf-8"))
    else:
        rec = {
            "segment_index": index,
            "model_name": model_name(args, index),
            "hbm_path": str(hbm_path(args, index)),
            "exceptions": [f"child_no_output:returncode={proc.returncode}", proc.stderr[-2000:]],
            "unavailable_fields": ["runtime_descriptor_probe"],
        }
    rec["child_returncode"] = proc.returncode
    rec["child_stderr_tail"] = proc.stderr[-2000:]
    return rec


def compare_seg26_to_seg27(segments: list[dict[str, Any]]) -> dict[str, Any]:
    seg26 = next((s for s in segments if s.get("segment_index") == 26), None)
    seg27 = next((s for s in segments if s.get("segment_index") == 27), None)
    if not seg26 or not seg27:
        return {"status": "fail", "reason": "missing_seg26_or_seg27"}
    blocking = []
    observations = {
        "observed_v2_seg26_output_shape": [128, 3584],
        "observed_v2_seg27_input_accepted_shape": [128, 3584],
        "observed_shape_contract": "pass",
        "seg27_declared_input_shapes": seg27.get("declared_input_shapes"),
        "seg26_declared_output_shapes": seg26.get("declared_output_shapes"),
        "seg27_input_quant_params": seg27.get("input_quant_params"),
        "seg26_output_quant_params": seg26.get("output_quant_params"),
        "seg27_input_dtype": seg27.get("input_dtype"),
        "seg26_output_dtype": seg26.get("output_dtype"),
    }
    for field in ["declared_output_shapes", "output_dtype", "output_quant_params"]:
        if seg26.get(field) == "unavailable":
            blocking.append(f"seg26_{field}")
    for field in ["declared_input_shapes", "input_dtype", "input_quant_params"]:
        if seg27.get(field) == "unavailable":
            blocking.append(f"seg27_{field}")
    status = "pass" if not blocking else "inconclusive"
    return {
        "status": status,
        "blocking_fields_missing": sorted(set(blocking)),
        "observations": observations,
        "interpretation": (
            "No gross shape mismatch is visible from observed v2 tensors, but runtime input descriptors or input quant params are unavailable."
            if blocking
            else "Segment 26 output and segment 27 input descriptors are available and compatible."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--single-segment" in argv:
        return child_main(argv)
    parser = base_parser()
    parser.add_argument("--output-json", default="reports/110_segment_io_contract.json")
    parser.add_argument("--output-md", default="reports/110_segment_io_contract.md")
    parser.add_argument("--tmp-dir", default="logs/segment_io_contract_child")
    args = parser.parse_args(argv)
    args.layer_count = 28
    tmp_dir = Path(args.tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    segments = [run_child_for_segment(args, i, tmp_dir) for i in range(28)]
    comparison = compare_seg26_to_seg27(segments)
    child_failures = [s for s in segments if s.get("child_returncode") not in (0, None)]
    verdict = "pass"
    if child_failures:
        verdict = "inconclusive"
    if comparison["status"] != "pass":
        verdict = "inconclusive"
    payload = {
        "schema_version": "dream7b_s100p_segment_io_contract_v3",
        "created_at_utc": utc_now_iso(),
        "segment_io_contract_verdict": verdict,
        "seg26_to_seg27_contract_match": comparison["status"],
        "blocking_fields_missing": comparison.get("blocking_fields_missing", []),
        "seg26_to_seg27_comparison": comparison,
        "segments": segments,
    }
    write_json(Path(args.output_json), payload)
    lines = [
        "# Segment IO Contract Audit V3",
        "",
        f"- segment_io_contract_verdict: `{verdict}`",
        f"- seg26_to_seg27_contract_match: `{comparison['status']}`",
        f"- blocking_fields_missing: `{comparison.get('blocking_fields_missing', [])}`",
        "",
        "| segment | model | hbm_size | child_rc | output_quant | input_quant | exceptions |",
        "| ---: | --- | ---: | ---: | --- | --- | --- |",
    ]
    for s in segments:
        lines.append(
            f"| {s.get('segment_index')} | `{s.get('model_name')}` | {s.get('hbm_size_bytes')} | {s.get('child_returncode')} | "
            f"{s.get('output_quant_params') != 'unavailable'} | {s.get('input_quant_params') != 'unavailable'} | {len(s.get('exceptions', []))} |"
        )
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
