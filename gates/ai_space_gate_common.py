from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report-root", type=Path, default=Path("reports"))
    parser.add_argument("--personal-root", type=Path, default=None)
    parser.add_argument("--no-rebuild", action="store_true")


def write_gate(report_root: Path, name: str, payload: dict[str, Any]) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "generated_at": now()}
    json_path = report_root / f"{name}.json"
    md_path = report_root / f"{name}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# {name}", "", f"verdict: `{payload.get('verdict')}`", ""]
    for item in payload.get("checks", []):
        status = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"- {status}: {item.get('name')} - {item.get('detail')}")
    if payload.get("blockers"):
        lines.extend(["", "## Blockers"])
        for blocker in payload["blockers"]:
            lines.append(f"- {blocker}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def check(name: str, ok: bool, detail: Any = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def verdict(ok_name: str, fail_name: str, checks: list[dict[str, Any]]) -> str:
    return ok_name if all(item.get("ok") for item in checks) else fail_name


def blockers(checks: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("name")) for item in checks if not item.get("ok")]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
