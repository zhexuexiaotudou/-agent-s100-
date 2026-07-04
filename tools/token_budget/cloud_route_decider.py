from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .privacy_redactor import PrivacyRedactor, find_private_leaks


LOCAL_SIMPLE_TASKS = {
    "nas_search",
    "chinese_search",
    "mixed_zh_en_search",
    "folder_summary",
    "file_organization_suggestion",
}

CLOUD_PUBLIC_TASKS = {
    "document_qa",
    "report_generation",
    "public_research",
    "cloud_sensitive_mixed",
}

INJECTION_RE = re.compile(
    r"(?i)(ignore previous|bypass|exfiltrate|send raw|upload raw|dump secrets|disable redaction|原文发给云|绕过|泄露|忽略.*规则)"
)


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str
    split_private_local: bool = False
    cloud_allowed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "reason": self.reason,
            "split_private_local": self.split_private_local,
            "cloud_allowed": self.cloud_allowed,
        }


class CloudRouteDecider:
    def __init__(self) -> None:
        self.redactor = PrivacyRedactor()

    def decide(self, case: Dict[str, Any], redacted_text: Optional[str] = None) -> RouteDecision:
        task_type = case.get("task_type") or case.get("category") or "unknown"
        prompt = str(case.get("user_prompt", ""))
        context = str(case.get("context_text", ""))
        combined = prompt + "\n" + context
        markers = case.get("private_markers") or []

        if case.get("acl_denied"):
            return RouteDecision("cloud_blocked_private", "acl_denied", cloud_allowed=False)
        if case.get("prompt_injection") or INJECTION_RE.search(combined):
            return RouteDecision("cloud_blocked_private", "prompt_injection_fail_closed", cloud_allowed=False)

        redaction_result = self.redactor.redact(combined)
        has_private = bool(markers) or redaction_result.redaction_count > 0 or bool(find_private_leaks(combined))
        sensitivity = case.get("sensitivity", "")

        if sensitivity == "mixed" and has_private:
            return RouteDecision(
                "cloud_allowed_redacted",
                "mixed_private_public_split",
                split_private_local=True,
                cloud_allowed=True,
            )
        if has_private and task_type in {
            "document_qa",
            "folder_summary",
            "nas_search",
            "chinese_search",
            "mixed_zh_en_search",
            "file_organization_suggestion",
        }:
            return RouteDecision("local_only", "private_context_kept_local", cloud_allowed=False)
        if has_private:
            return RouteDecision("cloud_blocked_private", "raw_private_context_detected", cloud_allowed=False)
        if task_type in LOCAL_SIMPLE_TASKS:
            return RouteDecision("local_only", "simple_local_nas_task", cloud_allowed=False)
        if task_type in CLOUD_PUBLIC_TASKS or case.get("complexity") == "high":
            return RouteDecision("cloud_allowed_redacted", "public_or_redacted_complex_task", cloud_allowed=True)
        return RouteDecision("local_only", "default_local_first", cloud_allowed=False)


def decide_route(case: Dict[str, Any], redacted_text: Optional[str] = None) -> RouteDecision:
    return CloudRouteDecider().decide(case, redacted_text)
