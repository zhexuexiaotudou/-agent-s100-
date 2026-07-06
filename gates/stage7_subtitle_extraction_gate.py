from __future__ import annotations

import argparse

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate
from src.openclaw.routes.subtitle_extraction_routes import subtitle_extraction_route_response


NAME = "stage7_subtitle_extraction_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate local subtitle extraction.")
    add_common_args(parser)
    parser.add_argument("--ci-fixture-ok", action="store_true")
    args = parser.parse_args()
    _code, status = subtitle_extraction_route_response("/api/subtitle/status", method="GET", report_root=args.report_root, personal_root=args.personal_root)
    backend = status.get("backend") or {}
    checks = [
        check("local ASR backend available", backend.get("available") is True, backend),
        check("real ASR backend for product", backend.get("real_asr") is True or args.ci_fixture_ok, backend),
        check("transcript_count >= 1", int(status.get("transcript_count") or 0) >= 1, status.get("transcript_count")),
        check("segment_count > 0", int(status.get("segment_count") or 0) > 0, status.get("segment_count")),
        check("cloud_used == false", status.get("cloud_used") is False, status.get("cloud_used")),
        check("raw_path_returned == false", status.get("raw_path_returned") is False, status.get("raw_path_returned")),
        check("fixture not accepted for product", (not status.get("fixture_only_for_ci")) or args.ci_fixture_ok, status.get("fixture_only_for_ci")),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_subtitle_extraction_gate", "blocked_stage7_subtitle_extraction_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "status": status,
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
