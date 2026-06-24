#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_GATE_JSON = Path("tmp/product_guardrail_snapshots/dream7b_bpu_quality_candidate_gate_latest.json")
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
PYTHON = r"C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def file_contains(path: Path, needles: list[str]) -> dict[str, Any]:
    text = read_text(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "contains": {needle: needle in text for needle in needles},
    }


def all_true(values: dict[str, bool]) -> bool:
    return all(values.values())


def ps_command(*parts: str) -> str:
    return " ".join(parts)


def wsl_state_dict_command(
    *,
    segment_start: int,
    segment_end: int,
    batch_size: int,
    seq_len: int,
    w_bits: int,
    lm_head_w_bits: int = 0,
    final_logits_mode: str = "full",
    output_dir: str,
) -> str:
    extra: list[str] = []
    if lm_head_w_bits:
        extra.extend(["--lm-head-w-bits", str(lm_head_w_bits)])
    if final_logits_mode != "full":
        extra.extend(["--final-logits-mode", final_logits_mode])
    extra.append("--state-dict-report-only")
    inner = " ".join(
        [
            "source /opt/digua/dream-true-batch-venv/bin/activate &&",
            "python -X faulthandler /mnt/f/Project/Digua/tmp/wsl_compile_dream_full_forward.py",
            "--model-dir /mnt/f/Project/Digua/tmp/true_batch_inputs/dream7b-hf",
            f"--output-dir {output_dir}",
            f"--seq-len {seq_len}",
            f"--batch-size {batch_size}",
            f"--segment-start {segment_start}",
            f"--segment-end {segment_end}",
            "--dtype float32",
            "--march nash-e",
            f"--w-bits {w_bits}",
            *extra,
        ]
    )
    return f'wsl.exe -d DiguaTrueBatchBuilder -- bash -lc "{inner}"'


def compile_wrapper_command(
    *,
    segments: str,
    batch_size: int,
    seq_len: int,
    w_bits: int,
    lm_head_w_bits: int = 0,
    final_logits_mode: str = "full",
    remote_output_root: str,
    remote_report_root: str,
    preflight_only: bool,
) -> str:
    parts = [
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File",
        "scripts\\probes\\Compile-DreamTrueBatchSegments.ps1",
        f"-Segments {segments}",
        f"-BatchSize {batch_size}",
        f"-SeqLen {seq_len}",
        f"-WBits {w_bits}",
    ]
    if lm_head_w_bits:
        parts.append(f"-LmHeadWBits {lm_head_w_bits}")
    if final_logits_mode != "full":
        parts.append(f"-FinalLogitsMode {final_logits_mode}")
    parts.extend(
        [
            f"-RemoteOutputRoot {remote_output_root}",
            f"-RemoteReportRoot {remote_report_root}",
        ]
    )
    if preflight_only:
        parts.append("-PreflightOnly")
    return ps_command(*parts)


def build_candidates(stamp: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "seg27_28_lmheadq16_last_token_sentinel",
            "rank": 1,
            "purpose": "Smallest compile sentinel for the lm_head precision fix and final-logits path.",
            "scope": {
                "segments": "27:28",
                "batch_size": 4,
                "seq_len": 16,
                "w_bits": 8,
                "lm_head_w_bits": 16,
                "final_logits_mode": "last-token",
            },
            "remote_output_root": "/mnt/nas/openclaw/models/dream7b-hbm/bpu-quality-seq16-b4-lmheadq16-last-token",
            "remote_report_root": f"/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_lmheadq16_compile_{stamp}",
        },
        {
            "id": "seg21_28_lateq16_quality_set",
            "rank": 2,
            "purpose": "Repair the late-layer saturation diagnosed in seg21_24 and seg24_26.",
            "scope": {
                "segments": "21:24,24:26,26:28",
                "batch_size": 1,
                "seq_len": 16,
                "w_bits": 16,
                "lm_head_w_bits": 16,
                "final_logits_mode": "full",
            },
            "remote_output_root": "/mnt/nas/openclaw/models/dream7b-hbm/bpu-quality-seq16-b1-lateq16",
            "remote_report_root": f"/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_lateq16_compile_{stamp}",
        },
        {
            "id": "seg27_28_seq128_lmheadq16_state_dict_sentinel",
            "rank": 3,
            "purpose": "First larger-window parameterization probe; not a full seq128 HBM set.",
            "scope": {
                "segments": "27:28",
                "batch_size": 1,
                "seq_len": 128,
                "w_bits": 8,
                "lm_head_w_bits": 16,
                "final_logits_mode": "last-token",
            },
            "remote_output_root": "/mnt/nas/openclaw/models/dream7b-hbm/bpu-quality-seq128-b1-lmheadq16-last-token",
            "remote_report_root": f"/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_seq128_compile_{stamp}",
        },
        {
            "id": "seg27_28_seq256_lmheadq16_state_dict_sentinel",
            "rank": 4,
            "purpose": "Second larger-window parameterization probe for seq256 feasibility; not a full seq256 HBM set.",
            "scope": {
                "segments": "27:28",
                "batch_size": 1,
                "seq_len": 256,
                "w_bits": 8,
                "lm_head_w_bits": 16,
                "final_logits_mode": "last-token",
            },
            "remote_output_root": "/mnt/nas/openclaw/models/dream7b-hbm/bpu-quality-seq256-b1-lmheadq16-last-token",
            "remote_report_root": f"/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_seq256_compile_{stamp}",
        },
    ]


