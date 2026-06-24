#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("tmp/b4_runtime_schedule_analysis_20260619")
DEFAULT_READINESS = DEFAULT_ROOT / "dream7b_b4_last_token_compile_readiness_20260619.json"
DEFAULT_CAPACITY = DEFAULT_ROOT / "dream7b_b4_compile_capacity_plan_20260619.json"
DEFAULT_EXPERIMENT_GATE = DEFAULT_ROOT / "dream7b_b4_last_token_experiment_gate_20260620.json"
DEFAULT_OUT_JSON = DEFAULT_ROOT / "dream7b_b4_compile_command_guard_20260621.json"
DEFAULT_OUT_MD = DEFAULT_ROOT / "dream7b_b4_compile_command_guard_20260621.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def split_command(command: str) -> list[str]:
    if not command.strip():
        return []
    try:
        return [token.strip("'\"") for token in shlex.split(command, posix=False)]
    except ValueError:
        return [token.strip("'\"") for token in command.split()]


def option_map(tokens: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("-"):
            key = token.lower()
            values: list[str] = []
            cursor = index + 1
            while cursor < len(tokens) and not tokens[cursor].startswith("-"):
                values.append(tokens[cursor].strip("'\""))
                cursor += 1
            if not values:
                options[key] = True
            elif len(values) == 1:
                options[key] = values[0]
            else:
                options[key] = values
            index = cursor
        else:
            index += 1
    return options


def is_compile_command(tokens: list[str]) -> bool:
    return any("compile-dreamtruebatchsegments.ps1" in token.lower() for token in tokens)


def values_list(value: Any) -> list[str]:
    if value is None or value is True:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = [value]
    values: list[str] = []
    for item in raw:
        values.extend(part.strip() for part in str(item).split(",") if part.strip())
    return values


def as_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value is True:
            return default
        return int(str(value))
    except ValueError:
        return default


def classify_command(command: str, readiness: dict[str, Any], capacity: dict[str, Any]) -> dict[str, Any]:
    tokens = split_command(command)
    options = option_map(tokens)
    segments = values_list(options.get("-segments"))
    batch_size = as_int(options.get("-batchsize"), default=2)
    seq_len = as_int(options.get("-seqlen"), default=16)
    final_mode = str(options.get("-finallogitsmode") or "full")
    preflight_only = options.get("-preflightonly") is True
    skip_preflight = options.get("-skippreflight") is True
    force = options.get("-force") is True
    is_compile = is_compile_command(tokens)
    is_allowed_shape = (
        is_compile
        and segments == ["27:28"]
        and batch_size == 4
        and seq_len == 16
        and final_mode == "last-token"
    )
    b8_or_larger = bool(batch_size is not None and batch_size >= 8)
    multi_segment = is_compile and segments != ["27:28"]
    full_final = is_compile and final_mode != "last-token"
    readiness_ready = readiness.get("compile_ready") is True
    capacity_allows_compile = (capacity.get("recommendation") or {}).get(
        "do_not_start_compile_now"
    ) is False
    remote_manifest_exists = (readiness.get("remote") or {}).get("manifest_exists") is True
    blockers: list[str] = []
    if not command.strip():
        blockers.append("no_command_proposed")
    elif not is_compile:
        blockers.append("not_dream7b_compile_command")
    if b8_or_larger:
        blockers.append("b8_or_larger_compile_blocked")
    if multi_segment:
        blockers.append("non_single_segment_compile_blocked")
    if full_final:
        blockers.append("full_final_logits_compile_blocked")
    if skip_preflight:
        blockers.append("skip_preflight_blocked")
    if force:
        blockers.append("force_compile_blocked")
    if is_allowed_shape and not readiness_ready:
        blockers.append("compile_readiness_not_ready")
    if is_allowed_shape and not capacity_allows_compile:
        blockers.append("compile_capacity_plan_blocks_compile")
    if is_allowed_shape and remote_manifest_exists:
        blockers.append("remote_last_token_manifest_already_exists")

    command_admitted = (
        is_allowed_shape
        and readiness_ready
        and capacity_allows_compile
        and not remote_manifest_exists
        and not skip_preflight
        and not force
        and not preflight_only
    )
    preflight_admitted = (
        is_allowed_shape
        and preflight_only
        and not skip_preflight
        and not force
    )
    return {
        "proposed_command": command,
        "tokens": tokens,
        "is_compile_command": is_compile,
        "parsed_options": {
            "segments": segments,
            "batch_size": batch_size,
            "seq_len": seq_len,
            "final_logits_mode": final_mode,
            "preflight_only": preflight_only,
            "skip_preflight": skip_preflight,
            "force": force,
        },
        "matches_allowed_single_segment_last_token_shape": is_allowed_shape,
        "b8_or_larger_compile": b8_or_larger,
        "multi_segment_compile": multi_segment,
        "full_final_logits_compile": full_final,
        "preflight_admitted": preflight_admitted,
        "command_admitted": command_admitted,
        "would_start_compile": command_admitted,
        "blockers": sorted(set(blockers)),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    readiness = read_json(args.readiness_json)
    capacity = read_json(args.capacity_json)
    experiment_gate = read_json(args.experiment_gate_json)
    classification = classify_command(args.proposed_command or "", readiness, capacity)
    recommendation = capacity.get("recommendation") or {}
    compile_guard_active = (
        readiness.get("verdict") == "blocked_dream7b_b4_last_token_compile"
        or readiness.get("compile_ready") is True
    ) and experiment_gate.get("candidate") == "seg27_28_last_token_logits"
    only_single_segment_last_token_compile_allowed = True
    blocked_now_by_capacity = recommendation.get("do_not_start_compile_now") is True
    blocked_now_by_readiness = readiness.get("compile_ready") is not True
    b8_full_compile_blocked = True
    verdict = (
        "ok_dream7b_b4_compile_command_guard"
        if compile_guard_active
        and only_single_segment_last_token_compile_allowed
        and b8_full_compile_blocked
        and (
            not args.proposed_command.strip()
            or classification["command_admitted"]
            or classification["preflight_admitted"]
            or bool(classification["blockers"])
        )
        else "warning_dream7b_b4_compile_command_guard"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "verdict": verdict,
        "source_paths": {
            "last_token_compile_readiness": str(args.readiness_json),
            "compile_capacity_plan": str(args.capacity_json),
            "last_token_experiment_gate": str(args.experiment_gate_json),
        },
        "guard": {
            "compile_guard_active": compile_guard_active,
            "proposed_command_present": bool(args.proposed_command.strip()),
            "command_admitted": classification["command_admitted"],
            "preflight_admitted": classification["preflight_admitted"],
            "would_start_compile": classification["would_start_compile"],
            "only_single_segment_last_token_compile_allowed": only_single_segment_last_token_compile_allowed,
            "b8_full_compile_blocked": b8_full_compile_blocked,
            "blocked_now_by_readiness": blocked_now_by_readiness,
            "blocked_now_by_capacity": blocked_now_by_capacity,
            "compile_ready": readiness.get("compile_ready"),
            "commit_headroom_gb": (readiness.get("preflight") or {}).get("values", {}).get(
                "commit_headroom_gb"
            ),
            "required_commit_headroom_gb": (capacity.get("compile_guard") or {}).get(
                "required_commit_headroom_gb"
            ),
            "large_private_process_count": len(readiness.get("large_private_processes") or []),
        },
        "classification": classification,
        "next_actions": capacity.get("next_actions") or readiness.get("next_actions") or [],
        "audit": {
            "compile_started": False,
            "runtime_started": False,
            "service_restarted": False,
            "remote_write_performed": False,
            "local_writes": "JSON/Markdown compile command guard only",
        },
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    guard = payload["guard"]
    classification = payload["classification"]
    lines = [
        "# Dream7B B=4 Compile Command Guard",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- compile_guard_active: `{guard['compile_guard_active']}`",
        f"- proposed_command_present: `{guard['proposed_command_present']}`",
        f"- command_admitted: `{guard['command_admitted']}`",
        f"- preflight_admitted: `{guard['preflight_admitted']}`",
        f"- would_start_compile: `{guard['would_start_compile']}`",
        f"- only_single_segment_last_token_compile_allowed: `{guard['only_single_segment_last_token_compile_allowed']}`",
        f"- b8_full_compile_blocked: `{guard['b8_full_compile_blocked']}`",
        f"- blocked_now_by_readiness: `{guard['blocked_now_by_readiness']}`",
        f"- blocked_now_by_capacity: `{guard['blocked_now_by_capacity']}`",
        f"- commit_headroom_gb: `{guard['commit_headroom_gb']}`",
        f"- required_commit_headroom_gb: `{guard['required_commit_headroom_gb']}`",
        f"- large_private_process_count: `{guard['large_private_process_count']}`",
        "",
        "## Classification",
        "",
        f"- proposed_command: `{classification['proposed_command']}`",
        f"- is_compile_command: `{classification['is_compile_command']}`",
        f"- matches_allowed_single_segment_last_token_shape: `{classification['matches_allowed_single_segment_last_token_shape']}`",
        f"- b8_or_larger_compile: `{classification['b8_or_larger_compile']}`",
        f"- multi_segment_compile: `{classification['multi_segment_compile']}`",
        f"- full_final_logits_compile: `{classification['full_final_logits_compile']}`",
        f"- blockers: `{classification['blockers']}`",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.extend(["", "## Source Paths", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in payload["source_paths"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify a proposed Dream7B B=4 compile command before starting local compile."
    )
    parser.add_argument("--readiness-json", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--capacity-json", type=Path, default=DEFAULT_CAPACITY)
    parser.add_argument("--experiment-gate-json", type=Path, default=DEFAULT_EXPERIMENT_GATE)
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
