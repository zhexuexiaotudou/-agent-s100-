#!/usr/bin/env python3
"""Create the compact Dream7B/S100P v5 GPT Pro evidence package."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path, includes: list[str]) -> list[Path]:
    files: list[Path] = []
    for rel in includes:
        p = root / rel
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(x for x in p.rglob("*") if x.is_file())
    return sorted(set(files))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out-zip", required=True)
    ap.add_argument(
        "--include",
        nargs="*",
        default=[
            "reports",
            "01_final_evidence",
            "cases",
            "tools",
            "evidence/s100p_remote_v5",
            "deliverables/dream7b_s100p_v3_execution_20260701/raw_evidence_subset",
            "deliverables/dream7b_s100p_v3_execution_20260701/RAW_EVIDENCE_SUBSET_MANIFEST.json",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/CODEX_EXECUTE_THIS.md",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/CURRENT_STATE_UNIFIED.md",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/GATE_DEFINITIONS_V5.md",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/EXECUTION_ORDER.md",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/SAFETY_BOUNDS.md",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/MANIFEST.json",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/SHA256SUMS.txt",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/reference/extracted_mainline_v3",
            "tmp/dream7b_s100p_unified_v5_execution_pack_20260701/reference/extracted_llada_llamacpp_v4",
        ],
    )
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    out_zip = Path(args.out_zip).resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    files = iter_files(root, args.include)
    manifest_files = []
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arc = path.relative_to(root).as_posix()
            zf.write(path, arc)
            manifest_files.append(
                {
                    "path": arc,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        manifest = {
            "schema_version": "dream7b_s100p_v5_gptpro_evidence_zip_manifest",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "zip_path": out_zip.name,
            "file_count": len(manifest_files),
            "files": manifest_files,
            "exclusions": [
                "huge HBM tar/files excluded",
                "product route logs and credentials excluded",
                "generation quality outputs absent by design",
            ],
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        sums = "".join(f"{item['sha256']}  {item['path']}\n" for item in manifest_files)
        zf.writestr("SHA256SUMS.txt", sums.encode("utf-8"))

    with zipfile.ZipFile(out_zip) as zf:
        bad = zf.testzip()
        if bad:
            raise SystemExit(f"bad zip member: {bad}")

    sidecar_manifest = out_zip.with_name(out_zip.stem + "_MANIFEST.json")
    sidecar_sums = out_zip.with_name(out_zip.stem + "_SHA256SUMS.txt")
    write_json(sidecar_manifest, manifest)
    sidecar_sums.write_text("".join(f"{item['sha256']}  {item['path']}\n" for item in manifest_files), encoding="utf-8")
    print(out_zip)
    print(sidecar_manifest)
    print(sidecar_sums)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
