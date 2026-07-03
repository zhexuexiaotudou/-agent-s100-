#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    root = Path("/mnt/nas/openclaw/models/dream7b-hf")
    hbm = Path(
        "/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken/seg27_28/"
        "dream7b_segment_27_28_seq128_q8_lmheadq16_last_token_logits.hbm"
    )
    out = Path("/mnt/nas/openclaw/reports/models/dream7b_s100p_v10_execution_20260701/reports")
    out.mkdir(parents=True, exist_ok=True)
    wanted = {
        "config.json",
        "model.safetensors.index.json",
        "SHA256SUMS",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
        "tokenization_dream.py",
    }
    files = []
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name in wanted:
            files.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    report = {
        "schema_version": "dream7b_s100p_v10_remote_model_hbm_inventory",
        "created_at_unix": time.time(),
        "hf_model_dir": str(root),
        "hf_files": files,
        "hbm": {
            "path": str(hbm),
            "exists": hbm.exists(),
            "size_bytes": hbm.stat().st_size if hbm.exists() else None,
            "sha256": sha256_file(hbm) if hbm.exists() else None,
        },
    }
    (out / "model_hbm_inventory_v10.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"hf_files": len(files), "hbm_sha": report["hbm"]["sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
