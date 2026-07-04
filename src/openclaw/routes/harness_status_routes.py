from __future__ import annotations

from pathlib import Path
from typing import Any

from src.openclaw.harness_default_middleware import HarnessDefaultMiddleware


def harness_status_response(*, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> dict[str, Any]:
    return HarnessDefaultMiddleware(report_root=report_root, personal_root=personal_root).status()
