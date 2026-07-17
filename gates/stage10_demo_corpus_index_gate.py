from __future__ import annotations

import argparse
import os
import sys

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, latest_product_smoke, run_cmd, token_from_args
from stage9_final_recording_readiness_gate import configure_production_env, prepare_recording_indices


NAME = "stage10_demo_corpus_index_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live product indexes for the demo corpus path.")
    add_stage10_args(parser)
    args = parser.parse_args()
    configure_production_env()
    prepare = prepare_recording_indices(args.report_root, args.personal_root) if args.personal_root else {"ok": False, "error": "personal_root_missing"}
    smoke_cmd = [sys.executable, "scripts/product_smoke_test.py", "--base-url", args.base_url, "--report-root", str(args.report_root), "--timeout", str(args.timeout)]
    env = dict(os.environ); env["DIGUA_ADMIN_TOKEN"] = token_from_args(args)
    smoke_run = run_cmd(smoke_cmd, timeout=args.timeout + 90, env=env)
    smoke = latest_product_smoke(args.report_root) or {}
    summary = smoke.get("summary") or {}
    checks = [
        check("product smoke ran", bool(smoke), smoke_run.get("stderr") or smoke_run.get("stdout")),
        check("recording indexes prepared", prepare.get("ok") is True, prepare),
        check("product smoke ok", smoke.get("ok") is True, smoke.get("verdict")),
        check("AI Space assets indexed", int(summary.get("ai_space_asset_count") or 0) >= 10, summary),
        check("multimodal embeddings indexed", int(summary.get("multimodal_embedding_count") or 0) >= 5, summary),
        check("document RAG chunks indexed", int(summary.get("document_rag_chunk_count") or 0) >= 1, summary),
        check("smart categories indexed", int(summary.get("smart_category_count") or 0) >= 5, summary),
        check("YOLO backend indexed path live", summary.get("yolo_runtime_target") == "s100p_bpu_hbm", summary),
        check("no product smoke failures", int(summary.get("failure_count") or 0) == 0, summary),
    ]
    payload = gate_payload("ok_stage10_demo_corpus_index_gate", "blocked_stage10_demo_corpus_index_gate", checks, {"smoke": smoke, "smoke_run": smoke_run, "prepare_recording_indices": prepare})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
