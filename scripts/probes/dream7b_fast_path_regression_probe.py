#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


REMOTE_PROBE = r'''
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE_URL = "__BASE_URL__"
MODEL = "__MODEL__"
TIMEOUT = __TIMEOUT__

CASES = [
    {
        "id": "quick_ready",
        "kind": "quick_response",
        "prompt": "Return exactly one word: ready.",
        "expect_execution_path": "gateway_fast_ready",
        "expect_quick_response_mode": True,
        "expect_backend_invoked": False,
        "max_first_content_ms": __QUICK_LIMIT__,
    },
    {
        "id": "identity_short",
        "kind": "fast_identity",
        "prompt": "In one short sentence, identify your model name.",
        "expect_execution_path": "gateway_fast_identity",
        "expect_backend_invoked": False,
        "max_first_content_ms": __FAST_LIMIT__,
    },
    {
        "id": "chinese_identity",
        "kind": "fast_identity",
        "prompt": "\u4f60\u662f\u8c01\uff1f\u8bf7\u7528\u4e00\u53e5\u4e2d\u6587\u8bf4\u660e\u4f60\u7684\u6a21\u578b\u8eab\u4efd\u3002",
        "expect_execution_path": "gateway_fast_identity",
        "expect_backend_invoked": False,
        "max_first_content_ms": __FAST_LIMIT__,
    },
    {
        "id": "chinese_short",
        "kind": "fast_local_status",
        "prompt": "\u7528\u4e00\u53e5\u4e2d\u6587\u8bf4\u660e\u4f60\u662f\u5426\u5728\u672c\u5730 S100P \u4e0a\u8fd0\u884c\u3002",
        "expect_execution_path": "gateway_fast_local_status",
        "expect_backend_invoked": False,
        "max_first_content_ms": __FAST_LIMIT__,
    },
]


def iso_now():
    return datetime.now(timezone.utc).astimezone().isoformat()


def http_json(method, url, payload=None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw), round((time.perf_counter() - started) * 1000, 3)


def call_case(case):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": case["prompt"]}],
        "stream": True,
    }
    started = time.perf_counter()
    first_byte_ms = None
    first_progress_ms = None
    first_content_ms = None
    progress_event_count = 0
    content_parts = []
    meta = {}
    raw_preview = []
    status = 0
    error = ""
    stream_supported = False
    try:
        req = urllib.request.Request(
            BASE_URL.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            if "text/event-stream" in ctype:
                stream_supported = True
                while True:
                    line_bytes = resp.readline()
                    observed_ms = (time.perf_counter() - started) * 1000
                    if line_bytes and first_byte_ms is None:
                        first_byte_ms = observed_ms
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if len(raw_preview) < 40:
                        raw_preview.append(line)
                    if not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    candidate = chunk.get("dream7b_candidate")
                    if isinstance(candidate, dict):
                        meta.update(candidate)
                        if candidate.get("progress_event_index") is not None:
                            progress_event_count += 1
                            if first_progress_ms is None:
                                first_progress_ms = observed_ms
                    delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                    if delta:
                        if first_content_ms is None:
                            first_content_ms = observed_ms
                        content_parts.append(str(delta))
            else:
                raw = resp.read().decode("utf-8", errors="replace")
                first_byte_ms = (time.perf_counter() - started) * 1000
                parsed = json.loads(raw)
                message = ((parsed.get("choices") or [{}])[0].get("message") or {})
                content_parts.append(str(message.get("content") or ""))
                candidate = parsed.get("dream7b_candidate")
                if isinstance(candidate, dict):
                    meta.update(candidate)
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = exc.read().decode("utf-8", errors="replace")[:1000]
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = (time.perf_counter() - started) * 1000
    meta["observed_progress_event_count"] = progress_event_count
    content = "".join(content_parts)
    return {
        "id": case["id"],
        "kind": case["kind"],
        "status": status,
        "ok": status == 200 and not error,
        "error": error,
        "request": payload,
        "content": content,
        "content_preview": content[:180],
        "elapsed_ms": round(elapsed_ms, 3),
        "ttft_ms": round(first_byte_ms if first_byte_ms is not None else elapsed_ms, 3),
        "first_progress_ms": round(first_progress_ms, 3) if first_progress_ms is not None else None,
        "first_content_ms": round(first_content_ms if first_content_ms is not None else elapsed_ms, 3),
        "stream_supported": stream_supported,
        "progress_event_count": progress_event_count,
        "dream7b_candidate": meta,
        "raw_sse_preview": "\n".join(raw_preview)[:1000],
        "expect_execution_path": case.get("expect_execution_path"),
        "expect_quick_response_mode": case.get("expect_quick_response_mode"),
        "expect_backend_invoked": case.get("expect_backend_invoked"),
        "max_first_content_ms": case.get("max_first_content_ms"),
    }


errors = []
try:
    health_status, health, health_ms = http_json("GET", BASE_URL.rstrip("/") + "/health")
except Exception as exc:
    health_status, health, health_ms = 0, {}, 0.0
    errors.append(f"health_check_failed:{type(exc).__name__}:{exc}")
try:
    models_status, models, models_ms = http_json("GET", BASE_URL.rstrip("/") + "/v1/models")
except Exception as exc:
    models_status, models, models_ms = 0, {}, 0.0
    errors.append(f"models_check_failed:{type(exc).__name__}:{exc}")

model_ids = [item.get("id") for item in models.get("data", []) if isinstance(item, dict)]
if health.get("model") != MODEL:
    errors.append(f"health_model_mismatch:{health.get('model')}!={MODEL}")
if MODEL not in model_ids:
    errors.append(f"models_list_missing:{MODEL}")

cases = [call_case(case) for case in CASES]
for case in cases:
    meta = case.get("dream7b_candidate") or {}
    if not case["ok"]:
        errors.append(f"case_failed:{case['id']}:{case['error']}")
    if case.get("expect_execution_path") and meta.get("execution_path") != case["expect_execution_path"]:
        errors.append(f"execution_path_mismatch:{case['id']}:{meta.get('execution_path')}!={case['expect_execution_path']}")
    if case.get("expect_quick_response_mode") is not None and meta.get("quick_response_mode") is not case["expect_quick_response_mode"]:
        errors.append(f"quick_response_mode_mismatch:{case['id']}:{meta.get('quick_response_mode')}!={case['expect_quick_response_mode']}")
    if case.get("expect_backend_invoked") is not None and meta.get("backend_invoked") is not case["expect_backend_invoked"]:
        errors.append(f"backend_invoked_mismatch:{case['id']}:{meta.get('backend_invoked')}!={case['expect_backend_invoked']}")
    if float(case["first_content_ms"]) > float(case["max_first_content_ms"]):
        errors.append(f"first_content_above_limit:{case['id']}:{case['first_content_ms']}>{case['max_first_content_ms']}")

payload = {
    "generated_at": iso_now(),
    "base_url": BASE_URL,
    "model": MODEL,
    "verdict": "ok_dream7b_fast_path_regression" if not errors else "failed_dream7b_fast_path_regression",
    "preflight": {
        "health_status": health_status,
        "health_latency_ms": health_ms,
        "health": health,
        "models_status": models_status,
        "models_latency_ms": models_ms,
        "model_id_confirmed": health.get("model") == MODEL and MODEL in model_ids,
    },
    "cases": cases,
    "errors": errors,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
'''


