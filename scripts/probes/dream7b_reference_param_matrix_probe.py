#!/usr/bin/env python3
"""Dream7B GGUF diffuse-resident parameter matrix probe.

Sweeps n_generate (max_tokens) and n_steps across a fixed set of Chinese prompts
to find the quality/speed tradeoff for OpenClaw reply quality.

Usage on S100P:
  python3 scripts/probes/dream7b_reference_param_matrix_probe.py \
    --base-url http://127.0.0.1:18888 \
    --model Dream7B-S100P-local \
    --report-dir /mnt/nas/openclaw/reports/models
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(CST).isoformat()


def chat_completion(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    steps: int,
    timeout_sec: int = 300,
) -> dict:
    """Call the OpenAI-compatible chat completions endpoint."""
    url = f"{base_url}/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "dream7b_steps": steps,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            elapsed_ms = int((time.time() - started) * 1000)
            result = json.loads(resp.read().decode("utf-8"))
            content = ""
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
            return {
                "ok": True,
                "content": content,
                "elapsed_ms": elapsed_ms,
                "finish_reason": result["choices"][0].get("finish_reason", "") if result.get("choices") else "",
            }
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        return {"ok": False, "error": str(exc), "elapsed_ms": elapsed_ms}


# Fixed Chinese prompts covering AI-NAS use cases
PROMPTS = [
    {
        "id": "self_intro",
        "text": "请用中文介绍一下你自己，你是谁，你运行在什么设备上。",
        "min_chars": 10,
    },
    {
        "id": "file_search",
        "text": "假设你是一个NAS文件助手，用户问你：'帮我找一下2024年的装修合同'。请用中文简短回答你会怎么处理这个请求。",
        "min_chars": 15,
    },
    {
        "id": "nas_status",
        "text": "假设你连接到一台NAS，请用中文简要说明NAS存储状态检查应该看哪些方面。",
        "min_chars": 20,
    },
]

# Parameter combinations to sweep
SWEEP = [
    # (max_tokens, steps, label)
    (16, 4, "baseline"),
    (16, 8, "steps_x2"),
    (16, 16, "steps_x4"),
    (16, 32, "steps_x8"),
    (16, 64, "steps_x16"),
    (32, 4, "tokens_x2"),
    (32, 8, "t2_s8"),
    (32, 16, "t2_s16"),
    (32, 32, "t2_s32"),
    (64, 4, "tokens_x4"),
    (64, 8, "t4_s8"),
    (64, 16, "t4_s16"),
    (64, 32, "t4_s32"),
    (128, 8, "t8_s8"),
    (128, 16, "t8_s16"),
    (128, 32, "t8_s32"),
    (128, 64, "t8_s64"),
]


def quality_score(content: str, min_chars: int) -> dict:
    """Basic quality heuristics for generated text."""
    has_chinese = any("\u4e00" <= c <= "\u9fff" for c in content)
    length = len(content)
    words = content.split()
    return {
        "char_count": length,
        "word_count": len(words),
        "has_chinese": has_chinese,
        "meets_min_chars": length >= min_chars,
        "is_empty": length == 0,
        "is_garbled": length > 0 and not has_chinese and min_chars > 10,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18888")
    parser.add_argument("--model", default="Dream7B-S100P-local")
    parser.add_argument("--report-dir", default="/mnt/nas/openclaw/reports/models")
    parser.add_argument("--prompt-ids", default="self_intro,file_search,nas_status")
    parser.add_argument("--skip-if-exists", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.report_dir) / f"dream7b_gguf_param_matrix_{datetime.now(CST).strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt_ids = [p.strip() for p in args.prompt_ids.split(",")]
    prompts = [p for p in PROMPTS if p["id"] in prompt_ids]

    results = []
    errors = []
    total = len(SWEEP) * len(prompts)
    done = 0

    print(f"=== Dream7B GGUF Parameter Matrix Probe ===")
    print(f"base_url: {args.base_url}")
    print(f"prompts: {len(prompts)}, combos: {len(SWEEP)}")
    print(f"total runs: {total}")
    print(f"report: {run_dir}")
    print()

    for max_tokens, steps, label in SWEEP:
        for prompt_info in prompts:
            done += 1
            pid = prompt_info["id"]
            prompt_text = prompt_info["text"]

            print(f"[{done}/{total}] {label} n={max_tokens} s={steps} prompt={pid} ... ", end="", flush=True)

            result = chat_completion(args.base_url, args.model, prompt_text, max_tokens, steps)
            result.update({
                "prompt_id": pid,
                "max_tokens": max_tokens,
                "steps": steps,
                "label": label,
            })

            if result["ok"]:
                q = quality_score(result["content"], prompt_info["min_chars"])
                result["quality"] = q
                print(f"OK {result['elapsed_ms']}ms {q['char_count']}chars chinese={q['has_chinese']}")
            else:
                errors.append(result)
                print(f"FAIL {result['error'][:80]}")

            results.append(result)

    # Summary
    ok_results = [r for r in results if r["ok"]]
    fail_results = [r for r in results if not r["ok"]]

    # Find best combo per prompt
    best = {}
    for prompt_info in prompts:
        pid = prompt_info["id"]
        prompt_oks = [r for r in ok_results if r["prompt_id"] == pid and r.get("quality", {}).get("meets_min_chars")]
        if prompt_oks:
            best[pid] = min(prompt_oks, key=lambda r: r["elapsed_ms"])

    payload = {
        "generated_at": now_iso(),
        "verdict": "ok_dream7b_gguf_param_matrix" if ok_results else "partial",
        "base_url": args.base_url,
        "model": args.model,
        "prompt_count": len(prompts),
        "combo_count": len(SWEEP),
        "total_runs": total,
        "ok_count": len(ok_results),
        "fail_count": len(fail_results),
        "results": results,
        "best_per_prompt": {k: {
            "label": v["label"],
            "max_tokens": v["max_tokens"],
            "steps": v["steps"],
            "elapsed_ms": v["elapsed_ms"],
            "char_count": v.get("quality", {}).get("char_count"),
        } for k, v in best.items()},
        "summary": {
            "total_elapsed_ms": sum(r["elapsed_ms"] for r in results),
            "baseline_ms": [r["elapsed_ms"] for r in ok_results if r["label"] == "baseline"],
        },
        "errors": errors,
    }

    (run_dir / "dream7b_gguf_param_matrix.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Markdown report
    lines = [
        "# Dream7B GGUF Parameter Matrix Probe",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- ok: {len(ok_results)}, fail: {len(fail_results)}",
        f"- total runs: {total}",
        "",
        "## Best per prompt (meets min chars, fastest)",
        "",
        "| Prompt | Label | max_tokens | steps | elapsed_ms | chars |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for pid, info in payload["best_per_prompt"].items():
        lines.append(f"| {pid} | {info['label']} | {info['max_tokens']} | {info['steps']} | {info['elapsed_ms']} | {info['char_count']} |")

    lines += [
        "",
        "## All results",
        "",
        "| Label | Prompt | max_tokens | steps | elapsed_ms | chars | Chinese | OK |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        q = r.get("quality", {})
        lines.append(
            f"| {r['label']} | {r['prompt_id']} | {r['max_tokens']} | {r['steps']} | "
            f"{r['elapsed_ms']} | {q.get('char_count', 0)} | {q.get('has_chinese', False)} | {r['ok']} |"
        )

    if fail_results:
        lines += ["", "## Failures", ""]
        for r in fail_results:
            lines.append(f"- {r['label']}/{r['prompt_id']}: {r.get('error', 'unknown')[:120]}")

    (run_dir / "dream7b_gguf_param_matrix.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\n=== DONE ===")
    print(f"ok: {len(ok_results)}, fail: {len(fail_results)}")
    for pid, info in payload["best_per_prompt"].items():
        print(f"  {pid}: {info['label']} n={info['max_tokens']} s={info['steps']} {info['elapsed_ms']}ms")
    print(f"report: {run_dir / 'dream7b_gguf_param_matrix.md'}")


if __name__ == "__main__":
    main()
