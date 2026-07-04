#!/usr/bin/env python3
"""Build Dream7B/S100P v20 reports and GPT Pro evidence packet.

The builder consumes local and pulled remote evidence. It does not run
generation, product routes, or touch ports 18888/18889.
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
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SAFETY = {
    "generation_quality_run": False,
    "product_routes_18888_18889_touched": False,
    "dream7b_frontend_openclaw_traffic_touched": False,
    "harness_qwen_openclaw_defaults_modified": False,
}


EXPORT_SCRIPT = r'''#!/usr/bin/env python3
"""Export Dream7B semantic HF/PyTorch truth logits on x86/GPU or torch2 CPU.

Offline logits-only runner. It does not call generation or product routes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stats(arr: np.ndarray) -> dict[str, Any]:
    x = np.asarray(arr)
    y = x.reshape(-1)
    return {
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "size": int(x.size),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "abs_max": float(np.max(np.abs(y))),
        "nonzero_count": int(np.count_nonzero(y)),
        "allzero": bool(np.all(y == 0)),
        "constant": bool(np.all(y == y.flat[0])),
        "nan_count": int(np.isnan(y.astype(np.float64, copy=False)).sum()),
        "inf_count": int(np.isinf(y.astype(np.float64, copy=False)).sum()),
    }


def save_array(path: Path, arr: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, arr)
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "stats": stats(arr)}


def tensor_to_numpy(tensor: Any) -> np.ndarray:
    return np.asarray(tensor.detach().float().cpu().tolist(), dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--cases-jsonl", default="semantic_cases.jsonl")
    ap.add_argument("--output-root", default="semantic_truth_output")
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--device-map", default="", help="Optional transformers device_map value, e.g. auto")
    ap.add_argument("--torch-threads", type=int, default=8)
    ap.add_argument("--fallback-fp32", action="store_true")
    args = ap.parse_args()

    started = time.time()
    out_root = Path(args.output_root)
    report: dict[str, Any] = {
        "schema_version": "dream7b_s100p_v20_x86_gpu_semantic_truth_export",
        "started_at_unix": started,
        "python": sys.version,
        "platform": platform.platform(),
        "args": vars(args),
        "safety": {
            "generation_quality_run": False,
            "product_routes_18888_18889_touched": False,
            "dream7b_frontend_openclaw_traffic_touched": False,
            "harness_qwen_openclaw_defaults_modified": False,
        },
        "hf_rows": [],
        "errors": [],
        "status": "started",
    }
    write_json(out_root / "semantic_truth_export_report.json", report)
    try:
        import torch
        import transformers
        from transformers import AutoModel

        torch.set_num_threads(args.torch_threads)
        device = "cuda" if args.device == "auto" and torch.cuda.is_available() else ("cpu" if args.device == "auto" else args.device)
        dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
        report["runtime_versions"] = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__}
        report["device_selected"] = device
        report["cuda_available"] = bool(torch.cuda.is_available())
        report["model_files"] = {}
        model_dir = Path(args.model_dir)
        for name in ["config.json", "model.safetensors.index.json", "tokenizer_config.json", "vocab.json", "merges.txt", "modeling_dream.py", "configuration_dream.py"]:
            p = model_dir / name
            if p.exists():
                report["model_files"][name] = {"path": str(p), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)}
        load_kwargs: dict[str, Any] = {
            "trust_remote_code": True,
            "torch_dtype": dtype,
            "low_cpu_mem_usage": True,
            "use_safetensors": True,
        }
        if args.device_map:
            load_kwargs["device_map"] = args.device_map
        report["status"] = "model_load_start"
        write_json(out_root / "semantic_truth_export_report.json", report)
        try:
            model = AutoModel.from_pretrained(args.model_dir, **load_kwargs)
        except Exception:
            if not args.fallback_fp32 or args.dtype == "float32":
                raise
            dtype = torch.float32
            report["fallback_used"] = "float32"
            load_kwargs["torch_dtype"] = dtype
            model = AutoModel.from_pretrained(args.model_dir, **load_kwargs)
        if not args.device_map:
            model = model.to(device)
        model.eval()
        report["status"] = "model_loaded"
        report["model_class"] = type(model).__name__
        report["parameter_count"] = int(sum(p.numel() for p in model.parameters()))
        report["parameter_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
        write_json(out_root / "semantic_truth_export_report.json", report)

        cases = read_jsonl(Path(args.cases_jsonl))
        with torch.no_grad():
            for case in cases:
                cid = case["case_id"]
                t0 = time.time()
                input_ids = torch.tensor([case["token_ids"]], dtype=torch.long, device=device if not args.device_map else None)
                position_ids = torch.tensor([case.get("position_ids", list(range(input_ids.shape[1])))], dtype=torch.long, device=device if not args.device_map else None)
                attention_mask = torch.tensor([case.get("attention_mask", [1] * input_ids.shape[1])], dtype=torch.bool, device=device if not args.device_map else None)
                kwargs = {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "position_ids": position_ids,
                    "use_cache": False,
                    "return_dict": True,
                    "output_hidden_states": False,
                    "num_logits_to_keep": 1,
                }
                try:
                    outputs = model(**kwargs)
                except TypeError:
                    kwargs.pop("num_logits_to_keep", None)
                    outputs = model(**kwargs)
                logits = tensor_to_numpy(outputs.logits[0, -1])
                row = {
                    "case_id": cid,
                    "semantic_or_diagnostic": case.get("semantic_or_diagnostic", "semantic"),
                    "truth_row_type": f"HF/PyTorch {str(dtype).replace('torch.', '')}",
                    "elapsed_seconds": round(time.time() - t0, 3),
                    "token_ids_sha256": case.get("token_ids_sha256"),
                    "logits": save_array(out_root / cid / "hf_truth_logits.npy", logits),
                    "top10": np.argsort(logits.reshape(-1))[-10:][::-1].astype(int).tolist(),
                    "status": "pass",
                }
                write_json(out_root / cid / "metadata.json", row)
                report["hf_rows"].append(row)
                report["status"] = "running"
                report["hf_truth_rows"] = len(report["hf_rows"])
                write_json(out_root / "semantic_truth_export_report.json", report)
        report["status"] = "pass" if len(report["hf_rows"]) == len(cases) else "partial"
    except Exception as exc:
        report["status"] = "fail"
        report["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    report["hf_truth_rows"] = len(report.get("hf_rows", []))
    report["elapsed_total_seconds"] = round(time.time() - started, 3)
    write_json(out_root / "semantic_truth_export_report.json", report)
    return 0 if report["hf_truth_rows"] >= 8 else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def artifact(path: Path, root: Path) -> dict[str, Any]:
    row: dict[str, Any] = {"path": rel(path, root), "exists": path.exists()}
    if path.exists() and path.is_file():
        row.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    elif path.exists() and path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        row.update({"file_count": len(files), "size_bytes": sum(p.stat().st_size for p in files)})
    return row


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-12000:]}
    except Exception as exc:
        return {"cmd": cmd, "error": f"{type(exc).__name__}:{exc}"}


