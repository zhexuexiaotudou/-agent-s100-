from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_nas_harness.config_io import safe_write_json, utc_stamp
from src.harness.copy_route_guard import (
    approval_phrase,
    candidate_args_hash,
    clone_candidate,
    confirm,
    dry_run,
    execute,
    path_hash,
    preview,
    public_candidate_fingerprint,
    rollback,
    stable_hash,
)
from src.agent_runtime.service import AgentRuntimeService
from src.harness.copy_route_types import COPY_EXECUTE_TOOL_ID, COPY_ROLLBACK_TOOL_ID, CopyCandidate, CopyRouteFeatureFlags, CopyRoutePolicy
from src.harness.token_budget_integration import route_token_budget


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FLAGS_PATH = REPO_ROOT / "configs" / "harness_default_service_feature_flags.json"
DEFAULT_POLICY_PATH = REPO_ROOT / "configs" / "harness_default_service_policy.json"
COPY_ROUTE_POLICY_PATH = REPO_ROOT / "configs" / "copy_route_policy.json"
DEFAULT_DISPATCHER = "/mnt/nas/openclaw/scripts/probes/ai_nas_allowlisted_tool.sh"
DEFAULT_PERSONAL_ROOT = Path(os.environ.get("AI_NAS_PERSONAL_ROOT", "/mnt/nas/openclaw/Personal"))
DEFAULT_REPORT_ROOT = Path(os.environ.get("AI_NAS_REPORT_ROOT", "/mnt/nas/openclaw/reports/ai_nas_mvp"))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import hashlib

    return hashlib.sha256(encoded).hexdigest()


def _stable_action_id(action_type: str, source_relative_path: str, target_relative_path: str) -> str:
    import hashlib

    raw = f"{action_type}\0{source_relative_path}\0{target_relative_path}".encode("utf-8")
    return f"{action_type}-{hashlib.sha256(raw).hexdigest()[:16]}"


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


@dataclass
class DefaultServiceResponse:
    status_code: int
    payload: dict[str, Any]


