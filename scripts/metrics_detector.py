#!/usr/bin/env python3
"""Evidence-aware metrics summary that rejects stale and inconsistent inputs."""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PASS_PREFIXES = ("ok_", "ready_", "pass", "passed")
FAIL_PREFIXES = ("blocked_", "failed_", "fail", "error")


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def evidence_time(path: Path, payload: dict[str, Any]) -> float:
    for key in ("generated_at", "created_at", "timestamp"):
        value = payload.get(key)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
    return path.stat().st_mtime


def is_stale(path: Path, payload: dict[str, Any], *, now: float, max_age_hours: float) -> bool:
    return now - evidence_time(path, payload) > max_age_hours * 3600


def gate_identity(path: Path, payload: dict[str, Any]) -> str:
    explicit = payload.get("gate") or payload.get("name")
    if explicit:
        return str(explicit)
    return re.sub(r"_\d{8}[-_]\d{6}.*$", "", path.stem)


def gate_passed(payload: dict[str, Any]) -> bool | None:
    if isinstance(payload.get("ok"), bool):
        return bool(payload["ok"])
    verdict = str(payload.get("verdict") or "").lower()
    if verdict.startswith(PASS_PREFIXES):
        return True
    if verdict.startswith(FAIL_PREFIXES):
        return False
    return None


def latest_gate_records(report_root: Path, *, now: float, max_age_hours: float) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in report_root.rglob("*.json") if report_root.exists() else []:
        if "gate" not in path.name.lower():
            continue
        payload = load_json(path)
        if not payload:
            continue
        passed = gate_passed(payload)
        if passed is None:
            continue
        identity = gate_identity(path, payload)
        record = {"path": str(path), "passed": passed, "timestamp": evidence_time(path, payload), "stale": is_stale(path, payload, now=now, max_age_hours=max_age_hours), "verdict": payload.get("verdict")}
        if identity not in latest or record["timestamp"] > latest[identity]["timestamp"]:
            latest[identity] = record
    return latest


def latest_matching(report_root: Path, pattern: str) -> tuple[Path, dict[str, Any]] | None:
    candidates = []
    for path in report_root.rglob(pattern) if report_root.exists() else []:
        payload = load_json(path)
        if payload:
            candidates.append((evidence_time(path, payload), path, payload))
    if not candidates:
        return None
    _, path, payload = max(candidates, key=lambda row: row[0])
    return path, payload


def detect(report_root: Path, *, max_age_hours: float = 72.0, now: float | None = None) -> dict[str, Any]:
    now = now or time.time()
    gates = latest_gate_records(report_root, now=now, max_age_hours=max_age_hours)
    current_gates = [row for row in gates.values() if not row["stale"]]
    gate_passed_count = sum(row["passed"] for row in current_gates)
    gate_score = gate_passed_count / len(current_gates) if current_gates else None

    smoke_record = latest_matching(report_root, "*product_smoke*.json")
    smoke = {"available": False, "stale": True, "score": None}
    if smoke_record:
        path, payload = smoke_record
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
        failures = int(summary.get("failure_count") or 0)
        warnings = int(summary.get("warning_count") or 0)
        degraded = summary.get("degraded_modules") if isinstance(summary.get("degraded_modules"), list) else []
        stale = is_stale(path, payload, now=now, max_age_hours=max_age_hours)
        score = max(0.0, 1.0 - 0.25 * failures - 0.05 * warnings - 0.10 * len(degraded) - (0.30 if summary.get("production_ready") is not True else 0.0))
        smoke = {"available": True, "path": str(path), "stale": stale, "score": None if stale else score, "failures": failures, "warnings": warnings, "degraded_modules": degraded, "production_ready": summary.get("production_ready") is True}

    attack_record = latest_matching(report_root, "*safety_attack*.json")
    attacks = {"available": False, "stale": True, "score": None}
    if attack_record:
        path, payload = attack_record
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        stale = is_stale(path, payload, now=now, max_age_hours=max_age_hours)
        measured = int(summary.get("measured") or payload.get("total_attack_attempts") or 0)
        leaked = int(summary.get("leaked") or payload.get("attacks_passed") or 0)
        inconclusive = int(summary.get("inconclusive") or 0)
        score = None if stale or not measured or inconclusive else max(0.0, 1.0 - leaked / measured)
        attacks = {"available": True, "path": str(path), "stale": stale, "score": score, "measured": measured, "leaked": leaked, "inconclusive": inconclusive, "verdict": payload.get("verdict")}

    inference_record = latest_matching(report_root, "*inference*bench*cache*.json")
    inference = {"available": False, "stale": True, "score": None}
    if inference_record:
        path, payload = inference_record
        stale = is_stale(path, payload, now=now, max_age_hours=max_age_hours)
        q7 = payload.get("qwen7b") if isinstance(payload.get("qwen7b"), dict) else {}
        declared = q7.get("available") is True
        model_dirs = [entry for entry in q7.get("model_dirs") or [] if str(entry).strip()]
        consistent = not declared or bool(model_dirs)
        inference = {"available": True, "path": str(path), "stale": stale, "score": None if stale or not consistent else (1.0 if declared else 0.5), "qwen7b_declared_available": declared, "qwen7b_model_dirs": model_dirs, "consistent": consistent}

    scored = [value for value in (gate_score, smoke["score"], attacks["score"], inference["score"]) if value is not None]
    overall = sum(scored) / len(scored) if scored else None
    blockers = []
    if not current_gates:
        blockers.append("no_current_gate_evidence")
    if smoke["score"] is None:
        blockers.append("no_current_product_smoke")
    if attacks["score"] is None:
        blockers.append("no_conclusive_current_safety_probe")
    if inference.get("consistent") is False:
        blockers.append("inference_availability_inconsistent")
    return {
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "max_age_hours": max_age_hours,
        "overall_score": overall,
        "production_ready": not blockers and overall is not None and overall >= 0.85 and smoke.get("production_ready") is True,
        "blockers": blockers,
        "gates": {"total_discovered": len(gates), "current_total": len(current_gates), "passed": gate_passed_count, "failed": len(current_gates) - gate_passed_count, "score": gate_score, "records": gates},
        "product_smoke": smoke,
        "safety_attacks": attacks,
        "inference": inference,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=Path("reports"))
    parser.add_argument("--max-age-hours", type=float, default=72.0)
    parser.add_argument("--output", type=Path, default=Path("reports/metrics_detection/metrics_detection_latest.json"))
    args = parser.parse_args()
    result = detect(args.report_root, max_age_hours=args.max_age_hours)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    print(json.dumps({"overall_score": result["overall_score"], "production_ready": result["production_ready"], "blockers": result["blockers"]}, ensure_ascii=False))
    return 0 if result["production_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
