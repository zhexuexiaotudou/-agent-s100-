#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_SIZING = DEFAULT_ROOT / "dream7b_b4_final_logits_candidate_sizing_20260619.json"
DEFAULT_READINESS = DEFAULT_ROOT / "dream7b_b4_last_token_compile_readiness_20260619.json"
DEFAULT_EXPERIMENT_MD = DEFAULT_ROOT / "dream7b_b4_last_token_final_logits_experiment_20260619.md"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_last_token_experiment_gate_20260620.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_last_token_experiment_gate_20260620.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cmd(args: list[str], timeout: int = 30) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def ssh_cmd(args: argparse.Namespace, remote_command: str, timeout: int = 30) -> dict[str, Any]:
    return run_cmd(
        [
            "ssh.exe",
            "-i",
            str(args.ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            remote_command,
        ],
        timeout=timeout,
    )


def py_parse_ok(path: Path) -> bool:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return False
    return True


def text_has_all(path: Path, needles: list[str]) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return all(needle in text for needle in needles)


def powershell_support(path: Path) -> dict[str, Any]:
    required = [
        "[ValidateSet(\"full\", \"last-token\")]",
        "$FinalLogitsMode",
        "-last-token-final",
        "_last_token_logits",
        "FinalLogitsMode '$FinalLogitsMode' is only valid for final segment 27:28",
    ]
    return {
        "path": str(path),
        "found": path.exists(),
        "supports_final_logits_mode": text_has_all(path, required),
        "required_markers": required,
    }


def local_probe_support(path: Path) -> dict[str, Any]:
    required = [
        "--final-hbm-root",
        "--final-logits-mode",
        "choices=[\"full\", \"last-token\"]",
        "final_logits_seq_len",
        "_last_token_logits",
        "expected_final_shape",
    ]
    return {
        "path": str(path),
        "found": path.exists(),
        "python_parse_ok": py_parse_ok(path),
        "supports_last_token_runtime": text_has_all(path, required),
        "required_markers": required,
    }


def compiler_support(path: Path) -> dict[str, Any]:
    required = [
        "final-logits-mode",
        "last-token",
        "final_logits_mode",
    ]
    return {
        "path": str(path),
        "found": path.exists(),
        "python_parse_ok": py_parse_ok(path),
        "supports_last_token_compile": text_has_all(path, required),
        "required_markers": required,
    }


def remote_probe_support(args: argparse.Namespace) -> dict[str, Any]:
    command = f"{args.remote_python} {args.remote_probe} --help"
    result = ssh_cmd(args, command, timeout=args.remote_timeout_sec)
    help_text = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
    return {
        "path": args.remote_probe,
        "python": args.remote_python,
        "command": command,
        "returncode": result.get("returncode"),
        "supports_final_hbm_root": "--final-hbm-root" in help_text,
        "supports_final_logits_mode": "--final-logits-mode" in help_text
        and "last-token" in help_text,
        "help_excerpt": "\n".join(
            line
            for line in help_text.splitlines()
            if "--final-hbm-root" in line or "--final-logits-mode" in line
        ),
        "raw": result,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    sizing = read_json(args.sizing_json)
    readiness = read_json(args.readiness_json)
    candidate = sizing.get("last_token_logits_candidate") or {}
    current = sizing.get("current") or {}
    compile_wrapper = powershell_support(args.compile_wrapper)
    compiler = compiler_support(args.compiler_py)
    local_probe = local_probe_support(args.local_probe)
    remote_probe = remote_probe_support(args)
    remote = readiness.get("remote") or {}
    blockers = list(readiness.get("blockers") or [])

    expected_last_token_shape = candidate.get("target_shape")
    runtime_shape_gate_ready = expected_last_token_shape == [
        args.batch_size,
        1,
        args.vocab_size,
    ]
    code_support_ready = (
        compile_wrapper["supports_final_logits_mode"]
        and compiler["supports_last_token_compile"]
        and local_probe["python_parse_ok"]
        and local_probe["supports_last_token_runtime"]
        and remote_probe["supports_final_hbm_root"]
        and remote_probe["supports_final_logits_mode"]
        and runtime_shape_gate_ready
    )
    compile_ready = readiness.get("compile_ready") is True
    manifest_ready = remote.get("manifest_verified") is True and remote.get("last_token_hbm_exists") is True
    runtime_validation_ready = readiness.get("runtime_validation_ready") is True and manifest_ready
    experiment_ready = code_support_ready and compile_ready and runtime_validation_ready

    gate_blockers: list[str] = []
    if not code_support_ready:
        gate_blockers.append("last_token_code_support_incomplete")
    if not compile_ready:
        gate_blockers.append("last_token_compile_not_ready")
    if not manifest_ready:
        gate_blockers.append("last_token_manifest_not_ready")
    if not runtime_validation_ready:
        gate_blockers.append("last_token_runtime_validation_not_ready")

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": "ready_dream7b_b4_last_token_experiment_gate"
        if experiment_ready
        else "blocked_dream7b_b4_last_token_experiment_gate",
        "candidate": "seg27_28_last_token_logits",
        "source_paths": {
            "sizing": str(args.sizing_json),
            "readiness": str(args.readiness_json),
            "experiment_plan": str(args.experiment_md) if args.experiment_md.exists() else None,
            "compile_wrapper": str(args.compile_wrapper),
            "compiler_py": str(args.compiler_py),
            "local_probe": str(args.local_probe),
            "remote_probe": args.remote_probe,
        },
        "current": {
            "shape": current.get("final_shape"),
            "final_excess_ms_per_request_if_hidden_speed": current.get(
                "final_excess_ms_per_request_if_hidden_speed"
            ),
            "final_run_ms_per_request": current.get("final_run_ms_per_request"),
            "final_segment_overhead_ms_per_request": current.get(
                "final_segment_overhead_ms_per_request"
            ),
        },
        "candidate_shape": {
            "target_shape": expected_last_token_shape,
            "output_element_reduction_vs_current": candidate.get(
                "output_element_reduction_vs_current"
            ),
            "projection_only_hypothesis_saved_ms_per_request": candidate.get(
                "projection_only_hypothesis_saved_ms_per_request"
            ),
            "projection_only_hypothesis_final_run_ms_per_request": candidate.get(
                "projection_only_hypothesis_final_run_ms_per_request"
            ),
            "runtime_shape_gate_ready": runtime_shape_gate_ready,
        },
        "code_support": {
            "ready": code_support_ready,
            "compile_wrapper": compile_wrapper,
            "compiler": compiler,
            "local_probe": local_probe,
            "remote_probe": {key: value for key, value in remote_probe.items() if key != "raw"},
        },
        "compile_readiness": {
            "verdict": readiness.get("verdict"),
            "compile_ready": compile_ready,
            "runtime_validation_ready": readiness.get("runtime_validation_ready"),
            "blockers": blockers,
            "commit_headroom_gb": ((readiness.get("preflight") or {}).get("values") or {}).get(
                "commit_headroom_gb"
            ),
            "commit_headroom_deficit_gb": (
                (readiness.get("preflight") or {}).get("values") or {}
            ).get("commit_headroom_deficit_gb"),
            "large_private_process_count": len(readiness.get("large_private_processes") or []),
        },
        "remote_manifest": {
            "final_hbm_root": remote.get("final_hbm_root"),
            "segment_dir": remote.get("segment_dir"),
            "hbm_path": remote.get("hbm_path"),
            "final_hbm_root_exists": remote.get("final_hbm_root_exists"),
            "last_token_hbm_exists": remote.get("last_token_hbm_exists"),
            "manifest_exists": remote.get("manifest_exists"),
            "manifest_verified": remote.get("manifest_verified"),
        },
        "summary": {
            "code_support_ready": code_support_ready,
            "compile_ready": compile_ready,
            "manifest_ready": manifest_ready,
            "runtime_validation_ready": runtime_validation_ready,
            "experiment_ready": experiment_ready,
            "gate_blockers": gate_blockers,
        },
        "next_actions": [
            "Keep queue-batch as production default.",
            "Do not run more group-boundary sweeps before this candidate changes the final-logits path.",
            "Free Windows commit headroom or move the single-segment compile to a host with enough commit capacity.",
            "Compile only seg27_28 with FinalLogitsMode last-token.",
            "Verify the remote manifest, then run mb512 validation with --final-hbm-root and --final-logits-mode last-token.",
        ],
        "audit": {
            "compile_started": False,
            "runtime_probe_started": False,
            "service_restarted": False,
            "remote_write_performed": False,
            "local_writes": "JSON/Markdown gate report only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    shape = payload["candidate_shape"]
    compile_readiness = payload["compile_readiness"]
    remote = payload["remote_manifest"]
    lines = [
        "# Dream7B B4 Last-Token Experiment Gate",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate: `{payload['candidate']}`",
        f"- code_support_ready: `{summary['code_support_ready']}`",
        f"- compile_ready: `{summary['compile_ready']}`",
        f"- manifest_ready: `{summary['manifest_ready']}`",
        f"- runtime_validation_ready: `{summary['runtime_validation_ready']}`",
        f"- experiment_ready: `{summary['experiment_ready']}`",
        f"- gate_blockers: `{summary['gate_blockers']}`",
        "",
        "## Candidate Shape",
        "",
        f"- current_shape: `{payload['current']['shape']}`",
        f"- target_shape: `{shape['target_shape']}`",
        f"- output_element_reduction_vs_current: `{shape['output_element_reduction_vs_current']}`",
        f"- projection_only_hypothesis_saved_ms_per_request: `{shape['projection_only_hypothesis_saved_ms_per_request']}`",
        f"- runtime_shape_gate_ready: `{shape['runtime_shape_gate_ready']}`",
        "",
        "## Code Support",
        "",
        f"- compile_wrapper_supports_final_logits_mode: `{payload['code_support']['compile_wrapper']['supports_final_logits_mode']}`",
        f"- compiler_supports_last_token_compile: `{payload['code_support']['compiler']['supports_last_token_compile']}`",
        f"- local_probe_supports_last_token_runtime: `{payload['code_support']['local_probe']['supports_last_token_runtime']}`",
        f"- remote_probe_supports_final_hbm_root: `{payload['code_support']['remote_probe']['supports_final_hbm_root']}`",
        f"- remote_probe_supports_final_logits_mode: `{payload['code_support']['remote_probe']['supports_final_logits_mode']}`",
        "",
        "## Compile / Manifest Readiness",
        "",
        f"- readiness_verdict: `{compile_readiness['verdict']}`",
        f"- commit_headroom_gb: `{compile_readiness['commit_headroom_gb']}`",
        f"- commit_headroom_deficit_gb: `{compile_readiness['commit_headroom_deficit_gb']}`",
        f"- large_private_process_count: `{compile_readiness['large_private_process_count']}`",
        f"- readiness_blockers: `{compile_readiness['blockers']}`",
        f"- final_hbm_root: `{remote['final_hbm_root']}`",
        f"- last_token_hbm_exists: `{remote['last_token_hbm_exists']}`",
        f"- manifest_verified: `{remote['manifest_verified']}`",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.extend(["", "## Source Paths", ""])
    for key, value in payload["source_paths"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report-only gate for the Dream7B B4 last-token final-logits experiment."
    )
    parser.add_argument("--sizing-json", type=Path, default=DEFAULT_SIZING)
    parser.add_argument("--readiness-json", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--experiment-md", type=Path, default=DEFAULT_EXPERIMENT_MD)
    parser.add_argument("--compile-wrapper", type=Path, default=Path("scripts/probes/Compile-DreamTrueBatchSegments.ps1"))
    parser.add_argument("--compiler-py", type=Path, default=Path("tmp/wsl_compile_dream_full_forward.py"))
    parser.add_argument(
        "--local-probe",
        type=Path,
        default=Path("scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py"),
    )
    parser.add_argument("--remote-host", default="sunrise@192.168.127.10")
    parser.add_argument("--ssh-key", type=Path, default=Path(r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"))
    parser.add_argument("--known-hosts", type=Path, default=Path(r"C:\Users\zhexu\.ssh\known_hosts"))
    parser.add_argument("--remote-python", default="/mnt/nas/openclaw/runtimes/hbm-runtime-venv/bin/python")
    parser.add_argument(
        "--remote-probe",
        default="/mnt/nas/openclaw/scripts/probes/dream7b_true_batch_group_major_telemetry_probe.py",
    )
    parser.add_argument("--remote-timeout-sec", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--vocab-size", type=int, default=152064)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_md)
    print(args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
