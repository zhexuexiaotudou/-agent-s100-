#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_BASE_URL = "http://127.0.0.1:18080"


REMOTE_PROBE = r'''
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = __BASE_URL__
REPORT_ROOT = Path(__REPORT_ROOT__)
PROMPT = __PROMPT__


def http_json(method, url, payload=None, timeout=260):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "json": json.loads(raw) if raw else {},
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw}
        return {
            "ok": False,
            "status": exc.code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "json": parsed,
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": 0,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "json": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def latest(pattern):
    paths = [p for p in REPORT_ROOT.glob(pattern) if p.is_file()]
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def load_json(path):
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"load_error": f"{type(exc).__name__}: {exc}"}


def path_check(path):
    p = Path(path)
    item = {"path": path, "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() and p.is_file() else 0}
    if p.suffix == ".json" and p.exists():
        payload = load_json(p)
        item["verdict"] = payload.get("verdict")
        item["summary"] = payload.get("summary")
        item["answer_status"] = payload.get("answer_status")
    return item


health = http_json("GET", BASE_URL.rstrip("/") + "/health", timeout=10)
models = http_json("GET", BASE_URL.rstrip("/") + "/v1/models", timeout=10)
chat_payload = {
    "model": "Qwen2.5-1.5B-Instruct-S100P-official",
    "messages": [
        {
            "role": "user",
            "content": PROMPT,
        }
    ],
    "temperature": 0,
    "max_tokens": 256,
}
chat = http_json("POST", BASE_URL.rstrip("/") + "/v1/chat/completions", chat_payload, timeout=300)

metadata = {}
try:
    metadata = (((chat.get("json") or {}).get("choices") or [{}])[0].get("message") or {}).get("metadata") or {}
except Exception:
    metadata = {}
report_paths = list(dict.fromkeys((metadata.get("report_paths") or []) + list((metadata.get("gateway_turn") or {}).values())))
reports = [path_check(path) for path in report_paths]

runtime_1024_path = latest("s100_official_qwen_runtime_*/official_qwen_runtime_probe.json")
runtime_1024 = load_json(runtime_1024_path)
errors = []
if not health.get("ok"):
    errors.append("gateway_health_failed")
if not models.get("ok"):
    errors.append("models_endpoint_failed")
if not chat.get("ok"):
    errors.append("chat_ai_nas_flow_failed")
if not report_paths:
    errors.append("no_ai_nas_report_paths_returned")
if any(not item.get("exists") for item in reports):
    errors.append("returned_report_path_missing")
if not runtime_1024_path:
    errors.append("missing_official_qwen_1024_runtime_probe")
elif runtime_1024.get("qwen_hbm_path", "").endswith("Qwen2.5_1.5B_Instruct_1024.hbm") is not True:
    errors.append("latest_runtime_probe_not_1024_hbm")

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "verdict": "ok_qwen25_ai_nas_acceptance_packet" if not errors else "partial_qwen25_ai_nas_acceptance_packet",
    "base_url": BASE_URL,
    "prompt": PROMPT,
    "health": health,
    "models": models,
    "chat": chat,
    "metadata": metadata,
    "reports": reports,
    "official_qwen_1024_runtime_probe": {
        "path": str(runtime_1024_path) if runtime_1024_path else "",
        "verdict": runtime_1024.get("verdict"),
        "runtime_completed": runtime_1024.get("runtime_completed"),
        "runtime_returncode": runtime_1024.get("runtime_returncode"),
        "hbm_load_success_observed": runtime_1024.get("hbm_load_success_observed"),
        "init_model_success_observed": runtime_1024.get("init_model_success_observed"),
        "memory_alloc_failure_observed": runtime_1024.get("memory_alloc_failure_observed"),
        "qwen_hbm_path": runtime_1024.get("qwen_hbm_path"),
        "qwen_hbm_size_bytes": runtime_1024.get("qwen_hbm_size_bytes"),
        "warnings": runtime_1024.get("warnings"),
    },
    "errors": errors,
}

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
run_dir = REPORT_ROOT / f"qwen25_ai_nas_acceptance_{stamp}"
run_dir.mkdir(parents=True, exist_ok=True)
json_path = run_dir / "qwen25_ai_nas_acceptance.json"
md_path = run_dir / "qwen25_ai_nas_acceptance.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Qwen2.5 AI-NAS Acceptance Packet",
    "",
    f"- generated_at: `{payload['generated_at']}`",
    f"- verdict: `{payload['verdict']}`",
    f"- base_url: `{BASE_URL}`",
    f"- chat_elapsed_ms: `{chat.get('elapsed_ms')}`",
    f"- report_count: `{len(reports)}`",
    "",
    "## Official 1024 HBM Probe",
    "",
    f"- path: `{payload['official_qwen_1024_runtime_probe']['path']}`",
    f"- hbm: `{payload['official_qwen_1024_runtime_probe']['qwen_hbm_path']}`",
    f"- hbm_load_success_observed: `{payload['official_qwen_1024_runtime_probe']['hbm_load_success_observed']}`",
    f"- init_model_success_observed: `{payload['official_qwen_1024_runtime_probe']['init_model_success_observed']}`",
    f"- runtime_completed: `{payload['official_qwen_1024_runtime_probe']['runtime_completed']}`",
    f"- memory_alloc_failure_observed: `{payload['official_qwen_1024_runtime_probe']['memory_alloc_failure_observed']}`",
    "",
    "## Returned Evidence",
    "",
]
for item in reports:
    lines.append(f"- `{item['path']}` exists `{item['exists']}` verdict `{item.get('verdict')}`")
lines.extend(["", "## Errors", ""])
lines.extend([f"- `{error}`" for error in errors] or ["- none"])
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
payload["acceptance_paths"] = {"json": str(json_path), "md": str(md_path)}
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
'''


