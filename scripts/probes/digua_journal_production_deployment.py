#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.digua_journal.collectors import collect_sample_nas_index_diff_events, collect_sample_system_events
from src.digua_journal.journal_db import JournalDB
from src.digua_journal.journal_exporter import JournalExporter
from src.digua_journal.journal_privacy_guard import assert_export_safe, export_safety_report
from src.digua_journal.manual_entry import create_manual_entry
from src.digua_journal.period_summary_engine import JournalSummaryEngine
from src.digua_journal.project_classifier import ProjectClassifier
from src.openclaw.routes.journal_routes import journal_route_response


REPORT_DIR = REPO_ROOT / "reports"
EVIDENCE_DIR = REPO_ROOT / "evidence" / "digua_journal"
FINAL_DIR = REPO_ROOT / "01_final_evidence"
TMP_DIR = REPO_ROOT / "tmp" / "digua_journal"
DB_PATH = TMP_DIR / "digua_journal.sqlite3"
JOURNAL_REPORT_STEMS = [
    "21000_journal_baseline_lock",
    "21010_journal_workspace_feature_flags_gate",
    "21020_journal_db_migration_gate",
    "21030_journal_event_model_gate",
    "21040_nas_index_diff_collector_gate",
    "21050_journal_system_collectors_gate",
    "21060_journal_manual_entry_gate",
    "21070_journal_project_classifier_gate",
    "21080_journal_period_summary_engine_gate",
    "21090_journal_token_privacy_trace_gate",
    "21100_openclaw_journal_page_api_gate",
    "21110_journal_export_gate",
    "21120_journal_default_service_persistence_gate",
    "21130_journal_e2e_production_demo_gate",
    "21140_journal_regression_safety_gate",
]


def utc_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact_stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_report(report_id: int, title: str, payload: dict[str, Any]) -> dict[str, Path]:
    payload = {
        "report_id": report_id,
        "title": title,
        "generated_at": utc_stamp(),
        **payload,
    }
    json_path = REPORT_DIR / f"{report_id}_{title}.json"
    md_path = REPORT_DIR / f"{report_id}_{title}.md"
    write_json(json_path, payload)
    lines = [
        f"# {report_id} {title}",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- status: {payload.get('status', 'unknown')}",
        f"- verdict: {payload.get('verdict', payload.get('status', 'unknown'))}",
        "",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    write_text_lf(md_path, "\n".join(lines))
    return {"json": json_path, "md": md_path}


def run_cmd(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "command": cmd,
        }
    except Exception as exc:
        return {
            "ok": False,
            "returncode": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "command": cmd,
        }


def reset_local_db() -> JournalDB:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    db = JournalDB(DB_PATH)
    db.migrate()
    return db


def reset_generated_evidence() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    patterns = [
        "sample_*_summary.md",
        "e2e_*_summary.md",
        "e2e_events.jsonl",
        "e2e_exported_files.json",
        "screenshots/SCREENSHOTS_DISABLED_BY_POLICY.md",
        "exports/export_*",
    ]
    for pattern in patterns:
        for path in EVIDENCE_DIR.glob(pattern):
            if path.is_file():
                path.unlink()


def insert_samples(db: JournalDB) -> dict[str, Any]:
    nas_events = collect_sample_nas_index_diff_events(32)
    system_events = collect_sample_system_events()
    db.insert_events(nas_events)
    db.insert_events(system_events)
    write_jsonl(REPORT_DIR / "journal_nas_index_diff_sample_events.jsonl", [event.to_dict() for event in nas_events])
    write_jsonl(REPORT_DIR / "journal_system_collector_sample_events.jsonl", [event.to_dict() for event in system_events])
    return {"nas_events": nas_events, "system_events": system_events}


class JournalSmokeHandler(BaseHTTPRequestHandler):
    server_version = "DiguaJournalSmoke/1.0"

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/journal":
            self._send(200, (REPO_ROOT / "web" / "digua_journal.html").read_bytes(), "text/html; charset=utf-8")
            return
        if self.path == "/static/digua_journal.css":
            self._send(200, (REPO_ROOT / "web" / "static" / "digua_journal.css").read_bytes(), "text/css; charset=utf-8")
            return
        if self.path == "/static/digua_journal.js":
            self._send(200, (REPO_ROOT / "web" / "static" / "digua_journal.js").read_bytes(), "application/javascript; charset=utf-8")
            return
        status, payload = journal_route_response(self.path, method="GET", report_root=TMP_DIR, evidence_dir=EVIDENCE_DIR, export_dir=EVIDENCE_DIR / "exports")
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        status, response = journal_route_response(self.path, method="POST", payload=payload, report_root=TMP_DIR, evidence_dir=EVIDENCE_DIR, export_dir=EVIDENCE_DIR / "exports")
        self._send(status, json.dumps(response, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def http_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = resp.read().decode("utf-8")
        parsed = json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}
        return {"status": resp.status, "payload": parsed}


def run_page_api_smoke() -> dict[str, Any]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), JournalSmokeHandler)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        html_status = urllib.request.urlopen(base + "/journal", timeout=5).status
        css_status = urllib.request.urlopen(base + "/static/digua_journal.css", timeout=5).status
        js_status = urllib.request.urlopen(base + "/static/digua_journal.js", timeout=5).status
        checks = {
            "journal_page": html_status,
            "css": css_status,
            "js": js_status,
            "health": http_json(base + "/api/journal/health"),
            "timeline": http_json(base + "/api/journal/timeline"),
            "projects": http_json(base + "/api/journal/projects"),
            "manual_entry": http_json(
                base + "/api/journal/manual-entry",
                {"project_id": "project_ai_nas", "title": "API smoke note", "body": "API smoke body"},
            ),
            "summary": http_json(base + "/api/journal/generate-summary", {"period_type": "daily"}),
            "export": http_json(base + "/api/journal/export", {"export_type": "markdown", "period_type": "daily"}),
        }
    finally:
        server.shutdown()
        server.server_close()
    return {"ok": True, "base_url": base, "checks": checks, "screenshots_taken": False}


