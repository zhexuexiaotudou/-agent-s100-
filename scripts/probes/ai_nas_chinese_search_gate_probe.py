#!/usr/bin/env python3
"""Gate probe: Chinese natural language file search (Feature A2).

Uses the text embedding provider + vector store to validate semantic search
against the ground-truth manifest.

Tests S01 scenarios from ground_truth_manifest.json.
"""

from __future__ import annotations

import json, sys, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from ai_nas_text_embedding_provider import embed_text, embed_batch, semantic_search, embedding_provider_status
from ai_nas_vector_store import VectorStore

DEFAULT_REPORT_ROOT = Path("F:/mnt/nas/openclaw/reports/ai_nas_mvp")
MANIFEST_PATH = DEFAULT_REPORT_ROOT / "ground_truth_manifest.json"


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_file_inventory():
    inv_path = DEFAULT_REPORT_ROOT / "personal_file_inventory.json"
    if inv_path.exists():
        with open(inv_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def run_gate():
    manifest = load_manifest()
    inventory = load_file_inventory()

    embedding_status = embedding_provider_status()

    # Index all file paths + names as documents
    docs = []
    doc_map = {}
    for item in inventory:
        doc_text = f"{item['path']} {Path(item['path']).stem}"
        docs.append(doc_text)
        doc_map[len(docs) - 1] = item["path"]

    embed_result = embed_batch(docs, dim=embedding_status["dim"])
    vectors = embed_result.get("vectors", [])

    # Build vector store
    store_path = DEFAULT_REPORT_ROOT / "chinese_search_vector_store.sqlite3"
    store = VectorStore(store_path)
    for i, (doc, vec) in enumerate(zip(docs, vectors)):
        store.index_document(f"file_{i}", doc, vec, {"path": doc_map.get(i, "")})

    # Run search scenarios
    scenarios = manifest.get("scenarios", [])
    s01 = next((s for s in scenarios if s["id"] == "S01_document_search"), None)

    results = []
    if s01:
        for q in s01.get("queries", []):
            query = q["query"]
            expect_cat = q.get("expect_category", "")
            expect_paths = q.get("expect_paths", [])

            sr = store.semantic_search(query, top_k=5)
            top_results = sr.get("results", [])

            # Check if any result matches expected paths
            matched = any(
                any(ep in r.get("text", "") or ep in r.get("metadata", {}).get("path", "")
                    for ep in expect_paths)
                for r in top_results
            )

            results.append({
                "query": query,
                "expect_category": expect_cat,
                "expect_paths": expect_paths,
                "matched": matched,
                "top_results": [
                    {"score": r["score"], "snippet": r["text"][:80]}
                    for r in top_results[:3]
                ],
                "evidence": sr.get("evidence", {}),
            })

    store.close()

    passed = sum(1 for r in results if r["matched"])
    total = len(results)

    gate = {
        "gate_id": "ok_ai_nas_chinese_search_gate",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "feature": "A2_chinese_nl_file_search",
        "verdict": "passed" if total > 0 and passed >= total * 0.6 else "failed",
        "embedding_backend": embedding_status["backend"],
        "embedding_dim": embedding_status["dim"],
        "queries_total": total,
        "queries_passed": passed,
        "pass_rate": round(passed / total, 2) if total > 0 else 0,
        "results": results,
        "evidence": {
            "manifest": str(MANIFEST_PATH),
            "inventory_size": len(inventory),
            "vector_store_docs": store.count if hasattr(store, 'count') else len(docs),
        },
    }

    output_path = DEFAULT_REPORT_ROOT / "chinese_search_gate_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(gate, f, ensure_ascii=False, indent=2)

    print(f"Gate {gate['verdict']}: {passed}/{total} queries passed")
    print(f"Report: {output_path}")
    return gate


if __name__ == "__main__":
    gate = run_gate()
    print(json.dumps(gate, ensure_ascii=False, indent=2))
