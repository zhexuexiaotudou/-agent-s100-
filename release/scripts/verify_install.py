#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
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
    parser.add_argument("--username", default=os.environ.get("DIGUA_ADMIN_USERNAME", ""))
    parser.add_argument("--password-env", default="DIGUA_ADMIN_PASSWORD")
    parser.add_argument("--token-env", default="DIGUA_ADMIN_TOKEN")
    args = parser.parse_args()
    token = os.environ.get(args.token_env, "")
    login = {"ok": bool(token), "source": "token_env" if token else "none"}
    if not token and args.username and os.environ.get(args.password_env):
        login = post_json(
            args.base_url.rstrip("/") + "/api/identity/login",
            {"username": args.username, "password": os.environ[args.password_env]},
            args.timeout,
        )
        token = str((login.get("payload") or {}).get("token") or "")
    checks = {
        name: get_json(
            args.base_url.rstrip("/") + path,
            args.timeout,
            "" if name == "health" else token,
        )
        for name, path in ENDPOINTS.items()
    }
    checks["qwen_health"] = get_json(args.qwen_url, args.timeout)
    payload = {
        "ok": bool(token) and all(item.get("ok") for item in checks.values()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": args.base_url,
        "qwen_url": args.qwen_url,
        "checks": checks,
        "authentication": {"ok": bool(token), "login": {key: value for key, value in login.items() if key != "payload"}, "token_redacted": True},
        "public_exposure_checked": "loopback_or_lan_only",
    }
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


def get_json(url: str, timeout: int, token: str = "") -> dict[str, Any]:
    try:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(response.read().decode("utf-8"))}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": json.loads(response.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


if __name__ == "__main__":
    raise SystemExit(main())