def attach_commands(candidates: list[dict[str, Any]], stamp: str) -> None:
    for candidate in candidates:
        scope = candidate["scope"]
        segment_specs = [part.strip() for part in str(scope["segments"]).split(",") if part.strip()]
        stage_name = candidate["id"]
        state_dict_commands: dict[str, str] = {}
        for segment_spec in segment_specs:
            start, end = [int(part) for part in segment_spec.split(":")]
            state_dict_commands[segment_spec] = wsl_state_dict_command(
                segment_start=start,
                segment_end=end,
                batch_size=int(scope["batch_size"]),
                seq_len=int(scope["seq_len"]),
                w_bits=int(scope["w_bits"]),
                lm_head_w_bits=int(scope["lm_head_w_bits"]),
                final_logits_mode=str(scope["final_logits_mode"]),
                output_dir=(
                    f"/mnt/f/Project/Digua/tmp/bpu_quality_candidate_stage/{stamp}/"
                    f"{stage_name}/state_dict/seg{start:02d}_{end:02d}"
                ),
            )
        candidate["commands"] = {
            "state_dict_report_only_by_segment": state_dict_commands,
            "state_dict_report_only": "\n".join(state_dict_commands.values()),
            "compile_preflight_only": compile_wrapper_command(
                segments=str(scope["segments"]),
                batch_size=int(scope["batch_size"]),
                seq_len=int(scope["seq_len"]),
                w_bits=int(scope["w_bits"]),
                lm_head_w_bits=int(scope["lm_head_w_bits"]),
                final_logits_mode=str(scope["final_logits_mode"]),
                remote_output_root=str(candidate["remote_output_root"]),
                remote_report_root=str(candidate["remote_report_root"]),
                preflight_only=True,
            ),
            "compile_after_capacity_gate_only": compile_wrapper_command(
                segments=str(scope["segments"]),
                batch_size=int(scope["batch_size"]),
                seq_len=int(scope["seq_len"]),
                w_bits=int(scope["w_bits"]),
                lm_head_w_bits=int(scope["lm_head_w_bits"]),
                final_logits_mode=str(scope["final_logits_mode"]),
                remote_output_root=str(candidate["remote_output_root"]),
                remote_report_root=str(candidate["remote_report_root"]),
                preflight_only=False,
            ),
        }
        candidate["admission"] = {
            "state_dict_report_allowed_now": True,
            "compile_preflight_allowed_now": True,
            "compile_allowed_now": False,
            "compile_requires": [
                "fresh quality candidate gate ok",
                "fresh compile capacity gate ok",
                "explicit operator decision to spend compile time",
            ],
        }


