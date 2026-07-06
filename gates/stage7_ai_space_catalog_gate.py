from __future__ import annotations

import argparse

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate
from src.openclaw.routes.ai_space_routes import ai_space_route_response


NAME = "stage7_ai_space_catalog_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate AI Space catalog.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.no_rebuild:
        ai_space_route_response("/api/ai-space/rebuild", method="POST", payload={}, report_root=args.report_root, personal_root=args.personal_root)
    _code, status = ai_space_route_response("/api/ai-space/status", method="GET", report_root=args.report_root, personal_root=args.personal_root)
    _code, facets = ai_space_route_response("/api/ai-space/facets", method="GET", report_root=args.report_root, personal_root=args.personal_root)
    searches = {}
    for query in ["white clothes", "invoice", "video", "contract"]:
        _code, result = ai_space_route_response("/api/ai-space/search", method="POST", payload={"query": query, "top_k": 10}, report_root=args.report_root, personal_root=args.personal_root)
        searches[query] = result
    facet_payload = facets.get("facets") or {}
    checks = [
        check("AI Space rebuild/status ok", status.get("ok") is True, status.get("degraded_reason")),
        check("assets >= 10", int(status.get("asset_count") or 0) >= 10, status.get("asset_count")),
        check("facet modality exists", bool(facet_payload.get("modality")), facet_payload.get("modality")),
        check("facet time_bucket exists", bool(facet_payload.get("time_bucket")), facet_payload.get("time_bucket")),
        check("facet object_label exists", bool(facet_payload.get("object_label")), facet_payload.get("object_label")),
        check("white clothes query works", bool(searches["white clothes"].get("results")), len(searches["white clothes"].get("results") or [])),
        check("invoice query works", bool(searches["invoice"].get("results")), len(searches["invoice"].get("results") or [])),
        check("video query works", bool(searches["video"].get("results")), len(searches["video"].get("results") or [])),
        check("contract query works", bool(searches["contract"].get("results")), len(searches["contract"].get("results") or [])),
        check("raw_path_returned == false", status.get("raw_path_returned") is False, status.get("raw_path_returned")),
        check("cloud_used == false", status.get("cloud_used") is False, status.get("cloud_used")),
        check("evidence_refs exist", int(status.get("evidence_count") or 0) > 0, status.get("evidence_count")),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage7_ai_space_catalog_gate", "blocked_stage7_ai_space_catalog_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "status": status,
        "facets": facets,
        "searches": searches,
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
