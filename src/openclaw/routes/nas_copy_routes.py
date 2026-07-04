from __future__ import annotations

from pathlib import Path
from typing import Any

from src.openclaw.harness_default_middleware import HarnessDefaultMiddleware


def _middleware(report_root: str | Path | None, personal_root: str | Path | None) -> HarnessDefaultMiddleware:
    return HarnessDefaultMiddleware(report_root=report_root, personal_root=personal_root)


def copy_preview_response(payload: dict[str, Any], *, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    result = _middleware(report_root, personal_root).preview_copy(payload)
    return result.status_code, result.payload


def copy_dry_run_response(payload: dict[str, Any], *, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    result = _middleware(report_root, personal_root).dry_run_copy(payload)
    return result.status_code, result.payload


def copy_confirm_response(payload: dict[str, Any], *, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    result = _middleware(report_root, personal_root).confirm_copy(payload)
    return result.status_code, result.payload


def copy_execute_response(payload: dict[str, Any], *, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    result = _middleware(report_root, personal_root).execute_copy(payload)
    return result.status_code, result.payload


def copy_rollback_response(payload: dict[str, Any], *, report_root: str | Path | None = None, personal_root: str | Path | None = None) -> tuple[int, dict[str, Any]]:
    result = _middleware(report_root, personal_root).rollback_copy(payload)
    return result.status_code, result.payload
