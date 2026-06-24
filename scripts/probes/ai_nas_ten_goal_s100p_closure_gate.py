#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_nas_common import ensure_report_dir, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_ten_goal_s100p_closure_gate"
OK = "ok_ai_nas_ten_goal_s100p_closure_gate"
FAILED = "failed_ai_nas_ten_goal_s100p_closure_gate"


GOALS = [
    {
        "id": "goal_1_storage_foundation",
        "name": "NAS storage foundation",
        "script": "ai_nas_storage_foundation_gate_probe.py",
        "args": ["--report-root", "tmp/nas_storage_foundation_gate_local", "--file-count", "10000"],
        "pattern": "tmp/nas_storage_foundation_gate_local/**/nas_storage_foundation_gate.json",
        "ok": "ok_nas_storage_foundation_gate",
    },
    {
        "id": "goal_2_acl_identity",
        "name": "Users, permissions, and shared filesystem",
        "script": "ai_nas_acl_identity_gate_probe.py",
        "args": ["--report-root", "tmp/nas_acl_identity_gate_local"],
        "pattern": "tmp/nas_acl_identity_gate_local/**/nas_acl_identity_gate.json",
        "ok": "ok_nas_acl_identity_gate",
    },
    {
        "id": "goal_3_snapshot_recovery",
        "name": "Trash, snapshots, and version recovery",
        "script": "ai_nas_snapshot_recovery_gate_probe.py",
        "args": ["--report-root", "tmp/nas_snapshot_recovery_gate_local"],
        "pattern": "tmp/nas_snapshot_recovery_gate_local/**/snapshot_recovery_gate.json",
        "ok": "ok_nas_snapshot_recovery_gate",
    },
    {
        "id": "goal_4_backup_sync",
        "name": "Backup and sync",
        "script": "ai_nas_backup_sync_gate_probe.py",
        "args": ["--report-root", "tmp/nas_backup_sync_gate_local"],
        "pattern": "tmp/nas_backup_sync_gate_local/**/backup_sync_gate.json",
        "ok": "ok_nas_backup_sync_gate",
    },
    {
        "id": "goal_5_web_os",
        "name": "Web NAS OS",
        "script": "ai_nas_web_os_gate_probe.py",
        "args": ["--report-root", "tmp/nas_web_os_gate_local"],
        "pattern": "tmp/nas_web_os_gate_local/**/web_os_gate.json",
        "ok": "ok_nas_web_os_gate",
    },
    {
        "id": "goal_6_media_center",
        "name": "Media center",
        "script": "ai_nas_media_center_gate_probe.py",
        "args": ["--report-root", "tmp/nas_media_gate_local"],
        "pattern": "tmp/nas_media_gate_local/**/media_center_gate.json",
        "ok": "ok_nas_media_center_gate",
    },
    {
        "id": "goal_7_copilot",
        "name": "Document knowledge base and AI-NAS Copilot",
        "script": "ai_nas_copilot_product_gate_probe.py",
        "args": ["--report-root", "tmp/nas_copilot_gate_local"],
        "pattern": "tmp/nas_copilot_gate_local/**/copilot_product_gate.json",
        "ok": "ok_ai_nas_copilot_product_gate",
    },
    {
        "id": "goal_8_ops",
        "name": "Operations, monitoring, and alerts",
        "script": "ai_nas_ops_observability_gate_probe.py",
        "args": ["--report-root", "tmp/nas_ops_gate_local"],
        "pattern": "tmp/nas_ops_gate_local/**/ops_observability_gate.json",
        "ok": "ok_nas_ops_observability_gate",
    },
    {
        "id": "goal_9_app_ecosystem",
        "name": "App ecosystem and extension capability",
        "script": "ai_nas_app_ecosystem_gate_probe.py",
        "args": ["--report-root", "tmp/nas_app_gate_local"],
        "pattern": "tmp/nas_app_gate_local/**/app_ecosystem_gate.json",
        "ok": "ok_nas_app_ecosystem_gate",
    },
    {
        "id": "goal_10_top_replacement",
        "name": "Top NAS replacement product integration",
        "script": "ai_nas_top_replacement_gate_probe.py",
        "args": ["--report-root", "tmp/nas_top_gate_local"],
        "pattern": "tmp/nas_top_gate_local/**/top_nas_replacement_gate.json",
        "ok": "ok_top_nas_replacement_product_gate",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def newest(pattern: str) -> Path | None:
    paths = [path for path in Path(".").glob(pattern) if path.is_file()]
    if not paths:
        return None
    return max(paths, key=lambda path: (path.stat().st_mtime, str(path)))


def run_command(args: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(args, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
    return {
        "args": args,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_goal(goal: dict[str, Any], timeout: int) -> dict[str, Any]:
    script_path = Path(__file__).with_name(goal["script"])
    command = [sys.executable, str(script_path), *goal["args"]]
    result = run_command(command, timeout=timeout)
    path = newest(goal["pattern"])
    payload = load_json(path) if path else {}
    verdict = payload.get("verdict")
    return {
        "id": goal["id"],
        "name": goal["name"],
        "expected_verdict": goal["ok"],
        "ok": result["returncode"] == 0 and verdict == goal["ok"],
        "verdict": verdict,
        "path": str(path) if path else "",
        "passed_count": payload.get("passed_count"),
        "check_count": payload.get("check_count"),
        "failures": payload.get("failures") or [],
        "command": result,
    }


def read_goal(goal: dict[str, Any]) -> dict[str, Any]:
    path = newest(goal["pattern"])
    payload = load_json(path) if path else {}
    verdict = payload.get("verdict")
    return {
        "id": goal["id"],
        "name": goal["name"],
        "expected_verdict": goal["ok"],
        "ok": verdict == goal["ok"],
        "verdict": verdict,
        "path": str(path) if path else "",
        "passed_count": payload.get("passed_count"),
        "check_count": payload.get("check_count"),
        "failures": payload.get("failures") or [],
    }


def run_qwen_acceptance(out_root: Path, timeout: int) -> dict[str, Any]:
    script_path = Path(__file__).with_name("qwen25_ai_nas_acceptance_packet.py")
    prompt = (
        "Run the AI-NAS ten-goal product closure evidence flow on the S100P deployed "
        "Qwen2.5 gateway. Confirm grounded NAS evidence reports, model identity, and "
        "auditable report paths."
    )
    result = run_command(
        [sys.executable, str(script_path), "--out-root", str(out_root), "--prompt", prompt],
        timeout=timeout,
    )
    path = newest(str(out_root / "**/qwen25_ai_nas_acceptance.json"))
    payload = load_json(path) if path else {}
    health = payload.get("health") or {}
    chat = payload.get("chat") or {}
    model = ((health.get("json") or {}).get("model") or "")
    reports = payload.get("reports") or []
    ok = (
        result["returncode"] == 0
        and payload.get("verdict") == "ok_qwen25_ai_nas_acceptance_packet"
        and health.get("status") == 200
        and chat.get("status") == 200
        and model == "Qwen2.5-1.5B-Instruct-S100P-official"
        and all(item.get("exists") for item in reports)
    )
    return {
        "ok": ok,
        "path": str(path) if path else "",
        "verdict": payload.get("verdict"),
        "base_url": payload.get("base_url"),
        "model": model,
        "health_status": health.get("status"),
        "chat_status": chat.get("status"),
        "report_count": len(reports),
        "errors": payload.get("errors") or [],
        "active_profile": (health.get("json") or {}).get("active_profile"),
        "priority_status": (health.get("json") or {}).get("priority_status"),
        "official_qwen_1024_runtime_probe": payload.get("official_qwen_1024_runtime_probe") or {},
        "command": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict closure gate for the ten AI-NAS goals backed by S100P Qwen2.5 evidence.")
    parser.add_argument("--report-root", type=Path, default=Path("tmp/ai_nas_ten_goal_s100p_closure"))
    parser.add_argument("--use-existing", action="store_true", help="Do not rerun local goal probes; only inspect newest reports.")
    parser.add_argument("--skip-qwen-refresh", action="store_true", help="Inspect newest Qwen packet without running a fresh S100P acceptance.")
    parser.add_argument("--goal-timeout", type=int, default=240)
    parser.add_argument("--qwen-timeout", type=int, default=480)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "ten_goal_s100p_closure")
    goal_results = [read_goal(goal) if args.use_existing else run_goal(goal, args.goal_timeout) for goal in GOALS]
    qwen_out = Path("tmp/product_guardrail_snapshots")
    if args.skip_qwen_refresh:
        qwen_path = newest(str(qwen_out / "**/qwen25_ai_nas_acceptance.json"))
        qwen_payload = load_json(qwen_path) if qwen_path else {}
        health = qwen_payload.get("health") or {}
        chat = qwen_payload.get("chat") or {}
        qwen = {
            "ok": qwen_payload.get("verdict") == "ok_qwen25_ai_nas_acceptance_packet",
            "path": str(qwen_path) if qwen_path else "",
            "verdict": qwen_payload.get("verdict"),
            "base_url": qwen_payload.get("base_url"),
            "model": (health.get("json") or {}).get("model"),
            "health_status": health.get("status"),
            "chat_status": chat.get("status"),
            "report_count": len(qwen_payload.get("reports") or []),
            "errors": qwen_payload.get("errors") or [],
            "active_profile": (health.get("json") or {}).get("active_profile"),
            "priority_status": (health.get("json") or {}).get("priority_status"),
            "official_qwen_1024_runtime_probe": qwen_payload.get("official_qwen_1024_runtime_probe") or {},
        }
    else:
        qwen = run_qwen_acceptance(qwen_out, args.qwen_timeout)

    failed_goals = [item for item in goal_results if not item.get("ok")]
    blockers = []
    if failed_goals:
        blockers.extend([f"{item['id']}:{item.get('verdict') or 'missing'}" for item in failed_goals])
    if not qwen.get("ok"):
        blockers.append(f"s100p_qwen_acceptance:{qwen.get('verdict') or 'missing'}")

    goal10 = next((item for item in goal_results if item["id"] == "goal_10_top_replacement"), {})
    prerequisites_ok = all(item.get("ok") for item in goal_results if item["id"] != "goal_10_top_replacement")
    if goal10.get("ok") and not prerequisites_ok:
        blockers.append("goal_10_cannot_close_until_goals_1_to_9_are_all_ok")

    verdict = OK if not blockers else FAILED
    payload = {
        "generated_at": now_iso(),
        "tool_id": TOOL_ID,
        "verdict": verdict,
        "scope": "Ten NAS goals closed by independent gates plus live S100P deployed Qwen2.5 model acceptance.",
        "goal_results": goal_results,
        "s100p_model_acceptance": qwen,
        "summary": {
            "goal_count": len(goal_results),
            "goals_ok": sum(1 for item in goal_results if item.get("ok")),
            "s100p_model_ok": bool(qwen.get("ok")),
            "blocker_count": len(blockers),
        },
        "blockers": blockers,
        "claim_boundary": {
            "active_text_model": "Qwen2.5-1.5B-Instruct-S100P-official",
            "active_profile": qwen.get("active_profile"),
            "priority_1024_profile_status": qwen.get("priority_status"),
            "goal_10_requires_all_prior_goal_gates": True,
        },
    }
    safe_write_json(run_dir / "ten_goal_s100p_closure_gate.json", payload)
    safe_write_json(args.report_root / "ten_goal_s100p_closure_gate_latest.json", payload)
    lines = [
        "# AI-NAS Ten Goal S100P Closure Gate",
        "",
        f"- verdict: `{verdict}`",
        f"- goals_ok: `{payload['summary']['goals_ok']}/{payload['summary']['goal_count']}`",
        f"- s100p_model_ok: `{payload['summary']['s100p_model_ok']}`",
        f"- qwen_model: `{qwen.get('model')}`",
        f"- qwen_acceptance: `{qwen.get('path')}`",
        "",
        "## Goal Results",
        "",
    ]
    for item in goal_results:
        lines.append(f"- `{item['id']}`: ok=`{item.get('ok')}` verdict=`{item.get('verdict')}` report=`{item.get('path')}`")
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in blockers)
    safe_write_text(run_dir / "ten_goal_s100p_closure_gate.md", "\n".join(lines) + "\n")
    safe_write_text(args.report_root / "ten_goal_s100p_closure_gate_latest.md", "\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if verdict == OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
