#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ai_nas_common import DEFAULT_SQLITE_INDEX_PATH, ensure_report_dir, iso_now, safe_write_json, safe_write_text
from ai_nas_vision_search import search_product_visual_index


TOOL_ID = "ai_nas_s100_clip_realdata_gate"
OK = "ok_ai_nas_s100_clip_realdata_gate"
FAILED = "failed_ai_nas_s100_clip_realdata_gate"


def gateway_health(embed_endpoint: str) -> dict:
    parsed = urlparse(embed_endpoint)
    health = f"{parsed.scheme}://{parsed.netloc}/health"
    try:
        with urllib.request.urlopen(health, timeout=10) as response:
            raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw.strip() else {}
        payload["http_status"] = response.status
        payload["health_url"] = health
        return payload
    except Exception as exc:
        return {"ok": False, "health_url": health, "error": f"{type(exc).__name__}:{exc}"}


def product_embedding_counts(db_path: Path, model_id: str) -> dict:
    from ai_nas_common import open_index_db

    con = open_index_db(db_path)
    try:
        rows = con.execute(
            """
            SELECT status, dim, COUNT(*) AS count
            FROM vision_embeddings_v2
            WHERE model_id = ?
            GROUP BY status, dim
            ORDER BY status, dim
            """,
            (model_id,),
        ).fetchall()
        recent = [
            {
                "relative_path": row["relative_path"],
                "scope": row["scope"],
                "dim": row["dim"],
                "status": row["status"],
                "runtime": row["runtime"],
                "created_at": row["created_at"],
            }
            for row in con.execute(
                """
                SELECT relative_path, scope, dim, status, runtime, created_at
                FROM vision_embeddings_v2
                WHERE model_id = ?
                ORDER BY id DESC
                LIMIT 20
                """,
                (model_id,),
            )
        ]
    finally:
        con.close()
    return {
        "counts": [{"status": row["status"], "dim": int(row["dim"]), "count": int(row["count"])} for row in rows],
        "recent": recent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate real-data S100P CLIP image/text retrieval in product visual search.")
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--endpoint", default=os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT", "http://192.168.127.10:18182/embed"))
    parser.add_argument("--model-id", default=os.environ.get("AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL", "s100p-clip-vit-base-patch32"))
    parser.add_argument("--query", default="football player")
    parser.add_argument("--expected-top-contains", default="football")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_s100_clip_realdata_gate_local"))
    args = parser.parse_args()

    os.environ["AI_NAS_IMAGE_TEXT_EMBEDDING_ENDPOINT"] = args.endpoint
    os.environ["AI_NAS_IMAGE_TEXT_EMBEDDING_MODEL"] = args.model_id

    run_dir = ensure_report_dir(args.report_root, "s100_clip_realdata_gate")
    health = gateway_health(args.endpoint)
    counts = product_embedding_counts(args.sqlite_index_path, args.model_id)
    search = search_product_visual_index(args.sqlite_index_path, args.query, limit=8)
    matches = search.get("matches") or []
    top = matches[0] if matches else {}
    top_evidence = top.get("evidence_items") or []

    total_completed = sum(
        item["count"]
        for item in counts.get("counts") or []
        if item.get("status") == "product_image_text_embedding_completed" and int(item.get("dim") or 0) > 0
    )
    failures: list[str] = []
    if not health.get("ok") or not health.get("ready"):
        failures.append(f"gateway_not_ready:{health}")
    if total_completed < 3:
        failures.append(f"insufficient_product_embeddings:{total_completed}")
    if search.get("degraded"):
        failures.append(f"search_degraded:{search.get('degradation')}")
    if not matches:
        failures.append("no_search_matches")
    if args.expected_top_contains.lower() not in str(top.get("relative_path") or "").lower():
        failures.append(f"top_result_not_expected:{top.get('relative_path')}")
    if top.get("source") != "product_image_text_embedding_search":
        failures.append(f"top_result_not_product_embedding:{top.get('source')}")
    if top.get("confidence_kind") != "product_score":
        failures.append(f"top_confidence_not_product_score:{top.get('confidence_kind')}")
    if not any(item.get("type") == "image_text_embedding" and item.get("model_id") == args.model_id for item in top_evidence):
        failures.append("top_missing_s100_clip_evidence")

    verdict = OK if not failures else FAILED
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "sqlite_index_path": str(args.sqlite_index_path),
        "endpoint": args.endpoint,
        "model_id": args.model_id,
        "gateway_health": health,
        "product_embedding_counts": counts,
        "query": args.query,
        "search": search,
        "top_relative_path": top.get("relative_path"),
        "top_source": top.get("source"),
        "top_confidence_kind": top.get("confidence_kind"),
        "failures": failures,
        "acceptance": {
            "real_s100_clip_gateway_ready": True,
            "real_nas_photos_have_product_clip_vectors": True,
            "semantic_visual_query_uses_product_embedding": True,
            "result_has_s100_clip_evidence": True,
        },
    }
    json_path = run_dir / "s100_clip_realdata_gate.json"
    md_path = run_dir / "s100_clip_realdata_gate.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS S100 CLIP Real Data Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- endpoint: `{args.endpoint}`",
        f"- completed_embeddings: `{total_completed}`",
        f"- top_relative_path: `{top.get('relative_path')}`",
        f"- top_source: `{top.get('source')}`",
        f"- failures: `{failures}`",
    ]
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(f"verdict: {verdict}")
    print(f"report: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
