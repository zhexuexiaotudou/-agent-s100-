#!/usr/bin/env python3
"""Measure the current default Dream7B OpenClaw gateway latency.

This probe intentionally does not override max_tokens or steps. It measures the
gateway as OpenClaw sees it today and records both non-stream elapsed time and
SSE first-event / first-content timing.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_PROMPTS = [
    ("identity", "\u4f60\u662f\u8c01\uff1f\u8bf7\u7528\u4e00\u53e5\u4e2d\u6587\u8bf4\u660e\u4f60\u7684\u6a21\u578b\u8eab\u4efd\u3002"),
    ("math", "1+1\u7b49\u4e8e\u51e0\uff1f\u53ea\u56de\u7b54\u6570\u5b57\u3002"),
]


def post_json(url: str, payload: dict[str, Any], timeout: int) -> tuple[int, dict[str, Any], float]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        status = int(resp.status)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return status, json.loads(raw), elapsed_ms


def stream_json(url: str, payload: dict[str, Any], timeout: int) -> tuple[int, dict[str, Any], float]:
    body = json.dumps({**payload, "stream": True}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_event_ms: float | None = None
    first_progress_ms: float | None = None
    first_content_ms: float | None = None
    progress_count = 0
    content_parts: list[str] = []
    final_meta: dict[str, Any] = {}
    raw_preview: list[str] = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = int(resp.status)
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if len(raw_preview) < 8:
                raw_preview.append(line)
            if not line.startswith("data: "):
                continue
            if first_event_ms is None:
                first_event_ms = (time.perf_counter() - started) * 1000.0
            data_text = line[len("data: ") :]
            if data_text == "[DONE]":
                break
            try:
                event = json.loads(data_text)
            except json.JSONDecodeError:
                continue
            meta = event.get("dream7b_candidate") or {}
            if meta.get("progress_event_index") is not None:
                progress_count += 1
                if first_progress_ms is None:
                    first_progress_ms = (time.perf_counter() - started) * 1000.0
            choices = event.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    if first_content_ms is None:
                        first_content_ms = (time.perf_counter() - started) * 1000.0
                    content_parts.append(content)
                if choices[0].get("finish_reason") == "stop":
                    final_meta = meta
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return status, {
        "content": "".join(content_parts),
        "first_event_ms": first_event_ms,
        "first_progress_ms": first_progress_ms,
        "first_content_ms": first_content_ms,
        "progress_event_count": progress_count,
        "elapsed_ms": elapsed_ms,
        "dream7b_candidate": final_meta,
        "raw_sse_preview": "\n".join(raw_preview),
    }, elapsed_ms


def get_json(url: str, timeout: int) -> tuple[int, dict[str, Any], float]:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        status = int(resp.status)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return status, json.loads(raw), elapsed_ms


def summarize_number(values: list[float | None]) -> dict[str, float | int | None]:
    nums = sorted(float(v) for v in values if v is not None)
    if not nums:
        return {"count": 0, "min_ms": None, "max_ms": None, "avg_ms": None}
    return {
        "count": len(nums),
        "min_ms": round(nums[0], 3),
        "max_ms": round(nums[-1], 3),
        "avg_ms": round(sum(nums) / len(nums), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18888")
    parser.add_argument("--model", default="Dream7B-S100P-local")
    parser.add_argument("--report-root", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--timeout-sec", type=int, default=180)
    args = parser.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.report_root) / f"dream7b_openclaw_default_latency_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    chat_url = f"{args.base_url.rstrip('/')}/v1/chat/completions"
    health_status, health, health_ms = get_json(f"{args.base_url.rstrip('/')}/health", args.timeout_sec)
    models_status, models, models_ms = get_json(f"{args.base_url.rstrip('/')}/v1/models", args.timeout_sec)

    cases = []
    for case_id, prompt in DEFAULT_PROMPTS:
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        non_status, non_data, non_elapsed_ms = post_json(chat_url, {**payload, "stream": False}, args.timeout_sec)
        stream_status, stream_data, stream_elapsed_ms = stream_json(chat_url, payload, args.timeout_sec)
        non_content = ((non_data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        cases.append(
            {
                "id": case_id,
                "prompt": prompt,
                "non_stream": {
                    "status": non_status,
                    "elapsed_ms": round(non_elapsed_ms, 3),
                    "content": non_content,
                    "dream7b_candidate": non_data.get("dream7b_candidate") or {},
                },
                "stream": {
                    "status": stream_status,
                    "elapsed_ms": round(stream_elapsed_ms, 3),
                    "content": stream_data.get("content", ""),
                    "first_event_ms": None if stream_data.get("first_event_ms") is None else round(float(stream_data["first_event_ms"]), 3),
                    "first_progress_ms": None if stream_data.get("first_progress_ms") is None else round(float(stream_data["first_progress_ms"]), 3),
                    "first_content_ms": None if stream_data.get("first_content_ms") is None else round(float(stream_data["first_content_ms"]), 3),
                    "progress_event_count": stream_data.get("progress_event_count"),
                    "dream7b_candidate": stream_data.get("dream7b_candidate") or {},
                },
            }
        )

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool_id": "dream7b_openclaw_default_latency_probe",
        "base_url": args.base_url,
        "model": args.model,
        "preflight": {
            "health_status": health_status,
            "health_latency_ms": round(health_ms, 3),
            "health": health,
            "models_status": models_status,
            "models_latency_ms": round(models_ms, 3),
            "models": models,
        },
        "cases": cases,
    }
    errors = []
    if health.get("ok") is not True:
        errors.append("health_not_ok")
    if health.get("inline_tokenizer_enabled") is not False:
        errors.append("inline_tokenizer_not_disabled")
    for case in cases:
        if case["non_stream"]["status"] != 200:
            errors.append(f"{case['id']}_non_stream_status")
        if case["stream"]["status"] != 200:
            errors.append(f"{case['id']}_stream_status")
        if not case["non_stream"]["content"]:
            errors.append(f"{case['id']}_non_stream_empty_content")
        if not case["stream"]["content"]:
            errors.append(f"{case['id']}_stream_empty_content")
    payload["summary"] = {
        "non_stream_elapsed_ms": summarize_number([case["non_stream"]["elapsed_ms"] for case in cases]),
        "stream_first_event_ms": summarize_number([case["stream"]["first_event_ms"] for case in cases]),
        "stream_first_progress_ms": summarize_number([case["stream"]["first_progress_ms"] for case in cases]),
        "stream_first_content_ms": summarize_number([case["stream"]["first_content_ms"] for case in cases]),
        "stream_elapsed_ms": summarize_number([case["stream"]["elapsed_ms"] for case in cases]),
        "note": "The gateway emits SSE role/progress events before backend text. first_content_ms is the useful user-visible latency.",
    }
    payload["errors"] = errors
    payload["verdict"] = "ok_dream7b_openclaw_default_latency_probe" if not errors else "warning_dream7b_openclaw_default_latency_probe"

    json_path = run_dir / "default_latency.json"
    md_path = run_dir / "default_latency.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Dream7B OpenClaw Default Latency",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- base_url: `{args.base_url}`",
        f"- model: `{args.model}`",
        f"- inline_tokenizer_enabled: `{health.get('inline_tokenizer_enabled')}`",
        f"- report_json: `{json_path}`",
        "",
        "## Summary",
        "",
        f"- non_stream_elapsed_ms: `{payload['summary']['non_stream_elapsed_ms']}`",
        f"- stream_first_event_ms: `{payload['summary']['stream_first_event_ms']}`",
        f"- stream_first_progress_ms: `{payload['summary']['stream_first_progress_ms']}`",
        f"- stream_first_content_ms: `{payload['summary']['stream_first_content_ms']}`",
        f"- stream_elapsed_ms: `{payload['summary']['stream_elapsed_ms']}`",
        "",
        "## Cases",
        "",
    ]
    for case in cases:
        lines.extend(
            [
                f"- `{case['id']}` non_stream `{case['non_stream']['elapsed_ms']}` ms content `{case['non_stream']['content']}`",
                f"- `{case['id']}` stream first_event `{case['stream']['first_event_ms']}` ms first_content `{case['stream']['first_content_ms']}` ms elapsed `{case['stream']['elapsed_ms']}` ms content `{case['stream']['content']}`",
            ]
        )
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {item}" for item in errors] or ["- none"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(md_path)
    print(json_path)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
