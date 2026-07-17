#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import re
import subprocess
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_OPENCLAW = "/opt/node-v22.19.0-linux-arm64/bin/openclaw"
DEFAULT_MODEL = "custom-gateway/MiniMax-M2.7"
DEFAULT_AGENT = "web-research"
MAX_REQUEST_BYTES = 128 * 1024
MAX_PROMPT_CHARS = 64 * 1024
ALLOWED_WEB_TOOLS = frozenset({"web_search", "web_fetch", "tavily_search", "tavily_extract"})
WEB_RESEARCH_INSTRUCTION = (
    "You are the dedicated public-web research agent for Digua AI-NAS. "
    "You must use web_search, web_fetch, tavily_search, or tavily_extract before answering. "
    "Use only public internet information. Never use shell, exec, local files, NAS, messages, browser automation, "
    "or any other tool. Cite the source URLs in the final answer. If web search fails, say that it failed instead "
    "of answering from memory."
)


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


def parse_openclaw_agent_output(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(stdout[index:])
        except json.JSONDecodeError:
            continue
        result = value.get("result") if isinstance(value, dict) else None
        if isinstance(result, dict) and isinstance(result.get("payloads"), list):
            return value
    raise ValueError("OpenClaw returned no agent output JSON")


def build_web_research_prompt(prompt: str) -> str:
    return f"{WEB_RESEARCH_INSTRUCTION}\n\nPublic research request:\n{prompt}"


def extract_source_urls(answer: str) -> list[str]:
    urls: list[str] = []
    for match in re.findall(r"https?://[^\s<>\]\)\"']+", answer):
        url = match.rstrip(".,;:!?，。；：！？")
        if url and url not in urls:
            urls.append(url)
    return urls[:20]


def run_openclaw_agent(openclaw: str, agent: str, model: str, prompt: str, timeout: int) -> tuple[str, dict[str, Any]]:
    session_id = f"ai-nas-web-{uuid.uuid4().hex}"
    completed = subprocess.run(
        [
            openclaw,
            "agent",
            "--agent",
            agent,
            "--session-id",
            session_id,
            "--model",
            model,
            "--message",
            build_web_research_prompt(prompt),
            "--thinking",
            "off",
            "--json",
            "--timeout",
            str(timeout),
        ],
        text=True,
        capture_output=True,
        timeout=timeout + 15,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"OpenClaw web research failed with exit code {completed.returncode}")
    envelope = parse_openclaw_agent_output(completed.stdout)
    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    payloads = result.get("payloads") if isinstance(result.get("payloads"), list) else []
    answer = "\n\n".join(
        str(item.get("text") or "").strip()
        for item in payloads
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ).strip()
    if not answer:
        raise ValueError("OpenClaw web research returned an empty answer")
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    tool_summary = meta.get("toolSummary") if isinstance(meta.get("toolSummary"), dict) else {}
    tool_calls = int(tool_summary.get("calls") or 0)
    tool_failures = int(tool_summary.get("failures") or 0)
    tools = [str(name) for name in (tool_summary.get("tools") or []) if str(name)]
    unauthorized_tools = sorted(set(tools) - ALLOWED_WEB_TOOLS)
    if tool_calls < 1 or not tools:
        raise ValueError("OpenClaw agent returned without using a web-search tool")
    if unauthorized_tools:
        raise ValueError(f"OpenClaw agent used unauthorized tools: {','.join(unauthorized_tools)}")
    if tool_failures:
        raise ValueError(f"OpenClaw web-search tools reported {tool_failures} failure(s)")
    agent_meta = meta.get("agentMeta") if isinstance(meta.get("agentMeta"), dict) else {}
    return answer, {
        "provider": agent_meta.get("provider"),
        "model": agent_meta.get("model") or model,
        "agent": agent,
        "session_id": session_id,
        "tool_calls": tool_calls,
        "tools": tools,
        "tool_failures": tool_failures,
        "sources": extract_source_urls(answer),
    }


class OpenClawBridgeServer(ThreadingHTTPServer):
    token_file: Path
    openclaw: str
    agent: str
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
            self.write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "openclaw-web-research-bridge",
                    "agent": self.server.agent,
                    "model": self.server.model,
                    "web_search_required": True,
                },
            )
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
            answer, result = run_openclaw_agent(
                self.server.openclaw,
                self.server.agent,
                self.server.model,
                prompt,
                self.server.inference_timeout,
            )
        except subprocess.TimeoutExpired:
            self.write_json(HTTPStatus.GATEWAY_TIMEOUT, {"ok": False, "error": "openclaw_timeout", "prompt_hash": prompt_hash})
            return
        except (OSError, RuntimeError, ValueError) as exc:
            self.write_json(
                HTTPStatus.BAD_GATEWAY,
                {"ok": False, "error": "openclaw_web_research_failed", "detail": str(exc), "prompt_hash": prompt_hash},
            )
            return
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        response_model = str(result.get("model") or self.server.model)
        response_metadata = {
            "transport": "openclaw_agent",
            "provider": result.get("provider"),
            "agent": result.get("agent"),
            "web_search_used": True,
            "web_tools": result.get("tools") or [],
            "web_tool_calls": int(result.get("tool_calls") or 0),
            "web_tool_failures": int(result.get("tool_failures") or 0),
            "sources": result.get("sources") or [],
            "prompt_hash": prompt_hash,
            "prompt_chars": len(prompt),
            "elapsed_ms": elapsed_ms,
        }
        self.write_json(
            HTTPStatus.OK,
            {
                "id": f"openclaw-{prompt_hash[:16]}",
                "object": "chat.completion",
                "model": response_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": answer, "metadata": response_metadata},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
                "metadata": response_metadata,
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loopback-only OpenClaw web research bridge")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--openclaw", default=DEFAULT_OPENCLAW)
    parser.add_argument("--agent", default=DEFAULT_AGENT)
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
    server.agent = args.agent
    server.model = args.model
    server.inference_timeout = max(1, args.timeout)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
