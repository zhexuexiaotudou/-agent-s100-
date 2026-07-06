from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def write_rollback_manifest(report_root: Path, plan_id: str, payload: dict[str, Any]) -> Path:
    run_dir = report_root / "auto_organizer" / plan_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "rollback_manifest.json"
    enriched = {
        "generated_at": _now(),
        "schema": "digua_auto_organizer_rollback_v1",
        **payload,
    }
    path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
