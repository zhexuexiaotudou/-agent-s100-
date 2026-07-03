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


def call_chat(base_url: str, model: str, case: dict[str, Any], timeout: int, mock: bool) -> dict[str, Any]:
    prompt = str(case["prompt"])
    request_payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": int(case.get("max_tokens") or 64),
        "stream": True,
    }
    started = time.perf_counter()
    first_byte_ms: float | None = None
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
                first = resp.read(1)
                first_byte_ms = (time.perf_counter() - started) * 1000
                rest = resp.read()
                raw = (first + rest).decode("utf-8", errors="replace")
                ctype = resp.headers.get("Content-Type", "")
                if "text/event-stream" in ctype or raw.lstrip().startswith("data:"):
                    stream_supported = True
                    content_parts: list[str] = []
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
                        delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                        if delta:
                            content_parts.append(str(delta))
                    response_payload = {
                        "id": "stream-collected",
                        "object": "chat.completion",
                        "model": model,
                        "choices": [{"message": {"role": "assistant", "content": "".join(content_parts)}}],
                        "usage": {},
                    }
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
    prompt_tokens = int(usage.get("prompt_tokens") or token_like_count(prompt))
    completion_tokens = int(usage.get("completion_tokens") or token_like_count(content))
    ttft_ms = float(first_byte_ms if first_byte_ms is not None else elapsed_ms)
    elapsed_sec = max(elapsed_ms / 1000.0, 0.001)
    ttft_sec = max(ttft_ms / 1000.0, 0.001)
    decode_sec = max((elapsed_ms - ttft_ms) / 1000.0, 0.001) if stream_supported else elapsed_sec

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
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock responses for offline validation.")
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "dream7b_perf_identity")
    prompts = load_prompts(args.prompts_json)
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

    cases = [call_chat(args.base_url, args.model, case, args.timeout, args.mock) for case in prompts]
    failed_cases = [case for case in cases if not case["ok"]]
    errors.extend(f"chat_case_failed:{case['id']}:{case['error']}" for case in failed_cases)
    self_intro = next((case for case in cases if case["id"] == "self_intro"), None)
    if self_intro and "dream" not in self_intro.get("content", "").lower():
        warnings.append("self_intro_response_does_not_mention_dream")

    ok_cases = [case for case in cases if case["ok"]]
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
            "ttft_ms": latency_summary([float(case["ttft_ms"]) for case in ok_cases]),
            "elapsed_ms": latency_summary([float(case["elapsed_ms"]) for case in ok_cases]),
            "prefill_tokens_per_s": rate_summary([float(case["prefill_tokens_per_s"]) for case in ok_cases]),
            "decode_tokens_per_s": rate_summary([float(case["decode_tokens_per_s"]) for case in ok_cases]),
            "total_completion_tokens_per_s": rate_summary([float(case["total_completion_tokens_per_s"]) for case in ok_cases]),
            "stream_supported_case_count": sum(1 for case in ok_cases if case["stream_supported"]),
            "ttft_method_note": "Non-stream gateway results are first-response-byte upper bounds, not native token streaming.",
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
