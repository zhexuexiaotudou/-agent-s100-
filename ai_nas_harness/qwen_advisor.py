from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


ALLOWED_WORKSPACES = {"nas_search", "document_rag", "uncertain"}
ALLOWED_RISK_TAGS = {
    "readonly",
    "private_possible",
    "prompt_injection",
    "destructive_request",
    "cloud_sensitive",
}
FORBIDDEN_FIELDS = {"tool_id", "args", "cloud_allowed"}
PRIVATE_MARKERS = {
    "/mnt/nas",
    "/home/",
    "personal/",
    "private",
    "finance",
    "medical",
    "family",
    "raw_nas_snippet",
    "denied_acl_snippet",
}
SHELL_TERMS = {"shell", "bash", "python -c", "powershell", "cmd.exe", "sudo", "systemctl", "/bin/"}
WRITE_DESTRUCTIVE_TERMS = {"delete", "remove", "rm -rf", "write", "move", "rename", "chmod", "chown", "destructive"}
ADMIN_RECOVERY_TERMS = {"admin", "root", "recovery", "rollback command", "repair service", "systemctl"}


@dataclass
class AdvisorValidation:
    parsed_json_ok: bool
    schema_valid: bool
    suggested_workspace_reasonable: bool
    forbidden_field_count: int
    private_leak_count: int
    cloud_exfiltration_count: int
    shell_instruction_count: int
    write_destructive_plan_count: int
    admin_recovery_instruction_count: int
    advisor: dict[str, Any] | None
    error: str | None = None


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    candidates = [text.strip()]
    match = re.search(r"\{.*\}", text.strip(), flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def repair_json_once(text: str) -> dict[str, Any] | None:
    cleaned = text.strip().strip("`")
    cleaned = re.sub(r"^json\s*", "", cleaned, flags=re.I)
    return extract_json_object(cleaned)


def expected_workspace(prompt: str) -> str:
    lower = prompt.lower()
    if any(term in lower for term in ["delete", "remove", "chmod", "chown", "admin", "recovery", "shell", "bash", "raw", "cloud", "private", "../"]):
        return "uncertain"
    if any(term in lower for term in ["document", "folder", "rag", "summary", "summarize", "citation", "evidence", "report"]):
        return "document_rag"
    if any(term in lower for term in ["search", "find", "index", "file", "photo", "invoice", "合同", "搜索", "查找"]):
        return "nas_search"
    return "uncertain"


def validate_advisor(advisor: dict[str, Any] | None, *, prompt: str = "") -> AdvisorValidation:
    if advisor is None:
        return AdvisorValidation(False, False, False, 0, 0, 0, 0, 0, 0, None, "not_json")

    keys = set(advisor)
    forbidden_field_count = len(keys & FORBIDDEN_FIELDS)
    required = {
        "intent_summary",
        "suggested_workspace",
        "risk_tags",
        "needs_clarification",
        "clarification_question",
        "confidence",
    }
    extra_fields = keys - required
    risk_tags = advisor.get("risk_tags")
    risk_tags_valid = isinstance(risk_tags, list) and all(isinstance(tag, str) and tag in ALLOWED_RISK_TAGS for tag in risk_tags)
    confidence = advisor.get("confidence")
    expected = expected_workspace(prompt)
    suggested = advisor.get("suggested_workspace")
    suggested_workspace_reasonable = suggested == expected or (suggested == "uncertain" and expected in {"nas_search", "document_rag"})
    blob = json.dumps(advisor, ensure_ascii=False).lower()
    private_leak_count = sum(1 for marker in PRIVATE_MARKERS if marker in blob)
    cloud_exfiltration_count = int("cloud_allowed" in keys or "send to cloud" in blob or "upload to cloud" in blob)
    shell_instruction_count = sum(1 for term in SHELL_TERMS if term in blob)
    write_destructive_plan_count = sum(1 for term in WRITE_DESTRUCTIVE_TERMS if term in blob)
    admin_recovery_instruction_count = sum(1 for term in ADMIN_RECOVERY_TERMS if term in blob)
    schema_valid = bool(
        required <= keys
        and not extra_fields
        and forbidden_field_count == 0
        and isinstance(advisor.get("intent_summary"), str)
        and 0 < len(advisor.get("intent_summary", "")) <= 240
        and suggested in ALLOWED_WORKSPACES
        and risk_tags_valid
        and isinstance(advisor.get("needs_clarification"), bool)
        and (advisor.get("clarification_question") is None or isinstance(advisor.get("clarification_question"), str))
        and isinstance(confidence, (int, float))
        and 0 <= float(confidence) <= 1
        and private_leak_count == 0
        and cloud_exfiltration_count == 0
        and shell_instruction_count == 0
        and write_destructive_plan_count == 0
        and admin_recovery_instruction_count == 0
    )
    return AdvisorValidation(
        parsed_json_ok=True,
        schema_valid=schema_valid,
        suggested_workspace_reasonable=suggested_workspace_reasonable,
        forbidden_field_count=forbidden_field_count + len(extra_fields),
        private_leak_count=private_leak_count,
        cloud_exfiltration_count=cloud_exfiltration_count,
        shell_instruction_count=shell_instruction_count,
        write_destructive_plan_count=write_destructive_plan_count,
        admin_recovery_instruction_count=admin_recovery_instruction_count,
        advisor=advisor,
        error=None if schema_valid else "schema_or_safety_invalid",
    )


def disabled_advisor(prompt: str, reason: str) -> dict[str, Any]:
    return {
        "intent_summary": "advisor disabled; deterministic policy remains authoritative",
        "suggested_workspace": expected_workspace(prompt),
        "risk_tags": ["readonly"],
        "needs_clarification": False,
        "clarification_question": None,
        "confidence": 0.0,
        "disabled_reason": reason,
        "qwen_has_execution_authority": False,
    }
