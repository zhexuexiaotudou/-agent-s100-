from __future__ import annotations

import argparse
import platform
import subprocess
from pathlib import Path

from ai_space_gate_common import add_common_args, check, write_gate
from stage8_demo_common import gate_payload, http_get_json


NAME = "stage8_demo1_link_readiness_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate demo 1 resident S100P link readiness.")
    add_common_args(parser)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--qwen-url", default="http://127.0.0.1:18080/health")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()
    health = http_get_json(args.base_url, "/api/health", timeout=args.timeout)
    product = http_get_json(args.base_url, "/api/product/status", timeout=args.timeout)
    harness = http_get_json(args.base_url, "/api/harness/status", timeout=args.timeout)
    qwen = _http_url(args.qwen_url, timeout=args.timeout)
    systemd = _systemd_status()
    personal_root = Path(args.personal_root) if args.personal_root else None
    checks = [
        check("portal health ok", health.get("ok") is True and (health.get("payload") or {}).get("ok") is True, health),
        check("product status ok", product.get("ok") is True and (product.get("payload") or {}).get("ok") is True, product),
        check("harness status ok", harness.get("ok") is True and (harness.get("payload") or {}).get("ok") is True, harness),
        check("qwen health ok", qwen.get("ok") is True, qwen),
        check("personal root mounted/visible", bool(personal_root and personal_root.exists()), str(personal_root)),
        check("gateway not publicly exposed by gate", str(args.base_url).startswith("http://127.0.0.1") or str(args.base_url).startswith("http://localhost"), args.base_url),
        check("resident control plane observed", systemd.get("openclaw_active") is True or health.get("ok") is True, systemd),
    ]
    payload = gate_payload("ok_stage8_demo1_link_readiness_gate", "blocked_stage8_demo1_link_readiness_gate", checks, {"health": health, "product": product, "harness": harness, "qwen": qwen, "systemd": systemd})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


def _http_url(url: str, *, timeout: int) -> dict:
    import json
    import time
    import urllib.request

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read(65536).decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:1000]}
            return {"ok": 200 <= response.status < 300, "status": response.status, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "payload": payload}
    except Exception as exc:
        return {"ok": False, "status": None, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "error": f"{type(exc).__name__}:{exc}"}


def _systemd_status() -> dict:
    if platform.system().lower() != "linux":
        return {"available": False, "platform": platform.system()}
    result = {"available": True}
    for name in ["openclaw-gateway.service", "qwen25-local-openai-gateway.service"]:
        completed = subprocess.run(["systemctl", "--user", "is-active", name], text=True, capture_output=True, check=False, timeout=5)
        result[name] = completed.stdout.strip() or completed.stderr.strip()
    result["openclaw_active"] = result.get("openclaw-gateway.service") == "active"
    result["qwen_active"] = result.get("qwen25-local-openai-gateway.service") == "active"
    return result


if __name__ == "__main__":
    raise SystemExit(main())
