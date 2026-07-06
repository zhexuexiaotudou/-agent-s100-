from __future__ import annotations

import argparse
import json
import sys

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, run_cmd
from stage9_final_recording_readiness_gate import configure_production_env


NAME = "stage10_auto_organizer_real_image_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 10 Auto Organizer AI-index driven real-image flow.")
    add_stage10_args(parser)
    parser.add_argument("--demo-image", default="")
    args = parser.parse_args()
    configure_production_env()
    cmd = [
        sys.executable,
        "gates/stage9_auto_organizer_ai_driven_gate.py",
        "--report-root",
        str(args.report_root),
        "--timeout",
        str(args.timeout),
    ]
    if args.personal_root:
        cmd.extend(["--personal-root", str(args.personal_root), "--source-rel", "Uploads/stage10_real_image/IMG_0001.jpg"])
    if args.demo_image:
        cmd.extend(["--demo-image", args.demo_image])
    run = run_cmd(cmd, timeout=args.timeout + 180)
    result_path = args.report_root / "stage9_auto_organizer_ai_driven_gate.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    evidence = result.get("evidence") or {}
    checks = [
        check("stage9 auto organizer gate reused", result.get("ok") is True, result.get("verdict") or run.get("stderr")),
        check("neutral filename used", "IMG_0001" in str(evidence.get("source_rel") or ""), evidence.get("source_rel")),
        check("fixture status recorded", "fixture_only_for_ci" in evidence, evidence.get("fixture_only_for_ci")),
        check("delete disabled", (evidence.get("executed") or {}).get("delete_allowed") is False, evidence.get("executed")),
        check("overwrite disabled", (evidence.get("executed") or {}).get("overwrite_allowed") is False, evidence.get("executed")),
        check("fallback blocked", (evidence.get("fallback_plan") or {}).get("blocker") == "ai_index_missing_for_asset", evidence.get("fallback_plan")),
    ]
    payload = gate_payload("ok_stage10_auto_organizer_real_image_gate", "blocked_stage10_auto_organizer_real_image_gate", checks, {"stage9_gate": result, "run": run})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
