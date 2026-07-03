#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from common_artifact_utils import sha256_file, utc_now_iso, write_json


def array_meta(path: Path) -> dict[str, Any]:
    arr = np.load(path, mmap_mode="r")
    return {"dtype": str(arr.dtype), "shape": list(arr.shape)}


def inventory_file(path: Path, root: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    row = {"relative_path": rel, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
    if path.suffix == ".npy":
        row.update(array_meta(path))
    return row


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_readme(root: Path) -> None:
    write_text(
        root / "README_FOR_GPT_PRO.md",
        """# Dream7B S100P v3 Evidence Pack

This package is for GPT Pro review of the v3 Dream7B/S100P localization run.

Primary files:

- `01_final_evidence/dream7b_s100p_gate_packet_v3.json`
- `01_final_evidence/dream7b_s100p_final_technical_report_v3.md`
- `reports/110_segment_io_contract.json`
- `reports/120_final_segment_input_sweep.json`
- `reports/130_s100p_boundary_dump_subprocess.json`
- `reports/140_bf16_reference_status.json`
- `RAW_EVIDENCE_SUBSET_MANIFEST.json`

Scope: this run only investigates `seg26_27 -> seg27_28` final segment input contract/layout/dtype/scale/runtime interpretation. It does not run generation quality, does not enable product route, and does not touch `18888`.
""",
    )
    write_text(
        root / "GPT_PRO_REVIEW_PROMPT.md",
        """Please review this Dream7B/S100P v3 evidence package. Verify whether the v3 evidence supports the gate packet conclusion, especially the localization around `seg26_27 -> seg27_28` final segment input contract/runtime interpretation. Do not treat GGUF mismatch as BF16 failure unless `reports/140_bf16_reference_status.json` provides verified BF16 logits. Do not mark Gate 3/4 failed if they were not run. Check `RAW_EVIDENCE_SUBSET_MANIFEST.json` for included raw arrays and SHA256 values.
""",
    )


def build_raw_manifest(root: Path) -> list[dict[str, Any]]:
    raw_root = root / "raw_evidence_subset"
    rows = []
    if raw_root.is_dir():
        for p in sorted(raw_root.rglob("*")):
            if p.is_file():
                row = inventory_file(p, root)
                rel = row["relative_path"]
                parts = Path(rel).parts
                if "bpu_full_chain" in parts:
                    row.update({"source_report": "reports/020_s100p_dump_logits_run.json", "case_id": "zeros", "why_included": "required BPU full-chain raw/dequant final logits"})
                elif "gguf_reference" in parts:
                    row.update({"source_report": "reports/070_logits_probe_battery_triplet.json", "case_id": "zeros", "why_included": "required GGUF last-logits deployment reference sample"})
                elif "bpu_seg26_boundary" in parts:
                    row.update({"source_report": "reports/130_s100p_boundary_dump_subprocess.json", "case_id": "zeros", "segment": 26, "why_included": "required BPU seg26 raw/dequant boundary output"})
                elif "final_segment_input_sweep" in parts:
                    idx = parts.index("final_segment_input_sweep")
                    variant = parts[idx + 1] if len(parts) > idx + 1 else "unknown"
                    row.update({"source_report": "reports/120_final_segment_input_sweep.json", "variant_id": variant, "why_included": "required isolated seg27_28 input/output or representative input sweep variant"})
                # Sidecar metadata can override or add fields.
                sidecar = p.with_suffix(p.suffix + ".json")
                if sidecar.is_file():
                    try:
                        row.update(json.loads(sidecar.read_text(encoding="utf-8")))
                    except Exception:
                        pass
                rows.append(row)
    return rows


def package_manifest(root: Path, exclude: set[str]) -> list[dict[str, Any]]:
    rows = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel in exclude:
            continue
        if rel.endswith(".zip"):
            continue
        rows.append(inventory_file(p, root))
    return rows


def write_sha256s(root: Path, rows: list[dict[str, Any]]) -> None:
    lines = [f"{row['sha256']}  {row['relative_path']}" for row in rows]
    write_text(root / "SHA256SUMS.txt", "\n".join(lines) + "\n")


def zip_dir(root: Path, zip_path: Path) -> str:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if rel.endswith(".zip"):
                continue
            zf.write(p, rel)
    h = hashlib.sha256()
    with zip_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build normalized v3 GPT Pro evidence zip.")
    parser.add_argument("--run-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--zip-path", required=True)
    args = parser.parse_args()
    root = Path(args.run_root)
    make_readme(root)
    raw_rows = build_raw_manifest(root)
    write_json(root / "RAW_EVIDENCE_SUBSET_MANIFEST.json", {"created_at_utc": utc_now_iso(), "file_count": len(raw_rows), "files": raw_rows})
    manifest_rows = package_manifest(root, exclude={"MANIFEST.json", "SHA256SUMS.txt"})
    write_json(root / "MANIFEST.json", {"created_at_utc": utc_now_iso(), "file_count": len(manifest_rows), "files": manifest_rows})
    # Recompute after MANIFEST exists so SHA256SUMS includes it but not itself.
    manifest_rows = package_manifest(root, exclude={"SHA256SUMS.txt"})
    write_sha256s(root, manifest_rows)
    zip_hash = zip_dir(root, Path(args.zip_path))
    write_text(Path(args.zip_path).with_suffix(Path(args.zip_path).suffix + ".sha256"), f"{zip_hash}  {Path(args.zip_path).name}\n")
    print(args.zip_path)
    print(zip_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
