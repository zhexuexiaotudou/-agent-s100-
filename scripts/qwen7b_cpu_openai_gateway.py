#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MODEL_ID = "Qwen2.5-7B-Instruct-S100P-local-cpu"
MAX_REQUEST_BYTES = 1024 * 1024


def normalize_messages(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("messages must be a non-empty list")
    messages: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each message must be an object")
        role = str(item.get("role") or "").strip()
        content = item.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise ValueError("message role/content is invalid")
        if len(content) > 32768:
            raise ValueError("message content is too large")
        messages.append({"role": role, "content": content})
    return messages


class Qwen7BCpuState:
    def __init__(self, model_path: Path, *, n_ctx: int, n_threads: int, n_batch: int) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        from llama_cpp import Llama

        started = time.perf_counter()
        self.model_path = model_path
        self.lock = threading.Lock()
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_threads_batch=n_threads,
            n_batch=n_batch,
            verbose=False,
        )
        self.loaded_ms = round((time.perf_counter() - started) * 1000, 3)

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        requested_model = str(payload.get("model") or MODEL_ID)
        if requested_model not in {MODEL_ID, "Qwen2.5-7B-Instruct-S100P-official"}:
            raise ValueError("model_not_allowed")
        messages = normalize_messages(payload.get("messages"))
        max_tokens = max(1, min(int(payload.get("max_tokens") or 256), 512))
        temperature = max(0.0, min(float(payload.get("temperature") or 0.2), 1.5))
        with self.lock:
            result = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )
        result["model"] = "Qwen2.5-7B-Instruct-S100P-official"
        result.setdefault("id", f"chatcmpl-{uuid.uuid4().hex[:24]}")
        result.setdefault("object", "chat.completion")
        result.setdefault("created", int(time.time()))
        return result


class Handler(BaseHTTPRequestHandler):
    server_version = "DiguaQwen7BCpu/1.0"

    @property
    def state(self) -> Qwen7BCpuState:
        return self.server.state  # type: ignore[attr-defined]

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(HTTPStatus.OK, {
                "ok": True,
                "model": "Qwen2.5-7B-Instruct-S100P-official",
                "backend": "llama-cpp-python-cpu",
                "model_path": str(self.state.model_path),
                "loaded_ms": self.state.loaded_ms,
            })
            return
        if self.path == "/v1/models":
            self.send_json(HTTPStatus.OK, {
                "object": "list",
                "data": [{
                    "id": "Qwen2.5-7B-Instruct-S100P-official",
                    "object": "model",
                    "owned_by": "local-s100p-cpu",
                }],
            })
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": {"type": "not_found", "message": "not found"}})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": {"type": "not_found", "message": "not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("invalid_content_length")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            if payload.get("stream"):
                raise ValueError("streaming_not_supported")
            result = self.state.chat(payload)
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": {"type": "invalid_request", "message": str(exc)}})
            return
        except Exception as exc:
            self.send_json(HTTPStatus.BAD_GATEWAY, {
                "error": {"type": "qwen7b_cpu_runtime_error", "message": f"{type(exc).__name__}: {exc}"}
            })
            return
        self.send_json(HTTPStatus.OK, result)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Loopback OpenAI-compatible Qwen2.5 7B CPU gateway")
    parser.add_argument("--bind", default=os.environ.get("QWEN7B_CPU_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("QWEN7B_CPU_PORT", "18081")))
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(os.environ.get("QWEN7B_CPU_MODEL", "/mnt/nas/openclaw/models/qwen25-7b-gguf/Qwen2.5-7B-Instruct-Q4_K_M.gguf")),
    )
    parser.add_argument("--ctx", type=int, default=int(os.environ.get("QWEN7B_CPU_CTX", "1024")))
    parser.add_argument("--threads", type=int, default=int(os.environ.get("QWEN7B_CPU_THREADS", "8")))
    parser.add_argument("--batch", type=int, default=int(os.environ.get("QWEN7B_CPU_BATCH", "256")))
    args = parser.parse_args()

    state = Qwen7BCpuState(args.model, n_ctx=args.ctx, n_threads=args.threads, n_batch=args.batch)
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.state = state  # type: ignore[attr-defined]
    print(json.dumps({"listening": f"http://{args.bind}:{args.port}", "model": MODEL_ID, "loaded_ms": state.loaded_ms}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