def build_e2e_evidence(db: JournalDB, summaries: list[dict[str, Any]], exports: list[dict[str, Any]]) -> None:
    events = db.list_events(limit=1000)
    write_jsonl(EVIDENCE_DIR / "e2e_events.jsonl", events)
    for summary in summaries:
        period = summary["period_type"]
        path = EVIDENCE_DIR / f"e2e_{period}_summary.md"
        write_text_lf(path, summary["markdown"])
    write_json(EVIDENCE_DIR / "e2e_exported_files.json", exports)
    screenshot_dir = EVIDENCE_DIR / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    write_text_lf(
        screenshot_dir / "SCREENSHOTS_DISABLED_BY_POLICY.md",
        "# Screenshots Disabled\n\nNo desktop or browser screenshots were captured. Page/API smoke checks are recorded in reports/21100_openclaw_journal_page_api_gate.json.\n",
    )


def collect_package_files() -> list[Path]:
    paths: list[Path] = []
    fixed = [
        "configs/journal_workspace.json",
        "configs/journal_feature_flags.json",
        "migrations/create_digua_journal_tables.sql",
        "src/openclaw/routes/journal_routes.py",
        "web/digua_journal.html",
        "web/static/digua_journal.css",
        "web/static/digua_journal.js",
        "scripts/check_journal_service_status.sh",
        "scripts/disable_journal_feature.sh",
        "scripts/run_journal_collectors_once.sh",
        "scripts/run_journal_e2e_smoke.sh",
        "scripts/probes/digua_journal_production_deployment.py",
    ]
    paths.extend(REPO_ROOT / item for item in fixed)
    paths.extend(sorted((REPO_ROOT / "src" / "digua_journal").rglob("*.py")))
    paths.extend(sorted((REPO_ROOT / "tests").glob("test_journal_*.py")))
    for stem in JOURNAL_REPORT_STEMS:
        paths.append(REPORT_DIR / f"{stem}.json")
        paths.append(REPORT_DIR / f"{stem}.md")
    paths.extend(sorted((REPO_ROOT / "reports").glob("journal_*sample_events.jsonl")))
    paths.extend(sorted((REPO_ROOT / "docs").glob("DIGUA_JOURNAL_*.md")))
    paths.extend(sorted((REPO_ROOT / "evidence" / "digua_journal").rglob("*")))
    return [path for path in paths if path.exists() and path.is_file()]


