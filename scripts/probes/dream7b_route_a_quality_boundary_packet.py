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


TOOL_ID = "dream7b_route_a_quality_boundary_packet"
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"


SOURCE_REPORTS = {
    "fast_path_regression": "/mnt/nas/openclaw/reports/models/dream7b_fast_path_regression_20260622-174547/dream7b_fast_path_regression.json",
    "first_response_slo": "/mnt/nas/openclaw/reports/models/dream7b_first_response_slo_tier_guard_20260622-174823/dream7b_first_response_slo_tier_guard.json",
    "openclaw_entry_demo": "/mnt/nas/openclaw/reports/models/openclaw_entry_demo_20260622-174732/openclaw_entry_demo.json",
    "route_a_demo_readiness": "/mnt/nas/openclaw/reports/models/ai_nas_route_a_demo_readiness_packet_20260622-182319/ai_nas_route_a_demo_readiness_packet.json",
}


REMOTE_PROBE = r'''
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = "http://127.0.0.1:18888"
REPORTS = __REPORTS__


FAST_CASES = [
    {
        "id": "ready_probe",
        "messages": [{"role": "user", "content": "Return exactly one word: ready."}],
        "expected_path": "gateway_fast_ready",
        "max_first_content_ms": 100.0,
    },
    {
        "id": "english_identity",
        "messages": [{"role": "user", "content": "Who are you?"}],
        "expected_path": "gateway_fast_identity",
        "max_first_content_ms": 100.0,
    },
    {
        "id": "chinese_identity",
        "messages": [{"role": "user", "content": "你是谁？"}],
        "expected_path": "gateway_fast_identity",
        "max_first_content_ms": 100.0,
    },
    {
        "id": "local_status",
        "messages": [{"role": "user", "content": "用一句中文说明你是否在本地 S100P 上运行。"}],
        "expected_path": "gateway_fast_local_status",
        "max_first_content_ms": 100.0,
    },
]


GENERIC_CASES = [
    {
        "id": "generic_math_boundary",
        "messages": [{"role": "user", "content": "Reply with only the answer: 1+1="}],
        "max_elapsed_ms": 30000.0,
    },
]


def run(command, timeout=20):
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def service_state(name, *, root_user=False):
    if root_user:
        command = "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active " + name
    else:
        command = "systemctl is-active " + name
    result = run(command)
    return {
        "name": name,
        "root_user": root_user,
        "active": result["returncode"] == 0 and result["stdout"] == "active",
        "result": result,
    }


def http_json(url, timeout=5):
    try:
        started = time.perf_counter()
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            return {
                "url": url,
                "ok": response.status == 200,
                "status": response.status,
                "elapsed_ms": elapsed_ms,
                "json": json.loads(raw),
                "error": "",
            }
    except Exception as exc:
        return {
            "url": url,
            "ok": False,
            "status": 0,
            "elapsed_ms": None,
            "json": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def post_chat(messages, *, max_tokens=16, temperature=0.0, timeout=45):
    body = json.dumps(
        {
            "model": "Dream7B-S100P-local",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            parsed = json.loads(raw)
            choice = (parsed.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            meta = parsed.get("dream7b_candidate") or {}
            content = str(message.get("content") or "")
            return {
                "ok": response.status == 200,
                "status": response.status,
                "elapsed_ms": elapsed_ms,
                "content": content,
                "content_len": len(content.strip()),
                "dream7b_candidate": meta,
                "raw": parsed,
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "status": 0,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "content": "",
            "content_len": 0,
            "dream7b_candidate": {},
            "raw": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def report_status(report_id, path):
    p = Path(path)
    item = {
        "id": report_id,
        "path": path,
        "exists": p.exists(),
        "verdict": None,
        "error": "",
    }
    if not p.exists():
        return item
    try:
        with p.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        item["verdict"] = payload.get("verdict")
        if report_id == "first_response_slo":
            tiers = payload.get("tiers") or {}
            fast = tiers.get("fast_path_first_content") or {}
            backend = tiers.get("backend_first_content") or {}
            item["fast_path_max_first_content_ms"] = fast.get("max_first_content_ms")
            item["explicit_first_content_p50_ms"] = backend.get("explicit_first_content_p50_ms")
        if report_id == "route_a_demo_readiness":
            evaluation = payload.get("evaluation") or {}
            item["ready"] = evaluation.get("ready")
            item["tool_count"] = len(evaluation.get("tool_summaries") or [])
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item


def live_state():
    return {
        "services": {
            "dream7b_bpu_batch_queue": service_state("dream7b-bpu-batch-queue.service"),
            "dream7b_local_openai_gateway": service_state("dream7b-local-openai-gateway.service", root_user=True),
            "openclaw_gateway": service_state("openclaw-gateway.service", root_user=True),
        },
        "health": {
            "gateway_18888": http_json("http://127.0.0.1:18888/health"),
            "openclaw_18789": http_json("http://127.0.0.1:18789/health"),
        },
    }


before = live_state()
fast_results = []
for case in FAST_CASES:
    result = post_chat(case["messages"], max_tokens=8, timeout=15)
    meta = result.get("dream7b_candidate") or {}
    first_content_ms = result.get("elapsed_ms")
    fast_results.append(
        {
            "id": case["id"],
            "ok": result.get("ok"),
            "elapsed_ms": result.get("elapsed_ms"),
            "first_content_ms": first_content_ms,
            "content": result.get("content"),
            "content_len": result.get("content_len"),
            "execution_path": meta.get("execution_path"),
            "backend_invoked": meta.get("backend_invoked"),
            "expected_path": case["expected_path"],
            "max_first_content_ms": case["max_first_content_ms"],
            "error": result.get("error"),
        }
    )

generic_results = []
for case in GENERIC_CASES:
    result = post_chat(case["messages"], max_tokens=16, timeout=45)
    meta = result.get("dream7b_candidate") or {}
    generic_results.append(
        {
            "id": case["id"],
            "ok": result.get("ok"),
            "elapsed_ms": result.get("elapsed_ms"),
            "content": result.get("content"),
            "content_len": result.get("content_len"),
            "execution_path": meta.get("execution_path"),
            "backend_invoked": meta.get("backend_invoked"),
            "max_elapsed_ms": case["max_elapsed_ms"],
            "error": result.get("error"),
        }
    )
after = live_state()

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "host": run("hostname")["stdout"],
    "before": before,
    "after": after,
    "fast_results": fast_results,
    "generic_results": generic_results,
    "source_reports": {report_id: report_status(report_id, path) for report_id, path in REPORTS.items()},
    "audit": {
        "compile_started": False,
        "runtime_started": False,
        "service_restarted": False,
        "production_write_performed": False,
        "cloud_query_sent": False,
    },
}
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
        timeout,
    )


def run_remote_probe(args: argparse.Namespace) -> dict[str, Any]:
    source = REMOTE_PROBE.replace("__REPORTS__", json.dumps(SOURCE_REPORTS, ensure_ascii=False))
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


def active_live_state(state: dict[str, Any]) -> bool:
    services = state.get("services") or {}
    health = state.get("health") or {}
    return all(item.get("active") is True for item in services.values()) and all(
        item.get("ok") is True for item in health.values()
    )


def evaluate(remote: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not remote.get("ok"):
        errors.append(remote.get("error", "remote_probe_failed"))
    if not active_live_state(remote.get("before") or {}):
        errors.append("before_live_state_not_ready")
    if not active_live_state(remote.get("after") or {}):
        errors.append("after_live_state_not_ready")

    health = ((remote.get("after") or {}).get("health") or {}).get("gateway_18888") or {}
    gateway_health = health.get("json") or {}
    if gateway_health.get("backend") != "diffuse-resident":
        errors.append("gateway_backend_not_diffuse_resident")
    if gateway_health.get("quick_response_enabled") is not True:
        errors.append("quick_response_not_enabled")
    if gateway_health.get("resident_running") is not True:
        errors.append("resident_not_running")

    fast_rows = []
    for row in remote.get("fast_results") or []:
        row_errors = []
        if row.get("ok") is not True:
            row_errors.append("http_not_ok")
        if row.get("execution_path") != row.get("expected_path"):
            row_errors.append("unexpected_execution_path")
        if row.get("backend_invoked") is not False:
            row_errors.append("backend_invoked")
        if float(row.get("first_content_ms") or 999999.0) > float(row.get("max_first_content_ms") or 0):
            row_errors.append("first_content_above_fast_slo")
        if int(row.get("content_len") or 0) <= 0:
            row_errors.append("empty_content")
        if row_errors:
            errors.extend(f"fast:{row.get('id')}:{item}" for item in row_errors)
        fast_rows.append({**row, "errors": row_errors})

    generic_rows = []
    for row in remote.get("generic_results") or []:
        row_warnings = []
        if row.get("ok") is not True:
            row_warnings.append("http_not_ok")
        if row.get("backend_invoked") is not True:
            row_warnings.append("backend_not_invoked")
        if int(row.get("content_len") or 0) <= 0:
            row_warnings.append("empty_content")
        if float(row.get("elapsed_ms") or 999999.0) > float(row.get("max_elapsed_ms") or 0):
            row_warnings.append("elapsed_above_boundary")
        if row_warnings:
            warnings.extend(f"generic:{row.get('id')}:{item}" for item in row_warnings)
        generic_rows.append({**row, "warnings": row_warnings})

    expected_verdicts = {
        "fast_path_regression": "ok_dream7b_fast_path_regression",
        "first_response_slo": "ok_dream7b_first_response_slo_tier_guard",
        "openclaw_entry_demo": "ok_openclaw_entry_demo_probe",
        "route_a_demo_readiness": "ok_ai_nas_route_a_demo_readiness_packet",
    }
    for report_id, expected in expected_verdicts.items():
        report = (remote.get("source_reports") or {}).get(report_id) or {}
        if report.get("exists") is not True:
            errors.append(f"source_report_missing:{report_id}")
        if report.get("verdict") != expected:
            errors.append(f"source_report_not_ok:{report_id}:{report.get('verdict')}")
        if report.get("error"):
            errors.append(f"source_report_error:{report_id}:{report.get('error')}")

    return {
        "verdict": "ok_dream7b_route_a_quality_boundary_packet" if not errors else "failed_dream7b_route_a_quality_boundary_packet",
        "ready_for_demo": not errors,
        "errors": errors,
        "warnings": warnings,
        "fast_path": {
            "ready": not any(row["errors"] for row in fast_rows),
            "case_count": len(fast_rows),
            "max_first_content_ms": max((float(row.get("first_content_ms") or 0) for row in fast_rows), default=None),
            "cases": fast_rows,
        },
        "generic_generation_boundary": {
            "tracked": True,
            "promotion_claim": False,
            "interpretation": "generic resident output is recorded as a latency/quality boundary, not as a solved product-quality path",
            "case_count": len(generic_rows),
            "cases": generic_rows,
        },
        "policy": {
            "route_a_product_path": "OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF",
            "cloud_query_sent": False,
            "compile_started": False,
            "service_restarted": False,
            "production_write_performed": False,
        },
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    remote = run_remote_probe(args)
    evaluation = evaluate(remote)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "tool_id": TOOL_ID,
        "verdict": evaluation["verdict"],
        "remote": remote,
        "evaluation": evaluation,
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    evaluation = payload["evaluation"]
    lines = [
        "# Dream7B Route A Quality Boundary Packet",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- ready_for_demo: `{evaluation['ready_for_demo']}`",
        f"- error_count: `{len(evaluation['errors'])}`",
        f"- warning_count: `{len(evaluation['warnings'])}`",
        f"- route_a_product_path: `{evaluation['policy']['route_a_product_path']}`",
        "",
        "## Fast Path",
        "",
        f"- ready: `{evaluation['fast_path']['ready']}`",
        f"- case_count: `{evaluation['fast_path']['case_count']}`",
        f"- max_first_content_ms: `{evaluation['fast_path']['max_first_content_ms']}`",
        "",
        "| id | path | backend_invoked | first_content_ms | content | errors |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in evaluation["fast_path"]["cases"]:
        content = str(row.get("content") or "").replace("|", "\\|").replace("\n", " ")[:120]
        lines.append(
            f"| {row.get('id')} | {row.get('execution_path')} | {row.get('backend_invoked')} | "
            f"{row.get('first_content_ms')} | {content} | {row.get('errors')} |"
        )
    lines.extend(
        [
            "",
            "## Generic Generation Boundary",
            "",
            f"- tracked: `{evaluation['generic_generation_boundary']['tracked']}`",
            f"- promotion_claim: `{evaluation['generic_generation_boundary']['promotion_claim']}`",
            f"- interpretation: `{evaluation['generic_generation_boundary']['interpretation']}`",
            "",
            "| id | path | backend_invoked | elapsed_ms | content | warnings |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in evaluation["generic_generation_boundary"]["cases"]:
        content = str(row.get("content") or "").replace("|", "\\|").replace("\n", " ")[:120]
        lines.append(
            f"| {row.get('id')} | {row.get('execution_path')} | {row.get('backend_invoked')} | "
            f"{row.get('elapsed_ms')} | {content} | {row.get('warnings')} |"
        )
    lines.extend(["", "## Source Reports", ""])
    for report_id, report in (payload["remote"].get("source_reports") or {}).items():
        lines.append(
            f"- {report_id}: exists=`{report.get('exists')}` verdict=`{report.get('verdict')}` path=`{report.get('path')}`"
        )
    lines.extend(["", "## Errors", ""])
    if evaluation["errors"]:
        lines.extend(f"- `{error}`" for error in evaluation["errors"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if evaluation["warnings"]:
        lines.extend(f"- `{warning}`" for warning in evaluation["warnings"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sync_to_nas(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    remote_dir = f"{args.remote_report_root.rstrip('/')}/{report_dir.name}"
    mkdir = ssh_command(args, f"mkdir -p {remote_dir}", timeout=30)
    if mkdir["returncode"] != 0:
        return {"ok": False, "remote_dir": remote_dir, "mkdir": mkdir}
    scp = run_cmd(
        [
            "scp.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            str(report_dir / "dream7b_route_a_quality_boundary_packet.json"),
            str(report_dir / "dream7b_route_a_quality_boundary_packet.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--remote-timeout", type=int, default=180)
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.out_root) / f"dream7b_route_a_quality_boundary_packet_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_route_a_quality_boundary_packet.json"
    md_path = report_dir / "dream7b_route_a_quality_boundary_packet.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, payload)
    if not args.no_sync:
        sync = sync_to_nas(args, report_dir)
        payload["sync"] = sync
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_markdown(md_path, payload)
        if sync.get("ok") is False:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
    latest_json = Path(args.out_root) / "dream7b_route_a_quality_boundary_packet_latest.json"
    latest_md = Path(args.out_root) / "dream7b_route_a_quality_boundary_packet_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["evaluation"]["ready_for_demo"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