def common(root: Path, schema: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v20_{schema}",
        "created_at_utc": now(),
        "run_commands": [command],
        "host_environment": {"platform": platform.platform(), "python": sys.version},
        "git": run(["git", "status", "--short"], root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [],
        "blocking_or_failure_reasons": [],
        "safety": dict(SAFETY),
    }


def save_report(root: Path, stem: str, report: dict[str, Any], title: str, bullets: list[str]) -> dict[str, Any]:
    j = root / "reports" / f"{stem}.json"
    m = root / "reports" / f"{stem}.md"
    write_json(j, report)
    write_text(m, "# " + title + "\n\n" + "\n".join("- " + b for b in bullets) + "\n")
    report["output_artifacts"] = [artifact(j, root), artifact(m, root)]
    write_json(j, report)
    return report


def task3000(root: Path, command: str) -> dict[str, Any]:
    loc = root / "evidence" / "dream7b_s100p_v20_execution_20260704" / "evidence" / "single_case_forward_runtime_v20" / "single_case_forward_runtime_report.json"
    v19 = root / "01_final_evidence" / "dream7b_s100p_gate_packet_v19.json"
    report = common(root, "3000_baseline_lock", command, [v19, root / "reports" / "2010_semantic_hf_truth_loader_gate.json", loc])
    v19d = read_json(v19)
    v19truth = read_json(root / "reports" / "2010_semantic_hf_truth_loader_gate.json")
    locd = read_json(loc)
    report.update(
        {
            "v19_final_verdict": v19d.get("final_verdict"),
            "v19_direct_safetensors_status": v19truth.get("route_a_status"),
            "loaded_weight_count": v19truth.get("route_a_load_summary", {}).get("loaded_weight_keys"),
            "expected_weight_count": v19truth.get("route_a_load_summary", {}).get("expected_weight_keys"),
            "v19_forward_blocker": v19truth.get("verdict"),
            "v20_localization_status": locd.get("status"),
            "v20_selected_case": locd.get("selected_case"),
            "semantic_cases_count": read_jsonl_count(root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "targeted_bpu_islands_semantic_v18" / "cases" / "semantic_seq128_cases_v18.jsonl"),
            "current_island_status": "blocked_hf_semantic_truth_rows_missing",
            "verdict": "baseline_locked",
        }
    )
    return save_report(root, "3000_v20_baseline_lock", report, "V20 Baseline Lock", [f"v19_final_verdict: `{report['v19_final_verdict']}`", f"loaded_weight_count: `{report['loaded_weight_count']}/{report['expected_weight_count']}`", f"v20_localization_status: `{report['v20_localization_status']}`"])


def read_jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def task3010(root: Path, command: str) -> dict[str, Any]:
    ev = root / "evidence" / "dream7b_s100p_v20_execution_20260704" / "evidence" / "single_case_forward_runtime_v20"
    primary = ev / "single_case_forward_runtime_report.json"
    report = common(root, "3010_single_case_forward_runtime_localization", command, [primary, ev / "run_single_case_forward_runtime.command.log", root / "tools" / "run_v20_single_case_forward_localization.py"])
    data = read_json(primary)
    events = data.get("events", [])
    layer_times = []
    sdpa_times = []
    for row in events:
        stage = row.get("stage", "")
        if stage.startswith("layer_") and stage.endswith("_end"):
            layer_times.append({"layer": stage.replace("_end", ""), "seconds": row.get("seconds")})
        if stage == "sdpa_end":
            sdpa_times.append({"layer": row.get("active_layer"), "seconds": row.get("seconds")})
    completed_layers = [r["layer"] for r in layer_times]
    verdict = "manual_stop_s100p_reference_runtime_too_slow"
    if data.get("hf_truth_rows", 0) >= 1:
        verdict = "single_case_forward_completed"
    elif layer_times:
        report["blocking_or_failure_reasons"].append("Layer-level localization completed enough to show decoder layers take about 196s each while SDPA takes about 0.17s; full 28-layer semantic forward on S100P is not practical for 8-row truth export.")
    else:
        verdict = "blocked_before_layer_completion"
        report["blocking_or_failure_reasons"].append("No complete decoder layer was recorded.")
    report.update(
        {
            "selected_case": data.get("selected_case"),
            "hf_truth_rows": data.get("hf_truth_rows", 0),
            "completed_layers": completed_layers,
            "layer_times": layer_times,
            "sdpa_times": sdpa_times,
            "last_event": data.get("last_event") or (events[-1] if events else None),
            "load_summary": data.get("load_summary"),
            "verdict": verdict,
        }
    )
    return save_report(root, "3010_single_case_forward_runtime_localization", report, "Single Case Forward Runtime Localization", [f"verdict: `{verdict}`", f"completed_layers: `{completed_layers}`", f"hf_truth_rows: `{report['hf_truth_rows']}`"])


def create_x86_bundle(root: Path) -> dict[str, Any]:
    bundle = root / "evidence" / "x86_gpu_semantic_truth_export_bundle_v20"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)
    cases_src = root / "evidence" / "dream7b_s100p_v18_execution_20260704" / "evidence" / "targeted_bpu_islands_semantic_v18" / "cases" / "semantic_seq128_cases_v18.jsonl"
    shutil.copy2(cases_src, bundle / "semantic_cases.jsonl")
    small_tar = root / "evidence" / "dream7b_hf_small_source_v20.tar.gz"
    if small_tar.exists():
        with tarfile.open(small_tar, "r:gz") as tf:
            tf.extractall(bundle / "model_source_files")
    write_text(bundle / "export_semantic_truth.py", EXPORT_SCRIPT)
    write_text(bundle / "requirements.txt", "\n".join(["torch>=2.1", "transformers>=4.45", "safetensors>=0.4.3", "accelerate>=0.30", "numpy>=1.24"]) + "\n")
    write_text(
        bundle / "run_export.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\nMODEL_DIR=${1:?usage: ./run_export.sh /path/to/dream7b-hf [out_dir]}\nOUT_DIR=${2:-semantic_truth_output}\npython3 export_semantic_truth.py --model-dir \"$MODEL_DIR\" --cases-jsonl semantic_cases.jsonl --output-root \"$OUT_DIR\" --dtype bfloat16 --device auto --fallback-fp32\n",
    )
    write_text(
        bundle / "run_export.ps1",
        "param([Parameter(Mandatory=$true)][string]$ModelDir,[string]$OutDir='semantic_truth_output')\npy -3 .\\export_semantic_truth.py --model-dir $ModelDir --cases-jsonl .\\semantic_cases.jsonl --output-root $OutDir --dtype bfloat16 --device auto --fallback-fp32\n",
    )
    files = []
    for p in sorted((bundle / "model_source_files").rglob("*")) if (bundle / "model_source_files").exists() else []:
        if p.is_file():
            files.append({"path": rel(p, bundle), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    manifest = {
        "schema_version": "dream7b_s100p_v20_x86_gpu_export_bundle_manifest",
        "created_at_utc": now(),
        "purpose": "Produce 8 semantic HF/PyTorch BF16 or FP32 full-truth logits outside the S100P torch1.8 CPU runtime.",
        "expected_model_dir_on_s100p": "/mnt/nas/openclaw/models/dream7b-hf",
        "weights_not_embedded": True,
        "required_cases": 8,
        "semantic_cases_sha256": sha256_file(bundle / "semantic_cases.jsonl"),
        "model_source_files": files,
        "run_commands": [
            "bash run_export.sh /path/to/dream7b-hf semantic_truth_output",
            "py -3 .\\export_semantic_truth.py --model-dir C:\\path\\to\\dream7b-hf --cases-jsonl .\\semantic_cases.jsonl --output-root semantic_truth_output --dtype bfloat16 --device auto --fallback-fp32",
        ],
        "safety": dict(SAFETY),
    }
    write_json(bundle / "MODEL_MANIFEST.json", manifest)
    write_text(bundle / "README.md", "# Dream7B S100P V20 x86/GPU Semantic Truth Export Bundle\n\nRun this bundle on a machine with the Dream7B HF model directory and torch2. It exports logits only; it does not run generation or product routes.\n")
    return {"bundle_path": bundle, "manifest": manifest}


def task3020(root: Path, command: str) -> dict[str, Any]:
    info = create_x86_bundle(root)
    bundle = info["bundle_path"]
    report = common(root, "3020_x86_gpu_semantic_truth_export_bundle", command, [bundle / "semantic_cases.jsonl", bundle / "export_semantic_truth.py", root / "evidence" / "dream7b_hf_small_source_v20.tar.gz"])
    local_torch = run([sys.executable, "-c", "import torch, json; print(json.dumps({'torch': torch.__version__, 'cuda': torch.cuda.is_available()}))"], root)
    semantic_truth_rows = 0
    verdict = "export_bundle_ready_external_run_required"
    report["blocking_or_failure_reasons"].append("Current local Python environment does not provide a verified torch2 + Dream7B model runtime for completing the 8-row semantic truth export in this workspace.")
    report.update(
        {
            "bundle": artifact(bundle, root),
            "bundle_manifest": info["manifest"],
            "local_torch_probe": local_torch,
            "semantic_truth_rows": semantic_truth_rows,
            "verdict": verdict,
        }
    )
    return save_report(root, "3020_x86_gpu_semantic_truth_export_bundle", report, "X86 GPU Semantic Truth Export Bundle", [f"verdict: `{verdict}`", f"semantic_truth_rows: `{semantic_truth_rows}`", f"bundle: `{rel(bundle, root)}`"])


def task3030(root: Path, command: str, truth_rows: int) -> dict[str, Any]:
    report = common(root, "3030_semantic_bpu_island_battery_v20", command, [root / "reports" / "3020_x86_gpu_semantic_truth_export_bundle.json"])
    if truth_rows < 8:
        verdict = "blocked_hf_semantic_truth_rows_missing"
        report["blocking_or_failure_reasons"].append("Task 3 requires 8 semantic HF truth rows; none are available from S100P or local x86/GPU in v20.")
    else:
        verdict = "not_run_truth_rows_present_battery_required"
    report.update({"semantic_truth_rows": truth_rows, "island_rows": 0, "verdict": verdict})
    return save_report(root, "3030_semantic_bpu_island_battery_v20", report, "Semantic BPU Island Battery V20", [f"verdict: `{verdict}`", f"semantic_truth_rows: `{truth_rows}`", "island_rows: `0`"])


def task3040(root: Path, command: str, island: dict[str, Any]) -> dict[str, Any]:
    report = common(root, "3040_ramp_outlier_final_decision", command, [root / "reports" / "3030_semantic_bpu_island_battery_v20.json"])
    verdict = "C_inconclusive_missing_rows"
    report["blocking_or_failure_reasons"].append("Ramp outlier decision requires semantic island rows; semantic truth rows are still missing.")
    report.update({"verdict": verdict, "semantic_truth_rows": island.get("semantic_truth_rows", 0), "island_rows": island.get("island_rows", 0)})
    return save_report(root, "3040_ramp_outlier_final_decision", report, "Ramp Outlier Final Decision", [f"verdict: `{verdict}`"])


def final_docs(root: Path, command: str, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if reports["3020"].get("verdict") == "export_bundle_ready_external_run_required":
        verdict = "D_semantic_truth_export_bundle_ready_external_run_required"
    else:
        verdict = "E_reference_runtime_blocked_after_exhaustive_export_attempts"
    packet = {
        **SAFETY,
        "schema_version": "dream7b_s100p_v20_final_gate_packet",
        "created_at_utc": now(),
        "command": command,
        "final_verdict": verdict,
        "current_full_bpu_path_status": "falsified_against_HF_PyTorch_BF16_logits_truth_v17_v18_baseline",
        "single_case_forward_localization": reports["3010"].get("verdict"),
        "semantic_truth_rows": reports["3020"].get("semantic_truth_rows"),
        "semantic_island_status": reports["3030"].get("verdict"),
        "ramp_outlier_status": reports["3040"].get("verdict"),
        "generation_quality": "not_run_logits_gate_not_passed",
        "product_route": "not_run_generation_gate_not_passed",
        "gates": {k: v.get("verdict") for k, v in reports.items()},
        "paper_safe_claim": "v20 localizes S100P semantic HF reference runtime: direct BF16 safetensors load succeeds, embedding and SDPA are fast, but decoder layers take about 196 seconds each on S100P torch1.8 CPU. The 8-row semantic truth export is therefore moved to an x86/GPU torch2 bundle. No semantic BPU island verdict is claimed without those truth rows.",
    }
    write_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v20.json", packet)
    write_text(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v20.md", "# Dream7B S100P Gate Packet V20\n\n" + "\n".join(f"- {k}: `{v}`" for k, v in {
        "final_verdict": verdict,
        "single_case_forward_localization": packet["single_case_forward_localization"],
        "semantic_truth_rows": packet["semantic_truth_rows"],
        "semantic_island_status": packet["semantic_island_status"],
        "ramp_outlier_status": packet["ramp_outlier_status"],
        "generation_quality": packet["generation_quality"],
        "product_route": packet["product_route"],
    }.items()) + "\n")
    write_text(root / "reports" / "SEMANTIC_TRUTH_STATUS_V20.md", f"# Semantic Truth Status V20\n\nSemantic truth rows: `{packet['semantic_truth_rows']}`. S100P reference runtime is localized as decoder-layer BF16 CPU runtime blocked; x86/GPU export bundle is ready.\n")
    write_text(root / "reports" / "BPU_ISLAND_VERDICT_V20.md", f"# BPU Island Verdict V20\n\nSemantic island status: `{packet['semantic_island_status']}`. No island pass is claimed without semantic HF truth rows.\n")
    write_text(root / "reports" / "DREAM7B_S100P_V20_PAPER_EVIDENCE_DOSSIER.md", "# Dream7B S100P V20 Paper Evidence Dossier\n\nv20 does not repeat full-chain falsification. It localizes the remaining semantic HF truth blocker: the model loads all safetensors weights, embedding is fast, SDPA fallback is fast, and the decoder-layer dense/MLP path is the runtime bottleneck on S100P torch1.8 CPU. The reproducible next step is the included x86/GPU torch2 export bundle. Generation quality and product routes were not run.\n")
    return packet


def copy_path(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def package(root: Path, command: str) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = root / "tmp" / f"dream7b_s100p_v20_for_gptpro_{stamp}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    stems = [
        "3000_v20_baseline_lock",
        "3010_single_case_forward_runtime_localization",
        "3020_x86_gpu_semantic_truth_export_bundle",
        "3030_semantic_bpu_island_battery_v20",
        "3040_ramp_outlier_final_decision",
    ]
    for stem in stems:
        copy_path(root / "reports" / f"{stem}.json", staging / "reports" / f"{stem}.json")
        copy_path(root / "reports" / f"{stem}.md", staging / "reports" / f"{stem}.md")
    for name in ["SEMANTIC_TRUTH_STATUS_V20.md", "BPU_ISLAND_VERDICT_V20.md", "DREAM7B_S100P_V20_PAPER_EVIDENCE_DOSSIER.md"]:
        copy_path(root / "reports" / name, staging / "reports" / name)
    for p in (root / "01_final_evidence").glob("*v20*"):
        copy_path(p, staging / "01_final_evidence" / p.name)
    for p in [
        root / "tools" / "run_v20_single_case_forward_localization.py",
        root / "tools" / "build_v20_research_thread.py",
        root / "evidence" / "dream7b_s100p_v20_execution_20260704" / "evidence" / "single_case_forward_runtime_v20",
        root / "evidence" / "x86_gpu_semantic_truth_export_bundle_v20",
        root / "evidence" / "dream7b_s100p_v20_execution_20260704_remote_evidence.tar.gz",
        root / "evidence_for_gptpro" / "dream7b_s100p_v19_for_gptpro_20260704_025255.zip.sha256.txt",
    ]:
        copy_path(p, staging / rel(p, root))
    write_text(staging / "README.md", "Dream7B/S100P v20 evidence packet. No generation, no product route, no 18888/18889/OpenClaw foreground changes.\n")
    files = []
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            files.append({"path": rel(p, staging), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_json(staging / "MANIFEST.json", {"schema_version": "dream7b_s100p_v20_manifest", "created_at_utc": now(), "file_count": len(files), "files": files})
    manifest_row = {"path": "MANIFEST.json", "size_bytes": (staging / "MANIFEST.json").stat().st_size, "sha256": sha256_file(staging / "MANIFEST.json")}
    write_text(staging / "SHA256SUMS.txt", "\n".join(f"{f['sha256']}  {f['path']}" for f in files + [manifest_row]) + "\n")
    out = root / "evidence_for_gptpro" / f"dream7b_s100p_v20_for_gptpro_{stamp}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, rel(p, staging))
    zip_sha = sha256_file(out)
    write_text(out.with_suffix(out.suffix + ".sha256.txt"), f"{zip_sha}  {out.name}\n")
    report = common(root, "3050_final_v20_package", command, [out])
    with zipfile.ZipFile(out) as zf:
        report.update({"zip_path": rel(out, root), "zip_sha256": zip_sha, "zip_testzip_bad_member": zf.testzip(), "zip_member_count": len(zf.namelist())})
    save_report(root, "3050_final_v20_gate_packet_and_package", report, "Final V20 Gate Packet And Package", [f"zip_path: `{report['zip_path']}`", f"zip_sha256: `{zip_sha}`"])
    shutil.rmtree(staging)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    command = " ".join([sys.executable, *sys.argv])
    reports: dict[str, dict[str, Any]] = {}
    reports["3000"] = task3000(root, command)
    reports["3010"] = task3010(root, command)
    reports["3020"] = task3020(root, command)
    reports["3030"] = task3030(root, command, int(reports["3020"].get("semantic_truth_rows", 0)))
    reports["3040"] = task3040(root, command, reports["3030"])
    packet = final_docs(root, command, reports)
    pkg = package(root, command)
    print(json.dumps({"final_verdict": packet["final_verdict"], "zip": pkg["zip_path"], "zip_sha256": pkg["zip_sha256"], "gates": packet["gates"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