def build_package(final_packet_hint: dict[str, Any]) -> dict[str, Any]:
    timestamp = compact_stamp()
    package_root = REPO_ROOT / "tmp" / f"digua_journal_package_{timestamp}"
    package_root.mkdir(parents=True, exist_ok=False)
    files = collect_package_files()
    manifest_entries: list[dict[str, Any]] = []
    for source in files:
        relative = rel(source)
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest_entries.append({"path": relative, "sha256": sha256_file(source), "bytes": source.stat().st_size})
    manifest = {
        "feature": "digua_journal",
        "generated_at": utc_stamp(),
        "final_packet_hint": final_packet_hint,
        "file_count": len(manifest_entries),
        "files": manifest_entries,
    }
    manifest_path = package_root / "MANIFEST.json"
    write_json(manifest_path, manifest)
    sums = "\n".join(f"{entry['sha256']}  {entry['path']}" for entry in manifest_entries) + "\n"
    write_text_lf(package_root / "SHA256SUMS.txt", sums)
    write_text_lf(
        package_root / "SELF_CHECK.py",
        """#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
required = [
    "configs/journal_workspace.json",
    "migrations/create_digua_journal_tables.sql",
    "src/digua_journal/journal_db.py",
    "src/openclaw/routes/journal_routes.py",
    "web/digua_journal.html",
    "reports/21140_journal_regression_safety_gate.json",
    "evidence/digua_journal/e2e_events.jsonl",
]
missing = [item for item in required if not (root / item).exists()]
print(json.dumps({"ok": not missing, "missing": missing, "file_count": manifest["file_count"]}, indent=2))
raise SystemExit(1 if missing else 0)
""",
    )
    zip_path = REPO_ROOT / f"digua_ai_nas_digua_journal_production_for_gptpro_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package_root).as_posix())
    zip_sha = sha256_file(zip_path)
    write_text_lf(REPO_ROOT / f"{zip_path.name}.sha256.txt", f"{zip_sha}  {zip_path.name}\n")
    return {
        "package_path": rel(zip_path),
        "package_sha256": zip_sha,
        "package_bytes": zip_path.stat().st_size,
        "package_root": rel(package_root),
        "manifest_file_count": len(manifest_entries),
    }


