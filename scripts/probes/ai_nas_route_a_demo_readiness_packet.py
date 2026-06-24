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
DEFAULT_REMOTE_WORKSPACE = "/root/.openclaw/workspace"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"


REMOTE_PROBE = r'''
from __future__ import annotations

import json
import shlex
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__WORKSPACE__)
COMMANDS = __COMMANDS__


def run(command, *, timeout=240, root_workspace=False):
    if root_workspace:
        inner = "cd " + shlex.quote(str(WORKSPACE)) + " && " + command
        command = "sudo -n bash -lc " + shlex.quote(inner)
    started = time.perf_counter()
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
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def service_state(name, *, root_user=False):
    if root_user:
        command = "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active " + shlex.quote(name)
    else:
        command = "systemctl is-active " + shlex.quote(name)
    result = run(command, timeout=20)
    return {
        "name": name,
        "root_user": root_user,
        "active": result["returncode"] == 0 and result["stdout"] == "active",
        "result": result,
    }


def http_json(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {
                "url": url,
                "ok": response.status == 200,
                "status": response.status,
                "json": json.loads(raw),
                "error": "",
            }
    except Exception as exc:
        return {
            "url": url,
            "ok": False,
            "status": 0,
            "json": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


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


def json_paths_from_stdout(stdout):
    paths = []
    for line in stdout.splitlines():
        text = line.strip()
        if text.startswith("/") and text.endswith(".json"):
            paths.append(text)
        elif text.startswith("/") and text.endswith(".md"):
            sibling = str(Path(text).with_suffix(".json"))
            if Path(sibling).exists():
                paths.append(sibling)
    return list(dict.fromkeys(paths))


def summarize_payload(path):
    p = Path(path)
    item = {
        "path": path,
        "exists": p.exists(),
        "verdict": None,
        "summary": {},
        "audit": {},
        "mutation_flags": {},
        "error": "",
    }
    if not p.exists():
        return item
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
        return item
    audit = payload.get("audit") or {}
    summary = payload.get("summary") or {}
    item["verdict"] = payload.get("verdict")
    item["summary"] = summary
    item["audit"] = audit
    item["mutation_flags"] = {
        "source_files_modified": audit.get("source_files_modified"),
        "delete_performed": audit.get("delete_performed", payload.get("delete_performed")),
        "move_performed": audit.get("move_performed", payload.get("move_performed")),
        "overwrite_performed": audit.get("overwrite_performed", payload.get("overwrite_performed")),
        "copy_sort_executed": payload.get("copy_sort_executed"),
        "privacy_query_sent_to_cloud": summary.get("privacy_query_sent_to_cloud"),
    }
    return item


before = live_state()
tool_runs = []
for command_spec in COMMANDS:
    result = run(command_spec["command"], timeout=command_spec.get("timeout", 240), root_workspace=True)
    json_paths = json_paths_from_stdout(result["stdout"])
    payloads = [summarize_payload(path) for path in json_paths]
    tool_runs.append(
        {
            "id": command_spec["id"],
            "purpose": command_spec["purpose"],
            "result": result,
            "json_paths": json_paths,
            "payloads": payloads,
        }
    )
after = live_state()

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "host": run("hostname", timeout=20)["stdout"],
    "workspace": str(WORKSPACE),
    "before": before,
    "after": after,
    "tool_runs": tool_runs,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
'''


