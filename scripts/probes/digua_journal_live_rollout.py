#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports"
FINAL_DIR = REPO_ROOT / "01_final_evidence"
TMP_DIR = REPO_ROOT / "tmp"
APPROVAL_FILE = REPO_ROOT / "operator_approval" / "digua_journal_live_rollout_approved.json"
APPROVAL_ENV = "AI_NAS_OPERATOR_APPROVED_DIGUA_JOURNAL_LIVE_ROLLOUT"

REPORT_STEMS = {
    21200: "journal_live_rollout_gate",
    21210: "journal_live_e2e_gate",
    21220: "journal_live_regression_gate",
}


def utc_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact_stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cmd(cmd: list[str], timeout: int = 30) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": completed.stdout.strip()[-4000:],
            "stderr": completed.stderr.strip()[-4000:],
            "command": cmd,
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "command": cmd,
        }


def approval_state() -> dict[str, Any]:
    env_value = os.environ.get(APPROVAL_ENV)
    file_payload: dict[str, Any] | None = None
    if APPROVAL_FILE.exists():
        try:
            file_payload = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            file_payload = {"parse_error": f"{type(exc).__name__}: {exc}"}
    return {
        "approved": env_value == "1" or APPROVAL_FILE.exists(),
        "env_name": APPROVAL_ENV,
        "env_value_is_1": env_value == "1",
        "approval_file": rel(APPROVAL_FILE),
        "approval_file_exists": APPROVAL_FILE.exists(),
        "approval_file_payload": file_payload,
    }


def report_paths(report_id: int) -> tuple[Path, Path]:
    stem = REPORT_STEMS[report_id]
    return REPORT_DIR / f"{report_id}_{stem}.json", REPORT_DIR / f"{report_id}_{stem}.md"


def write_report(report_id: int, payload: dict[str, Any]) -> None:
    json_path, md_path = report_paths(report_id)
    payload = {
        "report_id": report_id,
        "title": REPORT_STEMS[report_id],
        "generated_at": utc_stamp(),
        **payload,
    }
    write_json(json_path, payload)
    write_text(
        md_path,
        "\n".join(
            [
                f"# {report_id} {REPORT_STEMS[report_id]}",
                "",
                f"- generated_at: {payload['generated_at']}",
                f"- status: {payload.get('status')}",
                f"- verdict: {payload.get('verdict')}",
                "",
                "```json",
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
            ]
        ),
    )


def hard_constraints() -> dict[str, bool]:
    return {
        "ports_8765_18080_18888_18889_modified": False,
        "openclaw_replaced": False,
        "qwen_replaced": False,
        "cloud_generation_enabled": False,
        "screenshot_enabled": False,
        "desktop_visual_enabled": False,
        "keyboard_mouse_tracking_enabled": False,
        "qwen_tool_execution_authority": False,
        "delete_move_rename_chmod_executed": False,
        "private_nas_raw_content_uploaded": False,
    }


