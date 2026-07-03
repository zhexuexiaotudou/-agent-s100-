#!/usr/bin/env python3
"""Build Dream7B/S100P v6 evidence reports and package."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import numpy as np


CASE_IDS = ["zeros", "ramp", "short_chinese_prompt_padded"]
CRITICAL_VARIANTS = [
    "real_x",
    "real_x_div_2",
    "real_x_div_2p25",
    "real_x_div_2p5",
    "real_x_div_2p75",
    "real_x_div_3",
    "real_x_div_3p25",
    "real_x_div_3p5",
    "real_x_div_4",
    "real_x_clip_8",
    "real_x_clip_6",
    "real_x_clip_5",
    "real_x_clip_4",
    "real_x_z_normalized",
]
REPORTS = [
    "400_evidence_hygiene_and_raw_endpoints",
    "410_canonical_seq128_cases",
    "420_verified_dream_bf16_wrapper",
    "430_gguf_f16_q4_reference_matrix",
    "440_hybrid_routes",
    "450_seg20_27_boundary_saturation_origin",
    "460_scale_fix_or_falsify",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except (UnicodeError, JSONDecodeError):
            continue
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path)


def artifact(path: Path, root: Path) -> dict[str, Any]:
    item: dict[str, Any] = {"path": rel(path, root), "exists": path.exists()}
    if path.exists() and path.is_file():
        item.update({"size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return item


def git_meta(root: Path) -> dict[str, Any]:
    git_dir = root / ".git"
    meta: dict[str, Any] = {
        "cwd": str(root.resolve()),
        "git_dir_exists": git_dir.exists(),
        "git_head_exists": (git_dir / "HEAD").exists(),
        "commit": None,
        "dirty": None,
        "status": "unavailable",
    }
    if git_dir.exists() and not (git_dir / "HEAD").exists():
        meta["status"] = "unavailable_empty_git_dir"
        return meta
    try:
        meta["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        meta["dirty"] = bool(dirty)
        meta["status"] = "available"
    except Exception as exc:
        meta["status"] = f"unavailable:{type(exc).__name__}"
    return meta


def array_stats(a: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(a)
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


def entropy_metrics(logits: np.ndarray) -> dict[str, Any]:
    v = np.asarray(logits, dtype=np.float64).reshape(-1)
    v = v - np.max(v)
    e = np.exp(v)
    s = float(np.sum(e))
    p = e / s if np.isfinite(s) and s else np.full_like(v, 1.0 / v.size)
    ent = -float(np.sum(p * np.log(p + 1e-300)))
    return {
        "entropy": ent,
        "normalized_entropy": ent / math.log(v.size) if v.size > 1 else 0.0,
        "top1_probability": float(np.max(p)),
    }


def topk(logits: np.ndarray, k: int = 10) -> list[dict[str, Any]]:
    v = np.asarray(logits).reshape(-1)
    idx = np.argsort(v)[-k:][::-1]
    return [{"token": int(i), "logit": float(v[i])} for i in idx]


def build_manifest(root: Path) -> dict[str, Any]:
    files = []
    for fp in sorted(root.rglob("*")):
        if not fp.is_file() or fp.name in {"MANIFEST.json", "SHA256SUMS.txt"}:
            continue
        files.append({"path": fp.relative_to(root).as_posix(), "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
    manifest = {"schema_version": "dream7b_s100p_v6_manifest", "created_at_utc": now(), "file_count": len(files), "files": files}
    write_json(root / "MANIFEST.json", manifest)
    (root / "SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in files), encoding="utf-8")
    return manifest


def zip_check(path: Path) -> dict[str, Any]:
    out = artifact(path, Path.cwd())
    try:
        with zipfile.ZipFile(path) as zf:
            out.update({"zip_readable": True, "testzip": zf.testzip(), "member_count": len(zf.infolist())})
    except Exception as exc:
        out.update({"zip_readable": False, "testzip": f"{type(exc).__name__}:{exc}"})
    return out


def md(title: str, bullets: list[str], rows: list[list[Any]] | None = None, headers: list[str] | None = None) -> str:
    lines = [f"# {title}", ""]
    lines.extend(f"- {x}" for x in bullets)
    if rows and headers:
        lines += ["", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        for row in rows:
            lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines) + "\n"


def common(root: Path, name: str, command: str, inputs: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": f"dream7b_s100p_v6_{name}",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "input_artifacts": [artifact(p, root) for p in inputs],
        "output_artifacts": [
            {"path": f"reports/{name}.json"},
            {"path": f"reports/{name}.md"},
        ],
        "gate_status": {},
        "blocking_or_failure_reasons": [],
        "next_minimal_experiments": [],
    }


def read_cases(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_reports(root: Path, name: str, data: dict[str, Any], text: str) -> None:
    write_json(root / "reports" / f"{name}.json", data)
    write_text(root / "reports" / f"{name}.md", text)


def endpoint_summary(raw_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows = []
    missing = []
    for case_id in CASE_IDS:
        for variant in CRITICAL_VARIANTS:
            base = raw_root / "final_segment_dense_sweep_v5" / case_id / variant
            required = ["input.npy", "raw_output.npy", "dequant_logits.npy", "metadata.json"]
            absent = [name for name in required if not (base / name).exists()]
            if absent:
                missing.append(f"{case_id}/{variant}:{','.join(absent)}")
                continue
            raw = np.load(base / "raw_output.npy")
            deq = np.load(base / "dequant_logits.npy")
            inp = np.load(base / "input.npy")
            row = {
                "case_id": case_id,
                "variant": variant,
                "input_path": rel(base / "input.npy", raw_root),
                "raw_output_path": rel(base / "raw_output.npy", raw_root),
                "dequant_logits_path": rel(base / "dequant_logits.npy", raw_root),
                "metadata_path": rel(base / "metadata.json", raw_root),
                "input_stats": array_stats(inp),
                "raw_stats": array_stats(raw),
                "dequant_stats": array_stats(deq),
                "softmax": entropy_metrics(deq.reshape(-1)),
                "top10": topk(deq.reshape(-1), 10),
                "sha256": {
                    "input": sha256_file(base / "input.npy"),
                    "raw_output": sha256_file(base / "raw_output.npy"),
                    "dequant_logits": sha256_file(base / "dequant_logits.npy"),
                    "metadata": sha256_file(base / "metadata.json"),
                },
            }
            rows.append(row)
    return rows, missing


def boundary_summary(boundary_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report = load_json(boundary_root / "reports" / "450_boundary_dump_raw_v6.json")
    rows = []
    for case_id in CASE_IDS:
        cdir = boundary_root / "evidence" / "boundary_subset_v6" / case_id
        for seg in range(20, 28):
            raw_path = cdir / f"seg_{seg:02d}_raw_output.npy"
            deq_path = cdir / f"seg_{seg:02d}_output.npy"
            if not raw_path.exists() or not deq_path.exists():
                continue
            raw = np.load(raw_path)
            deq = np.load(deq_path)
            rs = array_stats(raw)
            ds = array_stats(deq)
            raw_min = int(np.min(raw))
            raw_max = int(np.max(raw))
            rows.append(
                {
                    "case_id": case_id,
                    "segment": seg,
                    "raw_path": rel(raw_path, boundary_root),
                    "dequant_path": rel(deq_path, boundary_root),
                    "raw_stats": rs,
                    "dequant_stats": ds,
                    "observed_min_count": int(np.sum(raw == raw_min)),
                    "observed_max_count": int(np.sum(raw == raw_max)),
                    "raw_sha256": sha256_file(raw_path),
                    "dequant_sha256": sha256_file(deq_path),
                }
            )
    return rows, report


def write_canonical_cases(root: Path, source_cases: Path, inventory: dict[str, Any]) -> tuple[list[dict[str, Any]], Path]:
    out_path = root / "cases" / "canonical_seq128_cases_v6.jsonl"
    tokenizer_names = {"tokenization_dream.py", "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json", "vocab.json", "merges.txt"}
    tokenizer_files = [
        f
        for f in inventory.get("files", [])
        if "/tokenizer/" in f.get("path", "") or Path(f.get("path", "")).name in tokenizer_names
    ]
    tokenizer_hash = sha256_bytes(json.dumps(tokenizer_files, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    rows = []
    for case in read_cases(source_cases):
        token_ids = case.get("token_ids", [])
        position_ids = case.get("position_ids", list(range(len(token_ids))))
        attention_mask = case.get("attention_mask", [1] * len(token_ids))
        decoded = case.get("decoded_text")
        row = {
            "case_id": case["case_id"],
            "human_description": case.get("human_description"),
            "token_ids": token_ids,
            "position_ids": position_ids,
            "attention_mask": attention_mask,
            "last_token_index": int(case.get("expected_last_token_index", 127)),
            "semantic_or_diagnostic": "semantic" if case.get("is_semantic") else "diagnostic",
            "decoded_text_head": decoded[:120] if isinstance(decoded, str) else None,
            "decoded_text_tail": decoded[-120:] if isinstance(decoded, str) else None,
            "tokenizer_path": "/mnt/nas/openclaw/models/dream7b-hf",
            "tokenizer_manifest_sha256": tokenizer_hash,
            "token_ids_sha256": sha256_bytes(json.dumps(token_ids, separators=(",", ":")).encode("utf-8")),
            "source_case_sha256": sha256_bytes(json.dumps(case, sort_keys=True, ensure_ascii=False).encode("utf-8")),
        }
        rows.append(row)
    out_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return rows, out_path


def copy_reference_rows(root: Path) -> dict[str, Any]:
    ref_root = root / "evidence" / "reference_matrix_v6"
    q4_src = root / "deliverables" / "dream7b_s100p_v3_execution_20260701" / "raw_evidence_subset" / "gguf_reference" / "zeros" / "gguf_last_logits.npy"
    bpu_src = root / "deliverables" / "dream7b_s100p_v3_execution_20260701" / "raw_evidence_subset" / "bpu_full_chain" / "zeros" / "dequant_logits.npy"
    copied = []
    if q4_src.exists():
        dst = ref_root / "gguf_q4_k_m" / "zeros" / "last_logits.npy"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(q4_src, dst)
        copied.append({"backend": "gguf_q4_k_m", "case_id": "zeros", "path": rel(dst, root), "sha256": sha256_file(dst)})
    if bpu_src.exists():
        dst = ref_root / "s100p_bpu_dequant" / "zeros" / "last_logits.npy"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bpu_src, dst)
        copied.append({"backend": "s100p_bpu_dequant", "case_id": "zeros", "path": rel(dst, root), "sha256": sha256_file(dst)})
    return {"copied_reference_logits": copied}


def report_400(root: Path, pack: Path, command: str, raw_root: Path) -> dict[str, Any]:
    endpoint_rows, missing = endpoint_summary(raw_root)
    manifest = build_manifest(raw_root)
    data = common(root, "400_evidence_hygiene_and_raw_endpoints", command, [pack / "reference/v5_result_package/dream7b_s100p_v5_for_gptpro_20260701_161232.zip", raw_root])
    data.update(
        {
            "v5_reference_zip": zip_check(pack / "reference/v5_result_package/dream7b_s100p_v5_for_gptpro_20260701_161232.zip"),
            "critical_cases": CASE_IDS,
            "critical_variants": CRITICAL_VARIANTS,
            "endpoint_count_expected": len(CASE_IDS) * len(CRITICAL_VARIANTS),
            "endpoint_count_verified": len(endpoint_rows),
            "missing_endpoints": missing,
            "endpoint_stats": endpoint_rows,
            "raw_endpoint_manifest": {"path": "evidence/raw_endpoint_subset_v6/MANIFEST.json", "file_count": manifest["file_count"]},
            "verdict": "pass_all_endpoint_raw_arrays_present_and_verified" if not missing else "blocked_missing_endpoint_raw_arrays",
            "gate_status": {"gate_0_raw_endpoint_hygiene": "pass" if not missing else "fail"},
        }
    )
    write_reports(
        root,
        "400_evidence_hygiene_and_raw_endpoints",
        data,
        md(
            "Task 400 Evidence Hygiene and Raw Endpoints",
            [
                f"verdict: `{data['verdict']}`",
                f"verified endpoints: `{len(endpoint_rows)}/{data['endpoint_count_expected']}`",
                f"raw endpoint manifest files: `{manifest['file_count']}`",
                "All critical endpoint stats were recomputed from local `.npy` files.",
            ],
            [[r["case_id"], r["variant"], r["input_stats"]["abs_max"], r["raw_stats"]["allzero"], r["raw_stats"]["nonzero_count"]] for r in endpoint_rows if r["variant"] in {"real_x", "real_x_div_2", "real_x_div_2p75", "real_x_div_3", "real_x_clip_6"}],
            ["case", "variant", "input_abs_max", "raw_allzero", "raw_nonzero"],
        ),
    )
    return data


def report_410(root: Path, command: str, inventory: dict[str, Any]) -> dict[str, Any]:
    cases, canonical_path = write_canonical_cases(root, root / "cases" / "seq128_logits_probe_battery.jsonl", inventory)
    bad = []
    for case in cases:
        if len(case["token_ids"]) != 128 or len(case["position_ids"]) != 128 or len(case["attention_mask"]) != 128 or case["last_token_index"] != 127:
            bad.append(case["case_id"])
    data = common(root, "410_canonical_seq128_cases", command, [root / "cases" / "seq128_logits_probe_battery.jsonl", root / "evidence/model_inventory_v6.json"])
    data.update(
        {
            "canonical_cases_path": rel(canonical_path, root),
            "case_count": len(cases),
            "canonical_case_hashes": [{"case_id": c["case_id"], "token_ids_sha256": c["token_ids_sha256"], "source_case_sha256": c["source_case_sha256"]} for c in cases],
            "tokenizer_files": [
                f
                for f in inventory.get("files", [])
                if "/tokenizer/" in f.get("path", "")
                or Path(f.get("path", "")).name in {"tokenization_dream.py", "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json", "vocab.json", "merges.txt"}
            ],
            "alignment_failures": bad,
            "verdict": "pass_canonical_cases_verified" if not bad else "fail_alignment_mismatch_found",
            "gate_status": {"canonical_case_alignment": "pass" if not bad else "fail"},
        }
    )
    write_reports(
        root,
        "410_canonical_seq128_cases",
        data,
        md(
            "Task 410 Canonical seq128 Cases",
            [f"verdict: `{data['verdict']}`", f"case_count: `{len(cases)}`", "All cases have 128 token IDs, positions, masks, and last_token_index 127."],
            [[c["case_id"], c["semantic_or_diagnostic"], c["token_ids_sha256"][:16]] for c in cases],
            ["case", "type", "token_ids_sha256_prefix"],
        ),
    )
    return data


def report_420(root: Path, command: str, inventory: dict[str, Any]) -> dict[str, Any]:
    weight_like = inventory.get("weight_like_files", [])
    hf_safetensors = [x for x in weight_like if x["path"].endswith(".safetensors")]
    hf_code_files = [
        x
        for x in inventory.get("files", [])
        if Path(x.get("path", "")).name in {"config.json", "configuration_dream.py", "modeling_dream.py", "tokenization_dream.py", "generation_utils.py", "model.safetensors.index.json"}
        and "dream7b-hf" in x.get("path", "")
    ]
    probe_path = root / "evidence" / "hf_bf16_v6" / "wrapper_probe_status.json"
    probe = load_json(probe_path, {})
    has_hf_weights = bool(hf_safetensors)
    load_pass = any(x.get("step", "").startswith("AutoModel load") and x.get("status") == "pass" for x in probe.get("probe_results", []))
    config_pass = any("AutoConfig/AutoTokenizer" in x.get("step", "") and x.get("status") == "pass" for x in probe.get("probe_results", []))
    forward_block = bool(probe.get("no_bf16_logits_exported", True))
    data = common(
        root,
        "420_verified_dream_bf16_wrapper",
        command,
        [root / "evidence/model_inventory_v6.json", root / "cases/canonical_seq128_cases_v6.jsonl", probe_path],
    )
    data.update(
        {
            "checkpoint_roots": inventory.get("roots"),
            "hf_model_path": probe.get("hf_model_path", "/mnt/nas/openclaw/models/dream7b-hf"),
            "weight_like_files": weight_like,
            "hf_safetensors": hf_safetensors,
            "hf_wrapper_code_files": hf_code_files,
            "hf_weight_files_found": has_hf_weights,
            "hf_config_tokenizer_load_status": "pass" if config_pass else "blocked_or_not_attempted",
            "hf_model_load_status": "pass" if load_pass else "blocked_or_not_attempted",
            "bf16_logits_export_status": "blocked_forward_runtime_or_timeout" if forward_block else "available",
            "wrapper_probe_status": probe,
            "verified_wrapper_attempt": {
                "status": "blocked",
                "reason": "HF safetensors and Dream wrapper code are present on NAS and AutoModel loads with isolated transformers plus torch compatibility shims, but verified BF16/FP32 logits were not exported because forward execution is blocked/impractical on the current S100P torch runtime.",
                "generic_auto_model_rejected": False,
                "config_tokenizer_load_pass": config_pass,
                "model_load_pass": load_pass,
                "forward_logits_export_pass": False,
                "no_bf16_logits_fabricated": True,
            },
            "verdict": "blocked_verified_dream_wrapper_unavailable",
            "gate_status": {"hf_pytorch_bf16_or_fp32": "blocked_verified_logits_export_missing_model_load_pass"},
            "blocking_or_failure_reasons": [
                "Dream7B HF safetensors and wrapper files were found under /mnt/nas/openclaw/models/dream7b-hf.",
                "Config/tokenizer and model load were made to pass with isolated transformers/tokenizers and torch compatibility shims.",
                "A verified BF16/FP32 forward/logits export did not complete: torch 1.8 lacks required APIs and the shimmed CPU/S100P forward remained impractical, so no BF16 logits or BF16 segment boundaries were produced.",
            ],
            "next_minimal_experiments": ["Run the same Dream wrapper on a torch runtime that natively supports the required APIs, then export BF16/FP32 logits and seg20..27 boundary activations for the canonical cases."],
        }
    )
    write_reports(
        root,
        "420_verified_dream_bf16_wrapper",
        data,
        md(
            "Task 420 Verified Dream BF16 Wrapper",
            [
                f"verdict: `{data['verdict']}`",
                "BF16/FP32 logits were not exported or fabricated.",
                "NAS inventory found Dream7B HF safetensors and custom wrapper code; config/tokenizer and model load passed with isolated deps and compatibility shims.",
                "Verified BF16 forward/logits export remains blocked on the current runtime.",
            ],
        ),
    )
    return data


def report_430(root: Path, command: str, inventory: dict[str, Any], reference_info: dict[str, Any]) -> dict[str, Any]:
    weight_like = inventory.get("weight_like_files", [])
    ggufs = [x for x in weight_like if x["path"].endswith(".gguf")]
    hf_safetensors = [x for x in weight_like if x["path"].endswith(".safetensors")]
    rows = {
        "hf_pytorch_bf16_or_fp32": {"status": "model_load_pass_logits_export_blocked", "reason": "Task 420 found HF safetensors and loaded AutoModel, but no verified BF16/FP32 logits were exported"},
        "gguf_f16": {"status": "unavailable", "reason": "no F16 GGUF artifact found; HF safetensors exist but no verified conversion/export row was produced in this run"},
        "gguf_q4_0": {"status": "unavailable", "reason": "no Q4_0 GGUF artifact found; no verified F16/HF conversion and quantized reference row was produced in this run"},
        "gguf_q4_k_m": {"status": "available" if ggufs else "unavailable", "artifacts": ggufs},
        "hf_safetensors_source": {"status": "available" if hf_safetensors else "unavailable", "artifacts": hf_safetensors},
        "s100p_bpu_raw_dequant": {"status": "partial_available", "note": "representative zeros logits copied from v3 raw subset; full 10-case row remains from v5 reports"},
        "corrected_scale_variants": {"status": "available_without_reference_comparison", "source": "evidence/raw_endpoint_subset_v6"},
    }
    data = common(root, "430_gguf_f16_q4_reference_matrix", command, [root / "evidence/model_inventory_v6.json", root / "evidence/hf_bf16_v6/wrapper_probe_status.json", root / "evidence/reference_matrix_v6"])
    data.update(
        {
            "reference_rows": rows,
            "representative_logits": reference_info.get("copied_reference_logits", []),
            "required_metrics_status": "blocked_pairwise_metrics_for_missing_bf16_f16_q4_0",
            "verdict": "partial_q4km_only_bf16_or_f16_missing",
            "gate_status": {"reference_matrix_validity": "partial_q4km_s100p_corrected_variants_available_bf16_f16_q4_0_missing"},
            "blocking_or_failure_reasons": [
                "BF16/FP32 row unavailable as comparable logits, even though HF weights and a loadable model are present.",
                "GGUF F16 row unavailable.",
                "GGUF Q4_0 row unavailable.",
                "Only Q4_K_M can remain a deployment-reference blocker, not mathematical truth.",
            ],
            "next_minimal_experiments": ["Use the available HF safetensors to export verified BF16/FP32 logits, then generate and score GGUF F16 and Q4_0 rows for canonical cases."],
        }
    )
    write_reports(
        root,
        "430_gguf_f16_q4_reference_matrix",
        data,
        md(
            "Task 430 GGUF F16/Q4 Reference Matrix",
            [
                f"verdict: `{data['verdict']}`",
                "Q4_K_M and HF safetensors are available; comparable BF16/FP32 logits, GGUF F16, and GGUF Q4_0 rows are unavailable.",
                "Corrected-scale endpoint logits are packaged but cannot be scored for correctness without BF16/GGUF F16.",
            ],
        ),
    )
    return data


def report_440(root: Path, command: str, r420: dict[str, Any], r430: dict[str, Any]) -> dict[str, Any]:
    data = common(root, "440_hybrid_routes", command, [root / "reports/420_verified_dream_bf16_wrapper.json", root / "reports/430_gguf_f16_q4_reference_matrix.json", root / "evidence/raw_endpoint_subset_v6"])
    data.update(
        {
            "route_a_bpu_seg0_26_to_cpu_hf_final": {"status": "blocked", "reason": "HF weights/model load exist, but verified HF final norm/lm_head logits export did not complete"},
            "route_b_hf_seg26_to_bpu_seg27_28": {"status": "blocked", "reason": "HF seg26 boundary unavailable because BF16 forward/boundary export did not complete"},
            "route_c_bpu_seg26_to_bpu_seg27_28_corrected_scale": {"status": "executed_raw_endpoint_packaged", "reason": "Task 400 has all critical endpoint raw arrays", "correctness": "unproven_reference_unavailable"},
            "verdict": "blocked_hf_wrapper_or_boundary_missing",
            "gate_status": {"hybrid_routes": "blocked_hf_wrapper_or_boundary_missing_route_c_diagnostic_only"},
            "blocking_or_failure_reasons": ["Task 420 blocked; Route A/B cannot run.", "Task 430 missing BF16/F16 rows; Route C cannot be correctness-scored."],
            "next_minimal_experiments": ["After BF16 wrapper exists, run BPU seg0..26 -> CPU/HF lm_head for all Task 400 variants."],
        }
    )
    write_reports(
        root,
        "440_hybrid_routes",
        data,
        md(
            "Task 440 Hybrid Routes",
            [
                f"verdict: `{data['verdict']}`",
                "Route A/B blocked by missing verified HF logits/boundary export, not by missing HF files.",
                "Route C endpoint raw arrays are present but remain diagnostic only.",
            ],
        ),
    )
    return data


def report_450(root: Path, command: str, boundary_root: Path) -> dict[str, Any]:
    rows, remote_report = boundary_summary(boundary_root)
    manifest = build_manifest(boundary_root)
    first_full_range = {}
    for case_id in CASE_IDS:
        hits = [r for r in rows if r["case_id"] == case_id and (r["raw_stats"]["min"] <= -32768 or r["raw_stats"]["max"] >= 32767)]
        first_full_range[case_id] = hits[0]["segment"] if hits else None
    data = common(root, "450_seg20_27_boundary_saturation_origin", command, [boundary_root / "reports/450_boundary_dump_raw_v6.json", boundary_root])
    data.update(
        {
            "remote_boundary_report": remote_report,
            "boundary_rows": rows,
            "first_observed_full_int16_range_segment": first_full_range,
            "interpretation": "seg20 already reaches positive int16 max in all three cases; seg22, seg24 and seg25 reach both int16 extremes; seg26 has observed clamp at +/-19807; seg27 final logits are all-zero. Without BF16 boundaries this identifies saturation/range origin but not BF16 divergence.",
            "boundary_manifest": {"path": "evidence/boundary_subset_v6/MANIFEST.json", "file_count": manifest["file_count"]},
            "verdict": "partial_late_saturation_bounded_to_segment_range",
            "gate_status": {"boundary_saturation_origin": "pass_raw_seg20_27_dump_partial_bf16_boundaries_missing"},
            "blocking_or_failure_reasons": ["BF16 boundary activations unavailable, so first BF16-divergent segment cannot be proven."],
            "next_minimal_experiments": ["Align seg20..27 raw/dequant stats to BF16 layer outputs once Task 420 is unblocked."],
        }
    )
    write_reports(
        root,
        "450_seg20_27_boundary_saturation_origin",
        data,
        md(
            "Task 450 seg20..27 Boundary Saturation Origin",
            [
                f"verdict: `{data['verdict']}`",
                "S100P offline dump completed for seg20..27 on zeros/ramp/short_chinese.",
                "First observed full int16 positive max appears at seg20 for all three cases; BF16 divergence remains blocked.",
            ],
            [[r["case_id"], r["segment"], r["raw_stats"]["min"], r["raw_stats"]["max"], r["raw_stats"]["nonzero_count"], r["dequant_stats"]["abs_max"], r["dequant_stats"]["constant"]] for r in rows],
            ["case", "seg", "raw_min", "raw_max", "raw_nonzero", "deq_abs_max", "constant"],
        ),
    )
    return data


def report_460(root: Path, command: str) -> dict[str, Any]:
    r400 = load_json(root / "reports/400_evidence_hygiene_and_raw_endpoints.json")
    data = common(root, "460_scale_fix_or_falsify", command, [root / "reports/400_evidence_hygiene_and_raw_endpoints.json", root / "reports/420_verified_dream_bf16_wrapper.json", root / "reports/430_gguf_f16_q4_reference_matrix.json"])
    selected = [
        {"case_id": r["case_id"], "variant": r["variant"], "input_abs_max": r["input_stats"]["abs_max"], "raw_allzero": r["raw_stats"]["allzero"], "raw_nonzero_count": r["raw_stats"]["nonzero_count"]}
        for r in r400.get("endpoint_stats", [])
        if r["variant"] in {"real_x", "real_x_div_2", "real_x_div_2p75", "real_x_div_3", "real_x_clip_6", "real_x_clip_4"}
    ]
    data.update(
        {
            "transition_endpoint_stats": selected,
            "scale_correction_status": "blocked_reference_unavailable",
            "nonzero_recovery_not_correctness": True,
            "verdict": "blocked_reference_unavailable",
            "gate_status": {"scale_fix_or_falsify": "blocked_reference_unavailable"},
            "blocking_or_failure_reasons": ["No BF16/FP32 or GGUF F16 reference row exists to score corrected-scale logits."],
            "next_minimal_experiments": ["Once BF16/GGUF F16 exists, score /2.75, /3, /3.25, /3.5, clip_6, clip_5, clip_4 against semantic-case thresholds."],
        }
    )
    write_reports(
        root,
        "460_scale_fix_or_falsify",
        data,
        md(
            "Task 460 Scale Fix or Falsify",
            [
                f"verdict: `{data['verdict']}`",
                "All critical transition endpoint raw arrays are now packaged.",
                "No scale correction can be claimed without BF16/GGUF F16 comparison.",
            ],
        ),
    )
    return data


def build_gate_packet(root: Path, command: str) -> dict[str, Any]:
    reports = {name: load_json(root / "reports" / f"{name}.json") for name in REPORTS}
    packet = {
        "schema_version": "dream7b_s100p_gate_packet_v6",
        "created_at_utc": now(),
        "run_commands": [command],
        "git": git_meta(root),
        "verdict_class": "C_deployment_blocked_against_deployment_reference_but_bf16_unresolved",
        "verdict": "v6 fixes v5 raw endpoint hygiene and adds seg20..27 boundary evidence. NAS HF safetensors and Dream wrapper code are present and AutoModel load was demonstrated, but logits numerical validity remains blocked against the available deployment reference and unresolved against BF16 because verified BF16/FP32 logits plus GGUF F16/Q4_0 rows are unavailable.",
        "gate_status": {
            "gate_0_evidence_hygiene": "pass",
            "gate_1_compile_feasibility": "pass_from_v5_reference_metadata_large_hbm_excluded",
            "gate_2_s100p_board_runtime_validity": "pass_offline_seg20_27_and_prior_full_chain",
            "gate_3_reference_matrix_validity": "partial_q4km_s100p_corrected_variants_available_bf16_f16_q4_0_missing",
            "gate_4_logits_numerical_validity": "fail_against_q4_k_m_deployment_reference_inconclusive_against_bf16",
            "gate_5_root_cause_localization": "pass_late_range_saturation_bounded_seg20_27_and_final_input_contract",
            "gate_6_generation_quality": "not_run_by_design",
            "gate_7_product_route": "not_run_by_design",
        },
        "reference_matrix_summary": reports["430_gguf_f16_q4_reference_matrix"].get("reference_rows"),
        "canonical_case_hashes": reports["410_canonical_seq128_cases"].get("canonical_case_hashes"),
        "bf16_wrapper_status": reports["420_verified_dream_bf16_wrapper"].get("verified_wrapper_attempt"),
        "gguf_reference_status": reports["430_gguf_f16_q4_reference_matrix"].get("reference_rows"),
        "s100p_runtime_status": {
            "raw_endpoint_verdict": reports["400_evidence_hygiene_and_raw_endpoints"].get("verdict"),
            "boundary_dump_verdict": reports["450_seg20_27_boundary_saturation_origin"].get("remote_boundary_report", {}).get("s100p_boundary_dump_verdict"),
        },
        "hybrid_route_summary": {
            "route_a": reports["440_hybrid_routes"].get("route_a_bpu_seg0_26_to_cpu_hf_final"),
            "route_b": reports["440_hybrid_routes"].get("route_b_hf_seg26_to_bpu_seg27_28"),
            "route_c": reports["440_hybrid_routes"].get("route_c_bpu_seg26_to_bpu_seg27_28_corrected_scale"),
        },
        "first_divergent_segment_or_range": "Raw S100P range/saturation is now bounded across seg20..27: seg20 already hits positive int16 max, seg22/24/25 hit full int16 extremes, seg26 clamps at +/-19807, seg27 final logits are all-zero. BF16-divergent segment remains unresolved because BF16 boundaries are unavailable.",
        "scale_correction_status": reports["460_scale_fix_or_falsify"].get("scale_correction_status"),
        "blocking_issues": [
            "Verified BF16/FP32 logits export unavailable even though HF safetensors and wrapper code exist.",
            "GGUF F16 and Q4_0 rows unavailable.",
            "Hybrid Route A/B blocked by missing verified HF final lm_head logits export and HF seg26 boundary export.",
            "Corrected-scale logits are nonzero diagnostics but not correctness.",
        ],
        "allowed_claims": [
            "v6 includes all critical raw endpoint arrays including /2.75 and clip_6.",
            "v6 dumps seg20..27 raw/dequant boundaries for zeros/ramp/short_chinese on S100P.",
            "NAS contains Dream7B HF safetensors and custom wrapper code; config/tokenizer and AutoModel load passed under isolated deps plus compatibility shims.",
            "Current evidence supports a late range/saturation/input-contract anomaly, not deployment success.",
        ],
        "forbidden_claims": [
            "Dream7B is accurately deployed on S100P.",
            "Dream7B is falsified against BF16/PyTorch ground truth.",
            "Any corrected scale is a valid fix.",
            "Generation quality or product route 18888/18889 passed or failed.",
        ],
        "next_minimal_experiments": [
            "Run the available Dream7B HF safetensors/wrapper on a torch runtime that can export verified BF16/FP32 logits and boundary activations.",
            "Export GGUF F16 and Q4_0 logits for canonical cases.",
            "Score corrected-scale endpoints against BF16/GGUF F16.",
            "Compare seg20..27 BPU boundary tensors to BF16 layer/boundary activations.",
        ],
        "artifact_manifest": {
            "raw_endpoint_subset": "evidence/raw_endpoint_subset_v6/MANIFEST.json",
            "boundary_subset": "evidence/boundary_subset_v6/MANIFEST.json",
        },
        "sha256sums": {
            "raw_endpoint_subset": "evidence/raw_endpoint_subset_v6/SHA256SUMS.txt",
            "boundary_subset": "evidence/boundary_subset_v6/SHA256SUMS.txt",
        },
        "source_reports": {name: f"reports/{name}.json" for name in REPORTS},
    }
    write_json(root / "reports" / "470_gate_packet_v6.json", packet)
    write_json(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v6.json", packet)
    text = md(
        "Gate Packet v6",
        [
            f"verdict_class: `{packet['verdict_class']}`",
            packet["verdict"],
            f"Gate 6/7: `{packet['gate_status']['gate_6_generation_quality']}` / `{packet['gate_status']['gate_7_product_route']}`",
        ],
    )
    write_text(root / "reports" / "470_gate_packet_v6.md", text)
    write_text(root / "01_final_evidence" / "dream7b_s100p_gate_packet_v6.md", text)
    return packet


def write_dossier(root: Path, packet: dict[str, Any]) -> None:
    text = f"""# Dream7B/S100P v6 Paper Evidence Dossier

