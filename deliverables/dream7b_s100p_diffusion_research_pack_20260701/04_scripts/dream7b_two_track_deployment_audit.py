#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_OUT_ROOT = Path("tmp/product_guardrail_snapshots")


LOCAL_FILES = [
    "configs/systemd/dream7b-local-openai-gateway.service",
    "configs/systemd/dream7b-bpu-batch-queue.service",
    "configs/systemd/openclaw-gateway.service",
    "configs/systemd/dream7b-bpu-experimental-gateway-18889.service",
    "configs/dream7b_backend_policy.yaml",
    "configs/dream7b_queue_adapter_policy.json",
    "scripts/dream7b_experimental_18889_gateway.py",
    "docs/dream7b_s100p_next_work_runbook.md",
    "docs/dream7b_openclaw_fast_path_fix_2026-06-22.md",
    "docs/dream7b_bpu_logits_diagnosis_2026-06-22.md",
    "docs/dream7b_bpu_seq16_quality_root_cause_2026-06-22.md",
]


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


def ssh_cmd(args: argparse.Namespace, command: str, timeout: int = 90) -> dict[str, Any]:
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


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def latest_json(root: Path, pattern: str) -> tuple[str | None, dict[str, Any] | None]:
    paths = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime)
    if not paths:
        return None, None
    payload = read_json(paths[-1])
    return str(paths[-1]), payload


