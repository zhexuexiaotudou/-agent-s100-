from __future__ import annotations

import argparse

from ai_space_gate_common import add_common_args, blockers, check, verdict, write_gate
from src.openclaw.routes.multimodal_search_routes import multimodal_route_response


NAME = "stage6_multimodal_live_clip_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate live local CLIP embeddings for multimodal search.")
    add_common_args(parser)
    args = parser.parse_args()
    if not args.no_rebuild:
        multimodal_route_response(
            "/api/multimodal-index/rebuild",
            method="POST",
            payload={},
            report_root=args.report_root,
            personal_root=args.personal_root,
        )
    _code, status = multimodal_route_response("/api/multimodal-search/status", method="GET", report_root=args.report_root, personal_root=args.personal_root)
    queries = {}
    for query in ["white clothes", "person", "laptop or book"]:
        _code, result = multimodal_route_response(
            "/api/multimodal-search/query",
            method="POST",
            payload={"query": query, "top_k": 5},
            report_root=args.report_root,
            personal_root=args.personal_root,
        )
        queries[query] = result
    model = status.get("image_embedding_model") or {}
    checks = [
        check("indexed_assets >= 5", int(status.get("indexed_count") or 0) >= 5, status.get("indexed_count")),
        check("image_asset_count >= 5", int(status.get("image_asset_count") or 0) >= 5, status.get("image_asset_count")),
        check("embedding_count >= 5", int(status.get("embedding_count") or 0) >= 5, status.get("embedding_count")),
        check("production_semantic_embedding_count >= 5", int(status.get("production_semantic_embedding_count") or 0) >= 5, status.get("production_semantic_embedding_count")),
        check("model_family production", model.get("model_family") in {"clip", "siglip", "chinese_clip", "open_clip"}, model),
        check("vector_dim >= 128", int(model.get("vector_dim") or 0) >= 128, model.get("vector_dim")),
        check("cloud_used == false", status.get("cloud_used") is False, status.get("cloud_used")),
        check("raw_path_rows == 0", int(status.get("raw_path_rows") or 0) == 0, status.get("raw_path_rows")),
        check("private_leak_count == 0", int(status.get("private_leak_count") or 0) == 0, status.get("private_leak_count")),
        check("query white clothes has result", bool(queries["white clothes"].get("results")), len(queries["white clothes"].get("results") or [])),
        check("query person has result", bool(queries["person"].get("results")), len(queries["person"].get("results") or [])),
        check("query laptop or book has result", bool(queries["laptop or book"].get("results")), len(queries["laptop or book"].get("results") or [])),
        check("results have evidence_ref", all((r.get("evidence_ref") for q in queries.values() for r in (q.get("results") or []))), "all query rows"),
        check("raw path not returned", all("path" not in r and "raw_path" not in r for q in queries.values() for r in (q.get("results") or [])), "query rows"),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks),
        "verdict": verdict("ok_stage6_multimodal_live_clip_gate", "blocked_stage6_multimodal_live_clip_gate", checks),
        "checks": checks,
        "blockers": blockers(checks),
        "status": status,
        "queries": queries,
    }
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
