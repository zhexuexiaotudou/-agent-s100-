#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from common_artifact_utils import array_stats, utc_now_iso, write_json
from dream7b_research_common import iter_jsonl
from run_s100p_hbm_chain_dump_logits import hbm_path, model_name, quant_metadata


SAVE_SEGMENTS = {24, 25, 26, 27}


def load_cases(path: Path, case_ids: list[str]) -> list[dict[str, Any]]:
    cases = list(iter_jsonl(path))
    if not case_ids:
        return cases
    wanted = set(case_ids)
    return [case for case in cases if case.get("case_id") in wanted]


def run_single_case(args: argparse.Namespace) -> int:
    from hbm_runtime import HB_HBMRuntime

    case = json.loads(Path(args.single_case_json).read_text(encoding="utf-8"))
    case_id = case["case_id"]
    case_dir = Path(args.single_case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    pos = np.arange(args.seq_len, dtype=np.int32)
    hidden = None
    segments = []
    errors = []
    for index in range(args.layer_count):
        try:
            path = hbm_path(args, index)
            name = model_name(args, index)
            load_start = time.perf_counter()
            runtime = HB_HBMRuntime(str(path))
            load_ms = (time.perf_counter() - load_start) * 1000
            if index == 0:
                inputs = {"_input_0": np.asarray(case["token_ids"], dtype=np.int32).reshape(1, args.seq_len), "_input_1": pos}
            else:
                if hidden is None:
                    raise RuntimeError(f"missing hidden before segment {index}")
                inputs = {"_input_0": hidden.astype(np.float32, copy=False), "_input_1": pos}
            run_start = time.perf_counter()
            output = runtime.run(inputs, model_name=name)
            run_ms = (time.perf_counter() - run_start) * 1000
            raw = output[name]["_output_0"]
            qmeta = quant_metadata(runtime, name)
            scale = qmeta.get("scale_first")
            dequant = raw.astype(np.float32, copy=False) * float(scale) if scale is not None else raw.astype(np.float32, copy=True)
            rec: dict[str, Any] = {
                "segment": index,
                "model_name": name,
                "hbm_path": str(path),
                "load_ms": round(load_ms, 3),
                "run_ms": round(run_ms, 3),
                "raw_stats": array_stats(raw),
                "dequant_stats": array_stats(dequant),
                "quant_metadata": qmeta,
            }
            if index in SAVE_SEGMENTS:
                raw_path = case_dir / f"seg_{index:02d}_raw_output.npy"
                deq_path = case_dir / f"seg_{index:02d}_output.npy"
                np.save(raw_path, raw)
                np.save(deq_path, dequant)
                rec["raw_output"] = str(raw_path)
                rec["dequant_output"] = str(deq_path)
            segments.append(rec)
            if index != args.layer_count - 1:
                hidden = dequant.copy()
            del output
            del runtime
        except Exception as exc:
            errors.append(f"seg{index:02d}:{type(exc).__name__}:{exc}")
            break
    result = {
        "case_id": case_id,
        "case_dir": str(case_dir),
        "status": "pass" if not errors and len(segments) == args.layer_count else "fail",
        "errors": errors,
        "segments": segments,
        "saved_segments": sorted(SAVE_SEGMENTS),
    }
    write_json(case_dir / "case_result.json", result)
    return 0 if result["status"] == "pass" else 2


def child_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--single-case-json")
    parser.add_argument("--single-case-dir")
    parser.add_argument("--hbm-root", default="/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--hidden-size", type=int, default=3584)
    parser.add_argument("--layer-count", type=int, default=28)
    parser.add_argument("--w-bits", type=int, default=8)
    parser.add_argument("--lm-head-w-bits", type=int, default=16)
    parser.add_argument("--final-logits-mode", default="last-token")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--single-case-json" in argv:
        args = child_parser().parse_args(argv)
        return run_single_case(args)

    parser = child_parser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--case-ids", default="zeros,ramp,short_chinese_prompt_padded")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    args = parser.parse_args(argv)
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    case_ids = [x.strip() for x in args.case_ids.split(",") if x.strip()]
    cases = load_cases(Path(args.cases), case_ids)
    results = []
    memory_errors = []
    late_constant = []
    for case in cases:
        cid = case["case_id"]
        cdir = root / cid
        cdir.mkdir(parents=True, exist_ok=True)
        case_json = cdir / "case.json"
        case_json.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--single-case-json",
            str(case_json),
            "--single-case-dir",
            str(cdir),
            "--hbm-root",
            args.hbm_root,
            "--seq-len",
            str(args.seq_len),
            "--hidden-size",
            str(args.hidden_size),
            "--layer-count",
            str(args.layer_count),
            "--w-bits",
            str(args.w_bits),
            "--lm-head-w-bits",
            str(args.lm_head_w_bits),
            "--final-logits-mode",
            args.final_logits_mode,
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        (cdir / "runtime_subprocess.log").write_text(
            "COMMAND:\n" + " ".join(cmd) + "\n\nSTDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr,
            encoding="utf-8",
        )
        result_path = cdir / "case_result.json"
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            result = {"case_id": cid, "case_dir": str(cdir), "status": "fail", "errors": ["child_no_case_result"], "segments": []}
        result["returncode"] = proc.returncode
        result["runtime_log"] = str(cdir / "runtime_subprocess.log")
        text = proc.stdout + proc.stderr + " ".join(result.get("errors", []))
        if "Memory alloc failed" in text or "HBRT" in text and "memory" in text.lower() or "RESOURCE_EXHAUSTED" in text:
            memory_errors.append({"case_id": cid, "error_excerpt": text[-2500:]})
        for seg in result.get("segments", []):
            if seg.get("segment") in SAVE_SEGMENTS and (seg.get("dequant_stats") or {}).get("constant"):
                late_constant.append({"case_id": cid, "segment": seg.get("segment"), "model_name": seg.get("model_name")})
        results.append(result)

    completed = sum(1 for r in results if r.get("status") == "pass")
    failed = len(results) - completed
    verdict = "pass" if failed == 0 else ("partial" if completed else "fail")
    payload = {
        "schema_version": "dream7b_s100p_boundary_dump_subprocess_v3",
        "created_at_utc": utc_now_iso(),
        "run_id": root.name,
        "s100p_boundary_dump_subprocess_verdict": verdict,
        "cases_requested": [case["case_id"] for case in cases],
        "cases_completed": completed,
        "cases_failed": failed,
        "memory_errors": memory_errors,
        "late_segment_constant_outputs": late_constant,
        "cases": results,
    }
    write_json(Path(args.report_json), payload)
    lines = [
        "# S100P Boundary Dump Subprocess V3",
        "",
        f"- verdict: `{verdict}`",
        f"- cases_completed: `{completed}`",
        f"- cases_failed: `{failed}`",
        f"- memory_errors: `{len(memory_errors)}`",
        "",
        "| case | status | segments | errors |",
        "| --- | --- | ---: | --- |",
    ]
    for r in results:
        lines.append(f"| `{r['case_id']}` | `{r.get('status')}` | {len(r.get('segments', []))} | `{'; '.join(r.get('errors', []))}` |")
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.report_json)
    return 0 if completed else 2


if __name__ == "__main__":
    raise SystemExit(main())
