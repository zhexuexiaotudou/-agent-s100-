#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from dream7b_research_common import iter_jsonl, now_iso, read_logits_bin, run_cmd, sha256_file, tensor_stats, topk, write_json, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Export GGUF Q4_K_M last-token logits for seq128 token-id cases.")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--gguf-model", default="/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf")
    parser.add_argument("--dump-logits", default="/mnt/nas/openclaw/runtimes/diffuse-cpp/build/dump-logits")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    out_root = Path(args.output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    errors = []
    model_hash = sha256_file(Path(args.gguf_model)) if Path(args.gguf_model).is_file() else None
    for case in iter_jsonl(Path(args.cases)):
        case_id = case["case_id"]
        case_dir = out_root / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        logits_bin = case_dir / "gguf_logits.bin"
        cmd = [
            args.dump_logits,
            "-m",
            args.gguf_model,
            "--tokens",
            ",".join(str(item) for item in case["token_ids"]),
            "-o",
            str(logits_bin),
            "-t",
            str(args.threads),
        ]
        result = run_cmd(cmd, timeout=args.timeout)
        if result["returncode"] != 0:
            errors.append(f"gguf_export_failed:{case_id}")
            rows.append({"case_id": case_id, "ok": False, "command": result})
            continue
        logits = read_logits_bin(logits_bin)
        last = logits[-1].astype(np.float32, copy=False)
        out_npy = case_dir / "gguf_last_logits.npy"
        np.save(out_npy, last)
        meta = {
            "case_id": case_id,
            "ok": True,
            "reference_type": "gguf_q4km_dump_logits",
            "model_path": args.gguf_model,
            "model_sha256": model_hash,
            "dump_logits": args.dump_logits,
            "seq_len": int(logits.shape[0]),
            "vocab_size": int(logits.shape[1]),
            "last_token_index": int(logits.shape[0] - 1),
            "logits_bin": str(logits_bin),
            "last_logits_npy": str(out_npy),
            "stats": tensor_stats(last),
            "top5": topk(last, 5),
            "command": result,
        }
        write_json(case_dir / "gguf_metadata.json", meta)
        rows.append(meta)
    payload = {
        "created_at": now_iso(),
        "reference_type": "gguf_q4km_dump_logits",
        "cases": rows,
        "errors": errors,
        "verdict": "ok_gguf_reference_export" if not errors else "failed_gguf_reference_export",
    }
    write_json(out_root / "gguf_reference_export.json", payload)
    write_text(out_root / "gguf_reference_export.md", "# GGUF Reference Export\n\n" + "\n".join(f"- {r['case_id']}: `{r.get('ok')}`" for r in rows) + "\n")
    print(out_root / "gguf_reference_export.json")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