def build_payload(args: argparse.Namespace, report_dir: Path, stamp: str) -> dict[str, Any]:
    gate = json.loads(Path(args.gate_json).read_text(encoding="utf-8"))
    candidates = build_candidates(stamp)
    attach_commands(candidates, stamp)

    compiler = Path("tmp/wsl_compile_dream_full_forward.py")
    local_checks = {
        "quality_gate_verdict": gate.get("verdict"),
        "compiler_py_compile": run_cmd([PYTHON, "-m", "py_compile", str(compiler)]),
        "compiler_flags": file_contains(
            compiler,
            ["--lm-head-w-bits", "lm_head_w_bits", "_lmheadq", "--state-dict-report-only"],
        ),
        "windows_compile_wrapper": file_contains(
            Path("scripts/probes/Compile-DreamTrueBatchSegments.ps1"),
            ["LmHeadWBits", "--lm-head-w-bits", "_lmheadq"],
        ),
        "wsl_compile_wrapper": file_contains(
            Path("scripts/probes/dream7b_true_batch_compile_segments_wsl.sh"),
            ["LM_HEAD_W_BITS", "--lm-head-w-bits", "_lmheadq"],
        ),
        "nas_compile_wrapper": file_contains(
            Path("scripts/probes/compile_dream_true_batch_segments.sh"),
            ["LM_HEAD_W_BITS", "--lm-head-w-bits", "_lmheadq"],
        ),
    }
    errors: list[str] = []
    if gate.get("verdict") != "ok_dream7b_bpu_quality_candidate_gate":
        errors.append("quality_candidate_gate_not_ok")
    if local_checks["compiler_py_compile"]["returncode"] != 0:
        errors.append("compiler_py_compile_failed")
    for check_id in ("compiler_flags", "windows_compile_wrapper", "wsl_compile_wrapper", "nas_compile_wrapper"):
        check = local_checks[check_id]
        if check.get("exists") is not True:
            errors.append(f"missing:{check_id}")
        elif not all_true(check.get("contains") or {}):
            errors.append(f"incomplete:{check_id}")

    verdict = "ok_dream7b_bpu_quality_candidate_pack" if not errors else "blocked_dream7b_bpu_quality_candidate_pack"
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "errors": errors,
        "source_gate_json": str(args.gate_json),
        "local_checks": local_checks,
        "candidate_policy": {
            "compile_started": False,
            "runtime_started": False,
            "service_restarted": False,
            "production_write_performed": False,
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
            "compile_commands_are_not_admitted_until_capacity_gate": True,
        },
        "candidates": candidates,
        "verification_after_compile": [
            "sha256sum -c manifest.sha256 for every produced segment",
            "rerun BPU logits diagnostic against GGUF reference",
            "require argmax_match_gt_80_percent",
            "require top1_probability_gt_5_percent",
            "run dream7b-bpu-diffusion-generate on three Chinese prompts",
            "produce same-workload latency and rollback report",
        ],
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dream7B BPU Quality Candidate Pack",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        "- compile_started: `False`",
        "- service_restarted: `False`",
        "- production_write_performed: `False`",
        "",
        "## Boundary",
        "",
        "This pack prepares Route B candidates only. It does not admit HBM compilation, service replacement, 18888 changes, or seq16 deletion.",
        "",
        "## Candidate Order",
        "",
    ]
    for candidate in payload["candidates"]:
        scope = candidate["scope"]
        lines.extend(
            [
                f"{candidate['rank']}. `{candidate['id']}`",
                f"   - purpose: {candidate['purpose']}",
                f"   - scope: segments `{scope['segments']}`, batch `{scope['batch_size']}`, seq `{scope['seq_len']}`, w_bits `{scope['w_bits']}`, lm_head `{scope['lm_head_w_bits']}`, final `{scope['final_logits_mode']}`",
                f"   - compile_allowed_now: `{candidate['admission']['compile_allowed_now']}`",
            ]
        )
    lines.extend(["", "## Next Commands", ""])
    for candidate in payload["candidates"]:
        commands = candidate["commands"]
        lines.extend(
            [
                f"### {candidate['id']}",
                "",
                "State-dict report only:",
                "",
                "```powershell",
                commands["state_dict_report_only"],
                "```",
                "",
                "Compile preflight only:",
                "",
                "```powershell",
                commands["compile_preflight_only"],
                "```",
                "",
            ]
        )
    lines.extend(["## Verification After Compile", ""])
    for item in payload["verification_after_compile"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Errors", ""])
    if payload["errors"]:
        lines.extend(f"- `{item}`" for item in payload["errors"])
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
            str(report_dir / "dream7b_bpu_quality_candidate_pack.json"),
            str(report_dir / "dream7b_bpu_quality_candidate_pack.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate-json", default=str(DEFAULT_GATE_JSON))
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--remote-report-root", default=DEFAULT_REMOTE_REPORT_ROOT)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--no-sync", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = Path(args.out_root) / f"dream7b_bpu_quality_candidate_pack_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    payload = build_payload(args, report_dir, stamp)
    json_path = report_dir / "dream7b_bpu_quality_candidate_pack.json"
    md_path = report_dir / "dream7b_bpu_quality_candidate_pack.md"
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

    latest_json = Path(args.out_root) / "dream7b_bpu_quality_candidate_pack_latest.json"
    latest_md = Path(args.out_root) / "dream7b_bpu_quality_candidate_pack_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
