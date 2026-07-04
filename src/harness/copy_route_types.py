from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


COPY_ROUTE_TOOL_ID = "ai_nas_route_copy_guard_v1"
COPY_EXECUTE_TOOL_ID = "ai_nas_action_execute_copy"
COPY_ROLLBACK_TOOL_ID = "ai_nas_action_rollback_copy"


@dataclass(frozen=True)
class CopyRouteFeatureFlags:
    preview_enabled: bool = True
    dry_run_enabled: bool = True
    confirm_enabled: bool = True
    execute_enabled: bool = False
    rollback_enabled: bool = False
    execute_canary_enabled: bool = False
    require_operator_approval_file: bool = True
    require_execute_env: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "CopyRouteFeatureFlags":
        payload = payload or {}
        allowed = set(cls.__dataclass_fields__)
        return cls(**{key: bool(value) for key, value in payload.items() if key in allowed})

    def to_dict(self) -> dict[str, Any]:
        return {
            "preview_enabled": self.preview_enabled,
            "dry_run_enabled": self.dry_run_enabled,
            "confirm_enabled": self.confirm_enabled,
            "execute_enabled": self.execute_enabled,
            "rollback_enabled": self.rollback_enabled,
            "execute_canary_enabled": self.execute_canary_enabled,
            "require_operator_approval_file": self.require_operator_approval_file,
            "require_execute_env": self.require_execute_env,
        }


@dataclass(frozen=True)
class CopyRoutePolicy:
    policy_id: str = "digua_stage4_4_copy_route_policy_v1"
    workspace_id: str = "nas_action"
    allowed_action_type: str = "copy"
    allowed_source_prefixes: tuple[str, ...] = ("Collections/CodexPreflight/source/",)
    allowed_target_prefixes: tuple[str, ...] = ("Collections/CodexPreflight/target/",)
    allowed_source_owner_scopes: tuple[str, ...] = ("operator_visible", "codex_synthetic")
    target_root_prefix: str = "Collections/"
    max_size_bytes: int = 1_048_576
    approval_ttl_seconds: int = 600
    require_source_hash: bool = True
    require_target_absent: bool = True
    require_target_parent_exists: bool = True
    forbid_symlink: bool = True
    forbid_recursive: bool = True
    forbid_overwrite: bool = True
    forbid_qwen_autonomous: bool = True
    forbid_cloud_derived: bool = True
    forbidden_action_types: tuple[str, ...] = (
        "delete",
        "move",
        "rename",
        "chmod",
        "chown",
        "overwrite",
        "recursive",
        "recursive_delete",
        "shell",
    )

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "CopyRoutePolicy":
        payload = payload or {}
        data: dict[str, Any] = {}
        for key in cls.__dataclass_fields__:
            if key not in payload:
                continue
            value = payload[key]
            if key.endswith("prefixes") or key in {"allowed_source_owner_scopes", "forbidden_action_types"}:
                data[key] = tuple(str(item) for item in value)
            else:
                data[key] = value
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "workspace_id": self.workspace_id,
            "allowed_action_type": self.allowed_action_type,
            "allowed_source_prefixes": list(self.allowed_source_prefixes),
            "allowed_target_prefixes": list(self.allowed_target_prefixes),
            "allowed_source_owner_scopes": list(self.allowed_source_owner_scopes),
            "target_root_prefix": self.target_root_prefix,
            "max_size_bytes": self.max_size_bytes,
            "approval_ttl_seconds": self.approval_ttl_seconds,
            "require_source_hash": self.require_source_hash,
            "require_target_absent": self.require_target_absent,
            "require_target_parent_exists": self.require_target_parent_exists,
            "forbid_symlink": self.forbid_symlink,
            "forbid_recursive": self.forbid_recursive,
            "forbid_overwrite": self.forbid_overwrite,
            "forbid_qwen_autonomous": self.forbid_qwen_autonomous,
            "forbid_cloud_derived": self.forbid_cloud_derived,
            "forbidden_action_types": list(self.forbidden_action_types),
        }


@dataclass(frozen=True)
class CopyCandidate:
    action_type: str
    source_relative_path: str
    target_relative_path: str
    source_sha256: str
    expected_size_bytes: int
    source_owner_scope: str
    target_exists_now: bool = False
    target_parent_exists: bool = True
    source_is_symlink: bool = False
    target_parent_is_symlink: bool = False
    requested_by_qwen: bool = False
    cloud_derived: bool = False
    recursive: bool = False
    overwrite: bool = False
    operator_user_id: str = "operator-zhexu"
    candidate_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CopyCandidate":
        required = {
            "action_type",
            "source_relative_path",
            "target_relative_path",
            "source_sha256",
            "expected_size_bytes",
            "source_owner_scope",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"missing candidate fields: {', '.join(missing)}")
        return cls(
            action_type=str(payload["action_type"]),
            source_relative_path=str(payload["source_relative_path"]),
            target_relative_path=str(payload["target_relative_path"]),
            source_sha256=str(payload["source_sha256"]),
            expected_size_bytes=int(payload["expected_size_bytes"]),
            source_owner_scope=str(payload["source_owner_scope"]),
            target_exists_now=bool(payload.get("target_exists_now", False)),
            target_parent_exists=bool(payload.get("target_parent_exists", True)),
            source_is_symlink=bool(payload.get("source_is_symlink", False)),
            target_parent_is_symlink=bool(payload.get("target_parent_is_symlink", False)),
            requested_by_qwen=bool(payload.get("requested_by_qwen", False)),
            cloud_derived=bool(payload.get("cloud_derived", False)),
            recursive=bool(payload.get("recursive", False)),
            overwrite=bool(payload.get("overwrite", False)),
            operator_user_id=str(payload.get("operator_user_id", "operator-zhexu")),
            candidate_id=payload.get("candidate_id"),
            metadata=dict(payload.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "source_relative_path": self.source_relative_path,
            "target_relative_path": self.target_relative_path,
            "source_sha256": self.source_sha256,
            "expected_size_bytes": self.expected_size_bytes,
            "source_owner_scope": self.source_owner_scope,
            "target_exists_now": self.target_exists_now,
            "target_parent_exists": self.target_parent_exists,
            "source_is_symlink": self.source_is_symlink,
            "target_parent_is_symlink": self.target_parent_is_symlink,
            "requested_by_qwen": self.requested_by_qwen,
            "cloud_derived": self.cloud_derived,
            "recursive": self.recursive,
            "overwrite": self.overwrite,
            "operator_user_id": self.operator_user_id,
            "candidate_id": self.candidate_id,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class CopyRouteDecision:
    allowed: bool
    route: str
    status: str
    reason_codes: tuple[str, ...]
    response: dict[str, Any]
    audit_event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "route": self.route,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "response": self.response,
            "audit_event": self.audit_event,
        }
