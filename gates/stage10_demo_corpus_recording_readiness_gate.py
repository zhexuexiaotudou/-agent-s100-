from __future__ import annotations

import argparse
import json
import sys

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, bundle_stage10, gate_payload, run_cmd


NAME = "stage10_demo_corpus_recording_readiness_gate"
SUB_GATES = [
    "stage10_open_visual_corpus_license_gate.py",
    "stage10_open_visual_corpus_download_gate.py",
    "stage10_demo_corpus_index_gate.py",
    "stage10_gold_query_multimodal_gate.py",
    "stage10_auto_organizer_real_image_gate.py",
    "stage10_yolo_bbox_recording_gate.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate Stage 10 demo corpus recording readiness gates.")
    add_stage10_args(parser)
    parser.add_argument("--demo-image", default="")
    args = parser.parse_args()
    build = run_cmd([sys.executable, "demo_corpus/scripts/build_demo_corpus.py", "--report-root", str(args.report_root), "--fixture-ci", "--no-downloads"], timeout=180)
    results = {}
    for gate in SUB_GATES:
        cmd = [sys.executable, str((__import__("pathlib").Path(__file__).resolve().parent / gate)), "--report-root", str(args.report_root), "--corpus-root", str(args.corpus_root), "--base-url", args.base_url, "--timeout", str(args.timeout)]
        if args.personal_root:
            cmd.extend(["--personal-root", str(args.personal_root)])
        if args.auth_token:
            cmd.extend(["--auth-token", args.auth_token])
        if gate == "stage10_auto_organizer_real_image_gate.py" and args.demo_image:
            cmd.extend(["--demo-image", args.demo_image])
        run = run_cmd(cmd, timeout=args.timeout + 240)
        path = args.report_root / gate.replace(".py", ".json")
        results[gate] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"ok": False, "verdict": "missing_report", "run": run}
    checks = [check("demo corpus build ran", build.get("ok") is True, build.get("stderr"))]
    checks.extend(check(gate, result.get("ok") is True, result.get("verdict")) for gate, result in results.items())
    bundle, digest = bundle_stage10(args.report_root)
    payload = gate_payload("ok_stage10_demo_corpus_recording_readiness_gate", "blocked_stage10_demo_corpus_recording_readiness_gate", checks, {"sub_gates": results, "build": build, "gptpro_bundle": str(bundle) if bundle else None, "gptpro_bundle_sha256": digest})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    if bundle:
        print(bundle)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

