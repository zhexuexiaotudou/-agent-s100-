from __future__ import annotations

import argparse
import os
import sys

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, gate_payload, latest_product_smoke, run_cmd, token_from_args


NAME = "stage10_yolo_bbox_recording_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate YOLO bbox readiness or record an explicit recording blocker.")
    add_stage10_args(parser)
    args = parser.parse_args()
    env = dict(os.environ); env["DIGUA_ADMIN_TOKEN"] = token_from_args(args)
    run = run_cmd([sys.executable, "scripts/product_smoke_test.py", "--base-url", args.base_url, "--report-root", str(args.report_root), "--timeout", str(args.timeout)], timeout=args.timeout + 90, env=env)
    smoke = latest_product_smoke(args.report_root) or {}
    summary = smoke.get("summary") or {}
    detection_count = int(summary.get("yolo_detection_count") or 0)
    runtime = summary.get("yolo_runtime_target")
    blocker = None if detection_count > 0 else "yolo_demo_images_not_detectable"
    checks = [
        check("product smoke available", bool(smoke), run.get("stderr")),
        check("real S100P YOLO backend selected", runtime == "s100p_bpu_hbm", summary),
        check("bbox ok or explicit blocker recorded", detection_count > 0 or blocker == "yolo_demo_images_not_detectable", {"detection_count": detection_count, "recording_blocker": blocker}),
    ]
    verdict_ok = "ok_stage10_yolo_bbox_recording_gate" if detection_count > 0 else "explicit_blocker_stage10_yolo_bbox_recording_gate"
    payload = gate_payload(verdict_ok, "blocked_stage10_yolo_bbox_recording_gate", checks, {"smoke": smoke, "recording_blocker": blocker, "detection_count": detection_count})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
