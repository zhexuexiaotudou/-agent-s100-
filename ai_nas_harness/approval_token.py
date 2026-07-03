from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any


REQUIRED_FIELDS = {
    "approval_id",
    "user_id",
    "workspace_id",
    "tool_id",
    "args_hash",
    "action_type",
    "expires_at",
    "nonce",
}


def _canonical(payload: dict[str, Any]) -> bytes:
    unsigned = {key: payload[key] for key in sorted(payload) if key != "signature"}
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), _canonical(payload), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_approval_token(
    *,
    user_id: str,
    workspace_id: str,
    tool_id: str,
    args_hash: str,
    action_type: str,
    secret: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    payload = {
        "approval_id": f"apr-{uuid.uuid4().hex[:16]}",
        "user_id": user_id,
        "workspace_id": workspace_id,
        "tool_id": tool_id,
        "args_hash": args_hash,
        "action_type": action_type,
        "expires_at": int(time.time()) + ttl_seconds,
        "nonce": uuid.uuid4().hex,
    }
    payload["signature"] = sign_payload(payload, secret)
    return payload


def validate_approval_token(
    token: dict[str, Any],
    *,
    secret: str,
    workspace_id: str,
    tool_id: str,
    args_hash: str,
    now: int | None = None,
    test_mode: bool = False,
) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - set(token))
    if missing:
        return {"valid": False, "reason": "missing_fields", "missing": missing}
    if not token.get("signature"):
        return {"valid": False, "reason": "unsigned_token"}
    expected = sign_payload(token, secret)
    if not hmac.compare_digest(str(token.get("signature")), expected):
        return {"valid": False, "reason": "signature_mismatch"}
    current = int(time.time()) if now is None else int(now)
    if int(token.get("expires_at", 0)) <= current:
        return {"valid": False, "reason": "expired_token"}
    if token.get("workspace_id") != workspace_id:
        return {"valid": False, "reason": "wrong_workspace_id"}
    if token.get("tool_id") != tool_id:
        return {"valid": False, "reason": "wrong_tool_id"}
    if token.get("args_hash") != args_hash:
        return {"valid": False, "reason": "wrong_args_hash"}
    if not test_mode:
        return {"valid": False, "reason": "stage2_read_only_mode_rejects_write_execution"}
    return {"valid": True, "reason": "accepted_in_test_mode", "approval_id": token.get("approval_id")}
