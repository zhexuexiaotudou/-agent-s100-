from __future__ import annotations

import argparse
import os
import sys

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, latest_product_smoke, run_cmd, token_from_args
from stage9_final_recording_readiness_gate import configure_production_env, prepare_recording_indices


NAME = "stage10_release_product_smoke_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run product smoke as the release post-install acceptance gate.")
    add_stage10_args(parser)
    args = parser.parse_args()
    configure_production_env()
    prepare = prepare_recording_indices(args.report_root, args.personal_root) if args.personal_root else {"ok": False, "error": "personal_root_missing"}
    env = dict(os.environ); env["DIGUA_ADMIN_TOKEN"] = token_from_args(args)
    run = run_cmd([sys.executable, "scripts/product_smoke_test.py", "--base-url", args.base_url, "--report-root", str(args.report_root), "--timeout", str(args.timeout)], timeout=args.timeout + 90, env=env)
    smoke = latest_product_smoke(args.report_root) or {}
    summary = smoke.get("summary") or {}
    checks = [
        check("product smoke report exists", bool(smoke), run.get("stderr")),
        check("recording indexes prepared", prepare.get("ok") is True, prepare),
        check("product smoke ok", smoke.get("ok") is True, smoke.get("verdict")),
        check("production ready true", summary.get("production_ready") is True, summary),
        check("failure count zero", int(summary.get("failure_count") or 0) == 0, summary),
        check("security warnings only", int(summary.get("warning_count") or 0) >= 0, summary),
    ]
    payload = gate_payload("ok_stage10_release_product_smoke_gate", "blocked_stage10_release_product_smoke_gate", checks, {"smoke": smoke, "run": run, "prepare_recording_indices": prepare})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