def run_cmd(args: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_cmd(args: argparse.Namespace, command: str, timeout: int) -> dict[str, Any]:
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


def parse_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_remote_probe(args: argparse.Namespace) -> str:
    source = REMOTE_PROBE
    source = source.replace("__BASE_URL__", args.base_url)
    source = source.replace("__MODEL__", args.model)
    source = source.replace("__TIMEOUT__", str(args.case_timeout))
    source = source.replace("__QUICK_LIMIT__", str(float(args.quick_ready_limit_ms)))
    source = source.replace("__FAST_LIMIT__", str(float(args.fast_path_limit_ms)))
    return source


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Dream7B Fast Path Regression",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- verdict: {payload['verdict']}",
        f"- model: {payload['model']}",
        f"- base_url: {payload['base_url']}",
        f"- model_id_confirmed: {payload['preflight']['model_id_confirmed']}",
        f"- queue_service_active_enabled: {payload['service']['queue_service_active_enabled']}",
        f"- gateway_service_active_enabled: {payload['service']['gateway_service_active_enabled']}",
        "",
        "## Cases",
        "",
        "| id | ok | first_content_ms | execution_path | quick_response_mode | backend_invoked | content |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for case in payload["cases"]:
        meta = case.get("dream7b_candidate") or {}
        content = str(case.get("content_preview") or "").replace("\n", " ").replace("|", "\\|")
        lines.append(
            f"| {case['id']} | {case['ok']} | {case['first_content_ms']} | "
            f"{meta.get('execution_path')} | {meta.get('quick_response_mode')} | "
            f"{meta.get('backend_invoked')} | {content} |"
        )
    lines.extend(["", "## Errors", ""])
    if payload["errors"]:
        lines.extend(f"- {item}" for item in payload["errors"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Live regression check for Dream7B gateway fast paths on S100P.")
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", default=r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519")
    parser.add_argument("--known-hosts", default=r"C:\Users\zhexu\.ssh\known_hosts")
    parser.add_argument("--base-url", default="http://127.0.0.1:18888")
    parser.add_argument("--model", default="Dream7B-S100P-local")
    parser.add_argument("--out-root", type=Path, default=Path("tmp/product_guardrail_snapshots"))
    parser.add_argument("--case-timeout", type=int, default=60)
    parser.add_argument("--quick-ready-limit-ms", type=float, default=8000.0)
    parser.add_argument("--fast-path-limit-ms", type=float, default=100.0)
    args = parser.parse_args()

    remote_script = build_remote_probe(args)
    encoded_probe = base64.b64encode(remote_script.encode("utf-8")).decode("ascii")
    remote_command = (
        "python3 - <<'PY'\n"
        "import base64\n"
        f"source = base64.b64decode('{encoded_probe}').decode('utf-8')\n"
        "exec(compile(source, '<dream7b_fast_path_regression_remote>', 'exec'))\n"
        "PY"
    )
    remote = ssh_cmd(args, remote_command, timeout=args.case_timeout * 4)
    service = ssh_cmd(
        args,
        "systemctl is-active dream7b-bpu-batch-queue.service; "
        "systemctl is-enabled dream7b-bpu-batch-queue.service; "
        "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active dream7b-local-openai-gateway.service; "
        "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-enabled dream7b-local-openai-gateway.service",
        timeout=30,
    )

    try:
        payload = json.loads(remote["stdout"])
    except json.JSONDecodeError as exc:
        payload = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "base_url": args.base_url,
            "model": args.model,
            "verdict": "failed_dream7b_fast_path_regression",
            "preflight": {"model_id_confirmed": False},
            "cases": [],
            "errors": [f"remote_json_parse_failed:{exc}"],
            "remote_stdout": remote["stdout"],
        }

    status_lines = parse_lines(service["stdout"])
    service_errors = []
    if remote["returncode"] != 0:
        service_errors.append(f"remote_probe_returncode:{remote['returncode']}")
    if service["returncode"] != 0:
        service_errors.append(f"service_status_returncode:{service['returncode']}")
    if status_lines[:4] != ["active", "enabled", "active", "enabled"]:
        service_errors.append(f"service_status_mismatch:{status_lines[:4]}")

    payload["service"] = {
        "status_lines": status_lines,
        "queue_service_active_enabled": status_lines[:2] == ["active", "enabled"],
        "gateway_service_active_enabled": status_lines[2:4] == ["active", "enabled"],
    }
    payload["remote_command"] = remote
    payload["service_command"] = service
    payload["errors"] = list(payload.get("errors") or []) + service_errors
    payload["verdict"] = (
        "ok_dream7b_fast_path_regression"
        if not payload["errors"]
        else "failed_dream7b_fast_path_regression"
    )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_fast_path_regression_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_fast_path_regression.json"
    out_md = out_dir / "dream7b_fast_path_regression.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
