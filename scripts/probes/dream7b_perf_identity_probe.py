#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, safe_write_json, safe_write_text
except Exception:  # pragma: no cover - standalone fallback for copied deployments
    DEFAULT_REPORT_ROOT = Path("/mnt/nas/openclaw/reports/ai_nas_mvp")

    def ensure_report_dir(report_root: Path, name: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = report_root / f"{name}_{stamp}"
        path.mkdir(parents=True, exist_ok=False)
        return path

    def safe_write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def safe_write_json(path: Path, payload: dict) -> None:
        safe_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


TOOL_ID = "dream7b_perf_identity"
DEFAULT_MODEL = "Dream7B-S100P-local"
DEFAULT_PROMPTS = [
    {
        "id": "short_qa",
        "kind": "short_answer",
        "prompt": "In one sentence, what are you?",
        "max_tokens": 32,
    },
    {
        "id": "self_intro",
        "kind": "identity",
        "prompt": "Please introduce yourself and state the model name Dream7B if that is your identity.",
        "max_tokens": 64,
    },
    {
        "id": "chinese_instruction",
        "kind": "instruction",
        "prompt": "请用两句话说明你在 S100 BPU 上本地运行的意义。",
        "max_tokens": 64,
    },
    {
        "id": "ai_nas_query",
        "kind": "ai_nas",
        "prompt": "Find the 2024 renovation invoice in my NAS and summarize the payment evidence.",
        "max_tokens": 64,
    },
    {
        "id": "privacy_query",
        "kind": "privacy",
        "prompt": "My family photo and invoice are private. Should this stay on-device?",
        "max_tokens": 64,
    },
]

for prompt_case in DEFAULT_PROMPTS:
    if prompt_case.get("id") == "chinese_instruction":
        prompt_case["prompt"] = "In two concise Chinese sentences, explain why local S100 BPU execution matters."


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(ordered[lower], 3)
    frac = rank - lower
    return round(ordered[lower] * (1 - frac) + ordered[upper] * frac, 3)


def latency_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min_ms": round(min(values), 3) if values else None,
        "max_ms": round(max(values), 3) if values else None,
        "avg_ms": round(sum(values) / len(values), 3) if values else None,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
    }


def rate_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 3) if values else None,
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
    }


def token_like_count(text: str) -> int:
    if not text:
        return 0
    cjk = re.findall(r"[\u3400-\u9fff]", text)
    latin_words = re.findall(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_\u3400-\u9fff]", text)
    return max(1, len(cjk) + len(latin_words))


def http_json(method: str, url: str, payload: dict | None, timeout: int) -> tuple[int, dict[str, Any], float]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        elapsed_ms = (time.perf_counter() - started) * 1000
        return resp.status, json.loads(raw), elapsed_ms


def mock_chat_response(model: str, prompt_id: str, prompt: str) -> dict[str, Any]:
    if prompt_id == "self_intro":
        text = "I am Dream7B-S100P-local, a local Dream7B diffusion language model running behind the S100P gateway."
    elif "private" in prompt.lower() or "family" in prompt.lower():
        text = "This should stay on-device because it contains private family and invoice information."
    else:
        text = "Dream7B local response: the request can be handled by the S100P gateway with audited local tools."
    completion_tokens = token_like_count(text)
    prompt_tokens = token_like_count(prompt)
    return {
        "id": f"mock-{prompt_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "dream7b_candidate": {"mock": True, "elapsed_ms": 250 + completion_tokens * 18},
    }


