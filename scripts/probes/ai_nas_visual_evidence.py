#!/usr/bin/env python3
"""Small helpers for user-facing visual evidence payloads."""

from __future__ import annotations

from typing import Any


def evidence_item(
    evidence_type: str,
    *,
    label: str = "",
    confidence: float | None = None,
    model_id: str = "",
    runtime: str = "",
    region_id: int | str | None = None,
    artifact_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "type": evidence_type,
        "label": label,
        "model_id": model_id,
        "runtime": runtime,
        "metadata": metadata or {},
    }
    if confidence is not None:
        payload["confidence"] = max(0.0, min(1.0, float(confidence)))
    if region_id is not None:
        payload["region_id"] = region_id
    if artifact_id:
        payload["artifact_id"] = artifact_id
    return payload


def degradation_item(reason: str, *, stage: str, confidence_cap: float = 0.35) -> dict:
    return {
        "active": True,
        "stage": stage,
        "reason": reason,
        "confidence_cap": max(0.0, min(1.0, float(confidence_cap))),
    }


def evidence_chips(evidence: list[dict]) -> list[str]:
    chips: list[str] = []
    for item in evidence:
        label = str(item.get("label") or item.get("type") or "").strip()
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)):
            chips.append(f"{label} {float(confidence):.2f}".strip())
        elif label:
            chips.append(label)
    return chips
