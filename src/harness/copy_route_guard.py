from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from dataclasses import replace
from typing import Any

from ai_nas_harness.privacy_filter import detect_private_leaks

from .copy_route_types import (
    COPY_EXECUTE_TOOL_ID,
    COPY_ROLLBACK_TOOL_ID,
    COPY_ROUTE_TOOL_ID,
    CopyCandidate,
    CopyRouteDecision,
    CopyRouteFeatureFlags,
    CopyRoutePolicy,
)


DEFAULT_POLICY = CopyRoutePolicy()
DEFAULT_FLAGS = CopyRouteFeatureFlags()
DEFAULT_SECRET = "digua-stage4-4-copy-route-token"
VALID_ROUTES = {"preview", "dry-run", "confirm", "execute", "rollback"}
HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")
DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8", errors="replace")).hexdigest()


def path_hash(path: str) -> str:
    return hashlib.sha256(normalize_relative_path(path).encode("utf-8", errors="replace")).hexdigest()


def normalize_relative_path(path: str) -> str:
    return str(path).replace("\\", "/").strip()


def public_candidate_fingerprint(candidate: CopyCandidate) -> str:
    payload = {
        "action_type": candidate.action_type,
        "source_path_hash": path_hash(candidate.source_relative_path),
        "target_path_hash": path_hash(candidate.target_relative_path),
        "source_sha256": candidate.source_sha256.lower(),
        "expected_size_bytes": candidate.expected_size_bytes,
        "source_owner_scope": candidate.source_owner_scope,
        "candidate_id": candidate.candidate_id,
    }
    return stable_hash(payload)


def candidate_args_hash(candidate: CopyCandidate) -> str:
    return stable_hash(
        {
            "action_type": candidate.action_type,
            "source_relative_path": normalize_relative_path(candidate.source_relative_path),
            "target_relative_path": normalize_relative_path(candidate.target_relative_path),
            "source_sha256": candidate.source_sha256.lower(),
            "expected_size_bytes": candidate.expected_size_bytes,
            "source_owner_scope": candidate.source_owner_scope,
        }
    )


def approval_phrase(candidate: CopyCandidate) -> str:
    return f"APPROVE COPY {public_candidate_fingerprint(candidate)[:16]}"


def _is_absolute_or_escape(path: str) -> bool:
    normalized = normalize_relative_path(path)
    lowered = normalized.lower()
    if not normalized:
        return True
    if normalized.startswith("/") or normalized.startswith("//") or normalized.startswith("~"):
        return True
    if DRIVE_RE.match(normalized):
        return True
    if lowered.startswith("\\\\"):
        return True
    if "%2e" in lowered or "%2f" in lowered or "%5c" in lowered:
        return True
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return True
    return False


def _prefix_match(path: str, prefixes: tuple[str, ...]) -> bool:
    normalized = normalize_relative_path(path)
    return any(normalized.startswith(prefix) for prefix in prefixes)


