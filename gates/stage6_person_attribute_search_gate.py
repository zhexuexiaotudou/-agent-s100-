from __future__ import annotations

import argparse

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate
from src.openclaw.routes.person_attribute_routes import person_attribute_route_response


NAME = "stage6_person_attribute_search_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate local non-identifying person attribute search.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.no_rebuild:
        person_attribute_route_response("/api/person-attribute/rebuild", method="POST", payload={}, report_root=args.report_root, personal_root=args.personal_root)
    _code, status = person_attribute_route_response("/api/person-attribute/status", method="GET", report_root=args.report_root, personal_root=args.personal_root)
    searches = {}
    for query in ["person", "white shirt", "people in video", "who is this", "\u8bc6\u522b\u7167\u7247\u91cc\u7684\u7238\u7238"]:
        _code, result = person_attribute_route_response(
            "/api/person-attribute/search",
            method="POST",
            payload={"query": query, "top_k": 10},
            report_root=args.report_root,
            personal_root=args.personal_root,
        )
        searches[query] = result
    video_required = int(status.get("video_keyframe_count") or 0) > 0
    checks = [
        check("person_detection_count > 0", int(status.get("person_detection_count") or 0) > 0, status.get("person_detection_count")),
        check("attribute_count > 0", int(status.get("attribute_count") or 0) > 0, status.get("attribute_count")),
        check("cloud_used == false", status.get("cloud_used") is False, status.get("cloud_used")),
        check("raw_path_returned == false", status.get("raw_path_returned") is False, status.get("raw_path_returned")),
        check("face_identification_enabled == false", status.get("face_identification_enabled") is False, status.get("face_identification_enabled")),
        check("biometric_recognition_enabled == false", status.get("biometric_recognition_enabled") is False, status.get("biometric_recognition_enabled")),
        check("sensitive_attribute_inference_enabled == false", status.get("sensitive_attribute_inference_enabled") is False, status.get("sensitive_attribute_inference_enabled")),
        check("person query has result", bool(searches["person"].get("results")), len(searches["person"].get("results") or [])),
        check("white shirt query has result", bool(searches["white shirt"].get("results")), len(searches["white shirt"].get("results") or [])),
        check("video person query has result or no fixture", (not video_required) or bool(searches["people in video"].get("results")), len(searches["people in video"].get("results") or [])),
        check("identity query blocked", searches["who is this"].get("blocked") is True, searches["who is this"].get("blocked_reason")),
        check("family identity query blocked", searches["\u8bc6\u522b\u7167\u7247\u91cc\u7684\u7238\u7238"].get("blocked") is True, searches["\u8bc6\u522b\u7167\u7247\u91cc\u7684\u7238\u7238"].get("blocked_reason")),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage6_person_attribute_search_gate", "blocked_stage6_person_attribute_search_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "status": status,
        "searches": searches,
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
