from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


TOKEN_FIELDS = (
    "raw_user_prompt_tokens",
    "raw_context_tokens",
    "naive_cloud_payload_tokens",
    "redacted_payload_tokens",
    "compressed_payload_tokens",
    "optimized_cloud_payload_tokens",
    "saved_tokens",
    "reduction_ratio",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def trace_hash(record: Dict[str, Any]) -> str:
    payload = {k: v for k, v in record.items() if k != "trace_hash"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_trace_record(
    *,
    run_id: str,
    case: Dict[str, Any],
    route: Dict[str, Any],
    token_counts: Dict[str, Any],
    redaction_count: int,
    private_leak_count: int,
    tokenizer_identity_hash: str,
    quality_check: str,
) -> Dict[str, Any]:
    record = {
        "timestamp": now_iso(),
        "run_id": run_id,
        "case_id": case.get("case_id"),
        "task_type": case.get("task_type"),
        "route": route.get("route"),
        "route_reason": route.get("reason"),
        "cloud_call_avoided": route.get("route") in {"local_only", "cloud_blocked_private"},
        "private_leak_count": private_leak_count,
        "redaction_count": redaction_count,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "quality_check": quality_check,
        **{field: token_counts.get(field) for field in TOKEN_FIELDS},
    }
    record["trace_hash"] = trace_hash(record)
    return record


def append_trace(path: str | Path, record: Dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def trace_is_complete(record: Dict[str, Any]) -> bool:
    required = {"case_id", "task_type", "route", "private_leak_count", "redaction_count", "tokenizer_identity_hash", "trace_hash"}
    required.update(TOKEN_FIELDS)
    return all(record.get(field) is not None for field in required)

