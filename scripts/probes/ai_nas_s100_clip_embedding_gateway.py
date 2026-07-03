#!/usr/bin/env python3
"""S100/NAS CLIP image-text embedding gateway.

Runs on the S100P or another private host with local CLIP model files. It
accepts the same HTTP contract used by ai_nas_embedding_adapter.py:

POST /embed
{
  "input_type": "image" | "text",
  "model": "...",
  "image_url": {"url": "data:image/jpeg;base64,..."},
  "text": "white car"
}

The gateway never downloads models. It loads CLIP from --model-dir with
local_files_only=True and returns normalized vectors in the shared image/text
space.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_MODEL_DIR = Path(os.environ.get("AI_NAS_CLIP_MODEL_DIR", "/mnt/nas/openclaw/models/ai_nas_clip_vit_base_patch32"))


class ClipRuntime:
    def __init__(self, model_dir: Path, device: str = "cpu") -> None:
        self.model_dir = Path(model_dir)
        self.device = device
        self.model = None
        self.processor = None
        self.torch = None
        self.lock = threading.Lock()
        self.load_error: str | None = None

    def load(self) -> None:
        if self.model is not None and self.processor is not None:
            return
        with self.lock:
            if self.model is not None and self.processor is not None:
                return
            try:
                import torch
                from transformers import CLIPModel, CLIPProcessor

                model = CLIPModel.from_pretrained(str(self.model_dir), local_files_only=True)
                processor = CLIPProcessor.from_pretrained(str(self.model_dir), local_files_only=True)
                if self.device != "cpu" and torch.cuda.is_available():
                    model = model.to(self.device)
                model.eval()
                self.torch = torch
                self.model = model
                self.processor = processor
                self.load_error = None
            except Exception as exc:  # pragma: no cover - host dependent
                self.load_error = f"{type(exc).__name__}:{exc}"
                raise

    @property
    def ready(self) -> bool:
        return self.model is not None and self.processor is not None and self.load_error is None

    def embed_text(self, text: str) -> list[float]:
        self.load()
        assert self.model is not None and self.processor is not None and self.torch is not None
        inputs = self.processor(text=[text or ""], return_tensors="pt", padding=True)
        with self.torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
            outputs = outputs / outputs.norm(dim=-1, keepdim=True)
        return [round(float(item), 8) for item in outputs[0].detach().cpu().tolist()]

    def embed_image(self, image_bytes: bytes) -> list[float]:
        self.load()
        assert self.model is not None and self.processor is not None and self.torch is not None
        from PIL import Image

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        with self.torch.no_grad():
            outputs = self.model.get_image_features(**inputs)
            outputs = outputs / outputs.norm(dim=-1, keepdim=True)
        return [round(float(item), 8) for item in outputs[0].detach().cpu().tolist()]


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _decode_data_url(value: str) -> bytes:
    text = str(value or "")
    if "," not in text or not text.startswith("data:"):
        raise ValueError("image_url.url must be a data URL")
    _meta, data = text.split(",", 1)
    return base64.b64decode(data)


def make_handler(runtime: ClipRuntime, model_id: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AINASS100ClipGateway/1.0"

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path.rstrip("/") or "/"
            if route == "/health":
                payload = {
                    "ok": True,
                    "ready": runtime.ready,
                    "model_id": model_id,
                    "model_dir": str(runtime.model_dir),
                    "device": runtime.device,
                    "load_error": runtime.load_error,
                }
                _json_response(self, payload)
                return
            _json_response(self, {"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path.rstrip("/") or "/"
            if route != "/embed":
                _json_response(self, {"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                input_type = str(payload.get("input_type") or "").strip().lower()
                if input_type == "text":
                    vector = runtime.embed_text(str(payload.get("text") or ""))
                elif input_type == "image":
                    image_url = payload.get("image_url") or {}
                    vector = runtime.embed_image(_decode_data_url(str(image_url.get("url") or "")))
                else:
                    raise ValueError("input_type must be text or image")
                _json_response(
                    self,
                    {
                        "ok": True,
                        "model_id": model_id,
                        "embedding": vector,
                        "dim": len(vector),
                        "metadata": {
                            "backend": "transformers.CLIPModel",
                            "model_dir": str(runtime.model_dir),
                            "device": runtime.device,
                            "input_type": input_type,
                        },
                    },
                )
            except Exception as exc:
                _json_response(
                    self,
                    {"ok": False, "error": f"{type(exc).__name__}:{exc}", "model_id": model_id},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run S100/NAS CLIP image-text embedding HTTP gateway.")
    parser.add_argument("--bind", default=os.environ.get("AI_NAS_CLIP_GATEWAY_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AI_NAS_CLIP_GATEWAY_PORT", "18182")))
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--model-id", default=os.environ.get("AI_NAS_CLIP_MODEL_ID", "s100p-clip-vit-base-patch32"))
    parser.add_argument("--device", default=os.environ.get("AI_NAS_CLIP_DEVICE", "cpu"))
    parser.add_argument("--eager-load", action="store_true")
    args = parser.parse_args()

    runtime = ClipRuntime(args.model_dir, device=args.device)
    if args.eager_load:
        runtime.load()
        probe = runtime.embed_text("health check")
        print(json.dumps({"ok": True, "event": "eager_loaded", "dim": len(probe), "model_dir": str(args.model_dir)}), flush=True)
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(runtime, args.model_id))
    print(json.dumps({"ok": True, "event": "listening", "bind": args.bind, "port": args.port, "model_id": args.model_id}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
