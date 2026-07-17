#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import subprocess
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_OPENCLAW = "/opt/node-v22.19.0-linux-arm64/bin/openclaw"
DEFAULT_MODEL = "custom-gateway/MiniMax-M2.7"
MAX_REQUEST_BYTES = 128 * 1024
MAX_PROMPT_CHARS = 64 * 1024


def read_bridge_token(path: Path) -> str:
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("bridge token is empty")
    return token


def authorized(header: str | None, expected_token: str) -> bool:
    prefix = "Bearer "
    if not header or not header.startswith(prefix):
        return False
    return hmac.compare_digest(header[len(prefix) :], expected_token)


def prompt_from_messages(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    parts: list[str] = []
    for item in messages:
        if not isinstance(item, dict):
            raise ValueError("each message must be an object")
        role = str(item.get("role") or "user").strip().lower()
        content = item.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            raise ValueError("unsupported message role or content")
        if content.strip():
            parts.append(f"{role}: {content.strip()}")
    prompt = "\n\n".join(parts).strip()
    if not prompt:
        raise ValueError("message content is empty")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("prompt is too large")
    return prompt


def parse_openclaw_output(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(stdout[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("outputs"), list):
            return value
    raise ValueError("OpenClaw returned no model output JSON")


def run_openclaw_model(openclaw: str, model: str, prompt: str, timeout: int) -> tuple[str, dict[str, Any]]:
    completed = subprocess.run(
        [openclaw, "infer", "model", "run", "--gateway", "--model", model, "--prompt", prompt, "--json"],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"OpenClaw model inference failed with exit code {completed.returncode}")
    result = parse_openclaw_output(completed.stdout)
    outputs = result.get("outputs") or []
    first = outputs[0] if outputs and isinstance(outputs[0], dict) else {}
    answer = str(first.get("text") or "").strip()
    if not answer:
        raise ValueError("OpenClaw returned an empty answer")
    return answer, result


class OpenClawBridgeServer(ThreadingHTTPServer):
    token_file: Path
    openclaw: str
    model: str
    inference_timeout: int


class Handler(BaseHTTPRequestHandler):
    server: OpenClawBridgeServer

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self.write_json(HTTPStatus.OK, {"ok": True, "service": "openclaw-cloud-inference-bridge", "model": self.server.model})
            return
        self.write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") not in {"/v1/chat/completions", "/chat/completions"}:
            self.write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        try:
            expected_token = read_bridge_token(self.server.token_file)
        except (OSError, ValueError):
            self.write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "bridge_token_unavailable"})
            return
        if not authorized(self.headers.get("Authorization"), expected_token):
            self.write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        try:
            content_length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self.write_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "invalid_request_size"})
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            prompt = prompt_from_messages(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_request", "detail": str(exc)})
            return
        started = time.perf_counter()
        prompt_hash = hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest()
        try:
            answer, result = run_openclaw_model(self.server.openclaw, self.server.model, prompt, self.server.inference_timeout)
        except subprocess.TimeoutExpired:
            self.write_json(HTTPStatus.GATEWAY_TIMEOUT, {"ok": False, "error": "openclaw_timeout", "prompt_hash": prompt_hash})
            return
        except (OSError, RuntimeError, ValueError) as exc:
            self.write_json(
                HTTPStatus.BAD_GATEWAY,
                {"ok": False, "error": "openclaw_inference_failed", "detail": str(exc), "prompt_hash": prompt_hash},
            )
            return
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        response_model = str(result.get("model") or self.server.model)
        self.write_json(
            HTTPStatus.OK,
            {
                "id": f"openclaw-{prompt_hash[:16]}",
                "object": "chat.completion",
                "model": response_model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {},
                "metadata": {
                    "transport": "openclaw_gateway",
                    "provider": result.get("provider"),
                    "prompt_hash": prompt_hash,
                    "prompt_chars": len(prompt),
                    "elapsed_ms": elapsed_ms,
                },
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loopback-only OpenClaw cloud inference bridge")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--openclaw", default=DEFAULT_OPENCLAW)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not ipaddress.ip_address(args.bind).is_loopback:
        raise SystemExit("refusing non-loopback bind address")
    read_bridge_token(args.token_file)
    server = OpenClawBridgeServer((args.bind, args.port), Handler)
    server.token_file = args.token_file
    server.openclaw = args.openclaw
    server.model = args.model
    server.inference_timeout = max(1, args.timeout)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
