#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path("configs/dream7b_queue_adapter_policy.json")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config must be a JSON object")
    return payload


def first_message_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
                if parts:
                    return "\n".join(parts)
    prompt = payload.get("prompt")
    return prompt if isinstance(prompt, str) else ""


def request_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("metadata")
    return meta if isinstance(meta, dict) else {}


def classify_task(payload: dict[str, Any]) -> str:
    meta = request_metadata(payload)
    task_class = meta.get("task_class") or meta.get("route_class")
    if isinstance(task_class, str) and task_class:
        return task_class.strip().lower()
    return "interactive"


def valid_tokens(value: Any, seq_len: int) -> list[int] | None:
    if not isinstance(value, list) or len(value) != seq_len:
        return None
    tokens = []
    for item in value:
        if not isinstance(item, int):
            return None
        tokens.append(item)
    return tokens


def proxy_to_route_a(config: dict[str, Any], path: str, payload: dict[str, Any], timeout_ms: int) -> tuple[int, dict[str, Any]]:
    route_a = config["route_a"]
    url = route_a["base_url"].rstrip("/") + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=max(timeout_ms / 1000.0, 1.0)) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"error": raw}
        return exc.code, parsed
    except Exception as exc:
        return 502, {
            "error": {
                "message": f"route_a proxy failed: {type(exc).__name__}: {exc}",
                "type": "route_a_proxy_error",
            }
        }


def enqueue_bpu_job(config: dict[str, Any], payload: dict[str, Any], tokens: list[int]) -> dict[str, Any]:
    route_b = config["route_b"]
    queue_dir = Path(route_b["queue_dir"])
    pending = queue_dir / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    request_id = str(request_metadata(payload).get("request_id") or uuid.uuid4())
    not_after_epoch_ms = int(time.time() * 1000) + int(route_b["timeouts"]["enqueue_timeout_ms"])
    row = {
        "request_id": request_id,
        "tokens": tokens,
        "not_after_epoch_ms": not_after_epoch_ms,
        "metadata": {
            "accepted_by": "dream7b_experimental_18889_gateway",
            "accepted_at": now_iso(),
            "source_model": payload.get("model"),
            "task_class": classify_task(payload),
            "prompt_preview": first_message_text(payload)[:160],
        },
    }
    target = pending / f"openclaw-18889-{int(time.time() * 1000)}-{request_id}.jsonl"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(target)
    return {
        "request_id": request_id,
        "queue_file": str(target),
        "not_after_epoch_ms": not_after_epoch_ms,
    }


def completion_response(model: str, content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "metadata": metadata,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "Dream7BExperimental18889/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/health":
            config = self.server.config  # type: ignore[attr-defined]
            route_b = config["route_b"]
            self._json(
                200,
                {
                    "ok": True,
                    "model": route_b["model"],
                    "backend": "bpu-queue-experimental",
                    "protected_route_a": config["route_a"]["base_url"],
                    "enabled_by_default": route_b.get("enabled_by_default") is True,
                    "allowed_task_classes": route_b["allowed_task_classes"],
                    "queue_dir": route_b["queue_dir"],
                    "policy": "background_only_with_fallback",
                },
            )
            return
        self._json(404, {"error": {"message": "not found", "type": "not_found"}})

    def do_POST(self) -> None:
        config = self.server.config  # type: ignore[attr-defined]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
        except Exception as exc:
            self._json(400, {"error": {"message": str(exc), "type": "invalid_request"}})
            return

        if self.path not in {"/v1/chat/completions", "/v1/completions"}:
            self._json(404, {"error": {"message": "not found", "type": "not_found"}})
            return

        route_b = config["route_b"]
        fallback_timeout = int(route_b["timeouts"]["fallback_proxy_timeout_ms"])
        task_class = classify_task(payload)
        allowed = set(route_b["allowed_task_classes"])
        forbidden = set(route_b["forbidden_task_classes"])
        if task_class in forbidden or task_class not in allowed:
            status, body = proxy_to_route_a(config, self.path, payload, fallback_timeout)
            if isinstance(body, dict):
                body.setdefault("dream7b_18889_adapter", {})
                body["dream7b_18889_adapter"].update(
                    {
                        "decision": "fallback_route_a",
                        "reason": "task_class_not_allowed_for_bpu_queue",
                        "task_class": task_class,
                    }
                )
            self._json(status, body)
            return

        meta = request_metadata(payload)
        seq_len = int(route_b["bpu_job_contract"]["seq_len"])
        tokens = valid_tokens(meta.get("bpu_tokens"), seq_len)
        if tokens is None:
            status, body = proxy_to_route_a(config, self.path, payload, fallback_timeout)
            if isinstance(body, dict):
                body.setdefault("dream7b_18889_adapter", {})
                body["dream7b_18889_adapter"].update(
                    {
                        "decision": "fallback_route_a",
                        "reason": "missing_or_invalid_bpu_tokens",
                        "required_seq_len": seq_len,
                        "task_class": task_class,
                    }
                )
            self._json(status, body)
            return

        try:
            queued = enqueue_bpu_job(config, payload, tokens)
        except Exception as exc:
            status, body = proxy_to_route_a(config, self.path, payload, fallback_timeout)
            if isinstance(body, dict):
                body.setdefault("dream7b_18889_adapter", {})
                body["dream7b_18889_adapter"].update(
                    {
                        "decision": "fallback_route_a",
                        "reason": f"queue_error:{type(exc).__name__}",
                        "task_class": task_class,
                    }
                )
            self._json(status, body)
            return

        content = (
            "BPU queue job accepted for background processing. "
            f"request_id={queued['request_id']}"
        )
        self._json(
            200,
            completion_response(
                route_b["model"],
                content,
                {
                    "decision": "queued_bpu_background_job",
                    "task_class": task_class,
                    "queue_file": queued["queue_file"],
                    "not_after_epoch_ms": queued["not_after_epoch_ms"],
                    "fallback_route": config["route_a"]["base_url"],
                    "promotion_claim": False,
                },
            ),
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated 18889 BPU queue adapter for Dream7B/OpenClaw experiments.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default=os.environ.get("DREAM7B_EXPERIMENTAL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DREAM7B_EXPERIMENTAL_PORT", "18889")))
    args = parser.parse_args()
    config = load_config(args.config)
    server = ThreadingHTTPServer((args.host, args.port), GatewayHandler)
    server.config = config  # type: ignore[attr-defined]
    print(json.dumps({"listening": f"http://{args.host}:{args.port}", "config": str(args.config)}, ensure_ascii=False), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
