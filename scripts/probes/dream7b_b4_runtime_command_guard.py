#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_RUNTIME_GATE = DEFAULT_ROOT / "dream7b_b4_runtime_experiment_gate_20260620.json"
DEFAULT_VALIDATION_PLAN = DEFAULT_ROOT / "dream7b_b4_last_token_runtime_validation_plan_20260620.json"
DEFAULT_NAS_INVENTORY = DEFAULT_ROOT / "dream7b_true_batch_nas_inventory_20260620.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_runtime_command_guard_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_runtime_command_guard_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def split_command(command: str) -> list[str]:
    if not command.strip():
        return []
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


def option_map(tokens: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
                options[token] = tokens[index + 1]
                index += 2
            else:
                options[token] = True
                index += 1
        else:
            index += 1
    return options


def is_true_batch_runtime(tokens: list[str]) -> bool:
    return any("dream7b_true_batch_group_major_telemetry_probe.py" in token for token in tokens)


def as_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value is True:
            return default
        return int(str(value))
    except ValueError:
        return default


def classify_command(command: str, runtime_gate: dict[str, Any], validation_plan: dict[str, Any]) -> dict[str, Any]:
    tokens = split_command(command)
    options = option_map(tokens)
    decision = runtime_gate.get("decision") or {}
    allowed = set(decision.get("allowed_experiments") or [])
    readiness = validation_plan.get("readiness") or {}
    expected = validation_plan.get("expected") or {}
    expected_command = (validation_plan.get("runtime_command") or {}).get("shell")
    is_runtime = is_true_batch_runtime(tokens)
    final_mode = str(options.get("--final-logits-mode") or "full")
    microbatch_count = as_int(options.get("--microbatch-count"))
    batch_size = as_int(options.get("--batch-size"))
    groups = str(options.get("--groups") or "")
    inner_order = str(options.get("--inner-order") or "")
    has_final_root = bool(options.get("--final-hbm-root"))
    standard_sweep_like = (
        is_runtime
        and batch_size == 4
        and final_mode != "last-token"
    )
    current_experimental_flags = [
        flag
        for flag in ["--preallocate-hidden", "--prewarm-hbm"]
        if options.get(flag) is True
    ]
    if options.get("--release-gc-mode") == "skip":
        current_experimental_flags.append("--release-gc-mode skip")

    blockers: list[str] = []
    if not command.strip():
        blockers.append("no_command_proposed")
    elif not is_runtime:
        blockers.append("not_dream7b_b4_true_batch_runtime_command")
    elif not allowed:
        blockers.append("runtime_gate_allows_no_experiments")
    if standard_sweep_like:
        blockers.append("standard_b4_true_batch_sweep_blocked")
    if current_experimental_flags:
        blockers.append("experimental_runtime_flags_blocked")

    expected_last_token_shape = (
        is_runtime
        and final_mode == "last-token"
        and microbatch_count == expected.get("microbatch_count")
        and batch_size == 4
        and groups == ",".join(expected.get("groups") or [])
        and inner_order == expected.get("inner_order")
        and has_final_root
    )
    if is_runtime and final_mode == "last-token" and not expected_last_token_shape:
        blockers.append("last_token_command_shape_mismatch")

    last_token_gate_ready = (
        "mb512_segment_major_last_token_validation" in allowed
        and decision.get("run_last_token_mb512_validation_now") is True
        and readiness.get("validation_ready") is True
        and readiness.get("manifest_ready") is True
    )
    command_admitted = (
        is_runtime
        and expected_last_token_shape
        and last_token_gate_ready
        and not current_experimental_flags
        and not standard_sweep_like
    )
    if expected_last_token_shape and not last_token_gate_ready:
        blockers.append("last_token_runtime_gate_not_open")

    return {
        "proposed_command": command,
        "tokens": tokens,
        "is_true_batch_runtime_command": is_runtime,
        "parsed_options": {
            "batch_size": batch_size,
            "microbatch_count": microbatch_count,
            "groups": groups,
            "inner_order": inner_order,
            "final_logits_mode": final_mode,
            "has_final_hbm_root": has_final_root,
            "experimental_flags": current_experimental_flags,
        },
        "expected_last_token_command": expected_command,
        "matches_expected_last_token_validation_shape": expected_last_token_shape,
        "standard_sweep_like": standard_sweep_like,
        "command_admitted": command_admitted,
        "would_start_runtime": command_admitted,
        "blockers": sorted(set(blockers)),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    runtime_gate = read_json(args.runtime_gate_json)
    validation_plan = read_json(args.validation_plan_json)
    nas_inventory = read_json(args.nas_inventory_json)
    decision = runtime_gate.get("decision") or {}
    admission = runtime_gate.get("admission_evidence") or {}
    inventory_decision = nas_inventory.get("decision") or {}
    proposed_command = args.proposed_command or ""
    classification = classify_command(proposed_command, runtime_gate, validation_plan)
    standard_stop_rules = inventory_decision.get("duplicate_stop_rules") or []
    command_guard_active = (
        runtime_gate.get("verdict") in {
            "blocked_dream7b_b4_runtime_experiment_gate_no_s100p_run_now",
            "ok_dream7b_b4_runtime_experiment_gate_ready_to_run",
        }
        and admission.get("ready") is True
        and inventory_decision.get("run_more_standard_b4_runtime_sweeps_now") is False
    )
    standard_sweep_commands_blocked = (
        command_guard_active
        and admission.get("standard_group_or_inner_order_sweeps_blocked") is True
        and bool(standard_stop_rules)
    )
    last_token_command_requires_runtime_gate = True
    verdict = (
        "ok_dream7b_b4_runtime_command_guard"
        if command_guard_active
        and standard_sweep_commands_blocked
        and (
            not proposed_command.strip()
            or classification["command_admitted"]
            or bool(classification["blockers"])
        )
        else "warning_dream7b_b4_runtime_command_guard"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "runtime_experiment_gate": str(args.runtime_gate_json),
            "last_token_runtime_validation_plan": str(args.validation_plan_json),
            "true_batch_nas_inventory": str(args.nas_inventory_json),
        },
        "guard": {
            "command_guard_active": command_guard_active,
            "proposed_command_present": bool(proposed_command.strip()),
            "command_admitted": classification["command_admitted"],
            "would_start_runtime": classification["would_start_runtime"],
            "runtime_gate_allows_experiments": bool(decision.get("allowed_experiments") or []),
            "allowed_experiments": decision.get("allowed_experiments") or [],
            "s100p_runtime_experiment_now": decision.get("s100p_runtime_experiment_now"),
            "standard_sweep_commands_blocked": standard_sweep_commands_blocked,
            "last_token_command_requires_runtime_gate": last_token_command_requires_runtime_gate,
            "admission_evidence_ready": admission.get("ready"),
            "admission_projected_saved_ms_per_request": admission.get(
                "projected_saved_ms_per_request"
            ),
            "admission_not_bpu_promotion_proof": admission.get(
                "projection_is_not_bpu_promotion_proof"
            ),
        },
        "classification": classification,
        "standard_duplicate_stop_rules": standard_stop_rules,
        "remaining_nonduplicate_work": inventory_decision.get("remaining_nonduplicate_work") or [],
        "audit": {
            "runtime_started": False,
            "compile_started": False,
            "service_restarted": False,
            "remote_write_performed": False,
            "local_writes": "JSON/Markdown runtime command guard only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    guard = payload["guard"]
    classification = payload["classification"]
    lines = [
        "# Dream7B B=4 Runtime Command Guard",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- command_guard_active: `{guard['command_guard_active']}`",
        f"- proposed_command_present: `{guard['proposed_command_present']}`",
        f"- command_admitted: `{guard['command_admitted']}`",
        f"- would_start_runtime: `{guard['would_start_runtime']}`",
        f"- runtime_gate_allows_experiments: `{guard['runtime_gate_allows_experiments']}`",
        f"- allowed_experiments: `{guard['allowed_experiments']}`",
        f"- standard_sweep_commands_blocked: `{guard['standard_sweep_commands_blocked']}`",
        f"- last_token_command_requires_runtime_gate: `{guard['last_token_command_requires_runtime_gate']}`",
        f"- admission_projected_saved_ms_per_request: `{guard['admission_projected_saved_ms_per_request']}`",
        "",
        "## Classification",
        "",
        f"- proposed_command: `{classification['proposed_command']}`",
        f"- is_true_batch_runtime_command: `{classification['is_true_batch_runtime_command']}`",
        f"- matches_expected_last_token_validation_shape: `{classification['matches_expected_last_token_validation_shape']}`",
        f"- standard_sweep_like: `{classification['standard_sweep_like']}`",
        f"- blockers: `{classification['blockers']}`",
        "",
        "## Standard Duplicate Stop Rules",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["standard_duplicate_stop_rules"])
    lines.extend(["", "## Remaining Non-Duplicate Work", ""])
    lines.extend(f"- {item}" for item in payload["remaining_nonduplicate_work"])
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify a proposed Dream7B B=4 runtime command before any S100P execution."
    )
    parser.add_argument("--runtime-gate-json", type=Path, default=DEFAULT_RUNTIME_GATE)
    parser.add_argument("--validation-plan-json", type=Path, default=DEFAULT_VALIDATION_PLAN)
    parser.add_argument("--nas-inventory-json", type=Path, default=DEFAULT_NAS_INVENTORY)
    parser.add_argument("--proposed-command", default="")
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.out_md, payload)
    print(args.out_json)
    print(args.out_md)
    return 0 if payload["verdict"].startswith("ok_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