def run_cmd(command: list[str], timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "args": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_command(args: argparse.Namespace, command: str, timeout: int = 90) -> dict[str, Any]:
    return run_cmd(
        [
            "ssh.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            command,
        ],
        timeout=timeout,
    )


def run_remote_probe(args: argparse.Namespace) -> dict[str, Any]:
    source = (
        REMOTE_PROBE.replace("__BASE_URL__", json.dumps(args.base_url))
        .replace("__REPORT_ROOT__", json.dumps(args.remote_report_root))
        .replace("__PROMPT__", json.dumps(args.prompt, ensure_ascii=False))
    )
    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}').decode('utf-8'))\""
    result = ssh_command(args, command, timeout=args.remote_timeout)
    if result["returncode"] != 0:
        return {"ok": False, "error": "remote_probe_failed", "ssh": result}
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"remote_json_decode_failed:{exc}", "ssh": result}
    payload["ok"] = True
    return payload


def write_local_packet(report_dir: Path, payload: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "qwen25_ai_nas_acceptance.json"
    md_path = report_dir / "qwen25_ai_nas_acceptance.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    remote_paths = payload.get("acceptance_paths") or {}
    lines = [
        "# Qwen2.5 AI-NAS Acceptance Packet",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- verdict: `{payload.get('verdict')}`",
        f"- remote_json: `{remote_paths.get('json', '')}`",
        f"- remote_md: `{remote_paths.get('md', '')}`",
        f"- base_url: `{payload.get('base_url')}`",
        "",
        "## Errors",
        "",
    ]
    errors = payload.get("errors") or []
    lines.extend([f"- `{error}`" for error in errors] or ["- none"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Qwen2.5 AI-NAS remote acceptance packet.")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--prompt",
        default="请在 NAS 中检索 2024 装修付款相关发票、合同、收据和聊天截图，生成摘要和 Markdown/JSON 证据报告。",
    )
    parser.add_argument("--remote-timeout", type=int, default=420)
    parser.set_defaults(
        prompt=(
            "Please search the NAS for 2024 renovation payment invoices, contracts, "
            "receipts, and chat screenshots, then generate grounded Markdown and JSON "
            "evidence reports."
        )
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    payload = run_remote_probe(args)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    local_dir = Path(args.out_root) / f"qwen25_ai_nas_acceptance_{stamp}"
    write_local_packet(local_dir, payload)
    latest_json = Path(args.out_root) / "qwen25_ai_nas_acceptance_latest.json"
    latest_md = Path(args.out_root) / "qwen25_ai_nas_acceptance_latest.md"
    latest_json.write_text((local_dir / "qwen25_ai_nas_acceptance.json").read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text((local_dir / "qwen25_ai_nas_acceptance.md").read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("verdict") == "ok_qwen25_ai_nas_acceptance_packet" else 1


if __name__ == "__main__":
    raise SystemExit(main())
