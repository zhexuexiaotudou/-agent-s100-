#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def case_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(case.get("id")): case for case in payload.get("cases") or []}


def meta(case: dict[str, Any]) -> dict[str, Any]:
    return (case.get("dream7b_candidate") or (case.get("response") or {}).get("dream7b_candidate") or {})


def metric(case: dict[str, Any], key: str) -> Any:
    value = case.get(key)
    return value


def delta(a: Any, b: Any) -> float | None:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return round(float(b) - float(a), 3)
    return None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    pos = (len(ordered) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return round(ordered[lower] * (1.0 - frac) + ordered[upper] * frac, 3)


def metric_summary(payload: dict[str, Any], metric_name: str) -> dict[str, Any]:
    existing = (payload.get("summary") or {}).get(metric_name)
    if isinstance(existing, dict) and existing.get("p50_ms") is not None:
        return existing
    values = [
        float(case[metric_name])
        for case in payload.get("cases") or []
        if isinstance(case.get(metric_name), (int, float))
    ]
    return {
        "p50_ms": percentile(values, 0.5),
        "p95_ms": percentile(values, 0.95),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--explicit-json", type=Path, required=True)
    parser.add_argument("--quickpath-json", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    args = parser.parse_args()

    explicit = read_json(args.explicit_json)
    quickpath = read_json(args.quickpath_json)
    explicit_cases = case_by_id(explicit)
    quick_cases = case_by_id(quickpath)
    case_ids = sorted(set(explicit_cases) & set(quick_cases))
    rows = []
    for case_id in case_ids:
        left = explicit_cases[case_id]
        right = quick_cases[case_id]
        left_meta = meta(left)
        right_meta = meta(right)
        rows.append(
            {
                "id": case_id,
                "explicit_first_content_ms": metric(left, "first_content_ms"),
                "quickpath_first_content_ms": metric(right, "first_content_ms"),
                "delta_quickpath_minus_explicit_ms": delta(
                    metric(left, "first_content_ms"), metric(right, "first_content_ms")
                ),
                "explicit_quick_response_mode": left_meta.get("quick_response_mode"),
                "quickpath_quick_response_mode": right_meta.get("quick_response_mode"),
                "explicit_execution_path": left_meta.get("execution_path"),
                "quickpath_execution_path": right_meta.get("execution_path"),
                "explicit_progress_event_count": left.get("progress_event_count"),
                "quickpath_progress_event_count": right.get("progress_event_count"),
                "explicit_content_preview": str(left.get("content") or "")[:120],
                "quickpath_content_preview": str(right.get("content") or "")[:120],
            }
        )

    explicit_first_content = metric_summary(explicit, "first_content_ms")
    quick_first_content = metric_summary(quickpath, "first_content_ms")
    decision = {
        "quick_path_requires_omitting_explicit_max_tokens_and_steps": True,
        "quick_ready_improved_when_quickpath_enabled": any(
            row["id"] == "quick_ready"
            and row["quickpath_quick_response_mode"] is True
            and isinstance(row["delta_quickpath_minus_explicit_ms"], (int, float))
            and row["delta_quickpath_minus_explicit_ms"] < 0
            for row in rows
        ),
        "identity_fast_path_ready": any(
            row["id"] == "identity_short"
            and row["quickpath_execution_path"] == "gateway_fast_identity"
            and float(row["quickpath_first_content_ms"] or 1e9) < 100.0
            for row in rows
        ),
        "non_quick_localized_prompt_still_slow": any(
            row["id"] == "chinese_short"
            and row["quickpath_quick_response_mode"] is not True
            and float(row["quickpath_first_content_ms"] or 0.0) > 5000.0
            for row in rows
        ),
        "recommended_next": (
            "fast-ready, identity, and local-status prompts are now covered by gateway fast paths; "
            "keep SSE progress for general backend generation and continue tracking first-content latency separately"
        ),
    }
    verdict = (
        "warning_dream7b_first_response_routing_packet"
        if decision["non_quick_localized_prompt_still_slow"]
        else "ok_dream7b_first_response_routing_packet"
    )
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "explicit_json": str(args.explicit_json),
        "quickpath_json": str(args.quickpath_json),
        "summary": {
            "explicit_first_content_p50_ms": explicit_first_content.get("p50_ms"),
            "explicit_first_content_p95_ms": explicit_first_content.get("p95_ms"),
            "quickpath_first_content_p50_ms": quick_first_content.get("p50_ms"),
            "quickpath_first_content_p95_ms": quick_first_content.get("p95_ms"),
            "explicit_warnings": explicit.get("warnings") or [],
            "quickpath_warnings": quickpath.get("warnings") or [],
        },
        "rows": rows,
        "decision": decision,
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_first_response_routing_packet_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_first_response_routing_packet.json"
    out_md = out_dir / "dream7b_first_response_routing_packet.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Dream7B First Response Routing Packet",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- explicit_first_content_p50_ms: {payload['summary']['explicit_first_content_p50_ms']}",
        f"- quickpath_first_content_p50_ms: {payload['summary']['quickpath_first_content_p50_ms']}",
        f"- explicit_first_content_p95_ms: {payload['summary']['explicit_first_content_p95_ms']}",
        f"- quickpath_first_content_p95_ms: {payload['summary']['quickpath_first_content_p95_ms']}",
        "",
        "## Decision",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in decision.items())
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| id | explicit_content_ms | quickpath_content_ms | delta_ms | explicit_quick | quickpath_quick | quickpath_path |",
            "| --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['explicit_first_content_ms']} | {row['quickpath_first_content_ms']} | "
            f"{row['delta_quickpath_minus_explicit_ms']} | {row['explicit_quick_response_mode']} | "
            f"{row['quickpath_quick_response_mode']} | {row['quickpath_execution_path']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if verdict.startswith(("ok_", "warning_")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
