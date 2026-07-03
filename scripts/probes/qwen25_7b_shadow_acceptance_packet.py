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


DEFAULT_OUT_ROOT = Path("tmp/qwen25_7b_shadow_acceptance")
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_BASE_URL = "http://127.0.0.1:18081"
DEFAULT_MODEL = "Qwen2.5-7B-Instruct-S100P-official-shadow"
DEFAULT_EXPECTED_HBM = "Qwen2.5_7B_Instruct_1024.hbm"


REMOTE_PROBE = r'''
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = __BASE_URL__
MODEL_ID = __MODEL_ID__
EXPECTED_HBM_SUFFIX = __EXPECTED_HBM_SUFFIX__
REPORT_ROOT = Path(__REPORT_ROOT__)
PROMPT = __PROMPT__


def http_json(method, url, payload=None, timeout=360):
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


def load_json(path):
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
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


health = http_json("GET", BASE_URL.rstrip("/") + "/health", timeout=15)
models = http_json("GET", BASE_URL.rstrip("/") + "/v1/models", timeout=15)
chat_payload = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": PROMPT}],
    "temperature": 0,
    "max_tokens": 256,
}
chat = http_json("POST", BASE_URL.rstrip("/") + "/v1/chat/completions", chat_payload, timeout=420)

metadata = {}
try:
    metadata = (((chat.get("json") or {}).get("choices") or [{}])[0].get("message") or {}).get("metadata") or {}
except Exception:
    metadata = {}
report_paths = list(dict.fromkeys((metadata.get("report_paths") or []) + list((metadata.get("gateway_turn") or {}).values())))
reports = [path_check(path) for path in report_paths]
health_json = health.get("json") or {}
models_json = models.get("json") or {}
model_ids = [item.get("id") for item in models_json.get("data", []) if isinstance(item, dict)]
active_hbm = health_json.get("active_hbm") or {}

errors = []
if not health.get("ok"):
    errors.append("shadow_gateway_health_failed")
if health_json.get("model") != MODEL_ID:
    errors.append("shadow_gateway_model_id_mismatch")
if not str(active_hbm.get("path") or "").endswith(EXPECTED_HBM_SUFFIX):
    errors.append("shadow_gateway_active_hbm_mismatch")
if active_hbm.get("exists") is not True:
    errors.append("shadow_gateway_active_hbm_missing")
if not models.get("ok"):
    errors.append("models_endpoint_failed")
if MODEL_ID not in model_ids:
    errors.append("models_endpoint_missing_shadow_model_id")
if not chat.get("ok"):
    errors.append("chat_ai_nas_flow_failed")
if not report_paths:
    errors.append("no_ai_nas_report_paths_returned")
if any(not item.get("exists") for item in reports):
    errors.append("returned_report_path_missing")
gateway_verdicts = [item.get("verdict") for item in reports if str(item.get("path", "")).endswith("qwen25_gateway_turn.json")]
if gateway_verdicts and "ok_qwen25_ai_nas_gateway_turn" not in gateway_verdicts:
    errors.append("gateway_turn_not_ok")

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "verdict": "ok_qwen25_7b_shadow_acceptance_packet" if not errors else "partial_qwen25_7b_shadow_acceptance_packet",
    "base_url": BASE_URL,
    "model_id": MODEL_ID,
    "expected_hbm_suffix": EXPECTED_HBM_SUFFIX,
    "prompt": PROMPT,
    "health": health,
    "models": models,
    "chat": chat,
    "metadata": metadata,
    "reports": reports,
    "errors": errors,
}

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
run_dir = REPORT_ROOT / f"qwen25_7b_shadow_acceptance_{stamp}"
run_dir.mkdir(parents=True, exist_ok=True)
json_path = run_dir / "qwen25_7b_shadow_acceptance.json"
md_path = run_dir / "qwen25_7b_shadow_acceptance.md"
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = [
    "# Qwen2.5 7B Shadow Acceptance Packet",
    "",
    f"- generated_at: `{payload['generated_at']}`",
    f"- verdict: `{payload['verdict']}`",
    f"- base_url: `{BASE_URL}`",
    f"- model_id: `{MODEL_ID}`",
    f"- expected_hbm_suffix: `{EXPECTED_HBM_SUFFIX}`",
    f"- chat_elapsed_ms: `{chat.get('elapsed_ms')}`",
    f"- report_count: `{len(reports)}`",
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
        .replace("__MODEL_ID__", json.dumps(args.model_id))
        .replace("__EXPECTED_HBM_SUFFIX__", json.dumps(args.expected_hbm_suffix))
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
    json_path = report_dir / "qwen25_7b_shadow_acceptance.json"
    md_path = report_dir / "qwen25_7b_shadow_acceptance.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    remote_paths = payload.get("acceptance_paths") or {}
    lines = [
        "# Qwen2.5 7B Shadow Acceptance Packet",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- verdict: `{payload.get('verdict')}`",
        f"- remote_json: `{remote_paths.get('json', '')}`",
        f"- remote_md: `{remote_paths.get('md', '')}`",
        f"- base_url: `{payload.get('base_url')}`",
        f"- model_id: `{payload.get('model_id')}`",
        "",
        "## Errors",
        "",
    ]
    errors = payload.get("errors") or []
    lines.extend([f"- `{error}`" for error in errors] or ["- none"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Qwen2.5 7B shadow route acceptance packet.")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model-id", default=DEFAULT_MODEL)
    parser.add_argument("--expected-hbm-suffix", default=DEFAULT_EXPECTED_HBM)
    parser.add_argument(
        "--prompt",
        default=(
            "Please search the NAS for 2024 renovation payment invoices, contracts, "
            "receipts, and chat screenshots, then generate grounded Markdown and JSON "
            "evidence reports."
        ),
    )
    parser.add_argument("--remote-timeout", type=int, default=520)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    payload = run_remote_probe(args)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    local_dir = Path(args.out_root) / f"qwen25_7b_shadow_acceptance_{stamp}"
    write_local_packet(local_dir, payload)
    latest_json = Path(args.out_root) / "qwen25_7b_shadow_acceptance_latest.json"
    latest_md = Path(args.out_root) / "qwen25_7b_shadow_acceptance_latest.md"
    latest_json.write_text((local_dir / "qwen25_7b_shadow_acceptance.json").read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text((local_dir / "qwen25_7b_shadow_acceptance.md").read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("verdict") == "ok_qwen25_7b_shadow_acceptance_packet" else 1


if __name__ == "__main__":
    raise SystemExit(main())
