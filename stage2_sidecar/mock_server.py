#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        return

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self.send_json(
                {
                    "ok": True,
                    "runtime": "stage2_sidecar_mock",
                    "foreground_route": False,
                    "provider_base_url": self.server.provider_base_url,  # type: ignore[attr-defined]
                    "tools": ["mock.nas_search", "mock.document_rag"],
                }
            )
            return
        if self.path.rstrip("/") == "/tools":
            self.send_json(json.loads((ROOT / "stage2_sidecar" / "mock_tools.json").read_text(encoding="utf-8")))
            return
        self.send_json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 2 sidecar mock runtime.")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=19080)
    parser.add_argument("--provider-base-url", default="http://127.0.0.1:18080/v1")
    args = parser.parse_args()
    if args.port in {8765, 18080, 18888, 18889}:
        raise SystemExit(f"refusing protected port {args.port}")
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.provider_base_url = args.provider_base_url  # type: ignore[attr-defined]
    print(json.dumps({"listening": f"http://{args.bind}:{args.port}", "provider_base_url": args.provider_base_url}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
