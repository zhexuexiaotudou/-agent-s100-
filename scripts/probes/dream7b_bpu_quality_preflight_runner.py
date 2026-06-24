#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PACK_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_candidate_pack_latest.json")
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"


def run_shell(command: str, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
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
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
        }


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


def parse_state_dict_report(stdout: str) -> dict[str, Any]:
    marker = '"verdict": "ok_state_dict_report"'
    if marker not in stdout:
        return {"ok": False, "error": "state_dict_report_json_missing"}
    start = stdout.rfind("{", 0, stdout.find(marker))
    if start < 0:
        return {"ok": False, "error": "state_dict_report_json_start_missing"}
    try:
        parsed = json.loads(stdout[start:])
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"state_dict_report_json_decode_failed:{exc}"}
    return {"ok": parsed.get("verdict") == "ok_state_dict_report", "report": parsed}


def parse_preflight(stdout: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for line in stdout.splitlines():
        if not line.startswith("preflight_") and not line.startswith("verdict="):
            continue
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        value: Any = raw_value.strip()
        try:
            value = float(value)
        except ValueError:
            pass
        fields[key.strip()] = value
    return {
        "ok": fields.get("verdict") == "preflight_ok",
        "fields": fields,
        "error": "" if fields.get("verdict") == "preflight_ok" else "preflight_ok_missing",
    }


def selected_candidates(pack: dict[str, Any], ids: set[str]) -> list[dict[str, Any]]:
    candidates = list(pack.get("candidates") or [])
    if not ids:
        return candidates[:1]
    return [candidate for candidate in candidates if candidate.get("id") in ids]


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    pack_path = Path(args.pack_json)
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    wanted = set(args.candidate_id or [])
    candidates = selected_candidates(pack, wanted)
    errors: list[str] = []
    if not candidates:
        errors.append("no_candidates_selected")
    if pack.get("verdict") != "ok_dream7b_bpu_quality_candidate_pack":
        errors.append("candidate_pack_not_ok")

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        commands = candidate.get("commands") or {}
        candidate_result: dict[str, Any] = {
            "id": candidate.get("id"),
            "rank": candidate.get("rank"),
            "scope": candidate.get("scope"),
            "state_dict_reports": {},
            "compile_preflight": None,
            "compile_started": False,
            "runtime_started": False,
            "service_restarted": False,
            "production_write_performed": False,
        }
        if args.run_state_dict:
            by_segment = commands.get("state_dict_report_only_by_segment") or {}
            for segment, command in by_segment.items():
                run = run_shell(command, timeout=args.state_dict_timeout)
                parsed = parse_state_dict_report(run.get("stdout") or "")
                if run["returncode"] != 0 or not parsed.get("ok"):
                    errors.append(f"state_dict_preflight_failed:{candidate.get('id')}:{segment}")
                candidate_result["state_dict_reports"][segment] = {
                    "run": run,
                    "parsed": parsed,
                }
        if args.run_compile_preflight:
            command = commands.get("compile_preflight_only")
            if not command:
                errors.append(f"compile_preflight_command_missing:{candidate.get('id')}")
            else:
                run = run_shell(command, timeout=args.compile_preflight_timeout)
                parsed = parse_preflight(run.get("stdout") or "")
                if run["returncode"] != 0 or not parsed.get("ok"):
                    errors.append(f"compile_preflight_failed:{candidate.get('id')}")
                candidate_result["compile_preflight"] = {
                    "run": run,
                    "parsed": parsed,
                }
        results.append(candidate_result)

    verdict = "ok_dream7b_bpu_quality_preflight_runner" if not errors else "blocked_dream7b_bpu_quality_preflight_runner"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "errors": errors,
        "source_pack_json": str(pack_path),
        "selected_candidate_ids": [candidate.get("id") for candidate in candidates],
        "run_state_dict": args.run_state_dict,
        "run_compile_preflight": args.run_compile_preflight,
        "policy": {
            "compile_started": False,
            "runtime_started": False,
            "service_restarted": False,
            "production_write_performed": False,
            "compile_allowed_now": False,
        },
        "results": results,
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B BPU Quality Preflight Runner",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- selected_candidate_ids: `{payload['selected_candidate_ids']}`",
        "- compile_started: `False`",
        "- service_restarted: `False`",
        "- production_write_performed: `False`",
        "",
        "## Results",
        "",
    ]
    for result in payload["results"]:
        lines.append(f"### {result['id']}")
        state_reports = result.get("state_dict_reports") or {}
        if state_reports:
            lines.append("")
            lines.append("State-dict reports:")
            for segment, report in state_reports.items():
                parsed = report.get("parsed") or {}
                run = report.get("run") or {}
                state = (parsed.get("report") or {})
                lines.append(
                    f"- `{segment}`: ok=`{parsed.get('ok')}` returncode=`{run.get('returncode')}` "
                    f"elapsed_sec=`{run.get('elapsed_sec')}` tensors=`{state.get('tensor_count')}` "
                    f"seq_len=`{state.get('seq_len')}` lm_head_w_bits=`{state.get('lm_head_w_bits')}`"
                )
        preflight = result.get("compile_preflight")
        if preflight:
            parsed = preflight.get("parsed") or {}
            run = preflight.get("run") or {}
            fields = parsed.get("fields") or {}
            lines.append("")
            lines.append("Compile preflight:")
            lines.append(
                f"- ok=`{parsed.get('ok')}` returncode=`{run.get('returncode')}` "
                f"elapsed_sec=`{run.get('elapsed_sec')}` headroom_gb=`{fields.get('preflight_commit_headroom_gb')}` "
                f"min_headroom_gb=`{fields.get('preflight_min_commit_headroom_gb')}`"
            )
    lines.extend(["", "## Errors", ""])
    if payload["errors"]:
        lines.extend(f"- `{error}`" for error in payload["errors"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ssh_command(args: argparse.Namespace, command: str, timeout: int = 60) -> dict[str, Any]:
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
            str(report_dir / "dream7b_bpu_quality_preflight_runner.json"),
            str(report_dir / "dream7b_bpu_quality_preflight_runner.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-json", default=str(DEFAULT_PACK_JSON))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--candidate-id", action="append", default=[])
    parser.add_argument("--run-state-dict", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-compile-preflight", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--state-dict-timeout", type=int, default=900)
    parser.add_argument("--compile-preflight-timeout", type=int, default=300)
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.out_root) / f"dream7b_bpu_quality_preflight_runner_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_preflight_runner.json"
    md_path = report_dir / "dream7b_bpu_quality_preflight_runner.md"
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

    latest_json = Path(args.out_root) / "dream7b_bpu_quality_preflight_runner_latest.json"
    latest_md = Path(args.out_root) / "dream7b_bpu_quality_preflight_runner_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