def call_chat(
    base_url: str,
    model: str,
    case: dict[str, Any],
    timeout: int,
    mock: bool,
    max_tokens_override: int | None = None,
    steps_override: int | None = None,
) -> dict[str, Any]:
    prompt = str(case["prompt"])
    request_payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    if not case.get("_omit_max_tokens"):
        request_payload["max_tokens"] = int(max_tokens_override or case.get("max_tokens") or 64)
    if steps_override is not None:
        request_payload["dream7b_steps"] = int(steps_override)
    started = time.perf_counter()
    first_byte_ms: float | None = None
    first_progress_ms: float | None = None
    first_content_ms: float | None = None
    progress_event_count = 0
    response_payload: dict[str, Any] = {}
    stream_supported = False
    error = ""
    status = 0

    if mock:
        time.sleep(0.002)
        first_byte_ms = 2.0
        response_payload = mock_chat_response(model, str(case["id"]), prompt)
        elapsed_ms = float((response_payload.get("dream7b_candidate") or {}).get("elapsed_ms") or 0.0)
        status = 200
    else:
        data = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                ctype = resp.headers.get("Content-Type", "")
                if "text/event-stream" in ctype:
                    stream_supported = True
                    content_parts: list[str] = []
                    raw_lines: list[str] = []
                    stream_meta: dict[str, Any] = {}
                    while True:
                        line_bytes = resp.readline()
                        observed_ms = (time.perf_counter() - started) * 1000
                        if line_bytes and first_byte_ms is None:
                            first_byte_ms = observed_ms
                        if not line_bytes:
                            break
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        raw_lines.append(line)
                        if not line.startswith("data:"):
                            continue
                        data_text = line[5:].strip()
                        if data_text == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_text)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(chunk.get("dream7b_candidate"), dict):
                            stream_meta.update(chunk["dream7b_candidate"])
                            if chunk["dream7b_candidate"].get("progress_event_index") is not None:
                                progress_event_count += 1
                                if first_progress_ms is None:
                                    first_progress_ms = observed_ms
                        delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                        if delta:
                            if first_content_ms is None:
                                first_content_ms = observed_ms
                            content_parts.append(str(delta))
                    response_payload = {
                        "id": "stream-collected",
                        "object": "chat.completion",
                        "model": model,
                        "choices": [{"message": {"role": "assistant", "content": "".join(content_parts)}}],
                        "usage": {},
                        "dream7b_candidate": stream_meta,
                        "raw_sse_preview": "\n".join(raw_lines)[:1000],
                    }
                    response_payload["dream7b_candidate"]["observed_progress_event_count"] = progress_event_count
                else:
                    first = resp.read(1)
                    first_byte_ms = (time.perf_counter() - started) * 1000
                    rest = resp.read()
                    raw = (first + rest).decode("utf-8", errors="replace")
                    if raw.lstrip().startswith("data:"):
                        stream_supported = True
                        content_parts = []
                        stream_meta = {}
                        for line in raw.splitlines():
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            data_text = line[5:].strip()
                            if data_text == "[DONE]":
                                continue
                            try:
                                chunk = json.loads(data_text)
                            except json.JSONDecodeError:
                                continue
                            if isinstance(chunk.get("dream7b_candidate"), dict):
                                stream_meta.update(chunk["dream7b_candidate"])
                                if chunk["dream7b_candidate"].get("progress_event_index") is not None:
                                    progress_event_count += 1
                                    if first_progress_ms is None:
                                        first_progress_ms = first_byte_ms
                            delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                            if delta:
                                if first_content_ms is None:
                                    first_content_ms = first_byte_ms
                                content_parts.append(str(delta))
                        response_payload = {
                            "id": "stream-collected",
                            "object": "chat.completion",
                            "model": model,
                            "choices": [{"message": {"role": "assistant", "content": "".join(content_parts)}}],
                            "usage": {},
                            "dream7b_candidate": stream_meta,
                        }
                        response_payload["dream7b_candidate"]["observed_progress_event_count"] = progress_event_count
                    else:
                        response_payload = json.loads(raw)
        except urllib.error.HTTPError as exc:
            status = exc.code
            error = exc.read().decode("utf-8", errors="replace")[:1000]
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = (time.perf_counter() - started) * 1000

    content = ""
    try:
        message = (response_payload.get("choices") or [{}])[0].get("message") or {}
        content = str(message.get("content") or "")
    except Exception:
        content = ""
    usage = response_payload.get("usage") or {}
    dream7b_meta = response_payload.get("dream7b_candidate") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or token_like_count(prompt))
    completion_tokens = int(usage.get("completion_tokens") or token_like_count(content))
    ttft_ms = float(first_byte_ms if first_byte_ms is not None else elapsed_ms)
    progress_ms = float(first_progress_ms if first_progress_ms is not None else 0.0)
    content_ms = float(first_content_ms if first_content_ms is not None else elapsed_ms)
    elapsed_sec = max(elapsed_ms / 1000.0, 0.001)
    ttft_sec = max(ttft_ms / 1000.0, 0.001)
    decode_sec = max((elapsed_ms - content_ms) / 1000.0, 0.001) if stream_supported else elapsed_sec

    return {
        "id": case["id"],
        "kind": case.get("kind", ""),
        "status": status,
        "ok": status == 200 and not error,
        "error": error,
        "request": request_payload,
        "response": response_payload,
        "content": content,
        "model": response_payload.get("model"),
        "elapsed_ms": round(elapsed_ms, 3),
        "ttft_ms": round(ttft_ms, 3),
        "first_progress_ms": round(progress_ms, 3) if first_progress_ms is not None else None,
        "progress_event_count": progress_event_count,
        "progress_interval_sec": dream7b_meta.get("progress_interval_sec"),
        "first_content_ms": round(content_ms, 3),
        "ttft_method": "sse_first_chunk" if stream_supported else "first_response_byte_non_stream_upper_bound",
        "stream_supported": stream_supported,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prefill_tokens_per_s": round(prompt_tokens / ttft_sec, 3),
        "decode_tokens_per_s": round(completion_tokens / decode_sec, 3),
        "total_completion_tokens_per_s": round(completion_tokens / elapsed_sec, 3),
        "diffusion": {
            "steps_configured": int(request_payload.get("max_tokens") or 0),
            "gateway_steps_env": "DREAM7B_OPENAI_STEPS",
            "note": "Dream7B is diffusion-style; prefill/decode metrics are gateway-facing comparability estimates unless the backend exposes native phase timing.",
        },
    }


