#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SEQ128_DIR = Path("tmp/cloud_seq128_results")
DEFAULT_SEQ128_TAR = DEFAULT_SEQ128_DIR / "dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar"
DEFAULT_SEQ128_SHA = DEFAULT_SEQ128_DIR / "dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar.sha256"
DEFAULT_SEQ128_SUMMARY = DEFAULT_SEQ128_DIR / "seq128_b1_lmheadq16_lasttoken_summary.json"
DEFAULT_SEQ128_MANIFEST = DEFAULT_SEQ128_DIR / "seq128_b1_lmheadq16_lasttoken_hbm_manifest.tsv"
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"


NEGATIVE_CONTROL_EVIDENCE = [
    {
        "id": "seq16_prompt_tail_truncation",
        "path": "docs/dream7b_bpu_seq16_quality_root_cause_2026-06-22.md",
        "claim": "seq16 BPU single-request chat is structurally blocked by fixed 16-token window, 12-token prompt tail, and 4 mask slots.",
        "required_text": "truncate_prompt_keep_min_masks",
    },
    {
        "id": "seq16_bpu_logits_garbage",
        "path": "docs/dream7b_bpu_logits_diagnosis_2026-06-22.md",
        "claim": "seq16 BPU logits produced garbage text versus GGUF/CPU on the same 16-token input.",
        "required_text": "BPU diffusion generation produces garbage text",
    },
    {
        "id": "late_layer_int16_saturation",
        "path": "docs/dream7b_bpu_logits_diagnosis_2026-06-22.md",
        "claim": "late-layer hidden states saturated int16 in seg21_24 and seg24_26.",
        "required_text": "int16 saturation in seg21_24 and seg24_26",
    },
    {
        "id": "lm_head_q8_uncalibrated",
        "path": "docs/dream7b_bpu_logits_diagnosis_2026-06-22.md",
        "claim": "q8 lm_head without calibration compressed logits; seq128 package therefore uses lm_head q16 last-token head.",
        "required_text": "q8 weight quantization of lm_head without calibration",
    },
    {
        "id": "two_track_product_boundary",
        "path": "docs/dream7b_openclaw_two_track_deployment_2026-06-22.md",
        "claim": "18888 remains protected foreground GGUF route; BPU/true-batch remains isolated until all quality and product gates pass.",
        "required_text": "Do not route foreground OpenClaw replies to BPU/true-batch",
    },
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024 * 8), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    return text.split()[0] if text else None


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "row_count": 0, "rows": []}
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append({"segment": parts[0], "hbm_path": parts[1], "bytes": int(parts[2])})
    return {
        "exists": True,
        "row_count": len(rows),
        "total_bytes": sum(int(row["bytes"]) for row in rows),
        "rows": rows,
    }


def doc_evidence() -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in NEGATIVE_CONTROL_EVIDENCE:
        path = Path(item["path"])
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        evidence.append(
            {
                **item,
                "exists": path.is_file(),
                "required_text_present": bool(item["required_text"] in text),
            }
        )
    return evidence


def run_cmd(args: list[str], timeout: int = 60) -> dict[str, Any]:
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


def s100p_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    if not args.check_s100p:
        return {"checked": False}
    script = r"""
python3 - <<'PY'
import json
import pathlib
import subprocess

def cmd(argv):
    p = subprocess.run(argv, text=True, capture_output=True)
    return {"returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}

def first(argv):
    out = cmd(argv)["stdout"].splitlines()
    return out[0].strip() if out else ""

def exists(path):
    return pathlib.Path(path).exists()

seq128_root = pathlib.Path("/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken")
payload = {
    "hostname": first(["hostname"]),
    "arch": first(["uname", "-m"]),
    "nas_openclaw_exists": exists("/mnt/nas/openclaw"),
    "nas_df": cmd(["df", "-h", "/mnt/nas/openclaw"]),
    "target_seq128_root_exists": seq128_root.exists(),
    "target_seq128_hbm_count": len(list(seq128_root.rglob("*.hbm"))) if seq128_root.exists() else 0,
    "services": {
        "queue": first(["systemctl", "is-active", "dream7b-bpu-batch-queue.service"]),
        "queue_enabled": first(["systemctl", "is-enabled", "dream7b-bpu-batch-queue.service"]),
    },
    "runtime_script_exists": exists("/mnt/nas/openclaw/scripts/probes/dream7b_seq128_s100p_runtime_gate.py"),
    "latest_seq128_reports": [str(p) for p in sorted(pathlib.Path("/mnt/nas/openclaw/reports/models").glob("dream7b_seq128_s100p_runtime_gate_*/seq128_s100p_runtime_gate.json"))[-5:]],
}
print(json.dumps(payload, ensure_ascii=False))
PY
"""
    result = run_cmd(
        [
            "ssh.exe",
            "-i",
            args.ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={args.known_hosts}",
            args.remote_host,
            script,
        ],
        timeout=args.ssh_timeout,
    )
    try:
        payload = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError as exc:
        payload = {"_error": f"{type(exc).__name__}:{exc}", "raw_stdout": result["stdout"]}
    return {"checked": True, "payload": payload, "command": result}


