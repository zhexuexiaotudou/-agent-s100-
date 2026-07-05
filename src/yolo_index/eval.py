from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_cases(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def run_eval(service: Any, cases_path: str | Path) -> dict[str, Any]:
    cases = read_cases(cases_path)
    case_results: list[dict[str, Any]] = []
    private_leak_count = 0
    pass_count = 0
    strict_count = 0
    strict_pass_count = 0
    video_count = 0
    video_pass_count = 0
    for idx, case in enumerate(cases, start=1):
        query = str(case.get("query") or "")
        expected = [str(label) for label in case.get("expected_labels") or []]
        min_results = int(case.get("expect_min_results", 1 if expected else 0))
        allow_degraded = bool(case.get("allow_degraded"))
        modality = case.get("modality")
        result = service.search({"query": query, "top_k": int(case.get("top_k") or 8), "modality": modality})
        encoded = json.dumps(result, ensure_ascii=False)
        if "F:\\" in encoded or "/mnt/" in encoded or "\\Users\\" in encoded:
            private_leak_count += 1
        result_labels = sorted(
            {
                str(det.get("label"))
                for row in result.get("results") or []
                for det in row.get("detections") or []
                if det.get("label")
            }
        )
        has_min = len(result.get("results") or []) >= min_results
        has_labels = all(label in result_labels for label in expected)
        passed = bool(result.get("ok")) and private_leak_count == 0 and (allow_degraded or (has_min and has_labels))
        if allow_degraded and bool(result.get("ok")) and private_leak_count == 0:
            passed = True
        pass_count += 1 if passed else 0
        if not allow_degraded:
            strict_count += 1
            strict_pass_count += 1 if passed else 0
        if modality == "video":
            video_count += 1
            video_pass_count += 1 if passed else 0
        case_results.append(
            {
                "case_id": case.get("case_id") or f"case_{idx:03d}",
                "query": query,
                "expected_labels": expected,
                "result_labels": result_labels,
                "result_count": len(result.get("results") or []),
                "allow_degraded": allow_degraded,
                "passed": passed,
            }
        )
    denominator = len(cases) or 1
    strict_denominator = strict_count or 1
    return {
        "ok": bool(cases) and private_leak_count == 0 and strict_pass_count == strict_count,
        "case_count": len(cases),
        "pass_count": pass_count,
        "pass_rate": round(pass_count / denominator, 4),
        "strict_case_count": strict_count,
        "strict_pass_count": strict_pass_count,
        "strict_pass_rate": round(strict_pass_count / strict_denominator, 4),
        "video_case_count": video_count,
        "video_pass_rate": round(video_pass_count / (video_count or 1), 4),
        "private_leak_count": private_leak_count,
        "no_raw_path_rate": 0.0 if private_leak_count else 1.0,
        "cases": case_results,
    }