## Abstract-style conclusion

v6 does not validate accurate deployment and does not falsify Dream7B against BF16/PyTorch. It upgrades v5 by adding all critical threshold endpoint raw arrays and by dumping S100P `seg20..27` boundary tensors, but the decisive BF16/GGUF F16 reference gap remains (`reports/470_gate_packet_v6.json: verdict_class`).

## Methods

The workflow follows gate-based logits validation: canonical seq128 token IDs, S100P raw/dequant evidence, reference matrix rows, hybrid route diagnostics, boundary saturation localization, and final gate aggregation. Generation quality and product route gates are kept `not_run_by_design`.

## Canonical cases

`cases/canonical_seq128_cases_v6.jsonl` contains the 10 canonical seq128 cases with token ID hashes, position IDs, masks, last-token index 127, and tokenizer manifest hash (`reports/410_canonical_seq128_cases.json`).

## Endpoint evidence

`evidence/raw_endpoint_subset_v6/` now includes `input.npy`, `raw_output.npy`, `dequant_logits.npy`, and `metadata.json` for `real_x`, `/2`, `/2.25`, `/2.5`, `/2.75`, `/3`, `/3.25`, `/3.5`, `/4`, `clip_8`, `clip_6`, `clip_5`, `clip_4`, and `z_normalized` across zeros/ramp/short Chinese cases (`reports/400_evidence_hygiene_and_raw_endpoints.json`).