def build_package(final_packet: dict[str, Any]) -> dict[str, Any]:
    timestamp = compact_stamp()
    package_root = TMP_DIR / f"digua_journal_live_rollout_package_{timestamp}"
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)

    include_paths = [
        REPORT_DIR / "21200_journal_live_rollout_gate.json",
        REPORT_DIR / "21200_journal_live_rollout_gate.md",
        REPORT_DIR / "21210_journal_live_e2e_gate.json",
        REPORT_DIR / "21210_journal_live_e2e_gate.md",
        REPORT_DIR / "21220_journal_live_regression_gate.json",
        REPORT_DIR / "21220_journal_live_regression_gate.md",
        FINAL_DIR / "digua_journal_live_rollout_gate_packet.json",
        FINAL_DIR / "digua_journal_live_rollout_gate_packet.md",
        REPO_ROOT / "docs" / "DIGUA_JOURNAL_LIVE_ROLLOUT_RUNBOOK.md",
        REPO_ROOT / "docs" / "DIGUA_JOURNAL_SAFE_CLAIM_BOUNDARY.md",
        REPO_ROOT / "docs" / "DIGUA_JOURNAL_USER_GUIDE.md",
        REPO_ROOT / "configs" / "journal_feature_flags.json",
        REPO_ROOT / "configs" / "journal_workspace.json",
        REPO_ROOT / "scripts" / "probes" / "digua_journal_live_rollout.py",
    ]

    manifest_entries: list[dict[str, Any]] = []
    for source in include_paths:
        if not source.exists():
            continue
        target = package_root / rel(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest_entries.append({"path": rel(source), "sha256": sha256_file(source), "bytes": source.stat().st_size})

    manifest = {
        "feature": "digua_journal_live_rollout",
        "generated_at": utc_stamp(),
        "final_verdict": final_packet["verdict"],
        "file_count": len(manifest_entries),
        "files": manifest_entries,
    }
    write_json(package_root / "MANIFEST.json", manifest)
    write_text(package_root / "SHA256SUMS.txt", "\n".join(f"{item['sha256']}  {item['path']}" for item in manifest_entries) + "\n")
    write_text(
        package_root / "SELF_CHECK.py",
        """#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
required = [
    "reports/21200_journal_live_rollout_gate.json",
    "reports/21210_journal_live_e2e_gate.json",
    "reports/21220_journal_live_regression_gate.json",
    "01_final_evidence/digua_journal_live_rollout_gate_packet.json",
]
missing = [item for item in required if not (root / item).exists()]
print(json.dumps({"ok": not missing, "missing": missing, "file_count": manifest["file_count"]}, indent=2))
raise SystemExit(1 if missing else 0)
""",
    )

    zip_path = REPO_ROOT / f"digua_journal_live_rollout_for_gptpro_{timestamp}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package_root).as_posix())
    zip_sha = sha256_file(zip_path)
    write_text(REPO_ROOT / f"{zip_path.name}.sha256.txt", f"{zip_sha}  {zip_path.name}\n")
    return {
        "package_path": rel(zip_path),
        "package_sha256": zip_sha,
        "package_bytes": zip_path.stat().st_size,
        "package_root": rel(package_root),
        "manifest_file_count": len(manifest_entries),
    }


def write_blocked_outputs() -> dict[str, Any]:
    approval = approval_state()
    git_head = run_cmd(["git", "rev-parse", "HEAD"])
    base_payload = {
        "approval": approval,
        "hard_constraints": hard_constraints(),
        "live_rollout_attempted": False,
        "ssh_attempted": False,
        "openclaw_reload_attempted": False,
        "s100p_service_mutation_attempted": False,
        "reason": "missing operator approval gate",
    }
    write_report(
        21200,
        {
            **base_payload,
            "status": "blocked",
            "verdict": "blocked_by_no_operator_approval",
            "git_head": git_head,
            "required_operator_action": [
                f"Set process environment {APPROVAL_ENV}=1 before invoking the rollout runner",
                f"or create {rel(APPROVAL_FILE)} with operator approval metadata",
            ],
        },
    )
    write_report(
        21210,
        {
            **base_payload,
            "status": "skipped",
            "verdict": "blocked_by_no_operator_approval",
            "skipped_steps": [
                "OpenClaw health",
                "Qwen health",
                "protected port check",
                "journal DB migration on S100P",
                "feature flag load",
                "OpenClaw reload",
                "/journal HTTP 200",
                "/api/journal/health",
                "collector run",
                "manual entry",
                "period summaries",
                "Markdown export",
                "privacy scan",
            ],
        },
    )
    write_report(
        21220,
        {
            **base_payload,
            "status": "skipped",
            "verdict": "blocked_by_no_operator_approval",
            "regression_not_run_reason": "live rollout did not start because operator approval was absent",
            "disable_script_verified_for_existence": (REPO_ROOT / "scripts" / "disable_journal_feature.sh").exists(),
        },
    )
    final_packet = {
        "feature": "digua_journal_live_rollout",
        "generated_at": utc_stamp(),
        "verdict": "blocked_by_no_operator_approval",
        "reports": [rel(report_paths(report_id)[0]) for report_id in sorted(REPORT_STEMS)],
        "approval": approval,
        "hard_constraints": hard_constraints(),
        "live_rollout_attempted": False,
        "remote_state_changed": False,
        "next_unblock": {
            "env": f"{APPROVAL_ENV}=1",
            "approval_file": rel(APPROVAL_FILE),
        },
    }
    write_json(FINAL_DIR / "digua_journal_live_rollout_gate_packet.json", final_packet)
    write_text(
        FINAL_DIR / "digua_journal_live_rollout_gate_packet.md",
        "\n".join(
            [
                "# Digua Journal Live Rollout Gate Packet",
                "",
                f"- generated_at: {final_packet['generated_at']}",
                f"- verdict: {final_packet['verdict']}",
                "- live rollout attempted: false",
                "- remote state changed: false",
                f"- unblock env: `{APPROVAL_ENV}=1`",
                f"- unblock file: `{rel(APPROVAL_FILE)}`",
                "",
            ]
        ),
    )
    package = build_package(final_packet)
    final_packet["package"] = package
    write_json(FINAL_DIR / "digua_journal_live_rollout_gate_packet.json", final_packet)
    write_text(
        FINAL_DIR / "digua_journal_live_rollout_gate_packet.md",
        "\n".join(
            [
                "# Digua Journal Live Rollout Gate Packet",
                "",
                f"- generated_at: {final_packet['generated_at']}",
                f"- verdict: {final_packet['verdict']}",
                f"- package: {package['package_path']}",
                f"- package_sha256: {package['package_sha256']}",
                "- live rollout attempted: false",
                "- remote state changed: false",
                f"- unblock env: `{APPROVAL_ENV}=1`",
                f"- unblock file: `{rel(APPROVAL_FILE)}`",
                "",
            ]
        ),
    )
    return final_packet


def main() -> None:
    parser = argparse.ArgumentParser(description="Digua Journal S100P live rollout gate.")
    parser.add_argument("--allow-blocked-output", action="store_true", help="Write blocked reports when approval is missing.")
    args = parser.parse_args()

    approval = approval_state()
    if not approval["approved"]:
        if not args.allow_blocked_output:
            print(json.dumps({"ok": False, "verdict": "blocked_by_no_operator_approval", "approval": approval}, ensure_ascii=False, indent=2))
            raise SystemExit(2)
        final_packet = write_blocked_outputs()
        print(json.dumps({"ok": False, "verdict": final_packet["verdict"], "package": final_packet["package"]}, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0)

    print(json.dumps({"ok": False, "verdict": "approval_present_live_execution_requires_next_explicit_run", "approval": approval}, ensure_ascii=False, indent=2))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