def validation_reasons(candidate: CopyCandidate, policy: CopyRoutePolicy = DEFAULT_POLICY) -> list[str]:
    reasons: list[str] = []
    source = normalize_relative_path(candidate.source_relative_path)
    target = normalize_relative_path(candidate.target_relative_path)
    action = candidate.action_type.lower().strip()

    if action != policy.allowed_action_type:
        reasons.append("action_type_not_copy")
    if action in {item.lower() for item in policy.forbidden_action_types}:
        reasons.append("forbidden_action_type")
    if _is_absolute_or_escape(source):
        reasons.append("source_path_not_safe_relative")
    if _is_absolute_or_escape(target):
        reasons.append("target_path_not_safe_relative")
    if source == target:
        reasons.append("source_target_same_path")
    if not _prefix_match(source, policy.allowed_source_prefixes):
        reasons.append("source_prefix_not_allowlisted")
    if not _prefix_match(target, policy.allowed_target_prefixes):
        reasons.append("target_prefix_not_allowlisted")
    if not target.startswith(policy.target_root_prefix):
        reasons.append("target_not_under_collections")
    if CONTROL_RE.search(source) or CONTROL_RE.search(target):
        reasons.append("control_character_in_path")
    if policy.require_source_hash and not HASH_RE.match(candidate.source_sha256):
        reasons.append("source_sha256_missing_or_invalid")
    if candidate.expected_size_bytes <= 0:
        reasons.append("expected_size_not_positive")
    if candidate.expected_size_bytes > policy.max_size_bytes:
        reasons.append("expected_size_exceeds_limit")
    if candidate.source_owner_scope not in policy.allowed_source_owner_scopes:
        reasons.append("source_owner_scope_not_allowed")
    if policy.require_target_absent and candidate.target_exists_now:
        reasons.append("target_already_exists")
    if policy.require_target_parent_exists and not candidate.target_parent_exists:
        reasons.append("target_parent_missing")
    if policy.forbid_symlink and (candidate.source_is_symlink or candidate.target_parent_is_symlink):
        reasons.append("symlink_rejected")
    if policy.forbid_recursive and candidate.recursive:
        reasons.append("recursive_rejected")
    if policy.forbid_overwrite and candidate.overwrite:
        reasons.append("overwrite_rejected")
    if policy.forbid_qwen_autonomous and candidate.requested_by_qwen:
        reasons.append("qwen_has_no_execution_authority")
    if policy.forbid_cloud_derived and candidate.cloud_derived:
        reasons.append("cloud_derived_write_rejected")
    return sorted(set(reasons))