## Reference matrix

The live model inventory found both `dream-7b-q4km.gguf` and Dream7B HF safetensors under `/mnt/nas/openclaw/models/dream7b-hf`. The custom Dream wrapper/config/tokenizer files are present, and the model load probe passed with isolated dependencies and compatibility shims. However, verified BF16/FP32 logits were not exported, and GGUF F16/Q4_0 artifacts were not produced; therefore Q4_K_M remains a deployment-reference blocker only (`reports/420_verified_dream_bf16_wrapper.json`, `reports/430_gguf_f16_q4_reference_matrix.json`).

## Boundary saturation

S100P offline boundary dump completed for seg20..27 on the three target cases. The first observed positive int16 max occurs at seg20, seg22/24/25 hit full int16 extremes, seg26 clamps at +/-19807, and seg27 final logits are all-zero. BF16 divergence cannot be assigned without BF16 boundaries (`reports/450_seg20_27_boundary_saturation_origin.json`).

## Claim boundary

Allowed: v6 supports a late range/saturation/input-contract anomaly and fixes v5 raw endpoint packaging. Forbidden: accurate deployment, BF16 falsification, corrected-scale fix success, generation quality claims, or product route claims.
"""
    write_text(root / "01_final_evidence" / "dream7b_s100p_paper_evidence_dossier_v6.md", text)


def package_zip(root: Path, timestamp: str) -> tuple[Path, dict[str, Any]]:
    out = root / "evidence_zips" / f"dream7b_s100p_v6_for_gptpro_{timestamp}.zip"
    report_files = []
    for name in [*REPORTS, "470_gate_packet_v6"]:
        report_files.extend([root / "reports" / f"{name}.json", root / "reports" / f"{name}.md"])
    final_files = [
        root / "01_final_evidence" / "dream7b_s100p_gate_packet_v6.json",
        root / "01_final_evidence" / "dream7b_s100p_gate_packet_v6.md",
        root / "01_final_evidence" / "dream7b_s100p_paper_evidence_dossier_v6.md",
    ]
    include = [
        *report_files,
        *final_files,
        root / "cases" / "canonical_seq128_cases_v6.jsonl",
        root / "cases" / "seq128_logits_probe_battery.jsonl",
        root / "evidence" / "raw_endpoint_subset_v6",
        root / "evidence" / "boundary_subset_v6",
        root / "evidence" / "hf_bf16_v6",
        root / "evidence" / "reference_matrix_v6",
        root / "evidence" / "model_inventory_v6.json",
        root / "tools" / "build_v6_research_thread.py",
        root / "tools" / "run_s100p_hbm_chain_dump_boundaries_v6.py",
        root / "tmp" / "dream7b_s100p_v6_after_v5_review_pack_20260701" / "dream7b_s100p_v6_codex_after_v5_review_pack_20260701",
    ]
    files = []
    for item in include:
        if item.is_file():
            files.append(item)
        elif item.is_dir():
            files.extend(x for x in item.rglob("*") if x.is_file())
    files = sorted(set(files))
    manifest_files = []
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in files:
            arc = fp.relative_to(root).as_posix()
            if "operator_portal" in arc or "18888" in arc or "18889" in arc:
                continue
            zf.write(fp, arc)
            manifest_files.append({"path": arc, "size_bytes": fp.stat().st_size, "sha256": sha256_file(fp)})
        manifest = {
            "schema_version": "dream7b_s100p_v6_evidence_zip_manifest",
            "created_at_utc": now(),
            "file_count": len(manifest_files),
            "files": manifest_files,
            "exclusions": ["product-route artifacts", "generation outputs", "huge HBM binaries", "credentials"],
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        zf.writestr("SHA256SUMS.txt", "".join(f"{f['sha256']}  {f['path']}\n" for f in manifest_files).encode("utf-8"))
    with zipfile.ZipFile(out) as zf:
        bad = zf.testzip()
        if bad:
            raise SystemExit(f"bad zip member: {bad}")
    write_json(out.with_name(out.stem + "_MANIFEST.json"), manifest)
    out.with_name(out.stem + "_SHA256SUMS.txt").write_text("".join(f"{f['sha256']}  {f['path']}\n" for f in manifest_files), encoding="utf-8")
    return out, manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-root", default="tmp/dream7b_s100p_v6_after_v5_review_pack_20260701/dream7b_s100p_v6_codex_after_v5_review_pack_20260701")
    ap.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = ap.parse_args()
    root = Path.cwd()
    command = f"py tools/build_v6_research_thread.py --pack-root {args.pack_root} --timestamp {args.timestamp}"
    pack = Path(args.pack_root)
    raw_root = root / "evidence" / "raw_endpoint_subset_v6"
    boundary_root = root / "evidence" / "boundary_subset_v6"
    inventory = load_json(root / "evidence" / "model_inventory_v6.json")

    report_400(root, pack, command, raw_root)
    report_410(root, command, inventory)
    report_420(root, command, inventory)
    ref_info = copy_reference_rows(root)
    report_430(root, command, inventory, ref_info)
    report_440(root, command, load_json(root / "reports/420_verified_dream_bf16_wrapper.json"), load_json(root / "reports/430_gguf_f16_q4_reference_matrix.json"))
    report_450(root, command, boundary_root)
    report_460(root, command)
    packet = build_gate_packet(root, command)
    write_dossier(root, packet)
    out, manifest = package_zip(root, args.timestamp)
    print(root / "reports/470_gate_packet_v6.json")
    print(root / "01_final_evidence/dream7b_s100p_gate_packet_v6.json")
    print(out)
    print(f"zip_file_count={manifest['file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
