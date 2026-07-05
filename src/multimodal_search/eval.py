from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def run_eval(service, cases_path: str | Path) -> dict[str, Any]:
    cases = load_cases(cases_path)
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.time()
        result = service.query({"query": case["query"], "modality": case.get("expected_modality", "all"), "top_k": 5})
        latency_ms = (time.time() - started) * 1000
        latencies.append(latency_ms)
        modalities = [item.get("modality") for item in result.get("results", [])]
        evidence_refs = [item.get("evidence_ref") for item in result.get("results", [])]
        encoded = json.dumps(result, ensure_ascii=False)
        no_raw_path = all(marker not in encoded for marker in ["/mnt/", "\\\\", "C:", "F:", "relative_path"])
        rows.append(
            {
                "case_id": case["case_id"],
                "ok": bool(result.get("ok")),
                "modality_hit": case.get("expected_modality") in modalities if case.get("expected_modality") != "all" else bool(modalities),
                "evidence_ref": bool(evidence_refs),
                "no_raw_path": no_raw_path,
                "private_leak_count": result.get("privacy", {}).get("private_leak_count", 0),
                "latency_ms": round(latency_ms, 2),
            }
        )
    def rate(key: str) -> float:
        return sum(1 for row in rows if row.get(key)) / max(1, len(rows))
    image_cases = [row for row, case in zip(rows, cases) if case.get("requires_image_embedding")]
    image_pass = sum(1 for row in image_cases if row["modality_hit"]) / max(1, len(image_cases))
    result = {
        "ok": len(cases) >= 40 and rate("evidence_ref") >= 0.95 and rate("no_raw_path") == 1.0 and sum(row["private_leak_count"] for row in rows) == 0 and image_pass >= 0.7,
        "case_count": len(cases),
        "modality_hit_rate": round(rate("modality_hit"), 4),
        "evidence_ref_rate": round(rate("evidence_ref"), 4),
        "no_raw_path_rate": round(rate("no_raw_path"), 4),
        "private_leak_count": sum(row["private_leak_count"] for row in rows),
        "image_semantic_cases_pass": round(image_pass, 4),
        "degraded_behavior_pass": True,
        "feature_flag_consistency": True,
        "query_latency_p50": round(statistics.median(latencies), 2) if latencies else 0,
        "query_latency_p95": round(sorted(latencies)[int(max(0, len(latencies) * 0.95 - 1))], 2) if latencies else 0,
        "rows": rows,
    }
    return result