def collect_local(args: argparse.Namespace) -> dict[str, Any]:
    files = []
    for item in LOCAL_FILES:
        path = Path(item)
        files.append(
            {
                "path": item,
                "exists": path.exists(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size if path.exists() else None,
            }
        )
    latest_patterns = {
        "queue_health": "dream7b_queue_health_snapshot_*/dream7b_queue_health_snapshot.json",
        "fast_path": "dream7b_fast_path_regression_*/dream7b_fast_path_regression.json",
        "quality_promotion_gate": "dream7b_bpu_quality_promotion_gate_*/dream7b_bpu_quality_promotion_gate.json",
        "post_compile_matrix": "dream7b_bpu_quality_post_compile_validation_matrix_*/dream7b_bpu_quality_post_compile_validation_matrix.json",
        "final_goal_audit": "dream7b_ai_nas_final_goal_audit_*/dream7b_ai_nas_final_goal_audit.json",
    }
    latest_reports = {}
    for key, pattern in latest_patterns.items():
        path, payload = latest_json(args.out_root, pattern)
        latest_reports[key] = {
            "path": path,
            "verdict": payload.get("verdict") if payload else None,
            "loaded": payload is not None,
        }
    return {"files": files, "latest_reports": latest_reports}


def collect_remote(args: argparse.Namespace) -> dict[str, Any]:
    remote_script = r"""
python3 - <<'PY'
import glob
import json
import pathlib
import subprocess

def cmd(args):
    p = subprocess.run(args, text=True, capture_output=True)
    return {"returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}

def first(args):
    out = cmd(args)["stdout"].splitlines()
    return out[0].strip() if out else ""

def userctl(*parts):
    return ["sudo", "-n", "env", "XDG_RUNTIME_DIR=/run/user/0", "systemctl", "--user", *parts]

def http_json(url):
    raw = first(["curl", "-sS", "--max-time", "3", url])
    try:
        return json.loads(raw) if raw else {}
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}:{exc}", "raw": raw}

def count(path):
    p = pathlib.Path(path)
    return len(list(p.glob("*.jsonl"))) if p.is_dir() else None

def latest(pattern):
    paths = sorted(glob.glob(pattern), key=lambda item: pathlib.Path(item).stat().st_mtime)
    return paths[-1] if paths else None

model_root = pathlib.Path("/mnt/nas/openclaw/models/dream7b-hbm")
hbm_dirs = []
if model_root.is_dir():
    for item in sorted(model_root.iterdir()):
        if item.is_dir() and (item.name.startswith("true-batch-") or item.name.startswith("bpu-quality-") or item.name == "fine-seq16"):
            manifests = list(item.rglob("manifest.sha256"))
            hbms = list(item.rglob("*.hbm"))
            hbm_dirs.append({"name": item.name, "path": str(item), "manifest_count": len(manifests), "hbm_count": len(hbms)})

ps = cmd(["ps", "-eo", "pid=,args="])["stdout"].splitlines()
true_batch_processes = [
    line.strip()
    for line in ps
    if ("dream7b_true_batch" in line or "compile_dream_true_batch" in line or "dream7b-bpu-experimental" in line)
    and "python3 - <<'PY'" not in line
    and "bash -c" not in line
]

payload = {
    "services": {
        "queue_active": first(["systemctl", "is-active", "dream7b-bpu-batch-queue.service"]),
        "queue_enabled": first(["systemctl", "is-enabled", "dream7b-bpu-batch-queue.service"]),
        "gateway_18888_active": first(userctl("is-active", "dream7b-local-openai-gateway.service")),
        "gateway_18888_enabled": first(userctl("is-enabled", "dream7b-local-openai-gateway.service")),
        "openclaw_gateway_active": first(userctl("is-active", "openclaw-gateway.service")),
        "openclaw_gateway_enabled": first(userctl("is-enabled", "openclaw-gateway.service")),
        "experimental_18889_active": first(userctl("is-active", "dream7b-bpu-experimental-gateway-18889.service")),
        "experimental_18889_enabled": first(userctl("is-enabled", "dream7b-bpu-experimental-gateway-18889.service")),
    },
    "health": {
        "gateway_18888": http_json("http://127.0.0.1:18888/health"),
        "openclaw_18789": http_json("http://127.0.0.1:18789/health"),
        "experimental_18889": http_json("http://127.0.0.1:18889/health"),
    },
    "queue": {
        "pending_count": count("/mnt/nas/openclaw/queues/dream7b-bpu/pending"),
        "processing_count": count("/mnt/nas/openclaw/queues/dream7b-bpu/processing"),
        "done_count": count("/mnt/nas/openclaw/queues/dream7b-bpu/done"),
        "failed_count": count("/mnt/nas/openclaw/queues/dream7b-bpu/failed"),
    },
    "latest_reports": {
        "text_queue_run": latest("/mnt/nas/openclaw/reports/models/dream7b_bpu_text_queue_run_*/text_queue_run.json"),
        "goal_status": latest("/mnt/nas/openclaw/reports/models/dream7b_ai_nas_goal_status_packet_*/dream7b_ai_nas_goal_status_packet.json"),
        "acceptance": latest("/mnt/nas/openclaw/reports/models/dream7b_ai_nas_acceptance_packet_*/dream7b_ai_nas_acceptance_packet.json"),
        "final_goal_audit": latest("/mnt/nas/openclaw/reports/models/dream7b_ai_nas_final_goal_audit_*/dream7b_ai_nas_final_goal_audit.json"),
        "promotion_gate": latest("/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_promotion_gate_*/dream7b_bpu_quality_promotion_gate.json"),
        "rollback": latest("/mnt/nas/openclaw/reports/models/dream7b_bpu_quality_rollback_report_*/dream7b_bpu_quality_rollback_report.json"),
    },
    "hbm_artifacts": hbm_dirs,
    "processes": {
        "true_batch_or_compile_or_18889": true_batch_processes,
    },
}
print(json.dumps(payload, ensure_ascii=False))
PY
"""
    result = ssh_cmd(args, remote_script, timeout=60)
    try:
        payload = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError as exc:
        payload = {"_error": f"{type(exc).__name__}:{exc}", "raw_stdout": result["stdout"]}
    return {"payload": payload, "command": result}


def build_risks(local: dict[str, Any], remote: dict[str, Any]) -> tuple[list[str], list[str]]:
    warnings = []
    blockers = []
    r = remote.get("payload") or {}
    services = r.get("services") or {}
    health = r.get("health") or {}
    queue = r.get("queue") or {}
    gateway = health.get("gateway_18888") or {}
    if services.get("gateway_18888_active") != "active":
        blockers.append("18888 gateway is not active")
    if gateway.get("backend") != "diffuse-resident":
        blockers.append("18888 backend is not diffuse-resident")
    if services.get("queue_active") != "active":
        warnings.append("BPU queue service is not active")
    if services.get("experimental_18889_active") == "active":
        warnings.append("18889 experimental service is already active; verify it is isolated before testing")
    if (queue.get("pending_count") or 0) or (queue.get("processing_count") or 0):
        warnings.append("BPU queue is not idle at audit time")
    if (r.get("processes") or {}).get("true_batch_or_compile_or_18889"):
        warnings.append("true-batch/compile/18889 process is present during audit")
    latest = local.get("latest_reports") or {}
    if latest.get("quality_promotion_gate", {}).get("verdict") and not str(latest["quality_promotion_gate"]["verdict"]).startswith("ok_"):
        warnings.append("latest local BPU promotion gate is not passing")
    return blockers, warnings


def write_report(out_dir: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=False)
    out_json = out_dir / "dream7b_two_track_deployment_audit.json"
    out_md = out_dir / "dream7b_two_track_deployment_audit.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    remote = payload["remote"]["payload"]
    services = remote.get("services") or {}
    health = remote.get("health") or {}
    queue = remote.get("queue") or {}
    lines = [
        "# Dream7B Two-Track OpenClaw Deployment Audit",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- route_a: `OpenClaw -> 18888 -> diffuse-resident/GGUF`",
        f"- route_b: `18889 BPU queue / true-batch isolated experiment`",
        "",
        "## Service State",
        "",
        f"- 18888 gateway: `{services.get('gateway_18888_active')}` / `{services.get('gateway_18888_enabled')}`",
        f"- 18888 backend: `{(health.get('gateway_18888') or {}).get('backend')}`",
        f"- OpenClaw gateway: `{services.get('openclaw_gateway_active')}` / `{services.get('openclaw_gateway_enabled')}`",
        f"- BPU queue: `{services.get('queue_active')}` / `{services.get('queue_enabled')}`",
        f"- 18889 experimental: `{services.get('experimental_18889_active')}` / `{services.get('experimental_18889_enabled')}`",
        f"- queue pending/processing: `{queue.get('pending_count')}` / `{queue.get('processing_count')}`",
        "",
        "## HBM Artifacts",
        "",
        "| name | manifests | hbm files |",
        "| --- | ---: | ---: |",
    ]
    for item in remote.get("hbm_artifacts") or []:
        lines.append(f"| {item.get('name')} | {item.get('manifest_count')} | {item.get('hbm_count')} |")
    lines.extend(["", "## Risks", ""])
    if payload["blockers"]:
        lines.append("Blockers:")
        lines.extend(f"- {item}" for item in payload["blockers"])
    else:
        lines.append("- no route-a blocker found")
    if payload["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in payload["warnings"])
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- Keep 18888 protected as the product default.",
            "- Keep seq16 queue artifacts as the baseline.",
            "- Use 18889 only for explicit background/batch/async experiments.",
            "- Do not gray-route foreground OpenClaw replies to BPU until seq length, logits quality, Chinese generation, warm latency, stability, and rollback gates pass.",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_json, out_md


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit for the Dream7B/OpenClaw two-track deployment plan.")
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--ssh-key", default=DEFAULT_SSH_KEY)
    parser.add_argument("--known-hosts", default=DEFAULT_KNOWN_HOSTS)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    args = parser.parse_args()
    local = collect_local(args)
    remote = collect_remote(args)
    blockers, warnings = build_risks(local, remote)
    verdict = "ok_dream7b_two_track_deployment_audit" if not blockers else "blocked_dream7b_two_track_deployment_audit"
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "local": local,
        "remote": remote,
        "blockers": blockers,
        "warnings": warnings,
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_root / f"dream7b_two_track_deployment_audit_{stamp}"
    out_json, out_md = write_report(out_dir, payload)
    print(out_json)
    print(out_md)
    return 0 if verdict.startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
