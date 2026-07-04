from __future__ import annotations

from pathlib import Path
from typing import Any

from src.openclaw.harness_default_middleware import HarnessDefaultMiddleware


def token_budget_route_response(payload: dict[str, Any], *, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    result = HarnessDefaultMiddleware(report_root=report_root, personal_root=personal_root).token_budget_route(payload)
    return result.status_code, result.payload