class HarnessDefaultMiddleware:
    def __init__(
        self,
        *,
        personal_root: str | Path | None = None,
        report_root: str | Path | None = None,
        dispatcher: str | Path | None = None,
        feature_flags_path: str | Path | None = None,
        service_policy_path: str | Path | None = None,
        copy_route_policy_path: str | Path | None = None,
    ) -> None:
        self.personal_root = Path(personal_root) if personal_root else DEFAULT_PERSONAL_ROOT
        self.report_root = Path(report_root) if report_root else DEFAULT_REPORT_ROOT
        self.dispatcher = str(dispatcher or DEFAULT_DISPATCHER)
        self.feature_flags = _read_json(Path(feature_flags_path) if feature_flags_path else DEFAULT_FLAGS_PATH)
        self.service_policy = _read_json(Path(service_policy_path) if service_policy_path else DEFAULT_POLICY_PATH)
        self.copy_policy = CopyRoutePolicy.from_dict(_read_json(Path(copy_route_policy_path) if copy_route_policy_path else COPY_ROUTE_POLICY_PATH))

    def _copy_flags(self, *, execute_enabled: bool = False, rollback_enabled: bool = False) -> CopyRouteFeatureFlags:
        return CopyRouteFeatureFlags(
            preview_enabled=bool(self.feature_flags.get("copy_preview_enabled", True)),
            dry_run_enabled=bool(self.feature_flags.get("copy_dry_run_enabled", True)),
            confirm_enabled=bool(self.feature_flags.get("copy_confirm_enabled", True)),
            execute_enabled=execute_enabled and bool(self.feature_flags.get("copy_execute_enabled", False)),
            rollback_enabled=rollback_enabled and bool(self.feature_flags.get("copy_rollback_enabled", False)),
            execute_canary_enabled=execute_enabled and bool(self.feature_flags.get("copy_execute_enabled", False)),
            require_operator_approval_file=True,
            require_execute_env=True,
        )

    def status(self) -> dict[str, Any]:
        dispatcher_path = Path(self.dispatcher)
        try:
            agent_runtime = AgentRuntimeService(report_root=self.report_root, personal_root=self.personal_root).status()
        except Exception as exc:
            agent_runtime = {
                "ok": False,
                "service": "agent_runtime",
                "error": f"agent_runtime_status_failed:{type(exc).__name__}:{exc}",
                "qwen_execution_authority": False,
                "cloud_private_raw_egress": False,
                "public_mcp_exposed": False,
            }
        return {
            "ok": bool(self.feature_flags.get("harness_default_service_enabled", False)),
            "service": "harness_default_service",
            "policy_id": self.service_policy.get("policy_id"),
            "readonly_workspaces_enabled": bool(self.feature_flags.get("readonly_workspaces_enabled", False)),
            "token_budget_gate_enabled": bool(self.feature_flags.get("token_budget_gate_enabled", False)),
            "privacy_redaction_gate_enabled": bool(self.feature_flags.get("privacy_redaction_gate_enabled", False)),
            "copy_routes": self.service_policy.get("copy_routes", []),
            "copy_execute_enabled": bool(self.feature_flags.get("copy_execute_enabled", False)),
            "copy_execute_requires": {
                "user_confirmation": bool(self.feature_flags.get("copy_execute_requires_user_confirmation", False)),
                "signed_token": bool(self.feature_flags.get("copy_execute_requires_signed_token", False)),
                "source_rehash": bool(self.feature_flags.get("copy_execute_requires_source_rehash", False)),
                "target_absent": bool(self.feature_flags.get("copy_execute_requires_target_absent", False)),
                "dispatcher": bool(self.feature_flags.get("copy_execute_requires_dispatcher", False)),
            },
            "forbidden_actions": self.service_policy.get("forbidden_actions", []),
            "qwen_execution_authority": False,
            "cloud_private_raw_egress": False,
            "dispatcher": self.dispatcher,
            "dispatcher_exists": dispatcher_path.exists(),
            "dispatcher_sha256": _sha256_file(dispatcher_path) if dispatcher_path.exists() and dispatcher_path.is_file() else None,
            "raw_private_content_in_status": False,
            "agent_runtime": agent_runtime,
        }

    def candidate_from_payload(self, payload: dict[str, Any]) -> CopyCandidate:
        source_rel = str(payload.get("source_relative_path") or payload.get("source") or "")
        target_rel = str(payload.get("target_relative_path") or payload.get("target") or "")
        source_path = self.personal_root / source_rel
        source_sha = str(payload.get("source_sha256") or "")
        expected_size = int(payload.get("expected_size_bytes") or 0)
        if source_path.exists() and source_path.is_file():
            source_sha = source_sha or _sha256_file(source_path)
            expected_size = expected_size or source_path.stat().st_size
        stable_candidate_id = payload.get("candidate_id")
        if not stable_candidate_id:
            stable_candidate_id = "default-service-" + stable_hash(
                {
                    "source_relative_path": source_rel,
                    "target_relative_path": target_rel,
                    "source_sha256": source_sha,
                    "expected_size_bytes": expected_size,
                }
            )[:16]
        return CopyCandidate(
            action_type=str(payload.get("action_type") or "copy"),
            source_relative_path=source_rel,
            target_relative_path=target_rel,
            source_sha256=source_sha,
            expected_size_bytes=expected_size,
            source_owner_scope=str(payload.get("source_owner_scope") or "operator_visible"),
            target_exists_now=bool(payload.get("target_exists_now", (self.personal_root / target_rel).exists() if target_rel else False)),
            target_parent_exists=bool(payload.get("target_parent_exists", (self.personal_root / target_rel).parent.exists() if target_rel else False)),
            source_is_symlink=bool(payload.get("source_is_symlink", source_path.is_symlink() if source_rel else False)),
            target_parent_is_symlink=bool(payload.get("target_parent_is_symlink", (self.personal_root / target_rel).parent.is_symlink() if target_rel else False)),
            requested_by_qwen=bool(payload.get("requested_by_qwen", False)),
            cloud_derived=bool(payload.get("cloud_derived", False)),
            recursive=bool(payload.get("recursive", False)),
            overwrite=bool(payload.get("overwrite", False)),
            operator_user_id=str(payload.get("operator_user_id") or "operator-web-ui"),
            candidate_id=str(stable_candidate_id),
        )

    def _redacted_payload(self, candidate: CopyCandidate, route: str, decision: Any) -> dict[str, Any]:
        return {
            "ok": decision.allowed,
            "route": route,
            "status": decision.status,
            "reason_codes": list(decision.reason_codes),
            "candidate_fingerprint": public_candidate_fingerprint(candidate),
            "source_path_hash": path_hash(candidate.source_relative_path),
            "target_path_hash": path_hash(candidate.target_relative_path),
            "source_sha256_prefix": candidate.source_sha256[:12],
            "expected_size_bytes": candidate.expected_size_bytes,
            "qwen_execution_authority": False,
            "cloud_private_egress": False,
            "raw_paths_in_response": False,
            "audit_event": decision.audit_event,
        }

    def preview_copy(self, payload: dict[str, Any]) -> DefaultServiceResponse:
        candidate = self.candidate_from_payload(payload)
        decision = preview(candidate, flags=self._copy_flags(), policy=self.copy_policy)
        return DefaultServiceResponse(200 if decision.allowed else 400, self._redacted_payload(candidate, "preview", decision))

    def dry_run_copy(self, payload: dict[str, Any]) -> DefaultServiceResponse:
        candidate = self.candidate_from_payload(payload)
        decision = dry_run(candidate, flags=self._copy_flags(), policy=self.copy_policy)
        result = self._redacted_payload(candidate, "dry-run", decision)
        result["approval_phrase"] = approval_phrase(candidate) if decision.allowed else None
        result["rollback_plan"] = "remove only this action-created target after target sha256 verification"
        result["destructive_actions_available"] = False
        return DefaultServiceResponse(200 if decision.allowed else 400, result)

    def confirm_copy(self, payload: dict[str, Any]) -> DefaultServiceResponse:
        candidate = self.candidate_from_payload(payload)
        supplied_phrase = str(payload.get("approval_phrase") or "")
        decision = confirm(candidate, supplied_phrase, flags=self._copy_flags(), policy=self.copy_policy)
        result = self._redacted_payload(candidate, "confirm", decision)
        result["signed_approval_token"] = decision.response.get("signed_approval_token")
        result["signed_approval_token_hash"] = decision.response.get("signed_approval_token_hash")
        return DefaultServiceResponse(200 if decision.allowed else 400, result)

    def _verify_before_execute(self, candidate: CopyCandidate) -> tuple[bool, str, dict[str, Any]]:
        source = self.personal_root / candidate.source_relative_path
        target = self.personal_root / candidate.target_relative_path
        if not source.exists() or not source.is_file() or source.is_symlink():
            return False, "source_missing_or_not_regular_file", {}
        source_sha = _sha256_file(source)
        if source_sha != candidate.source_sha256:
            return False, "source_sha256_mismatch", {"actual_source_sha256": source_sha}
        if target.exists():
            return False, "target_exists_no_overwrite", {}
        if target.parent.is_symlink():
            return False, "target_parent_symlink", {}
        return True, "pre_execute_ok", {"source_sha256": source_sha, "target_exists": False}

    def _approval_manifest(self, candidate: CopyCandidate) -> dict[str, Any]:
        action_id = _stable_action_id("copy", candidate.source_relative_path, candidate.target_relative_path)
        manifest_id = "apm-" + _hash_payload(
            {
                "action_id": action_id,
                "candidate_fingerprint": public_candidate_fingerprint(candidate),
                "args_hash": candidate_args_hash(candidate),
                "created_by": "harness_default_service",
            }
        )[:16]
        manifest = {
            "generated_at": utc_stamp(),
            "tool_id": "ai_nas_action_approval_manifest",
            "manifest_id": manifest_id,
            "status": "awaiting_human_confirmation",
            "personal_root": str(self.personal_root),
            "query": "harness_default_service_copy",
            "collection_name": "HarnessDefaultService",
            "proposed_actions": [
                {
                    "action_id": action_id,
                    "action_type": "copy",
                    "status": "proposed_requires_human_confirmation",
                    "source_relative_path": candidate.source_relative_path,
                    "source_absolute_path": str(self.personal_root / candidate.source_relative_path),
                    "source_sha256": candidate.source_sha256,
                    "target_relative_path": candidate.target_relative_path,
                    "target_absolute_path": str(self.personal_root / candidate.target_relative_path),
                    "target_exists_now": candidate.target_exists_now,
                    "permission_level_required": "bounded-user-confirmed-copy",
                    "requires_human_confirmation": True,
                    "destructive": False,
                    "write_effect": "create one target file only if absent; never overwrite; never delete source",
                }
            ],
            "approval": {
                "required": True,
                "approval_phrase": f"APPROVE {manifest_id}",
                "approval_scope": "single copy action listed by exact action_id",
                "execution_allowed_by_this_tool": False,
            },
            "audit": {
                "tool_id": "ai_nas_action_approval_manifest",
                "source_files_modified": False,
                "delete_performed": False,
                "move_performed": False,
                "overwrite_performed": False,
                "execution_performed": False,
                "qwen_execution_authority": False,
                "cloud_private_egress": False,
            },
        }
        manifest["manifest_sha256"] = _hash_payload(manifest)
        return manifest

    def execute_copy(self, payload: dict[str, Any]) -> DefaultServiceResponse:
        candidate = self.candidate_from_payload(payload)
        token = payload.get("signed_approval_token")
        typed_phrase = str(payload.get("approval_phrase") or "")
        if typed_phrase != approval_phrase(candidate):
            return DefaultServiceResponse(403, {"ok": False, "error": "approval_phrase_mismatch", "qwen_execution_authority": False})
        pre_ok, pre_reason, pre_detail = self._verify_before_execute(candidate)
        if not pre_ok:
            return DefaultServiceResponse(409, {"ok": False, "error": pre_reason, "detail": pre_detail, "qwen_execution_authority": False})
        decision = execute(
            candidate,
            flags=self._copy_flags(execute_enabled=True),
            policy=self.copy_policy,
            approval_token=token if isinstance(token, dict) else None,
            operator_approved=True,
            env_enabled=True,
            approval_file_present=True,
        )
        if not decision.allowed:
            result = self._redacted_payload(candidate, "execute", decision)
            return DefaultServiceResponse(403, result)
        manifest = self._approval_manifest(candidate)
        run_dir = self.report_root / f"harness_default_service_copy_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = run_dir / "approval_manifest.json"
        safe_write_json(manifest_path, manifest)
        env = os.environ.copy()
        env["AI_NAS_PERSONAL_ROOT"] = str(self.personal_root)
        env["AI_NAS_REPORT_ROOT"] = str(run_dir)
        completed = subprocess.run(
            [
                self.dispatcher,
                COPY_EXECUTE_TOOL_ID,
                str(manifest_path),
                manifest["approval"]["approval_phrase"],
                "--report-root",
                str(run_dir),
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=120,
            env=env,
        )
        report_candidates = sorted(run_dir.glob("action_execute_copy_*/action_execute_copy.json"), key=lambda item: item.stat().st_mtime)
        report_payload = _read_json(report_candidates[-1]) if report_candidates else {}
        target = self.personal_root / candidate.target_relative_path
        target_sha = _sha256_file(target) if target.exists() and target.is_file() else None
        ok = completed.returncode == 0 and report_payload.get("executed_count") == 1 and target_sha == candidate.source_sha256
        return DefaultServiceResponse(
            200 if ok else 500,
            {
                "ok": ok,
                "route": "execute",
                "status": "completed" if ok else "failed",
                "candidate_fingerprint": public_candidate_fingerprint(candidate),
                "source_path_hash": path_hash(candidate.source_relative_path),
                "target_path_hash": path_hash(candidate.target_relative_path),
                "target_sha256": target_sha,
                "target_hash_verified": target_sha == candidate.source_sha256,
                "dispatcher_tool": COPY_EXECUTE_TOOL_ID,
                "dispatcher_bypass": False,
                "dispatcher_returncode": completed.returncode,
                "dispatcher_stdout_hash": stable_hash(completed.stdout),
                "dispatcher_stderr_hash": stable_hash(completed.stderr),
                "manifest_id": manifest["manifest_id"],
                "approval_manifest_path": str(manifest_path),
                "rollback_manifest_path": str(run_dir / report_candidates[-1].parent.name / "rollback_manifest.json") if report_candidates else None,
                "qwen_execution_authority": False,
                "cloud_private_egress": False,
                "raw_paths_in_response": False,
            },
        )

    def rollback_copy(self, payload: dict[str, Any]) -> DefaultServiceResponse:
        candidate = self.candidate_from_payload(payload)
        route_candidate = clone_candidate(candidate, target_exists_now=False)
        rollback_manifest_path = Path(str(payload.get("rollback_manifest_path") or ""))
        rollback_phrase = str(payload.get("rollback_phrase") or "")
        if not rollback_manifest_path or not _is_relative_to(rollback_manifest_path, self.report_root):
            return DefaultServiceResponse(403, {"ok": False, "error": "rollback_manifest_outside_report_root", "qwen_execution_authority": False})
        decision = rollback(route_candidate, flags=self._copy_flags(rollback_enabled=True), policy=self.copy_policy, operator_approved=True)
        if not decision.allowed:
            return DefaultServiceResponse(403, self._redacted_payload(route_candidate, "rollback", decision))
        env = os.environ.copy()
        env["AI_NAS_PERSONAL_ROOT"] = str(self.personal_root)
        env["AI_NAS_REPORT_ROOT"] = str(self.report_root)
        completed = subprocess.run(
            [
                self.dispatcher,
                COPY_ROLLBACK_TOOL_ID,
                str(rollback_manifest_path),
                rollback_phrase,
                "--report-root",
                str(self.report_root),
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=120,
            env=env,
        )
        target = self.personal_root / candidate.target_relative_path
        source = self.personal_root / candidate.source_relative_path
        source_sha = _sha256_file(source) if source.exists() and source.is_file() else None
        ok = completed.returncode == 0 and not target.exists() and source_sha == candidate.source_sha256
        return DefaultServiceResponse(
            200 if ok else 500,
            {
                "ok": ok,
                "route": "rollback",
                "status": "completed" if ok else "failed",
                "candidate_fingerprint": public_candidate_fingerprint(candidate),
                "source_path_hash": path_hash(candidate.source_relative_path),
                "target_path_hash": path_hash(candidate.target_relative_path),
                "target_missing": not target.exists(),
                "source_hash_unchanged": source_sha == candidate.source_sha256,
                "dispatcher_tool": COPY_ROLLBACK_TOOL_ID,
                "dispatcher_bypass": False,
                "dispatcher_returncode": completed.returncode,
                "dispatcher_stdout_hash": stable_hash(completed.stdout),
                "dispatcher_stderr_hash": stable_hash(completed.stderr),
                "qwen_execution_authority": False,
                "cloud_private_egress": False,
                "raw_paths_in_response": False,
            },
        )

    def token_budget_route(self, payload: dict[str, Any]) -> DefaultServiceResponse:
        if not self.feature_flags.get("token_budget_gate_enabled", False):
            return DefaultServiceResponse(503, {"ok": False, "error": "token_budget_gate_disabled"})
        result = route_token_budget(payload)
        result["qwen_execution_authority"] = False
        return DefaultServiceResponse(200 if result.get("ok") else 400, result)
