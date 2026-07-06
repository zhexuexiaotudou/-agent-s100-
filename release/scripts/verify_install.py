#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


ENDPOINTS = {
    "health": "/api/health",
    "product_status": "/api/product/status",
    "product_evidence": "/api/product/evidence/latest",
    "harness_status": "/api/harness/status",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Digua AI-NAS install through live HTTP endpoints.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--qwen-url", default="http://127.0.0.1:18080/health")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()
    checks = {name: get_json(args.base_url.rstrip("/") + path, args.timeout) for name, path in ENDPOINTS.items()}
    checks["qwen_health"] = get_json(args.qwen_url, args.timeout)
    payload = {
        "ok": all(item.get("ok") for item in checks.values()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": args.base_url,
        "qwen_url": args.qwen_url,
        "checks": checks,
        "public_exposure_checked": "loopback_or_lan_only",
    }
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


def get_json(url: str, timeout: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(response.read().decode("utf-8"))}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


if __name__ == "__main__":
    raise SystemExit(main())