def load_runtime_report(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    return read_json(path)


def load_logits_report(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    return read_json(path)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    summary = read_json(args.seq128_summary)
    manifest = load_manifest(args.seq128_manifest)
    expected = expected_sha(args.seq128_sha)
    actual = sha256_file(args.seq128_tar) if not args.skip_sha256 else None
    docs = doc_evidence()
    runtime_report = load_runtime_report(args.runtime_report_json)
    logits_report = load_logits_report(args.logits_report_json)

    seq128_errors: list[str] = []
    if not args.seq128_tar.is_file():
        seq128_errors.append("seq128_tar_missing")
    if expected is None:
        seq128_errors.append("seq128_expected_sha_missing")
    if not args.skip_sha256 and actual != expected:
        seq128_errors.append("seq128_sha256_mismatch")
    if not summary:
        seq128_errors.append("seq128_summary_missing_or_invalid")
    else:
        if summary.get("seq_len") != 128:
            seq128_errors.append("seq128_summary_seq_len_not_128")
        if summary.get("batch_size") != 1:
            seq128_errors.append("seq128_summary_batch_size_not_1")
        if summary.get("segment_count") != 28:
            seq128_errors.append("seq128_summary_segment_count_not_28")
        if summary.get("hbm_count") != 28:
            seq128_errors.append("seq128_summary_hbm_count_not_28")
        if summary.get("missing_or_bad"):
            seq128_errors.append("seq128_summary_missing_or_bad_not_empty")
        final_segment = str(summary.get("final_segment") or "")
        if "lm_head_w_bits=16" not in final_segment or "last-token" not in final_segment:
            seq128_errors.append("seq128_final_segment_not_lmheadq16_lasttoken")
    if manifest["row_count"] != 28:
        seq128_errors.append("seq128_manifest_row_count_not_28")
    if any(not item["exists"] or not item["required_text_present"] for item in docs):
        seq128_errors.append("negative_control_doc_evidence_incomplete")

    runtime_errors: list[str] = []
    if runtime_report:
        if runtime_report.get("verdict") != "ok_dream7b_seq128_s100p_runtime_gate":
            runtime_errors.append("runtime_report_not_ok")
        if not (runtime_report.get("gate_results") or {}).get("representative_segments", {}).get("pass"):
            runtime_errors.append("representative_segments_not_passing")
        full_chain = (runtime_report.get("gate_results") or {}).get("full_chain", {})
        if full_chain.get("attempted") and not full_chain.get("pass"):
            runtime_errors.append("full_chain_attempted_but_not_passing")

    logits_errors: list[str] = []
    if logits_report:
        if logits_report.get("verdict") != "ok_dream7b_seq128_logits_reference_compare":
            logits_errors.append("logits_report_not_ok")
        summary_logits = logits_report.get("summary") or {}
        if summary_logits.get("top1_agreement", 0.0) < 0.80:
            logits_errors.append("top1_agreement_below_threshold")
        if summary_logits.get("ref_top1_in_bpu_top5", 0.0) < 0.95:
            logits_errors.append("ref_top1_in_bpu_top5_below_threshold")
        if summary_logits.get("mean_cosine", 0.0) < 0.95:
            logits_errors.append("mean_cosine_below_threshold")
        if summary_logits.get("min_bpu_top1_probability", 0.0) < 0.05:
            logits_errors.append("bpu_top1_probability_below_threshold")
        if summary_logits.get("max_bpu_normalized_entropy", 1.0) > 0.95:
            logits_errors.append("bpu_entropy_too_uniform")

    gate_status = {
        "compile_feasible": {
            "status": "pass" if not seq128_errors else "fail",
            "errors": seq128_errors,
            "evidence": {
                "tar": str(args.seq128_tar),
                "tar_size_bytes": args.seq128_tar.stat().st_size if args.seq128_tar.is_file() else None,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "sha256_checked": not args.skip_sha256,
                "summary": str(args.seq128_summary),
                "manifest": str(args.seq128_manifest),
            },
        },
        "s100p_runtime_valid": {
            "status": "pass" if runtime_report and not runtime_errors else "fail" if runtime_report else "pending",
            "errors": runtime_errors,
            "evidence": {"runtime_report_json": str(args.runtime_report_json) if args.runtime_report_json else None},
        },
        "logits_numerically_valid": {
            "status": "pass" if logits_report and not logits_errors else "fail" if logits_report else "pending",
            "errors": logits_errors,
            "evidence": {"logits_report_json": str(args.logits_report_json) if args.logits_report_json else None}
            if logits_report
            else {},
            "required_evidence": None
            if logits_report
            else "CPU/BF16 or GGUF reference vs BPU dequantized logits/top-k/cosine/entropy report.",
        },
        "generation_quality_valid": {
            "status": "pending",
            "required_evidence": "pre-registered prompt battery output with no garbled/token-leak/empty replies.",
        },
        "product_route_valid": {
            "status": "pending",
            "required_evidence": "18889 isolation, foreground fallback to 18888, rollback, health, queue drain, latency and failure-rate logs.",
        },
    }
    if gate_status["compile_feasible"]["status"] == "fail":
        final_verdict = "failed_dream7b_s100p_diffusion_research_packet_compile_evidence"
        falsification_layer = "compile_feasible"
    elif gate_status["s100p_runtime_valid"]["status"] == "fail":
        final_verdict = "falsified_dream7b_seq128_s100p_runtime"
        falsification_layer = "s100p_runtime_valid"
    elif gate_status["s100p_runtime_valid"]["status"] == "pending":
        final_verdict = "blocked_pending_dream7b_seq128_s100p_runtime_gate"
        falsification_layer = None
    elif gate_status["logits_numerically_valid"]["status"] == "fail":
        final_verdict = "falsified_or_blocked_dream7b_seq128_logits_numerical_gate"
        falsification_layer = "logits_numerically_valid"
    elif gate_status["logits_numerically_valid"]["status"] == "pending":
        final_verdict = "blocked_pending_dream7b_seq128_logits_numerical_gate"
        falsification_layer = None
    else:
        final_verdict = "blocked_pending_dream7b_logits_quality_generation_product_gates"
        falsification_layer = None

    return {
        "generated_at": now_iso(),
        "verdict": final_verdict,
        "falsification_layer": falsification_layer,
        "scope": {
            "question": "Can Dream7B diffusion be accurately deployed on S100P?",
            "accuracy_definition": "layered evidence: compile, S100P runtime, numerical logits, generation quality, product route.",
            "non_mutation_boundary": [
                "do_not_overwrite_18888",
                "do_not_enable_foreground_bpu_route",
                "do_not_delete_seq16_queue_baseline",
                "do_not_compile_seq256_before_seq128_board_evidence",
            ],
        },
        "gate_status": gate_status,
        "seq128_artifact": {
            "summary": summary,
            "manifest": {key: value for key, value in manifest.items() if key != "rows"},
            "manifest_rows": manifest["rows"],
        },
        "negative_controls": docs,
        "runtime_report": runtime_report,
        "logits_report": logits_report,
        "s100p_snapshot": s100p_snapshot(args),
    }


def write_outputs(out_root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = out_root / f"dream7b_s100p_diffusion_research_packet_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_s100p_diffusion_research_packet.json"
    out_md = out_dir / "dream7b_s100p_diffusion_research_packet.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates = payload["gate_status"]
    lines = [
        "# Dream7B S100P Diffusion Research Packet",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- falsification_layer: `{payload['falsification_layer']}`",
        "",
        "## Gate Status",
        "",
        "| Gate | Status | Evidence / next requirement |",
        "| --- | --- | --- |",
    ]
    for name, gate in gates.items():
        evidence = gate.get("evidence") or gate.get("required_evidence") or ""
        if isinstance(evidence, dict):
            evidence_text = ", ".join(f"{key}={value}" for key, value in evidence.items() if value is not None)
        else:
            evidence_text = str(evidence)
        lines.append(f"| `{name}` | `{gate['status']}` | {evidence_text} |")
    lines.extend(
        [
            "",
            "## Seq128 Artifact",
            "",
            f"- tar: `{gates['compile_feasible']['evidence']['tar']}`",
            f"- expected_sha256: `{gates['compile_feasible']['evidence']['expected_sha256']}`",
            f"- actual_sha256: `{gates['compile_feasible']['evidence']['actual_sha256']}`",
            f"- manifest_rows: `{payload['seq128_artifact']['manifest']['row_count']}`",
            f"- total_hbm_bytes: `{payload['seq128_artifact']['manifest'].get('total_bytes')}`",
            "",
            "## Negative Controls",
            "",
        ]
    )
    for item in payload["negative_controls"]:
        lines.append(
            f"- `{item['id']}`: exists=`{item['exists']}`, required_text_present=`{item['required_text_present']}`; {item['claim']}"
        )
    lines.extend(["", "## Boundary", ""])
    for item in payload["scope"]["non_mutation_boundary"]:
        lines.append(f"- `{item}`")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_json, out_md


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Dream7B S100P diffusion layered research evidence packet.")
    parser.add_argument("--seq128-tar", type=Path, default=DEFAULT_SEQ128_TAR)
    parser.add_argument("--seq128-sha", type=Path, default=DEFAULT_SEQ128_SHA)
    parser.add_argument("--seq128-summary", type=Path, default=DEFAULT_SEQ128_SUMMARY)
    parser.add_argument("--seq128-manifest", type=Path, default=DEFAULT_SEQ128_MANIFEST)
    parser.add_argument("--runtime-report-json", type=Path)
    parser.add_argument("--logits-report-json", type=Path)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--skip-sha256", action="store_true")
    parser.add_argument("--check-s100p", action="store_true")
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--ssh-timeout", type=int, default=60)
    args = parser.parse_args()

    payload = evaluate(args)
    out_json, out_md = write_outputs(args.out_root, payload)
    print(out_json)
    print(out_md)
    return 1 if payload["verdict"].startswith(("failed_", "falsified_")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
