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
DEFAULT_PACK_JSON = DEFAULT_OUT_ROOT / "dream7b_bpu_quality_candidate_pack_latest.json"
DEFAULT_GOAL_STATUS_JSON = DEFAULT_OUT_ROOT / "dream7b_ai_nas_goal_status_packet_latest.json"
DEFAULT_REMOTE_REPORT_ROOT = "/mnt/nas/openclaw/reports/models"
DEFAULT_SSH_KEY = r"C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519"
DEFAULT_KNOWN_HOSTS = r"C:\Users\zhexu\.ssh\known_hosts"
DEFAULT_REMOTE_HOST = "sunrise@192.168.127.10"
DEFAULT_CANDIDATE_ID = "seg27_28_lmheadq16_last_token_sentinel"


REMOTE_PROBE = r'''
from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE_ROOT = Path(__CANDIDATE_ROOT__)
BASELINE_ROOTS = [Path(item) for item in __BASELINE_ROOTS__]


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
        enabled = "sudo -n env XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-enabled " + name
    else:
        command = "systemctl is-active " + name
        enabled = "systemctl is-enabled " + name
    active_result = run(command)
    enabled_result = run(enabled)
    return {
        "name": name,
        "root_user": root_user,
        "active": active_result["returncode"] == 0 and active_result["stdout"] == "active",
        "enabled": enabled_result["returncode"] == 0 and enabled_result["stdout"] == "enabled",
        "active_result": active_result,
        "enabled_result": enabled_result,
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


def root_status(path):
    return {
        "path": str(path),
        "exists": path.exists(),
        "hbm_count": int(run(f"find {str(path)!r} -type f -name '*.hbm' 2>/dev/null | wc -l")["stdout"] or "0") if path.exists() else 0,
        "manifest_count": int(run(f"find {str(path)!r} -type f -name 'manifest.sha256' 2>/dev/null | wc -l")["stdout"] or "0") if path.exists() else 0,
    }


def manifest_verified(path):
    manifest = path / "manifest.sha256"
    if not manifest.exists():
        return False
    result = run(f"cd {str(path)!r} && sha256sum -c manifest.sha256 >/dev/null 2>&1", timeout=120)
    return result["returncode"] == 0


candidate_hbm_count = int(run(f"find {str(CANDIDATE_ROOT)!r} -type f -name '*.hbm' 2>/dev/null | wc -l", timeout=30)["stdout"] or "0") if CANDIDATE_ROOT.exists() else 0
candidate_manifest_count = int(run(f"find {str(CANDIDATE_ROOT)!r} -type f -name 'manifest.sha256' 2>/dev/null | wc -l", timeout=30)["stdout"] or "0") if CANDIDATE_ROOT.exists() else 0

payload = {
    "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "host": run("hostname")["stdout"],
    "services": {
        "dream7b_bpu_batch_queue": service_state("dream7b-bpu-batch-queue.service"),
        "dream7b_local_openai_gateway": service_state("dream7b-local-openai-gateway.service", root_user=True),
        "openclaw_gateway": service_state("openclaw-gateway.service", root_user=True),
    },
    "health": {
        "gateway_18888": http_json("http://127.0.0.1:18888/health"),
        "openclaw_18789": http_json("http://127.0.0.1:18789/health"),
    },
    "listener": {
        "port_18888_pids": run("sudo -n lsof -t -iTCP:18888 -sTCP:LISTEN -P -n 2>/dev/null | tr '\\n' ' ' || true")["stdout"],
    },
    "seq16_baselines": [root_status(path) for path in BASELINE_ROOTS],
    "candidate": {
        "root": str(CANDIDATE_ROOT),
        "root_exists": CANDIDATE_ROOT.exists(),
        "hbm_count": candidate_hbm_count,
        "manifest_count": candidate_manifest_count,
        "manifest_verified": manifest_verified(CANDIDATE_ROOT) if CANDIDATE_ROOT.exists() else False,
    },
    "audit": {
        "compile_started_by_this_probe": False,
        "runtime_started_by_this_probe": False,
        "service_restarted_by_this_probe": False,
        "production_write_performed": False,
    },
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
'''


BASELINE_ROOTS = [
    "/home/sunrise/.cache/openclaw/dream7b-hbm/fine-seq16",
    "/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b4",
    "/mnt/nas/openclaw/models/dream7b-hbm/true-batch-seq16-b16",
]


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def candidate_by_id(pack: dict[str, Any] | None, candidate_id: str) -> dict[str, Any]:
    for candidate in (pack or {}).get("candidates") or []:
        if candidate.get("id") == candidate_id:
            return candidate
    return {}


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