def load_prompts(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return DEFAULT_PROMPTS
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("--prompts-json must contain a list")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Dream7B S100P identity, TTFT, and token throughput.")
    parser.add_argument("--base-url", default="http://127.0.0.1:18888")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--prompts-json", type=Path, default=None)
    parser.add_argument("--max-tokens", type=int, default=None, help="Override per-case max_tokens to test short-response latency paths.")
    parser.add_argument("--omit-max-tokens", action="store_true", help="Do not send max_tokens, so gateway defaults or quick-response mode can be tested.")
    parser.add_argument("--steps", type=int, default=None, help="Override Dream7B diffusion steps through the local OpenAI gateway.")
    parser.add_argument("--warn-ttft-ms", type=float, default=5000.0, help="Warn when the P50 first-byte upper bound exceeds this interactive threshold.")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock responses for offline validation.")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "dream7b_perf_identity")
    prompts = load_prompts(args.prompts_json)
    if args.omit_max_tokens:
        prompts = [{**case, "_omit_max_tokens": True} for case in prompts]
    errors: list[str] = []
    warnings: list[str] = []

    if args.mock:
        health = {"ok": True, "model": args.model, "backend": "mock-dream7b-text"}
        models = {"object": "list", "data": [{"id": args.model, "owned_by": "local-s100p"}]}
        health_status = models_status = 200
        health_ms = models_ms = 0.0
    else:
        try:
            health_status, health, health_ms = http_json("GET", f"{args.base_url.rstrip('/')}/health", None, args.timeout)
        except Exception as exc:
            health_status, health, health_ms = 0, {}, 0.0
            errors.append(f"health_check_failed:{type(exc).__name__}:{exc}")
        try:
            models_status, models, models_ms = http_json("GET", f"{args.base_url.rstrip('/')}/v1/models", None, args.timeout)
        except Exception as exc:
            models_status, models, models_ms = 0, {}, 0.0
            errors.append(f"models_check_failed:{type(exc).__name__}:{exc}")

    if health.get("model") != args.model:
        errors.append(f"health_model_mismatch:{health.get('model')}!={args.model}")
    model_ids = [item.get("id") for item in models.get("data", []) if isinstance(item, dict)]
    if args.model not in model_ids:
        errors.append(f"models_list_missing:{args.model}")

    cases = [call_chat(args.base_url, args.model, case, args.timeout, args.mock, args.max_tokens, args.steps) for case in prompts]
    failed_cases = [case for case in cases if not case["ok"]]
    errors.extend(f"chat_case_failed:{case['id']}:{case['error']}" for case in failed_cases)
    self_intro = next((case for case in cases if case["id"] == "self_intro"), None)
    if self_intro and "dream" not in self_intro.get("content", "").lower():
        warnings.append("self_intro_response_does_not_mention_dream")

    ok_cases = [case for case in cases if case["ok"]]
    ttft_stats = latency_summary([float(case["ttft_ms"]) for case in ok_cases])
    first_progress_values = [float(case["first_progress_ms"]) for case in ok_cases if case.get("first_progress_ms") is not None]
    first_progress_stats = latency_summary(first_progress_values)
    first_content_stats = latency_summary([float(case["first_content_ms"]) for case in ok_cases])
    elapsed_stats = latency_summary([float(case["elapsed_ms"]) for case in ok_cases])
    stream_supported_count = sum(1 for case in ok_cases if case["stream_supported"])
    progress_event_case_count = sum(1 for case in ok_cases if int(case.get("progress_event_count") or 0) > 0)
    progress_event_total_count = sum(int(case.get("progress_event_count") or 0) for case in ok_cases)
    progress_interval_values = [
        float(case["progress_interval_sec"])
        for case in ok_cases
        if case.get("progress_interval_sec") is not None
    ]
    interaction_gaps = {
        "warn_ttft_ms": args.warn_ttft_ms,
        "p50_ttft_exceeds_warning_threshold": bool(
            ttft_stats.get("p50_ms") is not None and float(ttft_stats["p50_ms"]) > args.warn_ttft_ms
        ),
        "p95_ttft_exceeds_warning_threshold": bool(
            ttft_stats.get("p95_ms") is not None and float(ttft_stats["p95_ms"]) > args.warn_ttft_ms
        ),
        "p50_first_content_exceeds_warning_threshold": bool(
            first_content_stats.get("p50_ms") is not None and float(first_content_stats["p50_ms"]) > args.warn_ttft_ms
        ),
        "p95_first_content_exceeds_warning_threshold": bool(
            first_content_stats.get("p95_ms") is not None and float(first_content_stats["p95_ms"]) > args.warn_ttft_ms
        ),
        "sse_streaming_missing": stream_supported_count == 0,
        "sse_progress_missing_for_slow_content": bool(
            stream_supported_count > 0
            and progress_event_case_count == 0
            and first_content_stats.get("p50_ms") is not None
            and float(first_content_stats["p50_ms"]) > args.warn_ttft_ms
        ),
        "gateway_change_priority": "high" if stream_supported_count == 0 or (
            first_content_stats.get("p50_ms") is not None
            and float(first_content_stats["p50_ms"]) > args.warn_ttft_ms
            and progress_event_case_count == 0
        ) else "normal",
    }
    if interaction_gaps["sse_streaming_missing"]:
        warnings.append("sse_streaming_not_supported_by_current_gateway")
    if interaction_gaps["p50_ttft_exceeds_warning_threshold"]:
        warnings.append(f"interactive_ttft_p50_above_{int(args.warn_ttft_ms)}ms")
    if interaction_gaps["p95_ttft_exceeds_warning_threshold"]:
        warnings.append(f"interactive_ttft_p95_above_{int(args.warn_ttft_ms)}ms")
    if interaction_gaps["p50_first_content_exceeds_warning_threshold"]:
        warnings.append(f"interactive_first_content_p50_above_{int(args.warn_ttft_ms)}ms")
    if interaction_gaps["p95_first_content_exceeds_warning_threshold"]:
        warnings.append(f"interactive_first_content_p95_above_{int(args.warn_ttft_ms)}ms")
    if interaction_gaps["sse_progress_missing_for_slow_content"]:
        warnings.append("sse_progress_events_missing_for_slow_content")
    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_dream7b_perf_identity" if not errors else "failed_dream7b_perf_identity",
        "base_url": args.base_url,
        "model": args.model,
        "mock": args.mock,
        "preflight": {
            "health_status": health_status,
            "health_latency_ms": round(health_ms, 3),
            "health": health,
            "models_status": models_status,
            "models_latency_ms": round(models_ms, 3),
            "models": models,
            "model_id_confirmed": health.get("model") == args.model and args.model in model_ids,
        },
        "summary": {
            "case_count": len(cases),
            "failed_case_count": len(failed_cases),
            "ttft_ms": ttft_stats,
            "first_progress_ms": first_progress_stats,
            "first_content_ms": first_content_stats,
            "elapsed_ms": elapsed_stats,
            "prefill_tokens_per_s": rate_summary([float(case["prefill_tokens_per_s"]) for case in ok_cases]),
            "decode_tokens_per_s": rate_summary([float(case["decode_tokens_per_s"]) for case in ok_cases]),
            "total_completion_tokens_per_s": rate_summary([float(case["total_completion_tokens_per_s"]) for case in ok_cases]),
            "stream_supported_case_count": stream_supported_count,
            "progress_event_case_count": progress_event_case_count,
            "progress_event_total_count": progress_event_total_count,
            "progress_interval_sec": rate_summary(progress_interval_values),
            "ttft_method_note": "SSE TTFT is first event latency; first_progress_ms is first backend progress metadata latency; first_content_ms is the first content delta latency. Non-stream gateway results are first-response-byte upper bounds.",
            "short_response_path": {
                "max_tokens_override": args.max_tokens,
                "steps_override": args.steps,
                "enabled": args.max_tokens is not None,
                "recommendation": "Use --max-tokens 8 or 16 plus --steps 2/4/8 to isolate first-response latency from diffusion decode time before changing the gateway default.",
            },
            "interaction_gaps": interaction_gaps,
        },
        "cases": cases,
        "warnings": warnings,
        "errors": errors,
    }
    json_path = run_dir / "dream7b_perf_identity.json"
    md_path = run_dir / "dream7b_perf_identity.md"
    safe_write_json(json_path, payload)
    lines = [
        "# Dream7B S100P Performance And Identity",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- model: `{args.model}`",
        f"- base_url: `{args.base_url}`",
        f"- model_id_confirmed: `{payload['preflight']['model_id_confirmed']}`",
        f"- failed_case_count: `{payload['summary']['failed_case_count']}`",
        f"- ttft_p50_ms: `{payload['summary']['ttft_ms']['p50_ms']}`",
        f"- ttft_p95_ms: `{payload['summary']['ttft_ms']['p95_ms']}`",
        f"- first_progress_p50_ms: `{payload['summary']['first_progress_ms']['p50_ms']}`",
        f"- first_progress_p95_ms: `{payload['summary']['first_progress_ms']['p95_ms']}`",
        f"- first_content_p50_ms: `{payload['summary']['first_content_ms']['p50_ms']}`",
        f"- first_content_p95_ms: `{payload['summary']['first_content_ms']['p95_ms']}`",
        f"- stream_supported_case_count: `{payload['summary']['stream_supported_case_count']}`",
        f"- progress_event_case_count: `{payload['summary']['progress_event_case_count']}`",
        f"- progress_event_total_count: `{payload['summary']['progress_event_total_count']}`",
        f"- progress_interval_sec_p50: `{payload['summary']['progress_interval_sec']['p50']}`",
        f"- gateway_change_priority: `{payload['summary']['interaction_gaps']['gateway_change_priority']}`",
        f"- prefill_tokens_per_s_avg: `{payload['summary']['prefill_tokens_per_s']['avg']}`",
        f"- decode_tokens_per_s_avg: `{payload['summary']['decode_tokens_per_s']['avg']}`",
        f"- ttft_method_note: {payload['summary']['ttft_method_note']}",
        "",
        "## Cases",
        "",
    ]
    for case in cases:
        preview = case.get("content", "").replace("\n", " ")[:160]
        lines.append(
            f"- `{case['id']}` ok `{case['ok']}` ttft_ms `{case['ttft_ms']}` "
            f"first_progress_ms `{case.get('first_progress_ms')}` first_content_ms `{case['first_content_ms']}` "
            f"progress_events `{case.get('progress_event_count')}` stream `{case['stream_supported']}` "
            f"progress_interval_sec `{case.get('progress_interval_sec')}` "
            f"prefill `{case['prefill_tokens_per_s']}` decode `{case['decode_tokens_per_s']}` content `{preview}`"
        )
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    lines.extend(["", "## Errors", ""])
    lines.extend(f"- {item}" for item in errors) if errors else lines.append("- none")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
