#!/usr/bin/env python3
"""Minimal OpenAI-compatible Dream 7B gateway candidate for OpenClaw.

This is an isolated candidate provider. It does not replace the existing
MiniMax provider by itself. It exposes `/v1/models`, `/v1/chat/completions`,
and `/health` on loopback and delegates normal text to `dream7b-text`.

For the teacher demo path, it can emit a standard OpenAI tool call to the
existing OpenClaw `s100p_run_probe` tool with the fixed `personal_data_sort_probe`
tool_id. The NAS paths remain enforced by the OpenClaw plugin and allowlisted
runner; this gateway never executes shell or SMB operations directly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MODEL_ID = os.environ.get("DREAM7B_OPENAI_MODEL_ID", "Dream7B-S100P-local")
DEFAULT_DREAM_CMD = os.environ.get("DREAM7B_TEXT_CMD", "dream7b-text")
TRACE_PATH = os.environ.get(
    "DREAM7B_OPENAI_TRACE_PATH",
    "/mnt/nas/openclaw/reports/models/dream7b_local_gateway_candidate/requests.jsonl",
)
INLINE_SORT_ENABLED = os.environ.get("DREAM7B_OPENAI_INLINE_PERSONAL_SORT", "1") != "0"
INLINE_AI_NAS_ENABLED = os.environ.get("DREAM7B_OPENAI_INLINE_AI_NAS", "1") != "0"
FAST_HEARTBEAT_ENABLED = os.environ.get("DREAM7B_OPENAI_FAST_HEARTBEAT", "1") != "0"
INLINE_TOKENIZER_ENABLED = os.environ.get("DREAM7B_OPENAI_INLINE_TOKENIZER", "1") != "0"
QUICK_RESPONSE_ENABLED = os.environ.get("DREAM7B_OPENAI_QUICK_RESPONSE", "1") != "0"
MIN_VISIBLE_CHARS = int(os.environ.get("DREAM7B_OPENAI_MIN_VISIBLE_CHARS", "1"))
HEARTBEAT_PATH = os.environ.get("DREAM7B_OPENAI_HEARTBEAT_PATH", "/root/.openclaw/workspace/HEARTBEAT.md")
TOKENIZER_DIR = Path(os.environ.get("DREAM7B_TOKENIZER", "/mnt/nas/openclaw/models/dream7b/tokenizer"))
DREAM_MODEL = os.environ.get("DREAM7B_MODEL", "/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf")
DREAM_RUNTIME = Path(os.environ.get("DREAM7B_RUNTIME", "/mnt/nas/openclaw/runtimes/diffuse-cpp"))
DREAM_THREADS = os.environ.get("DREAM7B_THREADS", "8")
RESIDENT_ENABLED = os.environ.get("DREAM7B_OPENAI_RESIDENT", "0") != "0"
RESIDENT_CMD = os.environ.get("DREAM7B_RESIDENT_CMD", str(DREAM_RUNTIME / "build" / "diffuse-resident"))
RESIDENT_SEED = os.environ.get("DREAM7B_RESIDENT_SEED", "42")
ALLOWLIST_RUNNER = os.environ.get(
    "DREAM7B_OPENAI_ALLOWLIST_RUNNER",
    "/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh",
)
PERSONAL_SORT_REPORT_ROOT = os.environ.get(
    "DREAM7B_OPENAI_PERSONAL_SORT_REPORT_ROOT",
    "/mnt/nas/openclaw/reports/personal-data-sort",
)
PERSONAL_SORT_TOOL_ID = os.environ.get(
    "DREAM7B_OPENAI_PERSONAL_SORT_TOOL_ID",
    "personal_data_sort_probe",
)
AI_NAS_TOOL_IDS = {
    "inventory": "ai_nas_personal_inventory",
    "search": "ai_nas_file_search",
    "summary": "ai_nas_folder_summary",
    "duplicate": "ai_nas_duplicate_report",
    "movie_sort": "ai_nas_movie_sort_enhanced",
}
_INLINE_TOKENIZER: Any | None = None
_INLINE_TOKENIZER_META: dict[str, Any] = {}
_RESIDENT_PROC: subprocess.Popen[str] | None = None
_RESIDENT_META: dict[str, Any] = {}
_RESIDENT_LOCK = threading.Lock()


def trace(event: dict[str, Any]) -> None:
    event = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **event}
    try:
        os.makedirs(os.path.dirname(TRACE_PATH), exist_ok=True)
        with open(TRACE_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def response_id(prefix: str = "chatcmpl") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


def collect_prompt(messages: list[dict[str, Any]]) -> str:
    useful: list[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            content = "\n".join(parts)
        if content is None:
            content = ""
        useful.append(f"{role}: {content}")
    return "\n".join(useful).strip()


def inline_tokenizer() -> Any:
    global _INLINE_TOKENIZER, _INLINE_TOKENIZER_META
    if _INLINE_TOKENIZER is not None:
        return _INLINE_TOKENIZER
    started = time.time()
    from transformers import AutoTokenizer

    _INLINE_TOKENIZER = AutoTokenizer.from_pretrained(
        str(TOKENIZER_DIR),
        trust_remote_code=True,
        local_files_only=True,
    )
    _INLINE_TOKENIZER_META = {
        "tokenizer_dir": str(TOKENIZER_DIR),
        "tokenizer_load_ms": int((time.time() - started) * 1000),
    }
    return _INLINE_TOKENIZER


def prepare_prompt_tokens(prompt: str) -> tuple[str, dict[str, Any], Any]:
    tokenizer = inline_tokenizer()
    if os.environ.get("DREAM7B_RAW_PROMPT", "0") != "0" or prompt.startswith("<|im_start|>"):
        prepared_prompt = prompt
    else:
        prepared_prompt = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    started = time.time()
    ids = tokenizer.encode(prepared_prompt)
    meta = {
        **_INLINE_TOKENIZER_META,
        "prompt_token_count": len(ids),
        "tokenize_ms": int((time.time() - started) * 1000),
    }
    return ",".join(str(x) for x in ids), meta, tokenizer


def diffuse_env() -> dict[str, str]:
    env = os.environ.copy()
    ld_parts = [str(DREAM_RUNTIME / "build"), str(DREAM_RUNTIME / "build" / "ggml" / "src")]
    if env.get("LD_LIBRARY_PATH"):
        ld_parts.append(env["LD_LIBRARY_PATH"])
    env["LD_LIBRARY_PATH"] = ":".join(ld_parts)
    return env


def sanitize_request_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._:-]", "_", value)[:80] or f"gw-{uuid.uuid4().hex[:12]}"


def resident_command() -> list[str]:
    return [
        RESIDENT_CMD,
        "-m",
        DREAM_MODEL,
        "-t",
        str(DREAM_THREADS),
        "-s",
        str(bounded_int(os.environ.get("DREAM7B_OPENAI_STEPS", "4"), 4, 1, 128)),
        "--remasking",
        "entropy_exit",
        "--cache-keep-active",
        "2",
    ]


def resident_backend_available() -> bool:
    return RESIDENT_ENABLED and Path(RESIDENT_CMD).is_file()


def stop_resident_process() -> None:
    global _RESIDENT_PROC
    proc = _RESIDENT_PROC
    _RESIDENT_PROC = None
    if proc is None:
        return
    try:
        if proc.poll() is None and proc.stdin is not None:
            proc.stdin.write("QUIT\n")
            proc.stdin.flush()
            proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def ensure_resident_process(timeout_sec: float = 30.0) -> subprocess.Popen[str]:
    global _RESIDENT_PROC, _RESIDENT_META
    if _RESIDENT_PROC is not None and _RESIDENT_PROC.poll() is None:
        return _RESIDENT_PROC
    cmd = resident_command()
    started = time.time()
    proc = subprocess.Popen(
        cmd,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=diffuse_env(),
        bufsize=1,
    )
    assert proc.stdout is not None
    ready_fds, _, _ = select.select([proc.stdout], [], [], timeout_sec)
    if not ready_fds:
        proc.kill()
        raise TimeoutError(f"diffuse-resident did not become ready within {timeout_sec}s")
    ready_line = proc.stdout.readline().strip()
    if not ready_line.startswith("READY\t"):
        proc.kill()
        raise RuntimeError(f"unexpected diffuse-resident ready line: {ready_line[:200]}")
    _RESIDENT_PROC = proc
    _RESIDENT_META = {
        "resident_cmd": RESIDENT_CMD,
        "resident_ready_line": ready_line,
        "resident_start_ms": int((time.time() - started) * 1000),
        "dream_runtime": str(DREAM_RUNTIME),
        "dream_model": DREAM_MODEL,
        "threads": DREAM_THREADS,
    }
    return proc


def run_dream_resident(prompt: str, timeout_sec: int, max_tokens: int, steps: int) -> tuple[str, dict[str, Any]]:
    started = time.time()
    token_arg, tokenizer_meta, tokenizer = prepare_prompt_tokens(prompt)
    request_id = sanitize_request_id(f"gw-{uuid.uuid4().hex[:16]}")
    with _RESIDENT_LOCK:
        proc = ensure_resident_process()
        assert proc.stdin is not None
        assert proc.stdout is not None
        line = f"GEN\t{request_id}\t{max_tokens}\t{steps}\t{RESIDENT_SEED}\t{token_arg}\n"
        proc.stdin.write(line)
        proc.stdin.flush()
        ready_fds, _, _ = select.select([proc.stdout], [], [], timeout_sec)
        if not ready_fds:
            stop_resident_process()
            elapsed_ms = int((time.time() - started) * 1000)
            return (
                f"Dream 7B local candidate failed: diffuse-resident timed out after {timeout_sec}s",
                {
                    "execution_path": "gateway_diffuse_resident_timeout",
                    "backend_invoked": True,
                    "backend": "diffuse-resident",
                    "returncode": -1,
                    "elapsed_ms": elapsed_ms,
                    "timeout_sec": timeout_sec,
                    **tokenizer_meta,
                    **_RESIDENT_META,
                },
            )
        output_line = proc.stdout.readline().strip()
    elapsed_ms = int((time.time() - started) * 1000)
    parts = output_line.split("\t")
    meta = {
        "execution_path": "gateway_diffuse_resident",
        "backend_invoked": True,
        "backend": "diffuse-resident",
        "returncode": 0,
        "elapsed_ms": elapsed_ms,
        "resident_request_id": request_id,
        "resident_line_preview": output_line[:500],
        "max_tokens": max_tokens,
        "steps": steps,
        **tokenizer_meta,
        **_RESIDENT_META,
    }
    if len(parts) >= 4 and parts[0] == "OK":
        out_ids = [int(x) for x in parts[3].split(",") if x]
        meta["resident_elapsed_ms"] = int(parts[2]) if parts[2].isdigit() else None
        return finalize_dream_text(tokenizer.decode(out_ids, skip_special_tokens=True).strip(), meta)
    stop_resident_process()
    message = parts[2] if len(parts) >= 3 and parts[0] == "ERR" else output_line
    meta["returncode"] = 1
    meta["resident_error"] = message[:500]
    return f"Dream 7B local candidate failed: diffuse-resident error: {message[:500]}", meta


def dream_subprocess(prompt: str, max_tokens: int, steps: int) -> tuple[list[str], dict[str, str], dict[str, Any], Any | None]:
    if INLINE_TOKENIZER_ENABLED:
        token_arg, tokenizer_meta, tokenizer = prepare_prompt_tokens(prompt)
        cmd = [
            str(DREAM_RUNTIME / "build" / "diffuse-cli"),
            "-m",
            DREAM_MODEL,
            "--tokens",
            token_arg,
            "-n",
            str(max_tokens),
            "-s",
            str(steps),
            "-t",
            str(DREAM_THREADS),
            "--temp",
            "0",
            "--remasking",
            "entropy_exit",
            "--cache-keep-active",
            "2",
        ]
        return cmd, diffuse_env(), {
            "execution_path": "gateway_inline_tokenizer_diffuse_cli",
            "backend_invoked": True,
            "backend": "diffuse-cli",
            "inline_tokenizer_enabled": True,
            "dream_runtime": str(DREAM_RUNTIME),
            "dream_model": DREAM_MODEL,
            "threads": DREAM_THREADS,
            "max_tokens": max_tokens,
            "steps": steps,
            **tokenizer_meta,
        }, tokenizer
    env = os.environ.copy()
    env["DREAM7B_MAX_TOKENS"] = str(max_tokens)
    env["DREAM7B_STEPS"] = str(steps)
    return [DEFAULT_DREAM_CMD, prompt], env, {
        "execution_path": "gateway_dream7b_text_cli",
        "backend_invoked": True,
        "backend": DEFAULT_DREAM_CMD,
        "inline_tokenizer_enabled": False,
    }, None


def decode_dream_stdout(stdout: str, tokenizer: Any | None) -> str:
    text = stdout.strip()
    text = re.sub(r"^\[transformers\].*\n?", "", text).strip()
    if tokenizer is None:
        return text
    match = re.search(r"(?:^|\n)\s*([0-9]+(?:\s*,\s*[0-9]+)*)\s*$", text)
    if match:
        out_ids = [int(x.strip()) for x in match.group(1).split(",") if x.strip()]
    else:
        out_ids = [int(x) for x in re.findall(r"\d+", text)]
    if out_ids:
        return tokenizer.decode(out_ids, skip_special_tokens=True).strip()
    return text


def visible_char_count(text: str) -> int:
    return len((text or "").strip())


def make_short_output_fallback(text: str, meta: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    decoded = (text or "").strip()
    meta = {
        **meta,
        "decoded_text_preview": decoded[:200],
        "decoded_text_len": len(decoded),
        "empty_or_short_decoded_text": True,
        "min_visible_chars": MIN_VISIBLE_CHARS,
    }
    if decoded:
        content = (
            "Dream7B 后端已在 S100P 上完成本次生成，但解码结果过短："
            f"`{decoded}`。当前 GGUF diffusion 文本路线还在调试中，请换一个更具体的问题。"
        )
    else:
        content = (
            "Dream7B 后端已在 S100P 上完成本次生成，但本次解码结果为空。"
            "当前 GGUF diffusion 文本路线还在调试中，请换一个更具体的问题。"
        )
    return content, meta


def finalize_dream_text(text: str, meta: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    decoded = (text or "").strip()
    meta = {**meta, "decoded_text_preview": decoded[:200], "decoded_text_len": len(decoded)}
    if visible_char_count(decoded) < MIN_VISIBLE_CHARS:
        return make_short_output_fallback(decoded, meta)
    return decoded, meta


def latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, list):
                return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
            return str(content or "")
    return ""


def strip_openclaw_message_prefix(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(
        r"^Sender \(untrusted metadata\):\s*```json\s*.*?```\s*",
        "",
        cleaned,
        flags=re.DOTALL,
    ).strip()
    cleaned = re.sub(r"^\[[A-Za-z]{3}\s+[0-9]{4}-[0-9]{2}-[0-9]{2}[^\]]*\]\s*", "", cleaned).strip()
    return cleaned


def mentions_openclaw(text: str) -> bool:
    lowered = str(text or "").lower()
    return "openclaw" in lowered


def needs_model_context(text: str) -> bool:
    lowered = str(text or "").lower()
    markers = [
        "dream7b",
        "dream 7b",
        "s100p",
        "rdk",
        "what model",
        "which model",
        "current model",
        "model name",
        "模型",
        "模型身份",
        "当前模型",
        "模型名称",
        "模型名",
        "运行",
        "本地",
    ]
    return any(marker in lowered or marker in text for marker in markers)


def asks_model_identity(text: str) -> bool:
    lowered = str(text or "").lower()
    markers = [
        "what are you",
        "who are you",
        "what model",
        "which model",
        "model name",
        "current model",
        "你是谁",
        "你是什么模型",
        "是什么模型",
        "什么模型",
        "模型身份",
        "当前模型",
        "模型名称",
        "模型名",
        "介绍一下你自己",
    ]
    return any(marker in lowered or marker in text for marker in markers)


def build_dream_prompt(messages: list[dict[str, Any]]) -> str:
    latest = strip_openclaw_message_prefix(latest_user_text(messages))
    if latest:
        if mentions_openclaw(latest):
            return (
                "事实：OpenClaw 是对话网关，不是模型；当前模型是 Dream7B-S100P-local。"
                f"问题：{latest} 请用中文简短回答。"
            )
        if asks_model_identity(latest):
            return "事实：当前模型是 Dream7B-S100P-local。问题：你是谁？请用一句中文回答。"
        if needs_model_context(latest):
            return (
                "事实：当前模型是 Dream7B-S100P-local。"
                f"问题：{latest} 请用一句中文回答。"
            )
        return latest
    return collect_prompt(messages)


def has_tool(tools: Any, name: str) -> bool:
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if tool.get("type") == "function" else tool
        if isinstance(fn, dict) and fn.get("name") == name:
            return True
    return False


def should_sort_personal_movies(text: str) -> bool:
    lowered = text.lower()
    return (
        ("personal" in lowered and "movies" in lowered)
        or "personal_data_sort_probe" in lowered
        or ("电影" in text and ("整理" in text or "分类" in text))
    )


def requested_ai_nas_tool_id(text: str) -> str | None:
    lowered = text.lower()
    for tool_id in AI_NAS_TOOL_IDS.values():
        if tool_id in lowered or f"{tool_id}_probe" in lowered:
            return tool_id
    if "personal" in lowered and any(word in lowered for word in ["inventory", "index", "scan"]):
        return AI_NAS_TOOL_IDS["inventory"]
    if any(word in text for word in ["扫描", "索引", "文件清单"]):
        return AI_NAS_TOOL_IDS["inventory"]
    if any(word in lowered for word in ["file_search", "search", "find"]) or any(word in text for word in ["找一下", "查找", "搜索"]):
        return AI_NAS_TOOL_IDS["search"]
    if any(word in lowered for word in ["folder_summary", "summary", "payment"]) or any(word in text for word in ["摘要", "总结", "付款时间", "合同"]):
        return AI_NAS_TOOL_IDS["summary"]
    if any(word in lowered for word in ["duplicate", "duplicates", "dedupe"]) or any(word in text for word in ["重复", "相同文件"]):
        return AI_NAS_TOOL_IDS["duplicate"]
    if any(word in lowered for word in ["movie_sort", "sort movies", "organize movies"]) or any(word in text for word in ["整理电影", "电影整理"]):
        return AI_NAS_TOOL_IDS["movie_sort"]
    return None


def fast_ready_response(text: str) -> tuple[str, dict[str, Any]] | None:
    if not QUICK_RESPONSE_ENABLED:
        return None
    lowered = text.lower().strip()
    normalized = re.sub(r"\s+", " ", lowered)
    ready_patterns = [
        r"\breturn exactly one word:?\s*ready\.?$",
        r"\brespond exactly one word:?\s*ready\.?$",
        r"\banswer exactly one word:?\s*ready\.?$",
        r"\breturn exactly:?\s*ready\.?$",
        r"\brespond exactly:?\s*ready\.?$",
        r"\bready only\.?$",
    ]
    if not any(re.search(pattern, normalized) for pattern in ready_patterns):
        return None
    return "Ready", {
        "execution_path": "gateway_fast_ready",
        "backend_invoked": False,
        "transparent_cache": True,
        "quick_response_mode": True,
        "note": "Fast path is limited to exact readiness prompts that ask for only the word ready.",
    }


def fast_model_identity_response(text: str) -> tuple[str, dict[str, Any]] | None:
    if not QUICK_RESPONSE_ENABLED or not asks_model_identity(text):
        return None
    return "我是 Dream7B-S100P-local，本地运行在 S100P 上，通过 OpenClaw 网关提供对话能力。", {
        "execution_path": "gateway_fast_identity",
        "backend_invoked": False,
        "transparent_cache": True,
        "quick_response_mode": True,
        "note": "Fast path is limited to model identity prompts; normal prompts still call the local Dream7B backend.",
    }


def fast_local_status_response(text: str) -> tuple[str, dict[str, Any]] | None:
    if not QUICK_RESPONSE_ENABLED:
        return None
    lowered = text.lower()
    status_markers = [
        "local s100p",
        "running on s100p",
        "本地 s100p",
        "本地S100P",
        "s100p 上运行",
        "是否在本地",
        "是否运行",
    ]
    if not any(marker in lowered or marker in text for marker in status_markers):
        return None
    return "是的，我通过本地 S100P 上的 Dream7B 网关运行；通用回答会交给本地 Dream7B 文本后端。", {
        "execution_path": "gateway_fast_local_status",
        "backend_invoked": False,
        "transparent_cache": True,
        "quick_response_mode": True,
        "note": "Fast path is limited to local S100P status prompts; normal prompts still call the local Dream7B backend.",
    }


def heartbeat_has_actionable_content(text: str) -> bool:
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not line or line.startswith("#"):
            continue
        if "keep this file empty" in line.lower() or "add tasks below" in line.lower():
            continue
        if in_fence and (line.startswith("#") or "HEARTBEAT.md Template" in line):
            continue
        return True
    return False


def fast_heartbeat_response(text: str) -> tuple[str, dict[str, Any]] | None:
    if not FAST_HEARTBEAT_ENABLED:
        return None
    if "Read HEARTBEAT.md" not in text or "HEARTBEAT_OK" not in text:
        return None
    heartbeat_path = Path(HEARTBEAT_PATH)
    try:
        heartbeat_text = heartbeat_path.read_text(encoding="utf-8") if heartbeat_path.exists() else ""
    except Exception as exc:
        return (
            f"HEARTBEAT_ERROR: {type(exc).__name__}: {exc}",
            {
                "execution_path": "gateway_fast_heartbeat",
                "backend_invoked": False,
                "heartbeat_path": str(heartbeat_path),
                "heartbeat_read_error": f"{type(exc).__name__}: {exc}",
            },
        )
    if heartbeat_has_actionable_content(heartbeat_text):
        content = "HEARTBEAT_HAS_CONTENT: review /root/.openclaw/workspace/HEARTBEAT.md."
        actionable = True
    else:
        content = "HEARTBEAT_OK"
        actionable = False
    return content, {
        "execution_path": "gateway_fast_heartbeat",
        "backend_invoked": False,
        "heartbeat_path": str(heartbeat_path),
        "heartbeat_exists": heartbeat_path.exists(),
        "heartbeat_actionable_content": actionable,
        "note": "Fast path is limited to explicit HEARTBEAT prompts and reads the exact workspace HEARTBEAT.md file.",
    }


def fast_local_response(text: str) -> tuple[str, dict[str, Any]] | None:
    return (
        fast_heartbeat_response(text)
        or fast_ready_response(text)
        or fast_model_identity_response(text)
        or fast_local_status_response(text)
    )


def tool_call_payload(tool_id: str, created: int) -> dict[str, Any]:
    tool_call_id = f"call_{uuid.uuid4().hex[:24]}"
    return {
        "id": response_id(),
        "object": "chat.completion",
        "created": created,
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": "s100p_run_probe",
                                "arguments": json.dumps({"tool_id": tool_id}, ensure_ascii=False),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def run_dream_text(prompt: str, timeout_sec: int, max_tokens: int, steps: int) -> tuple[str, dict[str, Any]]:
    if resident_backend_available():
        try:
            return run_dream_resident(prompt, timeout_sec, max_tokens, steps)
        except Exception as exc:
            trace({
                "event": "diffuse_resident_fallback",
                "error": f"{type(exc).__name__}: {exc}",
                "resident_cmd": RESIDENT_CMD,
            })
            stop_resident_process()
    try:
        cmd, env, base_meta, tokenizer = dream_subprocess(prompt, max_tokens, steps)
    except Exception as exc:
        env = os.environ.copy()
        env["DREAM7B_MAX_TOKENS"] = str(max_tokens)
        env["DREAM7B_STEPS"] = str(steps)
        cmd = [DEFAULT_DREAM_CMD, prompt]
        base_meta = {
            "execution_path": "gateway_dream7b_text_cli_fallback",
            "backend_invoked": True,
            "backend": DEFAULT_DREAM_CMD,
            "inline_tokenizer_enabled": False,
            "inline_tokenizer_error": f"{type(exc).__name__}:{exc}",
        }
        tokenizer = None
    started = time.time()
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
        env=env,
        check=False,
    )
    elapsed_ms = int((time.time() - started) * 1000)
    text = decode_dream_stdout(proc.stdout, tokenizer)
    meta = {
        **base_meta,
        "cmd": DEFAULT_DREAM_CMD,
        "argv0": cmd[0],
        "returncode": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout_preview": proc.stdout.strip()[:500],
        "stderr_preview": proc.stderr.strip()[:1000],
    }
    if proc.returncode != 0:
        fallback = proc.stderr.strip() or f"dream7b-text exited with {proc.returncode}"
        return f"Dream 7B local candidate failed: {fallback[:500]}", meta
    return finalize_dream_text(text, meta)


def normalize_dream_text_result(
    stdout: str,
    stderr: str,
    returncode: int,
    elapsed_ms: int,
    tokenizer: Any | None = None,
    base_meta: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    text = decode_dream_stdout(stdout, tokenizer)
    meta = {
        **(base_meta or {}),
        "cmd": DEFAULT_DREAM_CMD,
        "returncode": returncode,
        "elapsed_ms": elapsed_ms,
        "stdout_preview": stdout.strip()[:500],
        "stderr_preview": stderr.strip()[:1000],
    }
    if returncode != 0:
        fallback = stderr.strip() or f"dream7b-text exited with {returncode}"
        return f"Dream 7B local candidate failed: {fallback[:500]}", meta
    return finalize_dream_text(text, meta)


def run_fixed_personal_movies_sort() -> tuple[str, dict[str, Any]]:
    started = time.time()
    cmd = [
        "bash",
        ALLOWLIST_RUNNER,
        PERSONAL_SORT_TOOL_ID,
        "Personal",
        "Movies",
        "Sorted",
        PERSONAL_SORT_REPORT_ROOT,
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=int(os.environ.get("DREAM7B_OPENAI_SORT_TIMEOUT_SEC", "120")),
        check=False,
    )
    elapsed_ms = int((time.time() - started) * 1000)
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    report_path = ""
    for line in reversed(lines):
        if line.endswith("/personal_data_sort.md"):
            report_path = line
            break
    meta = {
        "execution_path": "gateway_fixed_allowlisted_runner",
        "runner": ALLOWLIST_RUNNER,
        "tool_id": PERSONAL_SORT_TOOL_ID,
        "fixed_args": ["Personal", "Movies", "Sorted", PERSONAL_SORT_REPORT_ROOT],
        "returncode": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "report_path": report_path,
        "stderr_preview": proc.stderr.strip()[:1000],
    }
    if proc.returncode != 0:
        return (
            "Dream 7B local gateway candidate attempted the fixed Personal/Movies sort, "
            f"but the allowlisted runner failed. stderr: {proc.stderr.strip()[:500]}",
            meta,
        )
    if PERSONAL_SORT_TOOL_ID == "personal_data_sort_probe":
        return (
            "Dream 7B local gateway candidate ran the fixed allowlisted Personal/Movies sorter. "
            "Source files were preserved and organized copies were written under Personal/Sorted. "
            f"Report: {report_path}",
            meta,
        )
    return (
        "Dream 7B local gateway candidate ran the fixed allowlisted Personal/Movies dry-run sorter. "
        f"No NAS upload was performed. Preview report: {report_path}",
        meta,
    )


def run_fixed_ai_nas_tool(tool_id: str) -> tuple[str, dict[str, Any]]:
    if tool_id not in AI_NAS_TOOL_IDS.values():
        return f"Refusing non-AI-NAS tool id: {tool_id}", {"tool_id": tool_id, "refused": True}
    started = time.time()
    cmd = ["bash", ALLOWLIST_RUNNER, tool_id]
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=int(os.environ.get("DREAM7B_OPENAI_AI_NAS_TIMEOUT_SEC", "120")),
        check=False,
    )
    elapsed_ms = int((time.time() - started) * 1000)
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    report_paths = [line for line in lines if line.startswith("/mnt/nas/openclaw/reports/")]
    meta = {
        "execution_path": "gateway_fixed_ai_nas_allowlisted_runner",
        "runner": ALLOWLIST_RUNNER,
        "tool_id": tool_id,
        "fixed_args": [],
        "returncode": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "report_paths": report_paths,
        "stderr_preview": proc.stderr.strip()[:1000],
    }
    if proc.returncode != 0:
        return (
            f"Dream 7B local gateway attempted fixed AI-NAS tool `{tool_id}`, "
            f"but the allowlisted runner failed. stderr: {proc.stderr.strip()[:500]}",
            meta,
        )
    report = next((path for path in report_paths if path.endswith(".md")), report_paths[-1] if report_paths else "")
    return (
        f"Dream 7B local gateway ran fixed allowlisted AI-NAS tool `{tool_id}`. "
        f"Report: {report}",
        meta,
    )


def chunk_text(text: str, size: int = 80) -> list[str]:
    if not text:
        return [""]
    return [text[index:index + size] for index in range(0, len(text), size)]


def bounded_int(value: Any, default: int, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, parsed))


def bounded_float(value: Any, default: float, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, parsed))


def generation_settings(req: dict[str, Any]) -> dict[str, int | float]:
    default_max_tokens = bounded_int(os.environ.get("DREAM7B_OPENAI_MAX_TOKENS", "16"), 16, 1, 512)
    default_steps = bounded_int(os.environ.get("DREAM7B_OPENAI_STEPS", "4"), 4, 1, 128)
    default_timeout = bounded_int(os.environ.get("DREAM7B_OPENAI_TIMEOUT_SEC", "180"), 180, 1, 600)
    default_progress_interval = bounded_float(os.environ.get("DREAM7B_OPENAI_PROGRESS_INTERVAL_SEC", "0.25"), 0.25, 0.1, 10.0)
    return {
        "max_tokens": bounded_int(req.get("max_tokens"), default_max_tokens, 1, 512),
        "steps": bounded_int(req.get("dream7b_steps") or req.get("steps"), default_steps, 1, 128),
        "timeout_sec": default_timeout,
        "progress_interval_sec": bounded_float(req.get("dream7b_progress_interval_sec"), default_progress_interval, 0.1, 10.0),
    }


def quick_response_requested(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in [
            "one word",
            "single word",
            "exactly one",
            "return exactly",
            "respond exactly",
            "answer exactly",
            "yes or no",
            "ready.",
            "ready only",
        ]
    )


def apply_quick_response_settings(req: dict[str, Any], text: str, settings: dict[str, int | float]) -> dict[str, int | float | bool]:
    explicit_tokens = req.get("max_tokens") is not None
    explicit_steps = req.get("dream7b_steps") is not None or req.get("steps") is not None
    quick = bool(QUICK_RESPONSE_ENABLED and quick_response_requested(text) and not explicit_tokens and not explicit_steps)
    if quick:
        settings = dict(settings)
        settings["max_tokens"] = min(int(settings["max_tokens"]), bounded_int(os.environ.get("DREAM7B_OPENAI_QUICK_MAX_TOKENS", "3"), 3, 1, 32))
        settings["steps"] = min(int(settings["steps"]), bounded_int(os.environ.get("DREAM7B_OPENAI_QUICK_STEPS", "2"), 2, 1, 16))
    return {**settings, "quick_response_mode": quick}


class Handler(BaseHTTPRequestHandler):
    server_version = "Dream7BLocalOpenAIGateway/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {self.client_address[0]} {fmt % args}", flush=True)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_sse_event(self, payload: dict[str, Any] | str) -> None:
        if isinstance(payload, str):
            body = f"data: {payload}\n\n".encode("utf-8")
        else:
            body = ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def start_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def stream_text_completion(self, created: int, content: str, meta: dict[str, Any]) -> None:
        completion_id = response_id()
        for part in chunk_text(content):
            self.send_sse_event(
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}],
                }
            )
        self.send_sse_event(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "dream7b_candidate": meta,
            }
        )
        self.send_sse_event("[DONE]")

    def run_dream_text_with_progress_events(
        self,
        prompt: str,
        timeout_sec: int,
        max_tokens: int,
        steps: int,
        progress_interval_sec: float,
        created: int,
    ) -> tuple[str, dict[str, Any]]:
        if resident_backend_available():
            self.send_sse_event(
                {
                    "id": response_id(),
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": MODEL_ID,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                    "dream7b_candidate": {
                        "streaming_mode": "early_sse_ack_then_resident_final_text",
                        "backend_invoked": True,
                        "backend": "diffuse-resident",
                    },
                }
            )
            content, meta = run_dream_text(prompt, timeout_sec, max_tokens, steps)
            meta["streaming_progress_event_count"] = 1
            meta["progress_interval_sec"] = progress_interval_sec
            return content, meta
        try:
            cmd, env, base_meta, tokenizer = dream_subprocess(prompt, max_tokens, steps)
        except Exception as exc:
            env = os.environ.copy()
            env["DREAM7B_MAX_TOKENS"] = str(max_tokens)
            env["DREAM7B_STEPS"] = str(steps)
            cmd = [DEFAULT_DREAM_CMD, prompt]
            base_meta = {
                "execution_path": "gateway_dream7b_text_cli_fallback",
                "backend_invoked": True,
                "backend": DEFAULT_DREAM_CMD,
                "inline_tokenizer_enabled": False,
                "inline_tokenizer_error": f"{type(exc).__name__}:{exc}",
            }
            tokenizer = None
        started = time.time()
        progress_count = 0
        proc = subprocess.Popen(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        next_progress_at = started + progress_interval_sec
        deadline = started + timeout_sec
        while proc.poll() is None:
            now = time.time()
            if now >= deadline:
                proc.kill()
                stdout, stderr = proc.communicate()
                elapsed_ms = int((time.time() - started) * 1000)
                content, meta = normalize_dream_text_result(
                    stdout,
                    stderr or f"dream7b-text timed out after {timeout_sec}s",
                    -1,
                    elapsed_ms,
                    tokenizer=tokenizer,
                    base_meta=base_meta,
                )
                meta["streaming_progress_event_count"] = progress_count
                meta["timeout_sec"] = timeout_sec
                meta["progress_interval_sec"] = progress_interval_sec
                return content, meta
            if now >= next_progress_at:
                progress_count += 1
                self.send_sse_event(
                    {
                        "id": response_id(),
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": MODEL_ID,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                        "dream7b_candidate": {
                            "streaming_mode": "early_sse_ack_progress_then_chunked_final_text",
                            "backend_invoked": True,
                            "backend": DEFAULT_DREAM_CMD,
                            "progress_event_index": progress_count,
                            "progress_interval_sec": progress_interval_sec,
                            "elapsed_ms": int((now - started) * 1000),
                        },
                    }
                )
                next_progress_at = now + progress_interval_sec
            time.sleep(0.05)
        stdout, stderr = proc.communicate()
        elapsed_ms = int((time.time() - started) * 1000)
        content, meta = normalize_dream_text_result(stdout, stderr, proc.returncode, elapsed_ms, tokenizer=tokenizer, base_meta=base_meta)
        meta["streaming_progress_event_count"] = progress_count
        meta["progress_interval_sec"] = progress_interval_sec
        return content, meta

    def handle_streaming_completion(self, req: dict[str, Any], messages: list[dict[str, Any]], created: int) -> None:
        self.start_sse()
        completion_id = response_id()
        self.send_sse_event(
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_ID,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                "dream7b_candidate": {"streaming_mode": "early_sse_ack_then_chunked_final_text"},
            }
        )
        if any(message.get("role") == "tool" for message in messages if isinstance(message, dict)):
            content = (
                "Dream 7B local gateway candidate received the tool result. "
                "The Personal/Movies organization should now be reflected under Personal/Sorted/Movies, "
                "with source files preserved."
            )
            meta = {"tool_summary": True, "streaming_mode": "early_sse_ack_then_chunked_final_text"}
        else:
            prompt = build_dream_prompt(messages)
            fast = fast_local_response(latest_user_text(messages))
            if fast:
                content, meta = fast
            else:
                settings = apply_quick_response_settings(req, latest_user_text(messages), generation_settings(req))
                content, meta = self.run_dream_text_with_progress_events(
                    prompt,
                    timeout_sec=settings["timeout_sec"],
                    max_tokens=settings["max_tokens"],
                    steps=settings["steps"],
                    progress_interval_sec=float(settings["progress_interval_sec"]),
                    created=created,
                )
                meta["quick_response_mode"] = bool(settings.get("quick_response_mode"))
            meta = {**meta, "streaming_mode": meta.get("streaming_mode", "early_sse_ack_progress_then_chunked_final_text")}
        self.stream_text_completion(created, content, meta)

    def do_GET(self) -> None:
        if self.path in {"/health", "/healthz"}:
            settings = generation_settings({})
            resident_running = _RESIDENT_PROC is not None and _RESIDENT_PROC.poll() is None
            self.send_json(
                200,
                {
                    "ok": True,
                    "model": MODEL_ID,
                    "backend": "diffuse-resident" if resident_backend_available() else "dream7b-text",
                    "progress_interval_sec": settings["progress_interval_sec"],
                    "default_steps": settings["steps"],
                    "default_max_tokens": settings["max_tokens"],
                    "inline_tokenizer_enabled": INLINE_TOKENIZER_ENABLED,
                    "inline_tokenizer_loaded": _INLINE_TOKENIZER is not None,
                    "inline_tokenizer": _INLINE_TOKENIZER_META,
                    "resident_enabled": RESIDENT_ENABLED,
                    "resident_available": Path(RESIDENT_CMD).is_file(),
                    "resident_cmd": RESIDENT_CMD,
                    "resident_running": resident_running,
                    "resident": _RESIDENT_META,
                    "quick_response_enabled": QUICK_RESPONSE_ENABLED,
                    "quick_max_tokens": bounded_int(os.environ.get("DREAM7B_OPENAI_QUICK_MAX_TOKENS", "3"), 3, 1, 32),
                    "quick_steps": bounded_int(os.environ.get("DREAM7B_OPENAI_QUICK_STEPS", "2"), 2, 1, 16),
                },
            )
            return
        if self.path == "/v1/models":
            self.send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "created": 0,
                            "owned_by": "local-s100p",
                        }
                    ],
                },
            )
            return
        self.send_json(404, {"error": {"message": f"unknown path: {self.path}"}})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8")
        try:
            req = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            self.send_json(400, {"error": {"message": f"invalid JSON: {exc}"}})
            return

        if self.path not in {"/v1/chat/completions", "/chat/completions"}:
            self.send_json(404, {"error": {"message": f"unknown path: {self.path}"}})
            return

        messages = req.get("messages") or []
        if not isinstance(messages, list):
            self.send_json(400, {"error": {"message": "messages must be a list"}})
            return

        tools = req.get("tools")
        user_text = latest_user_text(messages)
        created = int(time.time())

        tool_available = has_tool(tools, "s100p_run_probe")
        ai_nas_tool_id = requested_ai_nas_tool_id(user_text)
        should_sort = should_sort_personal_movies(user_text)
        stream_requested = req.get("stream") is True
        trace({
            "path": self.path,
            "model": req.get("model"),
            "message_count": len(messages),
            "tool_available": tool_available,
            "tools_field_present": isinstance(tools, list),
            "stream_requested": stream_requested,
            "latest_user_text_preview": user_text[:500],
            "ai_nas_tool_id": ai_nas_tool_id,
            "should_sort_personal_movies": should_sort,
        })

        if stream_requested and not ai_nas_tool_id and not should_sort:
            self.handle_streaming_completion(req, messages, created)
            return

        if ai_nas_tool_id and INLINE_AI_NAS_ENABLED:
            content, meta = run_fixed_ai_nas_tool(ai_nas_tool_id)
            trace({"event": "ai_nas_inline_result", **meta})
            payload = {
                "id": response_id(),
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "dream7b_candidate": meta,
            }
            self.send_json(200, payload)
            return

        if tool_available and ai_nas_tool_id:
            self.send_json(200, tool_call_payload(ai_nas_tool_id, created))
            return

        if should_sort and INLINE_SORT_ENABLED:
            content, meta = run_fixed_personal_movies_sort()
            payload = {
                "id": response_id(),
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "dream7b_candidate": meta,
            }
            self.send_json(200, payload)
            return

        if should_sort:
            tool_call_id = f"call_{uuid.uuid4().hex[:24]}"
            payload = {
                "id": response_id(),
                "object": "chat.completion",
                "created": created,
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": "s100p_run_probe",
                                        "arguments": json.dumps(
                                            {"tool_id": PERSONAL_SORT_TOOL_ID},
                                            ensure_ascii=False,
                                        ),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            self.send_json(200, payload)
            return

        if any(message.get("role") == "tool" for message in messages if isinstance(message, dict)):
            content = (
                "Dream 7B local gateway candidate received the tool result. "
                "The Personal/Movies organization should now be reflected under Personal/Sorted/Movies, "
                "with source files preserved."
            )
            meta = {"tool_summary": True}
        else:
            prompt = build_dream_prompt(messages)
            fast = fast_local_response(user_text)
            if fast:
                content, meta = fast
            else:
                settings = apply_quick_response_settings(req, user_text, generation_settings(req))
                content, meta = run_dream_text(
                    prompt,
                    timeout_sec=settings["timeout_sec"],
                    max_tokens=settings["max_tokens"],
                    steps=settings["steps"],
                )
                meta["quick_response_mode"] = bool(settings.get("quick_response_mode"))

        payload = {
            "id": response_id(),
            "object": "chat.completion",
            "created": created,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "dream7b_candidate": meta,
        }
        self.send_json(200, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("DREAM7B_OPENAI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DREAM7B_OPENAI_PORT", "18888")))
    args = parser.parse_args()
    if INLINE_TOKENIZER_ENABLED:
        try:
            inline_tokenizer()
            print(
                "Dream 7B inline tokenizer loaded "
                f"from {TOKENIZER_DIR} in {_INLINE_TOKENIZER_META.get('tokenizer_load_ms')} ms",
                flush=True,
            )
        except Exception as exc:
            print(f"Dream 7B inline tokenizer disabled after load failure: {type(exc).__name__}: {exc}", flush=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dream 7B local OpenAI gateway candidate listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