def run_remote_probe(args: argparse.Namespace, candidate_root: str) -> dict[str, Any]:
    source = REMOTE_PROBE.replace("__CANDIDATE_ROOT__", json.dumps(candidate_root)).replace(
        "__BASELINE_ROOTS__", json.dumps(BASELINE_ROOTS)
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


def active_live_state(remote: dict[str, Any]) -> bool:
    services = remote.get("services") or {}
    health = remote.get("health") or {}
    return all(item.get("active") is True for item in services.values()) and all(
        item.get("ok") is True for item in health.values()
    )


def evaluate(args: argparse.Namespace, remote: dict[str, Any], candidate: dict[str, Any], goal: dict[str, Any] | None) -> dict[str, Any]:
    errors: list[str] = []
    if not remote.get("ok"):
        errors.append(remote.get("error", "remote_probe_failed"))
    route_a_ready = (((goal or {}).get("evaluation") or {}).get("route_a") or {}).get("ready") is True
    health = remote.get("health") or {}
    gateway_health = (health.get("gateway_18888") or {}).get("json") or {}
    backend = gateway_health.get("backend")
    production_path_unchanged = active_live_state(remote) and route_a_ready and backend == "diffuse-resident"
    seq16_baseline_deleted = not any((item.get("exists") and item.get("hbm_count", 0) > 0) for item in remote.get("seq16_baselines") or [])
    candidate_remote = remote.get("candidate") or {}
    candidate_artifact_present = candidate_remote.get("root_exists") is True and int(candidate_remote.get("hbm_count") or 0) > 0
    candidate_manifest_verified = candidate_remote.get("manifest_verified") is True
    rollback_ready = (
        production_path_unchanged
        and not seq16_baseline_deleted
        and candidate_artifact_present
        and candidate_manifest_verified
    )
    if not production_path_unchanged:
        errors.append("production_path_not_unchanged")
    if seq16_baseline_deleted:
        errors.append("seq16_baseline_deleted")
    if not candidate_artifact_present:
        errors.append("candidate_artifact_missing")
    if not candidate_manifest_verified:
        errors.append("candidate_manifest_not_verified")
    return {
        "verdict": "ready_dream7b_bpu_quality_rollback_report" if rollback_ready else "blocked_dream7b_bpu_quality_rollback_report",
        "errors": errors,
        "summary": {
            "candidate_id": args.candidate_id,
            "rollback_ready": rollback_ready,
            "production_path_unchanged": production_path_unchanged,
            "service_restarted": False,
            "overwrote_18888": False if backend == "diffuse-resident" else True,
            "seq16_baseline_deleted": seq16_baseline_deleted,
            "candidate_artifact_present": candidate_artifact_present,
            "candidate_manifest_verified": candidate_manifest_verified,
            "route_a_ready": route_a_ready,
            "gateway_backend": backend,
            "candidate_remote_output_root": candidate.get("remote_output_root"),
        },
    }


def build_payload(args: argparse.Namespace, report_dir: Path) -> dict[str, Any]:
    pack = read_json(args.pack_json)
    goal = read_json(args.goal_status_json)
    candidate = candidate_by_id(pack, args.candidate_id)
    candidate_root = candidate.get("remote_output_root") or args.candidate_root
    remote = run_remote_probe(args, candidate_root)
    evaluation = evaluate(args, remote, candidate, goal)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": evaluation["verdict"],
        "errors": evaluation["errors"],
        "summary": evaluation["summary"],
        "candidate": {
            "present_in_pack": bool(candidate),
            "id": args.candidate_id,
            "scope": candidate.get("scope"),
            "remote_output_root": candidate_root,
            "remote_report_root": candidate.get("remote_report_root"),
        },
        "remote": remote,
        "source_paths": {
            "candidate_pack": str(args.pack_json),
            "goal_status": str(args.goal_status_json),
        },
        "policy": {
            "compile_started_by_this_probe": False,
            "runtime_started_by_this_probe": False,
            "service_restarted_by_this_probe": False,
            "production_write_performed": False,
            "do_not_replace_18888": True,
            "do_not_delete_seq16_baseline": True,
        },
        "report_dir": str(report_dir),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Dream7B BPU Quality Rollback Report",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- candidate_id: `{summary['candidate_id']}`",
        f"- rollback_ready: `{summary['rollback_ready']}`",
        f"- production_path_unchanged: `{summary['production_path_unchanged']}`",
        f"- service_restarted: `{summary['service_restarted']}`",
        f"- overwrote_18888: `{summary['overwrote_18888']}`",
        f"- seq16_baseline_deleted: `{summary['seq16_baseline_deleted']}`",
        f"- candidate_artifact_present: `{summary['candidate_artifact_present']}`",
        f"- candidate_manifest_verified: `{summary['candidate_manifest_verified']}`",
        "",
        "## Errors",
        "",
    ]
    if payload["errors"]:
        lines.extend(f"- `{item}`" for item in payload["errors"])
    else:
        lines.append("- none")
    lines.extend(["", "## Seq16 Baselines", ""])
    for item in (payload["remote"].get("seq16_baselines") or []):
        lines.append(
            f"- `{item['path']}` exists=`{item['exists']}` hbm_count=`{item['hbm_count']}` manifest_count=`{item['manifest_count']}`"
        )
    lines.extend(["", "## Candidate Artifact", ""])
    candidate = payload["remote"].get("candidate") or {}
    lines.append(
        f"- `{candidate.get('root')}` exists=`{candidate.get('root_exists')}` hbm_count=`{candidate.get('hbm_count')}` "
        f"manifest_count=`{candidate.get('manifest_count')}` manifest_verified=`{candidate.get('manifest_verified')}`"
    )
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
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
            str(report_dir / "dream7b_bpu_quality_rollback_report.json"),
            str(report_dir / "dream7b_bpu_quality_rollback_report.md"),
            f"{args.remote_host}:{remote_dir}/",
        ],
        timeout=60,
    )
    return {"ok": scp["returncode"] == 0, "remote_dir": remote_dir, "scp": scp}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    parser.add_argument("--candidate-root", default="")
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--goal-status-json", type=Path, default=DEFAULT_GOAL_STATUS_JSON)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
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
    report_dir = args.out_root / f"dream7b_bpu_quality_rollback_report_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args, report_dir)
    json_path = report_dir / "dream7b_bpu_quality_rollback_report.json"
    md_path = report_dir / "dream7b_bpu_quality_rollback_report.md"
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
    latest_json = args.out_root / "dream7b_bpu_quality_rollback_report_latest.json"
    latest_md = args.out_root / "dream7b_bpu_quality_rollback_report_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