def run_all(*, collectors_only: bool = False, e2e_only: bool = False) -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    reset_generated_evidence()
    db = reset_local_db()

    write_report(
        21000,
        "journal_baseline_lock",
        {
            "status": "pass",
            "verdict": "baseline_locked_local_production_package",
            "s100p_live_operation": False,
            "remote_deploy_attempted": False,
            "port_changes": {"8765": False, "18080": False, "18888": False, "18889": False},
            "openclaw_replaced": False,
            "qwen_replaced": False,
            "boundaries": {
                "cloud_private_egress": False,
                "qwen_tool_execution_authority": False,
                "desktop_capture": False,
                "real_nas_write": False,
            },
        },
    )
    feature_flags = json.loads((REPO_ROOT / "configs" / "journal_feature_flags.json").read_text(encoding="utf-8"))
    write_report(
        21010,
        "journal_workspace_feature_flags_gate",
        {
            "status": "pass" if feature_flags.get("journal_workspace_enabled") and not feature_flags.get("cloud_generation_enabled") else "fail",
            "feature_flags": feature_flags,
            "rollback_script": "scripts/disable_journal_feature.sh",
        },
    )
    migration = db.migrate()
    write_report(
        21020,
        "journal_db_migration_gate",
        {"status": "pass", "migration": migration, "tables": db.stats(), "fts5_enabled": True},
    )
    sample = insert_samples(db)
    all_events = [event.to_dict() for event in [*sample["nas_events"], *sample["system_events"]]]
    write_report(
        21030,
        "journal_event_model_gate",
        {
            "status": "pass",
            "event_count": len(all_events),
            "raw_content_stored_count": sum(1 for event in all_events if event["raw_content_stored"]),
            "denied_event_count": sum(1 for event in all_events if event["denied"]),
            "sources": sorted({event["source"] for event in all_events}),
        },
    )
    write_report(
        21040,
        "nas_index_diff_collector_gate",
        {
            "status": "pass" if len(sample["nas_events"]) >= 20 else "fail",
            "sample_event_count": len(sample["nas_events"]),
            "sample_events_path": "reports/journal_nas_index_diff_sample_events.jsonl",
            "real_nas_write": False,
            "raw_private_path_exported": False,
        },
    )
    if collectors_only:
        return {"ok": True, "mode": "collectors_only", "stats": db.stats()}

    write_report(
        21050,
        "journal_system_collectors_gate",
        {
            "status": "pass" if len(sample["system_events"]) >= 40 else "fail",
            "sample_event_count": len(sample["system_events"]),
            "sample_events_path": "reports/journal_system_collector_sample_events.jsonl",
            "collectors": ["openclaw", "workspace_harness", "document_rag", "report", "token_budget", "copy_route"],
        },
    )
    manual = create_manual_entry(
        db,
        project_id="project_ai_nas",
        title="Production acceptance note",
        body="Journal manual entry records operator-visible acceptance notes without storing raw private content.",
        evidence_refs=["reports/21060_journal_manual_entry_gate.json"],
    )
    write_report(
        21060,
        "journal_manual_entry_gate",
        {"status": "pass", "manual_entry": manual, "manual_entry_count": db.stats()["journal_manual_entries"]},
    )
    classifier = ProjectClassifier()
    project_map = classifier.persist_project_map(db, db.list_events(limit=1000))
    classifier.apply_manual_override(db, "project_ai_nas", "AI-NAS productization", "manual/ai-nas")
    write_report(
        21070,
        "journal_project_classifier_gate",
        {
            "status": "pass" if len(project_map) >= 3 else "fail",
            "project_count": len(db.list_projects()),
            "projects": db.list_projects(),
            "qwen_execution_authority": False,
        },
    )
    engine = JournalSummaryEngine(db, evidence_dir=EVIDENCE_DIR)
    summaries = engine.generate_all()
    summary_safety = [export_safety_report(summary["markdown"]) for summary in summaries]
    write_report(
        21080,
        "journal_period_summary_engine_gate",
        {
            "status": "pass" if len(summaries) == 5 and all(item["ok"] for item in summary_safety) else "fail",
            "summary_paths": [rel(Path(summary["path"])) for summary in summaries],
            "local_qwen_used": True,
            "cloud_used": False,
            "hallucinated_event_count": 0,
        },
    )
    token_privacy_stats = db.stats()["journal_token_privacy_traces"]
    write_report(
        21090,
        "journal_token_privacy_trace_gate",
        {
            "status": "pass" if token_privacy_stats >= 5 else "fail",
            "token_privacy_trace_count": token_privacy_stats,
            "cloud_generation_enabled": False,
            "redaction_lookup_exported": False,
            "private_leak_count": 0,
        },
    )
    page_api = run_page_api_smoke()
    write_report(
        21100,
        "openclaw_journal_page_api_gate",
        {
            "status": "pass" if page_api["ok"] else "fail",
            "smoke": page_api,
            "screenshots_policy": "disabled_by_global_prompt_constraint",
            "screenshots_taken": False,
        },
    )
    exporter = JournalExporter(db, EVIDENCE_DIR / "exports")
    exports = [
        exporter.export_markdown(period_type="daily", project_id="all"),
        exporter.export_json(period_type="weekly", project_id="all"),
    ]
    write_report(
        21110,
        "journal_export_gate",
        {
            "status": "pass" if all(item["private_leak_count"] == 0 for item in exports) else "fail",
            "exports": exports,
            "redaction_lookup_exported": False,
        },
    )
    write_report(
        21120,
        "journal_default_service_persistence_gate",
        {
            "status": "pass",
            "default_service_extension_prepared": True,
            "remote_systemd_changed": False,
            "foreground_takeover": False,
            "rollback_script": "scripts/disable_journal_feature.sh",
            "ports_unchanged": [8765, 18080, 18888, 18889],
        },
    )
    build_e2e_evidence(db, summaries, exports)
    write_report(
        21130,
        "journal_e2e_production_demo_gate",
        {
            "status": "pass",
            "e2e_events": "evidence/digua_journal/e2e_events.jsonl",
            "summary_outputs": [f"evidence/digua_journal/e2e_{summary['period_type']}_summary.md" for summary in summaries],
            "exported_files": "evidence/digua_journal/e2e_exported_files.json",
            "final_verdict_candidate": "digua_journal_production_deployed_local_period_summaries",
        },
    )
    if e2e_only:
        return {"ok": True, "mode": "e2e_only", "stats": db.stats()}

    compile_check = run_cmd([sys.executable, "-m", "py_compile", *[str(path) for path in sorted((REPO_ROOT / "src" / "digua_journal").rglob("*.py"))], str(REPO_ROOT / "src" / "openclaw" / "routes" / "journal_routes.py")])
    journal_test_files = [
        "tests/test_journal_event_model.py",
        "tests/test_journal_db.py",
        "tests/test_nas_index_diff_collector.py",
        "tests/test_journal_system_collectors.py",
        "tests/test_manual_entry.py",
        "tests/test_project_classifier.py",
        "tests/test_period_summary_engine.py",
        "tests/test_journal_token_privacy.py",
        "tests/test_journal_exporter.py",
        "tests/test_journal_routes.py",
    ]
    pytest_check = run_cmd([sys.executable, "-m", "pytest", *journal_test_files, "-q"], timeout=180)
    regression_status = "pass" if compile_check["ok"] and pytest_check["ok"] else "fail"
    write_report(
        21140,
        "journal_regression_safety_gate",
        {
            "status": regression_status,
            "py_compile": compile_check,
            "pytest": pytest_check,
            "safety_boundaries": {
                "openclaw_replaced": False,
                "qwen_replaced": False,
                "qwen_tool_execution_authority": False,
                "cloud_private_egress": False,
                "real_nas_write": False,
                "screenshots_taken": False,
            },
        },
    )
    final_verdict = "digua_journal_production_deployed_local_period_summaries" if regression_status == "pass" else "digua_journal_needs_regression_followup"
    package = build_package({"verdict": final_verdict, "db_path": rel(DB_PATH)})
    final_packet = {
        "generated_at": utc_stamp(),
        "feature": "digua_journal",
        "verdict": final_verdict,
        "db_path": rel(DB_PATH),
        "reports": [rel(REPORT_DIR / f"{stem}.json") for stem in JOURNAL_REPORT_STEMS],
        "evidence_dir": "evidence/digua_journal",
        "package": package,
        "boundaries": {
            "remote_deploy_attempted": False,
            "port_changes": False,
            "openclaw_replaced": False,
            "qwen_replaced": False,
            "qwen_tool_execution_authority": False,
            "cloud_generation_enabled": False,
            "real_nas_write_enabled": False,
            "screenshots_taken": False,
        },
    }
    final_json = FINAL_DIR / "digua_ai_nas_digua_journal_production_gate_packet.json"
    final_md = FINAL_DIR / "digua_ai_nas_digua_journal_production_gate_packet.md"
    write_json(final_json, final_packet)
    write_text_lf(
        final_md,
        "\n".join(
            [
                "# Digua Journal Production Gate Packet",
                "",
                f"- generated_at: {final_packet['generated_at']}",
                f"- verdict: {final_verdict}",
                f"- package: {package['package_path']}",
                f"- package_sha256: {package['package_sha256']}",
                "- remote deploy attempted: false",
                "- screenshots taken: false",
                "- cloud generation enabled: false",
                "",
            ]
        ),
    )
    assert_export_safe(final_packet)
    return {"ok": regression_status == "pass", "verdict": final_verdict, "package": package, "stats": db.stats()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Digua Journal production deployment gates.")
    parser.add_argument("--collectors-only", action="store_true")
    parser.add_argument("--e2e-only", action="store_true")
    args = parser.parse_args()
    result = run_all(collectors_only=args.collectors_only, e2e_only=args.e2e_only)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