def redacted_route_response(candidate: CopyCandidate, route: str, *, status: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    fingerprint = public_candidate_fingerprint(candidate)
    response: dict[str, Any] = {
        "route": route,
        "status": status,
        "action_type": candidate.action_type,
        "candidate_fingerprint": fingerprint,
        "source_path_hash": path_hash(candidate.source_relative_path),
        "target_path_hash": path_hash(candidate.target_relative_path),
        "source_sha256_prefix": candidate.source_sha256.lower()[:12],
        "expected_size_bytes": candidate.expected_size_bytes,
        "target_root": "Collections",
        "raw_paths_in_response": False,
        "private_content_in_response": False,
    }
    if extra:
        response.update(extra)
    return response


def audit_event(candidate: CopyCandidate, route: str, allowed: bool, reasons: list[str], *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "event_id": f"copy-route-{uuid.uuid4().hex[:16]}",
        "tool_id": COPY_ROUTE_TOOL_ID,
        "route": route,
        "allowed": allowed,
        "reason_codes": reasons,
        "candidate_fingerprint": public_candidate_fingerprint(candidate),
        "source_path_hash": path_hash(candidate.source_relative_path),
        "target_path_hash": path_hash(candidate.target_relative_path),
        "args_hash": candidate_args_hash(candidate),
        "qwen_execution_authority": False,
        "cloud_private_egress": False,
        "raw_private_content_logged": False,
        "dispatcher_tool": COPY_EXECUTE_TOOL_ID if route == "execute" else COPY_ROLLBACK_TOOL_ID if route == "rollback" else None,
    }
    if extra:
        event.update(extra)
    return event


def _sanitize_for_leak_scan(value: Any, key_hint: str = "") -> Any:
    lowered_key = key_hint.lower()
    opaque_key = any(
        marker in lowered_key
        for marker in [
            "hash",
            "fingerprint",
            "signature",
            "nonce",
            "event_id",
            "token_hash",
            "candidate_id",
        ]
    )
    if opaque_key and isinstance(value, str):
        return "[OPAQUE]"
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(key)
            for structural_key in [
                "private_content_in_response",
                "raw_private_content_logged",
                "cloud_private_egress",
                "private_leak_count",
                "private_leak_markers",
            ]:
                safe_key = safe_key.replace(structural_key, structural_key.replace("private", "sensitive"))
            sanitized[safe_key] = _sanitize_for_leak_scan(item, str(key))
        return sanitized
    if isinstance(value, list):
        return [_sanitize_for_leak_scan(item, key_hint) for item in value]
    return value


def assert_no_private_leak(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    text = canonical_json(_sanitize_for_leak_scan(payload))
    sanitized_text = text
    leaks = detect_private_leaks(sanitized_text)
    raw_path_markers = [
        marker
        for marker in [
            "/mnt/nas",
            "Personal/",
            "Personal\\",
            "Documents/",
            "Photos/",
            "Finance/",
            "Medical/",
            "source_relative_path",
            "target_relative_path",
        ]
        if marker.lower() in text.lower()
    ]
    return not leaks and not raw_path_markers, sorted(set([*leaks, *raw_path_markers]))


def _feature_enabled(route: str, flags: CopyRouteFeatureFlags) -> bool:
    return {
        "preview": flags.preview_enabled,
        "dry-run": flags.dry_run_enabled,
        "confirm": flags.confirm_enabled,
        "execute": flags.execute_enabled,
        "rollback": flags.rollback_enabled,
    }[route]


def make_decision(
    candidate: CopyCandidate,
    route: str,
    *,
    flags: CopyRouteFeatureFlags = DEFAULT_FLAGS,
    policy: CopyRoutePolicy = DEFAULT_POLICY,
    extra_response: dict[str, Any] | None = None,
    extra_audit: dict[str, Any] | None = None,
) -> CopyRouteDecision:
    if route not in VALID_ROUTES:
        raise ValueError(f"unsupported copy route: {route}")
    reasons = validation_reasons(candidate, policy)
    if not _feature_enabled(route, flags):
        reasons.append(f"{route.replace('-', '_')}_feature_disabled")
    allowed = not reasons
    status = f"{route}_allowed" if allowed else f"{route}_denied"
    response = redacted_route_response(candidate, route, status=status, extra=extra_response)
    event = audit_event(candidate, route, allowed, reasons, extra=extra_audit)
    return CopyRouteDecision(allowed=allowed, route=route, status=status, reason_codes=tuple(sorted(set(reasons))), response=response, audit_event=event)


def preview(candidate: CopyCandidate, *, flags: CopyRouteFeatureFlags = DEFAULT_FLAGS, policy: CopyRoutePolicy = DEFAULT_POLICY) -> CopyRouteDecision:
    return make_decision(
        candidate,
        "preview",
        flags=flags,
        policy=policy,
        extra_response={
            "would_require_dry_run": True,
            "would_require_confirm": True,
            "execute_enabled": flags.execute_enabled,
            "rollback_enabled": flags.rollback_enabled,
        },
    )


def dry_run(candidate: CopyCandidate, *, flags: CopyRouteFeatureFlags = DEFAULT_FLAGS, policy: CopyRoutePolicy = DEFAULT_POLICY) -> CopyRouteDecision:
    phrase = approval_phrase(candidate)
    return make_decision(
        candidate,
        "dry-run",
        flags=flags,
        policy=policy,
        extra_response={
            "planned_effect": "create_one_target_file_if_absent",
            "writes_performed": False,
            "rollback_plan": "remove_only_created_target_after_hash_match",
            "approval_phrase": phrase,
            "approval_phrase_hash": stable_hash(phrase),
        },
        extra_audit={"writes_performed": False, "approval_phrase_hash": stable_hash(phrase)},
    )


def _token_payload(candidate: CopyCandidate, *, expires_at: int, nonce: str, operator_user_id: str) -> dict[str, Any]:
    return {
        "token_type": "copy_route_execute_approval",
        "tool_id": COPY_EXECUTE_TOOL_ID,
        "workspace_id": DEFAULT_POLICY.workspace_id,
        "operator_user_id": operator_user_id,
        "candidate_fingerprint": public_candidate_fingerprint(candidate),
        "args_hash": candidate_args_hash(candidate),
        "source_path_hash": path_hash(candidate.source_relative_path),
        "target_path_hash": path_hash(candidate.target_relative_path),
        "action_type": candidate.action_type,
        "expires_at": expires_at,
        "nonce": nonce,
    }


def sign_token_payload(payload: dict[str, Any], secret: str = DEFAULT_SECRET) -> str:
    raw = canonical_json({key: value for key, value in payload.items() if key != "signature"}).encode("utf-8", errors="replace")
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_signed_approval_token(
    candidate: CopyCandidate,
    *,
    secret: str = DEFAULT_SECRET,
    now: int | None = None,
    ttl_seconds: int | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    current = int(time.time() if now is None else now)
    ttl = DEFAULT_POLICY.approval_ttl_seconds if ttl_seconds is None else int(ttl_seconds)
    payload = _token_payload(
        candidate,
        expires_at=current + ttl,
        nonce=nonce or uuid.uuid4().hex,
        operator_user_id=candidate.operator_user_id,
    )
    payload["signature"] = sign_token_payload(payload, secret)
    return payload


def validate_signed_approval_token(
    token: dict[str, Any] | None,
    candidate: CopyCandidate,
    *,
    secret: str = DEFAULT_SECRET,
    now: int | None = None,
    seen_nonces: set[str] | None = None,
) -> tuple[bool, str]:
    if not token:
        return False, "approval_token_missing"
    required = {
        "token_type",
        "tool_id",
        "workspace_id",
        "operator_user_id",
        "candidate_fingerprint",
        "args_hash",
        "source_path_hash",
        "target_path_hash",
        "action_type",
        "expires_at",
        "nonce",
        "signature",
    }
    missing = sorted(required - set(token))
    if missing:
        return False, "approval_token_missing_fields"
    expected = sign_token_payload(token, secret)
    if not hmac.compare_digest(str(token.get("signature")), expected):
        return False, "approval_token_signature_mismatch"
    current = int(time.time() if now is None else now)
    if int(token.get("expires_at", 0)) <= current:
        return False, "approval_token_expired"
    expected_payload = _token_payload(
        candidate,
        expires_at=int(token["expires_at"]),
        nonce=str(token["nonce"]),
        operator_user_id=candidate.operator_user_id,
    )
    for key, expected_value in expected_payload.items():
        if token.get(key) != expected_value:
            return False, f"approval_token_{key}_mismatch"
    if seen_nonces is not None:
        nonce = str(token["nonce"])
        if nonce in seen_nonces:
            return False, "approval_token_nonce_reuse"
        seen_nonces.add(nonce)
    return True, "approval_token_ok"


def confirm(
    candidate: CopyCandidate,
    supplied_phrase: str,
    *,
    flags: CopyRouteFeatureFlags = DEFAULT_FLAGS,
    policy: CopyRoutePolicy = DEFAULT_POLICY,
    secret: str = DEFAULT_SECRET,
    now: int | None = None,
) -> CopyRouteDecision:
    reasons = validation_reasons(candidate, policy)
    if not flags.confirm_enabled:
        reasons.append("confirm_feature_disabled")
    expected_phrase = approval_phrase(candidate)
    if supplied_phrase != expected_phrase:
        reasons.append("approval_phrase_mismatch")
    token: dict[str, Any] | None = None
    if not reasons:
        token = create_signed_approval_token(candidate, secret=secret, now=now, ttl_seconds=policy.approval_ttl_seconds)
    allowed = not reasons
    status = "confirm_allowed_token_issued" if allowed else "confirm_denied"
    response = redacted_route_response(
        candidate,
        "confirm",
        status=status,
        extra={
            "signed_approval_token": token,
            "signed_approval_token_hash": stable_hash(token) if token else None,
            "execute_enabled": flags.execute_enabled,
            "writes_performed": False,
        },
    )
    event = audit_event(
        candidate,
        "confirm",
        allowed,
        reasons,
        extra={
            "approval_phrase_hash": stable_hash(supplied_phrase),
            "token_issued": token is not None,
            "token_hash": stable_hash(token) if token else None,
            "writes_performed": False,
        },
    )
    return CopyRouteDecision(allowed=allowed, route="confirm", status=status, reason_codes=tuple(sorted(set(reasons))), response=response, audit_event=event)


def execute(
    candidate: CopyCandidate,
    *,
    flags: CopyRouteFeatureFlags = DEFAULT_FLAGS,
    policy: CopyRoutePolicy = DEFAULT_POLICY,
    approval_token: dict[str, Any] | None = None,
    operator_approved: bool = False,
    env_enabled: bool = False,
    approval_file_present: bool = False,
    secret: str = DEFAULT_SECRET,
    now: int | None = None,
    seen_nonces: set[str] | None = None,
) -> CopyRouteDecision:
    reasons = validation_reasons(candidate, policy)
    if not flags.execute_enabled:
        reasons.append("execute_feature_disabled")
    if flags.require_execute_env and not env_enabled:
        reasons.append("execute_env_not_enabled")
    if flags.require_operator_approval_file and not approval_file_present:
        reasons.append("operator_approval_file_missing")
    if not operator_approved:
        reasons.append("operator_approval_missing")
    token_ok, token_reason = validate_signed_approval_token(approval_token, candidate, secret=secret, now=now, seen_nonces=seen_nonces)
    if not token_ok:
        reasons.append(token_reason)
    allowed = not reasons
    status = "execute_authorized_for_allowlisted_dispatcher" if allowed else "execute_blocked"
    response = redacted_route_response(
        candidate,
        "execute",
        status=status,
        extra={
            "dispatcher_tool": COPY_EXECUTE_TOOL_ID,
            "execution_performed_by_guard": False,
            "writes_performed": False,
            "blocked_safely": not allowed,
        },
    )
    event = audit_event(
        candidate,
        "execute",
        allowed,
        reasons,
        extra={
            "dispatcher_tool": COPY_EXECUTE_TOOL_ID,
            "execution_performed_by_guard": False,
            "operator_approved": operator_approved,
            "env_enabled": env_enabled,
            "approval_file_present": approval_file_present,
            "token_validation_reason": token_reason,
        },
    )
    return CopyRouteDecision(allowed=allowed, route="execute", status=status, reason_codes=tuple(sorted(set(reasons))), response=response, audit_event=event)


def rollback(
    candidate: CopyCandidate,
    *,
    flags: CopyRouteFeatureFlags = DEFAULT_FLAGS,
    policy: CopyRoutePolicy = DEFAULT_POLICY,
    operator_approved: bool = False,
) -> CopyRouteDecision:
    reasons = validation_reasons(candidate, policy)
    if not flags.rollback_enabled:
        reasons.append("rollback_feature_disabled")
    if not operator_approved:
        reasons.append("rollback_operator_approval_missing")
    allowed = not reasons
    status = "rollback_authorized_for_allowlisted_dispatcher" if allowed else "rollback_blocked"
    response = redacted_route_response(
        candidate,
        "rollback",
        status=status,
        extra={
            "dispatcher_tool": COPY_ROLLBACK_TOOL_ID,
            "rollback_performed_by_guard": False,
            "writes_performed": False,
            "blocked_safely": not allowed,
        },
    )
    event = audit_event(
        candidate,
        "rollback",
        allowed,
        reasons,
        extra={
            "dispatcher_tool": COPY_ROLLBACK_TOOL_ID,
            "rollback_performed_by_guard": False,
            "operator_approved": operator_approved,
        },
    )
    return CopyRouteDecision(allowed=allowed, route="rollback", status=status, reason_codes=tuple(sorted(set(reasons))), response=response, audit_event=event)


def clone_candidate(candidate: CopyCandidate, **overrides: Any) -> CopyCandidate:
    return replace(candidate, **overrides)