COMMANDS = [
    {
        "id": "personal_inventory",
        "purpose": "refresh read-only NAS Personal inventory and SQLite index",
        "command": "bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_personal_inventory",
        "timeout": 300,
    },
    {
        "id": "file_search",
        "purpose": "demo natural-language file search over indexed metadata",
        "command": "bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_file_search '2024 renovation invoice'",
        "timeout": 180,
    },
    {
        "id": "case_packet",
        "purpose": "demo grounded evidence packet for renovation payment documents",
        "command": "bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_case_packet '2024 renovation payment contract invoice receipt chat screenshot'",
        "timeout": 240,
    },
    {
        "id": "folder_rag",
        "purpose": "demo folder-scoped grounded answer over Documents",
        "command": "bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_folder_rag Documents 'What payment dates and amounts are in this folder?'",
        "timeout": 180,
    },
    {
        "id": "duplicate_report",
        "purpose": "demo report-only duplicate detection with no deletion",
        "command": "bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_duplicate_report",
        "timeout": 180,
    },
    {
        "id": "movie_sort_enhanced",
        "purpose": "demo non-destructive movie organization suggestions without copy",
        "command": "bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_movie_sort_enhanced",
        "timeout": 180,
    },
    {
        "id": "edge_cloud_router",
        "purpose": "demo privacy-first local/cloud router in dry-run cloud mode",
        "command": "bash scripts/probes/ai_nas_allowlisted_tool.sh ai_nas_edge_cloud_router",
        "timeout": 180,
    },
]


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
    source = REMOTE_PROBE.replace("__WORKSPACE__", json.dumps(args.remote_workspace)).replace(
        "__COMMANDS__", json.dumps(COMMANDS, ensure_ascii=False)
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


def active_live_state(state: dict[str, Any]) -> bool:
    services = state.get("services") or {}
    health = state.get("health") or {}
    return all(item.get("active") is True for item in services.values()) and all(
        item.get("ok") is True for item in health.values()
    )


def mutation_violation(flags: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key in ["source_files_modified", "delete_performed", "move_performed", "overwrite_performed", "copy_sort_executed"]:
        if flags.get(key) is True:
            failures.append(key)
    if flags.get("privacy_query_sent_to_cloud") is True:
        failures.append("privacy_query_sent_to_cloud")
    return failures


def evaluate(remote: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not remote.get("ok"):
        errors.append(remote.get("error", "remote_probe_failed"))

    if not active_live_state(remote.get("before") or {}):
        errors.append("before_live_state_not_ready")
    if not active_live_state(remote.get("after") or {}):
        errors.append("after_live_state_not_ready")

    tool_summaries = []
    for run in remote.get("tool_runs") or []:
        result = run.get("result") or {}
        payloads = run.get("payloads") or []
        run_errors: list[str] = []
        if result.get("returncode") != 0:
            run_errors.append("returncode_nonzero")
        if not payloads:
            run_errors.append("no_json_payload_reported")
        payload_verdicts = []
        mutation_failures = []
        for payload in payloads:
            if payload.get("exists") is not True:
                run_errors.append("payload_missing")
            if payload.get("error"):
                run_errors.append("payload_error")
            verdict = payload.get("verdict")
            if verdict:
                payload_verdicts.append(verdict)
                if not str(verdict).startswith(("ok_", "ready_")):
                    run_errors.append(f"verdict_not_ok:{verdict}")
            mutation_failures.extend(mutation_violation(payload.get("mutation_flags") or {}))
        if mutation_failures:
            run_errors.extend(f"mutation_flag:{item}" for item in sorted(set(mutation_failures)))
        if run_errors:
            errors.extend(f"{run.get('id')}:{item}" for item in sorted(set(run_errors)))
        tool_summaries.append(
            {
                "id": run.get("id"),
                "purpose": run.get("purpose"),
                "returncode": result.get("returncode"),
                "elapsed_ms": result.get("elapsed_ms"),
                "json_paths": run.get("json_paths") or [],
                "verdicts": payload_verdicts,
                "errors": sorted(set(run_errors)),
            }
        )

    return {
        "verdict": "ok_ai_nas_route_a_demo_readiness_packet" if not errors else "failed_ai_nas_route_a_demo_readiness_packet",
        "ready": not errors,
        "errors": errors,
        "tool_summaries": tool_summaries,
        "policy": {
            "cloud_execution": "dry-run only",
            "source_mutation": "forbidden",
            "allowed_dispatcher": "scripts/probes/ai_nas_allowlisted_tool.sh",
        },
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    remote = run_remote_probe(args)
    evaluation = evaluate(remote)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": evaluation["verdict"],
        "remote": remote,
        "evaluation": evaluation,
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    evaluation = payload["evaluation"]
    remote = payload["remote"]
    lines = [
        "# AI-NAS Route A Demo Readiness Packet",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- ready: `{evaluation['ready']}`",
        f"- error_count: `{len(evaluation['errors'])}`",
        "",
        "## Live State",
        "",
        f"- before_ready: `{active_live_state(remote.get('before') or {})}`",
        f"- after_ready: `{active_live_state(remote.get('after') or {})}`",
        "",
        "## Tool Runs",
        "",
    ]
    for item in evaluation["tool_summaries"]:
        lines.append(
            f"- `{item['id']}` returncode `{item['returncode']}` elapsed_ms `{item['elapsed_ms']}` "
            f"verdicts `{item['verdicts']}` errors `{item['errors']}`"
        )
        for json_path in item["json_paths"]:
            lines.append(f"  - `{json_path}`")
    lines.extend(["", "## Errors", ""])
    if evaluation["errors"]:
        lines.extend(f"- `{error}`" for error in evaluation["errors"])
    else:
        lines.append("- none")
    lines.extend(["", "## Policy", ""])
    for key, value in evaluation["policy"].items():
        lines.append(f"- {key}: `{value}`")
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
            str(report_dir / "ai_nas_route_a_demo_readiness_packet.json"),
            str(report_dir / "ai_nas_route_a_demo_readiness_packet.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--remote-workspace", default=DEFAULT_REMOTE_WORKSPACE)
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--remote-timeout", type=int, default=1500)
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.out_root) / f"ai_nas_route_a_demo_readiness_packet_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "ai_nas_route_a_demo_readiness_packet.json"
    md_path = report_dir / "ai_nas_route_a_demo_readiness_packet.md"
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
    latest_json = Path(args.out_root) / "ai_nas_route_a_demo_readiness_packet_latest.json"
    latest_md = Path(args.out_root) / "ai_nas_route_a_demo_readiness_packet_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["evaluation"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
