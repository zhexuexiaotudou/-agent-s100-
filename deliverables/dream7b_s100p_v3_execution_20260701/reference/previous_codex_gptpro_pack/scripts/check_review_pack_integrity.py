#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from dream7b_research_common import host_metadata, now_iso, read_json, read_manifest_csv, sha256_file, write_json, write_text


def rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproduce and verify the Dream7B review package evidence.")
    parser.add_argument("--run-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--review-pack", default=str(Path(__file__).resolve().parents[2] / "dream7b_s100p_diffusion_research_pack_20260701"))
    args = parser.parse_args()
    run_root = Path(args.run_root)
    review = Path(args.review_pack)
    reports = run_root / "reports"
    manifest_path = review / "MANIFEST.csv"
    sha_path = review / "SHA256SUMS.txt"
    checks: list[dict] = []
    errors: list[str] = []

    if not review.is_dir():
        errors.append(f"review_pack_missing:{review}")
    if manifest_path.is_file():
        for row in read_manifest_csv(manifest_path):
            item = review / row["relative_path"]
            actual_exists = item.is_file()
            actual_size = item.stat().st_size if actual_exists else None
            actual_sha = sha256_file(item) if actual_exists else None
            ok = actual_exists and str(actual_size) == str(row["size_bytes"]) and actual_sha == row["sha256"]
            if not ok:
                errors.append(f"manifest_mismatch:{row['relative_path']}")
            checks.append(
                {
                    "relative_path": row["relative_path"],
                    "expected_size": int(row["size_bytes"]),
                    "actual_size": actual_size,
                    "expected_sha256": row["sha256"],
                    "actual_sha256": actual_sha,
                    "ok": ok,
                }
            )
    else:
        errors.append(f"manifest_missing:{manifest_path}")

    sha_lines = sha_path.read_text(encoding="ascii").splitlines() if sha_path.is_file() else []
    if not sha_lines:
        errors.append(f"sha256sums_missing_or_empty:{sha_path}")

    final_packet = read_json(review / "01_final_evidence" / "dream7b_s100p_diffusion_research_packet.json")
    runtime = read_json(review / "02_primary_reports" / "seq128_runtime_gate" / "seq128_s100p_runtime_gate.json")
    logits = read_json(review / "02_primary_reports" / "seq128_logits_compare" / "seq128_logits_reference_compare.json")
    artifact = read_json(review / "05_artifact_metadata" / "seq128_b1_lmheadq16_lasttoken_summary.json")

    final_gates = final_packet.get("gate_status", {})
    consistency = {
        "final_verdict": final_packet.get("verdict"),
        "falsification_layer": final_packet.get("falsification_layer"),
        "compile_status": final_gates.get("compile_feasible", {}).get("status"),
        "runtime_status": final_gates.get("s100p_runtime_valid", {}).get("status"),
        "logits_status": final_gates.get("logits_numerically_valid", {}).get("status"),
        "generation_status": final_gates.get("generation_quality_valid", {}).get("status"),
        "product_status": final_gates.get("product_route_valid", {}).get("status"),
        "runtime_report_verdict": runtime.get("verdict"),
        "runtime_full_chain_pass": (runtime.get("gate_results") or {}).get("full_chain", {}).get("pass"),
        "runtime_final_shape": (runtime.get("gate_results") or {}).get("full_chain", {}).get("final_shape"),
        "logits_report_verdict": logits.get("verdict"),
        "logits_reference": (logits.get("summary") or {}).get("reference"),
        "logits_top1_agreement": (logits.get("summary") or {}).get("top1_agreement"),
        "logits_mean_cosine": (logits.get("summary") or {}).get("mean_cosine"),
        "artifact_seq_len": artifact.get("seq_len"),
        "artifact_batch_size": artifact.get("batch_size"),
        "artifact_hbm_count": artifact.get("hbm_count"),
        "artifact_missing_or_bad": artifact.get("missing_or_bad"),
    }
    if consistency["compile_status"] != "pass":
        errors.append("compile_status_not_pass")
    if consistency["runtime_status"] != "pass" or consistency["runtime_full_chain_pass"] is not True:
        errors.append("runtime_status_not_consistent_pass")
    if consistency["logits_status"] != "fail" or consistency["logits_top1_agreement"] != 0.0:
        errors.append("logits_status_not_consistent_fail")

    excluded = []
    excluded_note = review / "EXCLUDED_LARGE_ARTIFACTS.md"
    if excluded_note.is_file():
        excluded.append(str(excluded_note.relative_to(review)).replace("\\", "/"))

    payload = {
        "report_name": "000_reproduce_existing_evidence",
        "created_at": now_iso(),
        "script": rel(run_root, Path(__file__).resolve()),
        "host": host_metadata(),
        "review_pack": str(review),
        "manifest_entries_checked": len(checks),
        "manifest_ok": not any(not item["ok"] for item in checks),
        "sha256sums_present": bool(sha_lines),
        "consistency": consistency,
        "gate_status": {
            "compile_feasible": "pass" if consistency["compile_status"] == "pass" and artifact.get("hbm_count") == 28 else "inconclusive",
            "s100p_runtime_valid": "pass" if consistency["runtime_status"] == "pass" and consistency["runtime_full_chain_pass"] is True else "inconclusive",
            "logits_numerically_valid_against_gguf_q4km": "fail" if consistency["logits_status"] == "fail" else "inconclusive",
            "generation_quality_valid": "pending",
            "product_route_valid": "pending",
        },
        "excluded_or_unverified_artifacts": excluded,
        "errors": errors,
        "checks": checks,
    }
    out_json = reports / "000_reproduce_existing_evidence.json"
    out_md = reports / "000_reproduce_existing_evidence.md"
    write_json(out_json, payload)
    lines = [
        "# 000 Reproduce Existing Evidence",
        "",
        f"- review_pack: `{review}`",
        f"- manifest_entries_checked: `{len(checks)}`",
        f"- manifest_ok: `{payload['manifest_ok']}`",
        f"- final_verdict: `{consistency['final_verdict']}`",
        f"- falsification_layer: `{consistency['falsification_layer']}`",
        "",
        "## Gate Status",
        "",
    ]
    for key, value in payload["gate_status"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Excluded / Unverified Artifacts", ""])
    lines.extend(f"- `{item}`" for item in excluded) if excluded else lines.append("- none")
    lines.extend(["", "## Errors", ""])
    lines.extend(f"- `{item}`" for item in errors) if errors else lines.append("- none")
    write_text(out_md, "\n".join(lines) + "\n")
    print(out_json)
    print(out_md)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

