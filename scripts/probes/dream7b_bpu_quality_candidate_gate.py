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
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


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
        command = (
            "sudo -n env XDG_RUNTIME_DIR=/run/user/0 "
            f"systemctl --user is-active {name}"
        )
    else:
        command = f"systemctl is-active {name}"
    result = run(command)
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


def path_info(path):
    p = Path(path)
    exists = p.exists()
    is_dir = p.is_dir()
    manifest = p / "manifest.sha256"
    return {
        "path": path,
        "exists": exists,
        "is_dir": is_dir,
        "manifest_sha256_exists": manifest.exists(),
    }


def command_exists(name):
    result = run(f"command -v {name}")
    return {
        "name": name,
        "exists": result["returncode"] == 0,
        "path": result["stdout"],
    }


compile_processes = run(
    "ps -eo pid,comm,args | grep -E "
    "'(oellm|hbdk|compile_dream|Compile-Dream|cmake|ninja|make|gcc|g\\+\\+)' "
    "| grep -v grep || true"
)

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "host": run("hostname")["stdout"],
    "services": {
        "dream7b_bpu_batch_queue": service_state("dream7b-bpu-batch-queue.service"),
        "dream7b_local_openai_gateway": service_state(
            "dream7b-local-openai-gateway.service", root_user=True
        ),
        "openclaw_gateway": service_state("openclaw-gateway.service", root_user=True),
    },
    "health": {
        "gateway_18888": http_json("http://127.0.0.1:18888/health"),
        "openclaw_18789": http_json("http://127.0.0.1:18789/health"),
    },
    "tools": {
        "dream7b_default_status": command_exists("dream7b-default-status"),
    },
    "baseline_paths": {
        "fine_seq16": path_info("/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16"),
        "true_batch_seq16_b4": path_info(
            "/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4"
        ),
        "last_token_final_candidate_root": path_info(
            "/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4-last-token-final"
        ),
        "reports_models_root": path_info("/mnt/nas/openclaw/reports/models"),
    },
    "route_a_evidence": {
        "fast_path_regression": path_info(
            "/mnt/nas/openclaw/reports/models/"
            "dream7b_fast_path_regression_20260622-174547/"
            "dream7b_fast_path_regression.json"
        ),
        "first_response_slo": path_info(
            "/mnt/nas/openclaw/reports/models/"
            "dream7b_first_response_slo_tier_guard_20260622-174823/"
            "dream7b_first_response_slo_tier_guard.json"
        ),
        "openclaw_entry_demo": path_info(
            "/mnt/nas/openclaw/reports/models/"
            "openclaw_entry_demo_20260622-174732/openclaw_entry_demo.json"
        ),
    },
    "compile_processes": {
        "active": bool(compile_processes["stdout"]),
        "ps": compile_processes,
    },
    "audit": {
        "compile_started": False,
        "runtime_started": False,
        "service_restarted": False,
        "production_write_performed": False,
    },
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
'''


DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_MODEL_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"


def run_cmd(command: list[str], timeout: int) -> dict[str, Any]:
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


def ssh_command(args: argparse.Namespace, remote_command: str, timeout: int = 60) -> dict[str, Any]:
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
            remote_command,
        ],
        timeout,
    )


def run_remote_probe(args: argparse.Namespace) -> dict[str, Any]:
    encoded = base64.b64encode(REMOTE_PROBE.encode("utf-8")).decode("ascii")
    command = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}').decode('utf-8'))\""
    result = ssh_command(args, command, timeout=args.remote_timeout)
    if result["returncode"] != 0:
        return {
            "ok": False,
            "error": "remote_probe_failed",
            "ssh": result,
        }
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"remote_probe_json_decode_failed:{exc}",
            "ssh": result,
        }
    payload["ok"] = True
    return payload


def file_contains(path: Path, needles: list[str]) -> dict[str, Any]:
    exists = path.exists()
    text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
    return {
        "path": str(path),
        "exists": exists,
        "contains": {needle: needle in text for needle in needles},
    }


def build_local_context() -> dict[str, Any]:
    compiler = Path("tmp/wsl_compile_dream_full_forward.py")
    return {
        "diagnosis_docs": {
            "logits_diagnosis": file_contains(
                Path("docs/dream7b_bpu_logits_diagnosis_2026-06-22.md"),
                ["seg21_24", "seg24_26", "lm_head", "argmax match >80%"],
            ),
            "seq16_quality_root_cause": file_contains(
                Path("docs/dream7b_bpu_seq16_quality_root_cause_2026-06-22.md"),
                ["truncate_prompt_keep_min_masks", "fine-seq128", "fine-seq256"],
            ),
        },
        "compiler_capability": {
            "script": file_contains(
                compiler,
                [
                    "--seq-len",
                    "--w-bits",
                    "--lm-head-w-bits",
                    "--segment-start",
                    "--segment-end",
                    "--final-logits-mode",
                    "lm_head",
                ],
            )
        },
    }


def all_values_true(values: dict[str, bool]) -> bool:
    return all(values.values())


def evaluate(remote: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not remote.get("ok"):
        errors.append(remote.get("error", "remote_probe_failed"))
    services = remote.get("services") or {}
    for service_id, service in services.items():
        if service.get("active") is not True:
            errors.append(f"service_not_active:{service_id}")

    health = remote.get("health") or {}
    for health_id, item in health.items():
        if item.get("ok") is not True:
            errors.append(f"health_not_ok:{health_id}:{item.get('error')}")

    baseline_paths = remote.get("baseline_paths") or {}
    for path_id in ("fine_seq16", "true_batch_seq16_b4", "reports_models_root"):
        item = baseline_paths.get(path_id) or {}
        if item.get("exists") is not True:
            errors.append(f"baseline_path_missing:{path_id}")

    route_a = remote.get("route_a_evidence") or {}
    for report_id, item in route_a.items():
        if item.get("exists") is not True:
            warnings.append(f"route_a_report_missing:{report_id}")

    if (remote.get("compile_processes") or {}).get("active") is True:
        errors.append("compile_process_active")

    for doc_id, info in (local.get("diagnosis_docs") or {}).items():
        if info.get("exists") is not True:
            errors.append(f"diagnosis_doc_missing:{doc_id}")
        elif not all_values_true(info.get("contains") or {}):
            errors.append(f"diagnosis_doc_incomplete:{doc_id}")

    compiler = ((local.get("compiler_capability") or {}).get("script") or {})
    if compiler.get("exists") is not True:
        errors.append("compiler_script_missing")
    elif not all_values_true(compiler.get("contains") or {}):
        errors.append("compiler_script_lacks_required_flags")

    route_b_candidates = [
        {
            "id": "bpu_logits_quality_candidate",
            "purpose": "Recover BPU logits quality before any chat promotion.",
            "compile_scope": [
                "lm_head with w_bits=16",
                "late segments seg21_24, seg24_26, seg26_28 with higher precision or calibration",
            ],
            "must_verify": [
                "argmax_match_gt_80_percent",
                "top1_probability_gt_5_percent",
                "three_prompt_readable_chinese_generation",
            ],
            "admitted_next_action": "prepare_compile_bundle_and_parameter_plan_only",
            "compile_now_admitted": False,
        },
        {
            "id": "bpu_larger_window_candidate",
            "purpose": "Remove seq16 truncation for future BPU chat experiments.",
            "compile_scope": ["isolated fine-seq128 or fine-seq256 HBM artifacts"],
            "must_verify": [
                "no_truncate_prompt_keep_min_masks_for_normal_prompts",
                "readable_chinese_generation",
                "same_workload_latency_and_memory_report",
            ],
            "admitted_next_action": "verify_seq_len_parameterization_and_capacity_plan_only",
            "compile_now_admitted": False,
        },
    ]

    verdict = (
        "ok_dream7b_bpu_quality_candidate_gate"
        if not errors
        else "blocked_dream7b_bpu_quality_candidate_gate"
    )
    return {
        "verdict": verdict,
        "errors": errors,
        "warnings": warnings,
        "route_b_decision": {
            "production_chat_default": "OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF",
            "bpu_current_role": "queue-batch throughput and telemetry baseline",
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
            "do_not_start_compile_from_this_gate": True,
            "next_admitted_work": [
                "prepare BPU quality compile bundle",
                "verify compiler parameter support for seq_len, w_bits, segment selection, final logits mode",
                "write a separate compile capacity gate before any HBM build",
            ],
        },
        "route_b_candidates": route_b_candidates,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    evaluation = payload["evaluation"]
    remote = payload["remote"]
    lines = [
        "# Dream7B BPU Quality Candidate Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{evaluation['verdict']}`",
        f"- compile_started: `{remote.get('audit', {}).get('compile_started')}`",
        f"- service_restarted: `{remote.get('audit', {}).get('service_restarted')}`",
        f"- production_write_performed: `{remote.get('audit', {}).get('production_write_performed')}`",
        "",
        "## Decision",
        "",
        "- Route A remains the product path: OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF.",
        "- Route B remains isolated BPU R&D. It may prepare candidate bundles, but this gate does not admit compile, service replacement, or 18888 changes.",
        "- Current BPU seq16 artifacts stay as the queue-batch throughput and telemetry baseline.",
        "",
        "## Guardrail",
        "",
    ]
    services = remote.get("services") or {}
    for service_id, service in services.items():
        lines.append(f"- {service_id}: active=`{service.get('active')}`")
    health = remote.get("health") or {}
    for health_id, item in health.items():
        lines.append(f"- {health_id}: ok=`{item.get('ok')}` status=`{item.get('status')}`")
    lines.extend(
        [
            f"- compile_process_active: `{(remote.get('compile_processes') or {}).get('active')}`",
            "",
            "## Candidate Order",
            "",
            "1. `bpu_logits_quality_candidate`: q16 or calibrated `lm_head` plus late segments `seg21_24`, `seg24_26`, `seg26_28`.",
            "2. `bpu_larger_window_candidate`: isolated `fine-seq128` or `fine-seq256` artifacts after capacity planning.",
            "",
            "## Acceptance Before Promotion",
            "",
            "- logits argmax agreement above 80 percent.",
            "- top-1 probability above 5 percent, not near-uniform logits.",
            "- readable Chinese output on at least three prompts.",
            "- same-workload latency and rollback report.",
            "- Route A services and NAS evidence remain unchanged.",
            "",
            "## Errors",
            "",
        ]
    )
    if evaluation["errors"]:
        lines.extend(f"- `{item}`" for item in evaluation["errors"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if evaluation["warnings"]:
        lines.extend(f"- `{item}`" for item in evaluation["warnings"])
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
            str(report_dir / "dream7b_bpu_quality_candidate_gate.json"),
            str(report_dir / "dream7b_bpu_quality_candidate_gate.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {
        "ok": scp["returncode"] == 0,
        "remote_dir": remote_dir,
        "scp": scp,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--remote-report-root", default=DEFAULT_MODEL_REPORT_ROOT)
    parser.add_argument("--remote-timeout", type=int, default=90)
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.out_root) / f"dream7b_bpu_quality_candidate_gate_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    remote = run_remote_probe(args)
    local = build_local_context()
    evaluation = evaluate(remote, local)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": evaluation["verdict"],
        "local": local,
        "remote": remote,
        "evaluation": evaluation,
        "report_dir": str(report_dir),
    }

    json_path = report_dir / "dream7b_bpu_quality_candidate_gate.json"
    md_path = report_dir / "dream7b_bpu_quality_candidate_gate.md"
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

    latest_json = Path(args.out_root) / "dream7b_bpu_quality_candidate_gate_latest.json"
    latest_md = Path(args.out_root) / "dream7b_bpu_quality_candidate_gate_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if evaluation["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
